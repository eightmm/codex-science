#!/usr/bin/env python3
"""Build evidence_graph.json from claims.json and studies.json."""
from __future__ import annotations

import argparse
import json
import textwrap
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.evidence import NODE_TYPES, RELATIONS  # noqa: E402
from codex_science.evidence_graph_build import build_evidence_graph  # noqa: E402


def _epilog() -> str:
    node_types = textwrap.fill(", ".join(sorted(NODE_TYPES - {"claim", "study"})), 70, subsequent_indent=" " * 10)
    relations = textwrap.fill(", ".join(sorted(RELATIONS)), 70, subsequent_indent=" " * 10)
    return textwrap.dedent(f"""\
        --extra FILE (inside the run directory) adds nodes and edges that claims.json and
        studies.json cannot express:

          {{"schema": "evidence-graph-extra-v1",
           "nodes": [{{"id": "dataset-1", "type": "dataset", "label": "Cohort data"}}],
           "edges": [{{"source": "study-1", "target": "dataset-1", "relation": "derived_from"}}]}}

        nodes: "id" is non-empty and not an existing node id; "type" is one of:
          {node_types}
          (claim and study nodes come only from claims.json and studies.json); other keys such
          as "label" are kept. A cohort node whose id matches a study cohort_id updates that
          automatically created cohort node.
        edges: "source", "target" and "relation"; relation is one of:
          {relations}.
          Both endpoints must exist as built-in or extra nodes. study->claim supports and
          contradicts edges must be declared in studies.json instead.
        The builder itself adds claim, study and cohort nodes and the study->claim and
        study->cohort edges. Problems are collected and reported together; nothing is
        written when any is found.
        """)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, epilog=_epilog(), formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--run-dir", type=Path, required=True, help="run directory holding the inputs and output")
    parser.add_argument("--claims", help="claims register JSON in the run directory (default claims.json)")
    parser.add_argument("--studies", help="study table JSON in the run directory (default studies.json)")
    parser.add_argument("--extra", help="extra nodes/edges JSON in the run directory; format below")
    parser.add_argument("--output", default="evidence_graph.json", help="graph file to write inside the run directory (default evidence_graph.json)")
    args = parser.parse_args(argv)
    try:
        result = build_evidence_graph(args.run_dir, args.claims, args.studies, args.extra, args.output)
    except (ValueError, OSError, RuntimeError, UnicodeError, TypeError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
