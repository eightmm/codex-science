#!/usr/bin/env python3
"""Build the deterministic manuscript-writing acceptance package."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.manuscript import build_acceptance_package  # noqa: E402
from codex_science.cli_io import load_json_object  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="JSON object with integer schema_version 1 and non-empty string manuscript_id")
    parser.add_argument("output", type=Path, help="new or empty package directory; invalid inputs leave it unchanged")
    args = parser.parse_args()
    try:
        payload = load_json_object(args.input)
        build_acceptance_package(payload, args.output)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(args.output / "submission-package.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
