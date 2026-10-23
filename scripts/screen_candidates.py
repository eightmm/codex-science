#!/usr/bin/env python3
"""Build and adjudicate a deterministic literature screening pool."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.screening_pool import apply_screening_decisions, build_candidate_pool  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    pool_parser = subparsers.add_parser("pool", help="merge query results into candidates.json")
    pool_parser.add_argument("--run-dir", type=Path, required=True)
    apply_parser = subparsers.add_parser("apply", help="apply screening decisions to the candidate pool")
    apply_parser.add_argument("--run-dir", type=Path, required=True)
    apply_parser.add_argument("--decisions", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "pool":
            result = build_candidate_pool(args.run_dir)
            output = args.run_dir / "candidates.json"
        else:
            result = apply_screening_decisions(args.run_dir, args.decisions)
            output = args.run_dir / "screening.json"
    except (ValueError, OSError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    counts = result["counts"] if "counts" in result else {
        "returned_records": result["returned_records"], "unique_records": result["unique_records"],
        "skipped_results": len(result["skipped_results"]),
    }
    print(json.dumps({"counts": counts, "output": str(output)}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
