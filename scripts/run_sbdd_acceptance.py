#!/usr/bin/env python3
from __future__ import annotations
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.sbdd_execution import execute_acceptance  # noqa: E402

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--registry", type=Path, default=ROOT / "models" / "registry-v2.json")
    args = parser.parse_args()
    print(execute_acceptance(args.input.resolve(), args.output.resolve(), registry_path=args.registry.resolve()))
    return 0
if __name__ == "__main__": raise SystemExit(main())
