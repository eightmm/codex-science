"""Structured, reproducible analysis artifact manifests and bundle validation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

REQUIRED_FIELDS = {"schema_version", "run_id", "question", "plan", "inputs", "code", "executions", "environment", "artifacts", "claims", "review"}


def new_manifest(run_id: str, question: str, plan: list[dict[str, Any]]) -> dict[str, Any]:
    if not run_id.strip() or not question.strip():
        raise ValueError("run_id and question are required")
    return {"schema_version": 1, "run_id": run_id, "question": question, "plan": plan, "inputs": [], "code": [], "executions": [], "environment": {}, "artifacts": [], "claims": [], "review": {"status": "pending", "findings": []}}


def _validate_relative_path(value: str) -> None:
    path = PurePosixPath(value)
    if path.is_absolute() or not value or ".." in path.parts:
        raise ValueError(f"Artifact path must stay inside the run bundle: {value}")


def _valid_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdefABCDEF" for character in value)


def add_artifact(manifest: dict[str, Any], path: str, *, kind: str, sha256: str) -> None:
    _validate_relative_path(path)
    if not _valid_sha256(sha256):
        raise ValueError("sha256 must be a 64-character hexadecimal digest")
    if not kind.strip():
        raise ValueError("artifact kind is required")
    manifest["artifacts"].append({"path": path, "kind": kind, "sha256": sha256.lower()})


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


def verify_bundle_artifacts(manifest: dict[str, Any], run_dir: Path) -> dict[str, Path]:
    validate_manifest(manifest)
    resolved_run = run_dir.resolve()
    verified: dict[str, Path] = {}
    for record in manifest["artifacts"]:
        relative = str(record["path"])
        path = run_dir / relative
        if not path.is_file():
            raise ValueError(f"Artifact file is missing: {relative}")
        resolved = path.resolve()
        if not resolved.is_relative_to(resolved_run):
            raise ValueError(f"Artifact resolves outside the run bundle: {relative}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != str(record["sha256"]).lower():
            raise ValueError(f"Artifact digest mismatch: {relative}")
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
