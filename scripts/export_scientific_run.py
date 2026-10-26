#!/usr/bin/env python3
"""Export a validated run as RO-Crate-oriented, PROV, and scientific-BOM metadata."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.fair_export import export_run  # noqa: E402
from codex_science.run_packaging import digest_mismatch_hint  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="run manifest JSON (schema_version 1 with run_id, question, plan, inputs, code, executions, environment, artifacts, claims, review); "
        "artifact files and sidecars are validated before export")
    parser.add_argument("output", type=Path, help="export directory (created if absent); writes ro-crate-metadata.json, prov.json and scientific-bom.json")
    parser.add_argument("--receipt", type=Path, required=True, help="output path for the receipt JSON: exports[] with name, path, sha256 and size_bytes")
    args = parser.parse_args()
    try:
        receipt = export_run(args.manifest, args.output)
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}{digest_mismatch_hint(error, args.manifest.resolve().parent)}", file=sys.stderr)
        return 1
    print(f"Success! Export written to: {args.output.resolve()}")
    print(f"Success! Receipt written to: {args.receipt.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
