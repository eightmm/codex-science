"""Blinded scientific review packets and hash-covered review response intake.

The runtime prepares deterministic packets for a separate human or agent. It
never sends data to a model service, claims reviewer independence, or exposes
private chain-of-thought. Reviewer identity and independence remain attestations
that must be governed by the calling system.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from codex_science.artifact_store import stream_sha256
from codex_science.artifacts import validate_bundle
from codex_science.review_receipts import build_review_receipt, validate_review_receipt


REVIEW_MODES = {"record", "source", "method", "reproduction"}
SEVERITIES = {"critical", "major", "minor", "suggestion"}
SENSITIVE_FRAGMENTS = {"token", "password", "secret", "credential", "private_key", "api_key", "apikey", "chain_of_thought", "hidden_rationale"}
EXCLUDED_PRODUCER_FIELDS = {"intended_conclusion", "producer_rationale", "chain_of_thought", "private_scratchpad", "hidden_answer", "suspected_bug"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _fingerprint(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _text(value: Any, label: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{label} is required")
    return text


def _sha(value: Any, label: str) -> str:
    text = _text(value, label).lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"{label} must be a SHA-256 digest")
    return text


def _redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            normalized = key_text.lower()
            if key_text in EXCLUDED_PRODUCER_FIELDS:
                continue
            if any(fragment in normalized for fragment in SENSITIVE_FRAGMENTS):
                result[key_text] = "[REDACTED]"
            else:
                result[key_text] = _redact(item)
        return result
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _material_claim_ids(manifest: Mapping[str, Any], sidecars: Mapping[str, Any]) -> list[str]:
    claim_register = sidecars.get("claim_by_id")
    if isinstance(claim_register, Mapping) and claim_register:
        return sorted(str(key) for key in claim_register)
    return sorted(str(item.get("id")) for item in manifest.get("claims", []) if isinstance(item, Mapping) and item.get("id"))


def build_review_packet(
    manifest_path: Path,
    *,
    review_modes: list[str],
    independent_required: bool = True,
    review_questions: list[str] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    sidecars = validate_bundle(manifest, manifest_path.parent)
    modes = sorted({_text(item, "review mode") for item in review_modes})
    unknown = sorted(set(modes) - REVIEW_MODES)
    if unknown or not modes:
        raise ValueError(f"invalid or empty review modes: {', '.join(unknown)}")
    digest, _size = stream_sha256(manifest_path)
    artifact_hashes = [
        {"path": str(item["path"]), "sha256": str(item["sha256"]).lower(), "kind": str(item.get("kind", "artifact"))}
        for item in manifest.get("artifacts", [])
        if isinstance(item, Mapping)
    ]
    claims = sidecars.get("claim_register", {}).get("claims") if isinstance(sidecars.get("claim_register"), Mapping) else None
    if not isinstance(claims, list):
        claims = [dict(item) for item in manifest.get("claims", []) if isinstance(item, Mapping)]
    graph = sidecars.get("graph_v2") or sidecars.get("evidence_graph")
    questions = review_questions or [
        "Does each material claim have direct, correctly attributed evidence?",
        "Do the design, controls, splits, metrics, uncertainty, and inference level support the claim?",
        "Are duplicated sources, shared cohorts or samples, and model-training overlap represented correctly?",
        "Do reported figures, tables, and values agree with the saved artifacts and execution record?",
        "Which alternative explanations or counterevidence remain unresolved?"
    ]
    material = {
        "schema_version": 1,
        "source_run_id": str(manifest["run_id"]),
        "source_manifest_path": str(manifest_path),
        "source_manifest_sha256": digest,
        "created_at": created_at or _now(),
        "review_modes": modes,
        "independent_required": bool(independent_required),
        "producer_context_excluded": sorted(EXCLUDED_PRODUCER_FIELDS),
        "decision_contract": {
            "question": str(manifest.get("question", "")),
            "plan": _redact(manifest.get("plan", [])),
            "inputs": _redact(manifest.get("inputs", [])),
            "code": _redact(manifest.get("code", [])),
            "executions": _redact(manifest.get("executions", [])),
            "environment": _redact(manifest.get("environment", {})),
        },
        "claims": _redact(claims),
        "material_claim_ids": _material_claim_ids(manifest, sidecars),
        "artifacts": artifact_hashes,
        "evidence_graph": _redact(graph) if isinstance(graph, Mapping) else None,
        "study_table": _redact(sidecars.get("study_table")) if sidecars.get("study_table") else None,
        "query_records": _redact(sidecars.get("query_records", [])),
        "lane_receipts": _redact(sidecars.get("lane_receipts", [])),
        "model_receipts": _redact(sidecars.get("model_receipts_v2", sidecars.get("model_receipts", []))),
        "review_questions": [_text(item, "review question") for item in questions],
        "response_contract": {
            "reviewer": "required",
            "independent": "boolean attestation",
            "review_modes": modes,
            "reviewed_claim_ids": "all material claims unless an explicit blocked reason is supplied",
            "reviewed_artifacts": "path and SHA-256 pairs from this packet",
            "findings": "stable ID, severity, code, message, evidence, required action, and resolution status",
            "limitations": "required"
        },
        "evidence_boundary": "This packet exposes recorded run evidence while excluding producer-only rationale fields. It does not authenticate the reviewer, guarantee true independence, or include unrecorded evidence."
    }
    fingerprint = _fingerprint(material)
    return {**material, "review_task_id": f"review-task-{fingerprint[:20]}", "fingerprint": fingerprint}


def validate_review_packet(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported review packet schema")
    for field in ("review_task_id", "source_run_id", "source_manifest_path", "source_manifest_sha256", "created_at", "evidence_boundary"):
        _text(payload.get(field), field)
    _sha(payload.get("source_manifest_sha256"), "source_manifest_sha256")
    modes = payload.get("review_modes")
    if not isinstance(modes, list) or not modes or set(modes) - REVIEW_MODES:
        raise ValueError("invalid review packet modes")
    if not isinstance(payload.get("artifacts"), list) or not isinstance(payload.get("material_claim_ids"), list):
        raise ValueError("review packet artifacts and material_claim_ids must be lists")
    material = dict(payload)
    task_id = str(material.pop("review_task_id"))
    fingerprint = str(material.pop("fingerprint", "")).lower()
    if _fingerprint(material) != fingerprint or task_id != f"review-task-{fingerprint[:20]}":
        raise ValueError("review packet fingerprint or task ID mismatch")


def _validate_finding(item: Mapping[str, Any], index: int) -> dict[str, Any]:
    finding_id = _text(item.get("id"), f"finding {index} id")
    severity = _text(item.get("severity"), f"finding {finding_id} severity")
    if severity not in SEVERITIES:
        raise ValueError(f"invalid finding severity: {severity}")
    code = _text(item.get("code"), f"finding {finding_id} code")
    message = _text(item.get("message", item.get("rationale")), f"finding {finding_id} message")
    resolution = str(item.get("resolution_status", "open"))
    if resolution not in {"open", "resolved", "accepted-risk", "not-applicable"}:
        raise ValueError(f"invalid finding resolution status: {resolution}")
    evidence = item.get("evidence", [])
    if not isinstance(evidence, list):
        raise ValueError(f"finding {finding_id} evidence must be a list")
    required_action = str(item.get("required_action", "")).strip()
    return {
        **dict(item),
        "id": finding_id,
        "severity": severity,
        "code": code,
        "message": message,
        "resolution_status": resolution,
        "evidence": evidence,
        "required_action": required_action,
    }


def finalize_review_response(packet: Mapping[str, Any], response: Mapping[str, Any]) -> dict[str, Any]:
    validate_review_packet(packet)
    if response.get("schema_version", 1) != 1:
        raise ValueError("unsupported review response schema")
    if response.get("review_task_id") != packet["review_task_id"] or response.get("packet_fingerprint") != packet["fingerprint"]:
        raise ValueError("review response covers a different packet")
    reviewer = _text(response.get("reviewer"), "reviewer")
    independent = response.get("independent")
    if not isinstance(independent, bool):
        raise ValueError("independent must be a boolean attestation")
    response_modes = sorted({_text(item, "response review mode") for item in response.get("review_modes", [])})
    if not response_modes or set(response_modes) - set(packet["review_modes"]):
        raise ValueError("response review modes are empty or exceed the packet")
    reviewed_claims = sorted({_text(item, "reviewed claim ID") for item in response.get("reviewed_claim_ids", [])})
    material_claims = set(map(str, packet["material_claim_ids"]))
    unknown_claims = sorted(set(reviewed_claims) - material_claims)
    if unknown_claims:
        raise ValueError(f"response references unknown claims: {', '.join(unknown_claims)}")
    blocked_reason = str(response.get("blocked_reason", "")).strip()
    missing_claims = sorted(material_claims - set(reviewed_claims))
    if missing_claims and not blocked_reason:
        raise ValueError(f"review omits material claims without blocked_reason: {', '.join(missing_claims)}")
    packet_artifacts = {str(item["path"]): str(item["sha256"]).lower() for item in packet["artifacts"]}
    reviewed_artifacts_raw = response.get("reviewed_artifacts", [])
    if not isinstance(reviewed_artifacts_raw, list):
        raise ValueError("reviewed_artifacts must be a list")
    covered_artifacts: list[dict[str, str]] = []
    for index, item in enumerate(reviewed_artifacts_raw):
        if not isinstance(item, Mapping):
            raise ValueError(f"reviewed artifact {index} must be an object")
        path = _text(item.get("path"), f"reviewed artifact {index} path")
        digest = _sha(item.get("sha256"), f"reviewed artifact {path} sha256")
        if packet_artifacts.get(path) != digest:
            raise ValueError(f"reviewed artifact does not match packet: {path}")
        covered_artifacts.append({"path": path, "sha256": digest})
    if not covered_artifacts:
        raise ValueError("review response must cover at least one artifact")
    findings_raw = response.get("findings", [])
    if not isinstance(findings_raw, list):
        raise ValueError("findings must be a list")
    findings = [_validate_finding(item, index) for index, item in enumerate(findings_raw) if isinstance(item, Mapping)]
    if len(findings) != len(findings_raw):
        raise ValueError("all findings must be objects")
    if packet.get("independent_required") and not independent:
        findings.append({
            "id": "F-review-independence",
            "severity": "major",
            "code": "review-not-independent",
            "message": "The review packet required independence but the reviewer attested independent=false.",
            "resolution_status": "open",
            "evidence": [],
            "required_action": "Obtain a separate reviewer or explicitly downgrade the completion claim."
        })
    if missing_claims:
        findings.append({
            "id": "F-review-coverage",
            "severity": "major",
            "code": "incomplete-review-coverage",
            "message": f"Material claims were not reviewed: {', '.join(missing_claims)}. Blocked reason: {blocked_reason}",
            "resolution_status": "open",
            "evidence": [],
            "required_action": "Resolve the blocker or review the missing claims."
        })
    unresolved_blocking = any(item["severity"] in {"critical", "major"} and item["resolution_status"] not in {"resolved", "not-applicable"} for item in findings)
    requested_status = str(response.get("status", "findings"))
    if requested_status not in {"passed", "findings", "blocked"}:
        raise ValueError("invalid review response status")
    status = "findings" if unresolved_blocking else requested_status
    if status == "passed" and (missing_claims or (packet.get("independent_required") and not independent)):
        status = "findings"
    limitations = response.get("limitations", [])
    if not isinstance(limitations, list) or not all(isinstance(item, str) and item.strip() for item in limitations):
        raise ValueError("limitations must be a non-empty string list")
    if not limitations:
        raise ValueError("review response must state limitations")
    receipt = build_review_receipt(
        review_id=f"review-{str(packet['review_task_id']).removeprefix('review-task-')}",
        reviewer=reviewer,
        independent=independent,
        review_modes=response_modes,
        status=status,
        covered_artifacts=covered_artifacts,
        covered_claim_ids=reviewed_claims,
        findings=findings,
        covered_registry_sha256=None if response.get("covered_registry_sha256") is None else _sha(response["covered_registry_sha256"], "covered_registry_sha256"),
        limitations=list(limitations),
    )
    receipt["review_task_id"] = packet["review_task_id"]
    receipt["packet_fingerprint"] = packet["fingerprint"]
    # Rebuild the receipt fingerprint after adding packet linkage.
    material = dict(receipt)
    material.pop("fingerprint", None)
    receipt["fingerprint"] = _fingerprint(material)
    validate_review_receipt(receipt)
    return receipt
