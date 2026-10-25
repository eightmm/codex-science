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


JOB_SPEC_EPILOG = """\
job spec JSON:
  required:
    backend          "local" or "slurm"
    name             non-empty string
    command          non-empty list of argv strings
    working_directory  existing directory
  optional (default):
    schema_version   1 (only 1 is accepted)
    environment      {} object; values are stored as strings; keys containing
                     token, secret, password, credential, private_key, api_key
                     or apikey are rejected
    inherit_environment  true
    inputs           [] list of objects: id (default input-<index>);
                     path (relative, no "..") or identifier (required when
                     path is absent); sha256 and root_sha256 (64-hex digests)
    outputs          [] relative paths
    checkpoint_paths []  relative paths
    resources        {cpus 1, memory_mb 1024, gpus 0, gpu_type null,
                     wall_time_seconds 3600, partition null, account null,
                     qos null}; cpus, memory_mb, wall_time_seconds >= 1, gpus >= 0
    timeout_seconds  3600 (>= 1)
    cost_cap         null, or a number >= 0
    approval_required  true unless backend is local
    scientific_run_id  null or string
    source_snapshot  null, or exactly {"mode": "git-archive",
                     "commit": 40- or 64-hex Git object ID}
"""


def _subparser(subcommands, name: str, help_text: str, *, spec: bool = False) -> argparse.ArgumentParser:
    options = {"epilog": JOB_SPEC_EPILOG, "formatter_class": argparse.RawDescriptionHelpFormatter} if spec else {}
    return subcommands.add_parser(name, help=help_text, **options)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True, help="durable state directory; job records and logs are kept under <state-dir>/jobs")
    subcommands = parser.add_subparsers(dest="command", required=True)

    command = _subparser(subcommands, "preflight", "Check a job spec and write a preflight report", spec=True)
    command.add_argument("--spec", type=Path, required=True, help="job spec JSON (format below)")
    command.add_argument("--output", type=Path, required=True, help="output path for the preflight report JSON")
    command.set_defaults(handler=command_preflight)

    command = _subparser(subcommands, "approve", "Write an approval receipt bound to a job spec fingerprint")
    command.add_argument("--spec", type=Path, required=True, help="job spec JSON to approve")
    command.add_argument("--approved-by", required=True, help="non-empty approver name recorded in the receipt")
    command.add_argument("--target", required=True, help="execution target stored verbatim in the receipt (submit does not compare it)")
    command.add_argument("--output", type=Path, required=True, help="output path for the approval receipt JSON")
    command.set_defaults(handler=command_approve)

    command = _subparser(subcommands, "render-slurm", "Render a Slurm batch script without submitting it", spec=True)
    command.add_argument("--spec", type=Path, required=True, help="job spec JSON (format below)")
    command.add_argument("--job-id", default="preview", help="job ID for the script's log paths: letters, digits, '-' and '_' only (default: preview)")
    command.add_argument("--output", type=Path, required=True, help="output path for the rendered script")
    command.set_defaults(handler=command_render_slurm)

    command = _subparser(subcommands, "submit", "Submit a job spec to the local or Slurm backend", spec=True)
    command.add_argument("--spec", type=Path, required=True, help="job spec JSON (format below)")
    command.add_argument(
        "--approval",
        type=Path,
        help="approval receipt JSON from approve; required for slurm and whenever approval_required is true; "
        "its job_spec_sha256 and backend must match the spec",
    )
    command.add_argument("--output", type=Path, required=True, help="output path for the submission record JSON")
    command.set_defaults(handler=command_submit)

    for name, handler, help_text in (
        ("status", command_status, "Print the current state of a job"),
        ("cancel", command_cancel, "Cancel a running or queued job"),
        ("collect", command_collect, "Collect the outputs and records of a job"),
    ):
        command = _subparser(subcommands, name, help_text)
        command.add_argument("--backend", choices=["local", "slurm"], required=True, help="backend that ran the job")
        command.add_argument("--job-id", required=True, help="job ID returned by submit")
        command.add_argument("--output", type=Path, required=True, help="output path for the result JSON")
        command.set_defaults(handler=handler)

    command = _subparser(subcommands, "wait", "Block until a local job finishes or the timeout expires")
    command.add_argument("--backend", choices=["local", "slurm"], required=True, help="backend that ran the job (only local is supported)")
    command.add_argument("--job-id", required=True, help="job ID returned by submit")
    command.add_argument("--timeout", type=float, required=True, help="maximum wait in seconds; must be positive")
    command.add_argument("--poll", type=float, default=0.2, help="polling interval in seconds; must be positive (default: 0.2)")
    command.add_argument("--output", type=Path, required=True, help="output path for the result JSON")
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
