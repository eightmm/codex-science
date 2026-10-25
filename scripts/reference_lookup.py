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


REFERENCE_INDEX_EPILOG = """\
references/index.json (schema_version 1; missing file is an error):
  schema_version   1
  skill            non-empty string
  references       non-empty list of objects:
    id             non-empty string, unique
    path           "references/<file>", exactly one level deep, not index.json; unique
    purpose        non-empty string
    read_when      non-empty list of strings
    required_before  non-empty list of strings
    search_patterns  optional list of strings (default [])
    authority      optional string (default "repository-contract")
    version        optional string (default "1")
    evidence_boundary  optional string (default "")
  default_policy   optional string (default "load-minimum-required")
With neither --route nor --query, every reference is returned in id order.
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=REFERENCE_INDEX_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("skill_dir", type=Path, help="skill directory containing references/index.json (format below)")
    parser.add_argument(
        "--route",
        default="",
        help="workflow route name; a substring of a reference's required_before adds 20 to its score, of read_when adds 10 (default: none)",
    )
    parser.add_argument(
        "--query",
        default="",
        help="free-text terms; lowercased and split into runs of a-z, 0-9, _ and -; each term found in a reference's "
        "id, purpose, read_when, required_before or search_patterns adds 3 (default: none)",
    )
    parser.add_argument("--limit", type=int, help="maximum number of references to return (default: all matches)")
    parser.add_argument("--receipt-dir", type=Path, help="directory to write one <skill>--<id>.json use receipt per selected reference")
    parser.add_argument(
        "--claim",
        action="append",
        default=[],
        help="used_for value recorded in each receipt; repeatable (default: workflow-route)",
    )
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
