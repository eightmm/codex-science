#!/usr/bin/env python3
"""Plan or explicitly execute short local stages with resumable handoffs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from codex_science.campaign_execution import read_json, run_campaign


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--state-dir", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--wait-seconds", type=float, default=10)
    args = parser.parse_args()
    try:
        result = run_campaign(read_json(args.input), args.workspace, args.state_dir,
                              execute=args.execute, retry_failed=args.retry_failed,
                              wait_seconds=args.wait_seconds)
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        return 0 if result["status"] in {"planned", "completed"} else 2
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as error:
        print(json.dumps({"status": "error", "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
