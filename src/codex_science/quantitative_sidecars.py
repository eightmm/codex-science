"""Validation and cross-link review for quantitative research sidecars."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

from codex_science.decision_analysis import review_decision_analysis, validate_decision_analysis
from codex_science.math_contracts import (
    math_review_findings,
    validate_mathematical_claim,
    validate_proof_obligation_graph,
    validate_proof_receipt,
)
from codex_science.numerical_verification import review_numerical_verification, validate_numerical_verification
from codex_science.research_design import review_research_design, validate_research_design
from codex_science.safe_expression import validate_counterexample_receipt
from codex_science.statistics_runtime import review_statistical_analysis, validate_statistical_analysis
from codex_science.uncertainty_runtime import review_uncertainty_propagation, validate_uncertainty_propagation
from codex_science.units_runtime import review_dimension_check, validate_dimension_check

QUANTITATIVE_KINDS = {
    "research-design",
    "mathematical-claim",
    "proof-obligation-graph",
    "proof-receipt",
    "counterexample-search",
    "formal-proof-check",
    "statistical-analysis",
    "decision-analysis",
    "numerical-verification",
    "dimension-check",
    "uncertainty-propagation",
}


def empty_quantitative_sidecars() -> dict[str, list[dict[str, Any]]]:
    return {
        "research_designs": [],
        "mathematical_claims": [],
        "proof_obligation_graphs": [],
        "proof_receipts": [],
        "counterexample_receipts": [],
        "formal_proof_checks": [],
        "statistical_analyses": [],
        "decision_analyses": [],
        "numerical_verifications": [],
        "dimension_checks": [],
        "uncertainty_propagations": [],
    }


RECEIPT_SCRIPTS = {
    "statistical-analysis": "run_statistical_analysis.py",
    "decision-analysis": "run_decision_analysis.py",
    "numerical-verification": "verify_numerical_result.py",
    "dimension-check": "check_dimensions.py",
    "uncertainty-propagation": "propagate_uncertainty.py",
    "counterexample-search": "search_counterexample.py",
    "research-design": "validate_research_design.py",
}


def validate_quantitative_sidecar(
    kind: str, payload: Mapping[str, Any], result: dict[str, Any], *, bundle_root: Path | None = None,
) -> None:
    try:
        _validate_quantitative_sidecar(kind, payload, result, bundle_root=bundle_root)
    except ValueError as exc:
        script = RECEIPT_SCRIPTS.get(kind)
        if script is None or payload.get("schema_version") == 1:
            raise
        raise ValueError(
            f"{exc}; `{kind}` is a receipt written by scripts/{script} --output; generate it with that "
            "script, or register a hand-written results file under a non-receipt kind with "
            "package_run.py refresh --kind PATH=KIND"
        ) from exc


def _validate_quantitative_sidecar(
    kind: str, payload: Mapping[str, Any], result: dict[str, Any], *, bundle_root: Path | None = None,
) -> None:
    if kind == "research-design":
        validate_research_design(payload)
        result["research_designs"].append(dict(payload))
    elif kind == "mathematical-claim":
        validate_mathematical_claim(payload)
        result["mathematical_claims"].append(dict(payload))
    elif kind == "proof-obligation-graph":
        validate_proof_obligation_graph(payload)
        result["proof_obligation_graphs"].append(dict(payload))
    elif kind == "proof-receipt":
        validate_proof_receipt(payload, bundle_root=bundle_root)
        result["proof_receipts"].append(dict(payload))
    elif kind == "counterexample-search":
        validate_counterexample_receipt(payload)
        result["counterexample_receipts"].append(dict(payload))
    elif kind == "formal-proof-check":
        receipt = payload.get("proof_receipt")
        if not isinstance(receipt, Mapping):
            raise ValueError("formal-proof-check requires proof_receipt")
        validate_proof_receipt(receipt, bundle_root=bundle_root)
        result["formal_proof_checks"].append(dict(payload))
        result["proof_receipts"].append(dict(receipt))
    elif kind == "statistical-analysis":
        validate_statistical_analysis(payload)
        result["statistical_analyses"].append(dict(payload))
    elif kind == "decision-analysis":
        validate_decision_analysis(payload)
        result["decision_analyses"].append(dict(payload))
    elif kind == "numerical-verification":
        validate_numerical_verification(payload)
        result["numerical_verifications"].append(dict(payload))
    elif kind == "dimension-check":
        validate_dimension_check(payload)
        result["dimension_checks"].append(dict(payload))
    elif kind == "uncertainty-propagation":
        validate_uncertainty_propagation(payload)
        result["uncertainty_propagations"].append(dict(payload))
    else:
        raise ValueError(f"unsupported quantitative sidecar kind: {kind}")


def _invalid(message: str) -> dict[str, str]:
    return {"code": "quantitative-sidecar-invalid", "severity": "critical", "message": message}


def _id_list(owner: Mapping[str, Any], key: str, findings: list[dict[str, str]]) -> list[Any]:
    value = owner.get(key, [])
    if isinstance(value, (list, tuple)):
        return list(value)
    findings.append(_invalid(f"Mathematical claim {owner.get('claim_id')} has malformed {key}: expected a list, got {type(value).__name__}."))
    return []


def _duplicate_id_findings(label: str, key: str, items: list[Mapping[str, Any]]) -> list[dict[str, str]]:
    # Byte-identical re-registration of one sidecar is idempotent; only conflicting payloads share an id wrongly.
    distinct = {(str(item[key]), json.dumps(item, sort_keys=True, default=str)) for item in items if item.get(key) is not None}
    counts = Counter(value for value, _ in distinct)
    return [
        {
            "code": "quantitative-duplicate-id",
            "severity": "major",
            "message": f"{label} {key} {value} is used by {count} sidecars; ids must be unique within a sidecar kind.",
        }
        for value, count in sorted(counts.items())
        if count > 1
    ]


def review_quantitative_sidecars(sidecars: Mapping[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []

    def section(key: str) -> list[Mapping[str, Any]]:
        value = sidecars.get(key, [])
        if value is None or not isinstance(value, (list, tuple)):
            findings.append(_invalid(f"Quantitative sidecar section {key} must be a list, got {type(value).__name__}."))
            return []
        items = [item for item in value if isinstance(item, Mapping)]
        if len(items) != len(value):
            findings.append(_invalid(f"Quantitative sidecar section {key} contains {len(value) - len(items)} non-object entries."))
        return items

    designs = section("research_designs")
    claims = section("mathematical_claims")
    proofs = section("proof_receipts")
    counters = section("counterexample_receipts")
    graphs = section("proof_obligation_graphs")
    analyses = section("statistical_analyses")
    decisions = section("decision_analyses")
    numerical = section("numerical_verifications")
    dimensions = section("dimension_checks")
    uncertainty = section("uncertainty_propagations")

    for design in designs:
        findings.extend(review_research_design(design))
    for analysis in analyses:
        findings.extend(review_statistical_analysis(analysis))
    for decision in decisions:
        findings.extend(review_decision_analysis(decision))
    for receipt in numerical:
        findings.extend(review_numerical_verification(receipt))
    for receipt in dimensions:
        findings.extend(review_dimension_check(receipt))
    for receipt in uncertainty:
        findings.extend(review_uncertainty_propagation(receipt))
    findings.extend(math_review_findings(claims, proofs, counters, graphs))

    for label, key, items in (
        ("Research design", "design_id", designs),
        ("Statistical analysis", "analysis_id", analyses),
        ("Decision analysis", "analysis_id", decisions),
        ("Numerical verification", "verification_id", numerical),
        ("Dimension check", "check_id", dimensions),
        ("Uncertainty propagation", "propagation_id", uncertainty),
    ):
        findings.extend(_duplicate_id_findings(label, key, items))

    design_ids = {str(item.get("design_id")) for item in designs}
    claim_ids = {str(item.get("claim_id")) for item in claims}
    proof_ids = {str(item.get("receipt_id")) for item in proofs}
    counter_ids = {str(item.get("receipt_id") or item.get("fingerprint")) for item in counters}
    for analysis in analyses:
        if str(analysis.get("design_id")) not in design_ids:
            findings.append({
                "code": "statistical-design-missing",
                "severity": "major",
                "message": f"Statistical analysis {analysis.get('analysis_id')} has no matching research-design sidecar; a research-design sidecar is written by scripts/validate_research_design.py --output and registered as kind research-design with the matching design_id.",
            })
    for collection_name, collection in (
        ("statistical analysis", analyses),
        ("numerical verification", numerical),
        ("dimension check", dimensions),
        ("uncertainty propagation", uncertainty),
    ):
        for item in collection:
            claim_id = str(item.get("claim_id", ""))
            if claim_id not in claim_ids:
                findings.append({
                    "code": "quantitative-claim-missing",
                    "severity": "major",
                    "message": f"{collection_name.title()} {item.get('analysis_id') or item.get('verification_id') or item.get('check_id') or item.get('propagation_id')} references missing mathematical claim {claim_id}.",
                })
    # Decision-analysis receipts are accepted without a claim sidecar; they are cross-checked only once claims exist.
    for item in decisions if claims else []:
        claim_id = str(item.get("claim_id", ""))
        if claim_id not in claim_ids:
            findings.append({
                "code": "quantitative-claim-missing",
                "severity": "major",
                "message": f"Decision Analysis {item.get('analysis_id')} references missing mathematical claim {claim_id}.",
            })
    for claim in claims:
        for receipt_id in _id_list(claim, "proof_receipt_ids", findings):
            if str(receipt_id) not in proof_ids:
                findings.append({
                    "code": "missing-proof-receipt",
                    "severity": "major",
                    "message": f"Mathematical claim {claim.get('claim_id')} references missing proof receipt {receipt_id}.",
                })
        for receipt_id in _id_list(claim, "counterexample_receipt_ids", findings):
            if str(receipt_id) not in counter_ids:
                findings.append({
                    "code": "missing-counterexample-receipt",
                    "severity": "major",
                    "message": f"Mathematical claim {claim.get('claim_id')} references missing counterexample receipt {receipt_id}.",
                })
    by_claim: dict[str, list[str]] = defaultdict(list)
    for item in analyses:
        by_claim[str(item.get("claim_id"))].append("statistical-analysis")
    for item in decisions:
        by_claim[str(item.get("claim_id"))].append("decision-analysis")
    for item in numerical:
        by_claim[str(item.get("claim_id"))].append("numerical-verification")
    for item in dimensions:
        by_claim[str(item.get("claim_id"))].append("dimension-check")
    for item in uncertainty:
        by_claim[str(item.get("claim_id"))].append("uncertainty-propagation")
    for claim in claims:
        if claim.get("status") in {"proved-formal", "proved-deductive", "proved-finite"} and by_claim.get(str(claim.get("claim_id"))) and not claim.get("proof_receipt_ids"):
            findings.append({
                "code": "computation-without-proof-receipt",
                "severity": "critical",
                "message": f"Claim {claim.get('claim_id')} is marked proved but has only quantitative computation sidecars and no proof receipt.",
            })
    checked: list[dict[str, str]] = []
    for item in findings:
        if isinstance(item, Mapping) and isinstance(item.get("code"), str) and isinstance(item.get("message"), str):
            checked.append(item)
        else:
            checked.append(_invalid(f"A quantitative sidecar reviewer returned a malformed finding entry: {item!r}."))
    unique = {(item["code"], item.get("claim_id", ""), item["message"]): item for item in checked}
    return sorted(unique.values(), key=lambda item: (item.get("severity", ""), item["code"], item["message"]))
