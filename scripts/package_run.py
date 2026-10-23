#!/usr/bin/env python3
"""Record commands and refresh hashes in a Codex Science run bundle (single writer per run directory)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.run_packaging import refresh, register_receipt, run_exec  # noqa: E402


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
    args = parser.parse_args()
    try:
        if args.action == "exec":
            command = args.command
            if command and command[0] == "--":
                command = command[1:]
            return run_exec(args.run_dir, command, args.id)
        overrides = []
        for value in args.kind:
            if "=" not in value:
                raise ValueError("--kind must be PATH=KIND")
            path, kind = value.split("=", 1)
            if not path or not kind:
                raise ValueError("--kind must be PATH=KIND")
            overrides.append((path, kind))
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
