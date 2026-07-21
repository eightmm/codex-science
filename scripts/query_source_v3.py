#!/usr/bin/env python3
"""Execute a true-paginated Connector Contract v3 source query."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.connector_contract import QueryRequest  # noqa: E402
from codex_science.source_operations_v3 import SOURCE_OPERATIONS_V3  # noqa: E402
from codex_science.transport_v3 import execute_paginated  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", choices=sorted(SOURCE_OPERATIONS_V3))
    parser.add_argument("query")
    parser.add_argument("--page-size", type=int, default=25)
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--evidence-cutoff")
    parser.add_argument("--snapshot-dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    request = QueryRequest(
        source=args.source,
        operation="search",
        parameters={"query": args.query},
        page_size=args.page_size,
        max_pages=args.max_pages,
        evidence_cutoff=args.evidence_cutoff,
        source_contract_version="3",
    )
    result = execute_paginated(
        SOURCE_OPERATIONS_V3[args.source],
        request,
        snapshot_dir=None if args.snapshot_dir is None else args.snapshot_dir.resolve(),
    )
    text = json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
