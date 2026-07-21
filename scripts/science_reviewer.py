#!/usr/bin/env python3
"""Prepare a blinded review packet or finalize a hash-covered review response."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.reviewer_runtime import build_review_packet, finalize_review_response  # noqa: E402


def read_object(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Success! Data written to: {path.resolve()}")


def prepare(args: argparse.Namespace) -> None:
    packet = build_review_packet(
        args.manifest,
        review_modes=args.mode,
        independent_required=not args.independence_not_required,
        review_questions=args.question or None,
    )
    write(args.output, packet)


def finalize(args: argparse.Namespace) -> None:
    packet = read_object(args.packet)
    response = read_object(args.response)
    write(args.output, finalize_review_response(packet, response))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("prepare")
    command.add_argument("manifest", type=Path)
    command.add_argument("--mode", action="append", choices=["record", "source", "method", "reproduction"], required=True)
    command.add_argument("--question", action="append", default=[])
    command.add_argument("--independence-not-required", action="store_true")
    command.add_argument("--output", type=Path, required=True)
    command.set_defaults(handler=prepare)
    command = commands.add_parser("finalize")
    command.add_argument("packet", type=Path)
    command.add_argument("response", type=Path)
    command.add_argument("--output", type=Path, required=True)
    command.set_defaults(handler=finalize)
    args = parser.parse_args()
    try:
        args.handler(args)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
