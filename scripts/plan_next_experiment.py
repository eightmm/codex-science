#!/usr/bin/env python3
"""Create a deterministic, non-executing multi-objective experiment proposal."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.experiment_planner import plan_next_experiment, validate_experiment_proposal  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("input must be a JSON object")
        proposal = plan_next_experiment(payload)
        validate_experiment_proposal(proposal)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(proposal, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Success! Proposal written to: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
