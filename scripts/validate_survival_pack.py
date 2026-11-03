#!/usr/bin/env python3
"""Validate an offline synthetic survival bundle; print JSON and write nothing."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from codex_science.survival_pack import validate_survival_pack  # noqa: E402


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError("cli-arguments: " + message)


def main() -> int:
    parser = _Parser(description=__doc__)
    parser.add_argument("bundle", help="survival-pack-v1 JSON naming hash-bound synthetic fixture inputs")
    try:
        args = parser.parse_args()
        result = validate_survival_pack(args.bundle)
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 0
    except (ValueError, OSError) as error:
        print(json.dumps({"status": "refused", "error": str(error)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
