"""Local stage execution over the existing backend, with digest-bound reuse.

Commands are trusted caller input, not instructions inferred from downloaded
records. This driver provides recovery and provenance, not an OS sandbox.
"""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import time
import uuid
from typing import Any, Mapping

from codex_science.artifact_store import stream_sha256
from codex_science.compute_backends import JobSpec, LocalBackend, TERMINAL_STATES


def read_json(path: Path) -> dict[str, Any]:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    result = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs,
                        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"nonfinite JSON: {value}")))
    if not isinstance(result, dict):
        raise ValueError("input must be a JSON object")
    return result


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def _save(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def confined_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("paths must be nonempty workspace-relative strings")
    if any(part in {"..", "."} for part in Path(relative).parts) or relative == ".":
        raise ValueError("parent and root paths are not allowed")
    if Path(relative).as_posix() != relative:
        raise ValueError("paths must use canonical relative spelling")
    candidate = root / relative
    for parent in (candidate, *candidate.parents):
        if parent == root:
            break
        if parent.is_symlink():
            raise ValueError(f"symlink path is not allowed: {relative}")
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"path escapes workspace: {relative}")
    return candidate


def capture_runtime_identity(executable: str, assets: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Hash actual executable and explicitly named model/database files."""
    if not isinstance(executable, str) or not executable:
        raise ValueError("executable must be a nonempty string")
    resolved = shutil.which(executable)
    if resolved is None:
        raise ValueError(f"executable unavailable: {executable}")
    path = Path(resolved).resolve()
    identity: dict[str, Any] = {"executable": str(path), "code_revision": "sha256:" + stream_sha256(path)[0]}
    if assets is not None and not isinstance(assets, Mapping):
        raise ValueError("assets must map names to files")
    digests = {}
    for name, filename in (assets or {}).items():
        if not isinstance(name, str) or not name or not isinstance(filename, str):
            raise ValueError("asset names and paths must be strings")
        asset = Path(filename)
        if not asset.is_file() or asset.is_symlink():
            raise ValueError(f"asset must be a regular file: {name}")
        digests[name] = {"path": str(asset.resolve()), "sha256": stream_sha256(asset)[0]}
    identity["assets"] = digests
    identity["fingerprint"] = fingerprint(identity)
    identity["evidence_boundary"] = "File identity only; transitive imports, undeclared assets and scientific validity are not established."
    return identity


def compare_runtime_identities(previous: Mapping[str, Any], current: Mapping[str, Any]) -> dict[str, Any]:
    changed = [name for name in ("executable", "code_revision", "assets") if previous.get(name) != current.get(name)]
    return {"changed": changed, "stale": bool(changed), "requires_revalidation": bool(changed)}


def _stages(payload: Mapping[str, Any], workspace: Path) -> list[dict[str, Any]]:
    if payload.get("schema") != "campaign-execution-v1":
        raise ValueError("unsupported campaign schema")
    raw = payload.get("stages")
    if not isinstance(raw, list) or not raw:
        raise ValueError("stages must be nonempty")
    stages = {}
    owners = {}
    for stage in raw:
        if not isinstance(stage, dict) or not isinstance(stage.get("id"), str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,47}", stage["id"]):
            raise ValueError("invalid stage ID")
        key = stage["id"]
        if key in stages:
            raise ValueError("duplicate stage ID")
        command = stage.get("command")
        if not isinstance(command, list) or not command or any(not isinstance(item, str) for item in command) or not command[0]:
            raise ValueError("command must be an argv array")
        normalized = dict(stage)
        assets = stage.get("assets", {})
        if not isinstance(assets, dict) or any(not isinstance(name, str) or not name or not isinstance(value, str) for name, value in assets.items()):
            raise ValueError("assets must map names to workspace-relative files")
        normalized["assets"] = assets
        for field in ("inputs", "outputs", "code", "depends_on"):
            value = stage.get(field, [])
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value) or len(set(value)) != len(value):
                raise ValueError(f"invalid {field}")
            normalized[field] = value
        if not normalized["outputs"]:
            raise ValueError("each stage must declare outputs")
        if "stdout_output" in stage and stage["stdout_output"] not in normalized["outputs"]:
            raise ValueError("stdout_output must be a declared output")
        if "approval_required" in stage and type(stage["approval_required"]) is not bool:
            raise ValueError("approval_required must be boolean")
        if "environment" in stage and not isinstance(stage["environment"], dict):
            raise ValueError("environment must be an object")
        for field in ("inputs", "outputs", "code"):
            for relative in normalized[field]:
                confined_path(workspace, relative)
        for relative in assets.values():
            confined_path(workspace, relative)
        for relative in normalized["outputs"]:
            if relative in owners:
                raise ValueError("stage output collision")
            owners[relative] = key
        timeout = stage.get("timeout_seconds", 60)
        if type(timeout) is not int or not 1 <= timeout <= 300:
            raise ValueError("local stage timeout must be 1..300 seconds")
        normalized["timeout_seconds"] = timeout
        stages[key] = normalized
    ordered = []
    ancestors: dict[str, set[str]] = {}
    while len(ordered) < len(stages):
        ready = [s for key, s in stages.items() if key not in ancestors and all(dep in ancestors for dep in s["depends_on"])]
        if not ready:
            raise ValueError("dependency cycle or unknown dependency")
        for stage in ready:
            key = stage["id"]
            ancestors[key] = set(stage["depends_on"])
            for dep in stage["depends_on"]:
                ancestors[key].update(ancestors[dep])
            ordered.append(stage)
    for stage in ordered:
        for relative in stage["inputs"] + stage["code"] + list(stage["assets"].values()):
            if relative in owners and owners[relative] not in ancestors[stage["id"]]:
                raise ValueError("produced input needs an explicit dependency")
        for output in stage["outputs"]:
            if any(output == item or output.startswith(item + "/") or item.startswith(output + "/")
                   for other in ordered for item in other["inputs"] + other["code"] + list(other["assets"].values()) if item not in owners):
                raise ValueError("output overlaps an external input or code")
    output_paths = sorted(owners)
    if any(right.startswith(left + "/") for left in output_paths for right in output_paths if left != right):
        raise ValueError("stage output paths overlap")
    return ordered


@contextmanager
def _driver_lock(state_dir: Path):
    with (state_dir / "driver.lock").open("a+") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("another campaign driver owns this state directory") from error
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def _file_digests(workspace: Path, paths: list[str]) -> dict[str, str]:
    result = {}
    for relative in paths:
        path = confined_path(workspace, relative)
        if not path.is_file():
            raise ValueError(f"required file unavailable: {relative}")
        result[relative] = stream_sha256(path)[0]
    return result


def _archive_outputs(workspace: Path, state_dir: Path, stage: Mapping[str, Any], nonce: str) -> None:
    destination = state_dir / "artifacts" / stage["id"] / nonce
    for relative in stage["outputs"]:
        source = confined_path(workspace, relative)
        if source.exists():
            if not source.is_file():
                raise ValueError("campaign outputs must be regular files")
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def run_campaign(payload: Mapping[str, Any], workspace: Path, state_dir: Path, *,
                 execute: bool = False, wait_seconds: float = 10, retry_failed: bool = False) -> dict[str, Any]:
    """Execute only caller-approved local argv; preserve attempts across calls.

    An interrupted submission without an identifiable backend job is ambiguous.
    It is never resubmitted automatically. Driver wait expiry leaves work alive.
    """
    if isinstance(wait_seconds, bool) or not isinstance(wait_seconds, (int, float)) or not 0 < wait_seconds <= 60:
        raise ValueError("wait_seconds must be 0 < value <= 60")
    workspace = workspace.resolve(strict=True)
    if not workspace.is_dir():
        raise ValueError("workspace must be a directory")
    stages = _stages(payload, workspace)
    if not execute:
        return {"schema": "campaign-execution-result-v1", "status": "planned", "executed": False,
                "stage_order": [stage["id"] for stage in stages]}
    state_dir = state_dir.resolve()
    if state_dir == workspace or any((workspace / output).is_relative_to(state_dir) or state_dir.is_relative_to(workspace / output)
                                     for stage in stages for output in stage["outputs"]):
        raise ValueError("state directory overlaps workspace outputs")
    state_dir.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + wait_seconds
    with _driver_lock(state_dir):
        return _drive(payload, workspace, state_dir, stages, deadline, retry_failed)


def _drive(payload, workspace, state_dir, stages, deadline, retry_failed):
    path = state_dir / "campaign.json"
    state = read_json(path) if path.exists() else {"schema": "campaign-driver-state-v1", "workspace": str(workspace), "stages": {}}
    if state.get("schema") != "campaign-driver-state-v1" or state.get("workspace") != str(workspace):
        raise ValueError("campaign state belongs to a different workspace")
    backend = LocalBackend(state_dir / "backend")
    active_ids = {stage["id"] for stage in stages}
    for old_id, old_attempts in state["stages"].items():
        if old_id not in active_ids and old_attempts and old_attempts[-1]["phase"] in {"submitting", "submitted"}:
            raise ValueError("unresolved stage removed or renamed; resume the original plan before changing its shape")
    results = {}
    signatures = {}
    plan_fingerprint = fingerprint(payload)
    invalidated = bool(state.get("plan_fingerprint") and state["plan_fingerprint"] != plan_fingerprint)
    state["plan_fingerprint"] = plan_fingerprint
    for stage in stages:
        key = stage["id"]
        if any(results[dep]["status"] not in {"completed", "reused"} for dep in stage["depends_on"]):
            results[key] = {"status": "blocked", "reason": "dependency incomplete"}
            continue
        assets = stage.get("assets", {})
        if not isinstance(assets, dict):
            raise ValueError("stage assets must map names to relative file paths")
        inputs = _file_digests(workspace, stage["inputs"] + stage["code"] + list(assets.values()))
        asset_paths = {name: str(confined_path(workspace, relative)) for name, relative in assets.items()}
        executable = stage["command"][0]
        if "/" in executable and not Path(executable).is_absolute():
            executable = str(confined_path(workspace, executable))
        identity = capture_runtime_identity(executable, asset_paths)
        signature = fingerprint({"stage": stage, "files": inputs, "runtime": identity,
                                 "dependencies": {dep: signatures[dep] for dep in stage["depends_on"]}})
        signatures[key] = signature
        attempts = state["stages"].setdefault(key, [])
        last = attempts[-1] if attempts else None
        if last and last["phase"] == "submitting":
            matches = []
            for spec_path in backend.jobs_dir.glob("*/spec.json"):
                if read_json(spec_path).get("name") == last["job_name"]:
                    matches.append(spec_path.parent.name)
            if len(matches) != 1:
                results[key] = {"status": "ambiguous", "reason": "interrupted submission requires reconciliation"}
                continue
            last.update(phase="submitted", job_id=matches[0])
            _save(path, state)
        if last and last["phase"] == "submitted":
            receipt = backend.status(last["job_id"])
            if last["signature"] != signature:
                if receipt["state"] not in TERMINAL_STATES:
                    results[key] = {"status": "blocked", "reason": "inputs changed while prior attempt is unresolved"}
                    continue
                last.update(phase="failed", reason="inputs changed before prior attempt was collected")
                _save(path, state)
        if last and last["phase"] == "completed" and last["signature"] == signature:
            receipt = backend.status(last["job_id"])
            try:
                unchanged = _file_digests(workspace, stage["outputs"]) == last["output_hashes"]
            except ValueError:
                unchanged = False
            if unchanged and receipt["state"] == "completed" and receipt["fingerprint"] == last["receipt_fingerprint"]:
                results[key] = {"status": "reused", "job_id": last["job_id"], "signature": signature}
                continue
        if not last or last["phase"] not in {"submitted"}:
            if last and last["phase"] == "failed" and not retry_failed:
                results[key] = {"status": "failed", "reason": "explicit retry required", "job_id": last["job_id"]}
                continue
            invalidated = invalidated or bool(attempts)
            nonce = uuid.uuid4().hex
            _archive_outputs(workspace, state_dir, stage, "before-" + nonce)
            command = [identity["executable"], *stage["command"][1:]]
            environment = {"OMP_NUM_THREADS": "1", **stage.get("environment", {})}
            spec = JobSpec.from_payload({"schema_version": 1, "backend": "local", "name": "campaign-" + key + "-" + nonce,
                "command": command, "working_directory": str(workspace), "environment": environment,
                "inherit_environment": False, "inputs": [{"id": item, "path": item, "sha256": digest} for item, digest in inputs.items()],
                "outputs": stage["outputs"], "resources": {"cpus": 1, "gpus": 0, "memory_mb": 1024,
                "wall_time_seconds": stage["timeout_seconds"]}, "timeout_seconds": stage["timeout_seconds"],
                "approval_required": stage.get("approval_required", False)})
            if spec.approval_required:
                raise ValueError("approval-gated stage must use its separately approved execution path")
            if not backend.preflight(spec)["ready"]:
                raise ValueError("stage backend preflight failed")
            for output in stage["outputs"]:
                confined_path(workspace, output).unlink(missing_ok=True)
            last = {"signature": signature, "phase": "submitting", "job_name": spec.name,
                    "runtime_identity": identity, "nonce": nonce}
            attempts.append(last)
            _save(path, state)
            receipt = backend.submit(spec)
            last.update(phase="submitted", job_id=receipt["job_id"])
            _save(path, state)
        remaining = deadline - time.monotonic()
        try:
            receipt = backend.wait(last["job_id"], timeout_seconds=max(remaining, 0.001), poll_seconds=0.02)
        except TimeoutError:
            results[key] = {"status": "running", "job_id": last["job_id"]}
            continue
        if receipt["state"] == "completed" and stage.get("stdout_output"):
            target = confined_path(workspace, stage["stdout_output"])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backend.jobs_dir / last["job_id"] / "stdout.log", target)
        receipt = backend.collect(last["job_id"])
        try:
            stable = _file_digests(workspace, list(inputs)) == inputs and capture_runtime_identity(executable, asset_paths) == identity
        except (ValueError, OSError):
            stable = False
        good = stable and receipt["state"] == "completed" and all(item["artifact_type"] == "file" for item in receipt["outputs"])
        if good:
            last.update(phase="completed", output_hashes=_file_digests(workspace, stage["outputs"]),
                        receipt_fingerprint=receipt["fingerprint"])
            _archive_outputs(workspace, state_dir, stage, last["nonce"])
        else:
            last.update(phase="failed", receipt_fingerprint=receipt["fingerprint"])
        _save(path, state)
        results[key] = {"status": "completed" if good else "failed", "job_id": last["job_id"], "signature": signature}
    complete = all(item["status"] in {"completed", "reused"} for item in results.values())
    return {"schema": "campaign-execution-result-v1", "status": "completed" if complete else "incomplete",
            "executed": True, "stages": results,
            "invalidated_review_receipts": payload.get("review_paths", []) if invalidated else [],
            "evidence_boundary": "Local command execution and file handoffs only; scientific controls and independent review remain separate."}
