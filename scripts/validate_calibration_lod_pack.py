#!/usr/bin/env python3
"""Check one offline synthetic calibration bundle and print JSON without writing files."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.calibration_lod_pack import validate_calibration_lod_pack  # noqa: E402


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(f"invalid-arguments: {message}")


def main():
    parser = _Parser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="calibration-lod-pack-v1 JSON with relative hashed synthetic inputs")
    try:
        args = parser.parse_args()
        result = validate_calibration_lod_pack(args.bundle)
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    except ValueError as error:
        print(json.dumps({"status": "refused", "finding": str(error)}, sort_keys=True), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
