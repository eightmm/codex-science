#!/usr/bin/env python3
"""Dry-run-first runner for the frozen literature-review evaluation set."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from codex_science.literature_evaluation_runner import run_evaluation  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--task", action="append", dest="tasks_selected")
    parser.add_argument("--execute", action="store_true", help="execute Codex tasks; default only writes a plan")
    parser.add_argument("--timeout-seconds", type=int)
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--codex-home", type=Path)
    parser.add_argument("--plugin", default="codex-science@codex-science",
                        help="plugin selector in codex-science@marketplace form")
    parser.add_argument("--output-schema", action="store_true",
                        help="require and cross-check a structured completion record")
    args = parser.parse_args()
    if args.timeout_seconds is not None and args.timeout_seconds < 1:
        parser.error("--timeout-seconds must be positive")
    try:
        result = run_evaluation(args.tasks, args.out, selected=args.tasks_selected,
                                execute=args.execute, timeout_seconds=args.timeout_seconds,
                                codex_bin=args.codex_bin, codex_home=args.codex_home,
                                output_schema=args.output_schema, plugin=args.plugin)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"literature evaluation failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"plan": result["_plan_path"],
                      "execute": args.execute, "tasks": len(result["tasks"])}, sort_keys=True))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
