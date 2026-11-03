"""Explicit screening-to-lead handoff preserving molecular and score identity."""
from __future__ import annotations

from codex_science.lead_optimization import analyze_hit_to_lead
from codex_science.virtual_screening import analyze_screening, fingerprint


def screening_to_lead(screening_input, handoff):
    source = analyze_screening(screening_input)
    if not isinstance(handoff, dict) or handoff.get("schema") != "screening-lead-handoff-v1":
        raise ValueError("expected screening-lead-handoff-v1")
    if source["input_sha256"] != handoff.get("source_input_sha256") or source["contract_sha256"] != handoff.get("source_contract_sha256"):
        raise ValueError("upstream input or contract identity mismatch")
    original = screening_input["contract"]
    if handoff.get("target_id") != original["target_id"]:
        raise ValueError("target handoff mismatch")
    unit = handoff.get("score_unit")
    if not isinstance(unit, str) or not unit.strip():
        raise ValueError("explicit score unit required; affinity units are never inferred")
    if handoff.get("selection_context") not in {"prospective", "held_out_evaluation"}:
        raise ValueError("explicit selection context required")
    if original["evaluation_partition"] == "test" and handoff["selection_context"] != "held_out_evaluation":
        raise ValueError("test-screen candidates cannot be silently relabeled as prospective discovery")
    objective = {"id": "screening_score", "assay_id": original["score_name"], "unit": unit,
                 "source_kind": "computed", "direction": "minimize" if original["score_direction"] == "lower" else "maximize"}
    if original.get("score_threshold") is not None:
        objective["maximum" if objective["direction"] == "minimize" else "minimum"] = original["score_threshold"]
    extra_objectives = handoff.get("additional_objectives", [])
    properties = handoff.get("additional_properties", {})
    if not isinstance(extra_objectives, list) or not isinstance(properties, dict):
        raise ValueError("additional objectives/properties have invalid shape")
    source_ids = {row["id"] for row in source["compounds"]}
    if not set(properties) <= source_ids:
        raise ValueError("unknown compound in property handoff")
    contract = {"target_id": original["target_id"], "decision": "Select follow-up compounds from a frozen screening analysis",
                "selection_context": handoff["selection_context"], "objectives": [objective, *extra_objectives],
                "selection": handoff.get("selection")}
    candidates = []
    excluded_partitions = []
    for row in source["compounds"]:
        if row["partition"] not in {"train", original["evaluation_partition"]}:
            excluded_partitions.append({"id": row["id"], "partition": row["partition"], "reason": "outside-frozen-evaluation-partition"})
            continue
        extra = properties.get(row["id"], {})
        if not isinstance(extra, dict) or "screening_score" in extra:
            raise ValueError("external properties cannot overwrite screening score")
        candidates.append({"id": row["id"], "chemical_identity": row["chemical_identity"],
            "target_id": row["target_id"], "partition": "train" if row["partition"] == "train" else "candidate",
            "scaffold_group": row["scaffold_group"], "training_overlap": row["training_overlap"],
            "parent_id": None, "cost": 1, "source_partition": row["partition"],
            "properties": {**extra, "screening_score": None if row["score"] is None else {
                "value": row["score"], "assay_id": objective["assay_id"], "unit": unit, "source_kind": "computed"}}})
    lead_input = {"schema_version": 1, "synthetic": handoff.get("synthetic", False), "contract": contract,
        "contract_sha256": fingerprint(contract), "candidates": candidates,
        "controls": [{"id": "upstream-analysis-admissible", "passed": source["acceptance"] == "accepted_analysis"}]}
    lead = analyze_hit_to_lead(lead_input)
    return {"schema": "screening-lead-handoff-result-v1", "source_input_sha256": source["input_sha256"],
        "source_analysis_sha256": fingerprint(source), "lead_input": lead_input, "lead_analysis": lead,
        "upstream_denominators": source["denominators"],
        "upstream_compounds": source["compounds"], "excluded_partitions": excluded_partitions,
        "evidence_boundary": "Supplied screening and property analysis only; no generation, docking, measured affinity or independent review."}
