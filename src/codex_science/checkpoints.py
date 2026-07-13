"""Durable control state for autonomous Codex Science runs."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


CHECKPOINT_FILE = "checkpoint.json"
MAX_ATTEMPTS_PER_FAILURE = 3
STATES = {"active", "approval_required", "blocked", "complete"}
STEP_STATUSES = {"pending", "in_progress", "completed"}


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
    if checkpoint["schema_version"] != 1:
        raise ValueError("unsupported checkpoint schema version")

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
        "schema_version": 1,
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
    checkpoint["updated_at"] = _timestamp()
    return _write_checkpoint(Path(run_dir), checkpoint)
