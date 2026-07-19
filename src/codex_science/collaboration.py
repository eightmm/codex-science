"""Hash-aware annotations, run diffs, and selective rerun planning."""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from codex_science.evidence_graph_v2 import impacted_nodes

ANNOTATION_TYPES = {"question", "finding", "decision", "note", "correction"}
ANNOTATION_STATUSES = {"open", "resolved", "dismissed", "stale-anchor"}


def _sha(value: Any, label: str) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"{label} must be a SHA-256 digest")
    return text


def validate_annotation(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported annotation schema")
    for field in ("annotation_id", "author", "text", "created_at"):
        if not str(payload.get(field, "")).strip():
            raise ValueError(f"annotation {field} is required")
    if payload.get("type") not in ANNOTATION_TYPES:
        raise ValueError("invalid annotation type")
    if payload.get("status") not in ANNOTATION_STATUSES:
        raise ValueError("invalid annotation status")
    anchor = payload.get("anchor")
    if not isinstance(anchor, dict):
        raise ValueError("annotation anchor must be an object")
    if not str(anchor.get("artifact_path", "")).strip():
        raise ValueError("annotation artifact_path is required")
    _sha(anchor.get("artifact_sha256"), "annotation artifact_sha256")
    if not any(str(anchor.get(field, "")).strip() for field in ("json_pointer", "claim_id", "line_range")):
        raise ValueError("annotation anchor needs json_pointer, claim_id, or line_range")


def stale_annotations(annotations: Iterable[dict[str, Any]], artifact_hashes: Mapping[str, str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for raw in annotations:
        validate_annotation(raw)
        item = dict(raw)
        anchor = dict(item["anchor"])
        current = artifact_hashes.get(str(anchor["artifact_path"]))
        if current != str(anchor["artifact_sha256"]).lower():
            item["status"] = "stale-anchor"
        results.append(item)
    return results


def _artifact_map(manifest: Mapping[str, Any]) -> dict[str, str]:
    return {str(item["path"]): str(item["sha256"]).lower() for item in manifest.get("artifacts", [])}


def diff_runs(previous: Mapping[str, Any], current: Mapping[str, Any]) -> dict[str, Any]:
    old, new = _artifact_map(previous), _artifact_map(current)
    changed = sorted(path for path in old.keys() & new.keys() if old[path] != new[path])
    old_claims = {str(item.get("id")): item for item in previous.get("claims", [])}
    new_claims = {str(item.get("id")): item for item in current.get("claims", [])}
    changed_claims = sorted(key for key in old_claims.keys() & new_claims.keys() if old_claims[key] != new_claims[key])
    environment_changed = previous.get("environment") != current.get("environment")
    code_changed = previous.get("code") != current.get("code")
    return {
        "schema_version": 1,
        "previous_run_id": previous.get("run_id"),
        "current_run_id": current.get("run_id"),
        "artifacts": {
            "added": sorted(new.keys() - old.keys()),
            "removed": sorted(old.keys() - new.keys()),
            "changed": changed,
        },
        "claims": {
            "added": sorted(new_claims.keys() - old_claims.keys()),
            "removed": sorted(old_claims.keys() - new_claims.keys()),
            "changed": changed_claims,
        },
        "code_changed": code_changed,
        "environment_changed": environment_changed,
        "review_invalidated": bool(changed or old.keys() != new.keys() or changed_claims or code_changed or environment_changed),
    }


def selective_rerun_plan(
    *, changed_nodes: Iterable[str], edges: list[dict[str, Any]],
    steps: Iterable[dict[str, Any]], review_paths: Iterable[str] = (),
) -> dict[str, Any]:
    impacted = impacted_nodes(changed_nodes, edges)
    impacted_set = set(impacted)
    selected: list[dict[str, Any]] = []
    for step in steps:
        produced = set(map(str, step.get("produces", [])))
        consumes = set(map(str, step.get("consumes", [])))
        if produced & impacted_set or consumes & impacted_set:
            selected.append({
                "id": step.get("id"),
                "description": step.get("description", step.get("id")),
                "requires_approval": bool(step.get("requires_approval", False)),
                "consumes": sorted(consumes),
                "produces": sorted(produced),
            })
    return {
        "schema_version": 1,
        "changed_nodes": sorted(set(map(str, changed_nodes))),
        "impacted_nodes": impacted,
        "rerun_steps": selected,
        "invalidated_review_receipts": sorted(set(map(str, review_paths))) if impacted else [],
        "approval_required": any(item["requires_approval"] for item in selected),
    }
