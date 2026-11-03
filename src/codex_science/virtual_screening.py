"""Offline compound-level analysis of supplied screening scores; no docking engine."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from itertools import groupby

from codex_science.sbdd_execution import average_precision


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _rows(value, name):
    _require(isinstance(value, list), f"{name} must be a list")
    ids = [row.get("id") if isinstance(row, dict) else None for row in value]
    _require(all(_text(item) for item in ids) and len(set(ids)) == len(ids), f"{name} duplicate or missing identity")
    return {row["id"]: row for row in value}


def _ranking_metrics(rows, top_k):
    labels = [row["active"] for row in rows]
    scores = [row["oriented_score"] for row in rows]
    positives = sum(labels)
    if not labels or not positives or positives == len(labels):
        return {"status": "unavailable", "reason": "both active and inactive labels required", "n": len(labels)}
    prevalence = positives / len(labels)
    remaining = min(top_k, len(rows))
    selected = remaining
    hits = 0.0
    for _, members in groupby(sorted(rows, key=lambda row: -row["oriented_score"]), key=lambda row: row["oriented_score"]):
        tied = list(members)
        take = min(remaining, len(tied))
        hits += take * (sum(row["active"] for row in tied) / len(tied))
        remaining -= take
        if not remaining:
            break
    return {"status": "computed", "n": len(rows), "actives": positives,
            "average_precision": average_precision(labels, scores),
            "constant_score_average_precision": prevalence,
            "enrichment_factor": (hits / selected) / prevalence,
            "random_expected_enrichment": 1.0, "top_k_effective": selected,
            "expected_hits_with_fractional_ties": hits}


def analyze_screening(payload):
    """Preserve all attempts, aggregate best observed pose, and qualify ranking claims.

    The frozen contract hash detects accidental edits, not retrospective threshold
    selection. Structural/chemical identities and control outcomes are declarations.
    """
    _require(isinstance(payload, dict) and type(payload.get("schema_version")) is int and payload["schema_version"] == 1,
             "unsupported screening schema")
    _require(_text(payload.get("run_id")), "run_id required")
    contract = payload.get("contract")
    _require(isinstance(contract, dict), "contract required")
    _require(payload.get("contract_sha256") == fingerprint(contract), "frozen contract hash mismatch")
    _require(contract.get("aggregation") == "best_observed_pose_across_states", "unsupported aggregation")
    direction = contract.get("score_direction")
    _require(direction in ("higher", "lower"), "score direction must be higher or lower")
    sign = 1 if direction == "higher" else -1
    _require(_text(contract.get("score_name")) and _text(contract.get("target_id")), "score and target identity required")
    _require(contract.get("tie_policy") == "fractional", "tie policy must be fractional")
    _require(type(contract.get("top_k")) is int and contract["top_k"] > 0, "top_k must be a positive integer")
    _require(_number(contract.get("minimum_ap_gain")) and 0 <= contract["minimum_ap_gain"] <= 1, "minimum_ap_gain must be in [0,1]")
    _require(_number(contract.get("minimum_enrichment")) and contract["minimum_enrichment"] >= 1, "minimum_enrichment must be >=1")
    threshold = contract.get("score_threshold")
    _require(threshold is None or _number(threshold), "score threshold must be finite or null")
    _require(contract.get("pocket_source") in ("independent_reference", "explicit_residues", "validated_prediction"), "invalid or leaked pocket source")
    _require(contract.get("evaluation_partition") == "test", "evaluation partition must be test")
    compounds = _rows(payload.get("compounds"), "compounds")
    _require(bool(compounds), "compound inventory must not be empty")
    identities = set()
    groups = {}
    for row in compounds.values():
        identity = row.get("chemical_identity")
        _require(_text(identity) and identity not in identities, "duplicate or missing chemical identity")
        identities.add(identity)
        _require(row.get("target_id") == contract["target_id"], "target identity mismatch")
        _require(row.get("partition") in ("train", "validation", "test"), "partition required")
        _require(row.get("active") is None or type(row["active"]) is bool, "active must be boolean or null")
        _require(_text(row.get("scaffold_group")), "scaffold group required")
        group = row["scaffold_group"]
        _require(group not in groups or groups[group] == row["partition"], "scaffold leakage across partitions")
        groups[group] = row["partition"]
        _require(row.get("training_overlap") in ("none", "unknown", "known"), "training overlap declaration required")
        _require(row["training_overlap"] != "known" or row["partition"] != "test", "known model training leakage")
    states = _rows(payload.get("states"), "states")
    for state in states.values():
        _require(state.get("compound_id") in compounds and _text(state.get("state_identity")), "invalid state parent or identity")
    state_keys = [(row["compound_id"], row["state_identity"]) for row in states.values()]
    _require(len(set(state_keys)) == len(state_keys), "duplicate state identity")
    plans = _rows(payload.get("planned_attempts"), "planned_attempts")
    _require(bool(plans), "planned attempts required")
    for plan in plans.values():
        _require(plan.get("state_id") in states, "invalid planned state")
    _require(set(states) == {row["state_id"] for row in plans.values()}, "every state requires a planned attempt")
    _require(set(compounds) == {row["compound_id"] for row in states.values()}, "every compound requires a state")
    results = _rows(payload.get("results"), "results")
    _require(set(results) <= set(plans), "unplanned attempt identity")
    attempts = []
    by_compound = {key: [] for key in compounds}
    for key, plan in plans.items():
        result = results.get(key, {"id": key, "status": "missing", "reason": "no result supplied"})
        expected_identity = {"state_id": plan["state_id"],
                             "compound_id": states[plan["state_id"]]["compound_id"],
                             "target_id": contract["target_id"], "score_name": contract["score_name"]}
        for field, identity in expected_identity.items():
            _require(field not in result or result[field] == identity, f"attempt {field} identity mismatch")
        status = result.get("status")
        _require(status in ("ok", "failed", "missing"), "invalid attempt status")
        if status == "ok":
            _require(_number(result.get("score")), "successful attempt requires finite score")
        else:
            _require(_text(result.get("reason")) and result.get("score") is None, "failed or missing attempt requires reason and no score")
        row = dict(result, state_id=plan["state_id"], compound_id=states[plan["state_id"]]["compound_id"])
        attempts.append(row)
        by_compound[row["compound_id"]].append(row)
    controls = _rows(payload.get("controls"), "controls")
    for control in controls.values():
        _require(type(control.get("essential")) is bool and control.get("status") in ("passed", "failed", "unavailable"), "invalid control status")
        _require(_text(control.get("kind")) and _text(control.get("evidence_ref")), "control kind and evidence_ref required")
    essential = [row for row in controls.values() if row["essential"]]
    controls_passed = bool(essential) and any(row["kind"] == "positive_redock" for row in essential) and all(row["status"] == "passed" for row in essential)
    table = []
    for key, compound in compounds.items():
        successful = [row for row in by_compound[key] if row["status"] == "ok"]
        best = max(successful, key=lambda row: (sign * row["score"], row["id"])) if successful else None
        oriented = sign * best["score"] if best else None
        survivor = best is not None and (threshold is None or oriented >= sign * threshold)
        table.append(dict(compound, score=best["score"] if best else None, oriented_score=oriented,
                          best_attempt_id=best["id"] if best else None, retained=survivor,
                          attempt_counts=dict(Counter(row["status"] for row in by_compound[key])),
                          status="evaluable" if best else "unavailable"))
    evaluable = [row for row in table if row["partition"] == "test" and row["status"] == "evaluable"]
    labeled = [row for row in evaluable if type(row.get("active")) is bool]
    metrics = _ranking_metrics(labeled, contract["top_k"])
    reasons = []
    if not controls_passed:
        reasons.append("essential positive/redock controls failed or unavailable")
    if any(row["status"] != "ok" for row in attempts):
        reasons.append("incomplete attempt denominator; ranking is conditional on observed scores")
    if len(labeled) != sum(row["partition"] == "test" for row in table):
        reasons.append("incomplete labeled evaluation denominator")
    if any(row["training_overlap"] == "unknown" for row in table if row["partition"] == "test"):
        reasons.append("unknown model training overlap")
    if not any(row["retained"] for row in evaluable):
        reasons.append("zero retained test compounds")
    if metrics["status"] != "computed":
        reasons.append(metrics["reason"])
    elif metrics["average_precision"] - metrics["constant_score_average_precision"] < contract["minimum_ap_gain"] or metrics["enrichment_factor"] < contract["minimum_enrichment"]:
        reasons.append("prespecified ranking thresholds failed")
    return {"schema_version": 1, "kind": "virtual-screening-analysis-v1", "run_id": payload["run_id"],
            "input_sha256": fingerprint(payload), "contract_sha256": payload["contract_sha256"],
            "process_completed": True, "engine_executed": False, "acceptance": "accepted_analysis" if not reasons else "inconclusive",
            "reasons": reasons, "controls": list(controls.values()), "attempts": attempts, "compounds": table,
            "denominators": {"compounds": len(table), "planned_attempts": len(plans),
                             "attempt_status": dict(Counter(row["status"] for row in attempts)),
                             "test_evaluable": len(evaluable), "test_labeled_evaluable": len(labeled),
                             "test_retained": sum(row["retained"] for row in evaluable)},
            "metrics": metrics, "limitations": ["Supplied-score analysis only; no docking or chemical identity verification.",
                "Metrics are conditional on labeled evaluable test compounds, before shortlist filtering.",
                "No uncertainty interval or prospective affinity/binding validation is supplied."]}
