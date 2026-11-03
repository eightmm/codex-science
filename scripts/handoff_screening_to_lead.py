#!/usr/bin/env python3
"""Join a frozen screening record to a declared follow-up selection contract."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from codex_science.campaign_execution import read_json
from codex_science.campaign_handoffs import screening_to_lead


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("screening", type=Path)
    parser.add_argument("handoff", type=Path)
    args = parser.parse_args()
    try:
        result = screening_to_lead(read_json(args.screening), read_json(args.handoff))
        output = json.dumps(result, indent=2, sort_keys=True, allow_nan=False)
    except (ValueError, TypeError, KeyError, OSError, OverflowError) as error:
        print(json.dumps({"status": "error", "error": str(error)}))
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
