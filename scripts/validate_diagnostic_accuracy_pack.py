#!/usr/bin/env python3
"""Validate one offline diagnostic accuracy bundle; print JSON without writing files."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.diagnostic_accuracy_pack import validate_diagnostic_accuracy_pack  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="diagnostic-accuracy-pack-v1 JSON containing relative hashed input identities")
    args = parser.parse_args()
    try:
        result = validate_diagnostic_accuracy_pack(args.bundle)
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    except ValueError as error:
        print(json.dumps({"status": "refused", "finding": str(error)}, sort_keys=True), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
