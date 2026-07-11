#!/usr/bin/env python3
"""Validate an artifact manifest and optionally emit a record-based review."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.artifacts import validate_manifest  # noqa: E402
from codex_science.review import review_manifest  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--review-output", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    validate_manifest(manifest)
    print("artifact manifest: valid")
    if args.review_output:
        review = review_manifest(manifest)
        args.review_output.parent.mkdir(parents=True, exist_ok=True)
        args.review_output.write_text(
            json.dumps(review, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"artifact review: {review['status']}")


if __name__ == "__main__":
    main()
