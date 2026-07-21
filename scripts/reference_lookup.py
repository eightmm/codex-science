#!/usr/bin/env python3
"""Select the minimum required skill references and optionally emit use receipts."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.reference_contract import (  # noqa: E402
    build_reference_use_receipt,
    load_reference_index,
    select_references,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill_dir", type=Path)
    parser.add_argument("--route", default="")
    parser.add_argument("--query", default="")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--receipt-dir", type=Path)
    parser.add_argument("--claim", action="append", default=[])
    args = parser.parse_args()
    skill_dir = args.skill_dir.resolve()
    index = load_reference_index(skill_dir)
    if index is None:
        raise SystemExit(f"skill has no references/index.json: {skill_dir}")
    selected = select_references(index, route=args.route, query=args.query, limit=args.limit)
    payload: dict[str, object] = {
        "schema_version": 1,
        "skill": index.skill,
        "selected": [entry.to_dict() for entry in selected],
    }
    if args.receipt_dir:
        args.receipt_dir.mkdir(parents=True, exist_ok=True)
        receipts = []
        for entry in selected:
            receipt = build_reference_use_receipt(
                skill_dir,
                entry,
                read_reason=args.route or args.query or "selected by reference lookup",
                used_for=args.claim or ["workflow-route"],
                search_terms=[args.query] if args.query else [],
            )
            path = args.receipt_dir / f"{index.skill}--{entry.id}.json"
            path.write_text(json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
            receipts.append(path.as_posix())
        payload["receipt_paths"] = receipts
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
