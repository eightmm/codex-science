"""Read-only completion summaries derived from run checkpoints and artifacts.

The completion-rate denominator includes every run except fresh ``active``
runs (reported as ``in_progress``). Invalid runs count as non-completions.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

RIGOR_TIERS = {"standard", "full"}


def _short(value: Any) -> str:
    text = " ".join(str(value).split())
    text = re.sub(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*[^ ,;]+", r"\1=[REDACTED]", text)
    return text[:200]


def _safe_child(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def _manifest_inconclusive(path: Path) -> bool:
    """A manifest is inconclusive when top-level result.status is inconclusive,
    or when it has claims and every claim status is inconclusive/conflicting.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    result = data.get("result")
    if isinstance(result, dict) and result.get("status") == "inconclusive":
        return True
    claims = data.get("claims")
    return bool(isinstance(claims, list) and claims and all(
        isinstance(claim, dict) and claim.get("status") in {"inconclusive", "conflicting"}
        for claim in claims
    ))


def report_completion(artifacts_root: Path, *, now: datetime, stale_after: timedelta) -> dict[str, Any]:
    """Summarize checkpoint runs without writing. Stop reasons retain their
    recorded codes; fresh active runs have outcome ``active`` and aggregate as
    ``in_progress`` rather than as a terminal outcome.
    """
    from codex_science.checkpoints import MAX_AUTOCONTINUE_CHECKPOINT_BYTES, validate_checkpoint

    root = Path(artifacts_root).resolve()
    runs = []
    for checkpoint_path in sorted(Path(artifacts_root).glob("*/checkpoint.json")):
        run_dir = checkpoint_path.parent
        if run_dir.name.startswith(".") or run_dir.is_symlink() or not run_dir.is_dir() or checkpoint_path.is_symlink() or not _safe_child(checkpoint_path, root):
            continue
        checkpoint = None
        try:
            if checkpoint_path.stat().st_size > MAX_AUTOCONTINUE_CHECKPOINT_BYTES:
                raise ValueError("checkpoint.json exceeds MAX_AUTOCONTINUE_CHECKPOINT_BYTES")
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            if not isinstance(checkpoint, dict):
                raise ValueError("checkpoint root must be an object")
            validate_checkpoint(checkpoint)
            if "rigor" in checkpoint:
                rigor = checkpoint["rigor"]
                if not isinstance(rigor, dict):
                    raise ValueError("rigor must be an object")
                tier = rigor.get("tier")
                if not isinstance(tier, str) or tier not in RIGOR_TIERS:
                    raise ValueError("rigor.tier must be 'standard' or 'full'")
            else:
                tier = "legacy"
        except Exception as exc:
            record = checkpoint if isinstance(checkpoint, dict) else {}
            steps = record.get("steps", [])
            criteria = record.get("done_criteria", [])
            runs.append({"run_id": run_dir.name, "outcome": "invalid", "stop_reason": {"code": "invalid_record", "detail": _short(exc)}, "tier": "legacy", "schema_version": record.get("schema_version"), "state": record.get("state"), "steps_completed": sum(s.get("status") == "completed" for s in steps if isinstance(s, dict)) if isinstance(steps, list) else 0, "steps_total": len(steps) if isinstance(steps, list) else 0, "criteria_satisfied": sum(c.get("status") == "satisfied" for c in criteria if isinstance(c, dict)) if isinstance(criteria, list) else 0, "criteria_total": len(criteria) if isinstance(criteria, list) else 0, "review_attached": isinstance(record.get("review_receipt"), dict), "updated_at": record.get("updated_at"), "evidence_refs": ["checkpoint.json"], "invalid": _short(exc)})
            continue
        try:
            runs.append(_summarize_run(run_dir, checkpoint, tier, root, now, stale_after))
        except Exception as exc:
            runs.append({"run_id": run_dir.name, "outcome": "invalid", "stop_reason": {"code": "invalid_record", "detail": _short(exc)}, "tier": tier, "schema_version": checkpoint.get("schema_version"), "state": checkpoint.get("state"), "steps_completed": 0, "steps_total": 0, "criteria_satisfied": 0, "criteria_total": 0, "review_attached": False, "updated_at": checkpoint.get("updated_at"), "evidence_refs": ["checkpoint.json"], "invalid": _short(exc)})
    counts = Counter("in_progress" if r["outcome"] == "active" else r["outcome"] for r in runs)
    denomin = sum(count for outcome, count in counts.items() if outcome != "in_progress")
    return {"schema": "completion-report-v1", "runs": runs, "aggregate": {"by_outcome": dict(sorted(counts.items())), "by_tier": dict(sorted(Counter(r["tier"] for r in runs).items())), "by_stop_reason": dict(sorted(Counter(r["stop_reason"]["code"] for r in runs).items())), "in_progress": counts.get("in_progress", 0), "completion_rate": (counts.get("completed", 0) / denomin if denomin else None), "completion_numerator": counts.get("completed", 0), "completion_denominator": denomin, "denominator_rule": "all runs except fresh active (in_progress); invalid runs count as non-completions"}}


def _summarize_run(run_dir: Path, checkpoint: dict[str, Any], tier: str, root: Path, now: datetime, stale_after: timedelta) -> dict[str, Any]:
        state = checkpoint["state"]
        termination = checkpoint.get("termination")
        partial = termination is not None
        if partial:
            from codex_science.checkpoints import _read_validated_partial_artifact
            _, artifact_sha256 = _read_validated_partial_artifact(
                run_dir, checkpoint, termination["artifact_ref"]
            )
            if artifact_sha256 != termination["artifact_sha256"]:
                raise ValueError("partial artifact hash mismatch")
        manifest = run_dir / "manifest.json"
        inconclusive = manifest.is_file() and not manifest.is_symlink() and _safe_child(manifest, root) and _manifest_inconclusive(manifest)
        updated = checkpoint["updated_at"]
        try:
            stamp = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            reference_now = now if now.tzinfo else now.astimezone()
            stale = state == "active" and stamp < reference_now - stale_after
        except (ValueError, TypeError, OverflowError):
            stale = False
        outcome = "terminal_inconclusive" if partial else (("terminal_inconclusive" if inconclusive else "completed") if state == "complete" else state)
        if stale:
            outcome = "stale_active"
        blocker = checkpoint.get("blocker")
        blocker = blocker if isinstance(blocker, str) else ""
        termination_reason = checkpoint.get("termination_reason")
        termination_reason = termination_reason if isinstance(termination_reason, str) else ""
        wait = checkpoint.get("wait")
        wait_detail = wait.get("reason", "") if isinstance(wait, dict) else ""
        if not isinstance(wait_detail, str): wait_detail = ""
        decisions = checkpoint.get("pending_decisions")
        if not isinstance(decisions, (list, str)): decisions = ""
        if state == "complete":
            code, detail = ("inconclusive_result", termination_reason) if inconclusive else ("done", termination_reason)
        elif state == "approval_required": code, detail = "approval_gate", decisions
        elif state == "waiting_external": code, detail = "external_wait", wait_detail
        elif state == "blocked": code, detail = "blocker", blocker
        elif partial: code, detail = "budget_exhausted", termination["reason_code"]
        elif state == "abandoned": code, detail = "abandoned", termination_reason
        elif state == "active" and stale: code, detail = "no_progress", blocker
        elif state == "active": code, detail = "in_progress", checkpoint.get("next_action", "")
        else: code, detail = "invalid_record", "unknown state"
        refs = ["checkpoint.json"]
        for ref in ("manifest.json", "index.md"):
            candidate = run_dir / ref
            if candidate.is_file() and not candidate.is_symlink() and _safe_child(candidate, root): refs.append(ref)
        receipt = checkpoint.get("review_receipt")
        review_attached = isinstance(receipt, dict)
        if review_attached:
            ref = receipt.get("artifact_ref")
            if isinstance(ref, str):
                ref = ref.split("#", 1)[0]
                candidate = run_dir / ref
                if _safe_child(candidate, root) and candidate.is_file() and not candidate.is_symlink(): refs.append(ref)
        if partial and termination["artifact_ref"] not in refs: refs.append(termination["artifact_ref"])
        binding = checkpoint.get("session_binding")
        record = {"run_id": run_dir.name, "outcome": outcome, "stop_reason": {"code": code, "detail": _short(detail)}, "tier": tier, "schema_version": checkpoint.get("schema_version"), "state": state, "steps_completed": sum(s.get("status") == "completed" for s in checkpoint.get("steps", [])), "steps_total": len(checkpoint.get("steps", [])), "criteria_satisfied": sum((c.get("status") == "satisfied" if isinstance(c, dict) else False) for c in checkpoint.get("done_criteria", [])), "criteria_total": len(checkpoint.get("done_criteria", [])), "review_attached": review_attached, "updated_at": updated, "evidence_refs": refs}
        if isinstance(binding, dict):
            record["session_binding_mode"] = binding["mode"]
        return record


def render_markdown(report: dict[str, Any]) -> str:
    aggregate = report["aggregate"]
    rate = aggregate["completion_rate"]
    lines = ["# Completion report", "", "## Status", f"Runs: {len(report['runs'])}; completed: {aggregate['completion_numerator']}/{aggregate['completion_denominator']}; rate: {'n/a' if rate is None else f'{rate:.1%}'}", "", "## Current"]
    lines.extend(f"- {r['run_id']}: {r['outcome']} ({r['stop_reason']['code']})" for r in report["runs"])
    lines.extend(["", "## Next", "Review gated, waiting, blocked, or stale runs.", "", "## Evidence", "Derived from checkpoint.json and existing run artifacts."])
    return "\n".join(lines) + "\n"
