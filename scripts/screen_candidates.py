#!/usr/bin/env python3
"""Build and adjudicate a deterministic literature screening pool."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.screening_pool import apply_screening_decisions, build_candidate_pool  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    pool_parser = subparsers.add_parser("pool", help="merge query results into candidates.json")
    pool_parser.add_argument("--run-dir", type=Path, required=True,
                             help="run directory with queries.jsonl and its query results; verifies non-null response_sha256 case-insensitively and writes candidates.json")
    apply_parser = subparsers.add_parser(
        "apply", help="apply screening decisions to the candidate pool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''Decisions file format (screening-decisions-v1):

```json
{
  "schema": "screening-decisions-v1",
  "reviewer": "Reviewer name",
  "stage": "full text",
  "groups": [
    {
      "decision": "include",
      "criterion": "Meets the protocol eligibility criteria",
      "rationale": "Eligible based on the available abstract.",
      "record_ids": ["<record_id_with_abstract>"]
    },
    {
      "decision": "exclude",
      "criterion": "Does not meet the protocol population criterion",
      "rationale": "Checked fulltext/article.txt; the study population is ineligible.",
      "record_ids": ["<record_id_without_abstract>"]
    }
  ]
}
```

For an exclusion without an abstract, include an existing run-relative
`fulltext/...` artifact path in the rationale so its contents are hashed as
the evidence; Markdown links such as [full text](fulltext/article.txt) also work.
Use separate groups when multiple records name two or more existing evidence
files. Missing files do not count; one existing file may be shared by a group.
Inputs and evidence cannot be output paths. Concurrent apply calls are
serialized using a persistent .<run-name>.screening.lock beside the resolved
run directory, outside the packaged contents. Lock acquisition failures are
reported as errors. Replace the example record IDs with IDs from candidates.json.''',
    )
    apply_parser.add_argument("--run-dir", type=Path, required=True,
                              help="run directory with candidates.json; writes screening.json")
    apply_parser.add_argument("--decisions", type=Path, required=True,
                              help="screening-decisions-v1 JSON file (format below)")
    args = parser.parse_args(argv)
    try:
        if args.command == "pool":
            result = build_candidate_pool(args.run_dir)
            output = args.run_dir / "candidates.json"
        else:
            result = apply_screening_decisions(args.run_dir, args.decisions)
            output = args.run_dir / "screening.json"
    except (ValueError, OSError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    counts = result["counts"] if "counts" in result else {
        "returned_records": result["returned_records"], "unique_records": result["unique_records"],
        "skipped_results": len(result["skipped_results"]),
    }
    print(json.dumps({"counts": counts, "output": str(output)}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
