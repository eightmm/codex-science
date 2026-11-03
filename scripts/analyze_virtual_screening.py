#!/usr/bin/env python3
"""Print offline virtual-screening analysis as JSON; never execute docking."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from codex_science.virtual_screening import analyze_screening


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    try:
        def unique_pairs(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError(f"duplicate JSON key: {key}")
                result[key] = value
            return result
        payload = json.loads(args.input.read_text(encoding="utf-8"), object_pairs_hook=unique_pairs)
        result = analyze_screening(payload)
    except (OSError, ValueError, TypeError, OverflowError) as error:
        print(json.dumps({"status": "error", "error": str(error)}, ensure_ascii=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
