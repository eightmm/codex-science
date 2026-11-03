"""Assay-bound supplied-property selection; no generator or molecular engine."""

from __future__ import annotations

import math
from codex_science.experiment_planner import plan_next_experiment
from codex_science.virtual_screening import fingerprint


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _identities(rows, label):
    _require(isinstance(rows, list), f"{label} must be a list")
    ids = [row.get("id") if isinstance(row, dict) else None for row in rows]
    _require(all(_text(i) for i in ids) and len(set(ids)) == len(ids), f"duplicate or missing {label} identity")
    return rows


def analyze_hit_to_lead(payload):
    """Select a cost/diversity bounded batch without mixing endpoint identities."""
    _require(isinstance(payload, dict) and type(payload.get("schema_version")) is int and payload["schema_version"] == 1,
             "unsupported hit-to-lead schema")
    fingerprint(payload)
    contract = payload.get("contract")
    _require(isinstance(contract, dict) and payload.get("contract_sha256") == fingerprint(contract), "frozen contract hash mismatch")
    _require(_text(contract.get("target_id")) and _text(contract.get("decision")), "target and decision required")
    context = contract.get("selection_context")
    _require(context in ("prospective", "held_out_evaluation"), "selection context required")
    objectives = _identities(contract.get("objectives"), "objectives")
    _require(bool(objectives), "at least one objective required")
    for item in objectives:
        _require(item.get("direction") in ("maximize", "minimize"), "invalid objective direction")
        _require(_text(item.get("unit")) and _text(item.get("assay_id")), "objective unit and assay_id required")
        _require(item.get("source_kind") in ("measured", "predicted", "computed"), "objective source_kind required")
        _require(_finite(item.get("weight", 1)) and item.get("weight", 1) >= 0, "objective weight must be finite and non-negative")
        for bound in ("minimum", "maximum"):
            _require(item.get(bound) is None or _finite(item[bound]), f"invalid {bound}")
        if item.get("minimum") is not None and item.get("maximum") is not None:
            _require(item["minimum"] <= item["maximum"], "inverted objective bounds")
    _require(any(item.get("weight", 1) > 0 for item in objectives), "at least one objective weight must be positive")
    selection = contract.get("selection")
    _require(isinstance(selection, dict), "selection constraints required")
    for field, minimum in (("batch_size", 1), ("diversity_group_cap", 1), ("minimum_controls", 0)):
        _require(type(selection.get(field)) is int and selection[field] >= minimum, f"selection.{field} must be an integer >= {minimum}")
    _require(_finite(selection.get("budget")) and selection["budget"] >= 0, "selection budget must be finite and non-negative")
    _require(_finite(contract.get("diversity_bonus", 0.1)) and contract.get("diversity_bonus", 0.1) >= 0,
             "diversity bonus must be finite and non-negative")
    controls = _identities(payload.get("controls"), "controls")
    _require(all(type(row.get("passed")) is bool for row in controls), "control outcome must be boolean")
    controls_passed = bool(controls) and all(row["passed"] for row in controls)
    candidates = _identities(payload.get("candidates"), "candidates")
    _require(bool(candidates), "candidate inventory required")
    known = {row["id"] for row in candidates}
    chemical_ids, scaffolds = set(), {}
    records, planned = [], []
    for row in candidates:
        _require(row.get("target_id") == contract["target_id"], "candidate target mismatch")
        chemical = row.get("chemical_identity")
        _require(_text(chemical) and chemical not in chemical_ids, "duplicate or missing chemical identity")
        chemical_ids.add(chemical)
        _require(row.get("parent_id") is None or row["parent_id"] in known - {row["id"]}, "missing or self parent")
        partition, scaffold = row.get("partition"), row.get("scaffold_group")
        _require(partition in ("train", "candidate") and _text(scaffold), "partition and scaffold required")
        _require(context != "held_out_evaluation" or scaffold not in scaffolds or scaffolds[scaffold] == partition,
                 "scaffold leakage across train/candidate evaluation")
        scaffolds[scaffold] = partition
        _require(row.get("training_overlap") in ("none", "known", "unknown"), "training overlap required")
        values = row.get("properties")
        _require(isinstance(values, dict), "candidate properties required")
        _require(set(values) <= {item["id"] for item in objectives}, "undeclared objective")
        reasons = [] if partition == "candidate" else ["training-row"]
        if row["training_overlap"] != "none":
            reasons.append("training-overlap-" + row["training_overlap"])
        properties = {}
        for objective in objectives:
            name = objective["id"]
            value = values.get(name)
            if value is None:
                reasons.append("missing-" + name)
                continue
            _require(isinstance(value, dict), "property must carry value/unit/assay/source identity")
            _require(all(value.get(field) == objective[field] for field in ("unit", "assay_id", "source_kind")), "property endpoint identity mismatch")
            number = value.get("value")
            _require(_finite(number), "property must be finite")
            properties[name] = number
            if objective.get("minimum") is not None and number < objective["minimum"]:
                reasons.append("below-minimum-" + name)
            if objective.get("maximum") is not None and number > objective["maximum"]:
                reasons.append("above-maximum-" + name)
        cost = row.get("cost")
        _require(_finite(cost) and cost >= 0, "candidate cost must be finite and non-negative")
        _require(type(row.get("control", False)) is bool, "candidate control flag must be boolean")
        records.append({**row, "eligible": not reasons, "exclusion_reasons": reasons})
        planned.append({"id": row["id"], "properties": properties, "cost": cost,
                        "diversity_group": scaffold, "control": row.get("control", False),
                        "eligible": not reasons, "exclusion_reason": ",".join(reasons)})
    # Resolve every lineage path; membership alone would allow an ancestry cycle.
    parents = {row["id"]: row.get("parent_id") for row in candidates}
    for identifier in parents:
        seen = set()
        while identifier is not None:
            _require(identifier not in seen, "cyclic candidate ancestry")
            seen.add(identifier)
            identifier = parents[identifier]
    proposal = None
    if controls_passed and any(row["eligible"] for row in records):
        proposal = plan_next_experiment({"schema_version": 1, "decision": contract["decision"],
            "objectives": [{"name": row["id"], "direction": row["direction"], "weight": row.get("weight", 1)} for row in objectives],
            "candidates": planned, "constraints": selection,
            "uncertainty_weight": 0, "diversity_bonus": contract.get("diversity_bonus", 0.1)}, created_at="supplied-contract")
    result = {"schema": "hit-to-lead-result-v1", "contract_sha256": payload["contract_sha256"],
            "engine_executed": False, "controls_passed": controls_passed, "controls": controls,
            "candidate_count": len(records), "eligible_count": sum(row["eligible"] for row in records),
            "candidates": records, "proposal": proposal,
            "acceptance": "qualified_shortlist" if proposal and proposal["selected_count"] else "inconclusive",
            "evidence_boundary": "Supplied properties and declared scaffold groups only. No chemical validation, generation, QSAR calibration, ADMET assay, affinity or synthesis feasibility is established."}
    fingerprint(result)
    return result
