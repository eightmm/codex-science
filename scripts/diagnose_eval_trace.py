#!/usr/bin/env python3
"""Diagnose a recorded Codex evaluation trace into fixed process-failure categories (read-only)."""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.eval_trace_diagnosis import diagnose_events, diagnose_task_dir  # noqa: E402

EPILOG = """Categories: failed_tool_use (plugin_script / benign_search_miss / other), repeated_exploration
(commands and files seen >= 3 times), plugin_source_reads, manifest_hand_edits, lost_artifacts,
premature_closure, phase_seconds. Each has a count and at most 5 examples (commands cut to 200 chars).
Counts are pattern matches over recorded commands, not judgments of scientific quality; nothing in the
trace is executed.

Examples:
  diagnose_eval_trace.py RUNS/task-1 --output diagnosis.json
  diagnose_eval_trace.py --events events.jsonl
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, epilog=EPILOG,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("task_dir", nargs="?", type=Path,
                        help="task directory from run_literature_evaluation.py (events.jsonl, receipt.json, last.md, project/)")
    parser.add_argument("--events", type=Path, help="diagnose this events JSONL alone (no receipt, last.md or project checks)")
    parser.add_argument("--output", type=Path, help="write JSON here instead of stdout (replaced atomically)")
    args = parser.parse_args()
    if (args.task_dir is None) == (args.events is None):
        parser.error("give exactly one of TASK_DIR or --events FILE")
    try:
        result = diagnose_events(args.events) if args.events else diagnose_task_dir(args.task_dir)
    except OSError as error:
        print(f"diagnose_eval_trace: {error}", file=sys.stderr)
        return 2
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        sys.stdout.write(text)
        return 0
    descriptor, temp = tempfile.mkstemp(dir=args.output.parent, prefix=f".{args.output.name}.")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temp, args.output)
    except BaseException:
        os.unlink(temp)
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
