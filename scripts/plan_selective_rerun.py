#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.collaboration import selective_rerun_plan  # noqa: E402
from codex_science.evidence_graph_v2 import graph_records  # noqa: E402

PLAN_EPILOG = """\
graph JSON (schema_version 2, required):
  nodes[]   objects with id and type (both non-empty strings, ids unique)
  edges[]   objects with source, target (existing node ids) and relation, one of
            supports, contradicts, depends_on, duplicates, derived_from,
            shares_cohort, shares_samples, propagated_from, training_overlap
            (no duplicate source/target/relation triple)
  Only supports, contradicts, depends_on, derived_from, propagated_from and
  training_overlap edges propagate impact; edge direction is source -> target.
steps JSON: a list of step objects, or an object whose steps[] is used.
  id                  echoed in rerun_steps (not validated)
  consumes[]          node ids this step reads
  produces[]          node ids this step writes
  description         optional (default: the id)
  requires_approval   optional (default: false)
A step is selected when any consumes or produces id is impacted.
Output keys: changed_nodes, impacted_nodes, rerun_steps, invalidated_review_receipts,
approval_required.
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plan the pipeline steps to rerun after changed evidence-graph nodes.",
        epilog=PLAN_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("graph", type=Path, help="evidence graph v2 JSON (format below)")
    parser.add_argument("steps", type=Path, help="pipeline steps JSON (format below)")
    parser.add_argument("--changed", action="append", required=True, help="changed node ID; repeatable, at least one")
    parser.add_argument(
        "--review-path",
        action="append",
        default=[],
        help="review receipt path reported as invalidated_review_receipts when any node is impacted; repeatable (default: none)",
    )
    parser.add_argument("--output", type=Path, help="write the rerun plan JSON to this path instead of stdout")
    args = parser.parse_args()
    _nodes, edges = graph_records(json.loads(args.graph.read_text()))
    steps = json.loads(args.steps.read_text())
    if isinstance(steps, dict): steps = steps.get("steps", [])
    report = selective_rerun_plan(changed_nodes=args.changed, edges=edges, steps=steps, review_paths=args.review_path)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output: args.output.write_text(text, encoding="utf-8")
    else: print(text, end="")
    return 0
if __name__ == "__main__": raise SystemExit(main())
