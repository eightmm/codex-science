#!/usr/bin/env python3
"""Report evidence-count sufficiency for a validated research run."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.claim_sufficiency import check_sufficiency  # noqa: E402
from codex_science.run_packaging import _stage_file, digest_mismatch_hint  # noqa: E402


def emit(payload: str, output: str | None) -> None:
    if output:
        target = Path(output)
        staged = _stage_file(target, (payload + "\n").encode("utf-8"))
        try:
            os.replace(staged, target)
        finally:
            staged.unlink(missing_ok=True)
    print(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, help="validated research run directory")
    parser.add_argument("--tier", choices=("quick", "standard", "full"), required=True,
                        help="rigor tier setting the minimum independent supporting study groups per claim")
    parser.add_argument("--require-sufficient", action="store_true",
                        help="exit 1 if any claim is insufficient or has unresolved contradicting studies")
    parser.add_argument("--output", help="also write the result JSON atomically to this path; untouched when the run is invalid (exit 2)")
    args = parser.parse_args()
    try:
        result = check_sufficiency(args.run_dir, tier=args.tier)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError,
            KeyError, RecursionError, OverflowError) as error:
        print(json.dumps({"schema": "claim-sufficiency-error-v1",
                          "error": {"code": "invalid_run", "message": str(error) + digest_mismatch_hint(error, args.run_dir)}},
                         sort_keys=True, ensure_ascii=False, separators=(",", ":")))
        if args.output:
            print(f"note: {args.output} was not written because the run is invalid", file=sys.stderr)
        return 2
    try:
        emit(json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(",", ":")), args.output)
    except OSError as error:
        print(json.dumps({"schema": "claim-sufficiency-error-v1", "error": {"code": "output_write_failed",
                          "message": f"cannot write {args.output}: {error}"}}, sort_keys=True))
        return 2
    if args.require_sufficient and result["counts"]["insufficient"] + result["counts"]["contradicted_unresolved"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
