"""Read-only, traceable views over validated research-discovery cycles.

These functions summarize recorded evidence.  They do not execute experiments,
reclassify observations, or turn a method effect into evidence of mechanism.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _identity(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _refs(value: Any) -> list[dict[str, str]]:
    return [{"path": item["path"], "sha256": item["sha256"]} for item in value]


def _evaluation_identity(cycle: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    evaluation = cycle["evaluation"]
    material = {
        "problem": cycle["problem"],
        "evaluator": evaluation["evaluator"],
        "baseline": evaluation["baseline"],
        "split": evaluation["split"],
        "primary_metric": evaluation["primary_metric"],
        "threshold": evaluation["threshold"],
        "budget": evaluation["budget"],
        "budget_rule": evaluation["budget_rule"],
        "artifact_refs": _refs(evaluation["artifact_refs"]),
    }
    return _identity(material), material


def _method_identity(method: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    # A method's optional structured design is part of its frozen contract.
    # IDs are local names, but every other declared field may change its scope.
    material = {key: value for key, value in method.items() if key != "id"}
    material["code_refs"] = _refs(method.get("code_refs", []))
    return _identity(material), material


def _hypothesis_identity(hypothesis: Mapping[str, Any]) -> str:
    return _identity({key: hypothesis[key] for key in ("statement", "conditions", "falsifier")})


def _revision_lessons(cycle: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Keep recorded change rationale and source links without inventing lessons."""
    lessons = []
    for event in cycle.get("events", []):
        if not isinstance(event, Mapping):
            continue
        sources = []
        additions: dict[str, list[str]] = {}
        for experiment in event.get("experiments", []):
            if isinstance(experiment, Mapping) and experiment.get("retry_of"):
                sources.append(experiment["retry_of"])
        for name in ("assumptions", "hypotheses", "methods", "experiments"):
            identifiers = [item["id"] for item in event.get(name, [])
                           if isinstance(item, Mapping) and isinstance(item.get("id"), str)]
            if identifiers:
                additions[name] = identifiers
        item = {"kind": event.get("kind"), "source_experiment_ids": sources}
        if isinstance(event.get("rationale"), str):
            item["rationale"] = event["rationale"]
        if event.get("source_experiment_id"):
            item["source_experiment_ids"].append(event["source_experiment_id"])
        if additions:
            item["added_definition_ids"] = additions
        if isinstance(event.get("lesson"), Mapping):
            item["lesson"] = copy.deepcopy(dict(event["lesson"]))
        if event.get("experiment_id"):
            item["experiment_id"] = event["experiment_id"]
        if event.get("outcome"):
            item["outcome"] = event["outcome"]
        lessons.append(item)
    return lessons


def _next_action(cycle: Mapping[str, Any], plan: Mapping[str, Any]) -> dict[str, Any]:
    """Prioritize state recovery before selecting another experiment."""
    experiments = cycle["experiments"]
    if cycle.get("status") != "active":
        unanswered = []
        for hypothesis in cycle["hypotheses"]:
            labels = [item.get("explanation_support", {}).get(hypothesis["id"])
                      for item in experiments if item.get("state") == "completed" and hypothesis["id"] in item["predictions"]]
            if not labels or all(label == "inconclusive" for label in labels):
                unanswered.append(hypothesis["id"])
        return {"kind": "review_or_report_bounded_result", "cycle_status": cycle.get("status"),
                "unanswered_hypothesis_ids": unanswered,
                "scope": "The cycle is terminal: obtain the applicable independent review or report its bounded result. Do not schedule a new experiment in this cycle."}
    ambiguous = [item["id"] for item in experiments if item.get("state") == "ambiguous"]
    if ambiguous:
        return {"kind": "reconcile_ambiguous_submission", "experiment_ids": ambiguous,
                "scope": "Reconcile recorded ambiguous submissions before reserving any new experiment."}
    pending = [item["id"] for item in experiments if item.get("state") in {"reserved", "running"}]
    if pending:
        return {"kind": "await_or_reconcile_submission", "experiment_ids": pending,
                "scope": "Wait for, or reconcile, existing reserved/running submissions before scheduling new work."}
    successors = {item.get("retry_of") for item in experiments if item.get("retry_of")}
    for event in cycle.get("events", []):
        if isinstance(event, Mapping) and event.get("kind") == "revise" and event.get("source_experiment_id"):
            if any(event.get(name) for name in ("assumptions", "hypotheses", "methods", "experiments")):
                successors.add(event["source_experiment_id"])
    failures = [item["id"] for item in experiments if item.get("state") == "failed" and item["id"] not in successors]
    if failures:
        return {"kind": "repair_failed_experiment", "experiment_ids": failures,
                "scope": "Repair the recorded failure; a later experiment may be proposed only through a new cycle revision."}
    if plan.get("selected"):
        selected = plan["selected"]
        experiment = next(item for item in experiments if item["id"] == selected["id"])
        method = next(item for item in cycle["methods"] if item["id"] == experiment["method_id"])
        if cycle.get("design_policy") == "required-for-reservation":
            from codex_science.discovery_design import audit_design
            audit = audit_design(cycle)
            method_audit = next((item for item in audit["methods"] if item["method_id"] == method["id"]), None)
            if not audit["problem_ready"] or not method_audit or not method_audit["implementation_ready"]:
                missing = list(audit.get("readiness", {}).get("design", {}).get("missing", []))
                if method_audit:
                    missing.extend(method_audit.get("missing", []))
                return {"kind": "complete_method_design_before_reservation", "proposal": selected,
                        "missing": sorted(set(missing)),
                        "scope": "Strict design policy blocks reservation until the problem and selected method audit as implementation-ready."}
        if not method.get("code_refs"):
            return {"kind": "implement_method_before_reservation", "proposal": selected,
                    "scope": "The idea is recorded, but it needs code identity before it can be reserved or executed."}
        return {"kind": "run_discriminating_proposal", "proposal": plan["selected"],
                "scope": "Conditional on the frozen evaluation, controls, measurement resolution, and remaining budget."}
    unresolved_hypotheses = sorted({hypothesis_id for item in experiments if item.get("state", "planned") != "completed" for hypothesis_id in item["predictions"]})
    observed = [item.get("method_effect") for item in experiments if item.get("state") == "completed"]
    if "inconclusive" in observed:
        reason = "Recorded observations remain inconclusive at the frozen measurement resolution."
    elif "nonpositive" in observed:
        reason = "Recorded nonpositive method effects do not by themselves reject an explanation."
    else:
        reason = "No eligible recorded discriminating proposal remains."
    return {"kind": "formulate_revision_or_stop", "unresolved_hypothesis_ids": unresolved_hypotheses,
            "scope": reason + " Any new question must preserve the recorded applicability boundary."}


def _next_question(group: Mapping[str, Any]) -> str:
    labels = {item["label"] for item in group["evidence"]}
    if "repair_required" in labels:
        return "Which recorded implementation, execution, or measurement failure must be repaired before interpreting this evidence?"
    if "unresolved" in labels:
        return "Which reserved, running, or ambiguous submission must be reconciled before a new discriminating experiment is selected?"
    if "contradicted" in labels:
        return "Which recorded applicability condition or competing explanation should a revised discriminating experiment test after this interval contradiction?"
    if "inconclusive" in labels:
        return "Can a revised experiment distinguish the remaining prediction intervals at the recorded measurement resolution and budget?"
    if "planned" in labels:
        return "Which recorded planned experiment best discriminates this exact hypothesis under the frozen evaluation contract?"
    if "nonpositive" in labels:
        return "What competing explanation or applicability boundary should be tested next; the nonpositive method effect alone does not reject this hypothesis?"
    return "No additional recorded discriminating proposal remains; should the bounded cycle stop or record a justified revision?"


def _experiment_state(experiment: Mapping[str, Any], hypothesis_id: str | None = None) -> str:
    state = experiment.get("state", "planned")
    if state == "completed":
        return experiment["explanation_support"].get(hypothesis_id, "inconclusive") if hypothesis_id else experiment["method_effect"]
    if state == "failed":
        return "repair_required"
    if state in {"reserved", "running", "ambiguous"}:
        return "unresolved"
    return "planned"


def _experiment_evidence(
    experiment: Mapping[str, Any],
    method: Mapping[str, Any],
    cycle: Mapping[str, Any],
    *,
    hypothesis_id: str | None = None,
) -> dict[str, Any]:
    state = experiment.get("state", "planned")
    entry: dict[str, Any] = {
        "experiment_id": experiment["id"],
        "experiment_fingerprint": experiment["fingerprint"],
        "cycle_hash": cycle["cycle_hash"],
        "cycle_revision": cycle["revision"],
        "state": state,
        "label": _experiment_state(experiment, hypothesis_id),
        "code_identity_refs": _refs(method.get("code_refs", [])),
        "evaluation_identity_refs": _refs(cycle["evaluation"]["artifact_refs"]),
        "predicted_interval": experiment["predictions"].get(hypothesis_id) if hypothesis_id else None,
        "applicability": list(experiment["controls"]),
        "observation_independence": "unknown",
        "evidence_paths": [],
        "observed_values": [],
    }
    if state == "completed":
        entry.update({
            "method_effect": experiment["method_effect"],
            "explanation_support": experiment["explanation_support"].get(hypothesis_id) if hypothesis_id else None,
            "execution_refs": _refs(experiment.get("execution_refs", [])),
            "evidence_paths": [item["path"] for item in experiment.get("evidence_refs", [])],
            "observed_values": [{"value": item["value"], "json_pointer": item["json_pointer"], "artifact_ref": item["artifact_ref"]} for item in experiment["observations"]],
        })
    elif state == "failed":
        entry.update({
            "failure_kind": experiment["failure_kind"], "outcome": experiment.get("outcome"),
            "execution_refs": _refs(experiment.get("execution_refs", [])),
            "evidence_paths": [item["path"] for item in experiment.get("evidence_refs", [])],
        })
    elif state in {"reserved", "running", "ambiguous"}:
        entry.update({"request_id": experiment.get("request_id"), "reconciliation_required": state == "ambiguous"})
    return entry


def summarize_cycle(cycle: Mapping[str, Any], run_dir: Path | str) -> dict[str, Any]:
    """Return a read-only evidence ledger for one fully validated cycle snapshot."""
    from codex_science.discovery import plan_cycle
    from codex_science.research_cycle import validate_cycle

    root = Path(run_dir)
    validate_cycle(cycle, run_dir=root)
    evaluation_id, evaluation_material = _evaluation_identity(cycle)
    methods = {item["id"]: item for item in cycle["methods"]}
    experiments_by_method: dict[str, list[Mapping[str, Any]]] = {item["id"]: [] for item in cycle["methods"]}
    for experiment in cycle["experiments"]:
        experiments_by_method[experiment["method_id"]].append(experiment)

    hypothesis_ledger = []
    for hypothesis in cycle["hypotheses"]:
        evidence = []
        for experiment in cycle["experiments"]:
            if hypothesis["id"] in experiment["predictions"]:
                evidence.append(_experiment_evidence(experiment, methods[experiment["method_id"]], cycle, hypothesis_id=hypothesis["id"]))
        hypothesis_ledger.append({
            "hypothesis_id": hypothesis["id"],
            "hypothesis_identity": _hypothesis_identity(hypothesis),
            "statement": hypothesis["statement"],
            "conditions": hypothesis["conditions"],
            "falsifier": hypothesis["falsifier"],
            "evidence": evidence,
        })

    method_ledger = []
    for method in cycle["methods"]:
        method_id, material = _method_identity(method)
        method_ledger.append({
            "method_id": method["id"],
            "method_identity": method_id,
            "definition": method["definition"],
            "correctness_checks": list(method.get("correctness_checks", [])),
            "code_identity_refs": _refs(method.get("code_refs", [])),
            "evidence": [_experiment_evidence(item, method, cycle) for item in experiments_by_method[method["id"]]],
            "identity_material": material,
        })

    plan = plan_cycle(dict(cycle), root)
    unresolved = [item["id"] for item in cycle["experiments"] if item.get("state", "planned") in {"reserved", "running", "ambiguous"}]
    failures = {kind: [] for kind in ("implementation", "execution", "measurement")}
    for experiment in cycle["experiments"]:
        if experiment.get("state") == "failed":
            failures[experiment["failure_kind"]].append({
                "experiment_id": experiment["id"],
                "cycle_hash": cycle["cycle_hash"],
                "cycle_revision": cycle["revision"],
                "outcome": experiment.get("outcome"),
                "required_action": "repair and record a new discriminating experiment if warranted",
            })
    next_action = plan["selected"]
    prioritized_action = _next_action(cycle, plan)
    return {
        "schema_version": 1,
        "cycle_hash": cycle["cycle_hash"],
        "cycle_revision": cycle["revision"],
        "cycle_status": cycle["status"],
        "evaluation_identity": evaluation_id,
        "evaluation_identity_material": evaluation_material,
        "remaining_budget": plan["remaining_budget"],
        "failure_ledger": failures,
        "unresolved_experiments": unresolved,
        "reconciliation_required": [item["id"] for item in cycle["experiments"] if item.get("state") == "ambiguous"],
        "next_action": prioritized_action,
        "next_discriminating_action": next_action,
        "next_action_scope": prioritized_action["scope"],
        "revision_lessons": _revision_lessons(cycle),
        "hypothesis_ledger": hypothesis_ledger,
        "method_ledger": method_ledger,
        "evidence_boundary": (
            "Observed labels are derived from preregistered intervals and recorded observations. "
            "A positive method effect does not prove a mechanism, verify correctness, establish novelty, or justify universal rejection. "
            "Implementation, execution, and measurement failures require repair and do not refute a hypothesis."
        ),
    }


def synthesize_history(history: Mapping[str, Any]) -> dict[str, Any]:
    """Group comparable recorded cycle evidence without voting across contexts.

    ``ProjectStore.discovery_history`` contains validated cycle snapshots but no
    run-directory locations.  Therefore this function consumes the preserved
    scientific state and does not re-read artifacts; callers should obtain its
    input from that method rather than hand-assembled data.
    """
    if not isinstance(history, Mapping) or not isinstance(history.get("runs"), list):
        raise ValueError("history must be ProjectStore.discovery_history output")
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    contexts: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for run in history["runs"]:
        if not isinstance(run, Mapping) or not isinstance(run.get("run_id"), str) or not isinstance(run.get("cycles"), list):
            raise ValueError("history run is invalid")
        # History contains an append-only revision chain.  Earlier snapshots are
        # provenance for the latest snapshot, not independent repeat studies.
        if not run["cycles"]:
            continue
        latest = max(run["cycles"], key=lambda item: item.get("revision", -1) if isinstance(item, Mapping) else -1)
        for cycle in [latest]:
            # ProjectStore has already validated every cycle against its immutable bundle.
            if not isinstance(cycle, Mapping):
                raise ValueError("history cycle is invalid")
            required = {"cycle_hash", "revision", "problem", "evaluation", "hypotheses", "methods", "experiments"}
            if not required <= set(cycle):
                missing.append({"run_id": run["run_id"], "reason": "cycle lacks full scientific state for synthesis"})
                continue
            evaluation_id, evaluation_material = _evaluation_identity(cycle)
            contexts.append({"run_id": run["run_id"], "cycle_hash": cycle["cycle_hash"], "cycle_revision": cycle["revision"], "evaluation_identity": evaluation_id})
            methods = {item["id"]: item for item in cycle["methods"]}
            hypotheses = {item["id"]: item for item in cycle["hypotheses"]}
            for experiment in cycle["experiments"]:
                method = methods[experiment["method_id"]]
                method_id, method_material = _method_identity(method)
                for hypothesis_id in experiment["predictions"]:
                    hypothesis = hypotheses[hypothesis_id]
                    hypothesis_key = _hypothesis_identity(hypothesis)
                    key = (evaluation_id, method_id, hypothesis_key)
                    group = groups.setdefault(key, {
                        "evaluation_identity": evaluation_id,
                        "evaluation_identity_material": evaluation_material,
                        "method_identity": method_id,
                        "method_identity_material": method_material,
                        "hypothesis_identity": hypothesis_key,
                        "hypothesis": {field: hypothesis[field] for field in ("statement", "conditions", "falsifier")},
                        "evidence": [],
                    })
                    entry = _experiment_evidence(experiment, method, cycle, hypothesis_id=hypothesis_id)
                    entry["run_id"] = run["run_id"]
                    entry["total_cost"] = float(experiment["cost"]) + float(experiment.get("control_cost", 0))
                    group["evidence"].append(entry)
    for group in groups.values():
        group["evidence"].sort(key=lambda item: (item["run_id"], item["cycle_revision"], item["experiment_id"]))
        shared: dict[tuple[str, ...], list[dict[str, Any]]] = {}
        for entry in group["evidence"]:
            execution = tuple(ref["sha256"] for ref in entry.get("execution_refs", []))
            if execution:
                shared.setdefault(execution, []).append(entry)
        group["shared_execution_evidence"] = [
            {"execution_ref_hashes": list(identity), "entries": [{"run_id": item["run_id"], "experiment_id": item["experiment_id"]} for item in entries],
             "independence": "unknown; shared execution identity is not an independent replication"}
            for identity, entries in sorted(shared.items()) if len(entries) > 1
        ]
        group["suggested_actionable_next_question"] = _next_question(group)
    context_ids = {item["evaluation_identity"] for item in contexts}
    return {
        "schema_version": 1,
        "project_id": history.get("project_id"),
        "comparable_evidence_groups": sorted(groups.values(), key=lambda item: (item["evaluation_identity"], item["method_identity"], item["hypothesis_identity"])),
        "heterogeneous_contexts": contexts if len(context_ids) > 1 else [],
        "uncombined_contexts": len(context_ids) > 1,
        "missing_minimal_enrichment": missing,
        "minimum_history_fields": ["run_id", "cycle_hash", "revision", "problem", "evaluation", "hypotheses", "methods", "experiments"],
        "evidence_boundary": (
            "Evidence is grouped only by exact evaluation, method, and hypothesis identities; labels are preserved per experiment and are never majority-voted. "
            "Different contexts remain separate. Observation independence is unknown unless a future contract records it. "
            "Failed, null/nonpositive, inconclusive, and unresolved outcomes remain visible. "
            "This is not a claim of mechanism, universal rejection, reproducibility, or paper novelty."
        ),
    }
