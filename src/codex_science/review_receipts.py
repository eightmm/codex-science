"""Hash-covered scientific review receipts and deterministic staleness checks."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

REVIEW_MODES = {"record", "source", "method", "reproduction"}
REVIEW_STATUSES = {"passed", "findings", "blocked", "superseded"}


def _text(value: Any, label: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{label} is required")
    return result


def _sha(value: Any, label: str) -> str:
    result = _text(value, label).lower()
    if len(result) != 64 or any(character not in "0123456789abcdef" for character in result):
        raise ValueError(f"{label} must be a SHA-256 digest")
    return result


def canonical_sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def validate_review_receipt(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported review receipt schema")
    _text(payload.get("review_id"), "review_id")
    _text(payload.get("reviewer"), "reviewer")
    if not isinstance(payload.get("independent"), bool):
        raise ValueError("independent must be boolean")
    modes = payload.get("review_modes")
    if not isinstance(modes, list) or not modes:
        raise ValueError("review_modes must be a non-empty list")
    unknown = sorted(set(map(str, modes)) - REVIEW_MODES)
    if unknown:
        raise ValueError(f"unknown review modes: {', '.join(unknown)}")
    status = _text(payload.get("status"), "review status")
    if status not in REVIEW_STATUSES:
        raise ValueError(f"invalid review status: {status}")
    covered = payload.get("covered_artifacts")
    if not isinstance(covered, list) or not covered:
        raise ValueError("covered_artifacts must be a non-empty list")
    paths: set[str] = set()
    for index, item in enumerate(covered):
        if not isinstance(item, dict):
            raise ValueError(f"covered_artifacts[{index}] must be an object")
        path = _text(item.get("path"), f"covered_artifacts[{index}].path")
        if path in paths:
            raise ValueError(f"duplicate covered artifact: {path}")
        paths.add(path)
        _sha(item.get("sha256"), f"covered_artifacts[{index}].sha256")
    claims = payload.get("covered_claim_ids", [])
    if not isinstance(claims, list) or not all(isinstance(value, str) and value for value in claims):
        raise ValueError("covered_claim_ids must be strings")
    registry = payload.get("covered_registry_sha256")
    if registry is not None:
        _sha(registry, "covered_registry_sha256")
    findings = payload.get("findings", [])
    if not isinstance(findings, list):
        raise ValueError("findings must be a list")
    fingerprint = payload.get("fingerprint")
    if fingerprint is not None:
        material = dict(payload)
        material.pop("fingerprint", None)
        if _sha(fingerprint, "fingerprint") != canonical_sha256(material):
            raise ValueError("review receipt fingerprint mismatch")


def build_review_receipt(
    *, review_id: str, reviewer: str, independent: bool, review_modes: list[str],
    status: str, covered_artifacts: list[dict[str, str]], covered_claim_ids: list[str],
    findings: list[dict[str, Any]], covered_registry_sha256: str | None = None,
    limitations: list[str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "review_id": review_id,
        "reviewer": reviewer,
        "independent": independent,
        "review_modes": review_modes,
        "status": status,
        "covered_artifacts": covered_artifacts,
        "covered_claim_ids": covered_claim_ids,
        "findings": findings,
        "limitations": limitations or [],
    }
    if covered_registry_sha256 is not None:
        payload["covered_registry_sha256"] = covered_registry_sha256
    validate_review_receipt(payload)
    payload["fingerprint"] = canonical_sha256(payload)
    validate_review_receipt(payload)
    return payload


def review_receipt_findings(
    payload: dict[str, Any], current_artifact_hashes: Mapping[str, str], *, registry_sha256: str | None = None
) -> list[dict[str, str]]:
    try:
        validate_review_receipt(payload)
    except ValueError as error:
        return [{"code": "invalid-review-receipt", "severity": "critical", "message": str(error)}]
    findings: list[dict[str, str]] = []
    for item in payload["covered_artifacts"]:
        path, expected = str(item["path"]), str(item["sha256"]).lower()
        actual = current_artifact_hashes.get(path)
        if actual != expected:
            findings.append({"code": "stale-review-receipt", "severity": "major", "message": f"Review receipt {payload['review_id']} covers stale or missing artifact {path}."})
    expected_registry = payload.get("covered_registry_sha256")
    if expected_registry is not None and registry_sha256 != expected_registry:
        findings.append({"code": "stale-review-receipt", "severity": "major", "message": f"Review receipt {payload['review_id']} covers a different model registry."})
    if payload.get("status") == "passed" and any(item.get("severity") in {"critical", "major"} and item.get("resolution_status", "open") != "resolved" for item in payload.get("findings", [])):
        findings.append({"code": "unsafe-review-pass", "severity": "critical", "message": f"Review receipt {payload['review_id']} is passed with unresolved blocking findings."})
    unique = {(item["code"], item["message"]): item for item in findings}
    return sorted(unique.values(), key=lambda item: (item["severity"], item["code"], item["message"]))
