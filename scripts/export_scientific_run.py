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
    parser.add_argument("output", type=Path, help="export directory (created if absent); writes ro-crate-metadata.json, prov.json, scientific-bom.json and export-receipt.json; "
        "existing export files are refused, so choose a new versioned directory; must not overlap the manifest, listed artifacts or descriptor files")
    parser.add_argument("--receipt", type=Path, required=True, help="separate output file for the receipt JSON: exports[] with name, path, sha256 and size_bytes; "
        "an existing file or directory is refused (choose a new path); must be outside the export directory, "
        "with no ancestor/descendant overlap with export outputs, including aliases")
    args = parser.parse_args()
    try:
        export_run(args.manifest, args.output, receipt_path=args.receipt)
    except RecursionError:
        print("error: manifest or export data is nested too deeply to process", file=sys.stderr)
        return 1
    except RuntimeError as error:
        print(f"error: symlink loop or runtime failure while resolving paths: {error}", file=sys.stderr)
        return 1
    except TypeError as error:
        print(f"error: manifest contains a value of an unexpected type: {error}", file=sys.stderr)
        return 1
    except (OSError, ValueError, json.JSONDecodeError) as error:
        try:
            run_dir = args.manifest.resolve().parent
        except RuntimeError:
            run_dir = args.manifest.parent
        print(f"error: {error}{digest_mismatch_hint(error, run_dir)}", file=sys.stderr)
        return 1
    print(f"Success! Export written to: {args.output.resolve()}")
    print(f"Success! Receipt written to: {args.receipt.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
