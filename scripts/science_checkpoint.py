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
        return {"status": "findings" if findings else "passed", "findings": findings, "advisory": True}
    except Exception as error:
        return {"status": "skipped", "findings": [], "advisory": True, "reason": type(error).__name__}


def _step(value: str) -> tuple[str, str]:
    identifier, separator, title = value.partition("=")
    if not separator or not identifier.strip() or not title.strip():
        raise argparse.ArgumentTypeError("step must use ID=TITLE")
    return identifier.strip(), title.strip()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="create a run checkpoint")
    init.add_argument("run_dir", type=Path)
    init.add_argument("--goal", required=True)
    init.add_argument("--deliverable", required=True)
    init.add_argument("--done", action="append", required=True, dest="done_criteria")
    init.add_argument("--step", action="append", required=True, type=_step, dest="steps")
    init.add_argument("--next-action", required=True)
    init.add_argument("--outer-goal", choices=("none", "native"), default="none")
    init.add_argument("--goal-task-key")
    init.add_argument("--continuation-budget", type=int, default=100)
    init.add_argument("--rigor-tier", choices=("standard", "full"))
    init.add_argument("--rigor-decision-sha256")
    init.add_argument("--budget-policy", choices=("tier-v1",))
    init.add_argument("--deadline-at")
    init_group = init.add_mutually_exclusive_group(required=True)
    init_group.add_argument("--session-key")
    init_group.add_argument("--hookless", action="store_true")

    escalate = commands.add_parser("escalate", help="raise the recorded rigor tier")
    escalate.add_argument("run_dir", type=Path)
    escalate.add_argument("--tier", required=True, choices=("standard", "full"))
    escalate.add_argument("--reason", required=True)
    escalate.add_argument("--rigor-decision-sha256")

    claim = commands.add_parser("claim", help="attach a legacy run to this Codex task")
    claim.add_argument("run_dir", type=Path)
    claim.add_argument("--session-key", required=True)
    claim.add_argument("--outer-goal", choices=("none", "native"), default="none")
    claim.add_argument("--goal-task-key")
    claim.add_argument("--previous-session-key")
    claim.add_argument("--continuation-budget", type=int, default=100)

    show = commands.add_parser("show", help="show a validated checkpoint")
    show.add_argument("run_dir", type=Path)

    heartbeat = commands.add_parser("heartbeat", help="record same-step progress")
    heartbeat.add_argument("run_dir", type=Path)
    heartbeat.add_argument("--next-action", required=True)
    heartbeat.add_argument("--progress-ref")

    advance = commands.add_parser("advance", help="complete the current step")
    advance.add_argument("run_dir", type=Path)
    advance.add_argument("--complete", required=True, dest="completed_step")
    advance.add_argument("--next", dest="next_step")
    advance.add_argument("--next-action", required=True)

    attempt = commands.add_parser("attempt", help="record a failed approach")
    attempt.add_argument("run_dir", type=Path)
    attempt.add_argument("--failure-class", required=True)
    attempt.add_argument("--approach", required=True)
    attempt.add_argument("--outcome", required=True)
    attempt.add_argument("--next-action", required=True)

    gate = commands.add_parser("gate", help="open one batched decision gate")
    gate.add_argument("run_dir", type=Path)
    gate.add_argument("--question", action="append", required=True, dest="questions")
    gate.add_argument("--reason", required=True)

    resume = commands.add_parser("resume", help="resume a gated or blocked run")
    resume.add_argument("run_dir", type=Path)
    resume.add_argument("--next-action", required=True)

    block = commands.add_parser("block", help="record a genuine blocker")
    block.add_argument("run_dir", type=Path)
    block.add_argument("--reason", required=True)
    block.add_argument("--next-action", required=True)

    wait = commands.add_parser("wait", help="record an external wait without busy-looping")
    wait.add_argument("run_dir", type=Path)
    wait.add_argument("--reason", required=True)
    wait.add_argument("--next-action", required=True)
    wait.add_argument("--poll-interval-seconds", type=int, required=True)
    wait.add_argument("--terminal-rule", required=True)

    criterion = commands.add_parser("criterion", help="satisfy a done criterion with evidence")
    criterion.add_argument("run_dir", type=Path)
    criterion.add_argument("--id", required=True, dest="criterion_id")
    criterion.add_argument("--evidence-ref", action="append", required=True, dest="evidence_refs")

    review = commands.add_parser("review", help="attach an independent review receipt")
    review.add_argument("run_dir", type=Path)
    review.add_argument("--artifact-ref", required=True)

    abandon = commands.add_parser("abandon", help="make a run permanently non-resumable")
    abandon.add_argument("run_dir", type=Path)
    abandon.add_argument("--reason", required=True)

    complete = commands.add_parser("complete", help="complete a fully executed plan")
    complete.add_argument("run_dir", type=Path)

    confirm = commands.add_parser(
        "confirm-goal-complete",
        help="record a native Goal completion attestation receipt",
    )
    confirm.add_argument("run_dir", type=Path)
    confirm.add_argument("--receipt", required=True, dest="receipt_ref")
    status = commands.add_parser("budget-status", help="show opt-in run budget without writing")
    status.add_argument("run_dir", type=Path)
    partial = commands.add_parser("finish-partial", help="finish an exhausted budgeted run as partial")
    partial.add_argument("run_dir", type=Path)
    partial.add_argument("--artifact-ref", required=True)
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
