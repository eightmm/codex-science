#!/usr/bin/env python3
"""Allocate literature candidates across uncovered mechanism families."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.cli_io import load_json_object, write_json_atomic  # noqa: E402
from codex_science.method_landscape import allocate_methods  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="method-landscape-v1 JSON")
    parser.add_argument("--output", required=True, type=Path, help="allocation artifact path")
    args = parser.parse_args()
    try:
        result = allocate_methods(load_json_object(args.input))
        write_json_atomic(args.output, result)
    except (OSError, UnicodeError, ValueError, RecursionError) as error:
        parser.error(str(error))
    print(json.dumps({"selected": len(result["selected"]), "clusters": len(result["clusters"]),
                      "screened_out": len(result["screened_out"]), "output": str(args.output)},
                     ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
