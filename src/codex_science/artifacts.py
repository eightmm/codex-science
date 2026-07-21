"""Structured, reproducible analysis artifact manifests and bundle validation."""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any

from codex_science.artifact_store import describe_directory, stream_sha256, validate_descriptor

REQUIRED_FIELDS = {
    "schema_version", "run_id", "question", "plan", "inputs", "code",
    "executions", "environment", "artifacts", "claims", "review",
}
LOCAL_ARTIFACT_TYPES = {"file", "chunked-file", "directory-tree"}


def new_manifest(run_id: str, question: str, plan: list[dict[str, Any]]) -> dict[str, Any]:
    if not run_id.strip() or not question.strip():
        raise ValueError("run_id and question are required")
    return {
        "schema_version": 1,
        "run_id": run_id,
        "question": question,
        "plan": plan,
        "inputs": [],
        "code": [],
        "executions": [],
        "environment": {},
        "artifacts": [],
        "claims": [],
        "review": {"status": "pending", "findings": []},
    }


def _validate_relative_path(value: str) -> None:
    path = PurePosixPath(value)
    if path.is_absolute() or not value or ".." in path.parts:
        raise ValueError(f"Artifact path must stay inside the run bundle: {value}")


def _valid_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdefABCDEF" for character in value)


def add_artifact(
    manifest: dict[str, Any],
    path: str,
    *,
    kind: str,
    sha256: str,
    artifact_type: str = "file",
    size_bytes: int | None = None,
    entry_count: int | None = None,
    media_type: str | None = None,
    descriptor_path: str | None = None,
) -> None:
    _validate_relative_path(path)
    if not _valid_sha256(sha256):
        raise ValueError("sha256 must be a 64-character hexadecimal digest")
    if not kind.strip():
        raise ValueError("artifact kind is required")
    if artifact_type not in LOCAL_ARTIFACT_TYPES:
        raise ValueError(f"unsupported local artifact_type: {artifact_type}")
    record: dict[str, Any] = {
        "path": path,
        "kind": kind,
        "sha256": sha256.lower(),
    }
    if artifact_type != "file":
        record["artifact_type"] = artifact_type
    if size_bytes is not None:
        if size_bytes < 0:
            raise ValueError("size_bytes must be non-negative")
        record["size_bytes"] = size_bytes
    if entry_count is not None:
        if entry_count < 0:
            raise ValueError("entry_count must be non-negative")
        record["entry_count"] = entry_count
    if media_type is not None:
        record["media_type"] = media_type
    if descriptor_path is not None:
        _validate_relative_path(descriptor_path)
        record["descriptor_path"] = descriptor_path
    manifest["artifacts"].append(record)


def validate_manifest(manifest: dict[str, Any]) -> None:
    if not isinstance(manifest, dict):
        raise ValueError("Artifact manifest must be a JSON object")
    missing = sorted(REQUIRED_FIELDS - manifest.keys())
    if missing:
        raise ValueError(f"Missing manifest fields: {', '.join(missing)}")
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported artifact schema version")
    if not str(manifest.get("run_id", "")).strip() or not str(manifest.get("question", "")).strip():
        raise ValueError("run_id and question are required")
    for field in ("plan", "inputs", "code", "executions", "artifacts", "claims"):
        if not isinstance(manifest.get(field), list):
            raise ValueError(f"Manifest field must be a list: {field}")
    if not isinstance(manifest.get("environment"), dict):
        raise ValueError("Manifest environment must be an object")
    if not isinstance(manifest.get("review"), dict):
        raise ValueError("Manifest review must be an object")
    artifact_paths: set[str] = set()
    for artifact in manifest.get("artifacts", []):
        if not isinstance(artifact, dict):
            raise ValueError("Artifact records must be objects")
        path = str(artifact.get("path", ""))
        _validate_relative_path(path)
        if path in artifact_paths:
            raise ValueError(f"Duplicate artifact path: {path}")
        artifact_paths.add(path)
        if not str(artifact.get("kind", "")).strip():
            raise ValueError(f"Artifact kind is required: {path}")
        if not _valid_sha256(str(artifact.get("sha256", ""))):
            raise ValueError("Invalid artifact sha256")
        artifact_type = str(artifact.get("artifact_type", "file"))
        if artifact_type not in LOCAL_ARTIFACT_TYPES:
            raise ValueError(f"Unsupported local artifact_type: {artifact_type}")
        for field in ("size_bytes", "entry_count"):
            if field in artifact and (isinstance(artifact[field], bool) or int(artifact[field]) < 0):
                raise ValueError(f"Artifact {field} must be a non-negative integer: {path}")
        if "descriptor_path" in artifact:
            _validate_relative_path(str(artifact["descriptor_path"]))
    claim_ids: set[str] = set()
    for claim in manifest.get("claims", []):
        if not isinstance(claim, dict):
            raise ValueError("Claim records must be objects")
        claim_id = str(claim.get("id", "")).strip()
        if not claim_id:
            raise ValueError("Claim id is required")
        if claim_id in claim_ids:
            raise ValueError(f"Duplicate manifest claim id: {claim_id}")
        claim_ids.add(claim_id)


def _validate_descriptor_path(record: dict[str, Any], run_dir: Path, target: Path) -> None:
    descriptor_relative = record.get("descriptor_path")
    if descriptor_relative is None:
        return
    descriptor_path = run_dir / str(descriptor_relative)
    if not descriptor_path.is_file():
        raise ValueError(f"Artifact descriptor is missing: {descriptor_relative}")
    payload = json.loads(descriptor_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Artifact descriptor must be an object: {descriptor_relative}")
    descriptor = validate_descriptor(payload, target)
    if descriptor.root_sha256 != str(record["sha256"]).lower():
        raise ValueError(f"Artifact descriptor root mismatch: {record['path']}")


def verify_bundle_artifacts(manifest: dict[str, Any], run_dir: Path) -> dict[str, Path]:
    validate_manifest(manifest)
    resolved_run = run_dir.resolve()
    verified: dict[str, Path] = {}
    for record in manifest["artifacts"]:
        relative = str(record["path"])
        path = run_dir / relative
        artifact_type = str(record.get("artifact_type", "file"))
        if artifact_type == "directory-tree":
            if not path.is_dir():
                raise ValueError(f"Artifact directory is missing: {relative}")
        elif not path.is_file():
            raise ValueError(f"Artifact file is missing: {relative}")
        resolved = path.resolve()
        if not resolved.is_relative_to(resolved_run):
            raise ValueError(f"Artifact resolves outside the run bundle: {relative}")
        if artifact_type == "directory-tree":
            descriptor = describe_directory(path, media_type=record.get("media_type"))
            digest = descriptor.root_sha256
            size_bytes = descriptor.total_bytes
            entry_count = descriptor.entry_count
        else:
            digest, size_bytes = stream_sha256(path)
            entry_count = 1
        if digest != str(record["sha256"]).lower():
            raise ValueError(f"Artifact digest mismatch: {relative}")
        if "size_bytes" in record and int(record["size_bytes"]) != size_bytes:
            raise ValueError(f"Artifact size mismatch: {relative}")
        if "entry_count" in record and int(record["entry_count"]) != entry_count:
            raise ValueError(f"Artifact entry count mismatch: {relative}")
        _validate_descriptor_path(record, run_dir, path)
        verified[relative] = path
    return verified


def validate_bundle(manifest: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    verified = verify_bundle_artifacts(manifest, run_dir)
    from codex_science.evidence import validate_sidecars
    base = validate_sidecars(manifest, run_dir, verified)
    from codex_science.advanced_sidecars import review_advanced_sidecars, validate_advanced_sidecars
    advanced = validate_advanced_sidecars(manifest, run_dir, verified, base_sidecars=base)
    advanced["advanced_findings"] = review_advanced_sidecars(advanced)
    base.update(advanced)
    return base


def write_manifest(manifest: dict[str, Any], path: Path) -> None:
    validate_manifest(manifest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
