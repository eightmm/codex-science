"""Durable local and Slurm scientific job execution contracts.

The local backend is fully executable. The Slurm backend submits only after an
explicit, hash-bound approval receipt and uses an existing scheduler
configuration. Neither backend invents credentials, installs software, or
interprets scientific success from a zero process exit code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Protocol

from codex_science.artifact_store import describe_directory, stream_sha256


TERMINAL_STATES = {"completed", "failed", "timed-out", "cancelled", "lost"}
ALL_STATES = {"submitted", "running", *TERMINAL_STATES}
SECRET_KEY_FRAGMENTS = {"token", "secret", "password", "credential", "private_key", "api_key", "apikey"}
SLURM_STATE_MAP = {
    "COMPLETED": "completed",
    "CANCELLED": "cancelled",
    "TIMEOUT": "timed-out",
    "FAILED": "failed",
    "NODE_FAIL": "failed",
    "OUT_OF_MEMORY": "failed",
    "PREEMPTED": "failed",
    "BOOT_FAIL": "failed",
    "DEADLINE": "timed-out",
    "RUNNING": "running",
    "PENDING": "submitted",
    "CONFIGURING": "submitted",
    "COMPLETING": "running",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _fingerprint(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".state-", suffix=".json", dir=path.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        temporary.write_text(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def _text(value: Any, label: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{label} is required")
    return text


def _safe_relative(value: Any, label: str) -> str:
    text = _text(value, label)
    pure = PurePosixPath(text)
    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"{label} must be a safe relative path")
    return pure.as_posix()


def _reject_secret_environment(environment: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in environment.items():
        key_text = _text(key, "environment key")
        normalized = key_text.lower()
        if any(fragment in normalized for fragment in SECRET_KEY_FRAGMENTS):
            raise ValueError(f"secret-like environment keys cannot be recorded in a job spec: {key_text}")
        result[key_text] = str(value)
    return result


def _sha(value: Any, label: str) -> str:
    digest = _text(value, label).lower()
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise ValueError(f"{label} must be a SHA-256 digest")
    return digest


def _normalize_inputs(value: Any) -> tuple[dict[str, Any], ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError("inputs must be a list")
    results: list[dict[str, Any]] = []
    ids: set[str] = set()
    for index, raw in enumerate(value):
        if not isinstance(raw, Mapping):
            raise ValueError(f"input {index} must be an object")
        item = dict(raw)
        input_id = _text(item.get("id", f"input-{index}"), f"input {index} id")
        if input_id in ids:
            raise ValueError(f"duplicate input ID: {input_id}")
        ids.add(input_id)
        item["id"] = input_id
        if item.get("path") is not None:
            item["path"] = _safe_relative(item["path"], f"input {input_id} path")
        elif not str(item.get("identifier", "")).strip():
            raise ValueError(f"input {input_id} needs path or identifier")
        if item.get("sha256") is not None:
            item["sha256"] = _sha(item["sha256"], f"input {input_id} sha256")
        if item.get("root_sha256") is not None:
            item["root_sha256"] = _sha(item["root_sha256"], f"input {input_id} root_sha256")
        results.append(item)
    return tuple(results)


def _input_preflight(spec: "JobSpec") -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    working = Path(spec.working_directory).resolve()
    for item in spec.inputs:
        input_id = str(item["id"])
        if item.get("path") is None:
            checks.append(
                {"name": f"input:{input_id}", "ready": True, "detail": "external identifier recorded"}
            )
            continue
        target = (working / str(item["path"])).resolve()
        if not target.is_relative_to(working):
            checks.append(
                {"name": f"input:{input_id}", "ready": False, "detail": "path escapes working directory"}
            )
            continue
        if not target.exists():
            checks.append({"name": f"input:{input_id}", "ready": False, "detail": "missing"})
            continue
        expected = item.get("sha256") or item.get("root_sha256")
        if expected is None:
            checks.append(
                {"name": f"input:{input_id}", "ready": True, "detail": "exists; no digest declared"}
            )
            continue
        if target.is_file():
            actual, _size = stream_sha256(target)
        elif target.is_dir():
            actual = describe_directory(target).root_sha256
        else:
            checks.append(
                {"name": f"input:{input_id}", "ready": False, "detail": "unsupported filesystem object"}
            )
            continue
        checks.append(
            {
                "name": f"input:{input_id}",
                "ready": actual == expected,
                "detail": "digest matches" if actual == expected else f"digest mismatch: {actual}",
            }
        )
    return checks


@dataclass(frozen=True)
class ResourceRequest:
    cpus: int = 1
    memory_mb: int = 1024
    gpus: int = 0
    gpu_type: str | None = None
    wall_time_seconds: int = 3600
    partition: str | None = None
    account: str | None = None
    qos: str | None = None

    def validate(self) -> None:
        for field in ("cpus", "memory_mb", "wall_time_seconds"):
            value = int(getattr(self, field))
            if value < 1:
                raise ValueError(f"resource {field} must be positive")
        if self.gpus < 0:
            raise ValueError("resource gpus must be non-negative")

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any] | None) -> "ResourceRequest":
        source = dict(payload or {})
        request = cls(
            cpus=int(source.get("cpus", 1)),
            memory_mb=int(source.get("memory_mb", 1024)),
            gpus=int(source.get("gpus", 0)),
            gpu_type=None if source.get("gpu_type") is None else str(source["gpu_type"]),
            wall_time_seconds=int(source.get("wall_time_seconds", 3600)),
            partition=None if source.get("partition") is None else str(source["partition"]),
            account=None if source.get("account") is None else str(source["account"]),
            qos=None if source.get("qos") is None else str(source["qos"]),
        )
        request.validate()
        return request


@dataclass(frozen=True)
class JobSpec:
    schema_version: int
    backend: str
    name: str
    command: tuple[str, ...]
    working_directory: str
    environment: dict[str, str]
    inherit_environment: bool
    inputs: tuple[dict[str, Any], ...]
    outputs: tuple[str, ...]
    resources: ResourceRequest
    timeout_seconds: int
    cost_cap: float | None
    approval_required: bool
    scientific_run_id: str | None
    checkpoint_paths: tuple[str, ...]

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "JobSpec":
        if payload.get("schema_version", 1) != 1:
            raise ValueError("unsupported job spec schema")
        backend = _text(payload.get("backend"), "backend")
        if backend not in {"local", "slurm"}:
            raise ValueError(f"unsupported job backend: {backend}")
        command_raw = payload.get("command")
        if not isinstance(command_raw, list) or not command_raw:
            raise ValueError("command must be a non-empty argv list")
        command = tuple(_text(item, "command item") for item in command_raw)
        environment_raw = payload.get("environment", {})
        if not isinstance(environment_raw, Mapping):
            raise ValueError("environment must be an object")
        inputs_raw = payload.get("inputs", [])
        outputs_raw = payload.get("outputs", [])
        if not isinstance(outputs_raw, list):
            raise ValueError("outputs must be a list")
        checkpoints_raw = payload.get("checkpoint_paths", [])
        if not isinstance(checkpoints_raw, list):
            raise ValueError("checkpoint_paths must be a list")
        timeout = int(payload.get("timeout_seconds", 3600))
        if timeout < 1:
            raise ValueError("timeout_seconds must be positive")
        cost_cap = None if payload.get("cost_cap") is None else float(payload["cost_cap"])
        if cost_cap is not None and cost_cap < 0:
            raise ValueError("cost_cap must be non-negative")
        spec = cls(
            schema_version=1,
            backend=backend,
            name=_text(payload.get("name"), "name"),
            command=command,
            working_directory=str(Path(_text(payload.get("working_directory"), "working_directory")).resolve()),
            environment=_reject_secret_environment(environment_raw),
            inherit_environment=bool(payload.get("inherit_environment", True)),
            inputs=_normalize_inputs(inputs_raw),
            outputs=tuple(_safe_relative(item, "output") for item in outputs_raw),
            resources=ResourceRequest.from_payload(payload.get("resources") if isinstance(payload.get("resources"), Mapping) else None),
            timeout_seconds=timeout,
            cost_cap=cost_cap,
            approval_required=bool(payload.get("approval_required", backend != "local")),
            scientific_run_id=None if payload.get("scientific_run_id") is None else str(payload["scientific_run_id"]),
            checkpoint_paths=tuple(_safe_relative(item, "checkpoint path") for item in checkpoints_raw),
        )
        spec.validate()
        return spec

    def validate(self) -> None:
        if self.backend not in {"local", "slurm"}:
            raise ValueError("unsupported backend")
        if not self.command:
            raise ValueError("job command cannot be empty")
        self.resources.validate()
        working = Path(self.working_directory)
        if not working.is_dir():
            raise ValueError(f"working_directory is not a directory: {working}")
        for item in self.inputs:
            if not str(item.get("id", item.get("path", ""))).strip():
                raise ValueError("each input needs id or path")
            if item.get("sha256") is not None:
                digest = str(item["sha256"]).lower()
                if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
                    raise ValueError("input sha256 is invalid")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["command"] = list(self.command)
        payload["inputs"] = [dict(item) for item in self.inputs]
        payload["outputs"] = list(self.outputs)
        payload["checkpoint_paths"] = list(self.checkpoint_paths)
        return payload

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.to_dict())


class JobBackend(Protocol):
    def preflight(self, spec: JobSpec) -> dict[str, Any]: ...
    def submit(self, spec: JobSpec, *, approval: Mapping[str, Any] | None = None) -> dict[str, Any]: ...
    def status(self, job_id: str) -> dict[str, Any]: ...
    def cancel(self, job_id: str) -> dict[str, Any]: ...
    def collect(self, job_id: str) -> dict[str, Any]: ...


def build_approval_receipt(spec: JobSpec, *, approved_by: str, target: str, approved_at: str | None = None) -> dict[str, Any]:
    material = {
        "schema_version": 1,
        "job_spec_sha256": spec.fingerprint,
        "backend": spec.backend,
        "target": _text(target, "target"),
        "approved_by": _text(approved_by, "approved_by"),
        "approved_at": approved_at or _now(),
        "approved": True,
        "resource_cap": asdict(spec.resources),
        "cost_cap": spec.cost_cap,
        "evidence_boundary": "Approval authorizes the described execution boundary; it does not endorse the scientific method or result.",
    }
    return {**material, "fingerprint": _fingerprint(material)}


def validate_approval_receipt(receipt: Mapping[str, Any], spec: JobSpec) -> None:
    if receipt.get("schema_version") != 1 or receipt.get("approved") is not True:
        raise ValueError("valid explicit approval receipt is required")
    if receipt.get("job_spec_sha256") != spec.fingerprint or receipt.get("backend") != spec.backend:
        raise ValueError("approval receipt covers a different job spec")
    material = dict(receipt)
    fingerprint = str(material.pop("fingerprint", "")).lower()
    if _fingerprint(material) != fingerprint:
        raise ValueError("approval receipt fingerprint mismatch")


def _state_material(spec: JobSpec, *, job_id: str, state: str, submitted_at: str, **updates: Any) -> dict[str, Any]:
    if state not in ALL_STATES:
        raise ValueError(f"invalid job state: {state}")
    payload = {
        "schema_version": 1,
        "job_id": job_id,
        "backend": spec.backend,
        "name": spec.name,
        "scientific_run_id": spec.scientific_run_id,
        "job_spec_sha256": spec.fingerprint,
        "state": state,
        "submitted_at": submitted_at,
        "started_at": None,
        "finished_at": None,
        "exit_code": None,
        "failure_class": None,
        "worker_pid": None,
        "scheduler_job_id": None,
        "stdout_path": "stdout.log",
        "stderr_path": "stderr.log",
        "resource_request": asdict(spec.resources),
        "resource_usage": {},
        "cost": None,
        "checkpoint_paths": list(spec.checkpoint_paths),
        "outputs": [],
        "message": "",
        "updated_at": _now(),
    }
    payload.update(updates)
    material = dict(payload)
    payload["fingerprint"] = _fingerprint(material)
    return payload


def validate_job_state(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != 1 or payload.get("state") not in ALL_STATES:
        raise ValueError("invalid job state record")
    for field in ("job_id", "backend", "name", "job_spec_sha256", "submitted_at", "updated_at"):
        _text(payload.get(field), field)
    material = dict(payload)
    fingerprint = str(material.pop("fingerprint", "")).lower()
    if _fingerprint(material) != fingerprint:
        raise ValueError("job state fingerprint mismatch")


def _process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class LocalBackend:
    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir.resolve()
        self.jobs_dir = self.state_dir / "jobs"

    def _job_dir(self, job_id: str) -> Path:
        safe = _text(job_id, "job_id")
        if any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for character in safe):
            raise ValueError("job_id contains unsafe characters")
        return self.jobs_dir / safe

    def preflight(self, spec: JobSpec) -> dict[str, Any]:
        spec.validate()
        executable = shutil.which(spec.command[0]) if not Path(spec.command[0]).is_absolute() else spec.command[0]
        checks = [
            {
                "name": "working-directory",
                "ready": Path(spec.working_directory).is_dir(),
                "detail": spec.working_directory,
            },
            {"name": "executable", "ready": executable is not None, "detail": executable or "not found"},
            {
                "name": "resource-request-recorded",
                "ready": True,
                "detail": asdict(spec.resources),
            },
        ]
        checks.extend(_input_preflight(spec))
        return {
            "schema_version": 1,
            "backend": "local",
            "ready": all(check["ready"] for check in checks),
            "checks": checks,
            "executable": executable,
            "working_directory": spec.working_directory,
            "job_spec_sha256": spec.fingerprint,
            "resource_request": asdict(spec.resources),
            "warnings": ["Local resource requests are recorded but are not a scheduler-enforced reservation."],
        }

    def submit(self, spec: JobSpec, *, approval: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if spec.backend != "local":
            raise ValueError("LocalBackend requires backend=local")
        preflight = self.preflight(spec)
        if not preflight["ready"]:
            raise ValueError("local preflight failed")
        if spec.approval_required:
            if approval is None:
                raise ValueError("job spec requires explicit approval")
            validate_approval_receipt(approval, spec)
        job_id = "local-" + uuid.uuid4().hex[:20]
        job_dir = self._job_dir(job_id)
        job_dir.mkdir(parents=True)
        _atomic_json(job_dir / "spec.json", spec.to_dict())
        submitted_at = _now()
        initial = _state_material(spec, job_id=job_id, state="submitted", submitted_at=submitted_at)
        _atomic_json(job_dir / "state.json", initial)
        worker_environment = os.environ.copy()
        source_root = str(Path(__file__).resolve().parents[1])
        existing_pythonpath = worker_environment.get("PYTHONPATH", "")
        worker_environment["PYTHONPATH"] = source_root + (
            os.pathsep + existing_pythonpath if existing_pythonpath else ""
        )
        process = subprocess.Popen(
            [sys.executable, "-m", "codex_science.compute_backends", "_worker", str(job_dir)],
            env=worker_environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
        current = _read_json(job_dir / "state.json")
        submitted_receipt = _state_material(
            spec,
            job_id=job_id,
            state="submitted",
            submitted_at=submitted_at,
            worker_pid=process.pid,
            message="local worker started",
        )
        if current.get("state") == "submitted":
            _atomic_json(job_dir / "state.json", submitted_receipt)
        return submitted_receipt

    def status(self, job_id: str) -> dict[str, Any]:
        job_dir = self._job_dir(job_id)
        state = _read_json(job_dir / "state.json")
        validate_job_state(state)
        if state["state"] in {"submitted", "running"} and state.get("worker_pid") and not _process_alive(int(state["worker_pid"])):
            # Give an atomically-written terminal state a short chance to land.
            time.sleep(0.05)
            state = _read_json(job_dir / "state.json")
            validate_job_state(state)
            if state["state"] in {"submitted", "running"}:
                spec = JobSpec.from_payload(_read_json(job_dir / "spec.json"))
                state = _state_material(
                    spec,
                    job_id=job_id,
                    state="lost",
                    submitted_at=str(state["submitted_at"]),
                    started_at=state.get("started_at"),
                    finished_at=_now(),
                    worker_pid=state.get("worker_pid"),
                    failure_class="worker-lost",
                    message="local worker exited without a terminal receipt",
                )
                _atomic_json(job_dir / "state.json", state)
        return state

    def wait(self, job_id: str, *, timeout_seconds: float, poll_seconds: float = 0.2) -> dict[str, Any]:
        if timeout_seconds <= 0 or poll_seconds <= 0:
            raise ValueError("wait timeout and poll interval must be positive")
        deadline = time.monotonic() + timeout_seconds
        while True:
            state = self.status(job_id)
            if state["state"] in TERMINAL_STATES:
                return state
            if time.monotonic() >= deadline:
                raise TimeoutError(f"job did not reach a terminal state within {timeout_seconds} seconds")
            time.sleep(poll_seconds)

    def cancel(self, job_id: str) -> dict[str, Any]:
        job_dir = self._job_dir(job_id)
        state = self.status(job_id)
        if state["state"] in TERMINAL_STATES:
            return state
        pid = int(state.get("worker_pid") or 0)
        if pid > 0 and _process_alive(pid):
            try:
                os.killpg(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        spec = JobSpec.from_payload(_read_json(job_dir / "spec.json"))
        cancelled = _state_material(
            spec,
            job_id=job_id,
            state="cancelled",
            submitted_at=str(state["submitted_at"]),
            started_at=state.get("started_at"),
            finished_at=_now(),
            worker_pid=pid or None,
            failure_class="user-cancelled",
            message="job cancelled",
        )
        _atomic_json(job_dir / "state.json", cancelled)
        return cancelled

    def collect(self, job_id: str) -> dict[str, Any]:
        job_dir = self._job_dir(job_id)
        state = self.status(job_id)
        if state["state"] not in TERMINAL_STATES:
            raise ValueError("cannot collect a nonterminal job")
        spec = JobSpec.from_payload(_read_json(job_dir / "spec.json"))
        root = Path(spec.working_directory).resolve()
        outputs: list[dict[str, Any]] = []
        for relative in spec.outputs:
            path = (root / relative).resolve()
            if not path.is_relative_to(root):
                raise ValueError(f"output escapes working directory: {relative}")
            if path.is_dir():
                descriptor = describe_directory(path)
                outputs.append({"path": relative, "artifact_type": "directory-tree", "sha256": descriptor.root_sha256, "size_bytes": descriptor.total_bytes, "entry_count": descriptor.entry_count})
            elif path.is_file():
                digest, size = stream_sha256(path)
                outputs.append({"path": relative, "artifact_type": "file", "sha256": digest, "size_bytes": size, "entry_count": 1})
            else:
                outputs.append({"path": relative, "artifact_type": "missing", "sha256": None, "size_bytes": None, "entry_count": 0})
        state = dict(state)
        state.pop("fingerprint", None)
        state["outputs"] = outputs
        state["updated_at"] = _now()
        state["fingerprint"] = _fingerprint(state)
        _atomic_json(job_dir / "state.json", state)
        return state


def _worker(job_dir: Path) -> int:
    spec = JobSpec.from_payload(_read_json(job_dir / "spec.json"))
    initial = _read_json(job_dir / "state.json")
    job_id = str(initial["job_id"])
    submitted_at = str(initial["submitted_at"])
    worker_pid = os.getpid()
    running = _state_material(spec, job_id=job_id, state="running", submitted_at=submitted_at, started_at=_now(), worker_pid=worker_pid, message="command running")
    _atomic_json(job_dir / "state.json", running)
    environment = os.environ.copy() if spec.inherit_environment else {}
    environment.update(spec.environment)
    stdout_path = job_dir / "stdout.log"
    stderr_path = job_dir / "stderr.log"
    started_monotonic = time.monotonic()
    state = "failed"
    exit_code: int | None = None
    failure_class: str | None = None
    message = ""
    try:
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            completed = subprocess.run(
                list(spec.command),
                cwd=spec.working_directory,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                timeout=spec.timeout_seconds,
                check=False,
            )
        exit_code = int(completed.returncode)
        state = "completed" if exit_code == 0 else "failed"
        failure_class = None if exit_code == 0 else "nonzero-exit"
        message = "command exited successfully" if exit_code == 0 else f"command exited with code {exit_code}"
    except subprocess.TimeoutExpired:
        state = "timed-out"
        failure_class = "wall-time"
        message = f"command exceeded timeout_seconds={spec.timeout_seconds}"
    except FileNotFoundError as error:
        state = "failed"
        failure_class = "executable-not-found"
        message = str(error)
    except BaseException as error:
        state = "failed"
        failure_class = "worker-exception"
        message = f"{type(error).__name__}: {error}"
    final = _state_material(
        spec,
        job_id=job_id,
        state=state,
        submitted_at=submitted_at,
        started_at=running["started_at"],
        finished_at=_now(),
        exit_code=exit_code,
        failure_class=failure_class,
        worker_pid=worker_pid,
        resource_usage={"wall_seconds": round(time.monotonic() - started_monotonic, 6)},
        message=message,
    )
    _atomic_json(job_dir / "state.json", final)
    return 0 if state == "completed" else 1


class SlurmBackend:
    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir.resolve()
        self.jobs_dir = self.state_dir / "jobs"

    def _job_dir(self, job_id: str) -> Path:
        safe = _text(job_id, "job_id")
        if any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for character in safe):
            raise ValueError("job_id contains unsafe characters")
        return self.jobs_dir / safe

    def preflight(self, spec: JobSpec) -> dict[str, Any]:
        spec.validate()
        tools = {name: shutil.which(name) for name in ("sbatch", "squeue", "sacct", "scancel")}
        checks = [
            {
                "name": "working-directory",
                "ready": Path(spec.working_directory).is_dir(),
                "detail": spec.working_directory,
            },
            {"name": "sbatch", "ready": tools["sbatch"] is not None, "detail": tools["sbatch"] or "not found"},
            {"name": "scancel", "ready": tools["scancel"] is not None, "detail": tools["scancel"] or "not found"},
            {
                "name": "status-command",
                "ready": tools["sacct"] is not None or tools["squeue"] is not None,
                "detail": tools["sacct"] or tools["squeue"] or "not found",
            },
        ]
        checks.extend(_input_preflight(spec))
        return {
            "schema_version": 1,
            "backend": "slurm",
            "ready": all(check["ready"] for check in checks),
            "checks": checks,
            "tools": tools,
            "job_spec_sha256": spec.fingerprint,
            "resource_request": asdict(spec.resources),
            "warnings": [] if tools["sacct"] else ["sacct is unavailable; terminal accounting may be incomplete."],
        }

    def render_script(self, spec: JobSpec, *, job_id: str) -> str:
        if spec.backend != "slurm":
            raise ValueError("SlurmBackend requires backend=slurm")
        resources = spec.resources
        hours, remainder = divmod(resources.wall_time_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        directives = [
            f"#SBATCH --job-name={spec.name}",
            f"#SBATCH --cpus-per-task={resources.cpus}",
            f"#SBATCH --mem={resources.memory_mb}M",
            f"#SBATCH --time={hours:02d}:{minutes:02d}:{seconds:02d}",
            f"#SBATCH --output={shlex.quote(str(self._job_dir(job_id) / 'stdout.log'))}",
            f"#SBATCH --error={shlex.quote(str(self._job_dir(job_id) / 'stderr.log'))}",
        ]
        if resources.gpus:
            gres = f"gpu:{resources.gpu_type}:{resources.gpus}" if resources.gpu_type else f"gpu:{resources.gpus}"
            directives.append(f"#SBATCH --gres={gres}")
        for flag, value in (("partition", resources.partition), ("account", resources.account), ("qos", resources.qos)):
            if value:
                directives.append(f"#SBATCH --{flag}={value}")
        exports = "\n".join(f"export {shlex.quote(key)}={shlex.quote(value)}" for key, value in sorted(spec.environment.items()))
        command = shlex.join(spec.command)
        return "\n".join([
            "#!/usr/bin/env bash",
            *directives,
            "set -euo pipefail",
            f"cd {shlex.quote(spec.working_directory)}",
            exports,
            f"timeout --signal=TERM {spec.timeout_seconds}s {command}",
            "",
        ])

    def submit(self, spec: JobSpec, *, approval: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if spec.backend != "slurm":
            raise ValueError("SlurmBackend requires backend=slurm")
        if approval is None:
            raise ValueError("Slurm submission requires explicit approval")
        validate_approval_receipt(approval, spec)
        preflight = self.preflight(spec)
        if not preflight["ready"]:
            raise ValueError("Slurm preflight failed")
        job_id = "slurm-local-" + uuid.uuid4().hex[:16]
        job_dir = self._job_dir(job_id)
        job_dir.mkdir(parents=True)
        _atomic_json(job_dir / "spec.json", spec.to_dict())
        script_path = job_dir / "job.sh"
        script_path.write_text(self.render_script(spec, job_id=job_id), encoding="utf-8")
        script_path.chmod(0o700)
        completed = subprocess.run(["sbatch", "--parsable", str(script_path)], text=True, capture_output=True, check=False)
        if completed.returncode != 0:
            raise ValueError(f"sbatch failed: {completed.stderr.strip() or completed.stdout.strip()}")
        scheduler_job_id = completed.stdout.strip().split(";", 1)[0]
        if not scheduler_job_id:
            raise ValueError("sbatch returned no scheduler job ID")
        submitted_at = _now()
        state = _state_material(spec, job_id=job_id, state="submitted", submitted_at=submitted_at, scheduler_job_id=scheduler_job_id, message="submitted to Slurm")
        _atomic_json(job_dir / "state.json", state)
        return state

    def status(self, job_id: str) -> dict[str, Any]:
        job_dir = self._job_dir(job_id)
        state = _read_json(job_dir / "state.json")
        validate_job_state(state)
        if state["state"] in TERMINAL_STATES:
            return state
        scheduler_job_id = str(state.get("scheduler_job_id") or "")
        raw_state = ""
        exit_code = None
        if shutil.which("sacct"):
            completed = subprocess.run(["sacct", "-n", "-P", "-j", scheduler_job_id, "--format=State,ExitCode,Elapsed,MaxRSS"], text=True, capture_output=True, check=False)
            first = next((line for line in completed.stdout.splitlines() if line.strip()), "")
            if first:
                fields = first.split("|")
                raw_state = fields[0].split("+", 1)[0].strip().upper()
                if len(fields) > 1 and fields[1]:
                    try:
                        exit_code = int(fields[1].split(":", 1)[0])
                    except ValueError:
                        exit_code = None
        if not raw_state and shutil.which("squeue"):
            completed = subprocess.run(["squeue", "-h", "-j", scheduler_job_id, "-o", "%T"], text=True, capture_output=True, check=False)
            raw_state = completed.stdout.strip().splitlines()[0].upper() if completed.stdout.strip() else ""
        if not raw_state:
            return state
        mapped = SLURM_STATE_MAP.get(raw_state, "running")
        spec = JobSpec.from_payload(_read_json(job_dir / "spec.json"))
        updated = _state_material(
            spec,
            job_id=job_id,
            state=mapped,
            submitted_at=str(state["submitted_at"]),
            started_at=state.get("started_at") or (_now() if mapped == "running" else None),
            finished_at=_now() if mapped in TERMINAL_STATES else None,
            exit_code=exit_code,
            failure_class=None if mapped == "completed" else (raw_state.lower() if mapped in TERMINAL_STATES else None),
            scheduler_job_id=scheduler_job_id,
            message=f"Slurm state {raw_state}",
        )
        _atomic_json(job_dir / "state.json", updated)
        return updated

    def cancel(self, job_id: str) -> dict[str, Any]:
        job_dir = self._job_dir(job_id)
        state = self.status(job_id)
        if state["state"] in TERMINAL_STATES:
            return state
        completed = subprocess.run(["scancel", str(state["scheduler_job_id"])], text=True, capture_output=True, check=False)
        if completed.returncode != 0:
            raise ValueError(f"scancel failed: {completed.stderr.strip() or completed.stdout.strip()}")
        spec = JobSpec.from_payload(_read_json(job_dir / "spec.json"))
        cancelled = _state_material(
            spec,
            job_id=job_id,
            state="cancelled",
            submitted_at=str(state["submitted_at"]),
            started_at=state.get("started_at"),
            finished_at=_now(),
            scheduler_job_id=state.get("scheduler_job_id"),
            failure_class="user-cancelled",
            message="Slurm job cancellation requested",
        )
        _atomic_json(job_dir / "state.json", cancelled)
        return cancelled

    def collect(self, job_id: str) -> dict[str, Any]:
        # Shared-filesystem Slurm output collection uses the same hash contract
        # as local execution. Remote object transfer belongs to a separate,
        # approved staging route.
        state = self.status(job_id)
        if state["state"] not in TERMINAL_STATES:
            raise ValueError("cannot collect a nonterminal Slurm job")
        local = LocalBackend(self.state_dir)
        return local.collect(job_id)


def load_spec(path: Path) -> JobSpec:
    return JobSpec.from_payload(_read_json(path))


def backend_for(name: str, state_dir: Path) -> JobBackend:
    if name == "local":
        return LocalBackend(state_dir)
    if name == "slurm":
        return SlurmBackend(state_dir)
    raise ValueError(f"unsupported backend: {name}")


def _worker_main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] != "_worker":
        raise ValueError("invalid worker invocation")
    return _worker(Path(argv[1]).resolve())


if __name__ == "__main__":
    raise SystemExit(_worker_main(sys.argv[1:]))
