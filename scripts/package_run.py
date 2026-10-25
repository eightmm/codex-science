#!/usr/bin/env python3
"""Record commands and refresh hashes in a Codex Science run bundle (single writer per run directory)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.run_packaging import prepare_review, refresh, register_receipt, run_exec  # noqa: E402


def parse_kind_overrides(values: list[str]) -> list[tuple[str, str]]:
    overrides = []
    for value in values:
        if "=" not in value:
            raise ValueError("--kind must be PATH=KIND")
        path, kind = value.split("=", 1)
        if not path or not kind:
            raise ValueError("--kind must be PATH=KIND")
        overrides.append((path, kind))
    return overrides


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    execute = commands.add_parser("exec", help="run and record a command")
    execute.add_argument("--run-dir", type=Path, required=True, help="run directory to record the execution in")
    execute.add_argument(
        "--id",
        help="execution ID, unique within the run (default exec-NNN); a used ID is refused, "
        "so a re-run needs a new ID or no --id",
    )
    execute.add_argument("command", nargs=argparse.REMAINDER, help="command to run, after --")
    update = commands.add_parser("refresh", help="refresh manifest hashes and registrations")
    update.add_argument("--run-dir", type=Path, required=True, help="run directory containing manifest.json")
    update.add_argument("--kind", action="append", default=[], metavar="PATH=KIND",
                        help="register a file as an artifact kind, PATH=KIND; PATH may be a glob relative to the run directory, later options win, repeatable")
    update.add_argument("--default-kind",
                        help="artifact kind for files that match no --kind and no built-in name rule (without it, such unregistered files make the command fail)")
    update.add_argument("--invalidate-review", action="store_true",
                        help="archive prior review files and reset review to pending; required when the run already has review evidence")
    update.add_argument("--register-receipt", metavar="PATH",
                        help="register a passed review receipt (run-relative path) instead of refreshing; cannot be combined with other refresh options")
    ready = commands.add_parser("prepare-review", help="run deterministic gates and build an independent review packet")
    ready.add_argument("--run-dir", type=Path, required=True, help="run directory containing manifest.json")
    ready.add_argument("--tier", choices=("quick", "standard", "full"), required=True,
                       help="rigor tier for the claim-sufficiency check and the packet review order")
    ready.add_argument("--mode", action="append", choices=("record", "source", "method", "reproduction"),
                       help="review mode to request; repeatable (default: record, source, method)")
    ready.add_argument("--question", action="append",
                       help="review question for the packet; repeatable, replaces the default questions")
    ready.add_argument("--new-round", action="store_true",
                       help="archive prior review files and start a new review round; required when the run already has review evidence")
    ready.add_argument("--kind", action="append", default=[], metavar="PATH=KIND",
                       help="register a file as an artifact kind, PATH=KIND; PATH may be a glob relative to the run directory, later options win, repeatable")
    ready.add_argument("--default-kind",
                       help="artifact kind for files that match no --kind and no built-in name rule (without it, such unregistered files make the command fail)")
    args = parser.parse_args()
    try:
        if args.action == "exec":
            command = args.command
            if command and command[0] == "--":
                command = command[1:]
            return run_exec(args.run_dir, command, args.id)
        if args.action == "prepare-review":
            summary = prepare_review(args.run_dir, tier=args.tier, modes=args.mode,
                                     questions=args.question, new_round=args.new_round,
                                     kind_overrides=parse_kind_overrides(args.kind),
                                     default_kind=args.default_kind)
            print(json.dumps(summary, sort_keys=True))
            return 0 if "review-task.json" in summary["outputs_written"] else 1
        overrides = parse_kind_overrides(args.kind)
        if args.register_receipt:
            given = (["--kind"] if overrides else []) + (["--default-kind"] if args.default_kind else []) \
                + (["--invalidate-review"] if args.invalidate_review else [])
            if given:
                raise ValueError(f"--register-receipt cannot be combined with refresh options ({', '.join(given)}); "
                                 "rerun with only --run-dir and --register-receipt")
            summary = register_receipt(args.run_dir, args.register_receipt)
        else:
            summary = refresh(args.run_dir, overrides, args.invalidate_review, args.default_kind)
        print(json.dumps(summary, sort_keys=True))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        suffix = "; no files were changed" if args.action == "refresh" else ""
        print(f"error: {error}{suffix}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
