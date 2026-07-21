#!/usr/bin/env python3
"""Generate a non-active skill draft from a currently passed scientific run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.pipeline_compiler import compile_pipeline_draft  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--name", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--commands", type=Path, help="JSON array of argv arrays")
    parser.add_argument("--limitation", action="append", default=[])
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        commands = None
        if args.commands:
            payload = json.loads(args.commands.read_text(encoding="utf-8"))
            if not isinstance(payload, list):
                raise ValueError("--commands must contain a JSON array")
            commands = payload
        receipt = compile_pipeline_draft(
            manifest_path=args.manifest,
            output_dir=args.output,
            name=args.name,
            description=args.description,
            command_contract=commands,
            limitations=args.limitation or None,
        )
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Success! Draft written to: {args.output.resolve()}")
    print(f"Success! Receipt written to: {args.receipt.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
