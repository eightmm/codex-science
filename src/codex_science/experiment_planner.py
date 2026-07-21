"""Deterministic, non-executing multi-objective next-experiment planning.

The planner ranks only declared candidate properties. It does not infer chemical
similarity, biological validity, or calibrated information gain from a model
name. Controls and scientific constraints remain explicit inputs.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


DIRECTIONS = {"maximize", "minimize"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _fingerprint(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _text(value: Any, label: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{label} is required")
    return text


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be numeric")
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be numeric") from error
    if result != result or result in {float("inf"), float("-inf")}:
        raise ValueError(f"{label} must be finite")
    return result


def _validate_objectives(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("objectives must be a non-empty list")
    objectives: list[dict[str, Any]] = []
    names: set[str] = set()
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise ValueError(f"objective {index} must be an object")
        name = _text(item.get("name"), f"objective {index} name")
        if name in names:
            raise ValueError(f"duplicate objective: {name}")
        names.add(name)
        direction = _text(item.get("direction"), f"objective {name} direction")
        if direction not in DIRECTIONS:
            raise ValueError(f"invalid objective direction: {direction}")
        weight = _number(item.get("weight", 1.0), f"objective {name} weight")
        if weight < 0:
            raise ValueError(f"objective {name} weight must be non-negative")
        objectives.append({"name": name, "direction": direction, "weight": weight, "required": bool(item.get("required", True))})
    if not any(item["weight"] > 0 for item in objectives):
        raise ValueError("at least one objective must have positive weight")
    return objectives


def _validate_candidates(raw: Any, objectives: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("candidates must be a non-empty list")
    required = {item["name"] for item in objectives if item["required"]}
    result: list[dict[str, Any]] = []
    ids: set[str] = set()
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise ValueError(f"candidate {index} must be an object")
        candidate_id = _text(item.get("id"), f"candidate {index} id")
        if candidate_id in ids:
            raise ValueError(f"duplicate candidate ID: {candidate_id}")
        ids.add(candidate_id)
        properties_raw = item.get("properties")
        if not isinstance(properties_raw, Mapping):
            raise ValueError(f"candidate {candidate_id} properties must be an object")
        missing = sorted(required - set(properties_raw))
        if missing:
            raise ValueError(f"candidate {candidate_id} lacks required objectives: {', '.join(missing)}")
        properties = {str(key): _number(value, f"candidate {candidate_id} property {key}") for key, value in properties_raw.items()}
        cost = _number(item.get("cost", 0), f"candidate {candidate_id} cost")
        uncertainty = _number(item.get("uncertainty", 0), f"candidate {candidate_id} uncertainty")
        if cost < 0 or uncertainty < 0:
            raise ValueError(f"candidate {candidate_id} cost and uncertainty must be non-negative")
        result.append({
            "id": candidate_id,
            "properties": properties,
            "cost": cost,
            "uncertainty": uncertainty,
            "diversity_group": str(item.get("diversity_group", item.get("scaffold_id", candidate_id))),
            "control": bool(item.get("control", False)),
            "eligible": bool(item.get("eligible", True)),
            "exclusion_reason": str(item.get("exclusion_reason", "")),
            "metadata": dict(item.get("metadata", {})) if isinstance(item.get("metadata", {}), Mapping) else {},
        })
    return result


def _normalize(candidates: list[dict[str, Any]], objectives: list[dict[str, Any]]) -> tuple[dict[str, dict[str, float]], dict[str, float]]:
    normalized: dict[str, dict[str, float]] = {item["id"]: {} for item in candidates}
    for objective in objectives:
        name = objective["name"]
        values = [candidate["properties"].get(name) for candidate in candidates if name in candidate["properties"]]
        if not values:
            continue
        minimum, maximum = min(values), max(values)
        for candidate in candidates:
            if name not in candidate["properties"]:
                normalized[candidate["id"]][name] = 0.0
                continue
            value = candidate["properties"][name]
            score = 1.0 if maximum == minimum else (value - minimum) / (maximum - minimum)
            if objective["direction"] == "minimize":
                score = 1.0 - score
            normalized[candidate["id"]][name] = score
    uncertainties = [candidate["uncertainty"] for candidate in candidates]
    low, high = min(uncertainties), max(uncertainties)
    uncertainty_scores = {
        candidate["id"]: (1.0 if high == low and high > 0 else 0.0 if high == low else (candidate["uncertainty"] - low) / (high - low))
        for candidate in candidates
    }
    return normalized, uncertainty_scores


def _dominates(left: Mapping[str, float], right: Mapping[str, float], objective_names: Iterable[str]) -> bool:
    values = [(left.get(name, 0.0), right.get(name, 0.0)) for name in objective_names]
    return all(a >= b for a, b in values) and any(a > b for a, b in values)


def pareto_fronts(candidates: list[dict[str, Any]], normalized: Mapping[str, Mapping[str, float]], objectives: list[dict[str, Any]]) -> list[list[str]]:
    remaining = {candidate["id"] for candidate in candidates}
    names = [item["name"] for item in objectives if item["weight"] > 0]
    fronts: list[list[str]] = []
    while remaining:
        front = sorted(
            candidate_id for candidate_id in remaining
            if not any(
                other != candidate_id and _dominates(normalized[other], normalized[candidate_id], names)
                for other in remaining
            )
        )
        if not front:
            raise ValueError("could not construct Pareto front")
        fronts.append(front)
        remaining.difference_update(front)
    return fronts


def plan_next_experiment(payload: Mapping[str, Any], *, created_at: str | None = None) -> dict[str, Any]:
    if payload.get("schema_version", 1) != 1:
        raise ValueError("unsupported next-experiment input schema")
    decision = _text(payload.get("decision"), "decision")
    objectives = _validate_objectives(payload.get("objectives"))
    candidates = _validate_candidates(payload.get("candidates"), objectives)
    constraints = payload.get("constraints")
    if not isinstance(constraints, Mapping):
        raise ValueError("constraints must be an object")
    batch_raw = constraints.get("batch_size", 0)
    group_raw = constraints.get("diversity_group_cap", constraints.get("scaffold_cap", batch_raw))
    controls_raw = constraints.get("minimum_controls", 0)
    if any(isinstance(item, bool) for item in (batch_raw, group_raw, controls_raw)):
        raise ValueError("batch size, diversity cap, and minimum controls must be integers")
    batch_size = int(batch_raw)
    budget = _number(constraints.get("budget", 0), "budget")
    group_cap = int(group_raw)
    minimum_controls = int(controls_raw)
    if batch_size < 1 or budget < 0 or group_cap < 1 or minimum_controls < 0:
        raise ValueError("batch size, budget, diversity cap, and minimum controls are invalid")
    uncertainty_weight = _number(payload.get("uncertainty_weight", 0.25), "uncertainty_weight")
    diversity_bonus = _number(payload.get("diversity_bonus", 0.1), "diversity_bonus")
    if uncertainty_weight < 0 or diversity_bonus < 0:
        raise ValueError("uncertainty_weight and diversity_bonus must be non-negative")
    claim_ids = sorted({_text(item, "claim_id") for item in payload.get("claim_ids", [])})

    eligible = [item for item in candidates if item["eligible"]]
    ineligible = [item for item in candidates if not item["eligible"]]
    if not eligible:
        raise ValueError("no eligible candidates")
    normalized, uncertainty_scores = _normalize(eligible, objectives)
    fronts = pareto_fronts(eligible, normalized, objectives)
    front_rank = {candidate_id: rank for rank, front in enumerate(fronts) for candidate_id in front}
    weight_total = sum(item["weight"] for item in objectives)
    by_id = {item["id"]: item for item in candidates}

    def base_utility(candidate: Mapping[str, Any]) -> float:
        objective_score = sum(
            objective["weight"] * normalized[candidate["id"]].get(objective["name"], 0.0)
            for objective in objectives
        ) / weight_total
        return objective_score + uncertainty_weight * uncertainty_scores[candidate["id"]]

    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    group_counts: Counter[str] = Counter()
    total_cost = 0.0
    rejection_reasons: dict[str, list[str]] = defaultdict(list)

    controls = sorted((item for item in eligible if item["control"]), key=lambda item: (item["cost"], item["id"]))
    if len(controls) < minimum_controls:
        raise ValueError(f"minimum_controls={minimum_controls} but only {len(controls)} eligible controls exist")
    for candidate in controls[:minimum_controls]:
        if total_cost + candidate["cost"] > budget or len(selected) >= batch_size:
            raise ValueError("required controls do not fit the batch or budget")
        if group_counts[candidate["diversity_group"]] >= group_cap:
            raise ValueError("required controls violate diversity_group_cap")
        selected.append(candidate)
        selected_ids.add(candidate["id"])
        group_counts[candidate["diversity_group"]] += 1
        total_cost += candidate["cost"]

    while len(selected) < batch_size:
        scored: list[tuple[float, int, str, dict[str, Any]]] = []
        for candidate in eligible:
            if candidate["id"] in selected_ids:
                continue
            if total_cost + candidate["cost"] > budget:
                rejection_reasons[candidate["id"]].append("budget")
                continue
            if group_counts[candidate["diversity_group"]] >= group_cap:
                rejection_reasons[candidate["id"]].append("diversity-group-cap")
                continue
            novelty = 1.0 if group_counts[candidate["diversity_group"]] == 0 else 0.0
            score = base_utility(candidate) + diversity_bonus * novelty - 0.01 * front_rank[candidate["id"]]
            scored.append((score, -front_rank[candidate["id"]], candidate["id"], candidate))
        if not scored:
            break
        scored.sort(key=lambda item: (-item[0], item[1], item[2]))
        candidate = scored[0][3]
        selected.append(candidate)
        selected_ids.add(candidate["id"])
        group_counts[candidate["diversity_group"]] += 1
        total_cost += candidate["cost"]

    selected_records = []
    for candidate in selected:
        selected_records.append({
            **candidate,
            "normalized_objectives": normalized[candidate["id"]],
            "uncertainty_score": uncertainty_scores[candidate["id"]],
            "pareto_front": front_rank[candidate["id"]],
            "base_utility": base_utility(candidate),
        })
    for candidate in ineligible:
        rejection_reasons[candidate["id"]].append(candidate["exclusion_reason"] or "ineligible")
    for candidate in eligible:
        if candidate["id"] not in selected_ids and not rejection_reasons[candidate["id"]]:
            rejection_reasons[candidate["id"]].append("not-selected-within-batch")

    expected_information_gain = sum(uncertainty_scores[item["id"]] for item in selected) / len(selected) if selected else 0.0
    material = {
        "schema_version": 1,
        "decision": decision,
        "status": "proposed",
        "executed": False,
        "created_at": created_at or _now(),
        "objectives": objectives,
        "constraints": {
            "batch_size": batch_size,
            "budget": budget,
            "diversity_group_cap": group_cap,
            "minimum_controls": minimum_controls,
        },
        "uncertainty_weight": uncertainty_weight,
        "diversity_bonus": diversity_bonus,
        "selected": selected_records,
        "selected_count": len(selected_records),
        "total_cost": total_cost,
        "remaining_budget": budget - total_cost,
        "diversity_groups": dict(sorted(group_counts.items())),
        "pareto_fronts": fronts,
        "expected_information_gain_proxy": expected_information_gain,
        "rejected": [
            {"id": candidate_id, "reasons": sorted(set(reasons)), "candidate": by_id[candidate_id]}
            for candidate_id, reasons in sorted(rejection_reasons.items())
        ],
        "claim_ids": claim_ids,
        "required_controls_satisfied": sum(item["control"] for item in selected) >= minimum_controls,
        "approval_required": True,
        "evidence_boundary": "This deterministic proposal ranks only declared candidate properties and constraints. It does not infer chemical similarity, validate uncertainty calibration, execute an experiment, or prove expected information gain."
    }
    fingerprint = _fingerprint(material)
    return {**material, "proposal_id": f"experiment-{fingerprint[:20]}", "fingerprint": fingerprint}


def validate_experiment_proposal(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != 1 or payload.get("status") != "proposed" or payload.get("executed") is not False:
        raise ValueError("invalid experiment proposal state")
    for field in ("proposal_id", "decision", "created_at", "evidence_boundary"):
        _text(payload.get(field), field)
    if not isinstance(payload.get("selected"), list) or not isinstance(payload.get("rejected"), list):
        raise ValueError("selected and rejected must be lists")
    material = dict(payload)
    proposal_id = str(material.pop("proposal_id"))
    fingerprint = str(material.pop("fingerprint", "")).lower()
    if _fingerprint(material) != fingerprint or proposal_id != f"experiment-{fingerprint[:20]}":
        raise ValueError("experiment proposal fingerprint or ID mismatch")
