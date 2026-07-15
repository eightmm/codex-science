"""Durable control state for autonomous Codex Science runs."""

from __future__ import annotations

import json
import hashlib
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


CHECKPOINT_FILE = "checkpoint.json"
MAX_ATTEMPTS_PER_FAILURE = 3
STATES = {
    "active",
    "approval_required",
    "waiting_external",
    "blocked",
    "abandoned",
    "complete",
}
NONTERMINAL_STATES = {"active", "approval_required", "waiting_external", "blocked"}
STEP_STATUSES = {"pending", "in_progress", "completed"}
CRITERION_STATUSES = {"pending", "satisfied"}
SESSION_KEY_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
MAX_AUTOCONTINUE_CHECKPOINT_BYTES = 1_000_000
MAX_AUTOCONTINUE_RUNS = 1_000
MAX_ARTIFACT_SCAN_DIRECTORIES = 10_000
DEFAULT_CONTINUATION_BUDGET = 100
IGNORED_ARTIFACT_SCAN_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "__pycache__",
    "node_modules",
    "venv",
}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _nonempty(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _nonnegative_integer(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _positive_integer(value: object, field: str) -> int:
    value = _nonnegative_integer(value, field)
    if value < 1:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _validate_steps(checkpoint: dict[str, Any]) -> None:
    steps = checkpoint["steps"]
    if not isinstance(steps, list) or not steps:
        raise ValueError("steps must contain at least one item")
    identifiers: set[str] = set()
    in_progress: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            raise ValueError("each step must be an object")
        identifier = _nonempty(step.get("id"), "step id")
        _nonempty(step.get("title"), "step title")
        if identifier in identifiers:
            raise ValueError(f"duplicate step id: {identifier}")
        identifiers.add(identifier)
        if step.get("status") not in STEP_STATUSES:
            raise ValueError(f"invalid status for step {identifier}")
        if step["status"] == "in_progress":
            in_progress.append(identifier)

    current_step = checkpoint["current_step"]
    if current_step is not None and current_step not in identifiers:
        raise ValueError("current_step must identify a planned step")
    if len(in_progress) > 1:
        raise ValueError("only one step may be in progress")
    if in_progress != ([] if current_step is None else [current_step]):
        raise ValueError("current_step must match the in-progress step")


def _validate_legacy_criteria(criteria: object) -> None:
    if not isinstance(criteria, list) or not criteria:
        raise ValueError("done_criteria must contain at least one item")
    for criterion in criteria:
        _nonempty(criterion, "done criterion")


def _validate_v3_criteria(criteria: object) -> None:
    if not isinstance(criteria, list) or not criteria:
        raise ValueError("done_criteria must contain at least one item")
    identifiers: set[str] = set()
    for criterion in criteria:
        if not isinstance(criterion, dict):
            raise ValueError("each done criterion must be an object")
        identifier = _nonempty(criterion.get("id"), "criterion id")
        _nonempty(criterion.get("text"), "criterion text")
        if identifier in identifiers:
            raise ValueError(f"duplicate criterion id: {identifier}")
        identifiers.add(identifier)
        if criterion.get("status") not in CRITERION_STATUSES:
            raise ValueError(f"invalid criterion status: {identifier}")
        evidence_refs = criterion.get("evidence_refs")
        if not isinstance(evidence_refs, list):
            raise ValueError(f"criterion evidence_refs must be a list: {identifier}")
        for evidence_ref in evidence_refs:
            _nonempty(evidence_ref, "criterion evidence ref")
        evidence_sha256 = criterion.get("evidence_sha256", {})
        if not isinstance(evidence_sha256, dict):
            raise ValueError(f"criterion evidence_sha256 must be an object: {identifier}")
        for evidence_ref, digest in evidence_sha256.items():
            _nonempty(evidence_ref, "criterion evidence digest ref")
            if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
                raise ValueError(f"invalid criterion evidence digest: {identifier}")
        if criterion["status"] == "satisfied" and not evidence_refs:
            raise ValueError(f"satisfied criterion requires evidence: {identifier}")
        if criterion["status"] == "satisfied" and set(evidence_sha256) != set(evidence_refs):
            raise ValueError(f"satisfied criterion requires a digest for every evidence ref: {identifier}")


def _validate_attempts_and_decisions(checkpoint: dict[str, Any]) -> None:
    if not isinstance(checkpoint["attempts"], list):
        raise ValueError("attempts must be a list")
    for attempt in checkpoint["attempts"]:
        if not isinstance(attempt, dict):
            raise ValueError("each attempt must be an object")
        for field in ("failure_class", "approach", "outcome", "recorded_at"):
            _nonempty(attempt.get(field), f"attempt {field}")
    if not isinstance(checkpoint["pending_decisions"], list):
        raise ValueError("pending_decisions must be a list")
    for decision in checkpoint["pending_decisions"]:
        if not isinstance(decision, dict):
            raise ValueError("each pending decision must be an object")
        _nonempty(decision.get("question"), "decision question")
        _nonempty(decision.get("reason"), "decision reason")


def _validate_outer_goal(outer_goal: object, state: str, schema_version: int) -> None:
    if not isinstance(outer_goal, dict):
        raise ValueError("outer_goal must be an object")
    mode = outer_goal.get("mode")
    phase = outer_goal.get("phase")
    if mode not in {"none", "native"}:
        raise ValueError("outer_goal mode must be none or native")
    if schema_version == 3:
        if mode == "none" and phase != "not_applicable":
            raise ValueError("non-native outer_goal must be not_applicable")
        if mode == "native" and phase not in {
            "running",
            "completion_pending",
            "host_reported_complete",
        }:
            raise ValueError("invalid native outer_goal phase")
        if state == "complete" and mode == "native" and phase != "host_reported_complete":
            raise ValueError("native completion requires host_reported_complete")
        if phase == "host_reported_complete" and state != "complete":
            raise ValueError("host_reported_complete requires complete state")
        if phase == "completion_pending" and state != "active":
            raise ValueError("completion_pending requires active state")
        return

    task_key = outer_goal.get("task_key")
    receipt = outer_goal.get("receipt")
    if mode == "none":
        if phase != "not_applicable" or task_key is not None or receipt is not None:
            raise ValueError("non-native outer_goal must be not_applicable and unbound")
    else:
        if not isinstance(task_key, str) or not SESSION_KEY_PATTERN.fullmatch(task_key):
            raise ValueError("native outer_goal task_key must be a SHA-256 digest")
        if phase not in {"running", "completion_pending", "host_completion_attested"}:
            raise ValueError("invalid native outer_goal phase")
        if receipt is not None:
            if not isinstance(receipt, dict):
                raise ValueError("outer_goal receipt must be null or an object")
            for field in ("artifact_ref", "recorded_at"):
                _nonempty(receipt.get(field), f"outer_goal receipt {field}")
            if not isinstance(receipt.get("artifact_sha256"), str) or not SHA256_PATTERN.fullmatch(
                receipt["artifact_sha256"]
            ):
                raise ValueError("outer_goal receipt artifact_sha256 must be a SHA-256 digest")
        if state == "complete" and phase != "host_completion_attested":
            raise ValueError("native completion requires host_completion_attested")
        if phase == "host_completion_attested" and (state != "complete" or receipt is None):
            raise ValueError("host_completion_attested requires complete state and receipt")
        if phase != "host_completion_attested" and receipt is not None:
            raise ValueError("outer_goal receipt requires host_completion_attested")
    if phase == "completion_pending" and state != "active":
        raise ValueError("completion_pending requires active state")


def validate_checkpoint(checkpoint: dict[str, Any]) -> None:
    """Validate the checkpoint schema and state invariants."""
    required = {
        "schema_version",
        "goal",
        "deliverable",
        "done_criteria",
        "steps",
        "state",
        "current_step",
        "next_action",
        "attempts",
        "pending_decisions",
        "blocker",
        "updated_at",
    }
    missing = sorted(required - checkpoint.keys())
    if missing:
        raise ValueError(f"missing checkpoint fields: {', '.join(missing)}")
    schema_version = checkpoint["schema_version"]
    if schema_version not in {1, 2, 3, 4}:
        raise ValueError("unsupported checkpoint schema version")
    if schema_version >= 2:
        version_two_fields = {"session_key", "continuation_count", "idle_continuations"}
        missing_v2 = sorted(version_two_fields - checkpoint.keys())
        if missing_v2:
            raise ValueError(f"missing checkpoint fields: {', '.join(missing_v2)}")
        if not SESSION_KEY_PATTERN.fullmatch(str(checkpoint["session_key"])):
            raise ValueError("session_key must be a 64-character lowercase SHA-256 digest")
        _nonnegative_integer(checkpoint["continuation_count"], "continuation_count")
        _nonnegative_integer(checkpoint["idle_continuations"], "idle_continuations")
    if schema_version >= 3:
        version_three_fields = {
            "continuation_budget",
            "outer_goal",
            "review_receipt",
            "wait",
            "termination_reason",
            "revision",
        }
        missing_v3 = sorted(version_three_fields - checkpoint.keys())
        if missing_v3:
            raise ValueError(f"missing checkpoint fields: {', '.join(missing_v3)}")
        _positive_integer(checkpoint["continuation_budget"], "continuation_budget")
        _nonnegative_integer(checkpoint["revision"], "revision")

    _nonempty(checkpoint["goal"], "goal")
    _nonempty(checkpoint["deliverable"], "deliverable")
    if schema_version >= 3:
        _validate_v3_criteria(checkpoint["done_criteria"])
    else:
        _validate_legacy_criteria(checkpoint["done_criteria"])
    _validate_steps(checkpoint)

    state = checkpoint["state"]
    allowed_states = STATES if schema_version >= 3 else {"active", "approval_required", "blocked", "complete"}
    if state not in allowed_states:
        raise ValueError(f"invalid checkpoint state: {state}")
    if not isinstance(checkpoint["next_action"], str):
        raise ValueError("next_action must be a string")
    _validate_attempts_and_decisions(checkpoint)
    if not isinstance(checkpoint["blocker"], str):
        raise ValueError("blocker must be a string")
    _nonempty(checkpoint["updated_at"], "updated_at")

    if schema_version >= 3:
        _validate_outer_goal(checkpoint["outer_goal"], state, schema_version)
        review = checkpoint["review_receipt"]
        if review is not None:
            if not isinstance(review, dict):
                raise ValueError("review_receipt must be null or an object")
            for field in ("reviewer", "verdict", "artifact_ref", "recorded_at"):
                _nonempty(review.get(field), f"review {field}")
            if not isinstance(review.get("artifact_sha256"), str) or not SHA256_PATTERN.fullmatch(
                review["artifact_sha256"]
            ):
                raise ValueError("review artifact_sha256 must be a SHA-256 digest")
            if review["verdict"] not in {"passed", "failed"}:
                raise ValueError("review verdict must be passed or failed")
            independence_field = "independence_attested" if schema_version >= 4 else "independent"
            if not isinstance(review.get(independence_field), bool):
                raise ValueError(f"review {independence_field} must be boolean")
        wait = checkpoint["wait"]
        if wait is not None:
            if not isinstance(wait, dict):
                raise ValueError("wait must be null or an object")
            for field in ("reason", "next_action", "terminal_rule", "recorded_at"):
                _nonempty(wait.get(field), f"wait {field}")
            _positive_integer(wait.get("poll_interval_seconds"), "wait poll_interval_seconds")
        if not isinstance(checkpoint["termination_reason"], str):
            raise ValueError("termination_reason must be a string")

    if state == "active" and not checkpoint["next_action"].strip():
        raise ValueError("an active checkpoint requires next_action")
    if state == "approval_required" and not checkpoint["pending_decisions"]:
        raise ValueError("approval_required requires pending_decisions")
    if state == "waiting_external" and checkpoint.get("wait") is None:
        raise ValueError("waiting_external requires wait metadata")
    if state == "blocked" and not checkpoint["blocker"].strip():
        raise ValueError("blocked requires blocker")
    if state == "abandoned" and not checkpoint.get("termination_reason", "").strip():
        raise ValueError("abandoned requires termination_reason")
    if state in {"complete", "abandoned"}:
        if state == "complete" and any(step["status"] != "completed" for step in checkpoint["steps"]):
            raise ValueError("complete requires every step to be completed")
        if checkpoint["current_step"] is not None or checkpoint["next_action"]:
            raise ValueError(f"{state} cannot have a current step or next action")
        if checkpoint["pending_decisions"] or checkpoint["blocker"]:
            raise ValueError(f"{state} cannot retain a gate or blocker")
    if schema_version >= 3 and (
        state == "complete" or checkpoint["outer_goal"]["phase"] == "completion_pending"
    ):
        if any(step["status"] != "completed" for step in checkpoint["steps"]):
            raise ValueError("verified completion requires every step to be completed")
        if any(item["status"] != "satisfied" for item in checkpoint["done_criteria"]):
            raise ValueError("verified completion requires every criterion to be satisfied")
        review = checkpoint["review_receipt"]
        independence_field = "independence_attested" if schema_version >= 4 else "independent"
        if not review or review["verdict"] != "passed" or not review[independence_field]:
            raise ValueError("verified completion requires a passed independent review")


def _write_checkpoint(run_dir: Path, checkpoint: dict[str, Any]) -> dict[str, Any]:
    validate_checkpoint(checkpoint)
    run_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = run_dir / CHECKPOINT_FILE
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(temporary, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(checkpoint, indent=2, sort_keys=True) + "\n")
        temporary.replace(path)
        path.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)
    return checkpoint


def _touch(checkpoint: dict[str, Any]) -> None:
    if checkpoint["schema_version"] >= 3:
        checkpoint["revision"] += 1
    checkpoint["updated_at"] = _timestamp()


def load_checkpoint(run_dir: Path) -> dict[str, Any]:
    """Load and validate a run checkpoint."""
    path = Path(run_dir) / CHECKPOINT_FILE
    checkpoint = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(checkpoint, dict):
        raise ValueError("checkpoint root must be an object")
    validate_checkpoint(checkpoint)
    return checkpoint


def _iter_checkpoints(artifacts: Path) -> Iterable[tuple[Path, dict[str, Any]]]:
    if artifacts.is_symlink():
        return
    try:
        run_dirs = tuple(artifacts.iterdir())
    except (FileNotFoundError, NotADirectoryError, PermissionError):
        return
    for index, run_dir in enumerate(run_dirs):
        if index >= MAX_AUTOCONTINUE_RUNS:
            break
        if run_dir.is_symlink() or not run_dir.is_dir():
            continue
        path = run_dir / CHECKPOINT_FILE
        try:
            metadata = path.lstat()
            if (
                path.is_symlink()
                or not stat.S_ISREG(metadata.st_mode)
                or metadata.st_size > MAX_AUTOCONTINUE_CHECKPOINT_BYTES
            ):
                continue
            checkpoint = load_checkpoint(run_dir)
        except (FileNotFoundError, PermissionError, OSError, UnicodeError, ValueError, json.JSONDecodeError):
            continue
        yield run_dir, checkpoint


def _has_git_marker(directory: Path) -> bool:
    marker = directory / ".git"
    if marker.is_dir():
        return (marker / "HEAD").is_file()
    if marker.is_file():
        try:
            return marker.read_text(encoding="utf-8", errors="strict").lstrip().startswith("gitdir:")
        except (OSError, UnicodeError):
            return False
    return False


def _ensure_single_nonterminal(run_dir: Path, session_key: str) -> None:
    run_dir = Path(run_dir).resolve()
    workspace = run_dir.parent.parent if run_dir.parent.name == "artifacts" else run_dir.parent
    for artifacts in _related_artifact_roots(workspace):
        artifacts = artifacts.resolve()
        for candidate, checkpoint in _iter_checkpoints(artifacts):
            if candidate.resolve() == run_dir:
                continue
            if (
                checkpoint.get("schema_version", 1) >= 2
                and checkpoint.get("session_key") == session_key
                and checkpoint.get("state") in NONTERMINAL_STATES
            ):
                raise ValueError(f"session already owns a nonterminal checkpoint: {candidate}")


def _project_root(workspace: Path) -> Path:
    current = Path(workspace).resolve()
    if current.is_file():
        current = current.parent
    while not current.exists() and current != current.parent:
        current = current.parent
    for directory in (current, *current.parents):
        if _has_git_marker(directory):
            return directory
    return current


def _related_artifact_roots(workspace: Path) -> Iterable[Path]:
    """Yield ancestor and descendant artifact roots, bounded and without symlink traversal."""
    seen: set[Path] = set()
    for artifacts in _artifact_roots(workspace):
        resolved = artifacts.resolve()
        if resolved not in seen:
            seen.add(resolved)
            yield resolved

    root = _project_root(workspace)
    scanned = 0

    def fail_scan(error: OSError) -> None:
        raise ValueError(f"cannot safely scan project artifact roots: {error}") from error

    for directory, directory_names, _ in os.walk(
        root,
        topdown=True,
        onerror=fail_scan,
        followlinks=False,
    ):
        scanned += 1
        if scanned > MAX_ARTIFACT_SCAN_DIRECTORIES:
            raise ValueError("project artifact-root scan limit exceeded")
        parent = Path(directory)
        retained: list[str] = []
        for name in directory_names:
            candidate = parent / name
            if name in IGNORED_ARTIFACT_SCAN_DIRECTORIES or candidate.is_symlink():
                continue
            if name == "artifacts":
                resolved = candidate.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    yield resolved
                continue
            retained.append(name)
        directory_names[:] = retained


def create_checkpoint(
    run_dir: Path,
    *,
    goal: str,
    deliverable: str,
    done_criteria: Iterable[str],
    steps: Iterable[tuple[str, str]],
    next_action: str,
    session_key: str,
    outer_goal: str = "none",
    goal_task_key: str | None = None,
    continuation_budget: int = DEFAULT_CONTINUATION_BUDGET,
) -> dict[str, Any]:
    """Create a schema-v4 checkpoint and start its first planned step."""
    run_dir = Path(run_dir)
    if (run_dir / CHECKPOINT_FILE).exists():
        raise FileExistsError(f"checkpoint already exists: {run_dir / CHECKPOINT_FILE}")
    if not SESSION_KEY_PATTERN.fullmatch(session_key):
        raise ValueError("session_key must be a 64-character lowercase SHA-256 digest")
    if outer_goal not in {"none", "native"}:
        raise ValueError("outer_goal must be none or native")
    if outer_goal == "native":
        if not isinstance(goal_task_key, str) or not SESSION_KEY_PATTERN.fullmatch(goal_task_key):
            raise ValueError("native outer_goal requires goal_task_key")
    elif goal_task_key is not None:
        raise ValueError("goal_task_key is only valid for native outer_goal")
    _positive_integer(continuation_budget, "continuation_budget")
    _ensure_single_nonterminal(run_dir, session_key)
    planned = [
        {"id": identifier.strip(), "title": title.strip(), "status": "pending"}
        for identifier, title in steps
    ]
    if planned:
        planned[0]["status"] = "in_progress"
    criteria = [
        {
            "id": f"criterion-{index}",
            "text": criterion.strip(),
            "status": "pending",
            "evidence_refs": [],
            "evidence_sha256": {},
        }
        for index, criterion in enumerate(done_criteria, start=1)
    ]
    now = _timestamp()
    checkpoint: dict[str, Any] = {
        "schema_version": 4,
        "session_key": session_key,
        "continuation_count": 0,
        "idle_continuations": 0,
        "continuation_budget": continuation_budget,
        "revision": 0,
        "goal": goal.strip(),
        "deliverable": deliverable.strip(),
        "done_criteria": criteria,
        "steps": planned,
        "state": "active",
        "current_step": planned[0]["id"] if planned else None,
        "next_action": next_action.strip(),
        "attempts": [],
        "pending_decisions": [],
        "blocker": "",
        "wait": None,
        "termination_reason": "",
        "review_receipt": None,
        "outer_goal": {
            "mode": outer_goal,
            "phase": "running" if outer_goal == "native" else "not_applicable",
            "task_key": goal_task_key,
            "receipt": None,
        },
        "created_at": now,
        "updated_at": now,
    }
    return _write_checkpoint(run_dir, checkpoint)


def _upgrade_checkpoint(
    checkpoint: dict[str, Any],
    *,
    session_key: str,
    outer_goal: str,
    goal_task_key: str | None,
    continuation_budget: int,
) -> dict[str, Any]:
    if checkpoint["state"] == "complete":
        raise ValueError("a completed legacy checkpoint is read-only")
    legacy_criteria = list(checkpoint["done_criteria"])
    checkpoint["schema_version"] = 4
    checkpoint["session_key"] = session_key
    checkpoint.setdefault("continuation_count", 0)
    checkpoint.setdefault("idle_continuations", 0)
    checkpoint["continuation_budget"] = continuation_budget
    checkpoint["revision"] = 0
    checkpoint["done_criteria"] = [
        {
            "id": f"criterion-{index}",
            "text": str(criterion.get("text", "")).strip()
            if isinstance(criterion, dict)
            else str(criterion).strip(),
            "status": "pending",
            "evidence_refs": [],
            "evidence_sha256": {},
        }
        for index, criterion in enumerate(legacy_criteria, start=1)
    ]
    checkpoint["review_receipt"] = None
    checkpoint["wait"] = None
    checkpoint["termination_reason"] = ""
    checkpoint["outer_goal"] = {
        "mode": outer_goal,
        "phase": "running" if outer_goal == "native" else "not_applicable",
        "task_key": goal_task_key,
        "receipt": None,
    }
    return checkpoint


def claim_checkpoint(
    run_dir: Path,
    *,
    session_key: str,
    outer_goal: str = "none",
    goal_task_key: str | None = None,
    previous_session_key: str | None = None,
    continuation_budget: int = DEFAULT_CONTINUATION_BUDGET,
) -> dict[str, Any]:
    """Attach a legacy run to this task and upgrade it to schema v4."""
    checkpoint = load_checkpoint(Path(run_dir))
    if not SESSION_KEY_PATTERN.fullmatch(session_key):
        raise ValueError("session_key must be a 64-character lowercase SHA-256 digest")
    if outer_goal not in {"none", "native"}:
        raise ValueError("outer_goal must be none or native")
    if outer_goal == "native":
        if not isinstance(goal_task_key, str) or not SESSION_KEY_PATTERN.fullmatch(goal_task_key):
            raise ValueError("native outer_goal requires goal_task_key")
    elif goal_task_key is not None:
        raise ValueError("goal_task_key is only valid for native outer_goal")
    if previous_session_key is not None and not SESSION_KEY_PATTERN.fullmatch(previous_session_key):
        raise ValueError("previous_session_key must be a SHA-256 digest")
    _positive_integer(continuation_budget, "continuation_budget")
    if checkpoint["schema_version"] >= 2 and checkpoint["session_key"] != session_key:
        if checkpoint["schema_version"] >= 4 or checkpoint["session_key"] != previous_session_key:
            raise ValueError("checkpoint belongs to another Codex task")
    _ensure_single_nonterminal(Path(run_dir), session_key)
    if checkpoint["schema_version"] < 4:
        checkpoint = _upgrade_checkpoint(
            checkpoint,
            session_key=session_key,
            outer_goal=outer_goal,
            goal_task_key=goal_task_key,
            continuation_budget=continuation_budget,
        )
    elif checkpoint["outer_goal"]["mode"] != outer_goal:
        raise ValueError("outer_goal mode cannot change after schema-v4 creation")
    _touch(checkpoint)
    return _write_checkpoint(Path(run_dir), checkpoint)


def _reset_idle_continuations(checkpoint: dict[str, Any]) -> None:
    if checkpoint["schema_version"] >= 2:
        checkpoint["idle_continuations"] = 0


def _artifact_path(run_dir: Path, artifact_ref: str, field: str) -> Path:
    artifact_ref = _nonempty(artifact_ref, field)
    path_text = artifact_ref.split("#", 1)[0]
    relative = Path(path_text)
    if relative.is_absolute() or not path_text or ".." in relative.parts:
        raise ValueError(f"{field} must be a run-relative evidence path")
    root = Path(run_dir).resolve()
    candidate = Path(run_dir) / relative
    try:
        metadata = candidate.lstat()
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (FileNotFoundError, OSError, RuntimeError, ValueError):
        raise ValueError(f"{field} must reference existing evidence inside the run") from None
    if candidate.is_symlink() or not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"{field} must reference a regular non-symlink evidence file")
    return resolved


def _artifact_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def heartbeat_checkpoint(
    run_dir: Path,
    *,
    next_action: str,
    progress_ref: str | None = None,
) -> dict[str, Any]:
    """Record meaningful same-step progress and keep the next action fresh."""
    checkpoint = load_checkpoint(Path(run_dir))
    if checkpoint["state"] != "active":
        raise ValueError("only an active checkpoint can record progress")
    next_action = _nonempty(next_action, "next_action")
    if next_action == checkpoint["next_action"]:
        raise ValueError("heartbeat must change next_action to prove progress")
    if checkpoint["schema_version"] >= 3:
        if progress_ref is None:
            raise ValueError("schema-v3+ heartbeat requires progress_ref evidence")
        _artifact_path(Path(run_dir), progress_ref, "progress evidence")
        checkpoint["last_progress_ref"] = progress_ref
    checkpoint["next_action"] = next_action
    _reset_idle_continuations(checkpoint)
    _touch(checkpoint)
    return _write_checkpoint(Path(run_dir), checkpoint)


def request_continuation(
    run_dir: Path,
    *,
    session_key: str,
    idle_limit: int,
) -> dict[str, Any]:
    """Count a Stop-hook continuation while bounding idle and total loops."""
    checkpoint = load_checkpoint(Path(run_dir))
    if checkpoint["schema_version"] < 2 or checkpoint["session_key"] != session_key:
        raise ValueError("checkpoint belongs to another Codex task")
    if checkpoint["state"] != "active":
        return {"continue": False, "reason": f"state_{checkpoint['state']}", "checkpoint": checkpoint}
    _positive_integer(idle_limit, "idle_limit")
    budget = checkpoint.get("continuation_budget", DEFAULT_CONTINUATION_BUDGET)
    if checkpoint["continuation_count"] >= budget:
        return {
            "continue": False,
            "reason": "continuation_budget_exhausted",
            "checkpoint": checkpoint,
        }
    if checkpoint["idle_continuations"] >= idle_limit:
        return {"continue": False, "reason": "idle_limit_exhausted", "checkpoint": checkpoint}
    checkpoint["continuation_count"] += 1
    checkpoint["idle_continuations"] += 1
    _touch(checkpoint)
    _write_checkpoint(Path(run_dir), checkpoint)
    return {"continue": True, "reason": "continue", "checkpoint": checkpoint}


def _artifact_roots(workspace: Path) -> Iterable[Path]:
    current = Path(workspace).resolve()
    if current.is_file():
        current = current.parent
    for directory in (current, *current.parents):
        yield directory / "artifacts"
        if _has_git_marker(directory):
            break


def find_nonterminal_checkpoint(workspace: Path, session_key: str) -> Path | None:
    """Find the single nonterminal run owned by this activation generation."""
    if not SESSION_KEY_PATTERN.fullmatch(session_key):
        raise ValueError("session_key must be a 64-character lowercase SHA-256 digest")
    matches: list[Path] = []
    for artifacts in _artifact_roots(Path(workspace)):
        for run_dir, checkpoint in _iter_checkpoints(artifacts):
            if (
                checkpoint.get("schema_version", 1) >= 2
                and checkpoint.get("session_key") == session_key
                and checkpoint.get("state") in NONTERMINAL_STATES
            ):
                matches.append(run_dir)
    unique = list(dict.fromkeys(matches))
    if len(unique) > 1:
        raise ValueError("multiple nonterminal checkpoints belong to this Codex task")
    return unique[0] if unique else None


def find_active_checkpoint(workspace: Path, session_key: str) -> Path | None:
    """Find the single active run owned by this activation generation."""
    run_dir = find_nonterminal_checkpoint(workspace, session_key)
    if run_dir is None:
        return None
    return run_dir if load_checkpoint(run_dir)["state"] == "active" else None


def advance_checkpoint(
    run_dir: Path,
    *,
    completed_step: str,
    next_step: str | None,
    next_action: str,
) -> dict[str, Any]:
    """Complete the current step and optionally start a pending step."""
    checkpoint = load_checkpoint(Path(run_dir))
    if checkpoint["state"] != "active":
        raise ValueError("only an active checkpoint can advance")
    if checkpoint["current_step"] != completed_step:
        raise ValueError(f"completed_step must be the current step: {checkpoint['current_step']}")
    by_id = {step["id"]: step for step in checkpoint["steps"]}
    by_id[completed_step]["status"] = "completed"
    if next_step is not None:
        if next_step not in by_id:
            raise ValueError(f"unknown next step: {next_step}")
        if by_id[next_step]["status"] != "pending":
            raise ValueError(f"next step is not pending: {next_step}")
        by_id[next_step]["status"] = "in_progress"
    checkpoint["current_step"] = next_step
    checkpoint["next_action"] = _nonempty(next_action, "next_action")
    _reset_idle_continuations(checkpoint)
    _touch(checkpoint)
    return _write_checkpoint(Path(run_dir), checkpoint)


def record_attempt(
    run_dir: Path,
    *,
    failure_class: str,
    approach: str,
    outcome: str,
    next_action: str,
) -> dict[str, Any]:
    """Record a failed approach while enforcing a bounded retry budget."""
    checkpoint = load_checkpoint(Path(run_dir))
    if checkpoint["state"] != "active":
        raise ValueError("only an active checkpoint can record an attempt")
    failure_class = _nonempty(failure_class, "failure_class")
    count = sum(item.get("failure_class") == failure_class for item in checkpoint["attempts"])
    if count >= MAX_ATTEMPTS_PER_FAILURE:
        raise RuntimeError(
            f"retry budget exhausted for {failure_class}; change the hypothesis or open a decision gate"
        )
    checkpoint["attempts"].append(
        {
            "failure_class": failure_class,
            "approach": _nonempty(approach, "approach"),
            "outcome": _nonempty(outcome, "outcome"),
            "recorded_at": _timestamp(),
        }
    )
    checkpoint["next_action"] = _nonempty(next_action, "next_action")
    _reset_idle_continuations(checkpoint)
    _touch(checkpoint)
    return _write_checkpoint(Path(run_dir), checkpoint)


def request_decision(
    run_dir: Path,
    *,
    questions: Iterable[str],
    reason: str,
) -> dict[str, Any]:
    """Pause at one batched approval gate."""
    checkpoint = load_checkpoint(Path(run_dir))
    if checkpoint["state"] != "active":
        raise ValueError("only an active checkpoint can request a decision")
    decisions = [_nonempty(question, "question") for question in questions]
    if not decisions:
        raise ValueError("at least one decision question is required")
    reason = _nonempty(reason, "reason")
    checkpoint["state"] = "approval_required"
    checkpoint["pending_decisions"] = [
        {"question": question, "reason": reason} for question in decisions
    ]
    checkpoint["blocker"] = reason
    checkpoint["wait"] = None
    checkpoint["next_action"] = "Resume after the batched decision is answered"
    _reset_idle_continuations(checkpoint)
    _touch(checkpoint)
    return _write_checkpoint(Path(run_dir), checkpoint)


def wait_checkpoint(
    run_dir: Path,
    *,
    reason: str,
    next_action: str,
    poll_interval_seconds: int,
    terminal_rule: str,
) -> dict[str, Any]:
    """Record an external wait without busy-looping the Stop hook."""
    checkpoint = load_checkpoint(Path(run_dir))
    if checkpoint["schema_version"] < 3 or checkpoint["state"] != "active":
        raise ValueError("only an active schema-v3+ checkpoint can wait externally")
    reason = _nonempty(reason, "reason")
    next_action = _nonempty(next_action, "next_action")
    poll_interval_seconds = _positive_integer(poll_interval_seconds, "poll_interval_seconds")
    checkpoint["state"] = "waiting_external"
    checkpoint["wait"] = {
        "reason": reason,
        "next_action": next_action,
        "poll_interval_seconds": poll_interval_seconds,
        "terminal_rule": _nonempty(terminal_rule, "terminal_rule"),
        "recorded_at": _timestamp(),
    }
    checkpoint["blocker"] = ""
    checkpoint["pending_decisions"] = []
    checkpoint["next_action"] = next_action
    _reset_idle_continuations(checkpoint)
    _touch(checkpoint)
    return _write_checkpoint(Path(run_dir), checkpoint)


def resume_checkpoint(run_dir: Path, *, next_action: str) -> dict[str, Any]:
    """Resume an approval-gated, externally waiting, or blocked checkpoint."""
    checkpoint = load_checkpoint(Path(run_dir))
    if checkpoint["state"] == "abandoned":
        raise ValueError("an abandoned checkpoint cannot resume")
    if checkpoint["state"] not in {"approval_required", "waiting_external", "blocked"}:
        raise ValueError("only an approval-gated, waiting, or blocked checkpoint can resume")
    checkpoint["state"] = "active"
    checkpoint["pending_decisions"] = []
    checkpoint["blocker"] = ""
    if checkpoint["schema_version"] >= 3:
        checkpoint["wait"] = None
    checkpoint["next_action"] = _nonempty(next_action, "next_action")
    _reset_idle_continuations(checkpoint)
    _touch(checkpoint)
    return _write_checkpoint(Path(run_dir), checkpoint)


def block_checkpoint(run_dir: Path, *, reason: str, next_action: str) -> dict[str, Any]:
    """Record a genuine blocker and the condition needed to continue."""
    checkpoint = load_checkpoint(Path(run_dir))
    if checkpoint["state"] != "active":
        raise ValueError("only an active checkpoint can become blocked")
    checkpoint["state"] = "blocked"
    checkpoint["pending_decisions"] = []
    checkpoint["blocker"] = _nonempty(reason, "reason")
    if checkpoint["schema_version"] >= 3:
        checkpoint["wait"] = None
    checkpoint["next_action"] = _nonempty(next_action, "next_action")
    _reset_idle_continuations(checkpoint)
    _touch(checkpoint)
    return _write_checkpoint(Path(run_dir), checkpoint)


def abandon_checkpoint(run_dir: Path, *, reason: str) -> dict[str, Any]:
    """Make a nonterminal checkpoint permanently non-resumable."""
    checkpoint = load_checkpoint(Path(run_dir))
    if checkpoint["state"] not in NONTERMINAL_STATES:
        raise ValueError("only a nonterminal checkpoint can be abandoned")
    if checkpoint["schema_version"] < 3:
        checkpoint = _upgrade_checkpoint(
            checkpoint,
            session_key=checkpoint["session_key"],
            outer_goal="none",
            goal_task_key=None,
            continuation_budget=DEFAULT_CONTINUATION_BUDGET,
        )
    checkpoint["state"] = "abandoned"
    checkpoint["current_step"] = None
    for step in checkpoint["steps"]:
        if step["status"] == "in_progress":
            step["status"] = "pending"
    checkpoint["next_action"] = ""
    checkpoint["pending_decisions"] = []
    checkpoint["blocker"] = ""
    checkpoint["wait"] = None
    checkpoint["termination_reason"] = _nonempty(reason, "reason")
    _reset_idle_continuations(checkpoint)
    _touch(checkpoint)
    return _write_checkpoint(Path(run_dir), checkpoint)


def verify_criterion(
    run_dir: Path,
    criterion_id: str,
    evidence_refs: Iterable[str],
) -> dict[str, Any]:
    """Satisfy one completion criterion with run-local evidence."""
    checkpoint = load_checkpoint(Path(run_dir))
    if checkpoint["schema_version"] < 3 or checkpoint["state"] != "active":
        raise ValueError("only an active schema-v3+ checkpoint can verify criteria")
    criterion_id = _nonempty(criterion_id, "criterion_id")
    by_id = {item["id"]: item for item in checkpoint["done_criteria"]}
    if criterion_id not in by_id:
        raise ValueError(f"unknown criterion: {criterion_id}")
    refs = [_nonempty(item, "evidence ref") for item in evidence_refs]
    if not refs:
        raise ValueError("criterion requires at least one evidence ref")
    evidence_sha256 = {
        evidence_ref: _artifact_sha256(
            _artifact_path(Path(run_dir), evidence_ref, "criterion evidence")
        )
        for evidence_ref in refs
    }
    by_id[criterion_id]["status"] = "satisfied"
    by_id[criterion_id]["evidence_refs"] = refs
    by_id[criterion_id]["evidence_sha256"] = evidence_sha256
    _reset_idle_continuations(checkpoint)
    _touch(checkpoint)
    return _write_checkpoint(Path(run_dir), checkpoint)


def record_review(
    run_dir: Path,
    *,
    artifact_ref: str,
) -> dict[str, Any]:
    """Attach a review artifact whose own fields attest reviewer and independence."""
    checkpoint = load_checkpoint(Path(run_dir))
    if checkpoint["schema_version"] < 4 or checkpoint["state"] != "active":
        raise ValueError("only an active schema-v4 checkpoint can record review")
    path = _artifact_path(Path(run_dir), artifact_ref, "review artifact")
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError):
        raise ValueError("review artifact must be valid JSON") from None
    if not isinstance(receipt, dict) or receipt.get("status") not in {"passed", "failed"}:
        raise ValueError("review artifact status must be passed or failed")
    verdict = receipt["status"]
    reviewer = _nonempty(receipt.get("reviewer"), "review artifact reviewer")
    independent = receipt.get("independent")
    if not isinstance(independent, bool):
        raise ValueError("review artifact independent must be boolean")
    findings = receipt.get("findings", [])
    if not isinstance(findings, list):
        raise ValueError("review artifact findings must be a list")
    if verdict == "passed" and findings:
        raise ValueError("passed review artifact cannot retain findings")
    checkpoint["review_receipt"] = {
        "reviewer": _nonempty(reviewer, "reviewer"),
        "verdict": verdict,
        "artifact_ref": artifact_ref,
        "artifact_sha256": _artifact_sha256(path),
        "independence_attested": independent,
        "recorded_at": _timestamp(),
    }
    _reset_idle_continuations(checkpoint)
    _touch(checkpoint)
    return _write_checkpoint(Path(run_dir), checkpoint)


def _check_local_completion(checkpoint: dict[str, Any]) -> None:
    unfinished = [step["id"] for step in checkpoint["steps"] if step["status"] != "completed"]
    if unfinished:
        raise ValueError(f"unfinished steps: {', '.join(unfinished)}")
    if checkpoint["schema_version"] >= 3:
        unsatisfied = [
            item["id"] for item in checkpoint["done_criteria"] if item["status"] != "satisfied"
        ]
        if unsatisfied:
            raise ValueError(f"unsatisfied criteria: {', '.join(unsatisfied)}")
        review = checkpoint["review_receipt"]
        independence_field = (
            "independence_attested" if checkpoint["schema_version"] >= 4 else "independent"
        )
        if not review or review["verdict"] != "passed" or not review[independence_field]:
            raise ValueError("completion requires a passed independent review")


def _check_completion_evidence(run_dir: Path, checkpoint: dict[str, Any]) -> None:
    if checkpoint["schema_version"] < 3:
        return
    for criterion in checkpoint["done_criteria"]:
        for evidence_ref in criterion["evidence_refs"]:
            path = _artifact_path(Path(run_dir), evidence_ref, "criterion evidence")
            if _artifact_sha256(path) != criterion["evidence_sha256"][evidence_ref]:
                raise ValueError(f"criterion evidence changed after verification: {evidence_ref}")
    review = checkpoint["review_receipt"]
    review_path = _artifact_path(Path(run_dir), review["artifact_ref"], "review artifact")
    if _artifact_sha256(review_path) != review["artifact_sha256"]:
        raise ValueError("review evidence changed after verification")


def complete_checkpoint(run_dir: Path) -> dict[str, Any]:
    """Finish local verification or enter native-Goal completion handoff."""
    checkpoint = load_checkpoint(Path(run_dir))
    if checkpoint["schema_version"] < 4:
        raise ValueError("claim and re-verify a legacy checkpoint before completion")
    if checkpoint["state"] != "active":
        raise ValueError("only an active checkpoint can complete")
    _check_local_completion(checkpoint)
    _check_completion_evidence(Path(run_dir), checkpoint)
    checkpoint["current_step"] = None
    if checkpoint["schema_version"] >= 3 and checkpoint["outer_goal"]["mode"] == "native":
        if checkpoint["outer_goal"]["phase"] != "running":
            raise ValueError("native Goal completion is already pending")
        checkpoint["outer_goal"]["phase"] = "completion_pending"
        checkpoint["next_action"] = (
            "Call get_goal, then update_goal(status=complete); after host success save a run-local "
            "Goal completion receipt and run science_checkpoint.py confirm-goal-complete --receipt"
        )
    else:
        checkpoint["state"] = "complete"
        checkpoint["next_action"] = ""
    checkpoint["pending_decisions"] = []
    checkpoint["blocker"] = ""
    if checkpoint["schema_version"] >= 3:
        checkpoint["wait"] = None
    _reset_idle_continuations(checkpoint)
    _touch(checkpoint)
    return _write_checkpoint(Path(run_dir), checkpoint)


def confirm_goal_complete(run_dir: Path, *, receipt_ref: str) -> dict[str, Any]:
    """Record an agent attestation derived from a successful native Goal tool result."""
    checkpoint = load_checkpoint(Path(run_dir))
    if (
        checkpoint["schema_version"] < 4
        or checkpoint["state"] != "active"
        or checkpoint["outer_goal"]["mode"] != "native"
        or checkpoint["outer_goal"]["phase"] != "completion_pending"
    ):
        raise ValueError("native Goal confirmation requires completion_pending")
    _check_local_completion(checkpoint)
    _check_completion_evidence(Path(run_dir), checkpoint)
    path = _artifact_path(Path(run_dir), receipt_ref, "Goal completion receipt")
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError):
        raise ValueError("Goal completion receipt must be valid JSON") from None
    if not isinstance(receipt, dict) or receipt.get("status") != "complete":
        raise ValueError("Goal completion receipt status must be complete")
    if receipt.get("task_key") != checkpoint["outer_goal"]["task_key"]:
        raise ValueError("Goal completion receipt task_key must match the bound native Goal")
    checkpoint["state"] = "complete"
    checkpoint["outer_goal"]["phase"] = "host_completion_attested"
    checkpoint["outer_goal"]["receipt"] = {
        "artifact_ref": receipt_ref,
        "artifact_sha256": _artifact_sha256(path),
        "recorded_at": _timestamp(),
    }
    checkpoint["next_action"] = ""
    _touch(checkpoint)
    return _write_checkpoint(Path(run_dir), checkpoint)
