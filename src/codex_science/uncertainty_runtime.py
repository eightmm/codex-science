"""Deterministic linear and Monte Carlo uncertainty propagation."""
from __future__ import annotations

import math
import random
from typing import Any, Mapping

from codex_science.safe_expression import canonical_sha256, evaluate_expression, parse_expression

MAX_INPUTS = 64
MAX_SAMPLES = 1_000_000


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("quantile requires samples")
    if len(ordered) == 1:
        return ordered[0]
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _cholesky(matrix: list[list[float]], *, tolerance: float = 1e-12) -> list[list[float]]:
    size = len(matrix)
    lower = [[0.0] * size for _ in range(size)]
    for row in range(size):
        for column in range(row + 1):
            value = matrix[row][column] - sum(lower[row][offset] * lower[column][offset] for offset in range(column))
            if row == column:
                if value < -tolerance:
                    raise ValueError("covariance matrix is not positive semidefinite")
                lower[row][column] = math.sqrt(max(0.0, value))
            elif lower[column][column] > tolerance:
                lower[row][column] = value / lower[column][column]
            elif abs(value) > tolerance:
                raise ValueError("covariance matrix is singular and inconsistent")
    return lower


def _gradient(expression: str, names: list[str], means: list[float], uncertainties: list[float]) -> list[float]:
    parsed = parse_expression(expression, allowed_names=names)
    gradient: list[float] = []
    for index, name in enumerate(names):
        step = max(abs(means[index]) * 1e-6, uncertainties[index] * 1e-3, 1e-8)
        plus = dict(zip(names, means))
        minus = dict(zip(names, means))
        plus[name] += step
        minus[name] -= step
        numerator = float(evaluate_expression(parsed, plus)) - float(evaluate_expression(parsed, minus))
        derivative = numerator / (2.0 * step)
        if not math.isfinite(derivative):
            raise ValueError(f"non-finite numerical derivative for {name}")
        gradient.append(derivative)
    return gradient


def _variance(gradient: list[float], covariance: list[list[float]]) -> float:
    value = sum(
        gradient[row] * covariance[row][column] * gradient[column]
        for row in range(len(gradient))
        for column in range(len(gradient))
    )
    if value < -1e-12:
        raise ValueError("linear propagation produced negative variance")
    return max(0.0, value)


def run_uncertainty_propagation(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported uncertainty-propagation input schema")
    propagation_id = str(payload.get("propagation_id", "")).strip()
    claim_id = str(payload.get("claim_id", "")).strip()
    expression = str(payload.get("expression", "")).strip()
    if not propagation_id or not claim_id or not expression:
        raise ValueError("propagation_id, claim_id, and expression are required")
    raw_inputs = payload.get("inputs")
    if not isinstance(raw_inputs, list) or not 1 <= len(raw_inputs) <= MAX_INPUTS:
        raise ValueError(f"inputs must contain 1 to {MAX_INPUTS} records")
    names: list[str] = []
    means: list[float] = []
    uncertainties: list[float] = []
    units: list[str | None] = []
    for index, item in enumerate(raw_inputs):
        if not isinstance(item, Mapping):
            raise ValueError(f"inputs[{index}] must be an object")
        name = str(item.get("name", "")).strip()
        if not name.isidentifier():
            raise ValueError(f"inputs[{index}].name must be an identifier")
        if name in names:
            raise ValueError(f"duplicate uncertainty input: {name}")
        mean = _finite(item.get("mean"), f"inputs[{index}].mean")
        uncertainty = abs(_finite(item.get("standard_uncertainty"), f"inputs[{index}].standard_uncertainty"))
        names.append(name)
        means.append(mean)
        uncertainties.append(uncertainty)
        units.append(None if item.get("unit") is None else str(item.get("unit")))
    parsed = parse_expression(expression, allowed_names=names)
    nominal = float(evaluate_expression(parsed, dict(zip(names, means))))
    if not math.isfinite(nominal):
        raise ValueError("nominal expression value is not finite")
    covariance = [[0.0] * len(names) for _ in names]
    for index, uncertainty in enumerate(uncertainties):
        covariance[index][index] = uncertainty ** 2
    raw_covariance = payload.get("covariance", [])
    if not isinstance(raw_covariance, list) or not all(isinstance(item, Mapping) for item in raw_covariance):
        raise ValueError("covariance must be a list of objects")
    index_by_name = {name: index for index, name in enumerate(names)}
    for index, item in enumerate(raw_covariance):
        left = str(item.get("left", ""))
        right = str(item.get("right", ""))
        if left not in index_by_name or right not in index_by_name:
            raise ValueError(f"covariance[{index}] references an unknown input")
        value = _finite(item.get("value"), f"covariance[{index}].value")
        left_index, right_index = index_by_name[left], index_by_name[right]
        if left_index == right_index and not math.isclose(value, uncertainties[left_index] ** 2, rel_tol=1e-9, abs_tol=1e-15):
            raise ValueError("diagonal covariance conflicts with standard_uncertainty")
        covariance[left_index][right_index] = value
        covariance[right_index][left_index] = value
    lower = _cholesky(covariance)
    gradient = _gradient(expression, names, means, uncertainties)
    linear_variance = _variance(gradient, covariance)
    linear_uncertainty = math.sqrt(linear_variance)
    sensitivities = []
    for index, name in enumerate(names):
        contribution = gradient[index] ** 2 * covariance[index][index]
        sensitivities.append({
            "name": name,
            "derivative": gradient[index],
            "diagonal_variance_contribution": contribution,
            "fraction_of_linear_variance": None if linear_variance == 0 else contribution / linear_variance,
        })
    method = str(payload.get("method", "both"))
    if method not in {"linear", "monte-carlo", "both"}:
        raise ValueError("method must be linear, monte-carlo, or both")
    confidence_level = float(payload.get("confidence_level", 0.95))
    if not 0.5 < confidence_level < 1:
        raise ValueError("confidence_level must be between 0.5 and 1")
    seed = payload.get("seed")
    samples = int(payload.get("samples", 20_000))
    if method in {"monte-carlo", "both"}:
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise ValueError("Monte Carlo propagation requires an explicit integer seed")
        if not 100 <= samples <= MAX_SAMPLES:
            raise ValueError(f"samples must be between 100 and {MAX_SAMPLES}")
        randomizer = random.Random(seed)
        outputs: list[float] = []
        failures = 0
        for _ in range(samples):
            independent = [randomizer.gauss(0.0, 1.0) for _ in names]
            values: list[float] = []
            for row in range(len(names)):
                perturbation = sum(lower[row][column] * independent[column] for column in range(row + 1))
                values.append(means[row] + perturbation)
            try:
                output = float(evaluate_expression(parsed, dict(zip(names, values))))
                if math.isfinite(output):
                    outputs.append(output)
                else:
                    failures += 1
            except (ValueError, OverflowError, ZeroDivisionError):
                failures += 1
        if len(outputs) < max(10, int(0.9 * samples)):
            raise ValueError("too many Monte Carlo samples failed expression evaluation")
        monte_carlo_mean = sum(outputs) / len(outputs)
        monte_carlo_uncertainty = math.sqrt(sum((value - monte_carlo_mean) ** 2 for value in outputs) / max(1, len(outputs) - 1))
        alpha = 1.0 - confidence_level
        interval = [_quantile(outputs, alpha / 2.0), _quantile(outputs, 1.0 - alpha / 2.0)]
    else:
        outputs = []
        failures = 0
        monte_carlo_mean = None
        monte_carlo_uncertainty = None
        interval = None
    findings: list[dict[str, str]] = []
    if method in {"monte-carlo", "both"} and samples < 1000:
        findings.append({"code": "low-monte-carlo-samples", "severity": "minor", "message": "Monte Carlo propagation uses fewer than 1000 accepted samples."})
    if method == "both" and monte_carlo_uncertainty is not None:
        scale = max(linear_uncertainty, monte_carlo_uncertainty, 1e-15)
        uncertainty_discrepancy = abs(linear_uncertainty - monte_carlo_uncertainty) / scale
        mean_discrepancy = abs(nominal - float(monte_carlo_mean)) / scale
        if uncertainty_discrepancy > float(payload.get("nonlinearity_threshold", 0.25)) or mean_discrepancy > 0.25:
            findings.append({
                "code": "nonlinear-propagation-disagreement",
                "severity": "major",
                "message": "Linear and Monte Carlo propagation disagree materially; report the nonlinear distribution rather than only a first-order standard uncertainty.",
            })
    else:
        uncertainty_discrepancy = None
        mean_discrepancy = None
    result: dict[str, Any] = {
        "schema_version": 1,
        "propagation_id": propagation_id,
        "claim_id": claim_id,
        "expression": expression,
        "expression_sha256": parsed.sha256,
        "status": "findings" if any(item["severity"] in {"critical", "major"} for item in findings) else "passed",
        "inputs": [
            {"name": name, "mean": mean, "standard_uncertainty": uncertainty, "unit": unit}
            for name, mean, uncertainty, unit in zip(names, means, uncertainties, units)
        ],
        "covariance": covariance,
        "nominal_value": nominal,
        "linear": {
            "gradient": gradient,
            "standard_uncertainty": linear_uncertainty,
            "variance": linear_variance,
            "sensitivities": sensitivities,
        },
        "monte_carlo": None if method == "linear" else {
            "seed": seed,
            "requested_samples": samples,
            "accepted_samples": len(outputs),
            "failed_samples": failures,
            "mean": monte_carlo_mean,
            "standard_uncertainty": monte_carlo_uncertainty,
            "confidence_level": confidence_level,
            "interval": interval,
        },
        "method": method,
        "nonlinearity": {
            "relative_uncertainty_discrepancy": uncertainty_discrepancy,
            "mean_shift_in_uncertainty_units": mean_discrepancy,
        },
        "findings": findings,
        "input_sha256": canonical_sha256(payload),
        "limitations": [
            "The covariance model and input distributions are assumptions that must be justified independently.",
            "First-order propagation may fail for discontinuities, boundaries, ratios near zero, and strongly nonlinear models.",
        ],
    }
    result["fingerprint"] = canonical_sha256(result)
    return result


def validate_uncertainty_propagation(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported uncertainty-propagation receipt schema")
    for field in ("propagation_id", "claim_id", "expression", "status", "method"):
        if not str(payload.get(field, "")).strip():
            raise ValueError(f"{field} is required")
    if payload.get("status") not in {"passed", "findings"}:
        raise ValueError("invalid uncertainty propagation status")
    if not isinstance(payload.get("linear"), Mapping) or not isinstance(payload.get("findings"), list):
        raise ValueError("linear result and findings are required")
    material = dict(payload)
    fingerprint = str(material.pop("fingerprint", "")).lower()
    if len(fingerprint) != 64 or canonical_sha256(material) != fingerprint:
        raise ValueError("uncertainty-propagation fingerprint mismatch")


def review_uncertainty_propagation(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    try:
        validate_uncertainty_propagation(payload)
    except ValueError as error:
        return [{"code": "invalid-uncertainty-propagation", "severity": "critical", "message": str(error)}]
    findings = [dict(item) for item in payload.get("findings", [])]
    if payload.get("method") in {"monte-carlo", "both"} and payload.get("monte_carlo", {}).get("seed") is None:
        findings.append({"code": "uncertainty-seed-missing", "severity": "critical", "message": "Monte Carlo uncertainty receipt lacks a deterministic seed."})
    if payload.get("status") == "passed" and any(item.get("severity") in {"critical", "major"} for item in findings):
        findings.append({"code": "unsafe-uncertainty-pass", "severity": "critical", "message": "Uncertainty propagation is passed despite blocking findings."})
    return findings
