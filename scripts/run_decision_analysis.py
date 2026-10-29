#!/usr/bin/env python3
"""Run bounded finite statistical decision analysis."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.cli_io import (  # noqa: E402
    load_json_object,
    preflight_output_paths,
    write_json_atomic,
    write_text_atomic,
)
from codex_science.decision_analysis import (  # noqa: E402
    render_decision_analysis,
    run_decision_analysis,
)


EPILOG = """\
input JSON keys (schema_version must be 1):
  analysis_id, claim_id, question, information_boundary, consequence_horizon,
  applicability, criterion_rationale      required non-empty strings
  state_model              required; must be 'exogenous'
  criterion                required; loss: bayes-risk, minimax-loss, minimax-regret;
                           utility: expected-utility, minimax-regret;
                           payoff: expected-payoff, minimax-regret
  scale                    required object: kind (loss, utility, payoff), unit,
                           risk_attitude (required value: encoded-in-loss for loss,
                           encoded-in-utility for utility, risk-neutral for payoff)
  actions                  required non-empty list (max 256) of {id (unique), label (optional)}
  states                   required non-empty list (max 256) of {id (unique), label (optional),
                           prior (optional number in [0, 1])}; priors must be given for
                           every state or none, and must sum to 1 (tolerance 1e-9).
                           bayes-risk, expected-utility, expected-payoff require priors.
  values                   required list of {action, state, value (finite number)};
                           exactly one entry per action/state pair
  assumptions              optional list of non-empty strings
  tie_tolerance            optional, in (0, 0.001]; default 1e-12
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", type=Path, help="decision-problem JSON object (format below)")
    parser.add_argument("--output", type=Path, required=True, help="output JSON path; overwritten with the analysis result")
    parser.add_argument("--report", type=Path, help="optional path for a rendered report of the analysis")
    args = parser.parse_args()
    try:
        result = run_decision_analysis(load_json_object(args.input))
        preflight_output_paths(args.output, args.report)
        write_json_atomic(args.output, result)
        if args.report is not None:
            write_text_atomic(args.report, render_decision_analysis(result))
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Success! Data written to: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
