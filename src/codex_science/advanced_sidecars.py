"""Optional advanced sidecars layered over the stable artifact manifest schema."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from codex_science.collaboration import stale_annotations, validate_annotation
from codex_science.evidence_graph_v2 import independent_support_groups, validate_graph_payload
from codex_science.literature_v2 import validate_risk_of_bias
from codex_science.model_registry_v2 import load_registry_v2, validate_model_receipt_v2
from codex_science.review_receipts import review_receipt_findings, validate_review_receipt

ADVANCED_KINDS = {"evidence-graph-v2", "review-receipt", "review-receipt-v2", "annotation", "model-receipt-v2", "risk-of-bias"}


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON in {label}: {path.name}: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be an object")
    return payload


def validate_advanced_sidecars(
    manifest: dict[str, Any], run_dir: Path, verified: dict[str, Path], *, base_sidecars: dict[str, Any] | None = None
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "graph_v2": None, "graph_v2_nodes": {}, "graph_v2_edges": [], "graph_v2_findings": [],
        "review_receipts": [], "annotations": [], "model_receipts_v2": [], "risk_of_bias": [],
        "artifact_hashes": {str(item["path"]): str(item["sha256"]).lower() for item in manifest.get("artifacts", [])},
        "advanced_paths": {},
    }
    seen_graph = False
    for record in manifest.get("artifacts", []):
        kind, relative = str(record.get("kind", "")), str(record.get("path", ""))
        if kind not in ADVANCED_KINDS:
            continue
        path = verified[relative]
        payload = _load(path, kind)
        if kind == "review-receipt" and not payload.get("review_id"):
            # Legacy receipt from schema-v1 bundles: keep it hashed and navigable,
            # but do not reinterpret it as the new hash-covered receipt contract.
            continue
        result["advanced_paths"].setdefault(kind, []).append(relative)
        if kind == "evidence-graph-v2":
            if seen_graph:
                raise ValueError("only one evidence-graph-v2 artifact is allowed")
            seen_graph = True
            nodes, edges, findings = validate_graph_payload(payload)
            result.update({"graph_v2": payload, "graph_v2_nodes": nodes, "graph_v2_edges": edges, "graph_v2_findings": findings})
        elif kind in {"review-receipt", "review-receipt-v2"}:
            validate_review_receipt(payload)
            result["review_receipts"].append(payload)
        elif kind == "annotation":
            validate_annotation(payload)
            result["annotations"].append(payload)
        elif kind == "model-receipt-v2":
            result["model_receipts_v2"].append(payload)
        elif kind == "risk-of-bias":
            validate_risk_of_bias(payload)
            result["risk_of_bias"].append(payload)
    result["annotations"] = stale_annotations(result["annotations"], result["artifact_hashes"])
    if base_sidecars:
        result["base_sidecars"] = base_sidecars
    return result


def review_advanced_sidecars(sidecars: dict[str, Any], *, registry_path: Path | None = None) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = list(sidecars.get("graph_v2_findings", []))
    artifact_hashes = sidecars.get("artifact_hashes", {})
    registry = None
    registry_digest = None
    path = registry_path or Path(__file__).resolve().parents[2] / "models" / "registry-v2.json"
    if path.is_file():
        from codex_science.model_registry_v2 import registry_sha256
        registry = load_registry_v2(path)
        registry_digest = registry_sha256(registry)
    for receipt in sidecars.get("review_receipts", []):
        findings.extend(review_receipt_findings(receipt, artifact_hashes, registry_sha256=registry_digest))
        if receipt.get("status") != "passed":
            unresolved = [
                item for item in receipt.get("findings", [])
                if item.get("resolution_status", "open") != "resolved"
            ]
            if unresolved:
                findings.extend(unresolved)
            else:
                findings.append({"code": "review-receipt-not-passed", "severity": "major", "message": f"Review receipt {receipt['review_id']} is {receipt.get('status')}."})
    for receipt in sidecars.get("model_receipts_v2", []):
        findings.extend(validate_model_receipt_v2(receipt, registry))
    for annotation in sidecars.get("annotations", []):
        if annotation.get("status") == "stale-anchor":
            findings.append({"code": "stale-annotation-anchor", "severity": "minor", "message": f"Annotation {annotation['annotation_id']} points to changed artifact bytes."})
    base = sidecars.get("base_sidecars", {})
    claims = base.get("claim_by_id", {}) if isinstance(base, dict) else {}
    nodes, edges = sidecars.get("graph_v2_nodes", {}), sidecars.get("graph_v2_edges", [])
    for claim_id, claim in claims.items():
        if claim.get("status") == "replicated" and len(independent_support_groups(claim_id, nodes, edges)) < 2:
            findings.append({"code": "dependent-evidence-v2", "severity": "major", "claim_id": claim_id, "message": f"Claim {claim_id} is replicated without two independent evidence components."})
    unique = {(item["code"], item.get("claim_id", ""), item["message"]): item for item in findings}
    return sorted(unique.values(), key=lambda item: (item.get("severity", ""), item["code"], item.get("claim_id", ""), item["message"]))
