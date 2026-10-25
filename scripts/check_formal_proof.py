#!/usr/bin/env python3
"""Preview or execute a bounded Lean kernel proof check and emit a receipt."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.cli_io import load_json_object, write_json_atomic  # noqa: E402
from codex_science.formal_proof import run_formal_proof_check  # noqa: E402


EPILOG = """\
input JSON keys (schema_version must be 1):
  check_id, receipt_id, claim_id, statement, theorem_file
                           required non-empty strings; theorem_file is a relative
                           path to a .lean file inside --workspace (no '..', not absolute)
  assumptions              optional list of strings; default: empty list
  timeout_seconds          optional integer, 1-600; default 120
  command_mode             optional: auto (default), lean, or lake. auto selects
                           'lake env lean' when the workspace has lakefile.lean,
                           lakefile.toml, or lake-manifest.json, otherwise 'lean'.
                           If the selected tool is missing, status is 'unavailable';
                           auto never falls back from lake to lean.
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", type=Path, help="proof-check JSON object (format below)")
    parser.add_argument("--workspace", type=Path, required=True, help="workspace directory that contains theorem_file")
    parser.add_argument("--output", type=Path, required=True, help="output receipt JSON path; overwritten")
    parser.add_argument("--preview", action="store_true", help="write a preview (status 'preview') with the resolved command, without running Lean/Lake")
    parser.add_argument("--require-passed", action="store_true", help="exit 1 unless status is 'passed' (default: exit 0)")
    args = parser.parse_args()
    try:
        result = run_formal_proof_check(
            load_json_object(args.input),
            workspace=args.workspace,
            execute=not args.preview,
        )
        write_json_atomic(args.output, result)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Success! Data written to: {args.output.resolve()}")
    return 1 if args.require_passed and result.get("status") != "passed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
