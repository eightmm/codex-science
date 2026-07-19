"""Machine-readable model registry and hash-aware execution receipts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


MODEL_FAMILIES = {
    "docking",
    "structure-prediction",
    "protein-design",
    "sequence-model",
    "genomics-model",
    "single-cell-model",
    "simulation",
}
REVISION_POLICIES = {"pin-required", "not-applicable"}


def _text(value: Any, label: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{label} is required")
    return text


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    return value


def _valid_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdefABCDEF" for character in value)


def _canonical_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def default_registry_path() -> Path:
    return Path(__file__).resolve().parents[2] / "models" / "registry.json"


def validate_registry(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if not isinstance(registry, dict):
        raise ValueError("Model registry must be an object")
    if registry.get("schema_version") != 1:
        raise ValueError("Unsupported model registry schema version")
    _text(registry.get("registry_revision"), "model registry revision")
    models = _list(registry.get("models"), "model registry models")
    by_id: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(models):
        model = _mapping(raw, f"model registry record {index}")
        model_id = _text(model.get("id"), f"model record {index} id")
        if model_id in by_id:
            raise ValueError(f"Duplicate model id: {model_id}")
        _text(model.get("skill"), f"model {model_id} skill")
        family = _text(model.get("family"), f"model {model_id} family")
        if family not in MODEL_FAMILIES:
            raise ValueError(f"Invalid model family for {model_id}: {family}")
        contract_revision = model.get("contract_revision")
        if (
            not isinstance(contract_revision, int)
            or isinstance(contract_revision, bool)
            or contract_revision < 1
        ):
            raise ValueError(f"model {model_id} contract_revision must be a positive integer")

        implementation = _mapping(model.get("implementation"), f"model {model_id} implementation")
        _text(implementation.get("repository"), f"model {model_id} repository")
        revision_policy = _text(
            implementation.get("revision_policy"), f"model {model_id} revision_policy"
        )
        if revision_policy not in REVISION_POLICIES:
            raise ValueError(f"Invalid revision policy for {model_id}: {revision_policy}")

        weights = _mapping(model.get("weights"), f"model {model_id} weights")
        weights_policy = _text(weights.get("revision_policy"), f"model {model_id} weights policy")
        if weights_policy not in REVISION_POLICIES:
            raise ValueError(f"Invalid weights policy for {model_id}: {weights_policy}")

        license_record = _mapping(model.get("license"), f"model {model_id} license")
        _text(license_record.get("code"), f"model {model_id} code license")
        _text(license_record.get("weights"), f"model {model_id} weights license")
        _list(model.get("modalities"), f"model {model_id} modalities")
        _list(model.get("required_databases"), f"model {model_id} required_databases")
        _mapping(model.get("hardware"), f"model {model_id} hardware")
        confidence = _mapping(
            model.get("confidence_semantics"), f"model {model_id} confidence_semantics"
        )
        _list(confidence.get("outputs"), f"model {model_id} confidence outputs")
        _list(
            confidence.get("not_equivalent_to"),
            f"model {model_id} confidence not_equivalent_to",
        )
        _list(model.get("leakage_risks"), f"model {model_id} leakage_risks")
        _list(model.get("validated_tasks"), f"model {model_id} validated_tasks")
        _text(model.get("acceptance_contract"), f"model {model_id} acceptance_contract")
        by_id[model_id] = model
    return by_id


def load_registry(path: Path | None = None) -> dict[str, Any]:
    registry_path = path or default_registry_path()
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    validate_registry(payload)
    return payload


def registry_sha256(registry: dict[str, Any]) -> str:
    validate_registry(registry)
    return _canonical_sha256(registry)


def _receipt_material(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "model_id": receipt["model_id"],
        "registry_contract_revision": receipt["registry_contract_revision"],
        "code_revision": receipt["code_revision"],
        "weight_revision": receipt["weight_revision"],
        "database_revisions": receipt["database_revisions"],
        "configuration_sha256": receipt["configuration_sha256"],
        "input_sha256": receipt["input_sha256"],
    }


def build_model_receipt(
    model: dict[str, Any],
    *,
    code_revision: str,
    weight_revision: str,
    database_revisions: dict[str, str],
    configuration_sha256: str,
    input_sha256: str,
) -> dict[str, Any]:
    model_id = _text(model.get("id"), "model id")
    receipt = {
        "schema_version": 1,
        "model_id": model_id,
        "registry_contract_revision": model["contract_revision"],
        "code_revision": _text(code_revision, "code_revision"),
        "weight_revision": _text(weight_revision, "weight_revision"),
        "database_revisions": dict(sorted(database_revisions.items())),
        "configuration_sha256": configuration_sha256.lower(),
        "input_sha256": input_sha256.lower(),
    }
    if not _valid_sha256(receipt["configuration_sha256"]):
        raise ValueError("configuration_sha256 must be a SHA-256 digest")
    if not _valid_sha256(receipt["input_sha256"]):
        raise ValueError("input_sha256 must be a SHA-256 digest")
    for name, revision in receipt["database_revisions"].items():
        _text(name, "database revision name")
        _text(revision, f"database revision {name}")
    receipt["fingerprint"] = _canonical_sha256(_receipt_material(receipt))
    return receipt


def validate_model_receipt(
    receipt: dict[str, Any], model: dict[str, Any] | None = None
) -> None:
    if not isinstance(receipt, dict):
        raise ValueError("Model receipt must be an object")
    if receipt.get("schema_version") != 1:
        raise ValueError("Unsupported model receipt schema version")
    _text(receipt.get("model_id"), "model receipt model_id")
    contract_revision = receipt.get("registry_contract_revision")
    if (
        not isinstance(contract_revision, int)
        or isinstance(contract_revision, bool)
        or contract_revision < 1
    ):
        raise ValueError("registry_contract_revision must be a positive integer")
    _text(receipt.get("code_revision"), "model receipt code_revision")
    _text(receipt.get("weight_revision"), "model receipt weight_revision")
    database_revisions = _mapping(
        receipt.get("database_revisions"), "model receipt database_revisions"
    )
    for name, revision in database_revisions.items():
        _text(name, "database revision name")
        _text(revision, f"database revision {name}")
    for field in ("configuration_sha256", "input_sha256", "fingerprint"):
        if not _valid_sha256(str(receipt.get(field, ""))):
            raise ValueError(f"Invalid model receipt {field}")
    expected = _canonical_sha256(_receipt_material(receipt))
    if expected != str(receipt["fingerprint"]).lower():
        raise ValueError("Model receipt fingerprint mismatch")
    if model is not None:
        if receipt["model_id"] != model["id"]:
            raise ValueError("Model receipt references the wrong registry model")
        if receipt["registry_contract_revision"] != model["contract_revision"]:
            raise ValueError("Model receipt contract revision is stale")


def review_model_receipt(receipt: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    try:
        validate_model_receipt(receipt)
    except ValueError as error:
        return [
            {
                "code": "invalid-model-receipt",
                "severity": "critical",
                "message": str(error),
            }
        ]

    path = default_registry_path()
    if not path.is_file():
        findings.append(
            {
                "code": "model-registry-unavailable",
                "severity": "minor",
                "message": "The current model registry is unavailable for staleness review.",
            }
        )
        return findings

    registry = load_registry(path)
    models = validate_registry(registry)
    model = models.get(str(receipt["model_id"]))
    if model is None:
        findings.append(
            {
                "code": "unknown-model",
                "severity": "major",
                "message": f"Model receipt references an unknown model: {receipt['model_id']}",
            }
        )
    elif receipt["registry_contract_revision"] != model["contract_revision"]:
        findings.append(
            {
                "code": "stale-model-receipt",
                "severity": "major",
                "message": (
                    f"Model receipt contract revision {receipt['registry_contract_revision']} "
                    f"does not match registry revision {model['contract_revision']} for {model['id']}."
                ),
            }
        )
    return findings


def changed_model_contracts(
    previous: dict[str, Any], current: dict[str, Any]
) -> list[str]:
    previous_models = validate_registry(previous)
    current_models = validate_registry(current)
    changed: set[str] = set(previous_models.keys() ^ current_models.keys())
    for model_id in previous_models.keys() & current_models.keys():
        if previous_models[model_id] != current_models[model_id]:
            changed.add(model_id)
    return sorted(changed)
