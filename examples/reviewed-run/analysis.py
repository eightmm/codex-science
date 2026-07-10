"""Deterministic example analysis for the Codex Science artifact contract."""

from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    n = 5
    observed = sum(value * value for value in range(1, n + 1)) / n
    expected = (n + 1) * (2 * n + 1) / 6
    result = {
        "expected_mean_square": expected,
        "matches_formula": observed == expected,
        "n": n,
        "observed_mean_square": observed,
    }
    output = Path(__file__).with_name("result.json")
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"mean_square={observed} expected={expected} match={observed == expected}")


if __name__ == "__main__":
    main()
