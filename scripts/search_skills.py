#!/usr/bin/env python3
"""Search the audited catalog without loading every skill into context."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.catalog import load_inventory, search_inventory  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--inventory", type=Path, default=ROOT / "catalog" / "inventory.json")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--include-inactive", action="store_true")
    args = parser.parse_args()
    matches = search_inventory(
        load_inventory(args.inventory),
        args.query,
        include_inactive=args.include_inactive,
        limit=args.limit,
    )
    print(json.dumps(matches, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
