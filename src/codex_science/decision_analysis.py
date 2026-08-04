"""Deterministic finite decision analysis under uncertainty.

The runtime deliberately supports finite, one-stage decision tables.  It keeps
probabilities, preferences, and the selected decision criterion explicit so a
computed optimum cannot be mistaken for an unconditional recommendation.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

from codex_science.safe_expression import canonical_sha256


MAX_ACTIONS = 256
MAX_STATES = 256
MAX_EXPERIMENTS = 64
MAX_OUTCOMES = 256
PROBABILITY_TOLERANCE = 1e-9
DEFAULT_TIE_TOLERANCE = 1e-12

EXPECTED_CRITERIA = {"bayes-risk", "expected-utility", "expected-payoff"}
ALLOWED_CRITERIA = {
    "loss": {"bayes-risk", "minimax-loss", "minimax-regret"},
    "utility": {"expected-utility", "minimax-regret"},
    "payoff": {"expected-payoff", "minimax-regret"},
}
REQUIRED_RISK_ATTITUDE = {
    "loss": "encoded-in-loss",
    "utility": "encoded-in-utility",
    "payoff": "risk-neutral",
}


def _text(value: Any, label: str) -> str:
    result = str(value if value is not None else "").strip()
    if not result:
        raise ValueError(f"{label} is required")
    return result


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _probability(value: Any, label: str) -> float:
    result = _finite(value, label)
    if result < 0.0 or result > 1.0:
        raise ValueError(f"{label} must be between 0 and 1")
    return result


def _normalize_zero(value: float, tolerance: float = DEFAULT_TIE_TOLERANCE) -> float:
    return 0.0 if abs(value) <= tolerance else value


def _normalize_named_items(
    raw: Any,
    label: str,
    *,
    maximum: int,
) -> list[dict[str, str]]:
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{label} must be a non-empty list")
    if len(raw) > maximum:
        raise ValueError(f"{label} exceeds the limit of {maximum}")
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise ValueError(f"{label}[{index}] must be an object")
        identifier = _text(item.get("id"), f"{label}[{index}].id")
        if identifier in seen:
            raise ValueError(f"{label} IDs must be unique: {identifier}")
        seen.add(identifier)
        name = str(item.get("label", identifier)).strip() or identifier
        normalized.append({"id": identifier, "label": name})
    return sorted(normalized, key=lambda item: item["id"])


def _normalize_assumptions(raw: Any) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("assumptions must be a list")
    assumptions: list[str] = []
    for index, item in enumerate(raw):
        assumptions.append(_text(item, f"assumptions[{index}]"))
    return assumptions


def _normalize_distribution(
    probabilities: Mapping[str, float],
    label: str,
) -> dict[str, float]:
    """Return a deterministic, float-idempotent distribution."""
    identifiers = sorted(probabilities)
    values = [probabilities[identifier] for identifier in identifiers]
    total = math.fsum(values)
    if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=PROBABILITY_TOLERANCE):
        raise ValueError(f"{label} must sum to 1; observed {total:.12g}")
    if total == 1.0:
        return {identifier: value for identifier, value in zip(identifiers, values)}

    normalized = [value / total for value in values]
    if math.fsum(normalized) != 1.0:
        pivot = max(range(len(normalized)), key=normalized.__getitem__)
        other_total = math.fsum(
            value for index, value in enumerate(normalized) if index != pivot
        )
        center = 1.0 - other_total
        candidates = [center]
        lower = center
        upper = center
        for _ in range(16):
            lower = math.nextafter(lower, -math.inf)
            upper = math.nextafter(upper, math.inf)
            candidates.extend((lower, upper))
        for candidate in candidates:
            if not 0.0 <= candidate <= 1.0:
                continue
            adjusted = list(normalized)
            adjusted[pivot] = candidate
            if math.fsum(adjusted) == 1.0:
                normalized = adjusted
                break
        else:
            raise ValueError(f"{label} could not be normalized stably")
    return {
        identifier: value
        for identifier, value in zip(identifiers, normalized)
    }


def _normalize_problem(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported decision-analysis input schema")
    analysis_id = _text(payload.get("analysis_id"), "analysis_id")
    claim_id = _text(payload.get("claim_id"), "claim_id")
    question = _text(payload.get("question"), "question")
    information_boundary = _text(payload.get("information_boundary"), "information_boundary")
    consequence_horizon = _text(payload.get("consequence_horizon"), "consequence_horizon")
    state_model = _text(payload.get("state_model"), "state_model")
    if state_model != "exogenous":
        raise ValueError("state_model must be exogenous for the finite one-stage runtime")
    applicability = _text(payload.get("applicability"), "applicability")
    criterion = _text(payload.get("criterion"), "criterion")
    criterion_rationale = _text(payload.get("criterion_rationale"), "criterion_rationale")

    scale_raw = payload.get("scale")
    if not isinstance(scale_raw, Mapping):
        raise ValueError("scale must be an object")
    scale_kind = _text(scale_raw.get("kind"), "scale.kind")
    if scale_kind not in ALLOWED_CRITERIA:
        raise ValueError("scale.kind must be loss, utility, or payoff")
    unit = _text(scale_raw.get("unit"), "scale.unit")
    risk_attitude = _text(scale_raw.get("risk_attitude"), "scale.risk_attitude")
    required_attitude = REQUIRED_RISK_ATTITUDE[scale_kind]
    if risk_attitude != required_attitude:
        raise ValueError(
            f"scale.risk_attitude must be {required_attitude} for {scale_kind} values"
        )
    if criterion not in ALLOWED_CRITERIA[scale_kind]:
        allowed = ", ".join(sorted(ALLOWED_CRITERIA[scale_kind]))
        raise ValueError(f"criterion {criterion} is incompatible with {scale_kind}; use {allowed}")

    tie_tolerance = _finite(payload.get("tie_tolerance", DEFAULT_TIE_TOLERANCE), "tie_tolerance")
    if not 0.0 < tie_tolerance <= 1e-3:
        raise ValueError("tie_tolerance must be greater than 0 and at most 0.001")

    actions = _normalize_named_items(payload.get("actions"), "actions", maximum=MAX_ACTIONS)
    states_raw = payload.get("states")
    states = _normalize_named_items(states_raw, "states", maximum=MAX_STATES)
    action_ids = [item["id"] for item in actions]
    state_ids = [item["id"] for item in states]

    if not isinstance(states_raw, list):
        raise ValueError("states must be a list")
    priors_by_id: dict[str, float] = {}
    any_prior = False
    for index, item in enumerate(states_raw):
        assert isinstance(item, Mapping)
        state_id = _text(item.get("id"), f"states[{index}].id")
        if "prior" in item:
            any_prior = True
            priors_by_id[state_id] = _probability(item.get("prior"), f"states[{index}].prior")
    if any_prior and set(priors_by_id) != set(state_ids):
        raise ValueError("priors must be supplied for every state or for no states")
    if priors_by_id:
        priors_by_id = _normalize_distribution(priors_by_id, "state priors")
    if criterion in EXPECTED_CRITERIA and not priors_by_id:
        raise ValueError(f"criterion {criterion} requires a prior for every state")

    values_raw = payload.get("values")
    if not isinstance(values_raw, list):
        raise ValueError("values must be a list")
    expected_cells = len(action_ids) * len(state_ids)
    if len(values_raw) != expected_cells:
        raise ValueError(
            f"values must contain exactly one cell for every action/state pair ({expected_cells})"
        )
    value_map: dict[tuple[str, str], float] = {}
    for index, cell in enumerate(values_raw):
        if not isinstance(cell, Mapping):
            raise ValueError(f"values[{index}] must be an object")
        action = _text(cell.get("action"), f"values[{index}].action")
        state = _text(cell.get("state"), f"values[{index}].state")
        if action not in action_ids:
            raise ValueError(f"values[{index}] references unknown action: {action}")
        if state not in state_ids:
            raise ValueError(f"values[{index}] references unknown state: {state}")
        key = (action, state)
        if key in value_map:
            raise ValueError(f"duplicate value for action {action} and state {state}")
        value_map[key] = _finite(cell.get("value"), f"values[{index}].value")
    missing = [(action, state) for action in action_ids for state in state_ids if (action, state) not in value_map]
    if missing:
        raise ValueError(f"value matrix is incomplete; first missing cell is {missing[0]}")

    experiments_raw = payload.get("experiments", [])
    if not isinstance(experiments_raw, list):
        raise ValueError("experiments must be a list")
    if len(experiments_raw) > MAX_EXPERIMENTS:
        raise ValueError(f"experiments exceeds the limit of {MAX_EXPERIMENTS}")
    if experiments_raw and criterion not in EXPECTED_CRITERIA:
        raise ValueError("experiments require bayes-risk, expected-utility, or expected-payoff")
    experiments: list[dict[str, Any]] = []
    experiment_ids: set[str] = set()
    for experiment_index, experiment in enumerate(experiments_raw):
        if not isinstance(experiment, Mapping):
            raise ValueError(f"experiments[{experiment_index}] must be an object")
        experiment_id = _text(experiment.get("id"), f"experiments[{experiment_index}].id")
        if experiment_id in experiment_ids:
            raise ValueError(f"experiment IDs must be unique: {experiment_id}")
        experiment_ids.add(experiment_id)
        cost = _finite(
            experiment.get("cost_in_scale_units", 0.0),
            f"experiments[{experiment_index}].cost_in_scale_units",
        )
        if cost < 0.0:
            raise ValueError("experiment cost_in_scale_units cannot be negative")
        outcomes_raw = experiment.get("outcomes")
        if not isinstance(outcomes_raw, list) or not outcomes_raw:
            raise ValueError(f"experiments[{experiment_index}].outcomes must be non-empty")
        if len(outcomes_raw) > MAX_OUTCOMES:
            raise ValueError(f"experiment outcomes exceeds the limit of {MAX_OUTCOMES}")
        outcomes: list[dict[str, Any]] = []
        outcome_ids: set[str] = set()
        likelihood_sums = {state: 0.0 for state in state_ids}
        for outcome_index, outcome in enumerate(outcomes_raw):
            if not isinstance(outcome, Mapping):
                raise ValueError(
                    f"experiments[{experiment_index}].outcomes[{outcome_index}] must be an object"
                )
            outcome_id = _text(
                outcome.get("id"),
                f"experiments[{experiment_index}].outcomes[{outcome_index}].id",
            )
            if outcome_id in outcome_ids:
                raise ValueError(f"outcome IDs must be unique within experiment {experiment_id}")
            outcome_ids.add(outcome_id)
            likelihoods_raw = outcome.get("likelihoods")
            if not isinstance(likelihoods_raw, Mapping):
                raise ValueError(f"outcome {outcome_id} likelihoods must be an object")
            if set(map(str, likelihoods_raw.keys())) != set(state_ids):
                raise ValueError(f"outcome {outcome_id} likelihoods must name every state exactly once")
            likelihoods: dict[str, float] = {}
            for state in state_ids:
                probability = _probability(
                    likelihoods_raw.get(state),
                    f"experiment {experiment_id} outcome {outcome_id} likelihood {state}",
                )
                likelihoods[state] = probability
                likelihood_sums[state] += probability
            outcomes.append({"id": outcome_id, "likelihoods": likelihoods})
        for state, total in likelihood_sums.items():
            if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=PROBABILITY_TOLERANCE):
                raise ValueError(
                    f"experiment {experiment_id} likelihoods for state {state} must sum to 1; observed {total:.12g}"
                )
            normalized_column = _normalize_distribution(
                {
                    str(outcome["id"]): float(outcome["likelihoods"][state])
                    for outcome in outcomes
                },
                f"experiment {experiment_id} likelihoods for state {state}",
            )
            for outcome in outcomes:
                outcome["likelihoods"][state] = normalized_column[str(outcome["id"])]
        experiments.append(
            {
                "id": experiment_id,
                "label": str(experiment.get("label", experiment_id)).strip() or experiment_id,
                "cost_in_scale_units": cost,
                "outcomes": sorted(outcomes, key=lambda item: item["id"]),
            }
        )

    sensitivity_raw = payload.get("sensitivity")
    sensitivity: dict[str, Any] | None = None
    if sensitivity_raw is not None:
        if not isinstance(sensitivity_raw, Mapping):
            raise ValueError("sensitivity must be an object")
        route = sensitivity_raw.get("two_state_prior")
        if not isinstance(route, Mapping):
            raise ValueError("sensitivity.two_state_prior must be an object")
        if criterion not in EXPECTED_CRITERIA:
            raise ValueError("prior sensitivity requires an expected-value criterion")
        if len(state_ids) != 2:
            raise ValueError("two_state_prior sensitivity requires exactly two states")
        focus_state = _text(route.get("state_id"), "sensitivity.two_state_prior.state_id")
        if focus_state not in state_ids:
            raise ValueError(f"sensitivity state is unknown: {focus_state}")
        minimum = _probability(route.get("minimum", 0.0), "sensitivity.two_state_prior.minimum")
        maximum = _probability(route.get("maximum", 1.0), "sensitivity.two_state_prior.maximum")
        if not minimum < maximum:
            raise ValueError("sensitivity prior minimum must be less than maximum")
        sensitivity = {
            "two_state_prior": {
                "state_id": focus_state,
                "minimum": minimum,
                "maximum": maximum,
            }
        }

    normalized_states = []
    labels_by_state = {item["id"]: item["label"] for item in states}
    for state in state_ids:
        record: dict[str, Any] = {"id": state, "label": labels_by_state[state]}
        if priors_by_id:
            record["prior"] = priors_by_id[state]
        normalized_states.append(record)
    normalized_values = [
        {"action": action, "state": state, "value": value_map[(action, state)]}
        for action in action_ids
        for state in state_ids
    ]
    problem: dict[str, Any] = {
        "schema_version": 1,
        "analysis_id": analysis_id,
        "claim_id": claim_id,
        "question": question,
        "information_boundary": information_boundary,
        "consequence_horizon": consequence_horizon,
        "state_model": state_model,
        "applicability": applicability,
        "criterion": criterion,
        "criterion_rationale": criterion_rationale,
        "scale": {
            "kind": scale_kind,
            "unit": unit,
            "risk_attitude": risk_attitude,
        },
        "tie_tolerance": tie_tolerance,
        "actions": actions,
        "states": normalized_states,
        "values": normalized_values,
        "experiments": sorted(experiments, key=lambda item: item["id"]),
        "assumptions": _normalize_assumptions(payload.get("assumptions")),
    }
    if sensitivity is not None:
        problem["sensitivity"] = sensitivity
    return problem


def _optimal_actions(
    scores: Mapping[str, float],
    direction: str,
    tolerance: float,
) -> tuple[list[str], float]:
    if not scores:
        raise ValueError("cannot choose from an empty score table")
    target = min(scores.values()) if direction == "minimize" else max(scores.values())
    selected = sorted(
        action
        for action, value in scores.items()
        if math.isclose(value, target, rel_tol=0.0, abs_tol=tolerance)
    )
    return selected, _normalize_zero(target, tolerance)


def _result_for_scores(
    criterion: str,
    scores: Mapping[str, float],
    direction: str,
    tolerance: float,
) -> dict[str, Any]:
    selected, target = _optimal_actions(scores, direction, tolerance)
    return {
        "criterion": criterion,
        "direction": direction,
        "scores": [
            {"action": action, "value": _normalize_zero(scores[action], tolerance)}
            for action in sorted(scores)
        ],
        "optimal_actions": selected,
        "optimal_value": target,
    }


def _expected_scores(
    actions: list[str],
    states: list[str],
    values: Mapping[tuple[str, str], float],
    probabilities: Mapping[str, float],
) -> dict[str, float]:
    return {
        action: math.fsum(probabilities[state] * values[(action, state)] for state in states)
        for action in actions
    }


def _regret_table(
    actions: list[str],
    states: list[str],
    values: Mapping[tuple[str, str], float],
    direction: str,
    tolerance: float,
) -> tuple[dict[tuple[str, str], float], dict[str, float]]:
    regrets: dict[tuple[str, str], float] = {}
    for state in states:
        state_values = [values[(action, state)] for action in actions]
        best = min(state_values) if direction == "minimize" else max(state_values)
        for action in actions:
            raw = values[(action, state)] - best if direction == "minimize" else best - values[(action, state)]
            regrets[(action, state)] = max(0.0, _normalize_zero(raw, tolerance))
    maximum = {action: max(regrets[(action, state)] for state in states) for action in actions}
    return regrets, maximum


def _dominance(
    actions: list[str],
    states: list[str],
    values: Mapping[tuple[str, str], float],
    direction: str,
    tolerance: float,
) -> list[dict[str, Any]]:
    dominated_by: dict[str, list[str]] = {action: [] for action in actions}
    for challenger in actions:
        for incumbent in actions:
            if challenger == incumbent:
                continue
            challenger_values = [values[(challenger, state)] for state in states]
            incumbent_values = [values[(incumbent, state)] for state in states]
            if direction == "minimize":
                no_worse = all(a <= b + tolerance for a, b in zip(challenger_values, incumbent_values))
                strictly_better = any(a < b - tolerance for a, b in zip(challenger_values, incumbent_values))
            else:
                no_worse = all(a >= b - tolerance for a, b in zip(challenger_values, incumbent_values))
                strictly_better = any(a > b + tolerance for a, b in zip(challenger_values, incumbent_values))
            if no_worse and strictly_better:
                dominated_by[incumbent].append(challenger)
    return [
        {"action": action, "dominated_by": sorted(dominators)}
        for action, dominators in sorted(dominated_by.items())
        if dominators
    ]


def _criterion_results(
    problem: Mapping[str, Any],
    actions: list[str],
    states: list[str],
    values: Mapping[tuple[str, str], float],
    priors: Mapping[str, float],
    direction: str,
    tolerance: float,
) -> tuple[dict[str, dict[str, Any]], dict[tuple[str, str], float]]:
    kind = str(problem["scale"]["kind"])
    results: dict[str, dict[str, Any]] = {}
    if priors:
        expected = _expected_scores(actions, states, values, priors)
        expected_name = {
            "loss": "bayes-risk",
            "utility": "expected-utility",
            "payoff": "expected-payoff",
        }[kind]
        results[expected_name] = _result_for_scores(expected_name, expected, direction, tolerance)
    if kind == "loss":
        worst_loss = {action: max(values[(action, state)] for state in states) for action in actions}
        results["minimax-loss"] = _result_for_scores(
            "minimax-loss", worst_loss, "minimize", tolerance
        )
    regrets, maximum_regret = _regret_table(actions, states, values, direction, tolerance)
    results["minimax-regret"] = _result_for_scores(
        "minimax-regret", maximum_regret, "minimize", tolerance
    )
    return results, regrets


def _information_value(
    problem: Mapping[str, Any],
    actions: list[str],
    states: list[str],
    values: Mapping[tuple[str, str], float],
    priors: Mapping[str, float],
    baseline: Mapping[str, Any],
    direction: str,
    tolerance: float,
) -> dict[str, Any] | None:
    experiments = problem.get("experiments", [])
    if not experiments:
        return None
    baseline_value = float(baseline["optimal_value"])
    if direction == "minimize":
        perfect_value = math.fsum(
            priors[state] * min(values[(action, state)] for action in actions) for state in states
        )
        evpi = baseline_value - perfect_value
    else:
        perfect_value = math.fsum(
            priors[state] * max(values[(action, state)] for action in actions) for state in states
        )
        evpi = perfect_value - baseline_value
    evpi = max(0.0, _normalize_zero(evpi, tolerance))
    experiment_results: list[dict[str, Any]] = []
    for experiment in experiments:
        outcome_results: list[dict[str, Any]] = []
        preposterior_terms: list[float] = []
        for outcome in experiment["outcomes"]:
            marginal = math.fsum(
                priors[state] * float(outcome["likelihoods"][state]) for state in states
            )
            if marginal == 0.0:
                outcome_results.append(
                    {
                        "outcome": outcome["id"],
                        "probability": 0.0,
                        "status": "unreachable",
                        "posterior": None,
                        "optimal_actions": [],
                        "optimal_value": None,
                    }
                )
                continue
            posterior = {
                state: priors[state] * float(outcome["likelihoods"][state]) / marginal
                for state in states
            }
            posterior_total = math.fsum(posterior.values())
            posterior = {state: posterior[state] / posterior_total for state in states}
            scores = _expected_scores(actions, states, values, posterior)
            selected, optimal_value = _optimal_actions(scores, direction, tolerance)
            preposterior_terms.append(marginal * optimal_value)
            outcome_results.append(
                {
                    "outcome": outcome["id"],
                    "probability": marginal,
                    "status": "reachable",
                    "posterior": posterior,
                    "optimal_actions": selected,
                    "optimal_value": optimal_value,
                }
            )
        preposterior_value = math.fsum(preposterior_terms)
        gross = (
            baseline_value - preposterior_value
            if direction == "minimize"
            else preposterior_value - baseline_value
        )
        if gross < -max(tolerance, PROBABILITY_TOLERANCE):
            raise ValueError(f"experiment {experiment['id']} produced negative information value")
        gross = max(0.0, _normalize_zero(gross, tolerance))
        if gross > evpi + max(tolerance, PROBABILITY_TOLERANCE):
            raise ValueError(f"experiment {experiment['id']} exceeds perfect information value")
        cost = float(experiment["cost_in_scale_units"])
        net = _normalize_zero(gross - cost, tolerance)
        if net > tolerance:
            decision = "worth-cost"
        elif net < -tolerance:
            decision = "not-worth-cost"
        else:
            decision = "indifferent-within-tolerance"
        experiment_results.append(
            {
                "experiment": experiment["id"],
                "cost_in_scale_units": cost,
                "preposterior_value": preposterior_value,
                "gross_evsi": gross,
                "net_evsi": net,
                "decision": decision,
                "outcome_policy": outcome_results,
            }
        )
    return {
        "basis": str(problem["criterion"]),
        "perfect_information_value": perfect_value,
        "evpi": evpi,
        "experiments": experiment_results,
    }


def _prior_sensitivity(
    problem: Mapping[str, Any],
    actions: list[str],
    states: list[str],
    values: Mapping[tuple[str, str], float],
    direction: str,
    tolerance: float,
) -> dict[str, Any] | None:
    sensitivity = problem.get("sensitivity")
    if not isinstance(sensitivity, Mapping):
        return None
    route = sensitivity["two_state_prior"]
    focus = str(route["state_id"])
    other = next(state for state in states if state != focus)
    minimum = float(route["minimum"])
    maximum = float(route["maximum"])

    def scores_at(probability: float) -> dict[str, float]:
        return {
            action: probability * values[(action, focus)] + (1.0 - probability) * values[(action, other)]
            for action in actions
        }

    points = [minimum, maximum]
    for index, action_a in enumerate(actions):
        intercept_a = values[(action_a, other)]
        slope_a = values[(action_a, focus)] - intercept_a
        for action_b in actions[index + 1 :]:
            intercept_b = values[(action_b, other)]
            slope_b = values[(action_b, focus)] - intercept_b
            denominator = slope_a - slope_b
            if math.isclose(denominator, 0.0, rel_tol=0.0, abs_tol=tolerance):
                continue
            crossing = (intercept_b - intercept_a) / denominator
            if minimum - tolerance <= crossing <= maximum + tolerance:
                points.append(min(maximum, max(minimum, crossing)))
    points.sort()
    unique_points: list[float] = []
    for point in points:
        if not unique_points or not math.isclose(
            point, unique_points[-1], rel_tol=0.0, abs_tol=tolerance
        ):
            unique_points.append(_normalize_zero(point, tolerance))

    raw_regions: list[dict[str, Any]] = []
    for lower, upper in zip(unique_points, unique_points[1:]):
        if upper - lower <= tolerance:
            continue
        midpoint = (lower + upper) / 2.0
        selected, _ = _optimal_actions(scores_at(midpoint), direction, tolerance)
        raw_regions.append(
            {
                "minimum": lower,
                "maximum": upper,
                "optimal_actions": selected,
            }
        )
    regions: list[dict[str, Any]] = []
    for region in raw_regions:
        if (
            regions
            and regions[-1]["optimal_actions"] == region["optimal_actions"]
            and math.isclose(
                float(regions[-1]["maximum"]),
                float(region["minimum"]),
                rel_tol=0.0,
                abs_tol=tolerance,
            )
        ):
            regions[-1]["maximum"] = region["maximum"]
        else:
            regions.append(dict(region))

    boundary_candidates: list[dict[str, Any]] = []
    for point in unique_points:
        selected, value = _optimal_actions(scores_at(point), direction, tolerance)
        boundary_candidates.append(
            {
                "prior": point,
                "optimal_actions": selected,
                "optimal_value": value,
            }
        )
    boundaries: list[dict[str, Any]] = []
    for index, boundary in enumerate(boundary_candidates):
        if index in {0, len(boundary_candidates) - 1}:
            boundaries.append(boundary)
            continue
        left = raw_regions[index - 1]["optimal_actions"]
        right = raw_regions[index]["optimal_actions"]
        at_boundary = boundary["optimal_actions"]
        if left != right or at_boundary != left or at_boundary != right:
            boundaries.append(boundary)
    interior_policies = {tuple(region["optimal_actions"]) for region in regions}
    return {
        "state_id": focus,
        "complement_state_id": other,
        "range": {"minimum": minimum, "maximum": maximum},
        "regions": regions,
        "boundaries": boundaries,
        "decision_changes_within_range": len(interior_policies) > 1,
    }


def run_decision_analysis(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize and solve one bounded finite decision problem."""
    problem = _normalize_problem(payload)
    actions = [item["id"] for item in problem["actions"]]
    states = [item["id"] for item in problem["states"]]
    values = {
        (str(item["action"]), str(item["state"])): float(item["value"])
        for item in problem["values"]
    }
    priors = {
        str(item["id"]): float(item["prior"])
        for item in problem["states"]
        if "prior" in item
    }
    kind = str(problem["scale"]["kind"])
    direction = "minimize" if kind == "loss" else "maximize"
    tolerance = float(problem["tie_tolerance"])
    criteria, regrets = _criterion_results(
        problem, actions, states, values, priors, direction, tolerance
    )
    selected = criteria[str(problem["criterion"])]
    dominated = _dominance(actions, states, values, direction, tolerance)
    information = _information_value(
        problem, actions, states, values, priors, selected, direction, tolerance
    )
    sensitivity = _prior_sensitivity(problem, actions, states, values, direction, tolerance)
    if sensitivity and sensitivity["decision_changes_within_range"]:
        status = "decision-sensitive"
    elif len(selected["optimal_actions"]) > 1:
        status = "multiple-optima"
    else:
        status = "completed"

    result: dict[str, Any] = {
        "schema_version": 1,
        "analysis_id": problem["analysis_id"],
        "claim_id": problem["claim_id"],
        "question": problem["question"],
        "problem": problem,
        "criterion_results": [criteria[name] for name in sorted(criteria)],
        "selected_criterion": problem["criterion"],
        "recommendation": {
            "status": status,
            "optimal_actions": list(selected["optimal_actions"]),
            "optimal_value": selected["optimal_value"],
            "conditional_on": "recorded probabilities, values, criterion, and information boundary",
        },
        "dominated_actions": dominated,
        "regret_table": [
            {
                "action": action,
                "state": state,
                "regret": _normalize_zero(regrets[(action, state)], tolerance),
            }
            for action in actions
            for state in states
        ],
        "information_value": information,
        "sensitivity": sensitivity,
        "input_sha256": canonical_sha256(problem),
        "status": status,
        "limitations": [
            "The result is conditional on the recorded finite action/state table, probabilities, values, and criterion.",
            "Payoff is treated as utility only when risk-neutrality is explicitly declared; utility or loss elicitation is not validated by this computation.",
            "The runtime does not identify causal effects, solve strategic games, or handle MDP, POMDP, or continuous decision spaces.",
        ],
    }
    result["fingerprint"] = canonical_sha256(result)
    return result


def validate_decision_analysis(payload: Mapping[str, Any]) -> None:
    """Validate both receipt integrity and deterministic recomputation."""
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported decision-analysis receipt schema")
    for field in ("analysis_id", "claim_id", "question", "selected_criterion", "status"):
        _text(payload.get(field), field)
    if not isinstance(payload.get("problem"), Mapping):
        raise ValueError("decision-analysis problem is required")
    if not isinstance(payload.get("recommendation"), Mapping):
        raise ValueError("decision-analysis recommendation is required")
    if not isinstance(payload.get("criterion_results"), list) or not payload.get("criterion_results"):
        raise ValueError("decision-analysis criterion_results are required")
    if not isinstance(payload.get("limitations"), list) or not payload.get("limitations"):
        raise ValueError("decision-analysis limitations are required")
    material = dict(payload)
    fingerprint = str(material.pop("fingerprint", "")).lower()
    if len(fingerprint) != 64 or canonical_sha256(material) != fingerprint:
        raise ValueError("decision-analysis fingerprint mismatch")
    recomputed = run_decision_analysis(payload["problem"])
    if recomputed != dict(payload):
        raise ValueError("decision-analysis receipt does not match deterministic recomputation")


def review_decision_analysis(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    try:
        validate_decision_analysis(payload)
    except ValueError as error:
        return [{"code": "invalid-decision-analysis", "severity": "critical", "message": str(error)}]
    findings: list[dict[str, str]] = []
    status = str(payload.get("status"))
    if status == "decision-sensitive":
        findings.append(
            {
                "code": "decision-sensitive",
                "severity": "minor",
                "message": "The preferred action changes within the declared prior sensitivity range.",
            }
        )
    if status == "multiple-optima":
        findings.append(
            {
                "code": "multiple-optima",
                "severity": "minor",
                "message": "Several actions are optimal within the declared tie tolerance; no tie was silently broken.",
            }
        )
    information = payload.get("information_value")
    if isinstance(information, Mapping):
        evpi = float(information["evpi"])
        for experiment in information.get("experiments", []):
            if float(experiment["gross_evsi"]) > evpi + PROBABILITY_TOLERANCE:
                findings.append(
                    {
                        "code": "evsi-exceeds-evpi",
                        "severity": "critical",
                        "message": f"Experiment {experiment['experiment']} exceeds the perfect-information bound.",
                    }
                )
    return findings


def render_decision_analysis(payload: Mapping[str, Any]) -> str:
    """Render a compact human-first summary of a validated receipt."""
    validate_decision_analysis(payload)
    recommendation = payload["recommendation"]
    problem = payload["problem"]
    labels = {item["id"]: item["label"] for item in problem["actions"]}
    chosen = ", ".join(labels.get(action, action) for action in recommendation["optimal_actions"])
    lines = [
        "# Statistical decision analysis",
        "",
        f"- Question: {payload['question']}",
        f"- Criterion: `{payload['selected_criterion']}` ({problem['criterion_rationale']})",
        f"- Conditional action set: **{chosen}**",
        f"- Criterion value: {recommendation['optimal_value']:.12g} {problem['scale']['unit']}",
        f"- Status: `{payload['status']}`",
        f"- Applicability: {problem['applicability']}",
        "",
        "## Criterion comparison",
        "",
    ]
    for result in payload["criterion_results"]:
        optimal = ", ".join(labels.get(action, action) for action in result["optimal_actions"])
        lines.append(
            f"- `{result['criterion']}`: {optimal} at {result['optimal_value']:.12g} {problem['scale']['unit']}"
        )
    dominated = payload.get("dominated_actions", [])
    if dominated:
        lines.extend(["", "## Dominance", ""])
        for item in dominated:
            action = labels.get(item["action"], item["action"])
            dominators = ", ".join(
                labels.get(dominator, dominator) for dominator in item["dominated_by"]
            )
            lines.append(f"- {action} is weakly dominated by: {dominators}.")
    information = payload.get("information_value")
    if isinstance(information, Mapping):
        lines.extend(["", "## Information value", "", f"- EVPI: {information['evpi']:.12g} {problem['scale']['unit']}"])
        for experiment in information["experiments"]:
            lines.append(
                f"- `{experiment['experiment']}`: gross EVSI {experiment['gross_evsi']:.12g}, "
                f"cost {experiment['cost_in_scale_units']:.12g}, net EVSI {experiment['net_evsi']:.12g} "
                f"{problem['scale']['unit']} (`{experiment['decision']}`)"
            )
            for outcome in experiment["outcome_policy"]:
                if outcome["status"] == "unreachable":
                    lines.append(
                        f"  - Outcome `{outcome['outcome']}`: unreachable; posterior policy undefined."
                    )
                    continue
                outcome_actions = ", ".join(
                    labels.get(action, action) for action in outcome["optimal_actions"]
                )
                posterior = ", ".join(
                    f"P({state})={probability:.12g}"
                    for state, probability in sorted(outcome["posterior"].items())
                )
                lines.append(
                    f"  - Outcome `{outcome['outcome']}` (P={outcome['probability']:.12g}): "
                    f"{outcome_actions}; posterior {posterior}."
                )
    sensitivity = payload.get("sensitivity")
    if isinstance(sensitivity, Mapping):
        lines.extend(["", "## Prior sensitivity", ""])
        for region in sensitivity["regions"]:
            actions = ", ".join(labels.get(action, action) for action in region["optimal_actions"])
            lines.append(
                f"- P({sensitivity['state_id']}) in ({region['minimum']:.12g}, {region['maximum']:.12g}): {actions}"
            )
        lines.append("- Exact evaluated boundaries:")
        for boundary in sensitivity["boundaries"]:
            boundary_actions = ", ".join(
                labels.get(action, action) for action in boundary["optimal_actions"]
            )
            lines.append(
                f"  - P({sensitivity['state_id']})={boundary['prior']:.12g}: {boundary_actions}"
            )
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "This is a conditional policy under the recorded probabilities, values, criterion, and information boundary. It is not an unconditional factual, causal, clinical, legal, or financial recommendation.",
            "",
        ]
    )
    return "\n".join(lines)
