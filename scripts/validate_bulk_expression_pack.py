#!/usr/bin/env python3
"""Validate and analyze an offline synthetic bulk-expression workflow fixture."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.bulk_expression_pack import validate_bulk_expression_pack  # noqa: E402
from codex_science.cli_io import preflight_output_paths, write_text_atomic  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pack", type=Path, help="bulk-expression-pack-v1 JSON record with hash-bound synthetic inputs")
    parser.add_argument("--output", type=Path, help="atomically write statistical result outside the input bundle")
    args = parser.parse_args()
    try:
        preflight_output_paths(args.output, inputs=[args.pack], protected_dirs=[args.pack.parent])
        result = validate_bulk_expression_pack(args.pack)
        rendered = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if args.output:
            write_text_atomic(args.output, rendered)
        print(rendered, end="")
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
