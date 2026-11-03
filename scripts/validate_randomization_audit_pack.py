#!/usr/bin/env python3
"""Check one offline synthetic randomization bundle and print JSON without writing files."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from codex_science.randomization_audit_pack import validate_randomization_audit_pack  # noqa: E402


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError("invalid-arguments: " + message)


def main():
    parser = _Parser(description=__doc__, allow_abbrev=False)
    parser.add_argument("bundle", help="randomization-audit-pack-v1 JSON with hash-bound synthetic fixture inputs")
    try:
        args = parser.parse_args()
        result = validate_randomization_audit_pack(args.bundle)
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 0
    except (ValueError, OSError) as error:
        finding = str(error) if isinstance(error, ValueError) else "input-file: unreadable input"
        print(json.dumps({"status": "refused", "finding": finding}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
