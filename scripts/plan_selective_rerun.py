#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.collaboration import selective_rerun_plan  # noqa: E402
from codex_science.evidence import _validate_evidence_graph  # noqa: E402
from codex_science.evidence_graph_v2 import graph_records  # noqa: E402

PLAN_EPILOG = """\
graph JSON (schema_version 1 as written by build_evidence_graph.py, or 2; required):
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
    parser.add_argument("graph", type=Path, help="evidence graph JSON, schema_version 1 or 2 (format below)")
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
    try:
        payload = json.loads(args.graph.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("evidence graph must be a JSON object")
        if payload.get("schema_version") == 1:
            _nodes, edges = _validate_evidence_graph(payload)
        elif payload.get("schema_version") == 2:
            _nodes, edges = graph_records(payload)
        else:
            raise ValueError(f"unsupported evidence graph schema_version {payload.get('schema_version')!r}; expected 1 or 2")
        unknown = [node for node in args.changed if node not in _nodes]
        if unknown:
            raise ValueError(f"--changed id is not a node in the evidence graph: {', '.join(unknown)}")
        steps = json.loads(args.steps.read_text(encoding="utf-8"))
        if isinstance(steps, dict):
            steps = steps.get("steps", [])
        if not isinstance(steps, list):
            raise ValueError("steps must be a JSON list or an object whose 'steps' value is a list")
        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                raise ValueError(f"step at index {index} must be a JSON object")
            for field in ("consumes", "produces"):
                if field in step and (
                    not isinstance(step[field], list)
                    or any(not isinstance(node, str) for node in step[field])
                ):
                    raise ValueError(f"step at index {index} field '{field}' must be a list of strings")
        report = selective_rerun_plan(changed_nodes=args.changed, edges=edges, steps=steps, review_paths=args.review_path)
        text = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.output: args.output.write_text(text, encoding="utf-8")
    except (ValueError, OSError, UnicodeError, RecursionError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if not args.output: print(text, end="")
    return 0
if __name__ == "__main__": raise SystemExit(main())
