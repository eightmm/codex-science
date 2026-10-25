#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.collaboration import diff_runs  # noqa: E402

def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two run manifests and report changed artifacts, claims, environment and code.")
    parser.add_argument("previous", type=Path, help="earlier run manifest JSON: artifacts[] entries need path and sha256; claims[] are matched by id; run_id, environment and code are also read")
    parser.add_argument("current", type=Path, help="later run manifest JSON, same format as previous")
    parser.add_argument("--output", type=Path, help="write the diff report JSON to this path instead of stdout")
    args = parser.parse_args()
    report = diff_runs(json.loads(args.previous.read_text()), json.loads(args.current.read_text()))
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output: args.output.write_text(text, encoding="utf-8")
    else: print(text, end="")
    return 0
if __name__ == "__main__": raise SystemExit(main())
