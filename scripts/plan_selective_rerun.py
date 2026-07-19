#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.collaboration import selective_rerun_plan  # noqa: E402
from codex_science.evidence_graph_v2 import graph_records  # noqa: E402

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("graph", type=Path)
    parser.add_argument("steps", type=Path)
    parser.add_argument("--changed", action="append", required=True)
    parser.add_argument("--review-path", action="append", default=[])
    parser.add_argument("--output", type=Path)
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
