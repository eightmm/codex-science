#!/usr/bin/env python3
"""Dry-run-first CLI for the bounded Codex Science resume driver."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from codex_science.run_driver import _argv, _resolve_paths, _validate_caps, drive


STOP_TABLE = ["terminal", "needs_human", "quick_answer", "turn_failed", "driver_error", "interrupted",
              "turn_cap", "wall_cap", "token_cap", "stalled"]
EXIT_CODES = ("Exit codes: 0 terminal or quick_answer; 3 needs_human; 4 caps or stalled (turn, wall, or token cap); "
              "5 turn_failed or interrupted; 2 usage errors and driver_error (including output directory errors). "
              "Token caps sum raw input + output totals for every invocation; "
              "this may overcount cumulative resume usage, whose semantics are unverified. "
              "Before each launch an exhausted token budget stops execution. "
              "Stop checks run in this order: launch failure, timeout, turn failure/interruption, outcome, "
              "quick answer, stalled/caps. The completion report is always recorded, including on errors.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, epilog=EXIT_CODES)
    parser.add_argument("--project", required=True, type=Path)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--prompt")
    source.add_argument("--prompt-file", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--max-turns", type=int, default=6)
    parser.add_argument("--wall-seconds", type=float, default=1800)
    parser.add_argument("--max-total-tokens", type=int,
                        help="cap on summed per-invocation input + output token totals; may overcount cumulative resume usage")
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--codex-home", type=Path, default=None)
    parser.add_argument("--execute", action="store_true")
    parser.description = (__doc__ or "") + " Prompts beginning with '-' are rejected because the installed Codex CLI " \
        "does not document '--' prompt termination."
    args = parser.parse_args()
    try:
        prompt = args.prompt if args.prompt is not None else args.prompt_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        parser.error(f"cannot read prompt file: {error}")
    try:
        project, out = _resolve_paths(args.project, args.out)
        _validate_caps(args.max_turns, args.wall_seconds, args.max_total_tokens)
        if prompt.startswith("-"):
            raise ValueError("prompts beginning with '-' are unsupported; use a prompt file with a non-dash-leading prompt")
        if os.path.lexists(out / "run-driver-receipt.json"):
            raise FileExistsError(f"output directory already contains run-driver-receipt.json; choose a new --out directory: {out}")
        if args.execute:
            result = drive(project, prompt, run_dir=out, codex_bin=args.codex_bin,
                           max_turns=args.max_turns, wall_seconds=args.wall_seconds,
                           max_total_tokens=args.max_total_tokens, codex_home=args.codex_home)
            print(json.dumps(result, indent=2))
            code = result["stop"]["code"]
            if code in {"terminal", "quick_answer"}:
                return 0
            if code == "needs_human":
                return 3
            if code in {"turn_cap", "wall_cap", "token_cap", "stalled"}:
                return 4
            if code == "driver_error":
                return 2
            return 5
        argv = _argv(args.codex_bin, project, prompt, out / "turn-1" / "last.md")
        result = {"execute": False, "first_argv": argv, "stop_table": STOP_TABLE}
        print(json.dumps(result, indent=2))
        return 0
    except (KeyboardInterrupt, SystemExit):
        print(json.dumps({"error": "interrupted"}), file=sys.stderr)
        return 5
    except BaseException as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
