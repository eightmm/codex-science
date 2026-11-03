#!/usr/bin/env python3
"""Validate one offline synthetic flow-cytometry bundle and print JSON; write nothing."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.flow_cytometry_qc_pack import validate_flow_cytometry_qc_pack  # noqa: E402


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(f"invalid-arguments: {message}")


def main():
    parser = _Parser(description=__doc__, allow_abbrev=False)
    parser.add_argument("bundle", type=Path, help="flow-cytometry-qc-pack-v1 JSON with relative hashed inputs")
    try:
        args = parser.parse_args()
        result = validate_flow_cytometry_qc_pack(args.bundle)
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    except ValueError as error:
        print(json.dumps({"status": "refused", "finding": str(error)}, sort_keys=True), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
