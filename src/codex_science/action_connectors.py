"""Approval-gated contract for optional authenticated connector packs.

Core Codex Science does not ship provider credentials or provider-specific write
implementations. Optional packs implement ConnectorActionAdapter and receive
credentials out of band from their host. The core contract enforces preview,
optimistic concurrency, idempotency, before/after hashes, and explicit receipts.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol


MODES = {"read", "write"}
SECRET_FRAGMENTS = {
    "token",
    "password",
    "secret",
    "credential",
    "private_key",
    "api_key",
    "apikey",
    "access_key",
    "client_secret",
    "authorization",
    "bearer",
    "session_cookie",
}


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


def _json_value(value: Any, label: str) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _json_value(item, f"{label}[{index}]")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            if any(fragment in key_text.lower() for fragment in SECRET_FRAGMENTS):
                raise ValueError(f"credential-like parameter keys are forbidden: {key_text}")
            _json_value(item, f"{label}.{key_text}")
        return
    raise ValueError(f"{label} must contain JSON values")


@dataclass(frozen=True)
class ActionSpec:
    schema_version: int
    connector: str
    operation: str
    mode: str
    target: str
    parameters: dict[str, Any]
    requested_scopes: tuple[str, ...]
    idempotency_key: str
    expected_before_sha256: str | None
    approval_required: bool
    destructive: bool
    paid: bool
    sensitive_data: bool
    compensation: str | None

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ActionSpec":
        if payload.get("schema_version", 1) != 1:
            raise ValueError("unsupported action spec schema")
        mode = _text(payload.get("mode"), "mode")
        if mode not in MODES:
            raise ValueError(f"invalid action mode: {mode}")
        parameters = payload.get("parameters", {})
        if not isinstance(parameters, Mapping):
            raise ValueError("parameters must be an object")
        _json_value(parameters, "parameters")
        scopes_raw = payload.get("requested_scopes", [])
        if not isinstance(scopes_raw, list):
            raise ValueError("requested_scopes must be a list")
        scopes = tuple(sorted({_text(item, "requested scope") for item in scopes_raw}))
        before = None if payload.get("expected_before_sha256") is None else _sha(payload["expected_before_sha256"], "expected_before_sha256")
        spec = cls(
            schema_version=1,
            connector=_text(payload.get("connector"), "connector"),
            operation=_text(payload.get("operation"), "operation"),
            mode=mode,
            target=_text(payload.get("target"), "target"),
            parameters=dict(parameters),
            requested_scopes=scopes,
            idempotency_key=_text(payload.get("idempotency_key"), "idempotency_key"),
            expected_before_sha256=before,
            approval_required=bool(payload.get("approval_required", mode == "write")),
            destructive=bool(payload.get("destructive", False)),
            paid=bool(payload.get("paid", False)),
            sensitive_data=bool(payload.get("sensitive_data", False)),
            compensation=None if payload.get("compensation") is None else str(payload["compensation"]),
        )
        if spec.mode == "write" and not spec.approval_required:
            raise ValueError("write actions must require approval")
        if spec.destructive and spec.mode != "write":
            raise ValueError("destructive actions must use write mode")
        if any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.:" for character in spec.idempotency_key):
            raise ValueError("idempotency_key contains unsafe characters")
        return spec

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["requested_scopes"] = list(self.requested_scopes)
        return payload

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.to_dict())


class ConnectorActionAdapter(Protocol):
    connector_name: str

    def snapshot(self, spec: ActionSpec) -> Mapping[str, Any]: ...

    def preview(self, spec: ActionSpec, before: Mapping[str, Any]) -> Mapping[str, Any]: ...

    def execute(self, spec: ActionSpec, preview: Mapping[str, Any]) -> Mapping[str, Any]: ...


def build_preview(adapter: ConnectorActionAdapter, spec: ActionSpec, *, created_at: str | None = None) -> dict[str, Any]:
    if adapter.connector_name != spec.connector:
        raise ValueError("adapter connector does not match action spec")
    before = dict(adapter.snapshot(spec))
    _json_value(before, "provider before state")
    before_sha = _fingerprint(before)
    if spec.expected_before_sha256 is not None and before_sha != spec.expected_before_sha256:
        raise ValueError("current remote state does not match expected_before_sha256")
    changes = dict(adapter.preview(spec, before))
    _json_value(changes, "provider proposed changes")
    material = {
        "schema_version": 1,
        "connector": spec.connector,
        "operation": spec.operation,
        "mode": spec.mode,
        "target": spec.target,
        "action_spec_sha256": spec.fingerprint,
        "idempotency_key": spec.idempotency_key,
        "requested_scopes": list(spec.requested_scopes),
        "before_state_sha256": before_sha,
        "before_state": before,
        "proposed_changes": changes,
        "approval_required": spec.approval_required,
        "destructive": spec.destructive,
        "paid": spec.paid,
        "sensitive_data": spec.sensitive_data,
        "compensation": spec.compensation,
        "created_at": created_at or _now(),
        "status": "preview",
        "executed": False,
        "evidence_boundary": "The preview describes a provider-specific proposed action and current state. It does not grant permission, reserve cost, or prove that execution will produce the previewed state."
    }
    fingerprint = _fingerprint(material)
    return {**material, "preview_id": f"preview-{fingerprint[:20]}", "fingerprint": fingerprint}


def validate_preview(payload: Mapping[str, Any], spec: ActionSpec | None = None) -> None:
    if payload.get("schema_version") != 1 or payload.get("status") != "preview" or payload.get("executed") is not False:
        raise ValueError("invalid action preview state")
    for field in ("preview_id", "connector", "operation", "target", "action_spec_sha256", "idempotency_key", "before_state_sha256", "created_at", "evidence_boundary"):
        _text(payload.get(field), field)
    _sha(payload.get("action_spec_sha256"), "action_spec_sha256")
    _sha(payload.get("before_state_sha256"), "before_state_sha256")
    material = dict(payload)
    preview_id = str(material.pop("preview_id"))
    fingerprint = str(material.pop("fingerprint", "")).lower()
    if _fingerprint(material) != fingerprint or preview_id != f"preview-{fingerprint[:20]}":
        raise ValueError("action preview fingerprint or ID mismatch")
    if spec is not None and payload.get("action_spec_sha256") != spec.fingerprint:
        raise ValueError("action preview covers a different spec")


def build_action_approval(preview: Mapping[str, Any], *, approved_by: str, approved_scopes: list[str], approved_at: str | None = None) -> dict[str, Any]:
    validate_preview(preview)
    scopes = sorted({_text(item, "approved scope") for item in approved_scopes})
    requested = set(map(str, preview.get("requested_scopes", [])))
    if not requested.issubset(scopes):
        raise ValueError("approved scopes do not cover requested scopes")
    material = {
        "schema_version": 1,
        "preview_id": preview["preview_id"],
        "preview_fingerprint": preview["fingerprint"],
        "action_spec_sha256": preview["action_spec_sha256"],
        "connector": preview["connector"],
        "operation": preview["operation"],
        "target": preview["target"],
        "before_state_sha256": preview["before_state_sha256"],
        "idempotency_key": preview["idempotency_key"],
        "approved_by": _text(approved_by, "approved_by"),
        "approved_scopes": scopes,
        "approved_at": approved_at or _now(),
        "approved": True,
        "evidence_boundary": "Approval authorizes the exact preview and scopes. It does not endorse the scientific content or waive provider, privacy, cost, or regulatory obligations."
    }
    return {**material, "fingerprint": _fingerprint(material)}


def validate_action_approval(approval: Mapping[str, Any], preview: Mapping[str, Any]) -> None:
    validate_preview(preview)
    if approval.get("schema_version") != 1 or approval.get("approved") is not True:
        raise ValueError("valid action approval is required")
    for field in ("preview_id", "preview_fingerprint", "action_spec_sha256", "before_state_sha256", "idempotency_key"):
        if approval.get(field) != preview.get(field if field != "preview_fingerprint" else "fingerprint"):
            raise ValueError(f"approval {field} does not match preview")
    material = dict(approval)
    fingerprint = str(material.pop("fingerprint", "")).lower()
    if _fingerprint(material) != fingerprint:
        raise ValueError("action approval fingerprint mismatch")


class ActionLedger:
    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS actions(idempotency_key TEXT PRIMARY KEY, action_spec_sha256 TEXT NOT NULL, receipt_json TEXT NOT NULL, created_at TEXT NOT NULL)"
            )

    def get(self, key: str) -> dict[str, Any] | None:
        with sqlite3.connect(self.path) as connection:
            row = connection.execute("SELECT receipt_json FROM actions WHERE idempotency_key=?", (key,)).fetchone()
        return None if row is None else json.loads(str(row[0]))

    def record(self, *, key: str, spec_sha256: str, receipt: Mapping[str, Any]) -> None:
        with sqlite3.connect(self.path) as connection:
            existing = connection.execute("SELECT action_spec_sha256, receipt_json FROM actions WHERE idempotency_key=?", (key,)).fetchone()
            if existing is not None:
                if str(existing[0]) != spec_sha256 or json.loads(str(existing[1])) != dict(receipt):
                    raise ValueError("idempotency key is already bound to a different action")
                return
            connection.execute(
                "INSERT INTO actions(idempotency_key, action_spec_sha256, receipt_json, created_at) VALUES(?,?,?,?)",
                (key, spec_sha256, json.dumps(dict(receipt), sort_keys=True, separators=(",", ":")), _now()),
            )


def execute_action(
    adapter: ConnectorActionAdapter,
    spec: ActionSpec,
    preview: Mapping[str, Any],
    *,
    approval: Mapping[str, Any] | None,
    ledger: ActionLedger,
    executed_at: str | None = None,
) -> dict[str, Any]:
    validate_preview(preview, spec)
    if adapter.connector_name != spec.connector:
        raise ValueError("adapter connector does not match action spec")
    existing = ledger.get(spec.idempotency_key)
    if existing is not None:
        if existing.get("action_spec_sha256") != spec.fingerprint:
            raise ValueError("idempotency key is already bound to a different spec")
        return existing
    if spec.mode == "write":
        if approval is None:
            raise ValueError("write action requires explicit approval")
        validate_action_approval(approval, preview)
    current = dict(adapter.snapshot(spec))
    _json_value(current, "provider current state")
    current_sha = _fingerprint(current)
    if current_sha != preview["before_state_sha256"]:
        raise ValueError("remote state changed after preview; create a new preview")
    result = dict(adapter.execute(spec, preview))
    _json_value(result, "provider execution result")
    after = dict(result.get("after_state", result))
    after_sha = _fingerprint(after)
    material = {
        "schema_version": 1,
        "action_id": "action-" + uuid.uuid4().hex[:20],
        "connector": spec.connector,
        "operation": spec.operation,
        "mode": spec.mode,
        "target": spec.target,
        "action_spec_sha256": spec.fingerprint,
        "preview_id": preview["preview_id"],
        "preview_fingerprint": preview["fingerprint"],
        "approval_fingerprint": None if approval is None else approval.get("fingerprint"),
        "idempotency_key": spec.idempotency_key,
        "before_state_sha256": current_sha,
        "after_state_sha256": after_sha,
        "after_state": after,
        "remote_object_ids": list(result.get("remote_object_ids", [])) if isinstance(result.get("remote_object_ids", []), list) else [],
        "provider_receipt": result.get("provider_receipt"),
        "compensation": spec.compensation,
        "executed_at": executed_at or _now(),
        "status": "executed",
        "evidence_boundary": "This receipt records a provider adapter action and before/after state hashes. It does not validate the scientific content, provider completeness, legal authorization, or successful downstream interpretation."
    }
    receipt = {**material, "fingerprint": _fingerprint(material)}
    ledger.record(key=spec.idempotency_key, spec_sha256=spec.fingerprint, receipt=receipt)
    return receipt


def validate_action_receipt(payload: Mapping[str, Any], spec: ActionSpec | None = None) -> None:
    if payload.get("schema_version") != 1 or payload.get("status") != "executed":
        raise ValueError("invalid action receipt state")
    for field in (
        "action_id",
        "connector",
        "operation",
        "mode",
        "target",
        "action_spec_sha256",
        "preview_id",
        "preview_fingerprint",
        "idempotency_key",
        "before_state_sha256",
        "after_state_sha256",
        "executed_at",
        "evidence_boundary",
    ):
        _text(payload.get(field), field)
    for field in (
        "action_spec_sha256",
        "preview_fingerprint",
        "before_state_sha256",
        "after_state_sha256",
    ):
        _sha(payload.get(field), field)
    material = dict(payload)
    fingerprint = str(material.pop("fingerprint", "")).lower()
    if _fingerprint(material) != fingerprint:
        raise ValueError("action receipt fingerprint mismatch")
    if spec is not None and payload.get("action_spec_sha256") != spec.fingerprint:
        raise ValueError("action receipt covers a different spec")
