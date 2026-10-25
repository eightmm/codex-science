#!/usr/bin/env python3
"""Validate a portable scientific manuscript package."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.manuscript import validate_manuscript_package  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "package",
        type=Path,
        help="manuscript package directory; must contain manuscript.md, manuscript-contract.json, "
        "claim-citation-map.json, reporting-checklist.json and submission-package.json",
    )
    parser.add_argument("--output", type=Path, help="also write the validation result JSON to this path")
    parser.add_argument("--require-clean", action="store_true", help="exit 1 unless the validation status is passed")
    args = parser.parse_args()

    result = validate_manuscript_package(args.package)
    serialized = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    if args.require_clean and result["status"] != "passed":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
