#!/usr/bin/env python3
"""Build the deterministic manuscript-writing acceptance package."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.manuscript import build_acceptance_package  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    build_acceptance_package(payload, args.output)
    print(args.output / "submission-package.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
