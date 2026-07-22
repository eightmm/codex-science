"""Validation and cross-link review for quantitative research sidecars."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping

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
        "numerical_verifications": [],
        "dimension_checks": [],
        "uncertainty_propagations": [],
    }


def validate_quantitative_sidecar(kind: str, payload: Mapping[str, Any], result: dict[str, Any]) -> None:
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
        validate_proof_receipt(payload)
        result["proof_receipts"].append(dict(payload))
    elif kind == "counterexample-search":
        validate_counterexample_receipt(payload)
        result["counterexample_receipts"].append(dict(payload))
    elif kind == "formal-proof-check":
        receipt = payload.get("proof_receipt")
        if not isinstance(receipt, Mapping):
            raise ValueError("formal-proof-check requires proof_receipt")
        validate_proof_receipt(receipt)
        result["formal_proof_checks"].append(dict(payload))
        result["proof_receipts"].append(dict(receipt))
    elif kind == "statistical-analysis":
        validate_statistical_analysis(payload)
        result["statistical_analyses"].append(dict(payload))
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


def review_quantitative_sidecars(sidecars: Mapping[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    designs = [item for item in sidecars.get("research_designs", []) if isinstance(item, Mapping)]
    claims = [item for item in sidecars.get("mathematical_claims", []) if isinstance(item, Mapping)]
    proofs = [item for item in sidecars.get("proof_receipts", []) if isinstance(item, Mapping)]
    counters = [item for item in sidecars.get("counterexample_receipts", []) if isinstance(item, Mapping)]
    graphs = [item for item in sidecars.get("proof_obligation_graphs", []) if isinstance(item, Mapping)]
    analyses = [item for item in sidecars.get("statistical_analyses", []) if isinstance(item, Mapping)]
    numerical = [item for item in sidecars.get("numerical_verifications", []) if isinstance(item, Mapping)]
    dimensions = [item for item in sidecars.get("dimension_checks", []) if isinstance(item, Mapping)]
    uncertainty = [item for item in sidecars.get("uncertainty_propagations", []) if isinstance(item, Mapping)]

    for design in designs:
        findings.extend(review_research_design(design))
    for analysis in analyses:
        findings.extend(review_statistical_analysis(analysis))
    for receipt in numerical:
        findings.extend(review_numerical_verification(receipt))
    for receipt in dimensions:
        findings.extend(review_dimension_check(receipt))
    for receipt in uncertainty:
        findings.extend(review_uncertainty_propagation(receipt))
    findings.extend(math_review_findings(claims, proofs, counters, graphs))

    design_ids = {str(item.get("design_id")) for item in designs}
    claim_ids = {str(item.get("claim_id")) for item in claims}
    proof_ids = {str(item.get("receipt_id")) for item in proofs}
    counter_ids = {str(item.get("receipt_id") or item.get("fingerprint")) for item in counters}
    for analysis in analyses:
        if str(analysis.get("design_id")) not in design_ids:
            findings.append({
                "code": "statistical-design-missing",
                "severity": "major",
                "message": f"Statistical analysis {analysis.get('analysis_id')} has no matching research-design sidecar.",
            })
    for collection_name, collection in (
        ("numerical verification", numerical),
        ("dimension check", dimensions),
        ("uncertainty propagation", uncertainty),
    ):
        for item in collection:
            claim_id = str(item.get("claim_id", ""))
            if claims and claim_id not in claim_ids:
                findings.append({
                    "code": "quantitative-claim-missing",
                    "severity": "major",
                    "message": f"{collection_name.title()} {item.get('verification_id') or item.get('check_id') or item.get('propagation_id')} references missing mathematical claim {claim_id}.",
                })
    for claim in claims:
        for receipt_id in claim.get("proof_receipt_ids", []):
            if str(receipt_id) not in proof_ids:
                findings.append({
                    "code": "missing-proof-receipt",
                    "severity": "major",
                    "message": f"Mathematical claim {claim.get('claim_id')} references missing proof receipt {receipt_id}.",
                })
        for receipt_id in claim.get("counterexample_receipt_ids", []):
            if str(receipt_id) not in counter_ids:
                findings.append({
                    "code": "missing-counterexample-receipt",
                    "severity": "major",
                    "message": f"Mathematical claim {claim.get('claim_id')} references missing counterexample receipt {receipt_id}.",
                })
    by_claim: dict[str, list[str]] = defaultdict(list)
    for item in analyses:
        by_claim[str(item.get("claim_id"))].append("statistical-analysis")
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
    unique = {(item["code"], item.get("claim_id", ""), item["message"]): item for item in findings}
    return sorted(unique.values(), key=lambda item: (item.get("severity", ""), item["code"], item["message"]))
