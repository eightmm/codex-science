#!/usr/bin/env python3
"""Compare cited report statements with verified run-local support excerpts."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.statement_support import check_statement_support  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--report", action="append", default=[])
    parser.add_argument("--require-excerpts", action="store_true")
    args = parser.parse_args()
    try:
        result = check_statement_support(args.run_dir, args.report or None)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, KeyError, TypeError, RecursionError) as error:
        print(json.dumps({"schema": "statement-support-error-v1", "error": {"code": "invalid_input", "message": str(error)}}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(",", ":")))
    return 1 if args.require_excerpts and result["counts"]["no_excerpt"] + result["counts"]["untraced"] > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
