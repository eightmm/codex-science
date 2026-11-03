#!/usr/bin/env python3
"""Validate a public variant evidence dossier offline; never attest clinical validity."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.cli_io import preflight_output_paths, write_json_atomic  # noqa: E402
from codex_science.variant_dossier import validate_variant_dossier  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path, help="directory containing dossier.json and its hash-bound artifacts")
    parser.add_argument("--output", type=Path, help="atomically write validation JSON outside the dossier")
    parser.add_argument("--require-clean", action="store_true", help="require a valid evidence-only dossier (invalid input always exits 1)")
    args = parser.parse_args()
    try:
        preflight_output_paths(args.output, inputs=[path for path in args.package.rglob("*") if path.is_file()],
                               protected_dirs=[args.package])
        report = validate_variant_dossier(args.package)
        if args.output is not None:
            write_json_atomic(args.output, report)
    except (OSError, ValueError, RuntimeError, RecursionError) as error:
        print(f"variant-dossier-refused: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
