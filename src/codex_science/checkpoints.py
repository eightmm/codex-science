"""Durable control state for autonomous Codex Science runs."""

from __future__ import annotations

import json
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


CHECKPOINT_FILE = "checkpoint.json"
MAX_ATTEMPTS_PER_FAILURE = 3
STATES = {"active", "approval_required", "blocked", "complete"}
STEP_STATUSES = {"pending", "in_progress", "completed"}
SESSION_KEY_PATTERN = re.compile(r"^[0-9a-f]{64}$")
MAX_AUTOCONTINUE_CHECKPOINT_BYTES = 1_000_000
MAX_AUTOCONTINUE_RUNS = 1_000


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _nonempty(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


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
    if schema_version not in {1, 2}:
        raise ValueError("unsupported checkpoint schema version")
    if schema_version == 2:
        version_two_fields = {"session_key", "continuation_count", "idle_continuations"}
        missing_v2 = sorted(version_two_fields - checkpoint.keys())
        if missing_v2:
            raise ValueError(f"missing checkpoint fields: {', '.join(missing_v2)}")
        if not SESSION_KEY_PATTERN.fullmatch(str(checkpoint["session_key"])):
            raise ValueError("session_key must be a 64-character lowercase SHA-256 digest")
        for field in ("continuation_count", "idle_continuations"):
            value = checkpoint[field]
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field} must be a non-negative integer")

    _nonempty(checkpoint["goal"], "goal")
    _nonempty(checkpoint["deliverable"], "deliverable")
    criteria = checkpoint["done_criteria"]
    if not isinstance(criteria, list) or not criteria:
        raise ValueError("done_criteria must contain at least one item")
    for criterion in criteria:
        _nonempty(criterion, "done criterion")

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

    state = checkpoint["state"]
    if state not in STATES:
        raise ValueError(f"invalid checkpoint state: {state}")
    current_step = checkpoint["current_step"]
    if current_step is not None and current_step not in identifiers:
        raise ValueError("current_step must identify a planned step")
    if len(in_progress) > 1:
        raise ValueError("only one step may be in progress")
    if in_progress != ([] if current_step is None else [current_step]):
        raise ValueError("current_step must match the in-progress step")

    if not isinstance(checkpoint["next_action"], str):
        raise ValueError("next_action must be a string")
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
    if not isinstance(checkpoint["blocker"], str):
        raise ValueError("blocker must be a string")
    _nonempty(checkpoint["updated_at"], "updated_at")

    if state == "active" and not checkpoint["next_action"].strip():
        raise ValueError("an active checkpoint requires next_action")
    if state == "approval_required" and not checkpoint["pending_decisions"]:
        raise ValueError("approval_required requires pending_decisions")
    if state == "blocked" and not checkpoint["blocker"].strip():
        raise ValueError("blocked requires blocker")
    if state == "complete":
        if any(step["status"] != "completed" for step in steps):
            raise ValueError("complete requires every step to be completed")
        if current_step is not None or checkpoint["next_action"]:
            raise ValueError("complete cannot have a current step or next action")
        if checkpoint["pending_decisions"] or checkpoint["blocker"]:
            raise ValueError("complete cannot retain a gate or blocker")


def _write_checkpoint(run_dir: Path, checkpoint: dict[str, Any]) -> dict[str, Any]:
    validate_checkpoint(checkpoint)
    run_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = run_dir / CHECKPOINT_FILE
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(checkpoint, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.chmod(0o600)
        temporary.replace(path)
        path.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)
    return checkpoint


def load_checkpoint(run_dir: Path) -> dict[str, Any]:
    """Load and validate a run checkpoint."""
    path = Path(run_dir) / CHECKPOINT_FILE
    checkpoint = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(checkpoint, dict):
        raise ValueError("checkpoint root must be an object")
    validate_checkpoint(checkpoint)
    return checkpoint


def create_checkpoint(
    run_dir: Path,
    *,
    goal: str,
    deliverable: str,
    done_criteria: Iterable[str],
    steps: Iterable[tuple[str, str]],
    next_action: str,
    session_key: str,
) -> dict[str, Any]:
    """Create a checkpoint and start its first planned step."""
    if (Path(run_dir) / CHECKPOINT_FILE).exists():
        raise FileExistsError(f"checkpoint already exists: {Path(run_dir) / CHECKPOINT_FILE}")
    planned = [
        {"id": identifier.strip(), "title": title.strip(), "status": "pending"}
        for identifier, title in steps
    ]
    if planned:
        planned[0]["status"] = "in_progress"
    checkpoint: dict[str, Any] = {
        "schema_version": 2,
        "session_key": session_key,
        "continuation_count": 0,
        "idle_continuations": 0,
        "goal": goal.strip(),
        "deliverable": deliverable.strip(),
        "done_criteria": [criterion.strip() for criterion in done_criteria],
        "steps": planned,
        "state": "active",
        "current_step": planned[0]["id"] if planned else None,
        "next_action": next_action.strip(),
        "attempts": [],
        "pending_decisions": [],
        "blocker": "",
        "updated_at": _timestamp(),
    }
    return _write_checkpoint(Path(run_dir), checkpoint)


def _reset_idle_continuations(checkpoint: dict[str, Any]) -> None:
    if checkpoint["schema_version"] == 2:
        checkpoint["idle_continuations"] = 0


def claim_checkpoint(run_dir: Path, *, session_key: str) -> dict[str, Any]:
    """Attach an existing run to this task, upgrading legacy schema v1."""
    checkpoint = load_checkpoint(Path(run_dir))
    if not SESSION_KEY_PATTERN.fullmatch(session_key):
        raise ValueError("session_key must be a 64-character lowercase SHA-256 digest")
    if checkpoint["schema_version"] == 2 and checkpoint["session_key"] != session_key:
        raise ValueError("checkpoint belongs to another Codex task")
    checkpoint["schema_version"] = 2
    checkpoint["session_key"] = session_key
    checkpoint.setdefault("continuation_count", 0)
    checkpoint.setdefault("idle_continuations", 0)
    checkpoint["updated_at"] = _timestamp()
    return _write_checkpoint(Path(run_dir), checkpoint)


def heartbeat_checkpoint(run_dir: Path, *, next_action: str) -> dict[str, Any]:
    """Record meaningful same-step progress and keep the next action fresh."""
    checkpoint = load_checkpoint(Path(run_dir))
    if checkpoint["state"] != "active":
        raise ValueError("only an active checkpoint can record progress")
    next_action = _nonempty(next_action, "next_action")
    if next_action == checkpoint["next_action"]:
        raise ValueError("heartbeat must change next_action to prove progress")
    checkpoint["next_action"] = next_action
    _reset_idle_continuations(checkpoint)
    checkpoint["updated_at"] = _timestamp()
    return _write_checkpoint(Path(run_dir), checkpoint)


def request_continuation(
    run_dir: Path,
    *,
    session_key: str,
    idle_limit: int,
) -> dict[str, Any]:
    """Count a Stop-hook continuation while bounding no-progress loops."""
    checkpoint = load_checkpoint(Path(run_dir))
    if checkpoint["schema_version"] != 2 or checkpoint["session_key"] != session_key:
        raise ValueError("checkpoint belongs to another Codex task")
    if checkpoint["state"] != "active":
        return {"continue": False, "checkpoint": checkpoint}
    if not isinstance(idle_limit, int) or isinstance(idle_limit, bool) or idle_limit < 1:
        raise ValueError("idle_limit must be a positive integer")
    if checkpoint["idle_continuations"] >= idle_limit:
        return {"continue": False, "checkpoint": checkpoint}
    checkpoint["continuation_count"] += 1
    checkpoint["idle_continuations"] += 1
    checkpoint["updated_at"] = _timestamp()
    _write_checkpoint(Path(run_dir), checkpoint)
    return {"continue": True, "checkpoint": checkpoint}


def find_active_checkpoint(workspace: Path, session_key: str) -> Path | None:
    """Find the newest direct artifact run owned by this task."""
    if not SESSION_KEY_PATTERN.fullmatch(session_key):
        raise ValueError("session_key must be a 64-character lowercase SHA-256 digest")
    artifacts = Path(workspace) / "artifacts"
    if artifacts.is_symlink():
        return None
    try:
        run_dirs = artifacts.iterdir()
    except (FileNotFoundError, NotADirectoryError, PermissionError):
        return None
    matches: list[tuple[str, Path]] = []
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
        except (
            FileNotFoundError,
            PermissionError,
            OSError,
            UnicodeError,
            ValueError,
            json.JSONDecodeError,
        ):
            continue
        if (
            checkpoint["schema_version"] == 2
            and checkpoint["session_key"] == session_key
            and checkpoint["state"] == "active"
        ):
            matches.append((checkpoint["updated_at"], run_dir))
    return max(matches, default=("", None))[1]


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
    checkpoint["next_action"] = next_action.strip()
    _reset_idle_continuations(checkpoint)
    checkpoint["updated_at"] = _timestamp()
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
    checkpoint["updated_at"] = _timestamp()
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
    checkpoint["next_action"] = "Resume after the batched decision is answered"
    _reset_idle_continuations(checkpoint)
    checkpoint["updated_at"] = _timestamp()
    return _write_checkpoint(Path(run_dir), checkpoint)


def resume_checkpoint(run_dir: Path, *, next_action: str) -> dict[str, Any]:
    """Resume an approval-gated or blocked checkpoint."""
    checkpoint = load_checkpoint(Path(run_dir))
    if checkpoint["state"] not in {"approval_required", "blocked"}:
        raise ValueError("only an approval-gated or blocked checkpoint can resume")
    checkpoint["state"] = "active"
    checkpoint["pending_decisions"] = []
    checkpoint["blocker"] = ""
    checkpoint["next_action"] = _nonempty(next_action, "next_action")
    _reset_idle_continuations(checkpoint)
    checkpoint["updated_at"] = _timestamp()
    return _write_checkpoint(Path(run_dir), checkpoint)


def block_checkpoint(run_dir: Path, *, reason: str, next_action: str) -> dict[str, Any]:
    """Record a genuine blocker and the condition needed to continue."""
    checkpoint = load_checkpoint(Path(run_dir))
    if checkpoint["state"] != "active":
        raise ValueError("only an active checkpoint can become blocked")
    checkpoint["state"] = "blocked"
    checkpoint["pending_decisions"] = []
    checkpoint["blocker"] = _nonempty(reason, "reason")
    checkpoint["next_action"] = _nonempty(next_action, "next_action")
    _reset_idle_continuations(checkpoint)
    checkpoint["updated_at"] = _timestamp()
    return _write_checkpoint(Path(run_dir), checkpoint)


def complete_checkpoint(run_dir: Path) -> dict[str, Any]:
    """Mark a checkpoint complete only after every planned step is done."""
    checkpoint = load_checkpoint(Path(run_dir))
    if checkpoint["state"] != "active":
        raise ValueError("only an active checkpoint can complete")
    unfinished = [step["id"] for step in checkpoint["steps"] if step["status"] != "completed"]
    if unfinished:
        raise ValueError(f"unfinished steps: {', '.join(unfinished)}")
    checkpoint["state"] = "complete"
    checkpoint["current_step"] = None
    checkpoint["next_action"] = ""
    checkpoint["pending_decisions"] = []
    checkpoint["blocker"] = ""
    _reset_idle_continuations(checkpoint)
    checkpoint["updated_at"] = _timestamp()
    return _write_checkpoint(Path(run_dir), checkpoint)
