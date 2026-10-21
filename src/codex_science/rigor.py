"""Deterministic minimum-rigor classification for research requests."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

REQUEST_SCHEMA = "rigor-request-v1"
DECISION_SCHEMA = "rigor-decision-v1"
TIERS = ("quick", "standard", "full")
CLAIM_STRENGTHS = ("descriptive", "associational", "causal", "confirmatory")

_FIELDS = {
    "schema", "deliverable", "source_count", "synthesis", "computation",
    "claim_strength", "domain_risk", "approval_gated_actions",
    "requested_tier", "current_tier",
}
_REQUIRED = {"schema", "deliverable", "source_count", "claim_strength"}
_GATE_POLICY = {
    "unchanged_by_tier": True,
    "audit_gate": "unchanged",
    "approval_gates": "unchanged",
    "inactive_skill_acknowledgement": "unchanged",
    "claim_boundaries": "unchanged",
}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _validate(request: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(request, Mapping):
        raise ValueError("request must be an object")
    if any(not isinstance(key, str) for key in request):
        raise ValueError("request keys must be strings")
    unknown = set(request) - _FIELDS
    if unknown:
        raise ValueError(f"unknown request keys: {sorted(unknown)!r}")
    missing = _REQUIRED - set(request)
    if missing:
        raise ValueError(f"missing required keys: {sorted(missing)!r}")
    if request["schema"] != REQUEST_SCHEMA:
        raise ValueError(f"schema must be {REQUEST_SCHEMA}")
    enums = {
        "deliverable": ("answer", "durable_artifact", "reviewed_package"),
        "claim_strength": CLAIM_STRENGTHS,
        "domain_risk": ("general", "high_stakes"),
        "requested_tier": TIERS,
        "current_tier": TIERS,
    }
    normalized = dict(request)
    defaults = {"synthesis": False, "computation": False,
                "domain_risk": "general", "approval_gated_actions": False,
                "requested_tier": None, "current_tier": None}
    for key, value in defaults.items():
        normalized.setdefault(key, value)
    for key, allowed in enums.items():
        value = normalized[key]
        if key in ("requested_tier", "current_tier") and value is None:
            continue
        if not isinstance(value, str) or value not in allowed:
            raise ValueError(f"{key} must be one of {allowed!r}" +
                             (" or null" if key in ("requested_tier", "current_tier") else ""))
    count = normalized["source_count"]
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise ValueError("source_count must be a non-negative integer")
    for key in ("synthesis", "computation", "approval_gated_actions"):
        if type(normalized[key]) is not bool:
            raise ValueError(f"{key} must be a boolean")
    return normalized


def classify_rigor(request: Mapping[str, Any]) -> dict[str, Any]:
    """Return a stable tier decision and its machine-readable rule reasons."""
    data = _validate(request)
    fired: list[dict[str, str]] = []

    def add(code: str, field: str, tier: str) -> None:
        fired.append({"code": code, "field": field, "tier": tier})

    if data["claim_strength"] in ("causal", "confirmatory"):
        add("claim_strength", "claim_strength", "full")
    if data["domain_risk"] == "high_stakes":
        add("high_stakes_domain", "domain_risk", "full")
    if data["synthesis"] and data["source_count"] >= 3:
        add("multi_source_synthesis", "synthesis", "full")
    if data["deliverable"] in ("durable_artifact", "reviewed_package"):
        add("durable_deliverable", "deliverable", "standard")
    if data["computation"]:
        add("computation", "computation", "standard")
    if data["synthesis"] and data["source_count"] < 3:
        add("synthesis", "synthesis", "standard")
    if data["source_count"] > 3:
        add("many_sources", "source_count", "standard")
    if data["claim_strength"] == "associational":
        add("associational_claim", "claim_strength", "standard")
    if data["approval_gated_actions"]:
        add("approval_gated_action", "approval_gated_actions", "standard")
    floor = max((reason["tier"] for reason in fired), key=TIERS.index, default="quick")
    if not fired:
        add("default_quick", "request", "quick")
    tier = max((floor, data["requested_tier"] or "quick", data["current_tier"] or "quick"), key=TIERS.index)
    if data["requested_tier"] and TIERS.index(data["requested_tier"]) > TIERS.index(floor):
        fired.append({"code": "requested_tier", "field": "requested_tier", "tier": data["requested_tier"]})
    if (data["current_tier"] and TIERS.index(data["current_tier"]) > TIERS.index(floor)
            and tier == data["current_tier"]):
        fired.append({"code": "retained_current_tier", "field": "current_tier", "tier": data["current_tier"]})
    if data["requested_tier"] and TIERS.index(data["requested_tier"]) < TIERS.index(floor):
        fired.append({"code": "requested_below_floor", "field": "requested_tier", "tier": floor})
    if data["current_tier"] and TIERS.index(tier) > TIERS.index(data["current_tier"]):
        fired.append({"code": "escalated", "field": "current_tier", "tier": tier})
    reasons = sorted(fired, key=lambda item: (item["code"], item["field"], TIERS.index(item["tier"])))
    requirements = {
        "checkpoint": tier != "quick",
        "artifact_bundle": tier != "quick",
        "provenance_bundle": tier != "quick",
        "deterministic_validation": tier != "quick",
        "independent_review": "record" if tier != "quick" else None,
        "label": "unreviewed_quick_answer" if tier == "quick" else None,
        "primary_citations_required": True,
        "offer_escalation": tier == "quick",
        "research_contract": tier == "full",
        "claim_evidence_graph": tier == "full",
        "lanes": tier == "full",
        "review_modes": ["record", "source", "method"] if tier == "full" else (["record"] if tier == "standard" else []),
    }
    return {
        "schema": DECISION_SCHEMA, "tier": tier, "floor": floor,
        "requested_tier": data["requested_tier"], "current_tier": data["current_tier"],
        "escalated": bool(data["current_tier"] and TIERS.index(tier) > TIERS.index(data["current_tier"])),
        "reasons": reasons, "requirements": requirements,
        "gate_policy": dict(_GATE_POLICY), "input_sha256": hashlib.sha256(_canonical(data)).hexdigest(),
    }
