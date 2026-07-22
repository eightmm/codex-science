"""Deterministic numerical-result verification with convergence and residual audits."""
from __future__ import annotations

import math
import statistics
from typing import Any, Mapping

from codex_science.safe_expression import canonical_sha256

MAX_REFINEMENTS = 1000


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _finding(code: str, severity: str, message: str) -> dict[str, str]:
    return {"code": code, "severity": severity, "message": message}


def _observed_orders(resolutions: list[float], errors: list[float]) -> list[float]:
    orders: list[float] = []
    for index in range(len(errors) - 1):
        coarse_error, fine_error = errors[index], errors[index + 1]
        coarse_h, fine_h = resolutions[index], resolutions[index + 1]
        if coarse_error <= 0 or fine_error <= 0 or coarse_h <= fine_h:
            continue
        ratio_h = coarse_h / fine_h
        if ratio_h <= 1:
            continue
        orders.append(math.log(coarse_error / fine_error) / math.log(ratio_h))
    return orders


def _difference_orders(resolutions: list[float], estimates: list[float]) -> list[float]:
    orders: list[float] = []
    if len(estimates) < 3:
        return orders
    for index in range(len(estimates) - 2):
        first = abs(estimates[index] - estimates[index + 1])
        second = abs(estimates[index + 1] - estimates[index + 2])
        ratio_1 = resolutions[index] / resolutions[index + 1]
        ratio_2 = resolutions[index + 1] / resolutions[index + 2]
        if first <= 0 or second <= 0 or ratio_1 <= 1 or ratio_2 <= 1:
            continue
        if not math.isclose(ratio_1, ratio_2, rel_tol=0.05, abs_tol=0.0):
            continue
        orders.append(math.log(first / second) / math.log(ratio_1))
    return orders


def run_numerical_verification(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported numerical-verification input schema")
    verification_id = str(payload.get("verification_id", "")).strip()
    claim_id = str(payload.get("claim_id", "")).strip()
    method = str(payload.get("method", "")).strip()
    if not verification_id or not claim_id or not method:
        raise ValueError("verification_id, claim_id, and method are required")
    raw_refinements = payload.get("refinements")
    if not isinstance(raw_refinements, list) or not 2 <= len(raw_refinements) <= MAX_REFINEMENTS:
        raise ValueError(f"refinements must contain 2 to {MAX_REFINEMENTS} levels")
    reference_value = payload.get("reference_value")
    reference = None if reference_value is None else _finite(reference_value, "reference_value")
    thresholds = payload.get("thresholds", {})
    if not isinstance(thresholds, Mapping):
        raise ValueError("thresholds must be an object")
    max_residual = None if thresholds.get("max_residual") is None else _finite(thresholds.get("max_residual"), "max_residual")
    max_invariant = None if thresholds.get("max_invariant_deviation") is None else _finite(thresholds.get("max_invariant_deviation"), "max_invariant_deviation")
    minimum_order = None if thresholds.get("minimum_order") is None else _finite(thresholds.get("minimum_order"), "minimum_order")
    max_cross_method_z = float(thresholds.get("max_cross_method_z", 3.0))
    if max_cross_method_z <= 0:
        raise ValueError("max_cross_method_z must be positive")

    refinements: list[dict[str, Any]] = []
    resolutions: list[float] = []
    estimates: list[float] = []
    errors: list[float] = []
    residuals: list[float] = []
    invariant_deviations: list[float] = []
    findings: list[dict[str, str]] = []
    for index, item in enumerate(raw_refinements):
        if not isinstance(item, Mapping):
            raise ValueError(f"refinements[{index}] must be an object")
        resolution = _finite(item.get("resolution"), f"refinements[{index}].resolution")
        estimate = _finite(item.get("estimate"), f"refinements[{index}].estimate")
        if resolution <= 0:
            raise ValueError("resolution values must be positive")
        if "error" in item:
            error = _finite(item.get("error"), f"refinements[{index}].error")
            if error < 0:
                raise ValueError("errors must be non-negative")
        elif reference is not None:
            error = abs(estimate - reference)
        else:
            error = None
        residual = None if item.get("residual") is None else abs(_finite(item.get("residual"), f"refinements[{index}].residual"))
        invariants_raw = item.get("invariants", {})
        if not isinstance(invariants_raw, Mapping):
            raise ValueError(f"refinements[{index}].invariants must be an object")
        invariants: dict[str, float] = {}
        for name, deviation in sorted(invariants_raw.items()):
            invariants[str(name)] = abs(_finite(deviation, f"invariant {name}"))
            invariant_deviations.append(invariants[str(name)])
        record = {
            "resolution": resolution,
            "estimate": estimate,
            "error": error,
            "residual": residual,
            "invariants": invariants,
        }
        refinements.append(record)
        resolutions.append(resolution)
        estimates.append(estimate)
        if error is not None:
            errors.append(error)
        if residual is not None:
            residuals.append(residual)
    if any(resolutions[index] <= resolutions[index + 1] for index in range(len(resolutions) - 1)):
        findings.append(_finding(
            "non-refining-resolution-sequence",
            "critical",
            "Resolution parameters must strictly decrease from coarse to fine.",
        ))
    if errors and len(errors) != len(refinements):
        findings.append(_finding(
            "partial-error-series",
            "major",
            "Only some refinement levels provide an error or reference-derived error.",
        ))
    if len(errors) == len(refinements):
        orders = _observed_orders(resolutions, errors)
        monotone = all(errors[index + 1] <= errors[index] for index in range(len(errors) - 1))
        if not monotone:
            findings.append(_finding(
                "nonmonotone-error",
                "major",
                "Reported error does not decrease monotonically under refinement.",
            ))
    else:
        orders = _difference_orders(resolutions, estimates)
        monotone = None
    if minimum_order is not None:
        if len(refinements) < 3:
            findings.append(_finding(
                "insufficient-refinement-levels",
                "critical",
                "A convergence-order claim requires at least three refinement levels.",
            ))
        elif not orders:
            findings.append(_finding(
                "observed-order-unavailable",
                "major",
                "Observed convergence order could not be estimated from the refinement series.",
            ))
        elif min(orders) < minimum_order:
            findings.append(_finding(
                "convergence-order-below-threshold",
                "major",
                f"Minimum observed order {min(orders):.6g} is below required {minimum_order:.6g}.",
            ))
    if max_residual is not None:
        if len(residuals) != len(refinements):
            findings.append(_finding(
                "residual-series-incomplete",
                "major",
                "A residual threshold is declared but some refinement levels lack residuals.",
            ))
        elif max(residuals) > max_residual:
            findings.append(_finding(
                "residual-threshold-failed",
                "major",
                f"Maximum residual {max(residuals):.6g} exceeds {max_residual:.6g}.",
            ))
    if max_invariant is not None:
        if not invariant_deviations:
            findings.append(_finding(
                "invariant-audit-missing",
                "major",
                "An invariant threshold is declared but no invariant deviations were recorded.",
            ))
        elif max(invariant_deviations) > max_invariant:
            findings.append(_finding(
                "invariant-threshold-failed",
                "major",
                f"Maximum invariant deviation {max(invariant_deviations):.6g} exceeds {max_invariant:.6g}.",
            ))
    solver = payload.get("solver", {})
    if not isinstance(solver, Mapping):
        raise ValueError("solver must be an object")
    if not str(solver.get("precision", "")).strip():
        findings.append(_finding(
            "floating-precision-unstated",
            "minor",
            "Floating-point or arithmetic precision is not recorded.",
        ))
    if solver.get("absolute_tolerance") is None and solver.get("relative_tolerance") is None:
        findings.append(_finding(
            "solver-tolerance-unstated",
            "minor",
            "Solver stopping tolerances are not recorded.",
        ))
    cross_method = payload.get("cross_method", [])
    if not isinstance(cross_method, list) or not all(isinstance(item, Mapping) for item in cross_method):
        raise ValueError("cross_method must be a list of objects")
    cross_records: list[dict[str, Any]] = []
    if cross_method:
        for index, item in enumerate(cross_method):
            name = str(item.get("method", "")).strip()
            if not name:
                raise ValueError(f"cross_method[{index}].method is required")
            estimate = _finite(item.get("estimate"), f"cross_method[{index}].estimate")
            uncertainty = abs(_finite(item.get("uncertainty"), f"cross_method[{index}].uncertainty"))
            cross_records.append({"method": name, "estimate": estimate, "uncertainty": uncertainty})
        baseline = cross_records[0]
        for item in cross_records[1:]:
            combined = math.hypot(baseline["uncertainty"], item["uncertainty"])
            difference = abs(baseline["estimate"] - item["estimate"])
            z_score = math.inf if combined == 0 and difference > 0 else (0.0 if combined == 0 else difference / combined)
            item["difference_from_first"] = difference
            item["combined_uncertainty_z"] = z_score
            if z_score > max_cross_method_z:
                findings.append(_finding(
                    "cross-method-disagreement",
                    "major",
                    f"Methods {baseline['method']} and {item['method']} disagree by {z_score:.3g} combined standard uncertainties.",
                ))
    status = "passed" if not any(item["severity"] in {"critical", "major"} for item in findings) else "findings"
    result: dict[str, Any] = {
        "schema_version": 1,
        "verification_id": verification_id,
        "claim_id": claim_id,
        "method": method,
        "status": status,
        "reference_value": reference,
        "refinements": refinements,
        "observed_orders": orders,
        "minimum_observed_order": min(orders) if orders else None,
        "error_monotone": monotone,
        "maximum_residual": max(residuals) if residuals else None,
        "maximum_invariant_deviation": max(invariant_deviations) if invariant_deviations else None,
        "cross_method": cross_records,
        "thresholds": dict(thresholds),
        "solver": dict(solver),
        "findings": findings,
        "input_sha256": canonical_sha256(payload),
        "limitations": [
            "Observed convergence on a finite refinement range does not prove asymptotic convergence outside that range.",
            "Agreement between implementations does not establish agreement with the governing physical model or experiment.",
        ],
    }
    result["fingerprint"] = canonical_sha256(result)
    return result


def validate_numerical_verification(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported numerical-verification receipt schema")
    for field in ("verification_id", "claim_id", "method", "status"):
        if not str(payload.get(field, "")).strip():
            raise ValueError(f"{field} is required")
    if payload.get("status") not in {"passed", "findings"}:
        raise ValueError("invalid numerical verification status")
    refinements = payload.get("refinements")
    findings = payload.get("findings")
    if not isinstance(refinements, list) or len(refinements) < 2:
        raise ValueError("numerical verification needs at least two refinements")
    if not isinstance(findings, list) or not all(isinstance(item, Mapping) for item in findings):
        raise ValueError("findings must be a list of objects")
    material = dict(payload)
    fingerprint = str(material.pop("fingerprint", "")).lower()
    if len(fingerprint) != 64 or canonical_sha256(material) != fingerprint:
        raise ValueError("numerical-verification fingerprint mismatch")


def review_numerical_verification(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    try:
        validate_numerical_verification(payload)
    except ValueError as error:
        return [_finding("invalid-numerical-verification", "critical", str(error))]
    findings = [dict(item) for item in payload.get("findings", [])]
    if payload.get("status") == "passed" and any(item.get("severity") in {"critical", "major"} for item in findings):
        findings.append(_finding(
            "unsafe-numerical-pass",
            "critical",
            "Numerical verification is passed despite blocking findings.",
        ))
    if payload.get("minimum_observed_order") is not None and len(payload.get("refinements", [])) < 3:
        findings.append(_finding(
            "order-claim-underidentified",
            "critical",
            "An observed-order claim has fewer than three refinement levels.",
        ))
    unique = {(item["code"], item["message"]): item for item in findings}
    return sorted(unique.values(), key=lambda item: (item.get("severity", ""), item["code"]))
