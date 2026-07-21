#!/usr/bin/env python3
"""Submit, inspect, cancel, and collect durable local or Slurm jobs.

Non-local submission requires an explicit approval receipt produced by the
`approve` subcommand. Scientific completion must still be established by the
run's metrics, claims, provenance, and review.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.compute_backends import (  # noqa: E402
    LocalBackend,
    SlurmBackend,
    backend_for,
    build_approval_receipt,
    load_spec,
)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Success! Data written to: {path.resolve()}")


def command_preflight(args: argparse.Namespace) -> None:
    spec = load_spec(args.spec)
    _write(args.output, backend_for(spec.backend, args.state_dir).preflight(spec))


def command_approve(args: argparse.Namespace) -> None:
    spec = load_spec(args.spec)
    receipt = build_approval_receipt(spec, approved_by=args.approved_by, target=args.target)
    _write(args.output, receipt)


def command_render_slurm(args: argparse.Namespace) -> None:
    spec = load_spec(args.spec)
    backend = SlurmBackend(args.state_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(backend.render_script(spec, job_id=args.job_id), encoding="utf-8")
    print(f"Success! Slurm script written to: {args.output.resolve()}")


def command_submit(args: argparse.Namespace) -> None:
    spec = load_spec(args.spec)
    approval = None if args.approval is None else _read_json(args.approval)
    _write(args.output, backend_for(spec.backend, args.state_dir).submit(spec, approval=approval))


def command_status(args: argparse.Namespace) -> None:
    _write(args.output, backend_for(args.backend, args.state_dir).status(args.job_id))


def command_wait(args: argparse.Namespace) -> None:
    if args.backend != "local":
        raise ValueError("wait is currently supported by the durable local backend; poll Slurm with status")
    _write(args.output, LocalBackend(args.state_dir).wait(args.job_id, timeout_seconds=args.timeout, poll_seconds=args.poll))


def command_cancel(args: argparse.Namespace) -> None:
    _write(args.output, backend_for(args.backend, args.state_dir).cancel(args.job_id))


def command_collect(args: argparse.Namespace) -> None:
    _write(args.output, backend_for(args.backend, args.state_dir).collect(args.job_id))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True)
    subcommands = parser.add_subparsers(dest="command", required=True)

    command = subcommands.add_parser("preflight")
    command.add_argument("--spec", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    command.set_defaults(handler=command_preflight)

    command = subcommands.add_parser("approve")
    command.add_argument("--spec", type=Path, required=True)
    command.add_argument("--approved-by", required=True)
    command.add_argument("--target", required=True)
    command.add_argument("--output", type=Path, required=True)
    command.set_defaults(handler=command_approve)

    command = subcommands.add_parser("render-slurm")
    command.add_argument("--spec", type=Path, required=True)
    command.add_argument("--job-id", default="preview")
    command.add_argument("--output", type=Path, required=True)
    command.set_defaults(handler=command_render_slurm)

    command = subcommands.add_parser("submit")
    command.add_argument("--spec", type=Path, required=True)
    command.add_argument("--approval", type=Path)
    command.add_argument("--output", type=Path, required=True)
    command.set_defaults(handler=command_submit)

    for name, handler in (("status", command_status), ("cancel", command_cancel), ("collect", command_collect)):
        command = subcommands.add_parser(name)
        command.add_argument("--backend", choices=["local", "slurm"], required=True)
        command.add_argument("--job-id", required=True)
        command.add_argument("--output", type=Path, required=True)
        command.set_defaults(handler=handler)

    command = subcommands.add_parser("wait")
    command.add_argument("--backend", choices=["local", "slurm"], required=True)
    command.add_argument("--job-id", required=True)
    command.add_argument("--timeout", type=float, required=True)
    command.add_argument("--poll", type=float, default=0.2)
    command.add_argument("--output", type=Path, required=True)
    command.set_defaults(handler=command_wait)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.handler(args)
    except (OSError, ValueError, TimeoutError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
