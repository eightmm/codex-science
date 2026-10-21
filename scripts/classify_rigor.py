#!/usr/bin/env python3
"""Classify a rigor-request-v1 JSON object."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.rigor import classify_rigor  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="-", help="JSON input path, or - for stdin")
    args = parser.parse_args()
    try:
        raw = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8")
        request = json.loads(raw)
        decision = classify_rigor(request)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, RecursionError) as error:
        print(json.dumps({"error": {"code": "invalid_request", "message": str(error)},
                          "schema": "rigor-error-v1"}, sort_keys=True))
        return 2
    print(json.dumps(decision, sort_keys=True, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
