#!/usr/bin/env python3
"""Audit convergence, residuals, invariants, precision, and cross-method agreement."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.cli_io import load_json_object, write_json_atomic  # noqa: E402
from codex_science.numerical_verification import run_numerical_verification  # noqa: E402

EPILOG = """\
input JSON keys (schema_version must be 1):
  verification_id, claim_id, method   required non-empty strings
  refinements       required list, 2-1000 objects: resolution (finite, > 0),
                    estimate (finite); optional error (finite, >= 0; when omitted it is
                    |estimate - reference_value| if reference_value is set, else unset),
                    residual (optional; absolute value), invariants (optional object:
                    name -> finite deviation)
  reference_value   optional finite number; default: none
  thresholds        optional object; each threshold is checked only when set:
                    max_residual, max_invariant_deviation, minimum_order (no default);
                    max_cross_method_z (default 3.0, must be > 0); other keys are refused
  solver            optional object: precision (absence is a minor finding);
                    absolute_tolerance or relative_tolerance (absence of both is a minor finding);
                    a finite absolute_tolerance is the noise floor: an observed order computed
                    from an error or successive difference at or below it is a major finding
  cross_method      optional list of at most 100 {method (non-empty), estimate (finite),
                    uncertainty (finite; sign ignored)}; every pair is compared and
                    difference_from_first is recorded against the first entry; default: none

An explicit error differing from |estimate - reference_value| by more than a relative
1e-9 and more than four ulps of the operands is a major finding.
Derived errors, successive differences or observed orders that overflow are refused.
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", type=Path, help="verification JSON object (format below)")
    parser.add_argument("--output", type=Path, required=True, help="output JSON path; overwritten with the audited result")
    parser.add_argument("--require-clean", action="store_true", help="exit 1 unless status is 'passed' (default: exit 0)")
    args = parser.parse_args()
    try:
        result = run_numerical_verification(load_json_object(args.input))
        write_json_atomic(args.output, result)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Success! Data written to: {args.output.resolve()}")
    return 1 if args.require_clean and result["status"] != "passed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
