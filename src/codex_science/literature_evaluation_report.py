"""Deterministic grading and descriptive summaries for literature evaluation runs."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any, Iterable, Mapping

from .literature_evaluation_runner import RECEIPT_SCHEMA, evaluate_criteria
from .rubric_tree import grade as grade_rubric


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_regular(path: Path) -> bytes:
    """Read one regular file without following its final symlink."""
    if not stat.S_ISREG(path.lstat().st_mode):
        raise OSError(f"not a regular file: {path}")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError(f"not a regular file: {path}")
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = -1
            return handle.read()
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _hash_recorded_artifacts(receipt: Mapping[str, Any], run_dir: Path) -> bool:
    files = receipt.get("artifact_files")
    if not isinstance(files, list):
        raise TypeError("receipt artifact_files must be a list")
    root = Path(run_dir) / "project" / "artifacts"
    try:
        if not stat.S_ISDIR(Path(run_dir).lstat().st_mode):
            return False
        if not stat.S_ISDIR((Path(run_dir) / "project").lstat().st_mode):
            return False
        root_mode = root.lstat().st_mode
    except OSError:
        return not files
    if not stat.S_ISDIR(root_mode):
        return False
    for item in files:
        if not isinstance(item, Mapping) or not isinstance(item.get("path"), str) or not isinstance(item.get("sha256"), str):
            raise TypeError("receipt artifact_files entries require path and sha256 strings")
        raw = item["path"]
        relative = PurePosixPath(raw)
        if "\\" in raw or "\0" in raw or relative.is_absolute() or not relative.parts or ".." in relative.parts:
            return False
        current = root
        try:
            for part in relative.parts[:-1]:
                current = current / part
                if not stat.S_ISDIR(current.lstat().st_mode):
                    return False
            target = current / relative.parts[-1]
            data = _read_regular(target)
            target.resolve(strict=True).relative_to(root.resolve(strict=True))
        except (OSError, ValueError):
            return False
        if _sha(data) != item["sha256"]:
            return False
    return True


def _integrity_ok(receipt: Mapping[str, Any], run_dir: Path) -> tuple[bool, str | None, bytes | None]:
    try:
        if not stat.S_ISDIR(Path(run_dir).lstat().st_mode):
            return False, None, None
        last = _read_regular(Path(run_dir) / "last.md")
        receipt_path = Path(run_dir) / "receipt.json"
        if not stat.S_ISREG(receipt_path.lstat().st_mode):
            return False, None, None
    except OSError:
        return False, None, None
    receipt_hash = receipt.get("_report_receipt_sha256")
    if not isinstance(receipt_hash, str):
        try:
            receipt_hash = _sha(_read_regular(receipt_path))
        except OSError:
            return False, None, None
    if not isinstance(receipt.get("last_message_sha256"), str) or _sha(last) != receipt["last_message_sha256"]:
        return False, receipt_hash, None
    if not _hash_recorded_artifacts(receipt, Path(run_dir)):
        return False, receipt_hash, None
    return True, receipt_hash, last


def _has_unrecorded_artifact(receipt: Mapping[str, Any], run_dir: Path) -> bool:
    root = Path(run_dir) / "project" / "artifacts"
    if not root.exists():
        return False
    recorded = {PurePosixPath(item["path"]).as_posix() for item in receipt["artifact_files"]}
    pending = [root]
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                metadata = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(metadata.st_mode):
                    pending.append(Path(entry.path))
                elif stat.S_ISREG(metadata.st_mode):
                    relative = Path(entry.path).relative_to(root).as_posix()
                    if relative not in recorded:
                        return True
    return False


def _trace_citations(receipt: Mapping[str, Any], run_dir: Path) -> dict[str, Any]:
    try:
        from .citation_trace import trace_citations
    except ImportError:
        return {"status": "unavailable"}
    files = receipt.get("artifact_files", [])
    if not isinstance(files, list):
        raise TypeError("receipt artifact_files must be a list")
    manifests = [PurePosixPath(item["path"]) for item in files
                 if isinstance(item, Mapping) and isinstance(item.get("path"), str)
                 and PurePosixPath(item["path"]).name == "manifest.json"]
    results = []
    artifacts_root = Path(run_dir) / "project" / "artifacts"
    for manifest in manifests:
        bundle = manifest.parent
        reports = []
        for item in files:
            if not isinstance(item, Mapping) or not isinstance(item.get("path"), str):
                continue
            path = PurePosixPath(item["path"])
            if path.suffix.lower() not in {".md", ".markdown"}:
                continue
            try:
                reports.append(path.relative_to(bundle).as_posix())
            except ValueError:
                continue
        results.append(trace_citations(artifacts_root / Path(bundle), reports))
    if not results:
        return {"status": "unavailable"}
    counts = [result.get("counts", {}) for result in results if isinstance(result, Mapping)]
    cited = sum(row.get("cited", 0) for row in counts)
    traced = sum(row.get("traced", 0) for row in counts)
    orphans = sum(row.get("orphans", 0) for row in counts)
    return {"status": "available", "citations_total": cited,
            "citations_traced": traced, "orphan_citations": orphans}


def _partial_credit(criteria: list[Mapping[str, Any]]) -> float | None:
    """Score criterion coverage with an equal-weight secondary rubric."""
    tree = {"schema": "rubric-tree-v1", "id": "literature-partial-credit", "root": {
        "id": "criteria", "title": "Automated task criteria", "weight": 1,
        "children": [{"id": f"criterion-{row['id']}", "title": str(row["id"]), "weight": 1,
                      "check": {"kind": "criterion", "criterion_id": str(row["id"])}}
                     for row in criteria]}}
    result = grade_rubric(tree, {str(row["id"]): row["passed"] for row in criteria})
    return result["score"]


def grade_run(receipt: Mapping[str, Any], task: Mapping[str, Any], run_dir: Path) -> dict[str, Any]:
    """Grade one receipt against its frozen task, retaining rejection reasons."""
    task_spec = task.get("spec")
    errors = []
    if not isinstance(receipt, Mapping) or receipt.get("schema") != RECEIPT_SCHEMA:
        errors.append("invalid_receipt_schema")
    if not isinstance(task_spec, Mapping):
        errors.append("invalid_task")
    if isinstance(receipt, Mapping):
        if type(receipt.get("executed")) is not bool: errors.append("invalid_executed_flag")
        if type(receipt.get("timed_out")) is not bool: errors.append("invalid_timeout_flag")
        if receipt.get("exit_code") is not None and (not isinstance(receipt.get("exit_code"), int) or isinstance(receipt.get("exit_code"), bool)):
            errors.append("invalid_exit_code")
        if receipt.get("task_id") != task.get("id"): errors.append("task_id_mismatch")
        if receipt.get("task_digest") != task.get("digest"): errors.append("task_digest_mismatch")
        if not isinstance(receipt.get("set_digest"), str): errors.append("missing_set_digest")
        if task.get("set_digest") is not None and receipt.get("set_digest") != task.get("set_digest"):
            errors.append("set_digest_mismatch")
    if errors:
        return {"schema": "literature-eval-graded-run-v1", "task_id": task.get("id"),
                "task_digest": task.get("digest"), "set_digest": receipt.get("set_digest") if isinstance(receipt, Mapping) else None,
                "outcome": "rejected", "stop_reason": "digest_mismatch" if any("digest" in e for e in errors) else "invalid_receipt",
                "errors": errors, "criteria": [], "partial_credit": None, "citations": {"status": "unavailable"}}
    assert isinstance(task_spec, Mapping)
    integrity_ok, receipt_hash, last_bytes = _integrity_ok(receipt, Path(run_dir))
    if not integrity_ok:
        return {"schema": "literature-eval-graded-run-v1", "task_id": task.get("id"),
                "task_digest": task.get("digest"), "set_digest": receipt.get("set_digest"),
                "outcome": "rejected", "stop_reason": "artifact_hash_mismatch", "errors": ["artifact_hash_mismatch"],
                "criteria": [], "partial_credit": None, "citations": {"status": "unavailable"}, "executed": receipt.get("executed") is True,
                "receipt_sha256": receipt_hash}
    if _has_unrecorded_artifact(receipt, Path(run_dir)):
        return {"schema": "literature-eval-graded-run-v1", "task_id": task.get("id"),
                "task_digest": task.get("digest"), "set_digest": receipt.get("set_digest"),
                "outcome": "rejected", "stop_reason": "unrecorded_artifact", "errors": ["unrecorded_artifact"],
                "criteria": [], "partial_credit": None, "citations": {"status": "unavailable"}, "executed": receipt.get("executed") is True,
                "receipt_sha256": receipt_hash}
    project = Path(run_dir) / "project"
    last_message = (last_bytes or b"").decode("utf-8", errors="replace")
    criteria = evaluate_criteria(task_spec["criteria"], project, last_message)
    partial_credit = _partial_credit(criteria)
    try:
        citations = _trace_citations(receipt, Path(run_dir))
    except (OSError, ValueError):
        citations = {"status": "unavailable", "reason": "bundle_input_unavailable"}
    completion = receipt.get("completion_report", {})
    completion_codes = set()
    completion_signals = set()
    if isinstance(completion, Mapping):
        completion_runs = completion.get("runs", [])
        if not isinstance(completion_runs, list):
            raise TypeError("completion_report runs must be a list")
        for row in completion_runs:
            if not isinstance(row, Mapping):
                raise TypeError("completion_report run entries must be objects")
            stop_reason = row.get("stop_reason")
            if "stop_reason" in row and not isinstance(stop_reason, Mapping):
                raise TypeError("completion_report stop_reason must be an object")
            if isinstance(stop_reason, Mapping) and isinstance(stop_reason.get("code"), str):
                completion_codes.add(stop_reason["code"])
            for key in ("outcome", "state"):
                if isinstance(row.get(key), str):
                    completion_signals.add(row[key])
    else:
        raise TypeError("completion_report must be an object")
    statuses = completion_codes | completion_signals
    text = last_message.lower()
    exit_code, timed_out = receipt.get("exit_code"), receipt.get("timed_out")
    unsure_statuses = {"inconclusive_result", "terminal_inconclusive", "approval_gate", "approval_required",
                       "gated", "external_wait", "waiting_external", "waiting", "in_progress"}
    unsure_reasons = statuses & unsure_statuses
    offers_escalation = re.search(r"\b(escalat\w*)\b", text)
    avoids_fabrication = re.search(r"\b(no result|result unavailable|not fabricated|without fabricating|"
                                  r"(?:without|not|never|cannot|can't|won't|do not|don't)\s+(?:fabricat\w+|invent\w+))\b", text)
    unsure = bool(unsure_reasons) or bool(offers_escalation and avoids_fabrication)
    event_metrics = receipt.get("event_metrics")
    error_message = event_metrics.get("error_message") if isinstance(event_metrics, Mapping) else None
    provider_unavailable = isinstance(error_message, str) and re.search(
        r"\b(?:at capacity|overloaded|rate[- ]limit(?:ed)?|(?:http|status|error)\s*429|429\s+too many requests|503\s+(?:service\s+)?unavailable)\b",
        error_message, re.IGNORECASE)
    provider_policy_block = isinstance(error_message, str) and re.search(
        r"\b(?:flagged for possible|content\s+(?:was\s+)?flagged|violat\w*\s+(?:our|the)\s+usage polic\w*)\b",
        error_message, re.IGNORECASE)
    if timed_out is True:
        outcome, stop_reason = "failed", "timeout"
    elif exit_code != 0:
        outcome, stop_reason = "failed", ("provider_unavailable" if provider_unavailable else
                                            "provider_policy_block" if provider_policy_block else "nonzero_exit")
    elif unsure:
        outcome, stop_reason = "unsure", next(iter(sorted(unsure_reasons or {"escalation_offered"})))
    elif statuses - {"done", "completed", "complete", ""}: outcome, stop_reason = "failed", sorted(statuses - {"done", "completed", "complete", ""})[0]
    elif not all(row["passed"] for row in criteria): outcome, stop_reason = "failed", "criteria_failed"
    # Standard/full runs require durable artifacts; quick tasks intentionally do not.
    elif task_spec.get("expected_tier") in {"standard", "full"} and not receipt.get("artifact_files"): outcome, stop_reason = "failed", "no_artifacts"
    elif all(row["passed"] for row in criteria): outcome, stop_reason = "completed", "done"
    else: outcome, stop_reason = "failed", "criteria_failed"
    loaded_runtime = receipt.get("loaded_runtime")
    loaded_runtime = dict(loaded_runtime) if isinstance(loaded_runtime, Mapping) else {}
    preflight = receipt.get("preflight")
    branch_runtime_version = receipt.get("branch_runtime_version")
    if not isinstance(branch_runtime_version, str):
        branch_runtime_version = loaded_runtime.get("branch_runtime_version")
    if not isinstance(branch_runtime_version, str) and isinstance(preflight, Mapping):
        branch_runtime_version = preflight.get("branch_runtime_version")
    result = {"schema": "literature-eval-graded-run-v1", "task_id": task["id"], "task_digest": task["digest"],
            "set_digest": receipt["set_digest"], "tier": task_spec.get("expected_tier"), "outcome": outcome,
            "stop_reason": stop_reason, "criteria": criteria, "citations": citations,
            "partial_credit": partial_credit,
            "loaded_runtime": loaded_runtime, "branch_runtime_version": branch_runtime_version,
            "executed": receipt.get("executed") is True,
            "codex_version": receipt.get("preflight", {}).get("codex_version", "unknown") if isinstance(receipt.get("preflight"), Mapping) else "unknown",
            "runtime_identity": receipt.get("runtime_identities", []),
            "receipt_sha256": receipt_hash}
    for key in ("stream_reconnects", "max_idle_gap_seconds", "idle_gap_seconds_over_300",
                "trailing_idle_seconds"):
        value = event_metrics.get(key) if isinstance(event_metrics, Mapping) else None
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
            result[key] = value
    return result


def wilson_interval(successes: int, n: int, z: float = 1.959963984540054) -> list[float] | None:
    if n == 0: return None
    p = successes / n; denom = 1 + z*z/n
    center = (p + z*z/(2*n)) / denom
    half = z * ((p*(1-p)/n + z*z/(4*n*n)) ** .5) / denom
    return [max(0.0, center-half), min(1.0, center+half)]


def _stats(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    n = len(rows); completed = sum(r.get("outcome") == "completed" for r in rows)
    infrastructure_failures = sum(r.get("stop_reason") == "provider_unavailable" for r in rows)
    provider_policy_blocks = sum(r.get("stop_reason") == "provider_policy_block" for r in rows)
    stall_affected_timeouts = sum(r.get("stop_reason") == "timeout" and
                                  (r.get("stream_reconnects", 0) > 0 or
                                   r.get("idle_gap_seconds_over_300", 0) > 0) for r in rows)
    stream_reconnects_total = sum(r.get("stream_reconnects", 0) for r in rows)
    adjusted_n = n - infrastructure_failures
    answered = sum(r.get("outcome") != "unsure" for r in rows)
    total = sum(isinstance(r.get("citations"), Mapping) and r["citations"].get("status") != "unavailable" for r in rows)
    traced = sum((r.get("citations") or {}).get("citations_traced", 0) for r in rows if isinstance(r.get("citations"), Mapping))
    citations = sum((r.get("citations") or {}).get("citations_total", 0) for r in rows if isinstance(r.get("citations"), Mapping))
    return {"n": n, "completed": completed, "completion_rate": completed/n if n else None,
            "completion_interval_95": wilson_interval(completed, n), "answered": answered,
            "infrastructure_failures": infrastructure_failures,
            "provider_policy_blocks": provider_policy_blocks,
            "stall_affected_timeouts": stall_affected_timeouts,
            "stream_reconnects_total": stream_reconnects_total,
            "completion_rate_excluding_infrastructure": completed/adjusted_n if adjusted_n else None,
            "completion_interval_excluding_infrastructure_95": wilson_interval(completed, adjusted_n),
            "coverage": answered/n if n else None, "precision": completed/answered if answered else None,
            "stop_reasons": dict(sorted((reason, sum(r.get("stop_reason") == reason for r in rows)) for reason in {r.get("stop_reason") for r in rows})),
            "citation_tracing": {"runs_available": total, "citations_total": citations,
                                 "citations_traced": traced, "ratio": traced/citations if citations else None}}


def _partial_credit_stats(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    values = [row["partial_credit"] for row in rows
              if isinstance(row.get("partial_credit"), (int, float)) and not isinstance(row.get("partial_credit"), bool)]
    return {"n": len(values), "mean": sum(values) / len(values) if values else None}


def summarize(graded_runs: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    all_rows = list(graded_runs)
    rejected = [{"task_id": row.get("task_id"), "reason": row.get("stop_reason", "rejected")}
                for row in all_rows if row.get("outcome") == "rejected"]
    rows = [row for row in all_rows if row.get("outcome") != "rejected"]
    digests = {r.get("set_digest") for r in rows}
    if len(digests) > 1: raise ValueError("cannot aggregate runs from different task set digests")
    match_values = [r.get("loaded_runtime", {}).get("runtime_under_test_matches_branch")
                    for r in all_rows if isinstance(r.get("loaded_runtime"), Mapping)]
    runtime_match = (False if False in match_values else True
                     if match_values and len(match_values) == len(all_rows) and all(value is True for value in match_values)
                     else None)
    versions = sorted({r["branch_runtime_version"] for r in all_rows
                       if isinstance(r.get("branch_runtime_version"), str) and r["branch_runtime_version"]})
    partial_credit_rows = [r for r in all_rows if r.get("outcome") != "rejected"]
    return {"schema": "literature-eval-report-v1", "set_digest": next(iter(digests), None),
            "overall": _stats(rows), "by_tier": {tier: _stats([r for r in rows if r.get("tier") == tier]) for tier in ("quick", "standard", "full")},
            "partial_credit_secondary": {"label": "Partial credit (secondary)",
                "overall": _partial_credit_stats(partial_credit_rows),
                "by_tier": {tier: _partial_credit_stats([r for r in partial_credit_rows if r.get("tier") == tier])
                            for tier in ("quick", "standard", "full")}},
            "loaded_runtime": {"runtime_under_test_matches_branch": runtime_match},
            "branch_runtime_version": versions[0] if len(versions) == 1 else None,
            "branch_runtime_versions": versions,
            "rejected": rejected,
            "claim_boundary": f"Results describe only these observed runs (n={len(rows)}); they do not establish performance beyond this task set and these runs."}


def render_markdown(report: Mapping[str, Any]) -> str:
    s = report["overall"]; interval = s["completion_interval_95"]
    rate = "n/a" if s["completion_rate"] is None else f"{s['completion_rate']:.1%} ({interval[0]:.1%}–{interval[1]:.1%} 95% Wilson interval)"
    adjusted_interval = s["completion_interval_excluding_infrastructure_95"]
    adjusted_rate = ("n/a" if s["completion_rate_excluding_infrastructure"] is None else
                     f"{s['completion_rate_excluding_infrastructure']:.1%} "
                     f"({adjusted_interval[0]:.1%}–{adjusted_interval[1]:.1%} 95% Wilson interval)")
    percent = lambda value: "n/a" if value is None else f"{value:.1%}"
    matches = report.get("loaded_runtime", {}).get("runtime_under_test_matches_branch")
    version = report.get("branch_runtime_version")
    if matches is False:
        runtime_status = f"Runtime mismatch: one or more runs used a runtime different from branch version {version or 'unknown'}."
    elif matches is True:
        runtime_status = f"Runs used the branch runtime{f' {version}' if version else ''}."
    else:
        runtime_status = "Branch runtime match could not be established from receipts."
    lines = ["# Literature evaluation report", "", "## Status",
             f"Completion rate: {rate}; completed {s['completed']}/{s['n']}.",
             f"Secondary completion rate excluding infrastructure failures: {adjusted_rate}; "
             f"provider infrastructure failures {s['infrastructure_failures']}; "
             f"provider policy blocks {s['provider_policy_blocks']}. Policy blocks remain failures in both rates. "
             "Runs failed by provider capacity "
             "should be re-run and not counted as product evidence.",
             f"Diagnostic stream stalls: {s['stall_affected_timeouts']} timeout runs affected; "
             f"{s['stream_reconnects_total']} stream reconnects.",
             runtime_status, "", "## Current", f"Answered coverage: {percent(s['coverage'])}; precision among answered: {percent(s['precision'])}.", "", "## Next", "Inspect unsure and failed runs before drawing conclusions.", "", "## Evidence", f"{report['claim_boundary']}", "", "Stop reasons:"]
    lines += [f"- {k}: {v}" for k, v in s["stop_reasons"].items()]
    secondary = report.get("partial_credit_secondary", {})
    overall_partial = secondary.get("overall", {})
    partial_mean = overall_partial.get("mean")
    lines += ["", "## Partial credit (secondary)",
              "This secondary metric is not used for the completion rate.",
              f"Overall mean: {percent(partial_mean)} (n={overall_partial.get('n', 0)}).",
              "", "| Tier | Mean partial credit (secondary) | n |", "|---|---:|---:|"]
    for tier, stats in secondary.get("by_tier", {}).items():
        lines.append(f"| {tier} | {percent(stats.get('mean'))} | {stats.get('n', 0)} |")
    return "\n".join(lines) + "\n"
