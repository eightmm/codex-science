#!/usr/bin/env python3
"""Validate offline synthetic single-cell pseudobulk evidence; print JSON and write nothing."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.single_cell_pseudobulk_pack import validate_single_cell_pseudobulk_pack  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pack", type=Path, help="single-cell-pseudobulk-pack-v1 JSON with hashed synthetic fixtures")
    args = parser.parse_args()
    try:
        result = validate_single_cell_pseudobulk_pack(args.pack)
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
