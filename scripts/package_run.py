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
    execute.add_argument("--run-dir", type=Path, required=True)
    execute.add_argument("--id")
    execute.add_argument("command", nargs=argparse.REMAINDER)
    update = commands.add_parser("refresh", help="refresh manifest hashes and registrations")
    update.add_argument("--run-dir", type=Path, required=True)
    update.add_argument("--kind", action="append", default=[], metavar="PATH=KIND")
    update.add_argument("--default-kind")
    update.add_argument("--invalidate-review", action="store_true")
    update.add_argument("--register-receipt", metavar="PATH")
    ready = commands.add_parser("prepare-review", help="run deterministic gates and build an independent review packet")
    ready.add_argument("--run-dir", type=Path, required=True)
    ready.add_argument("--tier", choices=("quick", "standard", "full"), required=True)
    ready.add_argument("--mode", action="append", choices=("record", "source", "method", "reproduction"))
    ready.add_argument("--question", action="append")
    ready.add_argument("--new-round", action="store_true")
    ready.add_argument("--kind", action="append", default=[], metavar="PATH=KIND")
    ready.add_argument("--default-kind")
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
            if overrides or args.default_kind or args.invalidate_review:
                raise ValueError("--register-receipt cannot be combined with refresh options")
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
