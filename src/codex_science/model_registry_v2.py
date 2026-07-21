"""Model registry v2 with maturity, immutable contracts, selection, and receipt invalidation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

STATUSES = {"cataloged", "experimental", "smoke-tested", "contract-tested", "acceptance-tested", "degraded", "deprecated", "license-blocked"}
USABLE_STATUSES = {"experimental", "smoke-tested", "contract-tested", "acceptance-tested"}


def canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _sha(value: Any, label: str) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"{label} must be a SHA-256 digest")
    return text


def _text(value: Any, label: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{label} is required")
    return text


def model_contract_material(model: dict[str, Any]) -> dict[str, Any]:
    material = dict(model)
    material.pop("contract_sha256", None)
    return material


def validate_registry_v2(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if payload.get("schema_version") != 2:
        raise ValueError("unsupported model registry v2 schema")
    _text(payload.get("registry_revision"), "registry_revision")
    models = payload.get("models")
    if not isinstance(models, list):
        raise ValueError("models must be a list")
    by_id: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(models):
        if not isinstance(raw, dict):
            raise ValueError(f"model {index} must be an object")
        model = dict(raw)
        model_id = _text(model.get("id"), f"model {index} id")
        if model_id in by_id:
            raise ValueError(f"duplicate model: {model_id}")
        status = _text(model.get("status"), f"model {model_id} status")
        if status not in STATUSES:
            raise ValueError(f"invalid model status: {status}")
        for field in ("family", "skill", "acceptance_contract"):
            _text(model.get(field), f"model {model_id} {field}")
        for field in ("modalities", "tasks", "leakage_risks"):
            if not isinstance(model.get(field), list) or not model[field]:
                raise ValueError(f"model {model_id} {field} must be non-empty")
        implementation = model.get("implementation")
        if not isinstance(implementation, dict):
            raise ValueError(f"model {model_id} implementation must be an object")
        _text(implementation.get("repository"), f"model {model_id} repository")
        license_record = model.get("license")
        if not isinstance(license_record, dict):
            raise ValueError(f"model {model_id} license must be an object")
        _text(license_record.get("code"), f"model {model_id} code license")
        _text(license_record.get("weights"), f"model {model_id} weights license")
        if not isinstance(model.get("hardware"), dict):
            raise ValueError(f"model {model_id} hardware must be an object")
        acceptance = model.get("acceptance")
        if not isinstance(acceptance, dict):
            raise ValueError(f"model {model_id} acceptance must be an object")
        if status == "acceptance-tested":
            _sha(implementation.get("commit_sha256"), f"model {model_id} implementation commit")
            _sha(acceptance.get("bundle_sha256"), f"model {model_id} acceptance bundle")
            if acceptance.get("status") != "passed":
                raise ValueError(f"acceptance-tested model {model_id} must have passed acceptance")
        expected_contract = canonical_sha256(model_contract_material(model))
        if model.get("contract_sha256") is not None and _sha(model["contract_sha256"], f"model {model_id} contract") != expected_contract:
            raise ValueError(f"model contract hash mismatch: {model_id}")
        model["contract_sha256"] = expected_contract
        by_id[model_id] = model
    return by_id


def load_registry_v2(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_registry_v2(payload)
    return payload


def registry_sha256(payload: dict[str, Any]) -> str:
    validate_registry_v2(payload)
    return canonical_sha256(payload)


def build_model_receipt_v2(
    model: dict[str, Any], *, registry_sha256_value: str, code_revision: str,
    weight_revision: str, database_revisions: dict[str, str],
    configuration_sha256: str, input_sha256: str, acceptance_bundle_sha256: str | None = None,
) -> dict[str, Any]:
    material = {
        "schema_version": 2,
        "model_id": _text(model.get("id"), "model_id"),
        "model_contract_sha256": canonical_sha256(model_contract_material(model)),
        "registry_sha256": _sha(registry_sha256_value, "registry_sha256"),
        "code_revision": _text(code_revision, "code_revision"),
        "weight_revision": _text(weight_revision, "weight_revision"),
        "database_revisions": dict(sorted(database_revisions.items())),
        "configuration_sha256": _sha(configuration_sha256, "configuration_sha256"),
        "input_sha256": _sha(input_sha256, "input_sha256"),
        "acceptance_bundle_sha256": None if acceptance_bundle_sha256 is None else _sha(acceptance_bundle_sha256, "acceptance_bundle_sha256"),
    }
    material["fingerprint"] = canonical_sha256(material)
    return material


def validate_model_receipt_v2(receipt: dict[str, Any], registry: dict[str, Any] | None = None) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if receipt.get("schema_version") != 2:
        return [{"code": "invalid-model-receipt-v2", "severity": "critical", "message": "unsupported model receipt v2 schema"}]
    try:
        material = dict(receipt)
        fingerprint = _sha(material.pop("fingerprint"), "fingerprint")
        if canonical_sha256(material) != fingerprint:
            raise ValueError("model receipt fingerprint mismatch")
        for field in ("model_contract_sha256", "registry_sha256", "configuration_sha256", "input_sha256"):
            _sha(receipt.get(field), field)
    except ValueError as error:
        return [{"code": "invalid-model-receipt-v2", "severity": "critical", "message": str(error)}]
    if registry is not None:
        models = validate_registry_v2(registry)
        model = models.get(str(receipt.get("model_id")))
        if model is None:
            findings.append({"code": "unknown-model-v2", "severity": "major", "message": f"unknown model: {receipt.get('model_id')}"})
        else:
            if receipt.get("registry_sha256") != registry_sha256(registry):
                findings.append({"code": "stale-model-receipt-v2", "severity": "major", "message": "model receipt covers a different registry"})
            if receipt.get("model_contract_sha256") != model["contract_sha256"]:
                findings.append({"code": "stale-model-receipt-v2", "severity": "major", "message": f"model contract changed: {model['id']}"})
            expected_bundle = model.get("acceptance", {}).get("bundle_sha256")
            if expected_bundle and receipt.get("acceptance_bundle_sha256") != expected_bundle:
                findings.append({"code": "stale-model-receipt-v2", "severity": "major", "message": f"acceptance bundle changed: {model['id']}"})
    return findings


def select_models(
    registry: dict[str, Any], *, task: str, modality: str,
    available_vram_gb: float | None = None, allow_experimental: bool = False,
    allowed_licenses: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    models = validate_registry_v2(registry)
    allowed = set(allowed_licenses or [])
    status_rank = {"acceptance-tested": 0, "contract-tested": 1, "smoke-tested": 2, "experimental": 3}
    candidates: list[dict[str, Any]] = []
    for model in models.values():
        status = str(model["status"])
        if status not in USABLE_STATUSES or (status == "experimental" and not allow_experimental):
            continue
        if task not in model["tasks"] or modality not in model["modalities"]:
            continue
        if allowed and (model["license"]["code"] not in allowed or model["license"]["weights"] not in allowed):
            continue
        minimum = model.get("hardware", {}).get("minimum_vram_gb")
        if available_vram_gb is not None and isinstance(minimum, (int, float)) and minimum > available_vram_gb:
            continue
        candidates.append(model)
    return sorted(candidates, key=lambda item: (status_rank.get(str(item["status"]), 99), len(item.get("leakage_risks", [])), str(item["id"])))
