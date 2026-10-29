"""Small valid bundles for checkpoint completion tests."""

import hashlib
from pathlib import Path

from codex_science.artifacts import new_manifest, write_manifest
from codex_science.checkpoints import load_checkpoint


def write_completion_manifest(run_dir: Path, evidence_ref: str) -> Path:
    checkpoint = load_checkpoint(run_dir)
    manifest = new_manifest(run_dir.name, checkpoint["goal"], checkpoint["steps"])
    manifest["artifacts"] = [{
        "path": evidence_ref,
        "kind": "report",
        "sha256": hashlib.sha256((run_dir / evidence_ref).read_bytes()).hexdigest(),
    }]
    path = run_dir / "manifest.json"
    write_manifest(manifest, path)
    return path
