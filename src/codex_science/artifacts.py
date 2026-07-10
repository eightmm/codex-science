"""Structured, reproducible analysis artifact manifests."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any


REQUIRED_FIELDS = {
    "schema_version",
    "run_id",
    "question",
    "plan",
    "inputs",
    "code",
    "executions",
    "environment",
    "artifacts",
    "claims",
    "review",
}


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


def add_artifact(
    manifest: dict[str, Any],
    path: str,
    *,
    kind: str,
    sha256: str,
) -> None:
    _validate_relative_path(path)
    if len(sha256) != 64 or any(character not in "0123456789abcdefABCDEF" for character in sha256):
        raise ValueError("sha256 must be a 64-character hexadecimal digest")
    manifest["artifacts"].append({"path": path, "kind": kind, "sha256": sha256.lower()})


def validate_manifest(manifest: dict[str, Any]) -> None:
    missing = sorted(REQUIRED_FIELDS - manifest.keys())
    if missing:
        raise ValueError(f"Missing manifest fields: {', '.join(missing)}")
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported artifact schema version")
    if not str(manifest.get("run_id", "")).strip() or not str(manifest.get("question", "")).strip():
        raise ValueError("run_id and question are required")
    for artifact in manifest.get("artifacts", []):
        _validate_relative_path(str(artifact.get("path", "")))
        digest = str(artifact.get("sha256", ""))
        if len(digest) != 64 or any(character not in "0123456789abcdefABCDEF" for character in digest):
            raise ValueError("Invalid artifact sha256")


def write_manifest(manifest: dict[str, Any], path: Path) -> None:
    validate_manifest(manifest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
