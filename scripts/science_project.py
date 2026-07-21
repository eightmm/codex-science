#!/usr/bin/env python3
"""Manage a local project evidence store over immutable Codex Science runs.

Every subcommand writes its result to --output. The merge-plan command is
non-executing and never mutates imported run bundles.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.project_store import ProjectStore  # noqa: E402


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Success! Data written to: {path.resolve()}")


def _json_object(value: str, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError(f"{label} must be valid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def create(args: argparse.Namespace) -> None:
    store = ProjectStore(args.database)
    _write(args.output, store.create_project(project_id=args.project_id, title=args.title, question=args.question))


def import_run(args: argparse.Namespace) -> None:
    store = ProjectStore(args.database)
    record = store.import_run(project_id=args.project_id, manifest_path=args.manifest, branch_name=args.branch, parent_run_id=args.parent_run)
    _write(args.output, record.to_dict())


def fork(args: argparse.Namespace) -> None:
    store = ProjectStore(args.database)
    _write(args.output, store.fork_branch(project_id=args.project_id, source_run_id=args.source_run, branch_name=args.branch))


def assertion(args: argparse.Namespace) -> None:
    store = ProjectStore(args.database)
    payload = store.add_assertion(
        project_id=args.project_id,
        run_id=args.run_id,
        claim_id=args.claim_id,
        source_id=args.source_id,
        polarity=args.polarity,
        locator=_json_object(args.locator, "--locator"),
        independence_group=args.independence_group,
        effect_measure=args.effect_measure,
        estimate=args.estimate,
        interval_low=args.interval_low,
        interval_high=args.interval_high,
        unit=args.unit,
        sample_size=args.sample_size,
        population=args.population,
        risk_of_bias_ref=args.risk_of_bias_ref,
    )
    _write(args.output, payload)


def compare(args: argparse.Namespace) -> None:
    store = ProjectStore(args.database)
    _write(args.output, store.compare_runs(project_id=args.project_id, previous_run_id=args.previous_run, current_run_id=args.current_run))


def merge_plan(args: argparse.Namespace) -> None:
    store = ProjectStore(args.database)
    _write(args.output, store.prepare_merge_plan(project_id=args.project_id, source_branch=args.source_branch, target_branch=args.target_branch))


def summary(args: argparse.Namespace) -> None:
    store = ProjectStore(args.database)
    _write(args.output, store.summary(project_id=args.project_id))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    subcommands = parser.add_subparsers(dest="command", required=True)

    command = subcommands.add_parser("init", help="Initialize a project")
    command.add_argument("--project-id", required=True)
    command.add_argument("--title", required=True)
    command.add_argument("--question", required=True)
    command.add_argument("--output", type=Path, required=True)
    command.set_defaults(handler=create)

    command = subcommands.add_parser("import-run", help="Validate and import an immutable run")
    command.add_argument("--project-id", required=True)
    command.add_argument("--manifest", type=Path, required=True)
    command.add_argument("--branch", required=True)
    command.add_argument("--parent-run")
    command.add_argument("--output", type=Path, required=True)
    command.set_defaults(handler=import_run)

    command = subcommands.add_parser("fork", help="Fork a project branch from an imported run")
    command.add_argument("--project-id", required=True)
    command.add_argument("--source-run", required=True)
    command.add_argument("--branch", required=True)
    command.add_argument("--output", type=Path, required=True)
    command.set_defaults(handler=fork)

    command = subcommands.add_parser("assert", help="Add a quantitative, located evidence assertion")
    command.add_argument("--project-id", required=True)
    command.add_argument("--run-id", required=True)
    command.add_argument("--claim-id", required=True)
    command.add_argument("--source-id", required=True)
    command.add_argument("--polarity", choices=["supports", "contradicts", "qualifies", "neutral", "unavailable"], required=True)
    command.add_argument("--locator", required=True, help="JSON object with artifact path/hash and an exact locator")
    command.add_argument("--independence-group", required=True)
    command.add_argument("--effect-measure")
    command.add_argument("--estimate", type=float)
    command.add_argument("--interval-low", type=float)
    command.add_argument("--interval-high", type=float)
    command.add_argument("--unit")
    command.add_argument("--sample-size", type=int)
    command.add_argument("--population")
    command.add_argument("--risk-of-bias-ref")
    command.add_argument("--output", type=Path, required=True)
    command.set_defaults(handler=assertion)

    command = subcommands.add_parser("compare", help="Compare two imported run manifests")
    command.add_argument("--project-id", required=True)
    command.add_argument("--previous-run", required=True)
    command.add_argument("--current-run", required=True)
    command.add_argument("--output", type=Path, required=True)
    command.set_defaults(handler=compare)

    command = subcommands.add_parser("merge-plan", help="Prepare a non-executing scientific merge plan")
    command.add_argument("--project-id", required=True)
    command.add_argument("--source-branch", required=True)
    command.add_argument("--target-branch", required=True)
    command.add_argument("--output", type=Path, required=True)
    command.set_defaults(handler=merge_plan)

    command = subcommands.add_parser("summary", help="Summarize project lineage and event-chain state")
    command.add_argument("--project-id", required=True)
    command.add_argument("--output", type=Path, required=True)
    command.set_defaults(handler=summary)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.handler(args)
    except (OSError, ValueError, sqlite3.Error if False else ValueError) as error:  # type: ignore[misc]
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
