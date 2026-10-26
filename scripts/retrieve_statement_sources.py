#!/usr/bin/env python3
"""Rank run-local source records for report statements without network access."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.statement_retrieval import retrieve_statement_sources  # noqa: E402
from codex_science.run_packaging import digest_mismatch_hint  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", help="saved run bundle directory")
    parser.add_argument("--report", action="append", default=[])
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    try:
        result = retrieve_statement_sources(args.run_dir, args.report or None, args.top_k)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, KeyError, TypeError, RecursionError) as error:
        print(f"retrieve_statement_sources: invalid input: {error}{digest_mismatch_hint(error, args.run_dir)}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
