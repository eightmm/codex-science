#!/usr/bin/env python3
"""Validate recorded target-assessment handoffs offline, without writing files."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.target_assessment_pack import validate_target_assessment_pack  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="directory containing dossier.json and its hash-bound artifacts")
    args = parser.parse_args()
    try:
        result = validate_target_assessment_pack(args.bundle)
    except (ValueError, OSError, RecursionError) as error:
        message = str(error)
        code, separator, detail = message.partition(": ")
        result = {"status": "refused", "finding": code if separator else "PACK_INPUT",
                  "message": detail if separator else message}
        print(json.dumps(result, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
