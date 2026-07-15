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
    heartbeat_checkpoint,
    load_checkpoint,
    record_review,
    record_attempt,
    request_decision,
    resume_checkpoint,
    verify_criterion,
    wait_checkpoint,
)


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
    init.add_argument("--session-key", required=True)
    init.add_argument("--outer-goal", choices=("none", "native"), default="none")
    init.add_argument("--goal-task-key")
    init.add_argument("--continuation-budget", type=int, default=100)

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
                outer_goal=args.outer_goal,
                goal_task_key=args.goal_task_key,
                continuation_budget=args.continuation_budget,
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
        else:
            result = confirm_goal_complete(args.run_dir, receipt_ref=args.receipt_ref)
    except (FileExistsError, FileNotFoundError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
