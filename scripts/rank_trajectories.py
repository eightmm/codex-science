#!/usr/bin/env python3
"""Build a consensus report from trajectory-set-v1 JSON."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.trajectory_consensus import build_consensus  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="-", help="JSON input path, or - for stdin")
    args = parser.parse_args()
    try:
        raw = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8")
        result = build_consensus(json.loads(raw))
        rendered = json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        rendered.encode("utf-8")
        print(rendered)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError, KeyError,
            RecursionError, OverflowError, ArithmeticError) as error:
        print(json.dumps({"schema": "trajectory-consensus-error-v1",
                          "error": {"code": "invalid_request", "message": str(error)}}, sort_keys=True, allow_nan=False))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
