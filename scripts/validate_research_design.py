#!/usr/bin/env python3
"""Validate and fingerprint a preregistered quantitative research design."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.cli_io import load_json_object, write_json_atomic  # noqa: E402
from codex_science.research_design import build_research_design  # noqa: E402


EPILOG = """\
input JSON keys (schema_version must be 1; required unless marked optional):
  design_id, question      non-empty strings
  experimental_unit, observational_unit
                           key must be present; value is converted to a string
  outcome                  object: name, measurement (non-empty strings)
  estimand                 object: population, contrast, summary_measure
                           (non-empty strings)
  assignment               object: type = randomized, observational,
                           quasi-experimental, simulation, or descriptive
  analysis                 object: method (non-empty string);
                           optional aggregation_unit (string), cluster_adjustment (bool)
  primary_endpoints        non-empty list of objects: id (non-empty, unique),
                           decision_threshold (non-empty string)
  multiplicity             object: method = none, bonferroni, holm,
                           benjamini-hochberg, hierarchical, gatekeeping, custom;
                           optional family_size (integer, default: number of endpoints)
  missing_data             object: strategy = complete-case, multiple-imputation,
                           inverse-probability, model-based, none-expected, custom
  exclusions               object (may be empty); exclusions.prespecified is
                           checked for a finding, not required
  stopping                 object; optional planned_looks (integer >= 1, default 1).
                           With planned_looks > 1 and no alpha_spending or decision_rule,
                           a critical optional-stopping-uncontrolled finding is added.
  sample_size              object: planned (integer >= 1); optional rationale
                           (absence is a finding, not an error)
  locked_before_outcomes   boolean; false is reported as a major
                           outcome-dependent-design finding
  sensitivity_analyses     optional list of non-empty strings
  identification_assumptions   optional list of non-empty strings
  outcome.subjective, blinding   optional; blinding is an optional object
  fingerprint              optional; removed on input and recomputed on output
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", type=Path, help="research-design JSON object (format below)")
    parser.add_argument("--output", type=Path, required=True, help="output JSON path; adds audit_status, audit_findings, fingerprint")
    parser.add_argument("--require-clean", action="store_true", help="exit 1 unless audit_status is 'passed' (default: exit 0)")
    args = parser.parse_args()
    try:
        result = build_research_design(load_json_object(args.input))
        write_json_atomic(args.output, result)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Success! Data written to: {args.output.resolve()}")
    return 1 if args.require_clean and result["audit_status"] != "passed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
