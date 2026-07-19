#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.literature_v2 import resolve_study_families  # noqa: E402

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("records", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.records.read_text())
    records = payload.get("studies", payload) if isinstance(payload, dict) else payload
    report = {"schema_version": 1, "families": resolve_study_families(records)}
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output: args.output.write_text(text, encoding="utf-8")
    else: print(text, end="")
    return 0
if __name__ == "__main__": raise SystemExit(main())
