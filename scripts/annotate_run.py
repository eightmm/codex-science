#!/usr/bin/env python3
"""Add, resolve, and list hash-aware annotations in an artifact run bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.artifacts import validate_bundle, validate_manifest  # noqa: E402
from codex_science.collaboration import (  # noqa: E402
    annotation_resolution_lock,
    append_resolution_event,
    fold_annotation_resolutions,
    load_resolution_events,
    validate_annotation,
)


def _atomic_write(target: Path, data: bytes) -> None:
    if target.is_symlink():
        raise ValueError(f"refusing symlink target: {target}")
    if target.parent.is_symlink():
        raise ValueError(f"refusing symlink directory: {target.parent}")
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else 0o644
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), mode)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _load(run_dir: Path) -> tuple[Path, dict, dict]:
    root = run_dir.resolve(strict=True)
    manifest_path = root / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("manifest.json must be a regular file")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sidecars = validate_bundle(manifest, root)
    return root, manifest, sidecars


def _dump(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _validate_add_artifact(args: argparse.Namespace, root: Path, manifest: dict, sidecars: dict) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.id):
        raise ValueError("annotation ID may contain only letters, digits, underscores, and hyphens")
    artifact = root / args.artifact
    if artifact.is_symlink() or not artifact.is_file() or not artifact.resolve().is_relative_to(root):
        raise ValueError("anchor artifact must be a regular run-local file")
    if args.artifact not in {str(item["path"]) for item in manifest["artifacts"]}:
        raise ValueError("anchor artifact must be a regular file inside the run bundle and registered in the manifest")
    artifact_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
    if artifact_hash != sidecars["artifact_hashes"].get(args.artifact):
        raise ValueError("anchor artifact changed after manifest verification")
    return artifact_hash


def _new_annotation(args: argparse.Namespace, artifact_hash: str) -> dict:
    record = {
        "schema_version": 1, "annotation_id": args.id, "author": args.author,
        "type": args.type, "text": args.text, "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "anchor": {"artifact_path": args.artifact, "artifact_sha256": artifact_hash},
    }
    key = "json_pointer" if args.json_pointer is not None else "claim_id" if args.claim_id is not None else "line_range"
    record["anchor"][key] = getattr(args, key)
    validate_annotation(record)
    return record


def _add_annotation(args: argparse.Namespace, registration: dict[str, str]) -> list[dict]:
    # Reject invalid inputs without creating the annotations directory or lock.
    root, manifest, sidecars = _load(args.run_dir)
    preflight_hash = _validate_add_artifact(args, root, manifest, sidecars)
    _new_annotation(args, preflight_hash)
    annotations = list(sidecars.get("annotations", []))
    events = load_resolution_events(root)
    fold_annotation_resolutions(annotations, events, sidecars["artifact_hashes"])

    with annotation_resolution_lock(root) as root:
        root, manifest, sidecars = _load(root)
        artifact_hash = _validate_add_artifact(args, root, manifest, sidecars)
        annotations = list(sidecars.get("annotations", []))
        events = load_resolution_events(root, lock_held=True)
        fold_annotation_resolutions(annotations, events, sidecars["artifact_hashes"])
        existing_paths = {str(item["path"]) for item in manifest["artifacts"]}
        annotation_id_exists = any(item["annotation_id"] == args.id for item in annotations)

        relative = f"annotations/{args.id}.json"
        target = root / relative
        record = _new_annotation(args, artifact_hash)
        if relative in existing_paths:
            raise ValueError(f"annotation sidecar path is already registered: {relative}")
        target_exists = target.exists() or target.is_symlink()
        if annotation_id_exists and not target_exists:
            raise ValueError(f"annotation ID already exists: {args.id}")
        if target.parent.is_symlink():
            raise ValueError(f"annotation sidecar directory must not be a symlink: {target.parent}")
        if target.is_symlink():
            recovery = (
                f"remove it because annotation ID {args.id} is already registered"
                if annotation_id_exists else "remove it; symlinked sidecars cannot be registered"
            )
            raise ValueError(f"unregistered annotation sidecar exists: {relative}; {recovery}")
        if target.exists():
            if annotation_id_exists:
                raise ValueError(
                    f"unregistered annotation sidecar exists: {relative}; remove it because annotation ID {args.id} is already registered"
                )
            if not target.is_file():
                raise ValueError(
                    f"unregistered annotation sidecar exists: {relative}; remove it or re-run add with identical content to register it"
                )
            try:
                existing_record = json.loads(target.read_text(encoding="utf-8"))
                if not isinstance(existing_record, dict):
                    raise ValueError("annotation sidecar must be an object")
                validate_annotation(existing_record)
            except (OSError, ValueError, json.JSONDecodeError) as error:
                raise ValueError(
                    f"unregistered annotation sidecar exists: {relative}; remove it or re-run add with identical content to register it"
                ) from error
            expected_content = {key: value for key, value in record.items() if key != "created_at"}
            existing_content = {key: value for key, value in existing_record.items() if key != "created_at"}
            if existing_content != expected_content:
                raise ValueError(
                    f"unregistered annotation sidecar exists: {relative}; remove it or re-run add with identical content to register it"
                )
            sidecar_bytes = target.read_bytes()
            registered_record = existing_record
        else:
            sidecar_bytes = _dump(record)
            registered_record = record

        updated_manifest = dict(manifest)
        updated_manifest["artifacts"] = [*manifest["artifacts"], {
            "path": relative, "kind": "annotation",
            "sha256": hashlib.sha256(sidecar_bytes).hexdigest(),
        }]
        validate_manifest(updated_manifest)
        effective = fold_annotation_resolutions(
            [*annotations, registered_record], events, sidecars["artifact_hashes"]
        )

        if not target_exists:
            _atomic_write(target, sidecar_bytes)
        _atomic_write(root / "manifest.json", _dump(updated_manifest))
        registration["path"] = relative
        return effective


def main() -> int:
    manifest_notice = (
        "add changes manifest.json bytes; a ProjectStore that already imported this run will refuse it "
        "('imported run manifest changed on disk'). Annotate runs before importing them."
    )
    parser = argparse.ArgumentParser(description="Manage hash-aware human annotations for an artifact run bundle.",
        epilog=manifest_notice)
    parser.add_argument("run_dir", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add", description=manifest_notice, help=manifest_notice,
        epilog=manifest_notice)
    add.add_argument("--id", required=True)
    add.add_argument("--author", required=True)
    add.add_argument("--type", choices=("question", "finding", "decision", "note", "correction"), default="note")
    add.add_argument("--text", required=True)
    add.add_argument("--artifact", required=True, help="run-relative artifact path")
    anchor = add.add_mutually_exclusive_group(required=True)
    anchor.add_argument("--json-pointer")
    anchor.add_argument("--claim-id")
    anchor.add_argument("--line-range")
    resolve = commands.add_parser("resolve")
    resolve.add_argument("--id", required=True)
    resolve.add_argument("--status", choices=("resolved", "dismissed"), required=True)
    resolve.add_argument("--resolver", required=True)
    resolve.add_argument("--note")
    commands.add_parser("list")
    args = parser.parse_args()
    registration: dict[str, str] = {}
    try:
        if args.command == "add":
            effective = _add_annotation(args, registration)
            print(f"warning: {manifest_notice}", file=sys.stderr)
        else:
            root, manifest, sidecars = _load(args.run_dir)
            annotations = list(sidecars.get("annotations", []))
        if args.command == "resolve":
            annotation = next((item for item in annotations if item["annotation_id"] == args.id), None)
            if annotation is None:
                raise ValueError(f"unknown annotation ID: {args.id}")
            with annotation_resolution_lock(root):
                events = load_resolution_events(root, lock_held=True)
                anchor_path = root / annotation["anchor"]["artifact_path"]
                if (anchor_path.is_symlink() or not anchor_path.is_file()
                        or not anchor_path.resolve().is_relative_to(root)):
                    raise ValueError("annotation anchor artifact must be a regular file inside the run bundle")
                observed = hashlib.sha256(anchor_path.read_bytes()).hexdigest()
                if observed != sidecars["artifact_hashes"].get(annotation["anchor"]["artifact_path"]):
                    raise ValueError("anchor artifact changed after manifest verification; resolution was not recorded")
                if observed != annotation["anchor"]["artifact_sha256"]:
                    raise ValueError("artifact hash differs from annotation anchor; resolution was not recorded")
                event = {"schema_version": 1, "annotation_id": args.id, "status": args.status,
                         "resolver": args.resolver, "resolved_at": datetime.now(timezone.utc).isoformat(),
                         "artifact_sha256": observed, "event_id": str(uuid4())}
                if args.note is not None:
                    event["note"] = args.note
                effective = fold_annotation_resolutions(annotations, [*events, event], sidecars["artifact_hashes"])
                append_resolution_event(root, event, lock_held=True)
        if args.command == "list":
            events = load_resolution_events(root)
            effective = fold_annotation_resolutions(annotations, events, sidecars["artifact_hashes"])
        print(json.dumps(effective, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        registered = registration.get("path")
        suffix = f"; annotation was registered at {registered} (manifest.json was updated)" if registered else ""
        print(f"annotate_run: {error}{suffix}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
