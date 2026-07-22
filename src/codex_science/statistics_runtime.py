"""Deterministic, dependency-free statistical analysis for bounded research fixtures.

The runtime emphasizes effect sizes, uncertainty intervals, experimental units,
and randomization-based tests. It intentionally avoids pretending that a generic
p-value establishes a scientific claim.
"""
from __future__ import annotations

import itertools
import math
import random
import statistics
from collections import defaultdict
from typing import Any, Iterable, Mapping

from codex_science.safe_expression import canonical_sha256

MAX_ROWS = 100_000
MAX_REPLICATES = 100_000
MAX_EXACT_PERMUTATIONS = 100_000


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _quantile(values: list[float], probability: float) -> float:
    if not values:
        raise ValueError("cannot compute a quantile of an empty sample")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _median(values: Iterable[float]) -> float:
    data = list(values)
    if not data:
        raise ValueError("median requires observations")
    return float(statistics.median(data))


def _estimate(values_a: list[float], values_b: list[float], measure: str) -> float:
    if measure == "mean-difference":
        return statistics.fmean(values_b) - statistics.fmean(values_a)
    if measure == "median-difference":
        return _median(values_b) - _median(values_a)
    raise ValueError(f"unsupported estimand: {measure}")


def _sample_variance(values: list[float]) -> float:
    return statistics.variance(values) if len(values) > 1 else 0.0


def _hedges_g(values_a: list[float], values_b: list[float]) -> float | None:
    if len(values_a) < 2 or len(values_b) < 2:
        return None
    degrees = len(values_a) + len(values_b) - 2
    if degrees <= 0:
        return None
    pooled = ((len(values_a) - 1) * _sample_variance(values_a) + (len(values_b) - 1) * _sample_variance(values_b)) / degrees
    if pooled <= 0:
        return None
    correction = 1.0 - 3.0 / (4.0 * degrees - 1.0) if degrees > 1 else 1.0
    return correction * (statistics.fmean(values_b) - statistics.fmean(values_a)) / math.sqrt(pooled)


def _paired_standardized(differences: list[float]) -> float | None:
    if len(differences) < 2:
        return None
    standard_deviation = statistics.stdev(differences)
    if standard_deviation == 0:
        return None
    return statistics.fmean(differences) / standard_deviation


def _extreme(value: float, observed: float, alternative: str, *, tolerance: float = 1e-15) -> bool:
    if alternative == "two-sided":
        return abs(value) >= abs(observed) - tolerance
    if alternative == "greater":
        return value >= observed - tolerance
    if alternative == "less":
        return value <= observed + tolerance
    raise ValueError(f"unsupported alternative: {alternative}")


def _bootstrap_independent(
    values_a: list[float],
    values_b: list[float],
    measure: str,
    *,
    replicates: int,
    randomizer: random.Random,
) -> list[float]:
    estimates: list[float] = []
    for _ in range(replicates):
        sample_a = [values_a[randomizer.randrange(len(values_a))] for _ in values_a]
        sample_b = [values_b[randomizer.randrange(len(values_b))] for _ in values_b]
        estimates.append(_estimate(sample_a, sample_b, measure))
    return estimates


def _bootstrap_paired(
    differences: list[float],
    *,
    replicates: int,
    randomizer: random.Random,
    measure: str,
) -> list[float]:
    estimates: list[float] = []
    for _ in range(replicates):
        sample = [differences[randomizer.randrange(len(differences))] for _ in differences]
        estimates.append(statistics.fmean(sample) if measure == "mean-difference" else _median(sample))
    return estimates


def _permutation_independent(
    values_a: list[float],
    values_b: list[float],
    measure: str,
    alternative: str,
    *,
    replicates: int,
    randomizer: random.Random,
) -> tuple[float, int, bool]:
    observed = _estimate(values_a, values_b, measure)
    combined = values_a + values_b
    count_a = len(values_a)
    combinations = math.comb(len(combined), count_a)
    extreme = 0
    if combinations <= MAX_EXACT_PERMUTATIONS:
        total = 0
        indexes = range(len(combined))
        for selected in itertools.combinations(indexes, count_a):
            selected_set = set(selected)
            group_a = [combined[index] for index in selected]
            group_b = [combined[index] for index in indexes if index not in selected_set]
            extreme += int(_extreme(_estimate(group_a, group_b, measure), observed, alternative))
            total += 1
        return extreme / total, total, True
    total = replicates
    for _ in range(replicates):
        shuffled = list(combined)
        randomizer.shuffle(shuffled)
        extreme += int(_extreme(_estimate(shuffled[:count_a], shuffled[count_a:], measure), observed, alternative))
    return (extreme + 1) / (total + 1), total, False


def _permutation_paired(
    differences: list[float],
    measure: str,
    alternative: str,
    *,
    replicates: int,
    randomizer: random.Random,
) -> tuple[float, int, bool]:
    observed = statistics.fmean(differences) if measure == "mean-difference" else _median(differences)
    combinations = 2 ** len(differences)
    extreme = 0
    if combinations <= MAX_EXACT_PERMUTATIONS:
        for mask in range(combinations):
            signed = [value if mask & (1 << index) else -value for index, value in enumerate(differences)]
            estimate = statistics.fmean(signed) if measure == "mean-difference" else _median(signed)
            extreme += int(_extreme(estimate, observed, alternative))
        return extreme / combinations, combinations, True
    for _ in range(replicates):
        signed = [value if randomizer.random() < 0.5 else -value for value in differences]
        estimate = statistics.fmean(signed) if measure == "mean-difference" else _median(signed)
        extreme += int(_extreme(estimate, observed, alternative))
    return (extreme + 1) / (replicates + 1), replicates, False


def benjamini_hochberg(hypotheses: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    parsed: list[tuple[str, float]] = []
    for index, item in enumerate(hypotheses):
        identifier = str(item.get("id", "")).strip()
        if not identifier:
            raise ValueError(f"hypotheses[{index}].id is required")
        p_value = _finite(item.get("p_value"), f"hypotheses[{index}].p_value")
        if not 0 <= p_value <= 1:
            raise ValueError("p-values must be between 0 and 1")
        parsed.append((identifier, p_value))
    if len({identifier for identifier, _ in parsed}) != len(parsed):
        raise ValueError("hypothesis IDs must be unique")
    ordered = sorted(enumerate(parsed), key=lambda item: (item[1][1], item[1][0]))
    q_values = [1.0] * len(parsed)
    running = 1.0
    count = len(parsed)
    for reverse_rank, (original_index, (_identifier, p_value)) in enumerate(reversed(ordered), 1):
        rank = count - reverse_rank + 1
        running = min(running, p_value * count / rank)
        q_values[original_index] = min(1.0, running)
    return [
        {"id": identifier, "p_value": p_value, "q_value": q_values[index]}
        for index, (identifier, p_value) in enumerate(parsed)
    ]


def _prepare_rows(payload: Mapping[str, Any]) -> tuple[str, str, list[float], list[float], dict[str, Any], list[float] | None]:
    rows = payload.get("data")
    if not isinstance(rows, list) or not rows:
        raise ValueError("data must be a non-empty list of observations")
    if len(rows) > MAX_ROWS:
        raise ValueError(f"data exceeds {MAX_ROWS} rows")
    labels = payload.get("group_labels")
    if not isinstance(labels, list) or len(labels) != 2 or not all(isinstance(item, str) and item.strip() for item in labels):
        raise ValueError("group_labels must contain exactly two non-empty labels")
    group_a_label, group_b_label = labels[0].strip(), labels[1].strip()
    if group_a_label == group_b_label:
        raise ValueError("group labels must be distinct")
    analysis_type = str(payload.get("analysis_type", "independent"))
    if analysis_type not in {"independent", "paired"}:
        raise ValueError("analysis_type must be independent or paired")
    values_by_unit: dict[tuple[str, str], list[float]] = defaultdict(list)
    values_by_pair: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    missing_by_group = {group_a_label: 0, group_b_label: 0}
    raw_counts = {group_a_label: 0, group_b_label: 0}
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise ValueError(f"data[{index}] must be an object")
        group = str(row.get("group", "")).strip()
        if group not in {group_a_label, group_b_label}:
            raise ValueError(f"data[{index}].group is not one of group_labels")
        raw_counts[group] += 1
        value = row.get("value")
        if value is None or value == "":
            missing_by_group[group] += 1
            continue
        numeric = _finite(value, f"data[{index}].value")
        unit_id = str(row.get("unit_id", f"row-{index}")).strip()
        if not unit_id:
            raise ValueError(f"data[{index}].unit_id is empty")
        values_by_unit[(group, unit_id)].append(numeric)
        if analysis_type == "paired":
            pair_id = str(row.get("pair_id", "")).strip()
            if not pair_id:
                raise ValueError(f"data[{index}].pair_id is required for paired analysis")
            values_by_pair[pair_id][group].append(numeric)
    aggregation = str(payload.get("within_unit_aggregation", "mean"))
    if aggregation not in {"mean", "median"}:
        raise ValueError("within_unit_aggregation must be mean or median")

    def aggregate(values: list[float]) -> float:
        return statistics.fmean(values) if aggregation == "mean" else _median(values)

    values_a = [aggregate(values) for (group, _unit), values in sorted(values_by_unit.items()) if group == group_a_label]
    values_b = [aggregate(values) for (group, _unit), values in sorted(values_by_unit.items()) if group == group_b_label]
    differences: list[float] | None = None
    if analysis_type == "paired":
        differences = []
        incomplete_pairs = 0
        for pair_id, groups in sorted(values_by_pair.items()):
            if group_a_label not in groups or group_b_label not in groups:
                incomplete_pairs += 1
                continue
            differences.append(aggregate(groups[group_b_label]) - aggregate(groups[group_a_label]))
        values_a = [0.0] * len(differences)
        values_b = list(differences)
    else:
        incomplete_pairs = 0
    if not values_a or not values_b:
        raise ValueError("each analysis group needs at least one experimental unit")
    summary = {
        "raw_counts": raw_counts,
        "missing_counts": missing_by_group,
        "experimental_units": {group_a_label: len(values_a), group_b_label: len(values_b)},
        "within_unit_aggregation": aggregation,
        "duplicate_observations_aggregated": sum(max(0, len(values) - 1) for values in values_by_unit.values()),
        "incomplete_pairs_excluded": incomplete_pairs,
    }
    return group_a_label, group_b_label, values_a, values_b, summary, differences


def run_statistical_analysis(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported statistical-analysis input schema")
    analysis_id = str(payload.get("analysis_id", "")).strip()
    claim_id = str(payload.get("claim_id", "")).strip()
    design_id = str(payload.get("design_id", "")).strip()
    if not analysis_id or not claim_id or not design_id:
        raise ValueError("analysis_id, claim_id, and design_id are required")
    measure = str(payload.get("estimand", "mean-difference"))
    if measure not in {"mean-difference", "median-difference"}:
        raise ValueError("estimand must be mean-difference or median-difference")
    alternative = str(payload.get("alternative", "two-sided"))
    if alternative not in {"two-sided", "greater", "less"}:
        raise ValueError("invalid alternative")
    confidence_level = float(payload.get("confidence_level", 0.95))
    if not 0.5 < confidence_level < 1:
        raise ValueError("confidence_level must be between 0.5 and 1")
    seed = payload.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an explicit integer")
    bootstrap_replicates = int(payload.get("bootstrap_replicates", 5000))
    permutation_replicates = int(payload.get("permutation_replicates", 10_000))
    if not 200 <= bootstrap_replicates <= MAX_REPLICATES:
        raise ValueError(f"bootstrap_replicates must be between 200 and {MAX_REPLICATES}")
    if not 200 <= permutation_replicates <= MAX_REPLICATES:
        raise ValueError(f"permutation_replicates must be between 200 and {MAX_REPLICATES}")
    group_a_label, group_b_label, values_a, values_b, sample_summary, differences = _prepare_rows(payload)
    randomizer = random.Random(seed)
    analysis_type = str(payload.get("analysis_type", "independent"))
    if analysis_type == "paired":
        assert differences is not None
        estimate = statistics.fmean(differences) if measure == "mean-difference" else _median(differences)
        bootstrap = _bootstrap_paired(differences, replicates=bootstrap_replicates, randomizer=randomizer, measure=measure)
        p_value, permutation_count, exact = _permutation_paired(
            differences,
            measure,
            alternative,
            replicates=permutation_replicates,
            randomizer=randomizer,
        )
        standardized = _paired_standardized(differences) if measure == "mean-difference" else None
    else:
        estimate = _estimate(values_a, values_b, measure)
        bootstrap = _bootstrap_independent(
            values_a,
            values_b,
            measure,
            replicates=bootstrap_replicates,
            randomizer=randomizer,
        )
        p_value, permutation_count, exact = _permutation_independent(
            values_a,
            values_b,
            measure,
            alternative,
            replicates=permutation_replicates,
            randomizer=randomizer,
        )
        standardized = _hedges_g(values_a, values_b) if measure == "mean-difference" else None
    alpha = 1.0 - confidence_level
    lower = _quantile(bootstrap, alpha / 2.0)
    upper = _quantile(bootstrap, 1.0 - alpha / 2.0)
    hypotheses_raw = payload.get("hypotheses", [])
    if not isinstance(hypotheses_raw, list) or not all(isinstance(item, Mapping) for item in hypotheses_raw):
        raise ValueError("hypotheses must be a list of objects")
    adjusted = benjamini_hochberg(hypotheses_raw) if hypotheses_raw else []
    result: dict[str, Any] = {
        "schema_version": 1,
        "analysis_id": analysis_id,
        "claim_id": claim_id,
        "design_id": design_id,
        "analysis_type": analysis_type,
        "estimand": measure,
        "contrast": f"{group_b_label} - {group_a_label}",
        "alternative": alternative,
        "effect": {
            "estimate": estimate,
            "standardized_estimate": standardized,
            "standardized_measure": "hedges-g" if analysis_type == "independent" else "paired-standardized-mean",
        },
        "interval": {
            "confidence_level": confidence_level,
            "lower": lower,
            "upper": upper,
            "method": "deterministic-percentile-bootstrap",
            "replicates": bootstrap_replicates,
        },
        "test": {
            "p_value": p_value,
            "method": "exact-randomization" if exact else "monte-carlo-randomization",
            "permutations": permutation_count,
            "exact": exact,
        },
        "multiplicity": {
            "method": "benjamini-hochberg" if adjusted else "not-requested",
            "hypotheses": adjusted,
        },
        "sample": sample_summary,
        "seed": seed,
        "input_sha256": canonical_sha256(payload),
        "status": "completed",
        "limitations": [
            "Randomization inference is valid only for an exchangeability or sign-flip design justified by the study contract.",
            "Percentile bootstrap intervals may be inaccurate for small or highly irregular samples.",
            "A p-value does not establish scientific importance, causality, or replication.",
        ],
    }
    result["fingerprint"] = canonical_sha256(result)
    return result


def validate_statistical_analysis(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported statistical-analysis receipt schema")
    for field in ("analysis_id", "claim_id", "design_id", "analysis_type", "estimand", "contrast", "status"):
        if not str(payload.get(field, "")).strip():
            raise ValueError(f"{field} is required")
    effect = payload.get("effect")
    interval = payload.get("interval")
    test = payload.get("test")
    sample = payload.get("sample")
    if not all(isinstance(item, Mapping) for item in (effect, interval, test, sample)):
        raise ValueError("effect, interval, test, and sample must be objects")
    _finite(effect.get("estimate"), "effect estimate")
    lower = _finite(interval.get("lower"), "interval lower")
    upper = _finite(interval.get("upper"), "interval upper")
    if lower > upper:
        raise ValueError("interval lower exceeds upper")
    p_value = _finite(test.get("p_value"), "p_value")
    if not 0 <= p_value <= 1:
        raise ValueError("p_value must be between 0 and 1")
    if isinstance(payload.get("seed"), bool) or not isinstance(payload.get("seed"), int):
        raise ValueError("analysis receipt requires an explicit integer seed")
    if not isinstance(payload.get("limitations"), list) or not payload.get("limitations"):
        raise ValueError("analysis receipt requires limitations")
    material = dict(payload)
    fingerprint = str(material.pop("fingerprint", "")).lower()
    if len(fingerprint) != 64 or canonical_sha256(material) != fingerprint:
        raise ValueError("statistical-analysis fingerprint mismatch")


def review_statistical_analysis(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    try:
        validate_statistical_analysis(payload)
    except ValueError as error:
        return [{"code": "invalid-statistical-analysis", "severity": "critical", "message": str(error)}]
    findings: list[dict[str, str]] = []
    interval = payload["interval"]
    test = payload["test"]
    sample = payload["sample"]
    if int(interval.get("replicates", 0)) < 1000:
        findings.append({"code": "low-bootstrap-replicates", "severity": "minor", "message": "Bootstrap interval uses fewer than 1000 replicates."})
    if not bool(test.get("exact", False)) and int(test.get("permutations", 0)) < 1000:
        findings.append({"code": "low-permutation-replicates", "severity": "minor", "message": "Monte Carlo randomization test uses fewer than 1000 permutations."})
    hypotheses = payload.get("multiplicity", {}).get("hypotheses", [])
    if len(hypotheses) > 1 and payload.get("multiplicity", {}).get("method") == "not-requested":
        findings.append({"code": "multiplicity-uncontrolled", "severity": "major", "message": "Multiple hypotheses lack adjusted q-values."})
    if int(sample.get("duplicate_observations_aggregated", 0)) > 0 and not str(sample.get("within_unit_aggregation", "")):
        findings.append({"code": "experimental-unit-aggregation-missing", "severity": "critical", "message": "Repeated observations were not reduced to declared experimental units."})
    if payload.get("status") == "passed":
        findings.append({"code": "statistical-significance-presented-as-review-pass", "severity": "major", "message": "A statistical computation receipt must not use passed as a scientific conclusion status."})
    return findings
