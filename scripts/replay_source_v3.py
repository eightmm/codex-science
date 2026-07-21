#!/usr/bin/env python3
"""Verify and replay raw pages saved by Connector Contract v3."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.transport_v3 import replay_snapshot_directory  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot_dir", type=Path)
    parser.add_argument("query_id")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    pages = replay_snapshot_directory(args.snapshot_dir.resolve(), args.query_id)
    report = {
        "schema_version": 1,
        "query_id": args.query_id,
        "page_count": len(pages),
        "pages": pages,
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
