#!/usr/bin/env python3
"""Validate one offline synthetic OD bundle; print JSON and write no files."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from codex_science.growth_curve_pack import validate_growth_curve_pack  # noqa: E402


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError("invalid-arguments: " + message)


def main():
    parser = _Parser(description=__doc__)
    parser.add_argument("bundle", help="growth-pack-v1 JSON naming hash-bound synthetic fixture inputs")
    try:
        args = parser.parse_args()
        result = validate_growth_curve_pack(args.bundle)
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 0
    except (ValueError, OSError) as error:
        print(json.dumps({"status": "refused", "finding": str(error)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
