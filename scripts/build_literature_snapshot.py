#!/usr/bin/env python3
"""Build snapshot.current.json from a literature run's registers."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.literature_snapshot_build import build_literature_snapshot  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True,
                        help="run directory with protocol.json, queries.jsonl, studies.json and claims.json (screening.json is used if present)")
    parser.add_argument("--output", default="snapshot.current.json",
                        help="snapshot path inside the run directory (default: %(default)s)")
    parser.add_argument("--protocol-id", help="stable protocol identifier when protocol.json has no protocol_id")
    args = parser.parse_args(argv)
    try:
        result = build_literature_snapshot(args.run_dir, args.output, protocol_id=args.protocol_id)
    except (ValueError, OSError, RuntimeError, UnicodeError, TypeError, KeyError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
