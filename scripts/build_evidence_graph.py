#!/usr/bin/env python3
"""Build evidence_graph.json from claims.json and studies.json."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.evidence_graph_build import build_evidence_graph  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--claims", default="claims.json")
    parser.add_argument("--studies", default="studies.json")
    parser.add_argument("--extra")
    parser.add_argument("--output", default="evidence_graph.json")
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
