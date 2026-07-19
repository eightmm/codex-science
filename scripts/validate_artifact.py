#!/usr/bin/env python3
"""Validate an artifact bundle and optionally emit a record/source review."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.artifacts import validate_bundle  # noqa: E402
from codex_science.review import review_manifest  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--review-output", type=Path)
    parser.add_argument("--require-passed-review", action="store_true")
    args = parser.parse_args()
    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sidecars = validate_bundle(manifest, manifest_path.parent)
    print("artifact bundle: valid")
    if args.review_output:
        review = review_manifest(manifest, manifest_path.parent, sidecars=sidecars)
        args.review_output.parent.mkdir(parents=True, exist_ok=True)
        args.review_output.write_text(
            json.dumps(review, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"artifact review: {review['status']}")
        if args.require_passed_review and review["status"] != "passed":
            raise SystemExit("artifact review has unresolved findings")
    elif args.require_passed_review:
        raise SystemExit("--require-passed-review requires --review-output")


if __name__ == "__main__":
    main()
