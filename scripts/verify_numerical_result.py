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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-clean", action="store_true")
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
