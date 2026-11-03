#!/usr/bin/env python3
"""Validate one offline batch-effect-pack-v1 bundle; print JSON without writes."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.batch_effect_assessment_pack import validate_batch_effect_assessment_pack  # noqa: E402


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError("invalid-arguments: " + message)


def main():
    parser = Parser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="batch-effect-pack-v1 JSON with relative hashed inputs")
    try:
        args = parser.parse_args()
        result = validate_batch_effect_assessment_pack(args.bundle)
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        return 0
    except ValueError as error:
        print(json.dumps({"status": "refused", "finding": str(error)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
