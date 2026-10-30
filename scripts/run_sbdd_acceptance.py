#!/usr/bin/env python3
from __future__ import annotations
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.cli_io import resolve_input_path  # noqa: E402
from codex_science.sbdd_execution import execute_acceptance  # noqa: E402

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--registry", type=Path, default=ROOT / "models" / "registry-v2.json")
    args = parser.parse_args()
    try:
        manifest_path = execute_acceptance(resolve_input_path(args.input), resolve_input_path(args.output), registry_path=resolve_input_path(args.registry))
    except (ValueError, OSError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(manifest_path)
    return 0
if __name__ == "__main__": raise SystemExit(main())
