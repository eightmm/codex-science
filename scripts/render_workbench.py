#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.run_packaging import digest_mismatch_hint  # noqa: E402
from codex_science.workbench import write_workbench  # noqa: E402

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or args.manifest.parent / "workbench.html"
    try:
        write_workbench(args.manifest.resolve(), output.resolve())
    except ValueError as error:
        print(f"error: {error}{digest_mismatch_hint(error, args.manifest.resolve().parent)}", file=sys.stderr)
        return 1
    print(output.resolve())
    return 0
if __name__ == "__main__": raise SystemExit(main())
