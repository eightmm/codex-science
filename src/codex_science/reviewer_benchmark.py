"""Seeded scientific-review benchmark evaluation and unsafe-pass metrics."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from codex_science.evidence_graph_v2 import independent_support_groups, validate_graph_payload
from codex_science.review_receipts import review_receipt_findings
from codex_science.structured_defects import structured_review_findings

WEIGHTS = {"critical": 3.0, "major": 2.0, "minor": 1.0, "suggestion": 0.25}


def evaluate_case(case: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    has_structured_input = "structured_review_input" in case
    if has_structured_input:
        findings.extend(structured_review_findings(case["structured_review_input"]))
    graph = case.get("evidence_graph_v2")
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    if isinstance(graph, dict):
        nodes, edges, graph_findings = validate_graph_payload(graph)
        findings.extend(graph_findings)
        claim_id = case.get("replicated_claim_id")
        if isinstance(claim_id, str) and len(independent_support_groups(claim_id, nodes, edges)) < 2:
            findings.append({"code": "dependent-evidence-v2", "severity": "major", "message": f"Claim {claim_id} has fewer than two independent evidence components."})
    receipt = case.get("review_receipt")
    if isinstance(receipt, dict):
        findings.extend(review_receipt_findings(receipt, case.get("artifact_hashes", {}), registry_sha256=case.get("registry_sha256")))
    if not has_structured_input:
        for item in case.get("additional_findings", []):
            if isinstance(item, dict):
                findings.append({"code": str(item.get("code", "")), "severity": str(item.get("severity", "major")), "message": str(item.get("message", item.get("code", "")))})
    unique = {(item["code"], item.get("message", "")): item for item in findings}
    return sorted(unique.values(), key=lambda item: (item.get("severity", ""), item["code"], item.get("message", "")))


def score_cases(cases: Iterable[dict[str, Any]]) -> dict[str, Any]:
    true_weight = predicted_weight = matched_weight = 0.0
    blocking_expected = blocking_missed = valid_cases = false_positive_cases = 0
    details: list[dict[str, Any]] = []
    severity_totals = {"critical": [0, 0], "major": [0, 0]}
    for case in cases:
        expected_items = [item for item in case.get("expected_findings", []) if isinstance(item, dict)]
        expected = {(str(item["code"]), str(item.get("severity", "major"))) for item in expected_items}
        actual_items = evaluate_case(case)
        actual = {(item["code"], str(item.get("severity", "major"))) for item in actual_items}
        matched = expected & actual
        for _code, severity in expected:
            true_weight += WEIGHTS.get(severity, 1.0)
            if severity in severity_totals: severity_totals[severity][0] += 1
        for _code, severity in actual: predicted_weight += WEIGHTS.get(severity, 1.0)
        for _code, severity in matched:
            matched_weight += WEIGHTS.get(severity, 1.0)
            if severity in severity_totals: severity_totals[severity][1] += 1
        has_blocking = any(severity in {"critical", "major"} for _, severity in expected)
        found_blocking = any(severity in {"critical", "major"} for _, severity in actual)
        if has_blocking:
            blocking_expected += 1
            if not found_blocking: blocking_missed += 1
        if not expected:
            valid_cases += 1
            if actual: false_positive_cases += 1
        details.append({"case_id": case.get("case_id"), "expected": sorted(expected), "actual": sorted(actual), "missing": sorted(expected - actual), "unexpected": sorted(actual - expected), "passed": expected == actual})
    empty_denominator_score = 1.0 if details else 0.0
    precision = matched_weight / predicted_weight if predicted_weight else empty_denominator_score
    recall = matched_weight / true_weight if true_weight else empty_denominator_score
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "schema_version": 1,
        "case_count": len(details),
        "severity_weighted_precision": precision,
        "severity_weighted_recall": recall,
        "severity_weighted_f1": f1,
        "critical_recall": severity_totals["critical"][1] / severity_totals["critical"][0] if severity_totals["critical"][0] else empty_denominator_score,
        "major_recall": severity_totals["major"][1] / severity_totals["major"][0] if severity_totals["major"][0] else empty_denominator_score,
        "unsafe_pass_rate": blocking_missed / blocking_expected if blocking_expected else 0.0,
        "false_positive_case_rate": false_positive_cases / valid_cases if valid_cases else 0.0,
        "details": details,
    }


def _case_object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value


def _case_array(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be an array")
    return value


def _case_text(value: Any, field: str, *, choices: Iterable[str] | None = None, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value.strip()):
        raise ValueError(f"{field} must be {'a' if empty else 'a non-empty'} string")
    if choices is not None and value not in choices:
        raise ValueError(f"{field} has unsupported value: {value!r}")
    return value


def _validate_case(payload: Any) -> None:
    case = _case_object(payload, "case")
    for field in ("case_id", "replicated_claim_id"):
        if field in case:
            _case_text(case[field], field)
    for field in ("expected_findings", "additional_findings"):
        for index, raw in enumerate(_case_array(case.get(field, []), field)):
            label = f"{field}[{index}]"
            item = _case_object(raw, label)
            _case_text(item.get("code"), f"{label}.code")
            if "severity" in item:
                _case_text(item["severity"], f"{label}.severity", choices=WEIGHTS)
            if field == "additional_findings" and "message" in item:
                _case_text(item["message"], f"{label}.message", empty=True)
    if "artifact_hashes" in case:
        _case_object(case["artifact_hashes"], "artifact_hashes")
    if "structured_review_input" in case:
        try:
            structured_review_findings(case["structured_review_input"])
        except ValueError as error:
            raise ValueError(f"structured_review_input: {error}") from error
    graph = case.get("evidence_graph_v2")
    if isinstance(graph, dict):
        try:
            validate_graph_payload(graph)
        except ValueError as error:
            raise ValueError(f"evidence_graph_v2: {error}") from error


def load_cases(path: Path) -> list[dict[str, Any]]:
    if not path.is_dir():
        raise ValueError(f"reviewer benchmark cases path must be an existing directory: {path}")
    cases = []
    for file in sorted(path.glob("*.json")):
        try:
            payload = json.loads(file.read_text(encoding="utf-8"))
            _validate_case(payload)
        except ValueError as error:
            raise ValueError(f"reviewer benchmark case {file}: {error}") from error
        cases.append(payload)
    return cases
