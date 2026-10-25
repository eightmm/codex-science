#!/usr/bin/env python3
"""Propagate correlated input uncertainty by linear and Monte Carlo methods."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.cli_io import load_json_object, write_json_atomic  # noqa: E402
from codex_science.uncertainty_runtime import run_uncertainty_propagation  # noqa: E402


EPILOG = """\
input JSON keys (schema_version must be 1):
  propagation_id, claim_id, expression   required non-empty strings;
                           expression uses the safe_expression grammar over the input names
  inputs                   required list, 1-64 objects: name (unique Python identifier),
                           mean (finite number), standard_uncertainty (finite; sign ignored),
                           unit (optional string, default null)
  covariance               optional list of {left, right, value}; left and right must be
                           input names; left == right must agree with standard_uncertainty;
                           default: no covariance
  method                   linear, monte-carlo, or both (default)
  seed                     integer; required (no default) for monte-carlo and both
  samples                  optional, 100-1000000; default 20000 (monte-carlo and both only)
  confidence_level         optional, in (0.5, 1); default 0.95
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", type=Path, help="propagation JSON object (format below)")
    parser.add_argument("--output", type=Path, required=True, help="output JSON path; overwritten with the propagation result")
    parser.add_argument("--require-clean", action="store_true", help="exit 1 unless status is 'passed' (default: exit 0)")
    args = parser.parse_args()
    try:
        result = run_uncertainty_propagation(load_json_object(args.input))
        write_json_atomic(args.output, result)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Success! Data written to: {args.output.resolve()}")
    return 1 if args.require_clean and result["status"] != "passed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
