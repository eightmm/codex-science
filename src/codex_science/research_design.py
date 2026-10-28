"""Preregistered quantitative research-design contracts and deterministic audits."""
from __future__ import annotations

import json
from typing import Any, Mapping

from codex_science.safe_expression import canonical_sha256

ASSIGNMENT_TYPES = {"randomized", "observational", "quasi-experimental", "simulation", "descriptive"}
MULTIPLICITY_METHODS = {"none", "bonferroni", "holm", "benjamini-hochberg", "hierarchical", "gatekeeping", "custom"}
MISSING_STRATEGIES = {"complete-case", "multiple-imputation", "inverse-probability", "model-based", "none-expected", "custom"}


def _text(payload: Mapping[str, Any], field: str, label: str | None = None) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label or field} must be a non-empty string")
    return value.strip()


def _optional_text(payload: Mapping[str, Any], field: str, label: str) -> str:
    return "" if payload.get(field) is None else _text(payload, field, label)


def _boolean(payload: Mapping[str, Any], field: str, label: str) -> bool:
    value = payload.get(field)
    if value is None:
        return False
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be boolean")
    return value


def _positive_integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _object(payload: Mapping[str, Any], field: str) -> Mapping[str, Any]:
    value = payload.get(field)
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def _strings(value: Any, label: str, *, required: bool = False) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{label} must be a list of non-empty strings")
    result = [item.strip() for item in value]
    if required and not result:
        raise ValueError(f"{label} must be non-empty")
    return result


def _finding(code: str, severity: str, message: str) -> dict[str, str]:
    return {"code": code, "severity": severity, "message": message}


def validate_research_design(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    if type(payload.get("schema_version")) is not int or payload.get("schema_version") != 1:
        raise ValueError("unsupported research-design schema")
    _text(payload, "design_id")
    _text(payload, "question")
    _text(payload, "experimental_unit")
    _text(payload, "observational_unit")
    outcome = _object(payload, "outcome")
    _text(outcome, "name", "outcome.name")
    _text(outcome, "measurement", "outcome.measurement")
    estimand = _object(payload, "estimand")
    _text(estimand, "population", "estimand.population")
    _text(estimand, "contrast", "estimand.contrast")
    _text(estimand, "summary_measure", "estimand.summary_measure")
    assignment = _object(payload, "assignment")
    assignment_type = _text(assignment, "type", "assignment.type")
    if assignment_type not in ASSIGNMENT_TYPES:
        raise ValueError(f"invalid assignment type: {assignment_type}")
    analysis = _object(payload, "analysis")
    _text(analysis, "method", "analysis.method")
    endpoints = payload.get("primary_endpoints")
    if not isinstance(endpoints, list) or not endpoints or not all(isinstance(item, Mapping) for item in endpoints):
        raise ValueError("primary_endpoints must be a non-empty list of objects")
    endpoint_ids: set[str] = set()
    for index, endpoint in enumerate(endpoints):
        identifier = _text(endpoint, "id", f"primary_endpoints[{index}].id")
        if not identifier or identifier in endpoint_ids:
            raise ValueError(f"primary endpoint {index} has missing or duplicate id")
        endpoint_ids.add(identifier)
        _text(endpoint, "decision_threshold", f"primary_endpoints[{index}].decision_threshold")
    multiplicity = _object(payload, "multiplicity")
    method = _text(multiplicity, "method", "multiplicity.method")
    if method not in MULTIPLICITY_METHODS:
        raise ValueError(f"invalid multiplicity method: {method}")
    missing = _object(payload, "missing_data")
    missing_strategy = _text(missing, "strategy", "missing_data.strategy")
    if missing_strategy not in MISSING_STRATEGIES:
        raise ValueError(f"invalid missing-data strategy: {missing_strategy}")
    exclusions = _object(payload, "exclusions")
    stopping = _object(payload, "stopping")
    sample_size = _object(payload, "sample_size")
    _positive_integer(sample_size.get("planned"), "sample_size.planned")
    _strings([] if payload.get("sensitivity_analyses") is None else payload["sensitivity_analyses"], "sensitivity_analyses")
    _strings([] if payload.get("identification_assumptions") is None else payload["identification_assumptions"], "identification_assumptions")
    if not isinstance(payload.get("locked_before_outcomes"), bool):
        raise ValueError("locked_before_outcomes must be boolean")

    aggregation_unit = _optional_text(analysis, "aggregation_unit", "analysis.aggregation_unit")
    confounding_strategy = _optional_text(analysis, "confounding_strategy", "analysis.confounding_strategy")
    alpha_spending = _optional_text(stopping, "alpha_spending", "stopping.alpha_spending")
    decision_rule = _optional_text(stopping, "decision_rule", "stopping.decision_rule")
    rationale = _optional_text(sample_size, "rationale", "sample_size.rationale")
    assumptions = _optional_text(missing, "assumptions", "missing_data.assumptions")
    mechanism = _optional_text(assignment, "mechanism", "assignment.mechanism")
    cluster_adjustment = _boolean(analysis, "cluster_adjustment", "analysis.cluster_adjustment")
    causal = _boolean(estimand, "causal", "estimand.causal")
    subjective = _boolean(outcome, "subjective", "outcome.subjective")
    prespecified = _boolean(exclusions, "prespecified", "exclusions.prespecified")
    allocation_concealment = _boolean(assignment, "allocation_concealment", "assignment.allocation_concealment")
    blinding = {} if payload.get("blinding") is None else _object(payload, "blinding")
    outcome_assessor = _boolean(blinding, "outcome_assessor", "blinding.outcome_assessor")
    if exclusions.get("criteria") is not None:
        _strings(exclusions["criteria"], "exclusions.criteria")
    family_size = _positive_integer(len(endpoints) if multiplicity.get("family_size") is None else multiplicity["family_size"], "multiplicity.family_size")
    looks = _positive_integer(1 if stopping.get("planned_looks") is None else stopping["planned_looks"], "stopping.planned_looks")

    findings: list[dict[str, str]] = []
    experimental_unit = str(payload["experimental_unit"])
    observational_unit = str(payload["observational_unit"])
    if experimental_unit != observational_unit and not cluster_adjustment and aggregation_unit != experimental_unit:
        findings.append(_finding(
            "pseudoreplication-risk",
            "critical",
            "Observations are nested below the experimental unit without aggregation or cluster-aware analysis.",
        ))
    if payload.get("locked_before_outcomes") is not True:
        findings.append(_finding(
            "outcome-dependent-design",
            "major",
            "The primary design was not locked before outcome inspection.",
        ))
    if family_size < len(endpoints):
        findings.append(_finding(
            "multiplicity-family-understated",
            "major",
            "Multiplicity family_size is smaller than the declared primary endpoint family.",
        ))
    if family_size > 1 and method == "none":
        findings.append(_finding(
            "multiplicity-uncontrolled",
            "major",
            "Multiple primary hypotheses are declared without a multiplicity strategy.",
        ))
    if looks > 1 and not alpha_spending and not decision_rule:
        findings.append(_finding(
            "optional-stopping-uncontrolled",
            "critical",
            "Repeated outcome looks lack an alpha-spending or prespecified decision rule.",
        ))
    if not prespecified:
        findings.append(_finding(
            "posthoc-exclusion-risk",
            "major",
            "Exclusion criteria are not marked prespecified.",
        ))
    if not isinstance(exclusions.get("criteria"), list) or not exclusions.get("criteria"):
        findings.append(_finding(
            "exclusion-criteria-missing",
            "major",
            "Explicit exclusion criteria are missing.",
        ))
    if not rationale:
        findings.append(_finding(
            "sample-size-rationale-missing",
            "major",
            "The planned sample size has no precision, power, feasibility, or information rationale.",
        ))
    if missing_strategy != "none-expected" and not assumptions:
        findings.append(_finding(
            "missingness-assumptions-unstated",
            "major",
            "The missing-data strategy does not state its missingness assumptions.",
        ))
    if missing_strategy == "complete-case" and not payload.get("sensitivity_analyses"):
        findings.append(_finding(
            "complete-case-without-sensitivity",
            "minor",
            "Complete-case analysis has no declared missing-data sensitivity analysis.",
        ))
    identification = payload.get("identification_assumptions") or []
    if causal and not identification:
        findings.append(_finding(
            "causal-identification-missing",
            "critical",
            "A causal estimand is declared without explicit identification assumptions.",
        ))
    if causal and assignment_type == "observational" and not confounding_strategy:
        findings.append(_finding(
            "observational-confounding-unaddressed",
            "critical",
            "An observational causal analysis has no declared confounding strategy.",
        ))
    if assignment_type == "randomized":
        if not mechanism:
            findings.append(_finding(
                "randomization-mechanism-missing",
                "major",
                "Randomized assignment is claimed without an explicit randomization mechanism.",
            ))
        if not allocation_concealment:
            findings.append(_finding(
                "allocation-concealment-missing",
                "minor",
                "Randomized assignment does not record allocation concealment.",
            ))
    if subjective and not outcome_assessor:
        findings.append(_finding(
            "subjective-outcome-unblinded",
            "major",
            "A subjective outcome lacks blinded outcome assessment.",
        ))
    if not payload.get("sensitivity_analyses"):
        findings.append(_finding(
            "sensitivity-analysis-missing",
            "minor",
            "No sensitivity analysis is prespecified.",
        ))
    if "fingerprint" in payload:
        material = dict(payload)
        fingerprint = str(material.pop("fingerprint", "")).lower()
        if len(fingerprint) != 64 or canonical_sha256(material) != fingerprint:
            raise ValueError("research-design fingerprint mismatch")
    unique = {(item["code"], item["message"]): item for item in findings}
    return sorted(unique.values(), key=lambda item: (item["severity"], item["code"]))


def build_research_design(payload: Mapping[str, Any]) -> dict[str, Any]:
    material = dict(payload)
    material.pop("fingerprint", None)
    findings = validate_research_design(material)
    material["audit_status"] = "findings" if findings else "passed"
    material["audit_findings"] = findings
    material["fingerprint"] = canonical_sha256(material)
    return material


def review_research_design(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    try:
        findings = validate_research_design(payload)
    except ValueError as error:
        return [_finding("invalid-research-design", "critical", str(error))]
    recorded = payload.get("audit_findings", [])
    if recorded and recorded != findings:
        findings.append(_finding(
            "stale-research-design-audit",
            "major",
            "Recorded design findings differ from the current deterministic audit.",
        ))
    if payload.get("audit_status") == "passed" and findings:
        findings.append(_finding(
            "unsafe-research-design-pass",
            "critical",
            "Research design is marked passed despite blocking deterministic findings.",
        ))
    unique = {(item["code"], item["message"]): item for item in findings}
    return sorted(unique.values(), key=lambda item: (item["severity"], item["code"]))
