#!/usr/bin/env python3
"""Plan or explicitly fetch capped, open-access Europe PMC full text."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.open_fulltext import fetch_fulltext, identifiers_from_run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--id", dest="ids", action="append", default=[])
    parser.add_argument("--execute", action="store_true", help="allow Europe PMC network requests")
    parser.add_argument("--max-fetches", type=int, default=10)
    parser.add_argument("--max-seconds", type=float, default=60)
    parser.add_argument("--max-body-bytes", type=int, default=8 * 1024 * 1024)
    parser.add_argument("--max-candidates", type=int, default=30)
    args = parser.parse_args(argv)
    try:
        if args.run_dir is None and not args.ids:
            raise ValueError("provide --run-dir and/or at least one --id")
        if args.execute and args.run_dir is None:
            raise ValueError("--run-dir is required with --execute")
        identifiers = identifiers_from_run(args.run_dir) if args.run_dir is not None else []
        identifiers.extend(args.ids)
        output = fetch_fulltext(identifiers, args.run_dir or Path.cwd(), execute=args.execute,
                                max_fetches=args.max_fetches, max_seconds=args.max_seconds,
                                max_body_bytes=args.max_body_bytes, max_candidates=args.max_candidates)
        print(json.dumps(output, sort_keys=True, ensure_ascii=False))
        return 0
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, json.JSONDecodeError,
            RecursionError, OverflowError) as exc:
        print(json.dumps({"schema": "open-fulltext-error-v1", "error": {
            "code": "invalid_request", "message": str(exc)}}, sort_keys=True, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
