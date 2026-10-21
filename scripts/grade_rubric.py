#!/usr/bin/env python3
"""Grade a rubric-tree-v1 JSON rubric against criterion results."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.rubric_tree import grade  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rubric", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--run-dir")
    args = parser.parse_args()
    try:
        if args.rubric == "-" and args.results == "-":
            raise ValueError("at most one of --rubric and --results may be -")
        rubric_raw = sys.stdin.read() if args.rubric == "-" else Path(args.rubric).read_text(encoding="utf-8")
        results_raw = sys.stdin.read() if args.results == "-" else Path(args.results).read_text(encoding="utf-8")
        rubric = json.loads(rubric_raw)
        results = json.loads(results_raw)
        if not isinstance(results, dict):
            raise ValueError("results must be a JSON object")
        output = grade(rubric, results, Path(args.run_dir) if args.run_dir else None)
        rendered = json.dumps(output, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError, KeyError,
            RecursionError, OverflowError) as error:
        print(json.dumps({"schema": "rubric-score-error-v1",
                          "error": {"code": "invalid_input", "message": str(error)}},
                         sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False))
        return 2
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
