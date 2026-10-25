#!/usr/bin/env python3
"""Search a bounded domain for a counterexample without promoting a test to proof."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.cli_io import load_json_object, write_json_atomic  # noqa: E402
from codex_science.safe_expression import search_counterexample  # noqa: E402


EPILOG = """\
input JSON keys (schema_version must be 1):
  claim_id, statement      required non-empty strings
  scope                    finite or general (default general); finite enables the
                           exhaustive finite-domain result path
  variables                required non-empty list of {name (unique identifier), and
                           exactly one domain key:
                             values: non-empty list of finite numbers or booleans
                             integer_range: {start, stop (required integers),
                               step (default 1, nonzero); stop is included}
                             float_grid: {start, stop (required finite numbers),
                               count (required integer >= 2); both ends included}}
  assumptions              optional list of expressions; default: empty list
  conclusion               required expression to test
  max_evaluations          optional, 1-1000000; default 100000
  expressions use the safe_expression grammar: arithmetic, comparisons, and/or,
  conditional expressions, and whitelisted functions over the variable names
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", type=Path, help="counterexample-search JSON object (format below)")
    parser.add_argument("--output", type=Path, required=True, help="output JSON path; overwritten with the search result")
    args = parser.parse_args()
    try:
        result = search_counterexample(load_json_object(args.input))
        write_json_atomic(args.output, result)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Success! Data written to: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
