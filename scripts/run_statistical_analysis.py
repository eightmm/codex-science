#!/usr/bin/env python3
"""Run bounded effect-size, bootstrap, and randomization-based inference."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.cli_io import load_json_object, write_json_atomic  # noqa: E402
from codex_science.statistics_runtime import run_statistical_analysis  # noqa: E402


EPILOG = """\
input JSON keys (schema_version must be 1):
  analysis_id, claim_id, design_id   required non-empty strings
  seed                     required integer (bool rejected); no default
  group_labels             required list of exactly two distinct non-empty labels
  data                     required non-empty list, up to 100000 objects:
                           group (must be one of group_labels), value (finite number),
                           unit_id (optional, default row-N; empty string rejected),
                           pair_id (required when analysis_type is paired)
  analysis_type            independent (default) or paired
  estimand                 mean-difference (default) or median-difference
  alternative              two-sided (default), greater, or less
  within_unit_aggregation  mean (default) or median
  confidence_level         optional, in (0.5, 1); default 0.95
  bootstrap_replicates     optional, 200-100000; default 5000
  permutation_replicates   optional, 200-100000; default 10000
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", type=Path, help="analysis JSON object (format below)")
    parser.add_argument("--output", type=Path, required=True, help="output JSON path; overwritten with the analysis result")
    args = parser.parse_args()
    try:
        result = run_statistical_analysis(load_json_object(args.input))
        write_json_atomic(args.output, result)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Success! Data written to: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
