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
from codex_science.cli_io import load_json_object, write_json_atomic  # noqa: E402


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


def discovery(args: argparse.Namespace) -> None:
    from codex_science.discovery import attach_cycle, finite_decision, plan_cycle
    from codex_science.experiment_planner import plan_discriminating_experiment
    from codex_science.research_cycle import apply_cycle_event, load_cycle, new_cycle, save_cycle

    action = args.discovery_command
    if args.output and getattr(args, "input", None) and args.output.resolve() == args.input.resolve():
        raise ValueError("--output cannot overwrite its input")
    if args.output and getattr(args, "input", None) and getattr(args, "run_dir", None):
        def protect_input_refs(value: Any) -> None:
            if isinstance(value, dict):
                if isinstance(value.get("path"), str) and "sha256" in value:
                    if (args.run_dir / value["path"]).resolve() == args.output.resolve():
                        raise ValueError("--output cannot overwrite referenced input evidence")
                for child in value.values():
                    protect_input_refs(child)
            elif isinstance(value, list):
                for child in value:
                    protect_input_refs(child)
        protect_input_refs(load_json_object(args.input))
    if args.output and getattr(args, "run_dir", None):
        root = args.run_dir.resolve()
        destination = args.output.resolve()
        if destination in {root / "manifest.json", root / "checkpoint.json"} or destination.is_relative_to(root / "discovery" / "revisions"):
            raise ValueError("--output cannot overwrite authoritative run state")
        manifest_path = root / "manifest.json"
        if manifest_path.exists():
            protected = {(root / item["path"]).resolve() for item in load_json_object(manifest_path)["artifacts"]}
            if destination in protected:
                raise ValueError("--output cannot overwrite a registered artifact")
    if action in {"history", "memory"}:
        if args.database is None:
            raise ValueError("--database is required for discovery history")
        result = ProjectStore(args.database).discovery_history(project_id=args.project_id, run_id=args.run_id)
        if action == "memory":
            from codex_science.discovery_synthesis import synthesize_history
            result = synthesize_history(result)
    elif action == "init":
        payload = load_json_object(args.input)
        if args.require_design:
            payload["design_policy"] = "required-for-reservation"
        cycle = new_cycle(payload)
        save_cycle(cycle, args.run_dir)
        attach_cycle(args.run_dir)
        result = load_cycle(args.run_dir)
    elif action == "event":
        cycle = load_cycle(args.run_dir)
        result = apply_cycle_event(cycle, load_json_object(args.input), run_dir=args.run_dir)
        save_cycle(result, args.run_dir)
        attach_cycle(args.run_dir)
        result = load_cycle(args.run_dir)
    elif action == "show":
        result = load_cycle(args.run_dir)
    elif action == "plan":
        result = (plan_cycle(load_cycle(args.run_dir), args.run_dir) if args.run_dir
                  else plan_discriminating_experiment(load_json_object(args.input)))
    elif action == "decision":
        result = finite_decision(load_cycle(args.run_dir), load_json_object(args.input), args.run_dir)
    elif action == "attach":
        result = attach_cycle(args.run_dir)
    elif action == "audit":
        from codex_science.discovery_design import audit_design
        result = audit_design(load_cycle(args.run_dir), args.run_dir)
    elif action == "next":
        from codex_science.discovery_synthesis import summarize_cycle
        result = summarize_cycle(load_cycle(args.run_dir), args.run_dir)
    elif action == "graph":
        from codex_science.discovery_evidence import cycle_graph
        result = cycle_graph(load_cycle(args.run_dir), args.run_dir)
    elif action == "assess":
        from codex_science.discovery_evidence import assess_cycle
        result = assess_cycle(load_cycle(args.run_dir), args.run_dir,
                              load_json_object(args.input) if args.input else None)
    elif action == "compare":
        from codex_science.discovery_comparison import evaluate_comparison
        payload = load_json_object(args.input)
        result = evaluate_comparison(payload.get("contract"), payload.get("records"), args.run_dir)
    else:
        raise ValueError(f"unknown discovery operation: {action}")
    if args.output:
        write_json_atomic(args.output, result)
        print(f"Success! Data written to: {args.output.resolve()}")
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    if action == "compare" and result["status"] != "passed":
        raise ValueError(f"comparison is {result['status']}; see the comparison report")


DISCOVERY_HELP = {
    "init": "Create a research cycle from a genesis JSON object",
    "event": "Append one transition event to a research cycle",
    "show": "Print the current research cycle",
    "plan": "Rank declared experiments by hypothesis separation (non-executing)",
    "decision": "Evaluate an explicit one-stage finite decision",
    "attach": "Register the research cycle in the run manifest",
    "history": "Print discovery history for a project (needs --database)",
    "audit": "Audit problem and method design completeness",
    "next": "Summarize the cycle state and next step",
    "graph": "Print the cycle evidence graph",
    "assess": "Project review coverage for the cycle",
    "memory": "Synthesize discovery history for a project (needs --database)",
    "compare": "Evaluate a matched-arm comparison contract and its records",
}

DISCOVERY_EPILOG = {
    "init": """\
--input: genesis cycle object (JSON).
  Required: problem (object with observed and interpreted text), evaluation (object),
    hypotheses, methods and experiments (lists of objects, each with a unique id).
  Optional: schema_version (default 1; only 1), status (default active; only active),
    events (default []; only []), design_policy (default legacy; legacy |
    required-for-reservation), problem.assumptions.
  Experiments must be planned and unobserved.
  Nested fields are validated by `science_project.py discovery init`; errors name the
  failing field.
--require-design: sets design_policy to required-for-reservation.
""",
    "event": """\
--input: one event object (JSON). kind selects the transition: reserve, running,
  ambiguous, complete, failure, propose, revise or conclude.
  reserve, running, ambiguous, complete, failure: experiment_id and request_id (text).
  complete: also outcome (text), observations (non-empty list) and execution_refs
    (non-empty list of {path, sha256}).
  failure: also outcome (text) and failure_kind (execution | implementation |
    measurement); evidence_refs is optional.
  propose, revise: rationale (text); optional append lists assumptions, hypotheses,
    methods and experiments. propose is rejected once any experiment is completed or
    failed. revise also needs source_experiment_id (a completed or failed experiment);
    lesson is optional, but when given needs observation, interpretation, limitation,
    change and next_test (text).
  revise under design_policy required-for-reservation: lesson is required, and at least
    one of assumptions, hypotheses, methods or experiments must be non-empty.
  conclude: status (improved | rejected | inconclusive) and rationale (text).
Nested fields are validated by `science_project.py discovery event`; errors name the
failing field.
""",
    "plan": """\
--input: plan object (JSON).
  Required: hypotheses (list of at least two objects with unique id), candidates
    (non-empty list of objects with unique id) and budget (number, not negative).
  Optional: policy (default discriminate_first_v1; only discriminate_first_v1).
  Nested fields are validated by `science_project.py discovery plan`; errors name the
  failing field.
--run-dir instead plans the research cycle's planned experiments.
""",
    "decision": """\
--input: decision object (JSON).
  Required: state_model_rationale (text), assumption_refs (non-empty list of
    {path, sha256} relative to --run-dir) and decision_contract (object).
  Optional: observed_outcome (object) with preregistered_decision_ref and artifact_ref
    (each {path, sha256}), cycle_experiment_id, decision_experiment_id and json_pointer.
  Nested fields are validated by `science_project.py discovery decision`; errors name
  the failing field.
""",
    "assess": """\
--input (optional): JSON object.
  Optional: review_refs (default []; list of {path, sha256} relative to --run-dir),
    novelty_comparison (object with scope, search_cutoff, difference and limitations
    text and a non-empty source_refs list of {path, sha256}).
  Supplied receipts apply to this view only.
""",
    "compare": """\
--input: JSON object with contract (object) and records (list).
  contract required keys: schema ("comparison-contract-v1"), arms (exactly
    ["ordinary", "prior", "rdl"]), synthetic (true or false), model, tools,
    arm_versions, tasks, seeds, repetitions, budget, preregistered_criteria,
    evaluation, evaluator_refs, evaluator_sha256 and contract_digest.
  Each task needs id, digest (canonical sha256 of spec) and spec.question.
  records: one object per grid cell, named by task_id, seed, arm and repetition.
  Nested fields are validated by `science_project.py discovery compare`; errors name
  the failing field.
  Status is passed, incomplete (cells missing, no errors) or rejected; any status
  other than passed exits with code 1.
""",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path,
                        help="SQLite project store path; required for project store commands and discovery history and memory")
    subcommands = parser.add_subparsers(dest="command", required=True)

    command = subcommands.add_parser("init", help="Initialize a project")
    command.add_argument("--project-id", required=True, help="project identifier; repeating init with the same title and question returns the existing project")
    command.add_argument("--title", required=True, help="human-readable project title")
    command.add_argument("--question", required=True, help="research question the project tracks")
    command.add_argument("--output", type=Path, required=True, help="JSON result path")
    command.set_defaults(handler=create)

    command = subcommands.add_parser("import-run", help="Validate and import an immutable run")
    command.add_argument("--project-id", required=True, help="project to import the run into")
    command.add_argument("--manifest", type=Path, required=True, help="run manifest.json path")
    command.add_argument("--branch", required=True, help="branch name to record the run on")
    command.add_argument("--parent-run", help="imported parent run ID (optional; defaults to the branch head when the branch exists)")
    command.add_argument("--output", type=Path, required=True, help="JSON result path")
    command.set_defaults(handler=import_run)

    command = subcommands.add_parser("fork", help="Fork a project branch from an imported run")
    command.add_argument("--project-id", required=True, help="project that holds the source run")
    command.add_argument("--source-run", required=True, help="imported run ID to fork from")
    command.add_argument("--branch", required=True, help="name of the new branch")
    command.add_argument("--output", type=Path, required=True, help="JSON result path")
    command.set_defaults(handler=fork)

    command = subcommands.add_parser("assert", help="Add a quantitative, located evidence assertion")
    command.add_argument("--project-id", required=True, help="project that holds the run")
    command.add_argument("--run-id", required=True, help="imported run ID that contains the source")
    command.add_argument("--claim-id", required=True, help="claim ID present in the imported run")
    command.add_argument("--source-id", required=True, help="source identifier stored with the assertion")
    command.add_argument("--polarity", choices=["supports", "contradicts", "qualifies", "neutral", "unavailable"], required=True,
                         help="how the located evidence bears on the claim")
    command.add_argument("--locator", required=True,
                         help='JSON object: artifact_path and artifact_sha256 (must match an imported artifact), plus at least one of '
                              "page, table, figure, cell, json_pointer, line_range, record_id")
    command.add_argument("--independence-group", required=True,
                         help="independence group label stored with the assertion (required)")
    command.add_argument("--effect-measure", help="effect measure name, for example risk ratio (optional)")
    command.add_argument("--estimate", type=float, help="point estimate of the effect (number, optional)")
    command.add_argument("--interval-low", type=float,
                         help="lower bound of the interval (number); give with --interval-high, and not above it")
    command.add_argument("--interval-high", type=float,
                         help="upper bound of the interval (number); give with --interval-low, and not below it")
    command.add_argument("--unit", help="unit of the estimate (optional)")
    command.add_argument("--sample-size", type=int, help="sample size behind the estimate (non-negative integer, optional)")
    command.add_argument("--population", help="population the estimate applies to (optional)")
    command.add_argument("--risk-of-bias-ref", help="risk-of-bias reference stored with the assertion (optional)")
    command.add_argument("--output", type=Path, required=True, help="JSON result path")
    command.set_defaults(handler=assertion)

    command = subcommands.add_parser("compare", help="Compare two imported run manifests")
    command.add_argument("--project-id", required=True, help="project that holds both runs")
    command.add_argument("--previous-run", required=True, help="imported run ID of the previous run")
    command.add_argument("--current-run", required=True, help="imported run ID of the current run")
    command.add_argument("--output", type=Path, required=True, help="JSON result path")
    command.set_defaults(handler=compare)

    command = subcommands.add_parser("merge-plan", help="Prepare a non-executing scientific merge plan")
    command.add_argument("--project-id", required=True, help="project that holds both branches")
    command.add_argument("--source-branch", required=True, help="branch to merge from")
    command.add_argument("--target-branch", required=True, help="branch to merge into")
    command.add_argument("--output", type=Path, required=True, help="JSON result path")
    command.set_defaults(handler=merge_plan)

    command = subcommands.add_parser("summary", help="Summarize project lineage and event-chain state")
    command.add_argument("--project-id", required=True, help="project to summarize")
    command.add_argument("--output", type=Path, required=True, help="JSON result path")
    command.set_defaults(handler=summary)

    command = subcommands.add_parser("discovery", help="Develop, record, and inspect a research cycle",
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog="Most operations take --run-dir and, where noted, --input (JSON file);\n"
                                            "history and memory take --project-id and need --database.\n"
                                            "Run `discovery <operation> --help` for that operation's input format.")
    operations = command.add_subparsers(dest="discovery_command", required=True)
    for action in ("init", "event", "show", "plan", "decision", "attach", "history",
                   "audit", "next", "graph", "assess", "memory", "compare"):
        operation = operations.add_parser(action, help=DISCOVERY_HELP[action], description=DISCOVERY_HELP[action],
                                          formatter_class=argparse.RawDescriptionHelpFormatter,
                                          epilog=DISCOVERY_EPILOG.get(action))
        if action not in {"history", "memory", "plan"}:
            operation.add_argument("--run-dir", type=Path, required=True,
                                   help="run directory of the research cycle (init creates the cycle)")
        if action == "plan":
            source = operation.add_mutually_exclusive_group(required=True)
            source.add_argument("--input", type=Path, help="plan object JSON (see epilog)")
            source.add_argument("--run-dir", type=Path, help="run directory whose research cycle is planned")
        if action in {"init", "event", "decision", "compare"}:
            operation.add_argument("--input", type=Path, required=True, help="input JSON object (see epilog)")
        if action == "assess":
            operation.add_argument("--input", type=Path, help="review receipts JSON object (optional, see epilog)")
        if action == "init":
            operation.add_argument("--require-design", action="store_true",
                                   help="set design_policy to required-for-reservation: reserve needs a complete design audit and revise follows strict rules")
        if action in {"history", "memory"}:
            operation.add_argument("--project-id", required=True, help="project to read history for")
            operation.add_argument("--run-id", help="restrict history to one imported run ID (optional)")
        operation.add_argument("--output", type=Path,
                               help="write the JSON result here instead of printing it; cannot overwrite inputs or run state")
        operation.set_defaults(handler=discovery)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command != "discovery" and args.database is None:
        parser.error("--database is required for project store commands")
    try:
        args.handler(args)
    except (OSError, ValueError, sqlite3.Error if False else ValueError) as error:  # type: ignore[misc]
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
