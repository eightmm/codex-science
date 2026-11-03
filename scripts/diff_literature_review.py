#!/usr/bin/env python3
"""Diff two protocol-compatible literature review snapshots."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.cli_io import load_json_object, preflight_output_paths, write_text_atomic  # noqa: E402
from codex_science.literature import diff_review_snapshots  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("previous", type=Path, help="earlier literature review snapshot JSON (schema_version 1)")
    parser.add_argument("current", type=Path, help="later snapshot JSON with the same protocol_id")
    parser.add_argument("--output", type=Path, help="write the diff JSON here instead of stdout")
    args = parser.parse_args()
    try:
        preflight_output_paths(args.output, inputs=[args.previous, args.current])
        previous = load_json_object(args.previous)
        current = load_json_object(args.current)
        diff = diff_review_snapshots(previous, current)
        rendered = json.dumps(diff, indent=2, sort_keys=True) + "\n"
        if args.output:
            write_text_atomic(args.output, rendered)
    except (ValueError, OSError, UnicodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if not args.output:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
