#!/usr/bin/env python3
"""Search the audited catalog without loading every skill into context.

Pass the query as one or more words (quoting is optional) or with --query TEXT;
all words are joined with single spaces into one search. Prints matches as JSON.
With --name NAME, prints the exact inventory record and its source entry instead.
Inventories with duplicate source keys are refused.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.catalog import load_inventory, search_inventory  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("words", nargs="*", metavar="query", help="search words, joined with single spaces into one search")
    parser.add_argument("--query", action="append", default=[], metavar="TEXT", help="alternative spelling of the query; combined with any positional words")
    parser.add_argument(
        "--inventory",
        type=Path,
        default=ROOT / "catalog" / "inventory.json",
        help="inventory JSON to search (default: catalog/inventory.json)",
    )
    parser.add_argument("--name", metavar="NAME", help="print the exact inventory record named NAME and its source entry (exit 1 if absent); cannot be combined with a query")
    parser.add_argument("--limit", type=int, default=5, help="maximum number of results (default: 5)")
    parser.add_argument("--include-inactive", action="store_true", help="also search inactive catalog entries")
    args = parser.parse_args()
    query = " ".join(" ".join([*args.query, *args.words]).split())
    if args.name is not None:
        if query:
            parser.error("--name cannot be combined with a query")
        inventory = load_inventory(args.inventory)
        record = next((item for item in inventory["skills"] if item.get("name") == args.name), None)
        if record is None:
            print(json.dumps({"error": f"no inventory record named {args.name!r}"}, ensure_ascii=False), file=sys.stderr)
            sys.exit(1)
        source = next((item for item in inventory.get("sources", []) if item.get("key") == record.get("source")), None)
        print(json.dumps({"record": record, "source": source}, indent=2, ensure_ascii=False))
        return
    if not query:
        parser.error("a query is required (positional words or --query TEXT)")
    matches = search_inventory(
        load_inventory(args.inventory),
        query,
        include_inactive=args.include_inactive,
        limit=args.limit,
    )
    print(json.dumps(matches, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
