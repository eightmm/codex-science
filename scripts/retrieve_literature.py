#!/usr/bin/env python3
"""Retrieve paginated literature into a run directory with a query ledger."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.literature_retrieval import retrieve_literature  # noqa: E402
from codex_science.transport_v3 import TransportError  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("source", choices=("europepmc", "pubmed"))
    parser.add_argument("query")
    parser.add_argument("--page-size", type=int, default=25)
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--evidence-cutoff")
    parser.add_argument("--abstracts", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = retrieve_literature(
            args.run_dir, args.source, args.query,
            page_size=args.page_size, max_pages=args.max_pages,
            evidence_cutoff=args.evidence_cutoff, abstracts=args.abstracts,
        )
    except (ValueError, FileExistsError, OSError, RuntimeError, TransportError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps({key: value for key, value in summary.items() if key != "records"}, ensure_ascii=False, sort_keys=True))
    for row in summary["records"]:
        print(f"{row['id']}\t{row['year']}\t{row['title']}\tabstract={'written' if row['abstract_written'] else 'no'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
