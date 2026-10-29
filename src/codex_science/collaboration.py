"""Hash-aware annotations, run diffs, and selective rerun planning."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Mapping

from codex_science.connector_contract import canonical_json_bytes
from codex_science.evidence_graph_v2 import impacted_nodes

ANNOTATION_TYPES = {"question", "finding", "decision", "note", "correction"}
ANNOTATION_STATUSES = {"open", "resolved", "dismissed", "stale-anchor"}


def _sha(value: Any, label: str) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"{label} must be a SHA-256 digest")
    return text


def _resolve_json_pointer(value: Any, pointer: Any) -> Any:
    """Resolve RFC 6901 tokens, preserving empty keys and strict array indices."""
    if not isinstance(pointer, str) or (pointer and not pointer.startswith("/")):
        raise ValueError("json_pointer must be an RFC 6901 pointer")
    if pointer == "":
        return value
    for raw in pointer[1:].split("/"):
        if re.search(r"~(?![01])", raw):
            raise ValueError("json_pointer contains an invalid escape")
        part = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(value, Mapping) and part in value:
            value = value[part]
        elif isinstance(value, list) and re.fullmatch(r"0|[1-9][0-9]*", part) and int(part) < len(value):
            value = value[int(part)]
        else:
            raise ValueError("json_pointer does not resolve")
    return value


def validate_annotation(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported annotation schema")
    for field in ("annotation_id", "author", "text", "created_at"):
        if not str(payload.get(field, "")).strip():
            raise ValueError(f"annotation {field} is required")
    if not isinstance(payload.get("type"), str) or payload["type"] not in ANNOTATION_TYPES:
        raise ValueError("invalid annotation type")
    if not isinstance(payload.get("status"), str) or payload["status"] not in ANNOTATION_STATUSES:
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


def validate_resolution_event(event: dict[str, Any]) -> None:
    if not isinstance(event, dict) or event.get("schema_version") != 1:
        raise ValueError("unsupported resolution event schema")
    for field in ("annotation_id", "resolver", "resolved_at"):
        if not isinstance(event.get(field), str) or not event[field].strip():
            raise ValueError(f"resolution {field} is required")
    if not isinstance(event.get("status"), str) or event["status"] not in {"resolved", "dismissed"}:
        raise ValueError("invalid resolution status")
    _sha(event.get("artifact_sha256"), "resolution artifact_sha256")
    if "note" in event and not isinstance(event["note"], str):
        raise ValueError("resolution note must be a string")


@contextmanager
def annotation_resolution_lock(run_dir: Path, *, exclusive: bool = True):
    root = Path(run_dir).resolve(strict=True)
    directory = root / "annotations"
    if directory.is_symlink():
        raise ValueError("annotation directory must not be a symlink")
    if exclusive:
        directory.mkdir(exist_ok=True)
    elif not directory.exists():
        yield root
        return
    lock_path = directory / ".resolutions.lock"
    flags = os.O_RDONLY if not exclusive else os.O_CREAT | os.O_RDWR
    flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(lock_path, flags, 0o644)
    except FileNotFoundError:
        if exclusive:
            raise
        yield root
        return
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("resolution lock must be a regular file")
        if exclusive:
            os.fchmod(descriptor, 0o644)
        fcntl.flock(descriptor, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        yield root
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def _read_resolution_events(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "annotations" / "resolutions.jsonl"
    if path.parent.is_symlink():
        raise ValueError("resolution event directory must not be a symlink")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        return []
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("resolution event sidecar must be a regular file")
        with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
            descriptor = -1
            events = []
            for line_number, line in enumerate(stream, 1):
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(f"invalid resolution event at line {line_number}: {error}") from error
                if not isinstance(event, dict):
                    raise ValueError(f"resolution event at line {line_number} must be an object")
                events.append(event)
            return events
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def load_resolution_events(run_dir: Path, *, lock_held: bool = False) -> list[dict[str, Any]]:
    """Read resolution history consistently; event bytes are not manifest-covered."""
    root = Path(run_dir).resolve(strict=True)
    directory = root / "annotations"
    if directory.is_symlink():
        raise ValueError("resolution event directory must not be a symlink")
    lock_path = directory / ".resolutions.lock"
    event_path = directory / "resolutions.jsonl"
    if lock_held:
        return _read_resolution_events(root)
    if lock_path.is_symlink():
        raise ValueError("resolution lock must not be a symlink")
    if event_path.is_symlink():
        raise ValueError("resolution event sidecar must not be a symlink")
    if lock_path.exists():
        with annotation_resolution_lock(root, exclusive=False):
            return _read_resolution_events(root)
    if event_path.exists():
        return _read_resolution_events(root)
    return []


def _append_resolution_event_locked(root: Path, event: dict[str, Any]) -> None:
    path = root / "annotations" / "resolutions.jsonl"
    flags = os.O_RDWR | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    descriptor = os.open(path, flags, 0o644)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("resolution event sidecar must be a regular file")
        os.fchmod(descriptor, 0o644)
        payload = json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        size = os.fstat(descriptor).st_size
        if size and os.pread(descriptor, 1, size - 1) != b"\n":
            payload = b"\n" + payload
        remaining = memoryview(payload)
        while remaining:
            written = os.write(descriptor, remaining)
            if written <= 0:
                raise OSError("short write while appending resolution event")
            remaining = remaining[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def append_resolution_event(run_dir: Path, event: dict[str, Any], *, lock_held: bool = False) -> None:
    """Append one complete JSONL record while holding the exclusive ledger lock."""
    validate_resolution_event(event)
    root = Path(run_dir).resolve(strict=True)
    if lock_held:
        _append_resolution_event_locked(root, event)
    else:
        with annotation_resolution_lock(root):
            _append_resolution_event_locked(root, event)


def fold_annotation_resolutions(
    annotations: Iterable[dict[str, Any]], events: Iterable[dict[str, Any]],
    artifact_hashes: Mapping[str, str],
) -> list[dict[str, Any]]:
    """Apply append-ordered resolutions while preserving stale-anchor precedence."""
    annotation_list = list(annotations)
    checked_events = list(events)
    for annotation in annotation_list:
        validate_annotation(annotation)
    latest: dict[str, dict[str, Any]] = {}
    known = {str(item["annotation_id"]): item for item in annotation_list}
    if checked_events and len(known) != len(annotation_list):
        raise ValueError("annotation IDs must be unique when folding resolutions")
    for event in checked_events:
        validate_resolution_event(event)
        annotation_id = str(event["annotation_id"])
        if annotation_id not in known:
            raise ValueError(f"resolution refers to unknown annotation: {annotation_id}")
        latest[annotation_id] = event
    results = []
    for annotation in annotation_list:
        item = dict(annotation)
        annotation_id = str(item["annotation_id"])
        resolution = latest.get(annotation_id)
        current_hash = artifact_hashes.get(str(item["anchor"]["artifact_path"]))
        anchor_hash = str(item["anchor"]["artifact_sha256"]).lower()
        resolution_uses_old_anchor = bool(
            resolution and str(resolution["artifact_sha256"]).lower() != anchor_hash
        )
        if current_hash != anchor_hash or resolution_uses_old_anchor:
            item["status"] = "stale-anchor"
        elif resolution:
            item["status"] = resolution["status"]
        item["latest_resolution"] = dict(resolution) if resolution else None
        results.append(item)
    return results


def _diff_record_map(manifest: Mapping[str, Any], section: str) -> dict[str | tuple[str], Any]:
    if not isinstance(manifest, Mapping):
        raise ValueError("manifest must be an object")
    records = manifest.get(section, [])
    if not isinstance(records, list):
        raise ValueError(f"manifest {section} must be a list")
    fields, label = {
        "artifacts": (("path",), "artifact path"),
        "claims": (("id",), "claim id"),
        "inputs": (("identifier", "id", "query_id", "url", "path"), "input identity"),
    }[section]
    result: dict[str | tuple[str], Any] = {}
    explicit_identities: set[str] = set()
    for record in records:
        if not isinstance(record, Mapping):
            raise ValueError(f"manifest {section} records must be objects")
        identity = next((record[field] for field in fields
                         if isinstance(record.get(field), str) and record[field].strip()), None)
        if identity is None and section == "inputs":
            canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            # Tuple keys cannot collide with any explicit string identity.
            identity = (hashlib.sha256(canonical.encode("utf-8")).hexdigest(),)
        else:
            if identity is None:
                raise ValueError(f"{label} must be a non-empty string")
            if identity in explicit_identities:
                raise ValueError(f"duplicate {label}: {identity}")
            explicit_identities.add(identity)
        value = record
        if section == "artifacts":
            digest = record.get("sha256")
            if not isinstance(digest, str) or not digest.strip():
                raise ValueError("artifact sha256 must be a non-empty string")
            value = {**record, "sha256": digest.lower()}
        result[identity] = value
    return result


def diff_runs(previous: Mapping[str, Any], current: Mapping[str, Any]) -> dict[str, Any]:
    """Preserve JSON numeric and boolean distinctions when invalidating reviews."""
    old, new = _diff_record_map(previous, "artifacts"), _diff_record_map(current, "artifacts")
    changed = sorted(path for path in old.keys() & new.keys()
                     if canonical_json_bytes(old[path]) != canonical_json_bytes(new[path]))
    old_claims = _diff_record_map(previous, "claims")
    new_claims = _diff_record_map(current, "claims")
    changed_claims = sorted(key for key in old_claims.keys() & new_claims.keys()
                            if canonical_json_bytes(old_claims[key]) != canonical_json_bytes(new_claims[key]))
    old_inputs = _diff_record_map(previous, "inputs")
    new_inputs = _diff_record_map(current, "inputs")

    def input_ids(keys: Iterable[str | tuple[str]]) -> list[str]:
        return sorted(key[0] if isinstance(key, tuple) else key for key in keys)

    changed_inputs = input_ids(key for key in old_inputs.keys() & new_inputs.keys()
                              if canonical_json_bytes(old_inputs[key]) != canonical_json_bytes(new_inputs[key]))
    environment_changed = canonical_json_bytes(previous.get("environment")) != canonical_json_bytes(current.get("environment"))
    code_changed = canonical_json_bytes(previous.get("code")) != canonical_json_bytes(current.get("code"))
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
        "inputs": {
            "added": input_ids(new_inputs.keys() - old_inputs.keys()),
            "removed": input_ids(old_inputs.keys() - new_inputs.keys()),
            "changed": changed_inputs,
        },
        "code_changed": code_changed,
        "environment_changed": environment_changed,
        "review_invalidated": bool(
            changed or old.keys() != new.keys() or changed_claims or old_claims.keys() != new_claims.keys()
            or code_changed or environment_changed or changed_inputs or old_inputs.keys() != new_inputs.keys()
        ),
    }


def selective_rerun_plan(
    *, changed_nodes: Iterable[str], edges: list[dict[str, Any]],
    steps: Iterable[dict[str, Any]], review_paths: Iterable[str] = (),
) -> dict[str, Any]:
    changed_nodes = list(changed_nodes)
    steps = list(steps)
    impacted = impacted_nodes(changed_nodes, edges)
    impacted_set = set(impacted)
    while True:
        selected: list[dict[str, Any]] = []
        outputs = set(impacted_set)
        for step in steps:
            produced = set(map(str, step.get("produces", [])))
            consumes = set(map(str, step.get("consumes", [])))
            if produced & impacted_set or consumes & impacted_set:
                outputs.update(produced)
                selected.append({
                    "id": step.get("id"),
                    "description": step.get("description", step.get("id")),
                    "requires_approval": bool(step.get("requires_approval", False)),
                    "consumes": sorted(consumes),
                    "produces": sorted(produced),
                })
        impacted = impacted_nodes(outputs, edges)
        if set(impacted) == impacted_set:
            break
        impacted_set = set(impacted)
    return {
        "schema_version": 1,
        "changed_nodes": sorted(set(map(str, changed_nodes))),
        "impacted_nodes": impacted,
        "rerun_steps": selected,
        "invalidated_review_receipts": sorted(set(map(str, review_paths))) if impacted else [],
        "approval_required": any(item["requires_approval"] for item in selected),
    }
