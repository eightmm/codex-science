#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.collaboration import diff_runs  # noqa: E402

def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two run manifests and report added, removed and changed artifacts, claims and inputs, environment and code changes, and review invalidation (including input changes). Invalid manifests exit 1 with an error message.")
    parser.add_argument("previous", type=Path, help="earlier run manifest JSON object: artifacts[] need unique non-empty string path and non-empty string sha256; claims[] need unique non-empty string id; inputs[] use the first non-empty string identifier, id, query_id, url or path as a unique identity, otherwise the SHA-256 of canonical JSON (sorted keys, compact separators, UTF-8); identical unidentified inputs collapse, edits appear as removed and added; run_id, environment and code are also read")
    parser.add_argument("current", type=Path, help="later run manifest JSON, same format as previous")
    parser.add_argument("--output", type=Path, help="write the diff report JSON to this path instead of stdout")
    args = parser.parse_args()
    try:
        report = diff_runs(json.loads(args.previous.read_text(encoding="utf-8")),
                           json.loads(args.current.read_text(encoding="utf-8")))
        text = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.output: args.output.write_text(text, encoding="utf-8")
        else: print(text, end="")
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0
if __name__ == "__main__": raise SystemExit(main())
