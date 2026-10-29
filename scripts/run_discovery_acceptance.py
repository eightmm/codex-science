#!/usr/bin/env python3
"""Run deterministic, CPU-only Research Discovery Loop acceptance fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.discovery import attach_cycle  # noqa: E402
from codex_science.discovery_design import audit_design  # noqa: E402
from codex_science.research_cycle import apply_cycle_event, load_cycle, new_cycle, save_cycle  # noqa: E402
from codex_science.checkpoints import advance_checkpoint, create_checkpoint, heartbeat_checkpoint  # noqa: E402
from codex_science.artifacts import validate_bundle  # noqa: E402
from codex_science.cli_io import write_json_atomic  # noqa: E402


EVALUATOR_SOURCE = ROOT / "examples" / "research-discovery" / "toy_evaluator.py"
INPUT = ROOT / "examples" / "research-discovery" / "input.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _ref(root: Path, path: Path) -> dict[str, str]:
    return {"path": str(path.relative_to(root)), "sha256": _sha256(path)}


def _toy_module() -> ModuleType:
    module = ModuleType("rdl_acceptance_toy")
    source = EVALUATOR_SOURCE.read_bytes()
    exec(compile(source, str(EVALUATOR_SOURCE), "exec"), module.__dict__)
    return module


def _experiment_by_id(cycle: dict[str, Any], experiment_id: str) -> dict[str, Any]:
    return next(item for item in cycle["experiments"] if item["id"] == experiment_id)


def _method_by_id(cycle: dict[str, Any], method_id: str) -> dict[str, Any]:
    return next(item for item in cycle["methods"] if item["id"] == method_id)


def _run_evaluator(
    root: Path, evaluator: Path, candidate: Path, cycle: dict[str, Any], experiment_id: str,
) -> tuple[dict[str, Any], Path, Path]:
    experiment = _experiment_by_id(cycle, experiment_id)
    method = _method_by_id(cycle, experiment["method_id"])
    code_refs = method["code_refs"]
    candidate_ref = _ref(root, candidate)
    if code_refs != [candidate_ref]:
        raise ValueError("candidate source does not exactly match the reserved method code reference")
    evaluation_refs = cycle["evaluation"]["artifact_refs"]
    if evaluation_refs != [_ref(root, evaluator)]:
        raise ValueError("protected evaluator does not exactly match the frozen evaluation reference")
    receipt = root / "evidence" / f"{candidate.stem}-receipt.json"
    receipt.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(evaluator), "--candidate", str(candidate), "--output", str(receipt)]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    if not receipt.is_file():
        raise RuntimeError(f"evaluator did not write a receipt (exit {completed.returncode}): {completed.stderr}")
    result = json.loads(receipt.read_text(encoding="utf-8"))
    if result.get("candidate_sha256") != candidate_ref["sha256"]:
        raise RuntimeError("measurement receipt candidate hash does not match the reserved method")
    measurement_refs = [_ref(root, receipt)]
    _write_json(
        root / "evidence" / f"{candidate.stem}-execution.json",
        {
            "schema_version": 1,
            "experiment_id": experiment_id,
            "experiment_fingerprint": experiment["fingerprint"],
            "method_id": method["id"],
            "code_refs": code_refs,
            "evaluation_refs": evaluation_refs,
            "measurement_refs": measurement_refs,
            "exit_code": completed.returncode,
            "command": command,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        },
    )
    expected = 0 if result["status"] == "completed" else 2
    if completed.returncode != expected:
        raise RuntimeError("evaluator exit status disagrees with its receipt")
    return result, receipt, root / "evidence" / f"{candidate.stem}-execution.json"


def _base_cycle(
    root: Path, *, name: str, method_id: str, candidate: Path, evaluator: Path, budget: float,
    baseline_predictions: dict[str, list[float]] | None = None,
) -> dict[str, Any]:
    return new_cycle(
        {
            "problem": {
                "observed": "A magnitude-only predictor is at chance on held-out paired signed samples.",
                "interpreted": "The result may reflect lost sign information rather than insufficient capacity.",
                "current_method": "Fit frozen ridge least squares on a candidate representation of the signed scalar input.",
                "unexplained": "Whether capacity can recover labels after sign is removed is unresolved by the baseline result.",
                "assumptions": [
                    {
                        "id": "paired-labels",
                        "statement": "For each held-out magnitude, the protected dataset contains opposite signed inputs with opposite labels.",
                        "category": "data",
                        "status": "inherited",
                    },
                    {
                        "id": "frozen-protocol",
                        "statement": "The recorded evaluator source fixes the train/test split, ridge fit, pair control, and held-out accuracy measurement.",
                        "category": "evaluation",
                        "status": "tested",
                        "evidence_refs": [_ref(root, evaluator)],
                    },
                ],
            },
            "design_policy": "required-for-reservation",
            "evaluation": {
                "evaluator": "frozen toy_evaluator.py",
                "baseline": "magnitude-only representation",
                "split": "train magnitudes 1-4; held-out paired magnitudes 5-6",
                "primary_metric": {"name": "held_out_accuracy", "direction": "maximize", "json_pointer": "/primary_accuracy"},
                "threshold": {"op": ">", "value": 0.75},
                "budget": budget,
                "budget_rule": "Each reserved experiment costs one deterministic CPU evaluation.",
                "artifact_refs": [_ref(root, evaluator)],
            },
            "hypotheses": [
                {
                    "id": "information-loss",
                    "statement": "Removing sign makes balanced opposite-label pairs indistinguishable.",
                    "conditions": "The held-out pairs share a magnitude representation and have opposite labels.",
                    "falsifier": "A magnitude-only candidate exceeds the paired information bound.",
                },
                {
                    "id": "capacity-only",
                    "statement": "More magnitude-only nonlinear features recover the held-out labels.",
                    "conditions": "Capacity changes while the input representation remains magnitude-only.",
                    "falsifier": "The capacity candidate remains at the paired information bound.",
                },
            ],
            "methods": [_method(root, method_id, candidate, "Candidate representation fit by frozen ridge least squares.")],
            "experiments": [_experiment(
                "baseline-evaluation", method_id, "baseline or capacity candidate",
                baseline_predictions or {"information-loss": [0.45, 0.55], "capacity-only": [0.85, 1.05]},
            )],
        }
    )


def _method(root: Path, ident: str, candidate: Path, definition: str) -> dict[str, Any]:
    if ident in {"baseline", "capacity"}:
        representation = (
            "Map x to abs(x), with capacity adding powers abs(x)^1 through abs(x)^4; both deliberately discard sign."
            if ident == "capacity" else "Map x to the one-dimensional magnitude feature abs(x), deliberately discarding sign."
        )
        prediction = (
            "If capacity-only is adequate, the four magnitude powers exceed the frozen threshold; "
            "if information is lost, paired opposite signs remain indistinguishable at 0.5 accuracy."
            if ident == "capacity" else "Both explanations permit the baseline to remain at the paired 0.5 information bound."
        )
        difference = (
            "Adds magnitude-only nonlinear features without restoring the sign variable."
            if ident == "capacity" else "Uses the declared magnitude-only baseline representation."
        )
    elif ident in {"directional", "repaired"}:
        representation = "Map x to the signed scalar x, preserving the direction that magnitude-only candidates remove."
        prediction = "The information-loss explanation predicts that restoring sign separates held-out opposite-label pairs and raises accuracy; capacity-only predicts no such representation-specific gain."
        difference = "Replaces magnitude-only features with the signed input while retaining the frozen ridge evaluator and split."
    else:  # The broken source intentionally exercises implementation-failure classification.
        representation = "Attempt to return one numeric feature, but this candidate intentionally returns NaN to test repair handling."
        prediction = "No hypothesis prediction is interpreted unless the candidate passes the finite-feature invariant and produces a protected measurement."
        difference = "Exercises the same proposed representation boundary with a deliberately invalid numerical implementation."
    code_refs = [_ref(root, candidate)]
    return {
        "id": ident,
        "definition": definition,
        "code_refs": code_refs,
        "correctness_checks": ["candidate source hash recorded", "protected evaluator receipt has actual predictions"],
        "design": {
            "hypothesis_ids": ["information-loss", "capacity-only"],
            "assumption_ids": ["paired-labels", "frozen-protocol"],
            "operator": "representation",
            "inputs": "A signed scalar x from the protected paired dataset.",
            "outputs": "A finite feature tuple consumed by the frozen ridge least-squares fit.",
            "computation": representation,
            "invariants": [
                "The candidate returns a non-empty finite numeric tuple with a consistent width.",
                "The protected evaluator retains its paired held-out split, ridge procedure, and accuracy metric.",
            ],
            "complexity": "O(n d^2 + d^3) for n protected samples and d candidate features in the fixed ridge solver.",
            "failure_modes": [
                "Non-finite or inconsistent candidate features are an implementation failure, not evidence against either hypothesis.",
                "Magnitude-only features can retain the paired information bound even when d increases.",
            ],
            "applicability": "The finite paired signed toy evaluated by the recorded protected evaluator.",
            "predictions": prediction,
            "baseline_difference": difference,
            "implementation": {"code_refs": code_refs},
            "correctness_refs": code_refs,
        },
    }


def _experiment(ident: str, method_id: str, label: str, predictions: dict[str, list[float]]) -> dict[str, Any]:
    return {
        "id": ident,
        "method_id": method_id,
        "state": "planned",
        "cost": 1.0,
        "predictions": predictions,
        "resolution": 0.001,
        "controls": ["held-out opposite-sign pairs", "frozen split and metric", label],
    }


def _persist(root: Path, cycle: dict[str, Any]) -> dict[str, Any]:
    save_cycle(cycle, root)
    return load_cycle(root)


def _execute_and_complete(root: Path, cycle: dict[str, Any], experiment_id: str, request_id: str, evaluator: Path, candidate: Path) -> tuple[dict[str, Any], dict[str, Any], Path]:
    cycle = _persist(root, apply_cycle_event(cycle, {"kind": "reserve", "experiment_id": experiment_id, "request_id": request_id}, root))
    cycle = _persist(root, apply_cycle_event(cycle, {"kind": "running", "experiment_id": experiment_id, "request_id": request_id}, root))
    receipt, receipt_path, execution_path = _run_evaluator(root, evaluator, candidate, cycle, experiment_id)
    if receipt["status"] != "completed":
        cycle = _persist(root, apply_cycle_event(cycle, {
            "kind": "failure", "experiment_id": experiment_id, "request_id": request_id,
            "failure_kind": "implementation", "outcome": "Candidate failed; no scientific hypothesis was assessed.",
            "evidence_refs": [_ref(root, receipt_path), _ref(root, execution_path)],
        }, root))
        return cycle, receipt, receipt_path
    cycle = _persist(root, apply_cycle_event(cycle, {
        "kind": "complete", "experiment_id": experiment_id, "request_id": request_id,
        "outcome": f"{receipt['primary_metric']['name']} measured from actual held-out predictions.",
        "observations": [{"artifact_ref": _ref(root, receipt_path), "json_pointer": "/primary_accuracy", "value": receipt["primary_accuracy"]}],
        "execution_refs": [_ref(root, execution_path)],
    }, root))
    return cycle, receipt, receipt_path


def _prepare(root: Path, name: str) -> tuple[Path, ModuleType]:
    root.mkdir(parents=True, exist_ok=False)
    evaluator = root / "protected" / "toy_evaluator.py"
    evaluator.parent.mkdir()
    shutil.copyfile(EVALUATOR_SOURCE, evaluator)
    _write_json(root / "input.json", json.loads(INPUT.read_text(encoding="utf-8")))
    return evaluator, _toy_module()


def _finish(root: Path, cycle: dict[str, Any]) -> dict[str, Any]:
    cycle = _persist(root, cycle)
    manifest = attach_cycle(root)
    manifest["environment"] = {"python": sys.version.split()[0], "compute": "local deterministic CPU"}
    manifest["executions"] = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((root / "evidence").glob("*-execution.json"))
    ]
    write_json_atomic(root / "manifest.json", manifest)
    validate_bundle(manifest, root)
    from codex_science.artifacts import add_artifact
    from codex_science.discovery_evidence import assess_cycle, cycle_graph
    from codex_science.discovery_synthesis import summarize_cycle

    views = {"design-audit": audit_design(cycle, root), "next": summarize_cycle(cycle, root),
             "graph": cycle_graph(cycle, root), "assessment": assess_cycle(cycle, root)}
    for name, payload in views.items():
        path = root / "discovery" / f"{name}.json"
        _write_json(path, payload)
        ref = _ref(root, path)
        add_artifact(manifest, ref["path"], kind="discovery-view", sha256=ref["sha256"])
    write_json_atomic(root / "manifest.json", manifest)
    validate_bundle(manifest, root)
    rows = [
        "# Research Discovery acceptance run", "",
        f"Status: `{cycle['status']}`. Independent review: **pending**.", "",
        "| Experiment | State | Effect | Support |", "| --- | --- | --- | --- |",
    ]
    for experiment in cycle["experiments"]:
        rows.append(f"| {experiment['id']} | {experiment['state']} | {experiment.get('method_effect', 'not assessed')} | {json.dumps(experiment.get('explanation_support', {}), sort_keys=True)} |")
    rows.extend(["", "Evidence and immutable revision snapshots are registered in `manifest.json`."])
    rows.extend(["", "## Development views", "",
                 "[Method design audit](discovery/design-audit.json) · [Evidence and next action](discovery/next.json) · "
                 "[Prediction graph](discovery/graph.json) · [Review axes](discovery/assessment.json)"])
    (root / "index.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    checkpoint = advance_checkpoint(root, completed_step="compute", next_step="independent-review", next_action="Obtain independent review; the current manifest is pending review.")
    return {"cycle": cycle, "manifest": manifest, "checkpoint": checkpoint}


def _start_checkpoint(root: Path) -> None:
    session_key = hashlib.sha256(f"rdl-acceptance:{root.name}".encode("utf-8")).hexdigest()
    create_checkpoint(
        root, goal="Run the deterministic discovery acceptance fixture", deliverable="A review-pending immutable run bundle",
        done_criteria=["Record protected evaluations", "Leave independent review pending"],
        steps=[("compute", "Run protected evaluator"), ("independent-review", "Obtain independent review")],
        next_action="Run the first protected evaluator scenario.", session_key=session_key,
    )
    heartbeat_checkpoint(root, next_action="Initial immutable cycle snapshot is recorded.", progress_ref="discovery/revisions/000001.json")


def _initialize(root: Path, cycle: dict[str, Any]) -> dict[str, Any]:
    """Keep the generated, runnable initialization contract beside its run."""
    audit = audit_design(cycle, root)
    if not audit["problem_ready"] or not all(item["implementation_ready"] for item in audit["methods"]):
        raise ValueError("acceptance cycle must carry a complete strict computational design")
    _write_json(root / "cycle-input.json", cycle)
    cycle = _persist(root, cycle)
    _start_checkpoint(root)
    return cycle


def _capacity_revision(output: Path) -> dict[str, Any]:
    root = output / "capacity-revision"
    evaluator, toy = _prepare(root, "capacity-revision")
    baseline = root / "models" / "capacity.py"
    baseline.parent.mkdir()
    toy.write_candidate(baseline, "capacity")
    cycle = _base_cycle(root, name="capacity-revision", method_id="capacity", candidate=baseline, evaluator=evaluator, budget=2.0)
    cycle = _initialize(root, cycle)
    cycle, first, _ = _execute_and_complete(root, cycle, "baseline-evaluation", "capacity-1", evaluator, baseline)
    directional = root / "models" / "directional.py"
    toy.write_candidate(directional, "directional")
    revision = {
        "kind": "revise", "source_experiment_id": "baseline-evaluation",
        "rationale": "The capacity observation was at the paired information bound, so preserve the result and add direction.",
        "lesson": {
            "observation": "The completed capacity candidate remained at the measured paired information bound on the frozen held-out split.",
            "interpretation": "Adding magnitude-only capacity did not separate opposite-sign pairs under this protected toy evaluation.",
            "limitation": "This finite toy does not establish a general mechanism outside its paired inputs, frozen ridge fit, and held-out metric.",
            "change": "Append a signed directional representation while retaining the evaluator, split, metric, and paired controls.",
            "next_test": "Measure the directional candidate once against the same frozen protected evaluator.",
        },
        "methods": [_method(root, "directional", directional, "Directional signed representation fit by frozen ridge least squares.")],
        "experiments": [_experiment(
            "directional-evaluation", "directional", "directional representation revision",
            {"information-loss": [0.95, 1.05], "capacity-only": [0.45, 0.55]},
        )],
        "hypotheses": [],
    }
    cycle = _persist(root, apply_cycle_event(cycle, revision, root))
    cycle, second, _ = _execute_and_complete(root, cycle, "directional-evaluation", "directional-1", evaluator, directional)
    cycle = apply_cycle_event(cycle, {"kind": "conclude", "status": "improved", "rationale": "The changed source hash added sign direction and measured higher held-out accuracy."}, root)
    result = _finish(root, cycle)
    return {"scenario": "capacity-revision", "first_accuracy": first["primary_accuracy"], "second_accuracy": second["primary_accuracy"], "changed_source_hash": first["candidate_sha256"] != second["candidate_sha256"], **result}


def _implementation_repair(output: Path) -> dict[str, Any]:
    root = output / "implementation-repair"
    evaluator, toy = _prepare(root, "implementation-repair")
    broken = root / "models" / "broken.py"
    broken.parent.mkdir()
    broken.write_text("def represent(x):\n    return (float('nan'),)\n", encoding="utf-8")
    cycle = _base_cycle(root, name="implementation-repair", method_id="broken", candidate=broken, evaluator=evaluator, budget=2.0)
    cycle = _initialize(root, cycle)
    cycle, failed, _ = _execute_and_complete(root, cycle, "baseline-evaluation", "broken-1", evaluator, broken)
    repaired = root / "models" / "repaired.py"
    toy.write_candidate(repaired, "directional")
    cycle = _persist(root, apply_cycle_event(cycle, {
        "kind": "revise", "source_experiment_id": "baseline-evaluation",
        "rationale": "The first run was an implementation failure, so it cannot reject either explanation; repair and rerun.",
        "lesson": {
            "observation": "The broken candidate returned a non-finite feature and the protected evaluator recorded an implementation failure.",
            "interpretation": "No hypothesis was assessed because the candidate violated the finite-feature invariant before a measurement was produced.",
            "limitation": "The failed run gives no comparative evidence about information loss or capacity under the protected metric.",
            "change": "Append a repaired signed representation with the same frozen evaluator and paired controls.",
            "next_test": "Measure the repaired candidate once and classify only its completed protected observation.",
        },
        "methods": [_method(root, "repaired", repaired, "Repaired directional signed representation.")],
        "experiments": [_experiment(
            "repaired-evaluation", "repaired", "repair after implementation failure",
            {"information-loss": [0.95, 1.05], "capacity-only": [0.45, 0.55]},
        )],
        "hypotheses": [],
    }, root))
    cycle, repaired_result, _ = _execute_and_complete(root, cycle, "repaired-evaluation", "repaired-1", evaluator, repaired)
    cycle = apply_cycle_event(cycle, {"kind": "conclude", "status": "improved", "rationale": "Only the repaired, completed evaluation supports the observed improvement."}, root)
    result = _finish(root, cycle)
    return {"scenario": "implementation-repair", "failed_status": failed["status"], "failed_science_conclusion": failed["science_conclusion"], "repaired_accuracy": repaired_result["primary_accuracy"], **result}


def _budget_overlap_inconclusive(output: Path) -> dict[str, Any]:
    root = output / "budget-overlap-inconclusive"
    evaluator, toy = _prepare(root, "budget-overlap-inconclusive")
    baseline = root / "models" / "baseline.py"
    baseline.parent.mkdir()
    toy.write_candidate(baseline, "baseline")
    cycle = _base_cycle(
        root, name="budget-overlap-inconclusive", method_id="baseline", candidate=baseline, evaluator=evaluator, budget=1.0,
        baseline_predictions={"information-loss": [0.4, 0.6], "capacity-only": [0.4, 0.6]},
    )
    # This fixture deliberately starts with overlapping predictions, so no
    # explanation wins even before budget prevents a non-overlapping follow-up.
    cycle = _initialize(root, cycle)
    cycle, receipt, _ = _execute_and_complete(root, cycle, "baseline-evaluation", "budget-1", evaluator, baseline)
    overlap = {
        "candidate_sha256": receipt["candidate_sha256"],
        "decision": "not_scheduled",
        "reason": "The proposed repeat has the same source hash and frozen split/metric, and the budget is exhausted.",
        "remaining_budget": 0.0,
    }
    _write_json(root / "evidence" / "overlap-decision.json", overlap)
    cycle = apply_cycle_event(cycle, {
        "kind": "conclude", "status": "inconclusive", "rationale": "The measured accuracy lies in overlapping prediction intervals; the fixed budget prevents a discriminating follow-up.",
        "evidence_refs": [_ref(root, root / "evidence" / "overlap-decision.json")],
    }, root)
    result = _finish(root, cycle)
    return {"scenario": "budget-overlap-inconclusive", "accuracy": receipt["primary_accuracy"], "overlap": overlap, **result}


def run_acceptance(output_dir: str | Path) -> dict[str, Any]:
    """Materialize three independently review-pending deterministic run bundles."""
    output = Path(output_dir).resolve()
    if output.exists():
        raise ValueError(f"output directory already exists: {output}")
    output.mkdir(parents=True)
    scenarios = [_capacity_revision(output), _implementation_repair(output), _budget_overlap_inconclusive(output)]
    result = {
        "status": "completed",
        "review": "pending_independent_review",
        "scenarios": [
            {key: value for key, value in scenario.items() if key not in {"cycle", "manifest"}}
            for scenario in scenarios
        ],
    }
    _write_json(output / "acceptance.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    try:
        result = run_acceptance(args.output_dir)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
