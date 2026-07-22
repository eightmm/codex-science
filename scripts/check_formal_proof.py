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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--require-passed", action="store_true")
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
