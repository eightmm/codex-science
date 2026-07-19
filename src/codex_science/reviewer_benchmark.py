"""Seeded scientific-review benchmark evaluation and unsafe-pass metrics."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from codex_science.evidence_graph_v2 import independent_support_groups, validate_graph_payload
from codex_science.review_receipts import review_receipt_findings

WEIGHTS = {"critical": 3.0, "major": 2.0, "minor": 1.0, "suggestion": 0.25}


def evaluate_case(case: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
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
    precision = matched_weight / predicted_weight if predicted_weight else 1.0
    recall = matched_weight / true_weight if true_weight else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "schema_version": 1,
        "case_count": len(details),
        "severity_weighted_precision": precision,
        "severity_weighted_recall": recall,
        "severity_weighted_f1": f1,
        "critical_recall": severity_totals["critical"][1] / severity_totals["critical"][0] if severity_totals["critical"][0] else 1.0,
        "major_recall": severity_totals["major"][1] / severity_totals["major"][0] if severity_totals["major"][0] else 1.0,
        "unsafe_pass_rate": blocking_missed / blocking_expected if blocking_expected else 0.0,
        "false_positive_case_rate": false_positive_cases / valid_cases if valid_cases else 0.0,
        "details": details,
    }


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases = []
    for file in sorted(path.glob("*.json")):
        payload = json.loads(file.read_text(encoding="utf-8"))
        if not isinstance(payload, dict): raise ValueError(f"reviewer benchmark case must be an object: {file}")
        cases.append(payload)
    return cases
