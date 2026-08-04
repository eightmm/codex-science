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
    write_json_atomic,
    write_text_atomic,
)
from codex_science.decision_analysis import (  # noqa: E402
    render_decision_analysis,
    run_decision_analysis,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        result = run_decision_analysis(load_json_object(args.input))
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
