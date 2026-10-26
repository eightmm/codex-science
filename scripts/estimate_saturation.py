#!/usr/bin/env python3
"""Estimate literature discovery saturation from JSON input."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.cli_io import write_json_atomic
from codex_science.literature_saturation import estimate_saturation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="JSON file or - for stdin: a list of cumulative {\"evaluated\", \"relevant\"} checkpoints, or a saturation-log-v1 object with \"checkpoints\" and optional hard_cap, remaining_threshold, min_evaluated")
    parser.add_argument("--hard-cap", type=int,
                        help="stop once this many records are evaluated (positive integer; required here or as hard_cap in the input)")
    parser.add_argument("--remaining-threshold", type=float,
                        help="predicted remaining relevant records at or below which to stop (default: 1.0)")
    parser.add_argument("--min-evaluated", type=int,
                        help="minimum evaluated records before fitting (default: 30)")
    parser.add_argument("--output", help="also write the result JSON atomically to this path; untouched on error (exit 2)")
    args = parser.parse_args()
    try:
        raw = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, dict):
            if data.get("schema") not in (None, "saturation-log-v1"):
                raise ValueError("unsupported input schema")
            params = data
            data = params.get("checkpoints")
        else:
            params = {}
        hard_cap = args.hard_cap if args.hard_cap is not None else params.get("hard_cap")
        threshold = args.remaining_threshold if args.remaining_threshold is not None else params.get("remaining_threshold", 1.0)
        minimum = args.min_evaluated if args.min_evaluated is not None else params.get("min_evaluated", 30)
        result = estimate_saturation(data, hard_cap=hard_cap,
                                     remaining_threshold=threshold, min_evaluated=minimum)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError, ArithmeticError, RecursionError) as exc:
        print(json.dumps({"schema": "saturation-estimate-error-v1",
                          "error": {"code": "invalid_request", "message": str(exc)}}, sort_keys=True))
        return 2
    if args.output:
        try:
            write_json_atomic(Path(args.output), result)
        except OSError as exc:
            print(json.dumps({"schema": "saturation-estimate-error-v1",
                              "error": {"code": "output_write_failed",
                                        "message": f"cannot write {args.output}: {exc}"}}, sort_keys=True))
            return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
