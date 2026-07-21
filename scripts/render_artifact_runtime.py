#!/usr/bin/env python3
"""Describe, render, select, or propose changes to a scientific artifact.

This CLI always writes structured output to a file. It never mutates the source
artifact and never executes a transform proposal.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.artifact_runtime import (  # noqa: E402
    build_selection,
    build_transform_proposal,
    describe_runtime,
    render_runtime_html,
    validate_runtime_descriptor,
    validate_selection,
)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Success! Data written to: {path.resolve()}")


def _json_argument(value: str, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError(f"{label} must be valid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def command_describe(args: argparse.Namespace) -> None:
    descriptor = describe_runtime(
        args.artifact,
        artifact_path=args.artifact_path,
        artifact_sha256=args.sha256,
        kind=args.kind,
        artifact_type=args.artifact_type,
        media_type=args.media_type,
        max_bytes=args.max_bytes,
        max_records=args.max_records,
    )
    _write_json(args.output, descriptor.to_dict())


def command_render(args: argparse.Namespace) -> None:
    descriptor = _read_json(args.descriptor)
    validate_runtime_descriptor(descriptor)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_runtime_html(descriptor, title=args.title), encoding="utf-8")
    print(f"Success! Runtime view written to: {args.output.resolve()}")


def command_select(args: argparse.Namespace) -> None:
    descriptor = _read_json(args.descriptor)
    selection = build_selection(
        descriptor,
        selector_type=args.selector_type,
        selector=_json_argument(args.selector, "--selector"),
        selected_by=args.selected_by,
        reason=args.reason,
        label=args.label,
    )
    _write_json(args.output, selection)


def command_propose(args: argparse.Namespace) -> None:
    selection = _read_json(args.selection)
    validate_selection(selection)
    proposal = build_transform_proposal(
        selection,
        operation=args.operation,
        parameters=_json_argument(args.parameters, "--parameters"),
        reason=args.reason,
        affected_steps=args.affected_step,
        expected_outputs=args.expected_output,
        proposed_by=args.proposed_by,
        requires_approval=not args.no_approval_required,
        approval_boundary=args.approval_boundary,
    )
    _write_json(args.output, proposal)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)

    describe = subcommands.add_parser("describe", help="Build a bounded runtime descriptor")
    describe.add_argument("artifact", type=Path)
    describe.add_argument("--artifact-path", required=True, help="Run-relative artifact path")
    describe.add_argument("--sha256", help="Expected manifest SHA-256")
    describe.add_argument("--kind", required=True)
    describe.add_argument("--artifact-type", default="file")
    describe.add_argument("--media-type")
    describe.add_argument("--max-bytes", type=int, required=True)
    describe.add_argument("--max-records", type=int, required=True)
    describe.add_argument("--output", type=Path, required=True)
    describe.set_defaults(handler=command_describe)

    render = subcommands.add_parser("render", help="Render a validated offline HTML view")
    render.add_argument("descriptor", type=Path)
    render.add_argument("--title")
    render.add_argument("--output", type=Path, required=True)
    render.set_defaults(handler=command_render)

    select = subcommands.add_parser("select", help="Create a typed hash-bound selection")
    select.add_argument("descriptor", type=Path)
    select.add_argument("--selector-type", required=True)
    select.add_argument("--selector", required=True, help="JSON object")
    select.add_argument("--selected-by", required=True)
    select.add_argument("--reason", required=True)
    select.add_argument("--label", default="")
    select.add_argument("--output", type=Path, required=True)
    select.set_defaults(handler=command_select)

    propose = subcommands.add_parser("propose", help="Create a non-executing transform proposal")
    propose.add_argument("selection", type=Path)
    propose.add_argument("--operation", required=True)
    propose.add_argument("--parameters", required=True, help="JSON object")
    propose.add_argument("--reason", required=True)
    propose.add_argument("--affected-step", action="append", required=True)
    propose.add_argument("--expected-output", action="append", default=[])
    propose.add_argument("--proposed-by", required=True)
    propose.add_argument("--approval-boundary", default="artifact mutation and rerun")
    propose.add_argument("--no-approval-required", action="store_true")
    propose.add_argument("--output", type=Path, required=True)
    propose.set_defaults(handler=command_propose)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.handler(args)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
