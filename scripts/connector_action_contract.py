#!/usr/bin/env python3
"""Validate connector action specs/previews and issue hash-bound approvals."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.action_connectors import ActionSpec, build_action_approval, validate_preview  # noqa: E402


def read_object(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Success! Data written to: {path.resolve()}")


def validate_spec(args: argparse.Namespace) -> None:
    spec = ActionSpec.from_payload(read_object(args.spec))
    write(args.output, {"schema_version": 1, "status": "valid", "action_spec_sha256": spec.fingerprint, "spec": spec.to_dict()})


def validate_preview_command(args: argparse.Namespace) -> None:
    preview = read_object(args.preview)
    spec = None if args.spec is None else ActionSpec.from_payload(read_object(args.spec))
    validate_preview(preview, spec)
    write(args.output, {"schema_version": 1, "status": "valid", "preview_id": preview["preview_id"], "preview_fingerprint": preview["fingerprint"]})


def approve(args: argparse.Namespace) -> None:
    preview = read_object(args.preview)
    write(args.output, build_action_approval(preview, approved_by=args.approved_by, approved_scopes=args.scope))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("validate-spec")
    command.add_argument("spec", type=Path)
    command.add_argument("--output", type=Path, required=True)
    command.set_defaults(handler=validate_spec)
    command = commands.add_parser("validate-preview")
    command.add_argument("preview", type=Path)
    command.add_argument("--spec", type=Path)
    command.add_argument("--output", type=Path, required=True)
    command.set_defaults(handler=validate_preview_command)
    command = commands.add_parser("approve")
    command.add_argument("preview", type=Path)
    command.add_argument("--approved-by", required=True)
    command.add_argument("--scope", action="append", required=True)
    command.add_argument("--output", type=Path, required=True)
    command.set_defaults(handler=approve)
    args = parser.parse_args()
    try:
        args.handler(args)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
