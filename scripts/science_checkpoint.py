#!/usr/bin/env python3
"""Create and update durable Codex Science run checkpoints."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.checkpoints import (  # noqa: E402
    abandon_checkpoint,
    advance_checkpoint,
    block_checkpoint,
    claim_checkpoint,
    complete_checkpoint,
    confirm_goal_complete,
    create_checkpoint,
    escalate_checkpoint,
    heartbeat_checkpoint,
    load_checkpoint,
    record_review,
    record_attempt,
    budget_status,
    finish_partial,
    request_decision,
    resume_checkpoint,
    verify_criterion,
    wait_checkpoint,
)
from codex_science.artifacts import validate_bundle  # noqa: E402
from codex_science.review import review_manifest  # noqa: E402


def _pre_review_advisories(sidecars: object, manifest: object) -> list[dict[str, str]]:
    """Return best-effort consistency prompts without affecting bundle gates."""
    findings: list[dict[str, str]] = []

    # A validated evidence bundle uses study IDs as graph node IDs. If any
    # receipt record cannot be mapped to a study node, leave that lane alone.
    lane_findings: list[dict[str, str]] = []
    try:
        if isinstance(sidecars, dict) and isinstance(manifest, dict):
            lanes = sidecars.get("lane_receipts", [])
            nodes = sidecars.get("node_by_id", {})
            edges = sidecars.get("edges", [])
            if isinstance(lanes, list) and isinstance(nodes, dict) and isinstance(edges, list):
                if any(not isinstance(edge, dict) for edge in edges):
                    raise TypeError("malformed evidence graph edge")
                for lane in lanes:
                    if not isinstance(lane, dict):
                        raise TypeError("malformed lane receipt")
                    lane_id = lane.get("lane_id")
                    included = lane.get("included_records")
                    supported = lane.get("supported_claim_ids")
                    if not isinstance(lane_id, str) or not isinstance(included, list) or not isinstance(supported, list):
                        raise TypeError("malformed lane receipt fields")
                    if any(not isinstance(record_id, str) for record_id in included) or any(
                        not isinstance(claim_id, str) for claim_id in supported
                    ):
                        raise TypeError("malformed lane receipt IDs")
                    if not included:
                        continue
                    if any(not isinstance(record_id, str) or not isinstance(nodes.get(record_id), dict)
                           or nodes[record_id].get("type") != "study" for record_id in included):
                        continue
                    for claim_id in supported:
                        has_support = any(
                            isinstance(edge, dict)
                            and edge.get("relation") == "supports"
                            and edge.get("source") in included
                            and edge.get("target") == claim_id
                            for edge in edges
                        )
                        if not has_support:
                            lane_findings.append({
                                "code": "lane-claim-without-support-edge",
                                "severity": "advisory",
                                "message": f"Lane {lane_id} lists claim {claim_id} as supported, but included records {', '.join(included) or '(none)'} have no supports edge to it.",
                            })
    except Exception:
        lane_findings = []
    findings.extend(lane_findings)

    # Lane outputs are artifact paths; execution receipts carry their recorded
    # hashes. Compare only paths that have both recorded and manifest hashes.
    hash_findings: list[dict[str, str]] = []
    try:
        if isinstance(sidecars, dict) and isinstance(manifest, dict):
            artifacts = manifest.get("artifacts", [])
            executions = manifest.get("executions", [])
            lanes = sidecars.get("lane_receipts", [])
            if isinstance(artifacts, list) and isinstance(executions, list) and isinstance(lanes, list):
                manifest_hashes = {
                    item["path"]: item["sha256"] for item in artifacts
                    if isinstance(item, dict) and isinstance(item.get("path"), str)
                    and isinstance(item.get("sha256"), str) and item["sha256"]
                }
                recorded_hashes: dict[str, list[str]] = {}
                for execution in executions:
                    if not isinstance(execution, dict):
                        raise TypeError("malformed execution receipt")
                    outputs = execution.get("outputs")
                    if not isinstance(outputs, list):
                        continue
                    for output in outputs:
                        if isinstance(output, str):
                            continue
                        if not isinstance(output, dict):
                            continue
                        path, digest = output.get("path"), output.get("sha256")
                        if not isinstance(path, str) or not isinstance(digest, str) or not digest:
                            continue
                        recorded_hashes.setdefault(path, []).append(digest)
                for lane in lanes:
                    if not isinstance(lane, dict) or not isinstance(lane.get("outputs"), list):
                        raise TypeError("malformed lane outputs")
                    if any(not isinstance(path, str) for path in lane["outputs"]):
                        raise TypeError("malformed lane output path")
                    lane_id = lane.get("lane_id", "<unknown>")
                    for path in lane["outputs"]:
                        if not isinstance(path, str) or path not in manifest_hashes:
                            continue
                        actual = manifest_hashes[path]
                        recorded = recorded_hashes.get(path, [])
                        # Reconcile against all run history: a later matching
                        # receipt makes an earlier mismatch stale evidence.
                        if recorded and not any(digest.casefold() == actual.casefold() for digest in recorded):
                            hash_findings.append({
                                "code": "lane-output-hash-stale",
                                "severity": "advisory",
                                "message": f"Lane {lane_id} output {path} records SHA-256 {recorded[-1]}, but the manifest records {actual}.",
                            })
    except Exception:
        hash_findings = []
    findings.extend(hash_findings)

    return findings


def _early_check(run_dir: Path) -> dict[str, object]:
    manifest_path = run_dir / "manifest.json"
    try:
        if not manifest_path.exists():
            return {"status": "skipped", "findings": [], "advisory": True, "reason": "manifest-not-found"}
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "skipped", "findings": [], "advisory": True, "reason": "invalid-json"}
    except Exception as error:
        return {"status": "skipped", "findings": [], "advisory": True, "reason": type(error).__name__}
    try:
        sidecars = validate_bundle(manifest, run_dir)
    except ValueError as error:
        return {
            "status": "findings", "advisory": True,
            "findings": [{"code": "bundle-invalid", "severity": "major", "message": str(error)}],
        }
    except Exception as error:
        return {"status": "skipped", "findings": [], "advisory": True, "reason": type(error).__name__}
    try:
        findings = [
            finding for finding in review_manifest(manifest, run_dir, sidecars=sidecars)["findings"]
            if finding.get("code") not in {"incomplete-plan", "declared-review-not-passed"}
        ]
        findings.extend(_pre_review_advisories(sidecars, manifest))
        return {"status": "findings" if findings else "passed", "findings": findings, "advisory": True}
    except Exception as error:
        return {"status": "skipped", "findings": [], "advisory": True, "reason": type(error).__name__}


def _step(value: str) -> tuple[str, str]:
    identifier, separator, title = value.partition("=")
    if not separator or not identifier.strip() or not title.strip():
        raise argparse.ArgumentTypeError(
            f"step must use ID=TITLE, e.g. --step retrieval='Retrieve and screen sources'; got {value}"
        )
    return identifier.strip(), title.strip()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="create a run checkpoint")
    init.add_argument("run_dir", type=Path, help="run directory to create; must not already contain checkpoint.json")
    init.add_argument("--goal", required=True, help="run goal text")
    init.add_argument("--deliverable", required=True, help="deliverable text")
    init.add_argument(
        "--done", action="append", required=True, dest="done_criteria",
        help="done criterion text; repeat for several (recorded as criterion-1, criterion-2, ...)",
    )
    init.add_argument(
        "--step", action="append", required=True, type=_step, dest="steps",
        help="planned step as ID=TITLE; repeat in order (the first step starts in progress)",
    )
    init.add_argument("--next-action", required=True, help="text describing the next action")
    init.add_argument(
        "--outer-goal", choices=("none", "native"), default="none",
        help="native binds the run to a native Codex Goal and requires --goal-task-key (not allowed with --hookless)",
    )
    init.add_argument("--goal-task-key", help="64-character lowercase hex SHA-256 task key; only valid with --outer-goal native")
    init.add_argument("--continuation-budget", type=int, default=100, help="positive integer continuation budget")
    init.add_argument("--rigor-tier", choices=("standard", "full"), help="rigor tier to record; required with --hookless and --budget-policy")
    init.add_argument("--rigor-decision-sha256", help="SHA-256 hex digest recorded in the rigor history entry")
    init.add_argument("--budget-policy", choices=("tier-v1",), help="opt in to a run budget derived from the rigor tier; requires --rigor-tier")
    init.add_argument("--deadline-at", help="run deadline as a future UTC timestamp ending in Z, e.g. 2030-01-01T00:00:00Z; requires --budget-policy")
    init_group = init.add_mutually_exclusive_group(required=True)
    init_group.add_argument("--session-key", help="64-character lowercase hex SHA-256 key of the Codex task that owns the run")
    init_group.add_argument("--hookless", action="store_true", help="bind to a random run-local key instead of a task session key; requires --rigor-tier")

    escalate = commands.add_parser("escalate", help="raise the recorded rigor tier")
    escalate.add_argument("run_dir", type=Path, help="run directory containing checkpoint.json")
    escalate.add_argument("--tier", required=True, choices=("standard", "full"), help="new tier; must be higher than the current tier")
    escalate.add_argument("--reason", required=True, help="why the rigor tier is raised")
    escalate.add_argument("--rigor-decision-sha256", help="SHA-256 hex digest recorded in the rigor history entry")

    claim = commands.add_parser("claim", help="attach a legacy run to this Codex task")
    claim.add_argument("run_dir", type=Path, help="run directory containing checkpoint.json")
    claim.add_argument("--session-key", required=True, help="64-character lowercase hex SHA-256 key of the Codex task claiming the run")
    claim.add_argument("--outer-goal", choices=("none", "native"), default="none", help="native requires --goal-task-key; cannot change on a schema-v4 run")
    claim.add_argument("--goal-task-key", help="64-character lowercase hex SHA-256 task key; only valid with --outer-goal native")
    claim.add_argument("--previous-session-key", help="session key recorded in the legacy (pre-v4) checkpoint being claimed, as a SHA-256 hex digest")
    claim.add_argument("--continuation-budget", type=int, default=100, help="positive integer continuation budget")

    show = commands.add_parser("show", help="show a validated checkpoint")
    show.add_argument("run_dir", type=Path, help="run directory containing checkpoint.json")

    heartbeat = commands.add_parser("heartbeat", help="record same-step progress")
    heartbeat.add_argument("run_dir", type=Path, help="run directory containing checkpoint.json")
    heartbeat.add_argument("--next-action", required=True, help="new next-action text; must differ from the recorded one")
    heartbeat.add_argument("--progress-ref", help="existing progress evidence file as a path relative to the run directory; required for schema-v3+ checkpoints")

    advance = commands.add_parser("advance", help="complete the current step")
    advance.add_argument("run_dir", type=Path, help="run directory containing checkpoint.json")
    advance.add_argument("--complete", dest="completed_step", help="ID of the current step to mark completed; omit only to start a step when none is in progress")
    advance.add_argument("--next", dest="next_step", help="ID of a pending step to start; defaults to the first pending step after --complete")
    advance.add_argument("--next-action", required=True, help="text describing the next action")

    attempt = commands.add_parser("attempt", help="record a failed approach")
    attempt.add_argument("run_dir", type=Path, help="run directory containing checkpoint.json")
    attempt.add_argument("--failure-class", required=True, help="label grouping similar failures; retries are limited per class")
    attempt.add_argument("--approach", required=True, help="the approach that was tried")
    attempt.add_argument("--outcome", required=True, help="what happened")
    attempt.add_argument("--next-action", required=True, help="text describing the next action")

    gate = commands.add_parser("gate", help="open one batched decision gate")
    gate.add_argument("run_dir", type=Path, help="run directory containing checkpoint.json")
    gate.add_argument("--question", action="append", required=True, dest="questions", help="decision question; repeat to batch several")
    gate.add_argument("--reason", required=True, help="why the decision is needed")

    resume = commands.add_parser("resume", help="resume a gated or blocked run")
    resume.add_argument("run_dir", type=Path, help="run directory containing checkpoint.json")
    resume.add_argument("--next-action", required=True, help="text describing the next action")

    block = commands.add_parser("block", help="record a genuine blocker")
    block.add_argument("run_dir", type=Path, help="run directory containing checkpoint.json")
    block.add_argument("--reason", required=True, help="the blocker")
    block.add_argument("--next-action", required=True, help="condition or action needed to continue")

    wait = commands.add_parser("wait", help="record an external wait without busy-looping")
    wait.add_argument("run_dir", type=Path, help="run directory containing checkpoint.json")
    wait.add_argument("--reason", required=True, help="what external event is awaited")
    wait.add_argument("--next-action", required=True, help="text describing the next action after the wait")
    wait.add_argument("--poll-interval-seconds", type=int, required=True, help="positive integer number of seconds between checks")
    wait.add_argument("--terminal-rule", required=True, help="rule for when to stop waiting")

    criterion = commands.add_parser("criterion", help="satisfy a done criterion with evidence")
    criterion.add_argument("run_dir", type=Path, help="run directory containing the checkpoint")
    criterion.add_argument("--id", required=True, dest="criterion_id", help="done criterion id to mark satisfied")
    criterion.add_argument(
        "--evidence-ref", action="append", required=True, dest="evidence_refs",
        help="existing evidence file as a path relative to the run directory, e.g. protocol.md "
        "or result.json#/result; absolute paths are refused; repeat for several files",
    )

    review = commands.add_parser("review", help="attach an independent review receipt")
    review.add_argument("run_dir", type=Path, help="run directory containing checkpoint.json")
    review.add_argument(
        "--artifact-ref", required=True,
        help="review receipt JSON as a path relative to the run directory; needs status (passed|failed), "
        "reviewer, independent (boolean) and optional findings (list)",
    )

    abandon = commands.add_parser("abandon", help="make a run permanently non-resumable")
    abandon.add_argument("run_dir", type=Path, help="run directory containing checkpoint.json")
    abandon.add_argument("--reason", required=True, help="why the run is abandoned")

    complete = commands.add_parser("complete", help="complete a fully executed plan")
    complete.add_argument("run_dir", type=Path, help="run directory containing checkpoint.json")

    confirm = commands.add_parser(
        "confirm-goal-complete",
        help="record a native Goal completion attestation receipt",
    )
    confirm.add_argument("run_dir", type=Path, help="run directory containing checkpoint.json")
    confirm.add_argument(
        "--receipt", required=True, dest="receipt_ref",
        help="Goal completion receipt JSON as a path relative to the run directory; needs status \"complete\" and the bound task_key",
    )
    status = commands.add_parser("budget-status", help="show opt-in run budget without writing")
    status.add_argument("run_dir", type=Path, help="run directory containing checkpoint.json")
    partial = commands.add_parser("finish-partial", help="finish an exhausted budgeted run as partial")
    partial.add_argument("run_dir", type=Path, help="run directory containing checkpoint.json")
    partial.add_argument(
        "--artifact-ref", required=True,
        help="partial-result JSON as a path relative to the run directory with exactly the keys schema_version (1), "
        "status (\"partial\"), result_refs, unmet_criteria, unfinished_steps, caveats, review_status",
    )
    return parser


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    try:
        if args.command == "init":
            result = create_checkpoint(
                args.run_dir,
                goal=args.goal,
                deliverable=args.deliverable,
                done_criteria=args.done_criteria,
                steps=args.steps,
                next_action=args.next_action,
                session_key=args.session_key,
                hookless=args.hookless,
                outer_goal=args.outer_goal,
                goal_task_key=args.goal_task_key,
                continuation_budget=args.continuation_budget,
                rigor_tier=args.rigor_tier,
                rigor_decision_sha256=args.rigor_decision_sha256,
                budget_policy=args.budget_policy,
                deadline_at=args.deadline_at,
            )
        elif args.command == "escalate":
            result = escalate_checkpoint(
                args.run_dir,
                tier=args.tier,
                reason=args.reason,
                rigor_decision_sha256=args.rigor_decision_sha256,
            )
        elif args.command == "claim":
            result = claim_checkpoint(
                args.run_dir,
                session_key=args.session_key,
                outer_goal=args.outer_goal,
                goal_task_key=args.goal_task_key,
                previous_session_key=args.previous_session_key,
                continuation_budget=args.continuation_budget,
            )
        elif args.command == "show":
            result = load_checkpoint(args.run_dir)
        elif args.command == "heartbeat":
            result = heartbeat_checkpoint(
                args.run_dir,
                next_action=args.next_action,
                progress_ref=args.progress_ref,
            )
        elif args.command == "advance":
            result = advance_checkpoint(
                args.run_dir,
                completed_step=args.completed_step,
                next_step=args.next_step,
                next_action=args.next_action,
            )
            result["early_check"] = _early_check(args.run_dir)
        elif args.command == "attempt":
            result = record_attempt(
                args.run_dir,
                failure_class=args.failure_class,
                approach=args.approach,
                outcome=args.outcome,
                next_action=args.next_action,
            )
        elif args.command == "gate":
            result = request_decision(args.run_dir, questions=args.questions, reason=args.reason)
        elif args.command == "resume":
            result = resume_checkpoint(args.run_dir, next_action=args.next_action)
        elif args.command == "block":
            result = block_checkpoint(args.run_dir, reason=args.reason, next_action=args.next_action)
        elif args.command == "wait":
            result = wait_checkpoint(
                args.run_dir,
                reason=args.reason,
                next_action=args.next_action,
                poll_interval_seconds=args.poll_interval_seconds,
                terminal_rule=args.terminal_rule,
            )
        elif args.command == "criterion":
            result = verify_criterion(args.run_dir, args.criterion_id, args.evidence_refs)
        elif args.command == "review":
            result = record_review(
                args.run_dir,
                artifact_ref=args.artifact_ref,
            )
        elif args.command == "abandon":
            result = abandon_checkpoint(args.run_dir, reason=args.reason)
        elif args.command == "complete":
            result = complete_checkpoint(args.run_dir)
        elif args.command == "budget-status":
            result = budget_status(args.run_dir)
        elif args.command == "finish-partial":
            result = finish_partial(args.run_dir, artifact_ref=args.artifact_ref)
        else:
            result = confirm_goal_complete(args.run_dir, receipt_ref=args.receipt_ref)
    except (FileExistsError, FileNotFoundError, RuntimeError, ValueError, OSError, TimeoutError, json.JSONDecodeError) as error:
        parser.error(str(error))
    registration = result.get("manifest_registration") if isinstance(result, dict) else None
    if args.command == "review" and isinstance(registration, dict) and registration.get("status") == "failed":
        reason = str(registration.get("reason", "unknown error")).replace("\r", " ").replace("\n", " ")
        print(f"warning: review recorded; manifest registration failed: {reason}", file=sys.stderr)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
