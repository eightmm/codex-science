#!/usr/bin/env python3
"""Read one exported-series JSON record and emit JSON only."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from codex_science.trajectory_comparison import analyze_trajectory_comparison


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError(f"nonfinite JSON constant: {value}")


def main():
    try:
        if len(sys.argv) != 2:
            raise ValueError("usage: analyze_trajectory_comparison.py INPUT.json")
        result = analyze_trajectory_comparison(json.loads(
            Path(sys.argv[1]).read_text(), object_pairs_hook=_unique_object,
            parse_constant=_invalid_constant))
        output = json.dumps(result, allow_nan=False, sort_keys=True)
    except (ValueError, KeyError, TypeError, OSError, OverflowError) as error:
        print(json.dumps({"status": "invalid", "error": str(error)}))
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
