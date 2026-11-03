#!/usr/bin/env python3
"""Analyze binder sequences and supplied matched selectivity panels."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from codex_science.binder_developability import analyze_binder_developability


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
        def invalid_constant(value):
            raise ValueError(f"nonfinite JSON: {value}")
        payload = json.loads(args.input.read_text(encoding="utf-8"), object_pairs_hook=unique_pairs,
                             parse_constant=invalid_constant)
        result = analyze_binder_developability(payload)
        encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False, ensure_ascii=True)
    except (OSError, ValueError, TypeError, OverflowError) as error:
        print(json.dumps({"status": "error", "error": str(error)}, ensure_ascii=True))
        return 1
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
