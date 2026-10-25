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


EPILOG = """\
input JSON keys (schema_version optional; must be 1 if given):
  decision                 required non-empty string
  objectives               required non-empty list of {name (unique), direction
                           (maximize or minimize), weight (number >= 0, default 1.0),
                           required (bool, default true)}; at least one weight must be positive
  candidates               required non-empty list of {id (unique non-empty string),
                           properties (object: objective name -> finite number; must
                           include every required objective), cost (>= 0, default 0),
                           uncertainty (>= 0, default 0), diversity_group (or scaffold_id;
                           default: the candidate id), control (bool, default false),
                           eligible (bool, default true), exclusion_reason (default "")}
  constraints              required object: batch_size (required, integer >= 1),
                           budget (>= 0, default 0), diversity_group_cap (or scaffold_cap;
                           default batch_size), minimum_controls (integer >= 0, default 0)
  uncertainty_weight       optional number >= 0; default 0.25
  diversity_bonus          optional number >= 0; default 0.1
  claim_ids                optional list of non-empty strings; default: empty list
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", type=Path, help="candidate-planning JSON object (format below)")
    parser.add_argument("--output", type=Path, required=True, help="output proposal JSON path; overwritten")
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
