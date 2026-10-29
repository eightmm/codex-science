#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.reviewer_benchmark import load_cases, score_cases  # noqa: E402

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=ROOT / "benchmarks" / "reviewer",
                        help="Existing directory containing benchmark JSON cases")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-safe", action="store_true",
                        help="Fail for zero cases, unsafe passes, or incomplete critical/major recall")
    args = parser.parse_args()
    try:
        report = score_cases(load_cases(args.cases))
        text = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.output: args.output.write_text(text, encoding="utf-8")
        else: print(text, end="")
    except (OSError, ValueError) as error:
        parser.exit(2, f"error: {error}\n")
    if args.require_safe and (report["case_count"] == 0 or report["unsafe_pass_rate"] != 0 or report["critical_recall"] != 1 or report["major_recall"] != 1):
        return 1
    return 0
if __name__ == "__main__": raise SystemExit(main())
