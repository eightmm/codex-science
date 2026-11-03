#!/usr/bin/env python3
"""Validate an offline meta-analysis fixture or evidence bundle without writing files."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.meta_analysis_pack import MAX_STUDIES, validate_meta_analysis_pack  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path,
                        help=f"directory containing pack.json and hash-bound artifacts (at most {MAX_STUDIES} studies)")
    args = parser.parse_args()
    try:
        result = validate_meta_analysis_pack(args.bundle)
    except ValueError as error:
        code, _, detail = str(error).partition(": ")
        print(json.dumps({"status": "refused", "finding": code, "message": detail}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
