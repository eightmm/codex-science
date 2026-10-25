#!/usr/bin/env python3
"""Check equation dimensions and perform bounded SI unit conversions."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.cli_io import load_json_object, write_json_atomic  # noqa: E402
from codex_science.units_runtime import run_dimension_check  # noqa: E402


EPILOG = """\
input JSON keys (schema_version must be 1):
  check_id, claim_id       required non-empty strings
  variables                required non-empty object {identifier: unit expression};
                           a unit expression combines built-in unit symbols
                           (for example m, s, kg) with *, /, and ^ (max 256 characters)
  equations                optional list of {id (default equation-N, N = list index),
                           left, right}. left and right are required non-empty
                           expressions over the variable names (not unit symbols),
                           using +, -, *, /, ^ or **, numeric constants, unary +/-,
                           sqrt, abs, and exp/log/log10/sin/cos/tan (dimensionless
                           argument). + and - need equal dimensions. An unknown name,
                           invalid syntax, or unequal dimensions is reported as a
                           critical dimension-mismatch finding.
  conversions              optional list of {id (default conversion-N), value
                           (required number), from, to (built-in unit symbols)}.
                           A failed conversion is a major unit-conversion-failed finding.
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", type=Path, help="dimension-check JSON object (format below)")
    parser.add_argument("--output", type=Path, required=True, help="output JSON path; overwritten with the check result")
    parser.add_argument("--require-clean", action="store_true", help="exit 1 unless status is 'passed' (default: exit 0)")
    args = parser.parse_args()
    try:
        result = run_dimension_check(load_json_object(args.input))
        write_json_atomic(args.output, result)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Success! Data written to: {args.output.resolve()}")
    return 1 if args.require_clean and result["status"] != "passed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
