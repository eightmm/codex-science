#!/usr/bin/env python3
"""Validate an artifact bundle and optionally emit a record/source review."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.artifacts import validate_bundle  # noqa: E402
from codex_science.evidence import (  # noqa: E402
    CLAIM_STATUSES,
    CONFIDENCE_LEVELS,
    EVIDENCE_TYPES,
    NODE_TYPES,
    QUERY_STATUSES,
    RELATIONS,
    SIDECAR_KINDS,
)
from codex_science.review import review_manifest  # noqa: E402


def _values(values: set[str]) -> str:
    return ", ".join(sorted(values))


EPILOG = f"""\
Recognized sidecar manifest kinds: {_values(SIDECAR_KINDS)}.
Allowed values (conventional file: field):
  evidence-graph   (evidence_graph.json): edges[].relation = {_values(RELATIONS)}
                   nodes[].type = {_values(NODE_TYPES)}
  claim-register   (claims.json): claims[].status = {_values(CLAIM_STATUSES)}
  query-ledger     (queries.jsonl): each record's status = {_values(QUERY_STATUSES)}
  study-table      (studies.json, optional): studies[].evidence_type = {_values(EVIDENCE_TYPES)}
  lane-receipt     (lanes/<lane>.json): confidence = {_values(CONFIDENCE_LEVELS)}
Complete example of the stable sidecars: examples/literature-review-reviewed-run/
(relative to the plugin root).
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check manifest artifact bytes and sidecar schemas (exit 1 with an error on failure); optionally write the record/source review.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("manifest", type=Path, help="path to the run manifest.json")
    parser.add_argument("--review-output", type=Path, help="also write the deterministic record/source review JSON here; not the independent review receipt or a reviewed artifact")
    parser.add_argument("--require-passed-review", action="store_true", help="exit non-zero unless the review status is passed; requires --review-output")
    args = parser.parse_args()
    manifest_path = args.manifest.resolve()
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        sidecars = validate_bundle(manifest, manifest_path.parent)
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        if "Artifact digest mismatch" in str(error):
            print(
                f"hint: rehash with package_run.py refresh --run-dir {manifest_path.parent}",
                file=sys.stderr,
            )
        raise SystemExit(1) from None
    print("artifact bundle: valid")
    if args.review_output:
        try:
            review = review_manifest(manifest, manifest_path.parent, sidecars=sidecars)
            args.review_output.parent.mkdir(parents=True, exist_ok=True)
            args.review_output.write_text(
                json.dumps(review, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except (ValueError, OSError, json.JSONDecodeError) as error:
            print(f"error: {error}", file=sys.stderr)
            if "Artifact digest mismatch" in str(error):
                print(
                    f"hint: rehash with package_run.py refresh --run-dir {manifest_path.parent}",
                    file=sys.stderr,
                )
            raise SystemExit(1) from None
        print(f"artifact review: {review['status']}")
        if args.require_passed_review and review["status"] != "passed":
            raise SystemExit("artifact review has unresolved findings")
    elif args.require_passed_review:
        raise SystemExit("--require-passed-review requires --review-output")


if __name__ == "__main__":
    main()
