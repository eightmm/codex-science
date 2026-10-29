"""Deterministic, non-executing multi-objective next-experiment planning.

The planner ranks only declared candidate properties. It does not infer chemical
similarity, biological validity, or calibrated information gain from a model
name. Controls and scientific constraints remain explicit inputs.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from fractions import Fraction
from typing import Any, Iterable, Mapping

from codex_science.safe_expression import _finite_real, _required_text


DIRECTIONS = {"maximize", "minimize"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    except ValueError as error:
        raise ValueError("planner values must be finite JSON numbers") from error


def _fingerprint(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _text(value: Any, label: str) -> str:
    return _required_text(value, label)


def _number(value: Any, label: str) -> float:
    return _finite_real(value, label)


def _boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be boolean")
    return value


def _decimal(value: float) -> Fraction:
    """Preserve declared decimal boundaries without a floating-point tolerance."""
    return Fraction(str(value))


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
        objectives.append({"name": name, "direction": direction, "weight": weight, "required": _boolean(item.get("required", True), f"objective {name} required")})
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
        eligible = _boolean(item.get("eligible", True), f"candidate {candidate_id} eligible")
        control = _boolean(item.get("control", False), f"candidate {candidate_id} control")
        properties_raw = item.get("properties")
        if not isinstance(properties_raw, Mapping):
            raise ValueError(f"candidate {candidate_id} properties must be an object")
        missing = sorted(required - set(properties_raw))
        if eligible and missing:
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
            "control": control,
            "eligible": eligible,
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
            if maximum == minimum:
                score = 1.0
            elif math.isfinite(maximum - minimum):
                score = (value - minimum) / (maximum - minimum)
            else:
                score = float((_decimal(value) - _decimal(minimum)) / (_decimal(maximum) - _decimal(minimum)))
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
    if type(payload.get("schema_version", 1)) is not int or payload.get("schema_version", 1) != 1:
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
    if any(not isinstance(item, int) or isinstance(item, bool) for item in (batch_raw, group_raw, controls_raw)):
        raise ValueError("batch size, diversity cap, and minimum controls must be integers")
    batch_size = batch_raw
    budget = _number(constraints.get("budget", 0), "budget")
    budget_exact = _decimal(budget)
    group_cap = group_raw
    minimum_controls = controls_raw
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
    weight_total = _number(sum(item["weight"] for item in objectives), "objective weight total")
    by_id = {item["id"]: item for item in candidates}

    def base_utility(candidate: Mapping[str, Any]) -> float:
        objective_score = sum(
            objective["weight"] * normalized[candidate["id"]].get(objective["name"], 0.0)
            for objective in objectives
        ) / weight_total
        return _number(objective_score + uncertainty_weight * uncertainty_scores[candidate["id"]], "candidate base utility")

    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    group_counts: Counter[str] = Counter()
    total_cost = Fraction(0)
    costs = {item["id"]: _decimal(item["cost"]) for item in eligible}
    rejection_reasons: dict[str, list[str]] = defaultdict(list)

    controls = sorted((item for item in eligible if item["control"]), key=lambda item: (item["cost"], item["id"]))
    if len(controls) < minimum_controls:
        raise ValueError(f"minimum_controls={minimum_controls} but only {len(controls)} eligible controls exist")
    if minimum_controls > batch_size:
        raise ValueError("required controls do not fit the batch or budget")
    # Cheapest-first under per-group caps minimizes the cost of the required set.
    for candidate in controls:
        if len(selected) == minimum_controls:
            break
        if group_counts[candidate["diversity_group"]] >= group_cap:
            continue
        if total_cost + costs[candidate["id"]] > budget_exact:
            raise ValueError("required controls do not fit the batch or budget")
        selected.append(candidate)
        selected_ids.add(candidate["id"])
        group_counts[candidate["diversity_group"]] += 1
        total_cost += costs[candidate["id"]]
    if len(selected) < minimum_controls:
        raise ValueError("required controls violate diversity_group_cap")

    while len(selected) < batch_size:
        scored: list[tuple[float, int, str, dict[str, Any]]] = []
        for candidate in eligible:
            if candidate["id"] in selected_ids:
                continue
            if total_cost + costs[candidate["id"]] > budget_exact:
                rejection_reasons[candidate["id"]].append("budget")
                continue
            if group_counts[candidate["diversity_group"]] >= group_cap:
                rejection_reasons[candidate["id"]].append("diversity-group-cap")
                continue
            novelty = 1.0 if group_counts[candidate["diversity_group"]] == 0 else 0.0
            score = _number(base_utility(candidate) + diversity_bonus * novelty - 0.01 * front_rank[candidate["id"]], "candidate selection score")
            scored.append((score, -front_rank[candidate["id"]], candidate["id"], candidate))
        if not scored:
            break
        scored.sort(key=lambda item: (-item[0], item[1], item[2]))
        candidate = scored[0][3]
        selected.append(candidate)
        selected_ids.add(candidate["id"])
        group_counts[candidate["diversity_group"]] += 1
        total_cost += costs[candidate["id"]]

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
        "total_cost": float(total_cost),
        "remaining_budget": float(budget_exact - total_cost),
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


def plan_discriminating_experiment(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Rank declared experiments by hypothesis-interval separation, never proxy EIG."""
    if payload.get("policy", "discriminate_first_v1") != "discriminate_first_v1":
        raise ValueError("unsupported discrimination policy")
    hypotheses = payload.get("hypotheses")
    candidates = payload.get("candidates")
    if not isinstance(hypotheses, list) or len(hypotheses) < 2 or not isinstance(candidates, list) or not candidates:
        raise ValueError("at least two hypotheses and one candidate are required")
    hypothesis_ids = sorted(
        _strict_text(x.get("id"), "hypothesis id") for x in hypotheses if isinstance(x, Mapping)
    )
    if len(hypothesis_ids) != len(hypotheses) or len(set(hypothesis_ids)) != len(hypothesis_ids): raise ValueError("hypothesis IDs are invalid")
    budget = _number(payload.get("budget"), "budget")
    if budget < 0: raise ValueError("budget must be non-negative")
    scored = []
    candidate_ids: set[str] = set()
    for raw in candidates:
        if not isinstance(raw, Mapping): raise ValueError("candidate must be an object")
        ident = _strict_text(raw.get("id"), "candidate id")
        if ident in candidate_ids:
            raise ValueError(f"duplicate candidate ID: {ident}")
        candidate_ids.add(ident)
        cost = _number(raw.get("cost"), "candidate cost")
        control_cost = _number(raw.get("control_cost", 0), "candidate control_cost")
        resolution = _number(raw.get("resolution"), "candidate resolution")
        controls = raw.get("controls")
        predictions = raw.get("predictions")
        if (
            cost < 0 or control_cost < 0 or resolution <= 0
            or not isinstance(controls, list) or not controls
            or not all(isinstance(control, str) and control.strip() for control in controls)
            or not isinstance(predictions, Mapping) or set(predictions) != set(hypothesis_ids)
        ):
            raise ValueError("candidate controls, predictions, or resolution are invalid")
        pairs = []
        for left_i, left in enumerate(hypothesis_ids):
            a = predictions[left]
            if not isinstance(a, list) or len(a) != 2:
                raise ValueError("prediction interval is invalid")
            a_low, a_high = _number(a[0], "prediction"), _number(a[1], "prediction")
            if a_low > a_high:
                raise ValueError("prediction interval is invalid")
            for right in hypothesis_ids[left_i + 1:]:
                b = predictions[right]
                if not isinstance(b, list) or len(b) != 2:
                    raise ValueError("prediction interval is invalid")
                b_low, b_high = _number(b[0], "prediction"), _number(b[1], "prediction")
                if b_low > b_high:
                    raise ValueError("prediction interval is invalid")
                gap = max(_decimal(a_low) - _decimal(b_high), _decimal(b_low) - _decimal(a_high), Fraction(0))
                if gap >= _decimal(resolution): pairs.append([left, right])
        reasons = []
        total_cost_exact = _decimal(cost) + _decimal(control_cost)
        # Round only the reported cost; feasibility still uses the exact sum.
        try:
            total_cost = float(total_cost_exact)
        except OverflowError as error:
            raise ValueError("candidate total cost must be finite") from error
        if total_cost_exact > _decimal(budget): reasons.append("budget")
        if not pairs: reasons.append("no-distinguishable-pair-at-declared-resolution")
        scored.append({"id": ident, "cost": cost, "control_cost": control_cost, "total_cost": total_cost, "resolution": resolution, "controls": list(controls), "predictions": dict(predictions), "distinguishable_pairs": pairs, "reasons": reasons})
    ranked = sorted(scored, key=lambda x: (bool(x["reasons"]), -len(x["distinguishable_pairs"]), x["total_cost"], x["id"]))
    selected = next((x for x in ranked if not x["reasons"]), None)
    material = {"schema_version": 1, "policy": "discriminate_first_v1", "budget": budget, "hypothesis_ids": hypothesis_ids, "selected": selected, "ranked": ranked, "evidence_boundary": "Ranks only declared interval separation, controls, resolution, and cost. It is not expected information gain or EVSI."}
    return {**material, "fingerprint": _fingerprint(material)}


def _strict_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} is required")
    return value.strip()
