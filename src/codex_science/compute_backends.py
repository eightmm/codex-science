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
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterator, Mapping, Protocol

try:
    import fcntl
except ImportError:
    fcntl = None

from codex_science.artifact_store import describe_directory, stream_sha256
from codex_science.source_snapshot import (
    SOURCE_ARCHIVE_NAME,
    SOURCE_RECEIPT_NAME,
    SourceSnapshotError,
    create_git_source_bundle,
    materialize_source_bundle,
    materialized_working_directory,
    preflight_git_source,
    validate_source_receipt,
)


_LOCAL_PROCESSES: dict[int, subprocess.Popen[bytes]] = {}


def _reap_local_process(pid: int) -> None:
    process = _LOCAL_PROCESSES.get(pid)
    if process is None:
        return
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        return
    _LOCAL_PROCESSES.pop(pid, None)


TERMINAL_STATES = {"completed", "failed", "timed-out", "cancelled", "lost"}
ALL_STATES = {"submitted", "running", *TERMINAL_STATES}
SECRET_KEY_FRAGMENTS = {"token", "secret", "password", "credential", "private_key", "api_key", "apikey"}
SLURM_SAFE_TOKEN_CHARACTERS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:@/+,-"
)
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


def _slurm_token(value: Any, label: str) -> str:
    text = _text(value, label)
    if any(character not in SLURM_SAFE_TOKEN_CHARACTERS for character in text):
        raise ValueError(f"{label} must be a newline-free Slurm-safe token")
    return text


def _slurm_directive_path(value: Path, label: str) -> str:
    text = str(value)
    if any(ord(character) < 32 or ord(character) == 127 for character in text):
        raise ValueError(f"{label} must not contain control characters")
    return text


def _required_tool(name: str) -> str:
    resolved = shutil.which(name)
    if resolved is None:
        raise ValueError(f"required execution tool is unavailable: {name}")
    return str(Path(resolved).resolve())


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


def _normalize_source_snapshot(value: Any) -> dict[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("source_snapshot must be an object")
    if set(value) != {"mode", "commit"} or value.get("mode") != "git-archive":
        raise ValueError("source_snapshot must contain only mode=git-archive and commit")
    commit = str(value.get("commit", "")).strip().lower()
    if len(commit) not in {40, 64} or any(character not in "0123456789abcdef" for character in commit):
        raise ValueError("source_snapshot commit must be an exact 40- or 64-hex Git object ID")
    return {"mode": "git-archive", "commit": commit}


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
    source_snapshot: dict[str, str] | None = None

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
            source_snapshot=_normalize_source_snapshot(payload.get("source_snapshot")),
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
        if self.source_snapshot is None:
            payload.pop("source_snapshot", None)
        return payload

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.to_dict())


def _validate_slurm_directive_tokens(spec: JobSpec) -> None:
    _slurm_token(spec.name, "Slurm job name")
    for label, value in (
        ("Slurm partition", spec.resources.partition),
        ("Slurm account", spec.resources.account),
        ("Slurm qos", spec.resources.qos),
        ("Slurm gpu_type", spec.resources.gpu_type),
    ):
        if value is not None:
            _slurm_token(value, label)


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


def _read_job_state(job_dir: Path) -> dict[str, Any]:
    try:
        return _read_json(job_dir / "state.json")
    except FileNotFoundError:
        script = job_dir / "job.sh"
        if not (job_dir / "spec.json").is_file() or not script.is_file():
            raise
        prefix = "#SBATCH --job-name="
        name = next(
            (line[len(prefix):] for line in script.read_text(encoding="utf-8").splitlines() if line.startswith(prefix)),
            "<unavailable>",
        )
        raise ValueError(
            f"Slurm job directory {job_dir} has no state.json; submission may have reached the scheduler. "
            f"Look up {prefix}{name} with squeue/sacct before retrying."
        ) from None


@contextmanager
def _job_state_lock(job_dir: Path) -> Iterator[None]:
    if fcntl is None:
        raise ValueError("job state publication requires POSIX file locking")
    lock_path = job_dir / ".state.lock"
    # This inode must survive every atomic state replacement and every caller.
    # Closing the descriptor releases the lock even on a failed publication.
    try:
        descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    except OSError as error:
        raise ValueError(f"job state lock must be a regular non-symlink file: {lock_path}") from error
    try:
        try:
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode):
                raise ValueError(f"job state lock must be a regular non-symlink file: {lock_path}")
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            current = lock_path.stat(follow_symlinks=False)
            if (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
                raise ValueError(f"job state lock changed during acquisition: {lock_path}")
        except OSError as error:
            raise ValueError(f"cannot acquire job state lock: {lock_path}") from error
        yield
    finally:
        os.close(descriptor)


def _publish_job_state(
    job_dir: Path, payload: Mapping[str, Any], *, collection: bool = False
) -> dict[str, Any]:
    with _job_state_lock(job_dir):
        return _publish_job_state_locked(job_dir, payload, collection=collection)


def _publish_job_state_locked(
    job_dir: Path, payload: Mapping[str, Any], *, collection: bool = False
) -> dict[str, Any]:
    validate_job_state(payload)
    try:
        current = _read_json(job_dir / "state.json")
    except FileNotFoundError:
        current = None
    if current is not None:
        validate_job_state(current)
        if collection:
            updated = dict(current)
            updated["outputs"] = payload["outputs"]
            if "source_collection_error" in payload:
                updated["source_collection_error"] = payload["source_collection_error"]
            updated["updated_at"] = _now()
            updated.pop("fingerprint", None)
            updated["fingerprint"] = _fingerprint(updated)
            payload = updated
        elif current["state"] in TERMINAL_STATES or (
            current["state"] == "running" and payload["state"] == "submitted"
        ):
            return current
        elif payload["state"] == "lost" and (
            not current.get("worker_pid") or _process_alive(int(current["worker_pid"]))
        ):
            return current
    _atomic_json(job_dir / "state.json", payload)
    return dict(payload)


def _source_preflight(spec: JobSpec) -> dict[str, Any] | None:
    if spec.source_snapshot is None:
        return None
    return preflight_git_source(
        Path(spec.working_directory),
        spec.source_snapshot["commit"],
        spec.inputs,
    )


def _prepare_source_snapshot(spec: JobSpec, job_dir: Path) -> dict[str, Any] | None:
    if spec.source_snapshot is None:
        return None
    job_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{job_dir.name}-source-", dir=job_dir.parent))
    temporary.chmod(0o700)
    try:
        receipt = create_git_source_bundle(
            working_directory=Path(spec.working_directory),
            commit=spec.source_snapshot["commit"],
            inputs=spec.inputs,
            job_spec_sha256=spec.fingerprint,
            job_dir=temporary,
            allowed_untracked_path=temporary,
        )
        _atomic_json(temporary / SOURCE_RECEIPT_NAME, receipt)
        os.replace(temporary, job_dir)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)
    return receipt


def _source_state_update(state: Mapping[str, Any]) -> dict[str, Any]:
    receipt = state.get("source_receipt")
    return {"source_receipt": dict(receipt)} if isinstance(receipt, Mapping) else {}


def _load_source_receipt(job_dir: Path, spec: JobSpec, state: Mapping[str, Any]) -> dict[str, Any] | None:
    if spec.source_snapshot is None:
        return None
    state_receipt = state.get("source_receipt")
    if not isinstance(state_receipt, Mapping):
        raise SourceSnapshotError("strict job state is missing its source receipt")
    recorded = _read_json(job_dir / SOURCE_RECEIPT_NAME)
    if dict(state_receipt) != recorded:
        raise SourceSnapshotError("job state and saved source receipts differ")
    validated = validate_source_receipt(recorded, expected_job_spec_sha256=spec.fingerprint)
    if validated["commit"] != spec.source_snapshot["commit"]:
        raise SourceSnapshotError("source receipt commit differs from the job spec")
    expected_input_ids = [str(item["id"]) for item in spec.inputs]
    if validated["input_ids"] != expected_input_ids:
        raise SourceSnapshotError("source receipt inputs differ from the job spec")
    return validated


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
        if spec.source_snapshot is None:
            checks.extend(_input_preflight(spec))
        else:
            source_check = _source_preflight(spec)
            assert source_check is not None
            checks.append(source_check)
        warnings = ["Local resource requests are recorded but are not a scheduler-enforced reservation."]
        if spec.source_snapshot is not None:
            warnings.append(
                "Source isolation covers the initial working directory and declared path inputs only; "
                "absolute paths, inherited environments, external services, and out-of-tree writes remain non-hermetic."
            )
        return {
            "schema_version": 1,
            "backend": "local",
            "ready": all(check["ready"] for check in checks),
            "checks": checks,
            "executable": executable,
            "working_directory": spec.working_directory,
            "job_spec_sha256": spec.fingerprint,
            "resource_request": asdict(spec.resources),
            "warnings": warnings,
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
        source_receipt = _prepare_source_snapshot(spec, job_dir)
        if source_receipt is None:
            job_dir.mkdir(parents=True)
        _atomic_json(job_dir / "spec.json", spec.to_dict())
        submitted_at = _now()
        source_update = {} if source_receipt is None else {"source_receipt": source_receipt}
        initial = _state_material(
            spec,
            job_id=job_id,
            state="submitted",
            submitted_at=submitted_at,
            **source_update,
        )
        worker_environment = os.environ.copy()
        source_root = str(Path(__file__).resolve().parents[1])
        existing_pythonpath = worker_environment.get("PYTHONPATH", "")
        worker_environment["PYTHONPATH"] = source_root + (
            os.pathsep + existing_pythonpath if existing_pythonpath else ""
        )
        with _job_state_lock(job_dir):
            _publish_job_state_locked(job_dir, initial)
            process = subprocess.Popen(
                [sys.executable, "-m", "codex_science.compute_backends", "_worker", str(job_dir)],
                env=worker_environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                close_fds=True,
            )
        _LOCAL_PROCESSES[process.pid] = process
        current = _read_json(job_dir / "state.json")
        submitted_receipt = _state_material(
            spec,
            job_id=job_id,
            state="submitted",
            submitted_at=submitted_at,
            worker_pid=process.pid,
            message="local worker started",
            **source_update,
        )
        if current.get("state") == "submitted":
            _publish_job_state(job_dir, submitted_receipt)
        return submitted_receipt

    def status(self, job_id: str) -> dict[str, Any]:
        job_dir = self._job_dir(job_id)
        state = _read_job_state(job_dir)
        validate_job_state(state)
        if state["state"] in TERMINAL_STATES and state.get("worker_pid"):
            _reap_local_process(int(state["worker_pid"]))
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
                    **_source_state_update(state),
                )
                state = _publish_job_state(job_dir, state)
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
        state = _read_job_state(job_dir)
        validate_job_state(state)
        if state["state"] in TERMINAL_STATES:
            return state
        with _job_state_lock(job_dir):
            state = _read_job_state(job_dir)
            validate_job_state(state)
            if state["state"] in TERMINAL_STATES:
                return state
            pid = int(state.get("worker_pid") or 0)
            spec = JobSpec.from_payload(_read_json(job_dir / "spec.json"))
            # Signal the group even if its leader has exited but children remain.
            if pid > 0:
                try:
                    os.killpg(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                except OSError as error:
                    raise ValueError(f"local cancellation failed: {error}") from error
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
                **_source_state_update(state),
            )
            return _publish_job_state_locked(job_dir, cancelled)

    def collect(self, job_id: str) -> dict[str, Any]:
        job_dir = self._job_dir(job_id)
        state = self.status(job_id)
        if state["state"] not in TERMINAL_STATES:
            raise ValueError("cannot collect a nonterminal job")
        spec = JobSpec.from_payload(_read_json(job_dir / "spec.json"))
        root: Path | None
        source_collection_error: str | None = None
        try:
            source_receipt = _load_source_receipt(job_dir, spec, state)
            root = (
                Path(spec.working_directory).resolve()
                if source_receipt is None
                else materialized_working_directory(job_dir, source_receipt)
            )
        except SourceSnapshotError as error:
            incomplete_source_attempt = spec.source_snapshot is not None and state["state"] != "completed"
            if not incomplete_source_attempt:
                raise
            root = None
            source_collection_error = str(error)
        outputs: list[dict[str, Any]] = []
        for relative in spec.outputs:
            if root is None:
                outputs.append(
                    {
                        "path": relative,
                        "artifact_type": "missing",
                        "sha256": None,
                        "size_bytes": None,
                        "entry_count": 0,
                    }
                )
                continue
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
        if source_collection_error is not None:
            state["source_collection_error"] = source_collection_error
        state["updated_at"] = _now()
        state["fingerprint"] = _fingerprint(state)
        return _publish_job_state(job_dir, state, collection=True)


def _worker(job_dir: Path) -> int:
    spec = JobSpec.from_payload(_read_json(job_dir / "spec.json"))
    initial = _read_json(job_dir / "state.json")
    validate_job_state(initial)
    job_id = str(initial["job_id"])
    submitted_at = str(initial["submitted_at"])
    worker_pid = os.getpid()
    running = _state_material(
        spec,
        job_id=job_id,
        state="running",
        submitted_at=submitted_at,
        started_at=_now(),
        worker_pid=worker_pid,
        message="command running",
        **_source_state_update(initial),
    )
    running = _publish_job_state(job_dir, running)
    if running["state"] in TERMINAL_STATES:
        return 0 if running["state"] == "completed" else 1
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
        source_receipt = _load_source_receipt(job_dir, spec, initial)
        execution_directory = (
            Path(spec.working_directory)
            if source_receipt is None
            else materialize_source_bundle(
                job_dir,
                source_receipt,
                expected_job_spec_sha256=spec.fingerprint,
            )
        )
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            completed = subprocess.run(
                list(spec.command),
                cwd=execution_directory,
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
    except SourceSnapshotError as error:
        state = "failed"
        failure_class = "source-integrity"
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
        **_source_state_update(initial),
    )
    final = _publish_job_state(job_dir, final)
    return 0 if final["state"] == "completed" else 1


class SlurmBackend:
    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir.resolve()
        _slurm_directive_path(self.state_dir, "Slurm state directory")
        self.jobs_dir = self.state_dir / "jobs"

    def _job_dir(self, job_id: str) -> Path:
        safe = _text(job_id, "job_id")
        if any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for character in safe):
            raise ValueError("job_id contains unsafe characters")
        return self.jobs_dir / safe

    def preflight(self, spec: JobSpec) -> dict[str, Any]:
        spec.validate()
        _validate_slurm_directive_tokens(spec)
        tool_names = ["sbatch", "squeue", "sacct", "scancel"]
        if spec.source_snapshot is not None:
            tool_names.extend(
                ["bash", "head", "mkdir", "mktemp", "rm", "sha256sum", "stat", "tar", "timeout", "wc"]
            )
        tools = {name: shutil.which(name) for name in tool_names}
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
        if spec.source_snapshot is not None:
            checks.extend(
                {"name": name, "ready": tools[name] is not None, "detail": tools[name] or "not found"}
                for name in (
                    "bash",
                    "head",
                    "mkdir",
                    "mktemp",
                    "rm",
                    "sha256sum",
                    "stat",
                    "tar",
                    "timeout",
                    "wc",
                )
            )
        if spec.source_snapshot is None:
            checks.extend(_input_preflight(spec))
        else:
            source_check = _source_preflight(spec)
            assert source_check is not None
            checks.append(source_check)
        warnings = [] if tools["sacct"] else ["sacct is unavailable; terminal accounting may be incomplete."]
        if spec.source_snapshot is not None:
            warnings.append(
                "Source isolation covers the initial working directory and declared path inputs only; "
                "absolute paths, inherited environments, external services, and out-of-tree writes remain non-hermetic."
            )
        return {
            "schema_version": 1,
            "backend": "slurm",
            "ready": all(check["ready"] for check in checks),
            "checks": checks,
            "tools": tools,
            "job_spec_sha256": spec.fingerprint,
            "resource_request": asdict(spec.resources),
            "warnings": warnings,
        }

    def render_script(
        self,
        spec: JobSpec,
        *,
        job_id: str,
        source_receipt: Mapping[str, Any] | None = None,
    ) -> str:
        if spec.backend != "slurm":
            raise ValueError("SlurmBackend requires backend=slurm")
        spec.validate()
        _validate_slurm_directive_tokens(spec)
        resources = spec.resources
        hours, remainder = divmod(resources.wall_time_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        stdout_path = _slurm_directive_path(self._job_dir(job_id) / "stdout.log", "Slurm stdout path")
        stderr_path = _slurm_directive_path(self._job_dir(job_id) / "stderr.log", "Slurm stderr path")
        directives = [
            f"#SBATCH --job-name={spec.name}",
            f"#SBATCH --cpus-per-task={resources.cpus}",
            f"#SBATCH --mem={resources.memory_mb}M",
            f"#SBATCH --time={hours:02d}:{minutes:02d}:{seconds:02d}",
            f"#SBATCH --output={shlex.quote(stdout_path)}",
            f"#SBATCH --error={shlex.quote(stderr_path)}",
        ]
        if resources.gpus:
            gres = f"gpu:{resources.gpu_type}:{resources.gpus}" if resources.gpu_type else f"gpu:{resources.gpus}"
            directives.append(f"#SBATCH --gres={gres}")
        for flag, value in (("partition", resources.partition), ("account", resources.account), ("qos", resources.qos)):
            if value:
                directives.append(f"#SBATCH --{flag}={value}")
        exports = "\n".join(f"export {shlex.quote(key)}={shlex.quote(value)}" for key, value in sorted(spec.environment.items()))
        command = shlex.join(spec.command)
        shebang = "#!/usr/bin/env bash"
        shell_options = "set -euo pipefail"
        timeout_command = "timeout"
        setup = [f"cd {shlex.quote(spec.working_directory)}"]
        preview_marker: list[str] = []
        if spec.source_snapshot is not None:
            bash_tool = _required_tool("bash")
            timeout_tool = _required_tool("timeout")
            shebang = f"#!{bash_tool} -p"
            shell_options = "builtin set -euo pipefail"
            timeout_command = shlex.quote(timeout_tool)
            if source_receipt is None:
                preview_marker = ["# PREVIEW ONLY: fail-closed source hash and size placeholders follow"]
                source_check = _source_preflight(spec)
                detail = source_check.get("detail") if isinstance(source_check, Mapping) else None
                relative_cwd = (
                    str(detail.get("worktree_relative_cwd", "__invalid_source_snapshot__"))
                    if isinstance(detail, Mapping)
                    else "__invalid_source_snapshot__"
                )
                expected_sha256 = "0" * 64
                expected_size = 0
            else:
                validated = validate_source_receipt(
                    source_receipt,
                    expected_job_spec_sha256=spec.fingerprint,
                )
                if validated["commit"] != spec.source_snapshot["commit"]:
                    raise SourceSnapshotError("source receipt commit differs from the job spec")
                expected_input_ids = [str(item["id"]) for item in spec.inputs]
                if validated["input_ids"] != expected_input_ids:
                    raise SourceSnapshotError("source receipt inputs differ from the job spec")
                relative_cwd = str(validated["worktree_relative_cwd"])
                expected_sha256 = str(validated["archive"]["sha256"])
                expected_size = int(validated["archive"]["size_bytes"])
            job_dir = self._job_dir(job_id)
            archive_path = job_dir / SOURCE_ARCHIVE_NAME
            source_root = job_dir / "source"
            snapshot_cwd = source_root.joinpath(*PurePosixPath(relative_cwd).parts)
            strict_tools = {
                name: _required_tool(name)
                for name in ("head", "mkdir", "mktemp", "rm", "sha256sum", "stat", "tar", "wc")
            }
            source_copy_timeout = max(30, (expected_size + 1024 * 1024 - 1) // (1024 * 1024))
            setup = [
                'saved_umask="$(builtin umask)"',
                "builtin umask 077",
                "builtin unset TAR_OPTIONS",
                f"head_tool={shlex.quote(strict_tools['head'])}",
                f"mkdir_tool={shlex.quote(strict_tools['mkdir'])}",
                f"mktemp_tool={shlex.quote(strict_tools['mktemp'])}",
                f"rm_tool={shlex.quote(strict_tools['rm'])}",
                f"sha256sum_tool={shlex.quote(strict_tools['sha256sum'])}",
                f"stat_tool={shlex.quote(strict_tools['stat'])}",
                f"tar_tool={shlex.quote(strict_tools['tar'])}",
                f"timeout_tool={shlex.quote(timeout_tool)}",
                f"wc_tool={shlex.quote(strict_tools['wc'])}",
                f"source_archive={shlex.quote(str(archive_path))}",
                f"source_root={shlex.quote(str(source_root))}",
                f"expected_source_sha256={shlex.quote(expected_sha256)}",
                f"expected_source_size={expected_size}",
                f"source_copy_timeout={source_copy_timeout}",
                f"source_copy=\"$(\"$mktemp_tool\" {shlex.quote(str(job_dir / '.source-copy.XXXXXX'))})\"",
                'builtin trap \'"$rm_tool" -f -- "$source_copy"\' EXIT',
                '[[ -f "$source_archive" && ! -L "$source_archive" ]]',
                'actual_source_size="$("$timeout_tool" --signal=TERM "${source_copy_timeout}s" "$stat_tool" -Lc %s -- "$source_archive")"',
                '[[ "$actual_source_size" -eq "$expected_source_size" ]]',
                '"$timeout_tool" --signal=TERM "${source_copy_timeout}s" "$head_tool" -c "$expected_source_size" -- "$source_archive" > "$source_copy"',
                '[[ "$("$stat_tool" -Lc %s -- "$source_archive")" -eq "$expected_source_size" ]]',
                'builtin exec {source_fd}<"$source_copy"',
                '"$rm_tool" -f -- "$source_copy"',
                'source_fd_path="/proc/$$/fd/$source_fd"',
                '[[ "$("$wc_tool" -c < "$source_fd_path")" -eq "$expected_source_size" ]]',
                'builtin read -r actual_source_sha256 _ < <("$sha256sum_tool" "$source_fd_path")',
                '[[ "$actual_source_sha256" = "$expected_source_sha256" ]]',
                '[[ ! -e "$source_root" ]]',
                '"$mkdir_tool" "$source_root"',
                'TAR_OPTIONS= "$tar_tool" -xpf "$source_fd_path" -C "$source_root"',
                'builtin exec {source_fd}<&-',
                'builtin trap - EXIT',
                'builtin umask "$saved_umask"',
                f"builtin cd {shlex.quote(str(snapshot_cwd))}",
            ]
        return "\n".join([
            shebang,
            *directives,
            *preview_marker,
            shell_options,
            *setup,
            exports,
            f"{timeout_command} --signal=TERM {spec.timeout_seconds}s {command}",
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
        source_receipt = _prepare_source_snapshot(spec, job_dir)
        if source_receipt is None:
            job_dir.mkdir(parents=True)
        _atomic_json(job_dir / "spec.json", spec.to_dict())
        script_path = job_dir / "job.sh"
        script_path.write_text(
            self.render_script(spec, job_id=job_id, source_receipt=source_receipt),
            encoding="utf-8",
        )
        script_path.chmod(0o700)
        with _job_state_lock(job_dir):
            completed = subprocess.run(["sbatch", "--parsable", str(script_path)], text=True, capture_output=True, check=False)
            if completed.returncode != 0:
                raise ValueError(f"sbatch failed: {completed.stderr.strip() or completed.stdout.strip()}")
            scheduler_job_id = completed.stdout.strip().split(";", 1)[0]
            if not scheduler_job_id:
                raise ValueError("sbatch returned no scheduler job ID")
            submitted_at = _now()
            source_update = {} if source_receipt is None else {"source_receipt": source_receipt}
            state = _state_material(
                spec,
                job_id=job_id,
                state="submitted",
                submitted_at=submitted_at,
                scheduler_job_id=scheduler_job_id,
                message="submitted to Slurm",
                **source_update,
            )
            return _publish_job_state_locked(job_dir, state)

    def status(self, job_id: str) -> dict[str, Any]:
        job_dir = self._job_dir(job_id)
        state = _read_job_state(job_dir)
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
            **_source_state_update(state),
        )
        return _publish_job_state(job_dir, updated)

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
            **_source_state_update(state),
        )
        return _publish_job_state(job_dir, cancelled)

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
