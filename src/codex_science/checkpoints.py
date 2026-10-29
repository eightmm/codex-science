"""Durable control state for autonomous Codex Science runs."""

from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import os
import re
import secrets
import stat
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable, Iterator

from codex_science.cli_io import write_text_atomic
from codex_science.runtime_identity import record_runtime_identity, validate_runtime_history


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


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_deadline(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("deadline_at must be a UTC timestamp ending in Z")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("deadline_at must be a UTC timestamp") from exc
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("deadline_at must be UTC")
    return parsed


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


def _validate_rigor(rigor: object) -> None:
    if not isinstance(rigor, dict):
        raise ValueError("rigor must be an object")
    if not isinstance(rigor.get("tier"), str) or rigor["tier"] not in {"standard", "full"}:
        raise ValueError("rigor tier must be standard or full")
    history = rigor.get("history")
    if not isinstance(history, list) or not history:
        raise ValueError("rigor history must contain at least one item")
    tiers = {"standard": 0, "full": 1}
    previous = -1
    for entry in history:
        if not isinstance(entry, dict):
            raise ValueError("each rigor history item must be an object")
        tier = entry.get("tier")
        if not isinstance(tier, str) or tier not in tiers:
            raise ValueError("rigor history tier must be standard or full")
        current = tiers[tier]
        if current < previous:
            raise ValueError("rigor history tiers must be non-decreasing")
        previous = current
        _nonempty(entry.get("at"), "rigor history at")
        _nonempty(entry.get("reason"), "rigor history reason")
        digest = entry.get("decision_sha256")
        if digest is not None and (not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest)):
            raise ValueError("rigor history decision_sha256 must be a SHA-256 digest")
    if history[-1]["tier"] != rigor["tier"]:
        raise ValueError("rigor tier must match the last history tier")


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
    if "rigor" in checkpoint:
        _validate_rigor(checkpoint["rigor"])
    schema_version = checkpoint["schema_version"]
    if schema_version not in {1, 2, 3, 4}:
        raise ValueError("unsupported checkpoint schema version")
    if "session_binding" in checkpoint:
        if schema_version != 4:
            raise ValueError("session_binding is supported only on schema-v4 checkpoints")
        binding = checkpoint["session_binding"]
        if not isinstance(binding, dict) or set(binding) != {"mode", "hook_bound", "key_source", "created_at"}:
            raise ValueError("session_binding must contain exactly mode, hook_bound, key_source, and created_at")
        if binding["mode"] != "hookless" or binding["hook_bound"] is not False or binding["key_source"] != "random_run_local":
            raise ValueError("session_binding values are invalid")
        if not isinstance(binding["created_at"], str) or not binding["created_at"].endswith("Z"):
            raise ValueError("session_binding.created_at must be a UTC timestamp")
        try:
            datetime.fromisoformat(binding["created_at"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("session_binding.created_at must be a UTC timestamp") from exc
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
    validate_runtime_history(checkpoint)

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

    if "run_budget" in checkpoint:
        budget = checkpoint["run_budget"]
        fields = {"policy_version", "tier", "max_failed_attempts_per_class", "max_review_rounds", "deadline_at"}
        if schema_version != 4 or not isinstance(budget, dict) or set(budget) != fields:
            raise ValueError("run_budget is invalid")
        if budget["policy_version"] != 1 or budget["tier"] not in {"standard", "full"}:
            raise ValueError("run_budget policy or tier is invalid")
        if checkpoint.get("rigor", {}).get("tier") != budget["tier"]:
            raise ValueError("run_budget tier must match rigor tier")
        _positive_integer(budget["max_failed_attempts_per_class"], "max_failed_attempts_per_class")
        _positive_integer(budget["max_review_rounds"], "max_review_rounds")
        expected_limits = (2, 1) if budget["tier"] == "standard" else (3, 2)
        if (budget["max_failed_attempts_per_class"] < expected_limits[0]
                or budget["max_review_rounds"] < expected_limits[1]):
            raise ValueError("run_budget limits are below tier-v1 defaults")
        if budget["deadline_at"] is not None:
            _parse_deadline(budget["deadline_at"])
        rounds = checkpoint.get("review_rounds")
        if not isinstance(rounds, list):
            raise ValueError("budgeted checkpoints require review_rounds")
        round_ids: set[str] = set()
        for item in rounds:
            if not isinstance(item, dict) or set(item) != {"id", "started_at", "receipt_ref", "receipt_sha256"}:
                raise ValueError("review_rounds entry is invalid")
            _nonempty(item.get("id"), "review round id")
            if item["id"] in round_ids: raise ValueError("review round ids must be unique")
            round_ids.add(item["id"])
            _nonempty(item.get("started_at"), "review round started_at")
            _nonempty(item.get("receipt_ref"), "review receipt ref")
            if not isinstance(item.get("receipt_sha256"), str) or not SHA256_PATTERN.fullmatch(item["receipt_sha256"]):
                raise ValueError("review receipt hash is invalid")
    elif "review_rounds" in checkpoint:
        raise ValueError("review_rounds requires run_budget")
    termination = checkpoint.get("termination")
    if "termination" in checkpoint:
        if (
            schema_version != 4
            or "run_budget" not in checkpoint
            or not isinstance(termination, dict)
            or checkpoint["state"] != "abandoned"
            or termination.get("kind") != "partial"
            or termination.get("reason_code") not in {"budget_exhausted", "deadline_passed"}
        ):
            raise ValueError("partial termination is invalid")
        for field in ("exhausted_limit", "recorded_at", "artifact_ref"):
            _nonempty(termination.get(field), f"termination {field}")
        if not isinstance(termination.get("artifact_sha256"), str) or not SHA256_PATTERN.fullmatch(termination["artifact_sha256"]):
            raise ValueError("termination artifact hash is invalid")
        if checkpoint["termination_reason"] != termination["reason_code"]:
            raise ValueError("termination_reason must match termination.reason_code")

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


@contextmanager
def _checkpoint_lock(run_dir: Path) -> Iterator[None]:
    run_dir = Path(run_dir).resolve()
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | os.O_NOFOLLOW
    directory = os.open(run_dir, flags)
    try:
        if not stat.S_ISDIR(os.fstat(directory).st_mode):
            raise ValueError("checkpoint run must be a directory")
        lock_path = run_dir.parent / f".{run_dir.name}.checkpoint.lock"
        flags = os.O_RDWR | os.O_NOFOLLOW
        try:
            descriptor = os.open(lock_path, flags)
        except FileNotFoundError:
            try:
                descriptor = os.open(lock_path, flags | os.O_CREAT, 0o600)
            except OSError as error:
                if error.errno not in {errno.EACCES, errno.EPERM, errno.EROFS}:
                    raise
                try:
                    descriptor = os.open(lock_path, flags)
                except FileNotFoundError:
                    # With the same parent permissions and no sibling file,
                    # callers of one user consistently choose the run inode.
                    descriptor = directory
        try:
            if descriptor != directory:
                metadata = os.fstat(descriptor)
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid() or metadata.st_mode & 0o077:
                    raise ValueError("checkpoint lock file is unsafe")
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX)
            except OSError as error:
                if descriptor == directory:
                    raise ValueError(
                        "checkpoint directory lock is unavailable; make the parent writable "
                        "or pre-create the checkpoint lock file with mode 0600"
                    ) from error
                raise
            try:
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            # Unlinking would let a concurrent caller lock a different inode.
            if descriptor != directory:
                os.close(descriptor)
    finally:
        os.close(directory)


def _serialized_mutation(function: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
    @wraps(function)
    def serialized(run_dir: Path, *args: Any, **kwargs: Any) -> dict[str, Any]:
        with _checkpoint_lock(run_dir):
            return function(run_dir, *args, **kwargs)

    return serialized


def _write_checkpoint(run_dir: Path, checkpoint: dict[str, Any]) -> dict[str, Any]:
    record_runtime_identity(checkpoint)
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


def _iter_checkpoints(artifacts: Path, *, strict: bool = False) -> Iterable[tuple[Path, dict[str, Any]]]:
    if artifacts.is_symlink():
        if strict:
            raise ValueError(f"cannot safely scan symlink artifact root: {artifacts}")
        return
    try:
        entries = tuple(artifacts.iterdir())
    except FileNotFoundError:
        return
    except (NotADirectoryError, PermissionError, OSError) as exc:
        if strict:
            raise ValueError(f"cannot safely scan artifact root: {exc}") from exc
        return
    run_dirs = []
    for entry in entries:
        try:
            metadata = entry.lstat()
        except OSError as exc:
            if strict:
                raise ValueError(f"cannot safely scan artifact entry {entry}: {exc}") from exc
            continue
        if stat.S_ISLNK(metadata.st_mode):
            if strict:
                raise ValueError(f"cannot safely scan symlink run directory: {entry}")
            continue
        if stat.S_ISDIR(metadata.st_mode) and not entry.name.startswith("."):
            run_dirs.append(entry)
    if strict and len(run_dirs) > MAX_AUTOCONTINUE_RUNS:
        raise ValueError("project artifact-root scan limit exceeded")
    for run_dir in run_dirs[:MAX_AUTOCONTINUE_RUNS]:
        path = run_dir / CHECKPOINT_FILE
        if not path.exists() and not path.is_symlink():
            continue
        try:
            metadata = path.lstat()
            if (
                path.is_symlink()
                or not stat.S_ISREG(metadata.st_mode)
                or metadata.st_size > MAX_AUTOCONTINUE_CHECKPOINT_BYTES
            ):
                if strict:
                    raise ValueError(f"cannot safely scan checkpoint path: {path}")
                continue
            checkpoint = load_checkpoint(run_dir)
        except (FileNotFoundError, PermissionError, OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            if strict:
                raise ValueError(f"cannot safely scan checkpoint {path}: {exc}") from exc
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


def _related_artifact_roots(workspace: Path, *, strict: bool = False) -> Iterable[Path]:
    """Yield ancestor and descendant artifact roots, bounded and without symlink traversal."""
    seen: set[Path] = set()
    for artifacts in _artifact_roots(workspace):
        if strict and artifacts.is_symlink():
            raise ValueError(f"cannot safely scan symlink artifact root: {artifacts}")
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
            if candidate.is_symlink():
                if strict and name == "artifacts":
                    raise ValueError(f"cannot safely scan symlink artifact root: {candidate}")
                continue
            if name in IGNORED_ARTIFACT_SCAN_DIRECTORIES:
                continue
            if name == "artifacts":
                resolved = candidate.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    yield resolved
                continue
            retained.append(name)
        directory_names[:] = retained


def _validate_hookless_run_path(run_dir: Path) -> Path:
    """Require a visible run directly under an artifact root included in scans."""
    run_dir = Path(run_dir)
    if run_dir.parent.name != "artifacts" or run_dir.name.startswith("."):
        raise ValueError("hookless runs must use a visible run directory directly under artifacts/")
    workspace = run_dir.parent.parent
    covered_roots = {root.resolve() for root in _artifact_roots(workspace)}
    if run_dir.parent.resolve() not in covered_roots:
        raise ValueError("hookless artifacts directory is not covered by the project artifact scan")
    return run_dir


def _scan_init_admission(run_dir: Path, workspace: Path, *, hookless: bool) -> None:
    for artifacts in _related_artifact_roots(workspace, strict=hookless):
        for candidate, checkpoint in _iter_checkpoints(artifacts, strict=hookless):
            if candidate.resolve() == run_dir.resolve() or checkpoint.get("state") not in NONTERMINAL_STATES:
                continue
            if hookless or checkpoint.get("session_binding", {}).get("mode") == "hookless":
                raise ValueError(f"cannot initialize while a nonterminal checkpoint exists: {candidate}")


@contextmanager
def _initialization_admission(
    run_dir: Path, *, hookless: bool, timeout: float = 10.0
) -> Iterator[None]:
    """Serialize hookless admission and hold all covered artifact-root locks through writing."""
    run_dir = Path(run_dir)
    workspace = run_dir.parent.parent if run_dir.parent.name == "artifacts" else run_dir.parent
    if not hookless:
        # Preserve hook-bound init's prior filesystem behavior; it may race a concurrent hookless init.
        _scan_init_admission(run_dir, workspace, hookless=False)
        yield
        return

    _validate_hookless_run_path(run_dir)
    _scan_init_admission(run_dir, workspace, hookless=True)
    artifacts_root = run_dir.parent
    artifacts_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    metadata = artifacts_root.lstat()
    if artifacts_root.is_symlink() or not stat.S_ISDIR(metadata.st_mode):
        raise ValueError("checkpoint artifact root is not a regular directory")
    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW

    def not_lockable(lock_root: Path, error: OSError) -> ValueError:
        return ValueError(f"checkpoint related artifact root is not lockable: {lock_root}: {error}")

    target_root = artifacts_root.resolve()
    lock_roots = {target_root}
    for related_root in _related_artifact_roots(workspace, strict=True):
        try:
            related_metadata = related_root.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise not_lockable(related_root, exc) from exc
        if related_root.is_symlink() or not stat.S_ISDIR(related_metadata.st_mode):
            continue
        lock_roots.add(related_root.resolve())

    deadline = time.monotonic() + max(timeout, 0.0)
    handles: list[tuple[Any, bool, Path]] = []
    try:
        for lock_root in sorted(lock_roots, key=str):
            try:
                root_metadata = lock_root.lstat()
            except FileNotFoundError:
                if lock_root == target_root:
                    raise
                continue
            except OSError as exc:
                if lock_root == target_root:
                    raise
                raise not_lockable(lock_root, exc) from exc
            if lock_root.is_symlink() or not stat.S_ISDIR(root_metadata.st_mode):
                if lock_root == target_root:
                    raise ValueError("checkpoint artifact root is not a regular directory")
                continue
            lock_path = lock_root / ".checkpoint-init.lock"
            try:
                descriptor = os.open(lock_path, flags, 0o600)
            except FileNotFoundError as open_error:
                if lock_root == target_root:
                    raise
                try:
                    lock_root.lstat()
                except FileNotFoundError:
                    continue
                except OSError as root_error:
                    raise not_lockable(lock_root, root_error) from root_error
                raise not_lockable(lock_root, open_error) from open_error
            except OSError as exc:
                raise not_lockable(lock_root, exc) from exc
            try:
                handle = os.fdopen(descriptor, "r+")
            except OSError as exc:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
                raise not_lockable(lock_root, exc) from exc
            handles.append((handle, False, lock_root))
            try:
                os.fchmod(handle.fileno(), 0o600)
            except OSError as exc:
                raise not_lockable(lock_root, exc) from exc
            while True:
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    if time.monotonic() >= deadline:
                        raise ValueError("checkpoint initialization is busy; retry after the active initialization finishes") from exc
                    time.sleep(0.05)
                except OSError as exc:
                    raise not_lockable(lock_root, exc) from exc
                else:
                    handles[-1] = (handle, True, lock_root)
                    break
        if (run_dir / CHECKPOINT_FILE).exists() or (run_dir / CHECKPOINT_FILE).is_symlink():
            raise FileExistsError(f"checkpoint already exists: {run_dir / CHECKPOINT_FILE}")
        _scan_init_admission(run_dir, workspace, hookless=True)
        yield
    finally:
        cleanup_error: tuple[Path, BaseException] | None = None
        for handle, locked, lock_root in reversed(handles):
            try:
                if locked:
                    fcntl.flock(handle, fcntl.LOCK_UN)
            except BaseException as exc:
                if cleanup_error is None:
                    cleanup_error = (lock_root, exc)
            try:
                handle.close()
            except BaseException as exc:
                if cleanup_error is None:
                    cleanup_error = (lock_root, exc)
        if cleanup_error is not None:
            lock_root, error = cleanup_error
            if isinstance(error, OSError):
                raise not_lockable(lock_root, error) from error
            raise error


def create_checkpoint(
    run_dir: Path,
    *,
    goal: str,
    deliverable: str,
    done_criteria: Iterable[str],
    steps: Iterable[tuple[str, str]],
    next_action: str,
    session_key: str | None = None,
    outer_goal: str = "none",
    goal_task_key: str | None = None,
    continuation_budget: int = DEFAULT_CONTINUATION_BUDGET,
    rigor_tier: str | None = None,
    rigor_decision_sha256: str | None = None,
    hookless: bool = False,
    budget_policy: str | None = None,
    deadline_at: str | None = None,
) -> dict[str, Any]:
    """Create a schema-v4 checkpoint and start its first planned step."""
    run_dir = Path(run_dir)
    checkpoint_path = run_dir / CHECKPOINT_FILE
    if checkpoint_path.exists() or checkpoint_path.is_symlink():
        raise FileExistsError(f"checkpoint already exists: {run_dir / CHECKPOINT_FILE}")
    if hookless:
        _validate_hookless_run_path(run_dir)
        if rigor_tier not in {"standard", "full"}:
            raise ValueError("hookless initialization requires rigor_tier standard or full")
        if outer_goal == "native":
            raise ValueError("hookless initialization does not support native outer_goal")
        if session_key is not None:
            raise ValueError("hookless initialization cannot accept an explicit session_key")
        session_key = secrets.token_hex(32)
    elif session_key is None:
        raise ValueError("init requires either --session-key or --hookless")
    elif not isinstance(session_key, str) or not SESSION_KEY_PATTERN.fullmatch(session_key):
        raise ValueError("session_key must be a 64-character lowercase SHA-256 digest")
    if outer_goal not in {"none", "native"}:
        raise ValueError("outer_goal must be none or native")
    if outer_goal == "native":
        if not isinstance(goal_task_key, str) or not SESSION_KEY_PATTERN.fullmatch(goal_task_key):
            raise ValueError("native outer_goal requires goal_task_key")
    elif goal_task_key is not None:
        raise ValueError("goal_task_key is only valid for native outer_goal")
    _positive_integer(continuation_budget, "continuation_budget")
    if rigor_tier is not None and (
        not isinstance(rigor_tier, str) or rigor_tier not in {"standard", "full"}
    ):
        raise ValueError("rigor_tier must be standard or full")
    if budget_policy is not None and (budget_policy != "tier-v1" or rigor_tier is None):
        raise ValueError("budget-policy tier-v1 requires rigor_tier")
    if deadline_at is not None:
        if _parse_deadline(deadline_at) <= _now():
            raise ValueError("deadline-at must be in the future")
        if budget_policy is None:
            raise ValueError("deadline-at requires budget-policy tier-v1")
    if rigor_decision_sha256 is not None and (
        not isinstance(rigor_decision_sha256, str) or not SHA256_PATTERN.fullmatch(rigor_decision_sha256)
    ):
        raise ValueError("rigor_decision_sha256 must be a SHA-256 digest")
    with _initialization_admission(run_dir, hookless=hookless):
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
        if rigor_tier is not None:
            history = {"tier": rigor_tier, "at": now, "reason": "requested at initialization"}
            if rigor_decision_sha256 is not None:
                history["decision_sha256"] = rigor_decision_sha256
            checkpoint["rigor"] = {"tier": rigor_tier, "history": [history]}
        if budget_policy == "tier-v1":
            checkpoint["run_budget"] = {"policy_version": 1, "tier": rigor_tier,
                "max_failed_attempts_per_class": 2 if rigor_tier == "standard" else 3,
                "max_review_rounds": 1 if rigor_tier == "standard" else 2,
                "deadline_at": deadline_at}
            checkpoint["review_rounds"] = []
        if hookless:
            checkpoint["session_binding"] = {
                "mode": "hookless", "hook_bound": False,
                "key_source": "random_run_local", "created_at": now,
            }
        validate_checkpoint(checkpoint)
        run_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        with _checkpoint_lock(run_dir):
            if checkpoint_path.exists() or checkpoint_path.is_symlink():
                raise FileExistsError(f"checkpoint already exists: {checkpoint_path}")
            return _write_checkpoint(run_dir, checkpoint)


@_serialized_mutation
def escalate_checkpoint(
    run_dir: Path,
    *,
    tier: str,
    reason: str,
    rigor_decision_sha256: str | None = None,
) -> dict[str, Any]:
    """Record a monotonic rigor escalation for an active run."""
    if not isinstance(tier, str) or tier not in {"standard", "full"}:
        raise ValueError("tier must be standard or full")
    reason = _nonempty(reason, "reason")
    if rigor_decision_sha256 is not None and (
        not isinstance(rigor_decision_sha256, str) or not SHA256_PATTERN.fullmatch(rigor_decision_sha256)
    ):
        raise ValueError("rigor_decision_sha256 must be a SHA-256 digest")
    checkpoint = load_checkpoint(Path(run_dir))
    if checkpoint["state"] not in NONTERMINAL_STATES:
        raise ValueError("cannot escalate a terminal checkpoint")
    current = checkpoint.get("rigor", {}).get("tier")
    tier_order = {"standard": 0, "full": 1}
    if current is not None and tier_order[tier] <= tier_order[current]:
        raise ValueError("escalation tier must be higher than the current tier")
    entry: dict[str, str] = {"tier": tier, "at": _timestamp(), "reason": reason}
    if rigor_decision_sha256 is not None:
        entry["decision_sha256"] = rigor_decision_sha256
    history = checkpoint.get("rigor", {}).get("history", [])
    checkpoint["rigor"] = {"tier": tier, "history": [*history, entry]}
    if "run_budget" in checkpoint:
        budget = checkpoint["run_budget"]
        budget["tier"] = tier
        failed_limit, review_limit = (2, 1) if tier == "standard" else (3, 2)
        budget["max_failed_attempts_per_class"] = max(budget["max_failed_attempts_per_class"], failed_limit)
        budget["max_review_rounds"] = max(budget["max_review_rounds"], review_limit)
    _touch(checkpoint)
    return _write_checkpoint(Path(run_dir), checkpoint)


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


@_serialized_mutation
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
    if checkpoint.get("session_binding", {}).get("mode") == "hookless":
        raise ValueError(
            "hookless checkpoints do not support claim or key rotation; continue the same run directory with checkpoint commands that do not require --session-key"
        )
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
        raise ValueError(
            f"{field} must be a run-relative evidence path: got {artifact_ref!r}; "
            "pass a path relative to the run directory such as 'protocol.md'"
        )
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


@_serialized_mutation
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


@_serialized_mutation
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


@_serialized_mutation
def advance_checkpoint(
    run_dir: Path,
    *,
    completed_step: str | None,
    next_step: str | None,
    next_action: str,
) -> dict[str, Any]:
    """Complete the current step or recover a cursorless checkpoint."""
    checkpoint = load_checkpoint(Path(run_dir))
    if checkpoint["state"] != "active":
        raise ValueError("only an active checkpoint can advance")
    by_id = {step["id"]: step for step in checkpoint["steps"]}
    current_step = checkpoint["current_step"]
    if completed_step is None:
        if current_step is not None:
            raise ValueError(f"cannot start a pending step while current step {current_step!r} is in progress; --complete is required")
        if next_step is None:
            raise ValueError("--next is required when no step is in progress")
    elif current_step != completed_step:
        if current_step is None:
            pending = [step["id"] for step in checkpoint["steps"] if step["status"] == "pending"]
            raise ValueError(
                "completed_step must be the current step: no step is in progress; "
                f"pending steps: {', '.join(pending) or '(none)'}. Recover with advance RUN --next STEP --next-action TEXT"
            )
        raise ValueError(f"completed_step must be the current step: {current_step}")
    else:
        by_id[completed_step]["status"] = "completed"
    if next_step is None and completed_step is not None:
        next_step = next((step["id"] for step in checkpoint["steps"] if step["status"] == "pending"), None)
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


@_serialized_mutation
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
    _ensure_before_deadline(checkpoint)
    failure_class = _nonempty(failure_class, "failure_class")
    count = sum(item.get("failure_class") == failure_class for item in checkpoint["attempts"])
    maximum = checkpoint.get("run_budget", {}).get("max_failed_attempts_per_class", MAX_ATTEMPTS_PER_FAILURE)
    if count >= maximum:
        raise RuntimeError(
            f"retry budget exhausted for {failure_class}; change the hypothesis to a different route, open a decision gate, or finish-partial if no in-scope route remains"
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


@_serialized_mutation
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


@_serialized_mutation
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


@_serialized_mutation
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


@_serialized_mutation
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


@_serialized_mutation
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


def budget_status(run_dir: Path, *, now: datetime | None = None) -> dict[str, Any]:
    """Return budget consumption and exhaustion without changing checkpoint state."""
    checkpoint = load_checkpoint(Path(run_dir))
    budget = checkpoint.get("run_budget")
    if budget is None:
        raise ValueError("checkpoint has no opt-in run budget")
    now = now or _now()
    deadline_passed = budget["deadline_at"] is not None and now >= _parse_deadline(budget["deadline_at"])
    remaining_seconds = (
        max(0, int((_parse_deadline(budget["deadline_at"]) - now).total_seconds()))
        if budget["deadline_at"] is not None else None
    )
    counts: dict[str, int] = {}
    for attempt in checkpoint["attempts"]:
        counts[attempt["failure_class"]] = counts.get(attempt["failure_class"], 0) + 1
    exhausted = [f"failed_attempts_per_class:{key}" for key, count in sorted(counts.items()) if count >= budget["max_failed_attempts_per_class"]]
    review = checkpoint.get("review_receipt")
    passing_review = bool(
        review
        and review.get("verdict") == "passed"
        and review.get("independence_attested") is True
    )
    if len(checkpoint["review_rounds"]) >= budget["max_review_rounds"] and (
        not passing_review
    ):
        exhausted.append("review_rounds")
    if deadline_passed:
        exhausted.append("deadline")
    return {"run_id": Path(run_dir).name, "tier": budget["tier"], "failed_attempts": counts,
            "max_failed_attempts_per_class": budget["max_failed_attempts_per_class"],
            "review_rounds": len(checkpoint["review_rounds"]), "max_review_rounds": budget["max_review_rounds"],
            "deadline_at": budget["deadline_at"], "deadline_passed": deadline_passed,
            "remaining_seconds": remaining_seconds,
            "exhausted": bool(exhausted), "exhausted_limits": exhausted}


def _ensure_before_deadline(checkpoint: dict[str, Any]) -> None:
    budget = checkpoint.get("run_budget")
    if budget and budget["deadline_at"] is not None and _now() >= _parse_deadline(budget["deadline_at"]):
        raise RuntimeError("run deadline passed; finalize the partial result")


def _read_validated_partial_artifact(
    run_dir: Path,
    checkpoint: dict[str, Any],
    artifact_ref: str,
) -> tuple[dict[str, Any], str]:
    """Read and validate partial evidence once, returning its content and digest."""
    path = _artifact_path(run_dir, artifact_ref, "partial artifact")
    artifact_bytes = path.read_bytes()
    try:
        result = json.loads(artifact_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeError):
        raise ValueError("partial artifact must be valid JSON") from None
    expected = {
        "schema_version", "status", "result_refs", "unmet_criteria",
        "unfinished_steps", "caveats", "review_status",
    }
    if (
        not isinstance(result, dict)
        or set(result) != expected
        or result.get("schema_version") != 1
        or result.get("status") != "partial"
    ):
        raise ValueError("partial artifact schema is invalid")
    for field in ("result_refs", "unmet_criteria", "unfinished_steps", "caveats"):
        if not isinstance(result[field], list) or any(
            not isinstance(item, str) or not item.strip() for item in result[field]
        ):
            raise ValueError(f"partial artifact {field} must be a list of non-empty strings")
    if not result["caveats"] or not isinstance(result["review_status"], str) or not result["review_status"].strip():
        raise ValueError("partial artifact requires caveats and review_status")
    for ref in result["result_refs"]:
        _artifact_path(run_dir, ref, "partial result ref")
    criterion_ids = {item["id"] for item in checkpoint["done_criteria"]}
    step_ids = {item["id"] for item in checkpoint["steps"]}
    expected_unmet = {item["id"] for item in checkpoint["done_criteria"] if item["status"] != "satisfied"}
    expected_unfinished = {item["id"] for item in checkpoint["steps"] if item["status"] != "completed"}
    if set(result["unmet_criteria"]) != expected_unmet or not expected_unmet <= criterion_ids:
        raise ValueError("partial artifact unmet_criteria is inconsistent")
    if set(result["unfinished_steps"]) != expected_unfinished or not expected_unfinished <= step_ids:
        raise ValueError("partial artifact unfinished_steps is inconsistent")
    return result, hashlib.sha256(artifact_bytes).hexdigest()


@_serialized_mutation
def finish_partial(run_dir: Path, *, artifact_ref: str) -> dict[str, Any]:
    """Validate partial evidence and atomically abandon an exhausted budgeted run."""
    run_dir = Path(run_dir)
    checkpoint = load_checkpoint(run_dir)
    if "run_budget" not in checkpoint:
        raise ValueError("checkpoint has no opt-in run budget")
    if checkpoint["state"] not in NONTERMINAL_STATES:
        raise ValueError("only a nonterminal checkpoint can finish partially")
    if checkpoint["state"] in {"approval_required", "waiting_external"}:
        raise ValueError("partial completion cannot override an approval gate or external wait")
    if checkpoint["outer_goal"]["phase"] == "completion_pending":
        raise ValueError("native Goal completion_pending cannot finish partially")
    status = budget_status(run_dir)
    if not status["exhausted"]:
        raise ValueError("run budget is not exhausted and deadline has not passed")
    try:
        _check_local_completion(checkpoint)
    except ValueError:
        pass
    else:
        raise ValueError("run satisfies local completion checks; complete it instead of finishing partially")
    reason = "deadline_passed" if status["deadline_passed"] else "budget_exhausted"
    _, artifact_sha256 = _read_validated_partial_artifact(run_dir, checkpoint, artifact_ref)
    _nonempty(artifact_ref, "artifact_ref")
    checkpoint["state"] = "abandoned"
    checkpoint["current_step"] = None
    for step in checkpoint["steps"]:
        if step["status"] == "in_progress": step["status"] = "pending"
    checkpoint["next_action"] = ""
    checkpoint["pending_decisions"] = []
    checkpoint["blocker"] = ""
    checkpoint["wait"] = None
    checkpoint["termination_reason"] = reason
    checkpoint["termination"] = {"kind": "partial", "reason_code": reason,
        "exhausted_limit": ",".join(status["exhausted_limits"]), "recorded_at": _timestamp(),
        "artifact_ref": artifact_ref, "artifact_sha256": artifact_sha256}
    _reset_idle_continuations(checkpoint)
    _touch(checkpoint)
    return _write_checkpoint(run_dir, checkpoint)


@_serialized_mutation
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


@_serialized_mutation
def record_review(
    run_dir: Path,
    *,
    artifact_ref: str,
) -> dict[str, Any]:
    """Attach a review artifact whose own fields attest reviewer and independence."""
    checkpoint = load_checkpoint(Path(run_dir))
    if checkpoint["schema_version"] < 4 or checkpoint["state"] != "active":
        raise ValueError("only an active schema-v4 checkpoint can record review")
    _ensure_before_deadline(checkpoint)
    if "run_budget" in checkpoint and len(checkpoint["review_rounds"]) >= checkpoint["run_budget"]["max_review_rounds"]:
        raise RuntimeError("review round budget exhausted")
    path = _artifact_path(Path(run_dir), artifact_ref, "review artifact")
    receipt_bytes = path.read_bytes()
    try:
        receipt = json.loads(receipt_bytes.decode("utf-8"))
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
    known_severities = {"critical", "major", "minor", "suggestion"}
    unresolved_blocking = any(
        not isinstance(item, dict)
        or item.get("severity") not in known_severities
        or (
            item.get("severity") in {"critical", "major"}
            and item.get("resolution_status", "open") not in {"resolved", "not-applicable"}
        )
        for item in findings
    )
    if verdict == "passed" and unresolved_blocking:
        raise ValueError("passed review artifact cannot retain unresolved critical or major findings")
    receipt_sha256 = hashlib.sha256(receipt_bytes).hexdigest()
    manifest, registration = _prepare_review_manifest(Path(run_dir), path, receipt, receipt_bytes)
    checkpoint["review_receipt"] = {
        "reviewer": _nonempty(reviewer, "reviewer"),
        "verdict": verdict,
        "artifact_ref": artifact_ref,
        "artifact_sha256": receipt_sha256,
        "independence_attested": independent,
        "recorded_at": _timestamp(),
    }
    if "run_budget" in checkpoint:
        rounds = checkpoint["review_rounds"]
        rounds.append({"id": f"review-{len(rounds) + 1}", "started_at": _timestamp(),
                      "receipt_ref": artifact_ref, "receipt_sha256": receipt_sha256})
    _reset_idle_continuations(checkpoint)
    _touch(checkpoint)
    result = _write_checkpoint(Path(run_dir), checkpoint)
    if manifest is not None:
        try:
            write_text_atomic(
                Path(run_dir) / "manifest.json",
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            )
        except OSError as error:
            registration = {
                "status": "failed",
                "reason": str(error),
                "checkpoint_recorded": True,
            }
    result["manifest_registration"] = registration
    return result


def _prepare_review_manifest(
    run_dir: Path, receipt_path: Path, receipt: dict[str, Any], receipt_bytes: bytes
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    from codex_science.artifacts import validate_manifest
    from codex_science.review_receipts import validate_review_receipt

    if receipt.get("status") != "passed":
        return None, {"status": "skipped", "reason": "receipt verdict is not passed"}
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        return None, {"status": "skipped", "reason": "manifest.json is missing"}
    if manifest_path.is_symlink() or not manifest_path.is_file():
        return None, {"status": "skipped", "reason": "manifest.json is not a regular file"}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError, OSError):
        return None, {"status": "skipped", "reason": "manifest.json is malformed or unreadable"}
    if not isinstance(manifest, dict):
        return None, {"status": "skipped", "reason": "manifest.json is not an object"}
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        return None, {"status": "skipped", "reason": "manifest artifacts is not a list"}

    relative = receipt_path.relative_to(run_dir.resolve()).as_posix()
    kind = (
        "review-receipt-v2"
        if receipt.get("schema_version") == 1 and isinstance(receipt.get("review_id"), str)
        else "review-receipt"
    )
    if kind == "review-receipt-v2":
        try:
            validate_review_receipt(receipt)
        except ValueError as error:
            return None, {"status": "skipped", "reason": f"invalid review receipt: {error}"}
    verdict_note: dict[str, Any] = {}
    if kind == "review-receipt-v2":
        from codex_science.run_packaging import plan_receipt_registration

        try:
            planned, summary = plan_receipt_registration(run_dir, manifest, relative)
            record_runtime_identity(planned)
            validate_manifest(planned)
        except Exception as error:  # verdict recording is optional; any failure must keep the listing-only checkpoint
            verdict_note = {
                "verdict_recorded": False,
                "reason": f"{type(error).__name__}: {error}; run package_run.py refresh --register-receipt after fixing",
            }
        else:
            status = "updated" if summary.get("updated") or summary.get("already_registered") else "registered"
            return planned, {"status": status, "path": relative, "kind": summary["kind"], "verdict_recorded": True}
    digest = hashlib.sha256(receipt_bytes).hexdigest()
    normalized_relative = _normalized_manifest_artifact_path(relative)
    previous_index = next((
        index
        for index, item in enumerate(artifacts)
        if isinstance(item, dict)
        and _normalized_manifest_artifact_path(item.get("path")) == normalized_relative
    ), None)
    record = {"path": relative, "kind": kind, "sha256": digest}
    if previous_index is None:
        artifacts.append(record)
        status = "registered"
    else:
        previous = artifacts[previous_index]
        if "size_bytes" in previous:
            record["size_bytes"] = len(receipt_bytes)
        artifacts[previous_index] = record
        status = "updated"
    try:
        record_runtime_identity(manifest)
        validate_manifest(manifest)
    except ValueError as error:
        return None, {"status": "skipped", "reason": str(error)}
    return manifest, {"status": status, "path": relative, "kind": kind, **verdict_note}


def _normalized_manifest_artifact_path(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    while value.startswith("./"):
        value = value[2:]
    return PurePosixPath(value).as_posix()


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


def _check_completion_bundle(run_dir: Path) -> None:
    from codex_science.artifacts import validate_bundle
    from codex_science.review import review_manifest

    manifest_path = Path(run_dir) / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        sidecars = validate_bundle(manifest, manifest_path.parent)
        review = review_manifest(manifest, manifest_path.parent, sidecars=sidecars)
        if review["status"] != "passed":
            findings = "; ".join(f"{item['code']}: {item['message']}" for item in review["findings"])
            raise ValueError(findings)
    except (ValueError, OSError, UnicodeError, TypeError, KeyError, AttributeError) as error:
        raise ValueError(
            f"completion blocked by manifest.json validation: {error}; "
            "run validate_artifact.py <manifest> --review-output <output> --require-passed-review"
        ) from error


@_serialized_mutation
def complete_checkpoint(run_dir: Path) -> dict[str, Any]:
    """Finish local verification or enter native-Goal completion handoff."""
    checkpoint = load_checkpoint(Path(run_dir))
    if checkpoint["schema_version"] < 4:
        raise ValueError("claim and re-verify a legacy checkpoint before completion")
    if checkpoint["state"] != "active":
        raise ValueError("only an active checkpoint can complete")
    _check_local_completion(checkpoint)
    _check_completion_evidence(Path(run_dir), checkpoint)
    _check_completion_bundle(Path(run_dir))
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


@_serialized_mutation
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
    _check_completion_bundle(Path(run_dir))
    path = _artifact_path(Path(run_dir), receipt_ref, "Goal completion receipt")
    receipt_bytes = path.read_bytes()
    try:
        receipt = json.loads(receipt_bytes.decode("utf-8"))
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
        "artifact_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
        "recorded_at": _timestamp(),
    }
    checkpoint["next_action"] = ""
    _touch(checkpoint)
    return _write_checkpoint(Path(run_dir), checkpoint)
