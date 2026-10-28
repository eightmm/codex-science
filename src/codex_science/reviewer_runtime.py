"""Blinded scientific review packets and hash-covered review response intake.

The runtime prepares deterministic packets for a separate human or agent. It
never sends data to a model service, claims reviewer independence, or exposes
private chain-of-thought. Reviewer identity and independence remain attestations
that must be governed by the calling system.
"""

from __future__ import annotations

import hashlib
import json
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from codex_science.artifact_store import stream_sha256
from codex_science.artifacts import validate_bundle
from codex_science.cli_io import write_json_atomic
from codex_science.review_receipts import build_review_receipt, canonical_sha256, validate_review_receipt
from codex_science.review import evidence_node_has_successful_execution
from codex_science.rigor import CLAIM_STRENGTHS, TIERS


REVIEW_MODES = {"record", "source", "method", "reproduction"}
SEVERITIES = {"critical", "major", "minor", "suggestion"}
SENSITIVE_FRAGMENTS = {"token", "password", "secret", "credential", "private_key", "api_key", "apikey", "chain_of_thought", "hidden_rationale"}
EXCLUDED_PRODUCER_FIELDS = {"intended_conclusion", "producer_rationale", "chain_of_thought", "private_scratchpad", "hidden_answer", "suspected_bug"}


class _DefaultTier(str):
    """String sentinel that preserves a string-valued public default."""


_DEFAULT_TIER = _DefaultTier("standard")

# Kosmos reported lower statement accuracy for synthesis/interpretation than
# data-analysis or literature statements. This is only a review-order heuristic:
# it does not estimate claim reliability. Categories use recorded claim/evidence
# links only; unseen or unlinked evidence is not inferred.
REVIEW_PRIORITY_POLICY = {
    "source_note": "Kosmos preprint/vendor report: reported statement accuracy was ~85.5% for data analysis, ~82.1% for literature, and ~57.9% for synthesis/interpretation.",
    "basis": {
        "synthesis": "2+ distinct resolved sources/artifacts on supports edges, or claim kind causal/confirmatory",
        "literature": "all resolved supports links point to literature/source records",
        "data": "resolved supports links include executed analysis artifacts",
        "unknown": "otherwise",
    },
    "support_relations": ["supports"],
    "ignored_relations": ["contradicts"],
    "order": ["synthesis", "literature", "unknown", "data"],
    "evidence_boundary": "Heuristic ordering from recorded claim fields and resolvable supports links; unresolvable references remain unknown. This is not a reliability estimate.",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _fingerprint(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} is required")
    return value.strip()


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
    if isinstance(value, str) and "://" in value:
        try:
            parsed = urllib.parse.urlsplit(value)
            query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
            if query:
                query = [
                    (
                        key,
                        "[REDACTED]"
                        if any(fragment in key.lower() for fragment in SENSITIVE_FRAGMENTS)
                        else item,
                    )
                    for key, item in query
                ]
                return urllib.parse.urlunsplit(
                    (
                        parsed.scheme,
                        parsed.netloc,
                        parsed.path,
                        urllib.parse.urlencode(query),
                        parsed.fragment,
                    )
                )
        except ValueError:
            return "[REDACTED-INVALID-URL]"
    return value


def _material_claim_ids(manifest: Mapping[str, Any], sidecars: Mapping[str, Any]) -> list[str]:
    claim_register = sidecars.get("claim_by_id")
    if isinstance(claim_register, Mapping) and claim_register:
        return sorted(str(key) for key in claim_register)
    return sorted(str(item.get("id")) for item in manifest.get("claims", []) if isinstance(item, Mapping) and item.get("id"))


def _claim_kinds_with_manifest_fallback(claims: list[Any], manifest: Mapping[str, Any]) -> list[Any]:
    manifest_claims = {
        str(claim["id"]).strip(): claim
        for claim in manifest.get("claims", [])
        if isinstance(claim, Mapping) and claim.get("id")
    }
    resolved = []
    for claim in claims:
        if not isinstance(claim, Mapping):
            resolved.append(claim)
            continue
        item = dict(claim)
        manifest_claim = manifest_claims.get(str(claim.get("id", "")).strip())
        if "kind" not in item and manifest_claim is not None and "kind" in manifest_claim:
            item["kind"] = manifest_claim["kind"]
        resolved.append(item)
    return resolved


def _review_priority(manifest: Mapping[str, Any], claims: list[Any], sidecars: Mapping[str, Any]) -> list[dict[str, str | int]]:
    claims = _claim_kinds_with_manifest_fallback(claims, manifest)
    claim_by_id = {str(claim.get("id")): claim for claim in claims if isinstance(claim, Mapping) and claim.get("id")}
    graph = sidecars.get("graph_v2") or sidecars.get("evidence_graph")
    nodes = {str(node.get("id")): node for node in graph.get("nodes", []) if isinstance(node, Mapping)} if isinstance(graph, Mapping) else {}
    edges = graph.get("edges", []) if isinstance(graph, Mapping) else []
    artifact_paths = {str(item.get("path")) for item in manifest.get("artifacts", []) if isinstance(item, Mapping)}
    support: dict[str, set[str]] = {claim_id: set() for claim_id in _material_claim_ids(manifest, sidecars)}
    for edge in edges:
        if isinstance(edge, Mapping) and edge.get("relation") == "supports" and str(edge.get("target")) in support:
            support[str(edge["target"])].add(str(edge.get("source", "")))
    rows = []
    order = {basis: index for index, basis in enumerate(REVIEW_PRIORITY_POLICY["order"])}
    for claim_id in _material_claim_ids(manifest, sidecars):
        claim = claim_by_id.get(claim_id, {})
        refs = support.get(claim_id, set())
        source_nodes = [nodes.get(ref) for ref in refs]
        unresolved = any(node is None for node in source_nodes)
        if claim.get("kind") in {"causal", "confirmatory"}:
            basis = "synthesis"
        elif unresolved:
            basis = "unknown"
        elif len(refs) >= 2:
            basis = "synthesis"
        elif refs and all(node.get("type") == "study" for node in source_nodes if node is not None):
            basis = "literature"
        elif refs and all(
            node is not None
            and (
                node.get("type") == "execution" and evidence_node_has_successful_execution(manifest, ref, node)
                or (
                    node.get("type") == "artifact"
                    and (str(node.get("path", ref)) in artifact_paths or ref in artifact_paths)
                    and evidence_node_has_successful_execution(manifest, ref, node)
                )
            )
            for ref, node in ((ref, nodes.get(ref)) for ref in refs)
        ):
            basis = "data"
        else:
            basis = "unknown"
        rows.append({"claim_id": claim_id, "basis": basis, "priority": order[basis] + 1})
    return sorted(rows, key=lambda row: (order[row["basis"]], row["claim_id"]))


def _review_order_policy(priority: list[dict[str, str | int]], tier: str, tier_source: str) -> dict[str, Any]:
    ranked = [row["claim_id"] for row in priority]
    synthesis = [row["claim_id"] for row in priority if row["basis"] == "synthesis"]
    suggested = ranked if tier == "full" else synthesis + [claim_id for claim_id in ranked if claim_id not in synthesis][: (1 if tier == "quick" else 3)]
    return {
        "tier": tier,
        "tier_source": tier_source,
        "suggested_first_claim_ids": sorted(set(suggested), key=lambda claim_id: (ranked.index(claim_id), claim_id)),
        "scope": "Advisory ordering only; every material claim must still be reviewed.",
    }


def build_review_packet(
    manifest_path: Path,
    *,
    review_modes: list[str],
    independent_required: bool = True,
    review_questions: list[str] | None = None,
    created_at: str | None = None,
    tier: str = _DEFAULT_TIER,
) -> dict[str, Any]:
    """Build a review packet with advisory ordering; every material claim remains required for review."""
    tier_source = "default" if tier is _DEFAULT_TIER else "caller"
    if not isinstance(tier, str) or tier not in TIERS:
        raise ValueError(f"tier must be one of {TIERS!r}")
    tier = str(tier)
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
    claims = _claim_kinds_with_manifest_fallback(claims, manifest)
    graph = sidecars.get("graph_v2") or sidecars.get("evidence_graph")
    use_default_questions = review_questions is None
    questions = list(review_questions) if review_questions is not None else [
        "Does each material claim have direct, correctly attributed evidence?",
        "Do the design, controls, splits, metrics, uncertainty, and inference level support the claim?",
        "Are duplicated sources, shared cohorts or samples, and model-training overlap represented correctly?",
        "Do reported figures, tables, and values agree with the saved artifacts and execution record?",
        "Which alternative explanations or counterevidence remain unresolved?"
    ]
    kind_questions = {
        "causal": [
            "Is the causal effect identified by the study design and assumptions?",
            "Could confounding explain the reported causal relationship?",
            "Does the evidence establish temporality from cause to outcome?",
        ],
        "confirmatory": [
            "Was the hypothesis prespecified before outcome inspection?",
            "Was the analysis prespecified, including outcomes and exclusions?",
            "Was multiplicity controlled or otherwise addressed?",
        ],
        "associational": [
            "Does the claim text avoid causal language unsupported by an associational claim?",
        ],
        "descriptive": [
            "Is the denominator for each descriptive result stated?",
            "Is the sampling frame stated and adequate for the described population?",
        ],
    }
    seen_kinds: set[str] = set()
    for claim in claims:
        kind = claim.get("kind") if isinstance(claim, Mapping) else None
        if (
            use_default_questions
            and isinstance(kind, str)
            and kind in CLAIM_STRENGTHS
            and kind in kind_questions
            and kind not in seen_kinds
        ):
            questions.extend(kind_questions[kind])
            seen_kinds.add(kind)
    review_priority = _review_priority(manifest, claims, sidecars)
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
        "review_priority": review_priority,
        "review_order_policy": _review_order_policy(review_priority, tier, tier_source),
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
    if isinstance(sidecars.get("protocol_commitment_context"), dict):
        material["protocol_commitment_context"] = _redact(sidecars["protocol_commitment_context"])
    if sidecars.get("research_cycles"):
        material["research_cycles"] = _redact(sidecars["research_cycles"])
        material["review_questions"].extend([
            "Do the method's computation and implementation address its stated assumptions and hypotheses?",
            "Do preregistered predictions and controls distinguish explanations, including null and failed attempts?",
            "Are revisions traceable to observations without rewriting earlier predictions or expanding the tested applicability?",
            "Keep execution integrity, method correctness, reproduction, explanation support and novelty separate."
        ])
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
    if "review_priority" in payload:
        rows = payload["review_priority"]
        if not isinstance(rows, list) or any(not isinstance(row, Mapping) or set(row) != {"claim_id", "basis", "priority"} or row.get("basis") not in REVIEW_PRIORITY_POLICY["order"] or type(row.get("priority")) is not int or row.get("priority") != REVIEW_PRIORITY_POLICY["order"].index(row["basis"]) + 1 for row in rows):
            raise ValueError("invalid review_priority")
        claim_ids = [row.get("claim_id") for row in rows]
        if any(not isinstance(claim_id, str) or not claim_id.strip() for claim_id in claim_ids) or len(claim_ids) != len(set(claim_ids)):
            raise ValueError("review_priority claim IDs must be non-empty and unique")
        expected_order = sorted(rows, key=lambda row: (REVIEW_PRIORITY_POLICY["order"].index(row["basis"]), row["claim_id"]))
        if rows != expected_order:
            raise ValueError("review_priority is not deterministically ordered")
        if set(claim_ids) != set(map(str, payload["material_claim_ids"])):
            raise ValueError("review_priority must cover material claims")
    if "review_order_policy" in payload:
        policy = payload["review_order_policy"]
        if (
            not isinstance(policy, Mapping)
            or not isinstance(policy.get("tier"), str)
            or policy.get("tier") not in TIERS
            or not isinstance(policy.get("tier_source"), str)
            or policy.get("tier_source") not in {"caller", "default"}
            or not isinstance(policy.get("suggested_first_claim_ids"), list)
            or policy.get("scope") != "Advisory ordering only; every material claim must still be reviewed."
        ):
            raise ValueError("invalid review_order_policy")
        suggested = policy["suggested_first_claim_ids"]
        if (
            any(not isinstance(claim_id, str) or not claim_id.strip() for claim_id in suggested)
            or len(suggested) != len(set(suggested))
            or not set(suggested).issubset(set(map(str, payload["material_claim_ids"])))
            or (policy["tier_source"] == "default" and policy["tier"] != "standard")
        ):
            raise ValueError("invalid suggested review order claim IDs")
        if "review_priority" in payload and dict(policy) != _review_order_policy(payload["review_priority"], str(policy["tier"]), str(policy["tier_source"])):
            raise ValueError("review_order_policy does not match review_priority")
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
    response_modes_raw = response.get("review_modes", [])
    if not isinstance(response_modes_raw, list):
        raise ValueError("response review_modes must be a list")
    response_modes = sorted({_text(item, "response review mode") for item in response_modes_raw})
    if not response_modes or set(response_modes) - set(packet["review_modes"]):
        raise ValueError("response review modes are empty or exceed the packet")
    reviewed_claims_raw = response.get("reviewed_claim_ids", [])
    if not isinstance(reviewed_claims_raw, list):
        raise ValueError("reviewed_claim_ids must be a list")
    reviewed_claims = sorted({_text(item, "reviewed claim ID") for item in reviewed_claims_raw})
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
    receipt["fingerprint"] = canonical_sha256(material)
    validate_review_receipt(receipt)
    return receipt


def respond_to_review(
    task_path: Path,
    *,
    reviewer: str,
    independent: bool,
    status: str,
    limitations: list[str],
    reviewed_paths: list[str] | None = None,
    reviewed_all: bool = False,
    findings_path: Path | None = None,
    claim_ids: list[str] | None = None,
    blocked_reason: str = "",
    modes: list[str] | None = None,
    output: Path | None = None,
) -> dict[str, Any]:
    """Fill a reviewer response's identity and hashes from the packet; judgment fields stay caller-supplied.

    Raises one ValueError listing every input problem and writes nothing on failure.
    """
    task_path = Path(task_path)
    run_dir = task_path.resolve().parent
    packet = json.loads(task_path.read_text(encoding="utf-8"))
    if not isinstance(packet, dict):
        raise ValueError(f"JSON object required: {task_path}")
    validate_review_packet(packet)
    problems: list[str] = []
    packet_hashes = {str(item["path"]): str(item["sha256"]).lower() for item in packet["artifacts"]}

    if bool(reviewed_all) == bool(reviewed_paths):
        problems.append("pass exactly one of --reviewed-all or --reviewed PATH")
    covered = sorted(packet_hashes) if reviewed_all else sorted(set(reviewed_paths or []))
    unknown = [path for path in covered if path not in packet_hashes]
    if unknown:
        problems.append(f"reviewed paths not in packet: {', '.join(unknown)}")
    stale: list[str] = []
    for path in covered:
        if path in unknown:
            continue
        target = (run_dir / path).resolve()
        try:
            target.relative_to(run_dir)
            current = stream_sha256(target)[0] if target.is_file() else None
        except (ValueError, OSError):
            current = None
        if current != packet_hashes[path]:
            stale.append(path)
    if stale:
        problems.append(f"artifact bytes no longer match the packet (stale packet): {', '.join(stale)}")

    packet_modes = list(packet["review_modes"])
    response_modes = sorted(set(modes)) if modes else packet_modes
    if set(response_modes) - set(packet_modes):
        problems.append(f"modes not in packet: {', '.join(sorted(set(response_modes) - set(packet_modes)))}")
    material_claims = [str(item) for item in packet["material_claim_ids"]]
    response_claims = sorted(set(claim_ids)) if claim_ids else sorted(material_claims)
    if set(response_claims) - set(material_claims):
        problems.append(f"claims not in packet: {', '.join(sorted(set(response_claims) - set(material_claims)))}")
    if set(material_claims) - set(response_claims) and not blocked_reason.strip():
        problems.append("--claim narrows coverage; --blocked-reason is required")

    findings: list[Any] = []
    if findings_path is not None:
        try:
            loaded = json.loads(Path(findings_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            loaded = None
            problems.append(f"findings file unreadable: {error}")
        else:
            if not isinstance(loaded, list):
                problems.append("findings file must contain a JSON list")
            else:
                for index, item in enumerate(loaded):
                    if not isinstance(item, dict):
                        problems.append(f"finding {index} must be an object")
                        continue
                    filled = dict(item)
                    evidence = filled.get("evidence", [])
                    if isinstance(evidence, list):
                        filled["evidence"] = []
                        for number, entry in enumerate(evidence):
                            label = f"finding {item.get('id', index)} evidence {number}"
                            if not isinstance(entry, dict):
                                problems.append(f"{label} must be an object")
                                filled["evidence"].append(entry)
                                continue
                            entry = dict(entry)
                            path = str(entry.get("artifact_path", ""))
                            if path not in packet_hashes:
                                problems.append(f"{label} path not in packet: {path or '<missing>'}")
                            elif entry.get("artifact_sha256") is None:
                                entry["artifact_sha256"] = packet_hashes[path]
                            elif str(entry["artifact_sha256"]).lower() != packet_hashes[path]:
                                problems.append(f"{label} hash differs from packet: {path}")
                            filled["evidence"].append(entry)
                    findings.append(filled)

    response = {
        "schema_version": 1,
        "review_task_id": packet["review_task_id"],
        "packet_fingerprint": packet["fingerprint"],
        "reviewer": reviewer,
        "independent": independent,
        "review_modes": response_modes,
        "reviewed_claim_ids": response_claims,
        "reviewed_artifacts": [{"path": path, "sha256": packet_hashes[path]} for path in covered if path in packet_hashes],
        "findings": findings,
        "limitations": list(limitations),
        "status": status,
    }
    if blocked_reason.strip():
        response["blocked_reason"] = blocked_reason.strip()

    destination = Path(output) if output is not None else task_path.parent / "reviewer-response.json"
    if destination.is_symlink():
        problems.append(f"output is a symlink: {destination}")
    resolved = destination.resolve()
    try:
        resolved.relative_to(run_dir)
    except ValueError:
        problems.append(f"output is outside the run directory: {destination}")
    source_manifest = Path(str(packet["source_manifest_path"]))
    protected = {task_path.resolve(), run_dir / "manifest.json", run_dir / source_manifest.name, source_manifest.resolve(), *((run_dir / path).resolve() for path in packet_hashes)}
    if resolved in protected:
        problems.append(f"output would overwrite a packet or manifest file: {destination}")

    effective = None
    if not problems:
        try:
            effective = finalize_review_response(packet, response)["status"]
        except ValueError as error:
            problems.append(str(error))
    if problems:
        raise ValueError("; ".join(problems))
    write_json_atomic(destination, response)
    return {
        "output": str(resolved),
        "requested_status": status,
        "effective_status": effective,
        "reviewed_artifacts": len(response["reviewed_artifacts"]),
        "reviewed_claims": len(response_claims),
        "findings": len(findings),
    }
