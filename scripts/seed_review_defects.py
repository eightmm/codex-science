#!/usr/bin/env python3
"""Plant a known defect into a copy of a reviewed run bundle, or score reviewer responses against the hidden key."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.review_seeding import score, seed  # noqa: E402

EPILOG = """Examples:
  seed_review_defects.py seed --bundle RUN --spec spec.json --out SEEDED --key key.json
  seed_review_defects.py score --key key.json --response review.json

SPEC: {"schema_version":1,"defect_id","defect_class","file","find","replace",
"claim_id"?,"expected_min_severity":"major"|"critical"}; defect_class "control"
with no find/replace makes an unmodified copy. Keep --key outside --out.
Responses are reviewer-response JSON or review receipts with findings[].
One response per variant is a detection record, not a sensitivity estimate."""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    seeding = commands.add_parser("seed", help="copy a bundle, apply the spec replacement, refresh its manifest")
    seeding.add_argument("--bundle", type=Path, required=True, help="reviewed run bundle directory (not modified)")
    seeding.add_argument("--spec", type=Path, required=True, help="defect spec JSON")
    seeding.add_argument("--out", type=Path, required=True, help="new directory for the seeded copy; must not exist")
    seeding.add_argument("--key", type=Path, required=True, help="answer key JSON to write, outside --out")
    scoring = commands.add_parser("score", help="score reviewer responses against an answer key")
    scoring.add_argument("--key", type=Path, required=True, help="answer key written by seed")
    scoring.add_argument("--response", type=Path, action="append", required=True, help="reviewer response or review receipt JSON; repeatable")
    args = parser.parse_args()
    try:
        if args.command == "seed":
            result = seed(args.bundle, args.spec, args.out, args.key)
        else:
            result = score(args.key, args.response)
    except (OSError, ValueError) as error:
        print(f"seed_review_defects failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
