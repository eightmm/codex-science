#!/usr/bin/env python3
"""Validate offline experiment-design pack artifacts without writing inputs."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.experiment_design_pack import validate_experiment_design_pack  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="experiment-design-pack-v1 JSON; artifact paths are relative to it")
    parser.add_argument("--mode", choices=("preregister", "audit"), default="preregister", help="preregister before collection, audit finished analysis and preserve all deviations")
    args = parser.parse_args()
    try:
        result = validate_experiment_design_pack(args.input, mode=args.mode)
    except (OSError, ValueError, RecursionError, RuntimeError) as error:
        print(f"error: experiment-design-pack: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
