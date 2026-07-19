#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.connector_contract import replay_snapshot  # noqa: E402

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.snapshot.read_text(encoding="utf-8"))
    result = replay_snapshot(payload)
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0
if __name__ == "__main__": raise SystemExit(main())
