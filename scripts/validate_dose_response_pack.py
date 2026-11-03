#!/usr/bin/env python3
"""Validate offline dose-response artifacts without writing files."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.dose_response_pack import validate_dose_response_pack  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="dose-response-pack-v1 JSON; paths are bundle-relative")
    args = parser.parse_args()
    try:
        result = validate_dose_response_pack(args.input)
    except ValueError as error:
        print(f"error: dose-response-pack: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
