#!/usr/bin/env python3
"""Validate an offline synthetic plate-screen bundle; print JSON and write nothing."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.hts_plate_qc_pack import validate_hts_plate_qc_pack  # noqa: E402


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(f"invalid-arguments: {message}")


def main() -> int:
    parser = _Parser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="hts-pack-v1 JSON with hashed synthetic fixtures")
    try:
        args = parser.parse_args()
        result = validate_hts_plate_qc_pack(args.bundle)
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    except ValueError as error:
        print(json.dumps({"status": "refused", "finding": str(error)}, sort_keys=True), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
