#!/usr/bin/env python3
"""Validate an offline synthetic solid-state screening bundle without writing it."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.solid_state_screening import validate_bundle  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="directory containing contract.json and the five fixed stage records")
    args = parser.parse_args()
    try:
        report = validate_bundle(args.bundle)
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
