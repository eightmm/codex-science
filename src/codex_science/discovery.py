"""Connect scientific cycle snapshots to existing run artifacts and project indexes."""
from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Any

from codex_science.artifact_store import stream_sha256
from codex_science.cli_io import load_json_object, write_json_atomic
from codex_science.runtime_identity import record_runtime_identity


def cycle_artifacts(manifest: dict[str, Any], run_dir: Path) -> list[dict[str, Any]]:
    """Validate the complete registered prefix, including links between snapshots."""
    records = [item for item in manifest["artifacts"] if item["kind"] == "research-cycle"]
    if not records:
        return []
    from codex_science.research_cycle import _confined_file, validate_cycle, validate_history
    cycles = []
    artifact_hashes = {item["path"]: item["sha256"].lower() for item in manifest["artifacts"]}

    def check_refs(value: Any) -> None:
        if isinstance(value, dict):
            if isinstance(value.get("path"), str) and "sha256" in value:
                if artifact_hashes.get(value["path"]) != value["sha256"]:
                    raise ValueError("research-cycle reference is not registered with its exact artifact hash")
            for child in value.values():
                check_refs(child)
        elif isinstance(value, list):
            for child in value:
                check_refs(child)

    for record in records:
        cycle = load_json_object(_confined_file(run_dir, record["path"]))
        validate_cycle(cycle, run_dir=run_dir)
        if record["path"] != f"discovery/revisions/{cycle['revision']:06d}.json":
            raise ValueError("research-cycle snapshot path does not match revision")
        check_refs(cycle)
        cycles.append(cycle)
    cycles.sort(key=lambda item: item["revision"])
    validate_history(cycles, run_dir=run_dir)
    return cycles


def attach_cycle(run_dir: Path) -> dict[str, Any]:
    """Recover a published snapshot into its manifest without fabricating review.

    The snapshot chain is the commit record. Repeating attachment after a crash
    before manifest replacement repairs that projection without a new experiment.
    Existing checkpoint ownership and lifecycle are intentionally untouched.
    """
    from codex_science.artifacts import add_artifact, new_manifest, validate_bundle, validate_manifest
    from codex_science.research_cycle import load_cycle

    run_dir = run_dir.resolve()
    cycle = load_cycle(run_dir)
    path = run_dir / "manifest.json"
    if path.is_symlink():
        raise ValueError("discovery manifest must not be a symlink")
    manifest = load_json_object(path) if path.exists() else new_manifest(
        run_dir.name,
        cycle["problem"]["observed"],
        [{"id": "discovery", "description": "Develop and test competing explanations", "status": "pending"}],
    )
    validate_manifest(manifest)
    existing = {item["path"]: item for item in manifest["artifacts"]}
    changed = False

    def register(relative: str, kind: str) -> None:
        nonlocal changed
        target = run_dir / relative
        if not target.resolve().is_relative_to(run_dir) or not target.is_file():
            raise ValueError(f"discovery evidence must stay in the run: {relative}")
        digest, _ = stream_sha256(target)
        previous = existing.get(relative)
        if previous:
            if previous["sha256"].lower() != digest:
                raise ValueError(f"registered discovery artifact changed: {relative}")
            if kind == "research-cycle" and previous["kind"] != kind:
                raise ValueError(f"research-cycle artifact kind mismatch: {relative}")
            return
        add_artifact(manifest, relative, kind=kind, sha256=digest)
        existing[relative] = manifest["artifacts"][-1]
        changed = True

    def references(value: Any) -> None:
        if isinstance(value, dict):
            if isinstance(value.get("path"), str) and "sha256" in value:
                register(value["path"], "discovery-evidence")
            for child in value.values():
                references(child)
        elif isinstance(value, list):
            for child in value:
                references(child)

    for revision in range(1, cycle["revision"] + 1):
        relative = f"discovery/revisions/{revision:06d}.json"
        register(relative, "research-cycle")
        references(load_json_object(run_dir / relative))
    if changed:
        manifest["review"] = {"status": "pending", "findings": [], "reason": "Discovery evidence changed; review the current bundle."}
        record_runtime_identity(manifest)
    validate_bundle(manifest, run_dir)
    if changed or not path.exists():
        write_json_atomic(path, manifest)
    return manifest


def finite_decision(cycle: dict[str, Any], payload: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    """Evaluate an explicitly supplied one-stage decision, separately from discrimination.

    Hypotheses may coexist; callers must define their own exogenous state space
    rather than treating the hypothesis list as a categorical prior by default.
    Outcome evidence never fabricates a likelihood or a calibrated posterior.
    """
    from codex_science.decision_analysis import run_decision_analysis
    from codex_science.research_cycle import _refs, validate_cycle

    validate_cycle(cycle, run_dir=run_dir)
    rationale = payload.get("state_model_rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        raise ValueError("state_model_rationale must explain the finite exogenous states")
    refs = payload.get("assumption_refs")
    if not isinstance(refs, list) or not refs:
        raise ValueError("assumption_refs must locate prior/likelihood/value assumptions")
    _refs(refs, "decision assumption_refs", run_dir)
    contract = payload.get("decision_contract")
    if not isinstance(contract, dict):
        raise ValueError("decision_contract must be an explicit finite decision table")
    result = run_decision_analysis(contract)
    report = {"schema_version": 1, "cycle_hash": cycle["cycle_hash"], "cycle_revision": cycle["revision"],
            "state_model_rationale": rationale, "assumption_refs": refs, "decision_analysis": result,
            "evidence_boundary": "Conditional one-stage EVSI/decision analysis. Not EIG, calibrated beliefs, execution authority, or an optimal sequential research policy."}
    if "observed_outcome" in payload:
        report["observed_policy"] = _observed_policy(cycle, payload, result, run_dir)
    return report


def _observed_policy(cycle: dict[str, Any], payload: dict[str, Any],
                     analysis: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    from codex_science.research_cycle import _confined_file, _pointer, _refs, _text

    observed = payload["observed_outcome"]
    if not isinstance(observed, dict):
        raise ValueError("observed_outcome must be an object")
    prior_ref = observed.get("preregistered_decision_ref")
    _refs([prior_ref], "preregistered_decision_ref", run_dir)
    if prior_ref not in cycle["evaluation"]["artifact_refs"]:
        raise ValueError("observed decision model must be frozen in evaluation artifact_refs")
    prior = load_json_object(_confined_file(run_dir, prior_ref["path"]))
    for field in ("state_model_rationale", "assumption_refs", "decision_contract"):
        if prior.get(field) != payload[field]:
            raise ValueError("observed decision assumptions differ from preregistration")
    cycle_id = _text(observed.get("cycle_experiment_id"), "cycle_experiment_id")
    experiment = next((item for item in cycle["experiments"] if item["id"] == cycle_id), None)
    if experiment is None or experiment.get("state") != "completed":
        raise ValueError("observed decision requires a completed valid experiment")
    # An outcome category is read from the actual measured artifact. It is not a
    # posterior invented from an explanation label or an execution failure.
    ref = observed.get("artifact_ref")
    _refs([ref], "observed decision artifact_ref", run_dir)
    if ref not in experiment["evidence_refs"]:
        raise ValueError("decision outcome artifact was not measured by this experiment")
    pointer = _text(observed.get("json_pointer"), "decision outcome json_pointer")
    contract_id = _text(observed.get("decision_experiment_id"), "decision_experiment_id")
    bindings = prior.get("observation_bindings", [])
    if {"cycle_experiment_id": cycle_id, "decision_experiment_id": contract_id,
        "json_pointer": pointer, "artifact_path": ref["path"]} not in bindings:
        raise ValueError("outcome measurement mapping must be preregistered")
    outcome = _pointer(load_json_object(_confined_file(run_dir, ref["path"])), pointer)
    if not isinstance(outcome, str):
        raise ValueError("decision outcome must be a recorded category")
    information = analysis.get("information_value") or {}
    policies = next((item for item in information.get("experiments", [])
                     if item["experiment"] == contract_id), None)
    if policies is None:
        raise ValueError("decision experiment has no finite observation policy")
    selected = next((item for item in policies["outcome_policy"] if item["outcome"] == outcome), None)
    if selected is None or selected["status"] == "unreachable":
        raise ValueError("observed outcome is absent or impossible under the declared model")
    return {"cycle_experiment_id": cycle_id, "decision_experiment_id": contract_id,
            "artifact_ref": ref, "json_pointer": pointer, "preregistered_decision_ref": prior_ref,
            "conditional_policy": selected,
            "evidence_boundary": "One preregistered observation conditioned once; not a calibrated belief about coexisting hypotheses or a sequential policy."}


def plan_cycle(cycle: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    """Rank unreserved experiments against the exact remaining frozen budget."""
    from codex_science.experiment_planner import plan_discriminating_experiment
    from codex_science.research_cycle import _remaining_budget, validate_cycle

    validate_cycle(cycle, run_dir=run_dir)
    remaining_exact = _remaining_budget(cycle)
    remaining = float(remaining_exact)
    ranked = []
    if cycle["status"] == "active":
        for experiment in cycle["experiments"]:
            if experiment.get("state", "planned") != "planned":
                continue
            identifiers = set(experiment["predictions"])
            if len(identifiers) < 2:
                continue
            result = plan_discriminating_experiment({
                "hypotheses": [item for item in cycle["hypotheses"] if item["id"] in identifiers],
                "candidates": [experiment], "budget": remaining,
            })
            # Float output can round either way; reservation uses decimal spellings.
            for item in result["ranked"]:
                item["reasons"] = [reason for reason in item["reasons"] if reason != "budget"]
                if Fraction(str(experiment["cost"])) + Fraction(str(experiment.get("control_cost", 0))) > remaining_exact:
                    item["reasons"].insert(0, "budget")
            ranked.extend(result["ranked"])
    ranked.sort(key=lambda item: (bool(item["reasons"]), -len(item["distinguishable_pairs"]), item["total_cost"], item["id"]))
    return {"schema_version": 1, "policy": "discriminate_first_v1", "cycle_hash": cycle["cycle_hash"],
            "remaining_budget": remaining, "selected": next((item for item in ranked if not item["reasons"]), None),
            "ranked": ranked, "executed": False,
            "evidence_boundary": "Selects a discriminating proposal from current unreserved experiments; performance confirmation may need a separately justified experiment."}
