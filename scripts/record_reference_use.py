#!/usr/bin/env python3
"""Record skill reference reads in a run-local reference-use ledger."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.reference_contract import record_reference_uses  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--reference", type=Path, action="append", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--used-for", action="append", default=[])
    parser.add_argument("--section", action="append", default=[])
    parser.add_argument("--search-term", action="append", default=[])
    parser.add_argument("--output", default="reference-use-ledger.json")
    args = parser.parse_args()
    try:
        summary = record_reference_uses(
            args.run_dir,
            args.reference,
            read_reason=args.reason,
            used_for=args.used_for or ["workflow-route"],
            sections=args.section,
            search_terms=args.search_term,
            output=args.output,
        )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
