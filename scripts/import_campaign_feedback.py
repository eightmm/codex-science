#!/usr/bin/env python3
"""Join assay CSV outcomes and compute a bounded next-candidate proposal."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from codex_science.campaign_execution import read_json
from codex_science.campaign_feedback import import_assay_feedback


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", type=Path)
    parser.add_argument("measurements", type=Path)
    args = parser.parse_args()
    try:
        result = import_assay_feedback(read_json(args.contract), args.measurements.read_text(encoding="utf-8"))
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as error:
        print(json.dumps({"status": "error", "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
