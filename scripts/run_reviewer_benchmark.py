#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.reviewer_benchmark import load_cases, score_cases  # noqa: E402

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=ROOT / "benchmarks" / "reviewer")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-safe", action="store_true")
    args = parser.parse_args()
    report = score_cases(load_cases(args.cases))
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output: args.output.write_text(text, encoding="utf-8")
    else: print(text, end="")
    if args.require_safe and (report["unsafe_pass_rate"] != 0 or report["critical_recall"] != 1 or report["major_recall"] != 1):
        return 1
    return 0
if __name__ == "__main__": raise SystemExit(main())
