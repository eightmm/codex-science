#!/usr/bin/env python3
"""Capture executable/asset file identities and compare a prior capture."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from codex_science.campaign_execution import capture_runtime_identity, compare_runtime_identities, read_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable")
    parser.add_argument("--assets", type=Path, help="JSON object mapping model/database names to file paths")
    parser.add_argument("--previous", type=Path)
    args = parser.parse_args()
    try:
        identity = capture_runtime_identity(args.executable, read_json(args.assets) if args.assets else {})
        result = {"identity": identity}
        if args.previous:
            result["comparison"] = compare_runtime_identities(read_json(args.previous)["identity"], identity)
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as error:
        print(json.dumps({"status": "error", "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
