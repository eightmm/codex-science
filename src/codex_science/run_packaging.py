"""Record executions and refresh run bundle hashes."""
from __future__ import annotations

import contextlib
import copy
import fcntl
import fnmatch
import hashlib
import io
import json
import os
import shlex
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from codex_science.artifacts import validate_bundle, validate_manifest, write_manifest
from codex_science.artifact_store import describe_directory
from codex_science.review_receipts import review_receipt_findings, validate_review_receipt
from codex_science.review import review_manifest
from codex_science.runtime_identity import record_runtime_identity

DEFAULT_KINDS = {
    "protocol.json": "protocol", "queries.jsonl": "query-ledger",
    "studies.json": "study-table", "claims.json": "claim-register",
    "evidence_graph.json": "evidence-graph", "reference-use-ledger.json": "reference-use-ledger",
    "report.md": "report", "snapshot.previous.json": "literature-snapshot-previous",
    "snapshot.current.json": "literature-snapshot", "snapshot.diff.json": "literature-snapshot-diff",
    "screening.json": "screening-table", "normalized-inputs.json": "entity-mapping",
    "saturation.json": "saturation-estimate",
}
EXCLUDED_NAMES = {"manifest.json", "checkpoint.json", "deterministic-review.json", "index.md", "index.html", "workbench.html", "execution-log.jsonl", "review.json", "review-packet.json", "review-response.json", "review-checklist.md"}
REVIEW_KINDS = {"review-receipt", "review-receipt-v2", "review-packet", "review-packet-v1", "review-response", "review-response-v1"}


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_sha(path: Path, item: dict[str, Any]) -> str:
    if item.get("artifact_type") == "directory-tree":
        return describe_directory(path, media_type=item.get("media_type")).root_sha256
    return _sha(path)


def _canonical_relative(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Artifact path must stay inside the run bundle: {value}")
    return path.as_posix()


def _inside(root: Path, relative: str) -> Path:
    canonical = _canonical_relative(relative)
    candidate = root / canonical
    resolved_root, resolved = root.resolve(), candidate.resolve()
    if not resolved.is_relative_to(resolved_root):
        raise ValueError(f"Path escapes run directory: {relative}")
    return candidate


def _write_target(root: Path, relative: str) -> Path:
    target = root / relative
    if target.is_symlink():
        raise ValueError(f"Write target is a symlink: {relative}; no files were changed")
    return _inside(root, relative)


def _safe_directory(root: Path, relative: str) -> Path:
    path = _write_target(root, relative)
    if path.exists() and not path.is_dir():
        raise ValueError(f"Write directory is not a directory: {relative}; no files were changed")
    return path


def _stage_file(target: Path, content: bytes) -> Path:
    fd, name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    staged = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if target.exists():
            os.chmod(staged, target.stat().st_mode & 0o7777)
        return staged
    except BaseException:
        staged.unlink(missing_ok=True)
        raise


def _atomic_write(root: Path, relative: str, content: bytes) -> None:
    target = _write_target(root, relative)
    staged = _stage_file(target, content)
    try:
        os.replace(staged, target)
    finally:
        staged.unlink(missing_ok=True)


def _write_manifest_atomic(root: Path, manifest: dict[str, Any]) -> None:
    target = _write_target(root, "manifest.json")
    staged = _stage_file(target, b"")
    try:
        write_manifest(manifest, staged)
        os.replace(staged, target)
    finally:
        staged.unlink(missing_ok=True)


def _atomic_commit(
    root: Path,
    staged_payloads: list[tuple[str, bytes]],
    manifest: dict[str, Any],
    archive_moves: list[tuple[str, str]] | None = None,
) -> None:
    """Stage replacements, archive review files, then replace the manifest last."""
    archive_moves = archive_moves or []
    target_paths = [(_write_target(root, relative), relative, payload) for relative, payload in staged_payloads]
    manifest_target = _write_target(root, "manifest.json")
    planned_moves: list[tuple[Path, Path]] = []
    for source_relative, destination_relative in archive_moves:
        source = _inside(root, source_relative)
        destination = _inside(root, destination_relative)
        if not source.is_file():
            raise ValueError(f"Review file is missing: {source_relative}; no files were changed")
        if destination.exists() or destination.is_symlink():
            raise ValueError(f"Review archive destination already exists: {destination_relative}; no files were changed")
        planned_moves.append((source, destination))
    validate_manifest(manifest)
    manifest_temp = _stage_file(manifest_target, b"")
    staged: list[tuple[Path, Path, bytes]] = []
    committed: list[tuple[Path, bytes]] = []
    moved: list[tuple[Path, Path]] = []
    created_dirs: list[Path] = []
    try:
        write_manifest(manifest, manifest_temp)
        for target, _relative, payload in target_paths:
            staged.append((target, _stage_file(target, payload), target.read_bytes()))
        for _source, destination in planned_moves:
            missing = []
            parent = destination.parent
            while not parent.exists():
                missing.append(parent)
                parent = parent.parent
            for directory in reversed(missing):
                directory.mkdir()
                created_dirs.append(directory)
        for source, destination in planned_moves:
            os.replace(source, destination)
            moved.append((source, destination))
        for target, temporary, original in staged:
            os.replace(temporary, target)
            committed.append((target, original))
        os.replace(manifest_temp, manifest_target)
    except BaseException:
        for target, original in reversed(committed):
            rollback = _stage_file(target, original)
            os.replace(rollback, target)
        for source, destination in reversed(moved):
            os.replace(destination, source)
        raise
    finally:
        manifest_temp.unlink(missing_ok=True)
        for _target, temporary, _original in staged:
            temporary.unlink(missing_ok=True)
        for directory in reversed(created_dirs):
            try:
                directory.rmdir()
            except OSError:
                pass


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _execution_is_later(
    candidate: dict[str, Any], candidate_index: int,
    failure: dict[str, Any], failure_index: int,
) -> bool:
    return candidate_index > failure_index


def run_exec(run_dir: Path, command: list[str], identifier: str | None = None) -> int:
    if not command:
        raise ValueError("command is required after --")
    run_dir.mkdir(parents=True, exist_ok=True)
    run_dir = run_dir.resolve()
    log_file = run_dir / "execution-log.jsonl"
    _write_target(run_dir, "execution-log.jsonl")
    logs_dir = _safe_directory(run_dir, "logs")
    records = [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines() if line.strip()] if log_file.exists() else []
    used = {str(item["id"]) for item in records if isinstance(item, dict) and item.get("id") is not None}
    manifest_path = run_dir / "manifest.json"
    if manifest_path.is_file():
        try:
            existing_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing_manifest = None
        if isinstance(existing_manifest, dict) and isinstance(existing_manifest.get("executions"), list):
            used.update(
                str(item["id"])
                for item in existing_manifest["executions"]
                if isinstance(item, dict) and item.get("id") is not None
            )
    logs_dir.mkdir(parents=True, exist_ok=True)
    if identifier is not None and identifier in used:
        raise ValueError(f"Duplicate execution id: {identifier}; execution IDs are unique per run, so pass a new --id or omit it")
    number = 1
    while True:
        selected = identifier if identifier is not None else f"exec-{number:03d}"
        if identifier is None and selected in used:
            number += 1
            continue
        log_relative = f"logs/{selected}.log"
        log_path = _write_target(run_dir, log_relative)
        try:
            output_fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
            break
        except FileExistsError:
            if identifier is not None:
                raise ValueError(f"Duplicate execution id: {identifier}; execution IDs are unique per run, so pass a new --id or omit it")
            number += 1
    identifier = selected
    started = _utc()
    with os.fdopen(output_fd, "wb") as output:
        result = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT, check=False)
    ended = _utc()
    record = {"id": identifier, "command": shlex.join(command), "started_at": started, "ended_at": ended,
              "exit_code": result.returncode, "log_path": log_relative, "log_sha256": _sha(log_path)}
    journal_fd = os.open(log_file, os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0), 0o666)
    with os.fdopen(journal_fd, "a", encoding="utf-8") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        payload = (json.dumps(record, sort_keys=True) + "\n").encode("utf-8")
        os.write(stream.fileno(), payload)
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines[-40:]:
        print(line)
    return result.returncode


def _kind(path: str, overrides: list[tuple[str, str]], default_kind: str | None = None) -> str | None:
    canonical = _canonical_relative(path)
    for pattern, kind in reversed(overrides):
        if _canonical_relative(pattern) == canonical:
            return kind
    for pattern, kind in reversed(overrides):
        if fnmatch.fnmatchcase(canonical, _canonical_relative(pattern)):
            return kind
    name = PurePosixPath(canonical).name
    if canonical.startswith("lanes/") and canonical.endswith(".json"):
        return "lane-receipt"
    if canonical.startswith("bias/"):
        return "risk-of-bias"
    if canonical.startswith(("raw/", "sources/")):
        return "source-snapshot"
    if canonical.endswith(".py") and "/" not in canonical:
        return "code"
    if name in DEFAULT_KINDS:
        return DEFAULT_KINDS[name]
    return default_kind


def _is_deterministic_review_file(path: Path) -> bool:
    name = path.name.lower()
    return name.startswith("deterministic-review") and path.suffix.lower() == ".json"


def _is_review_flow_file(path: Path) -> bool:
    name = path.name.lower()
    if name in {"review-task.json", "reviewer-response.json", "reviewer-notes.md"}:
        return True
    if any(tag in name for tag in ("review-receipt", "review-packet", "review-response")):
        return True
    if path.suffix.lower() != ".json":
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return isinstance(payload, dict) and (
        ("response_contract" in payload and "fingerprint" in payload and "independent_required" in payload)
        or ("review_task_id" in payload and "packet_fingerprint" in payload and "reviewed_artifacts" in payload)
        or ("review_task_id" in payload and "source_manifest_sha256" in payload)
        or ("review_id" in payload and "covered_artifacts" in payload and "fingerprint" in payload)
    )


def _review_flow_files(run_dir: Path) -> list[Path]:
    return [
        path for path in run_dir.rglob("*")
        if path.is_file()
        and "review-rounds" not in path.relative_to(run_dir).parts
        and _is_review_flow_file(path)
    ]


def _plan_review_archive(
    run_dir: Path,
    files: list[Path],
    additional_paths: list[str] | None = None,
    review_artifacts: list[dict[str, Any]] | None = None,
) -> tuple[str | None, list[tuple[str, str]], set[str]]:
    sources: dict[str, Path] = {}
    for source in files:
        relative = source.relative_to(run_dir).as_posix()
        sources.setdefault(_canonical_relative(relative), source)
    for relative in additional_paths or []:
        canonical = _canonical_relative(relative)
        sources.setdefault(canonical, run_dir / canonical)
    if not sources:
        return None, [], set()
    archive_root = run_dir / "review-rounds"
    _inside(run_dir, "review-rounds")
    expected_hashes = {
        _canonical_relative(str(item.get("path", ""))): item.get("sha256")
        for item in review_artifacts or []
        if item.get("path")
    }
    recovered_sources: set[str] = set()
    recovered_rounds: list[int] = []
    number = 1
    while (archive_root / str(number)).exists() or (archive_root / str(number)).is_symlink():
        number += 1
    archive_relative = f"review-rounds/{number}"
    moves = []
    for source_relative in sorted(sources):
        source = _inside(run_dir, source_relative)
        destination_relative = f"{archive_relative}/{source_relative}"
        if not source.is_file():
            expected_hash = expected_hashes.get(source_relative)
            recovered_round = None
            if expected_hash is not None and archive_root.is_dir() and not archive_root.is_symlink():
                round_dirs = sorted(
                    (path for path in archive_root.iterdir() if path.name.isdigit()),
                    key=lambda path: int(path.name), reverse=True,
                )
                for round_dir in round_dirs:
                    if round_dir.is_symlink() or not round_dir.is_dir() or not round_dir.name.isdigit():
                        continue
                    archived = _inside(run_dir, f"review-rounds/{round_dir.name}/{source_relative}")
                    if archived.is_symlink() or not archived.is_file():
                        continue
                    if _sha(archived) == expected_hash:
                        recovered_round = int(round_dir.name)
                        break
            if recovered_round is None:
                raise ValueError(
                    f"Review file is missing: {source_relative}; no archived copy matched; no files were changed"
                )
            recovered_rounds.append(recovered_round)
            recovered_sources.add(source_relative)
            continue
        destination = _inside(run_dir, destination_relative)
        if destination.exists() or destination.is_symlink():
            raise ValueError(f"Review archive destination already exists: {destination_relative}; no files were changed")
        moves.append((source_relative, destination_relative))
    if not moves:
        archive_relative = f"review-rounds/{max(recovered_rounds)}" if recovered_rounds else None
    return archive_relative, moves, recovered_sources


def _missing_receipt_message(run_dir: Path, relative: str) -> str:
    message = f"Review receipt is missing: {relative} (the path is relative to the run directory)"
    try:
        candidate = Path(os.path.abspath(relative))
        root = Path(os.path.abspath(run_dir))
        if candidate.is_relative_to(root) and candidate != root:
            parts = candidate.relative_to(root).parts
            chain = [root.joinpath(*parts[:i + 1]) for i in range(len(parts))]
            if candidate.is_file() and not any(item.is_symlink() for item in chain):
                message += f"; that file exists inside the run directory, pass {'/'.join(parts)}"
    except (OSError, ValueError):
        pass
    return message


def register_receipt(run_dir: Path, relative: str) -> dict[str, Any]:
    canonical_receipt = _canonical_relative(relative)
    manifest_path = _write_target(run_dir, "manifest.json")
    if not manifest_path.is_file():
        raise ValueError(f"Run manifest is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not isinstance(manifest.get("artifacts"), list):
        raise ValueError("Manifest and artifacts list are required")
    receipt_path = _inside(run_dir, canonical_receipt)
    if not receipt_path.is_file():
        raise ValueError(_missing_receipt_message(run_dir, relative))
    review = manifest.get("review", {})
    existing_receipts = [item for item in manifest["artifacts"] if isinstance(item, dict) and item.get("kind") in {"review-receipt", "review-receipt-v2"}]
    review_files = _review_flow_files(run_dir)
    if not existing_receipts and not review_files and not (isinstance(review, dict) and review.get("status", "pending") != "pending"):
        raise ValueError("--register-receipt requires existing review evidence")
    planned, summary = plan_receipt_registration(run_dir, manifest, relative)
    if "already_registered" not in summary:
        _write_manifest_atomic(run_dir, planned)
    return summary


def plan_receipt_registration(run_dir: Path, manifest: dict[str, Any], relative: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate a receipt against the manifest and return the updated manifest without writing.

    Raises ValueError on any refusal; the input manifest is never mutated.
    """
    manifest = copy.deepcopy(manifest)
    canonical_receipt = _canonical_relative(relative)
    if not isinstance(manifest.get("artifacts"), list):
        raise ValueError("Manifest and artifacts list are required")
    if not all(isinstance(item, dict) for item in manifest["artifacts"]):
        raise ValueError("Artifact records must be objects")
    receipt_path = _inside(run_dir, canonical_receipt)
    if not receipt_path.is_file():
        raise ValueError(_missing_receipt_message(run_dir, relative))
    review = manifest.get("review", {})
    mismatches = []
    for item in manifest["artifacts"]:
        rel = str(item.get("path", ""))
        target = _inside(run_dir, rel)
        if not target.exists() or _artifact_sha(target, item) != item.get("sha256"):
            mismatches.append(rel)
    for lane in sorted((run_dir / "lanes").glob("*.json")) if (run_dir / "lanes").exists() else []:
        payload = json.loads(lane.read_text(encoding="utf-8"))
        hashes = payload.get("output_sha256") if isinstance(payload, dict) else None
        if not isinstance(hashes, dict):
            continue
        for rel, expected in hashes.items():
            target = _inside(run_dir, _canonical_relative(str(rel)))
            if not target.is_file() or _sha(target) != expected:
                mismatches.append(str(rel))
    if mismatches:
        changed_paths = sorted({_canonical_relative(path) for path in mismatches})
        raise ValueError("Cannot register receipt; changed paths: " + ", ".join(changed_paths))
    existing_entry = next(
        (
            item for item in manifest["artifacts"]
            if isinstance(item, dict) and item.get("path") and _canonical_relative(str(item["path"])) == canonical_receipt
        ),
        None,
    )
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Review receipt must be a JSON object")
    if not payload.get("review_id"):
        raise ValueError("Legacy review receipts without review_id are not registered; register the receipt produced by the science-review flow")
    validate_review_receipt(payload)
    registry_digest = None
    registry_path = Path(__file__).resolve().parents[2] / "models" / "registry-v2.json"
    if registry_path.is_file():
        from codex_science.model_registry_v2 import load_registry_v2, registry_sha256

        registry_digest = registry_sha256(load_registry_v2(registry_path))
    current_hashes = {
        str(item["path"]): str(item["sha256"]).lower()
        for item in manifest["artifacts"]
        if isinstance(item, dict) and item.get("path") and item.get("sha256")
    }
    receipt_findings = review_receipt_findings(
        payload, current_hashes, registry_sha256=registry_digest
    )
    if receipt_findings:
        codes = ", ".join(sorted({item["code"] for item in receipt_findings}))
        raise ValueError(f"Cannot register receipt; validation findings: {codes}")
    kind = "review-receipt-v2" if "review_task_id" in payload and "packet_fingerprint" in payload else "review-receipt"
    new_review = {
        **(review if isinstance(review, dict) else {}),
        "status": payload["status"],
        "receipt": canonical_receipt,
        "findings": payload.get("findings", []),
    }
    fresh_entry = {"path": canonical_receipt, "kind": kind, "sha256": _sha(receipt_path)}
    if existing_entry is not None and "size_bytes" in existing_entry:
        fresh_entry["size_bytes"] = receipt_path.stat().st_size
    if (
        existing_entry is not None
        and existing_entry == fresh_entry
        and review == new_review
    ):
        return manifest, {"added": [], "already_registered": relative, "kind": kind}
    if existing_entry is None:
        manifest["artifacts"].append(fresh_entry)
    else:
        manifest["artifacts"][manifest["artifacts"].index(existing_entry)] = fresh_entry
    manifest["review"] = new_review
    if existing_entry is not None:
        return manifest, {"added": [], "updated": [relative], "kind": kind}
    return manifest, {"added": [relative], "kind": kind}


def refresh(run_dir: Path, overrides: list[tuple[str, str]], invalidate_review: bool = False, default_kind: str | None = None) -> dict[str, Any]:
    manifest_path = _write_target(run_dir, "manifest.json")
    if not manifest_path.is_file():
        raise ValueError(f"Run manifest is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("Manifest must be a JSON object")
    record_runtime_identity(manifest)
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("Manifest artifacts must be a list")
    review = manifest.get("review", {})
    review_artifacts = [item for item in artifacts if isinstance(item, dict) and item.get("kind") in REVIEW_KINDS]
    review_files = _review_flow_files(run_dir)
    has_review_evidence = bool(
        review_artifacts
        or (isinstance(review, dict) and review.get("status", "pending") != "pending")
        or review_files
    )
    deterministic_files = [
        path for path in run_dir.rglob("*")
        if path.is_file()
        and "review-rounds" not in path.relative_to(run_dir).parts
        and _is_deterministic_review_file(path)
    ]
    review_archive, archive_moves = (None, [])
    archived_sources: set[str] = set()
    if has_review_evidence:
        if not invalidate_review:
            raise ValueError(
                "Run has independent review evidence; any change invalidates the independent review. "
                "Start a new review round with --invalidate-review (which archives prior review files), "
                "or register a passed receipt with --register-receipt."
            )
        review_artifact_paths = [str(item.get("path", "")) for item in review_artifacts]
        review_archive, archive_moves, archived_sources = _plan_review_archive(
            run_dir, [*review_files, *deterministic_files], review_artifact_paths, review_artifacts
        )
        archived_sources.update(_canonical_relative(source) for source, _destination in archive_moves)
        print("warning: invalidating independent review; review files will be archived", file=sys.stderr)
        manifest["review"] = {**(review if isinstance(review, dict) else {}), "status": "pending"}
        manifest["review"].pop("receipt", None)
        manifest["artifacts"] = [
            item for item in artifacts
            if not (
                isinstance(item, dict)
                and (
                    item.get("kind") in REVIEW_KINDS
                    or (item.get("path") and _canonical_relative(str(item["path"])) in archived_sources)
                )
            )
        ]
        artifacts = manifest["artifacts"]

        for item in artifacts:
            if not isinstance(item, dict) or item.get("artifact_type") != "directory-tree" or not item.get("path"):
                continue
            artifact_root = PurePosixPath(_canonical_relative(str(item["path"])))
            affected = [path for pair in archive_moves for path in pair]
            if any(PurePosixPath(_canonical_relative(path)).is_relative_to(artifact_root) for path in affected):
                raise ValueError(
                    f"Cannot archive review files inside directory-tree artifact {artifact_root}; "
                    "exclude the review files from the directory artifact; no files were changed"
                )

    lanes_updated = 0
    lane_updates: list[tuple[str, bytes]] = []
    lanes_dir = run_dir / "lanes"
    if lanes_dir.exists() or lanes_dir.is_symlink():
        _safe_directory(run_dir, "lanes")
    for lane in sorted(lanes_dir.glob("*.json")) if lanes_dir.exists() else []:
        if not lane.is_file():
            continue
        lane_relative = lane.relative_to(run_dir).as_posix()
        _write_target(run_dir, lane_relative)
        payload = json.loads(lane.read_text(encoding="utf-8"))
        hashes = payload.get("output_sha256") if isinstance(payload, dict) else None
        lane_changed = False
        if isinstance(hashes, dict):
            for key in list(hashes):
                canonical_key = _canonical_relative(str(key))
                target = _inside(run_dir, canonical_key)
                if not target.is_file():
                    raise ValueError(f"Lane output is missing: {key}")
                digest = _sha(target)
                if hashes[key] != digest:
                    hashes[key] = digest
                    lane_changed = True
            if lane_changed:
                lane_updates.append((lane_relative, (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")))
                lanes_updated += 1
    planned_lanes = dict(lane_updates)
    for item in artifacts:
        if not isinstance(item, dict) or item.get("artifact_type") != "directory-tree" or not item.get("path"):
            continue
        artifact_root = PurePosixPath(_canonical_relative(str(item["path"])))
        for lane_path in planned_lanes:
            if PurePosixPath(_canonical_relative(lane_path)).is_relative_to(artifact_root):
                raise ValueError(
                    f"Cannot refresh directory-tree artifact {artifact_root} while lane {lane_path} needs rewriting; "
                    "refresh the lane outputs first or exclude the lane from the directory artifact; no files were changed"
                )

    by_path: dict[str, dict[str, Any]] = {}
    changed, unchanged = [], 0
    for item in artifacts:
        if not isinstance(item, dict) or "path" not in item:
            raise ValueError("Manifest artifact records must include path")
        relative = str(item["path"])
        canonical = _canonical_relative(relative)
        target = _inside(run_dir, relative)
        if not target.is_file() and item.get("artifact_type") != "directory-tree":
            raise ValueError(f"Artifact file is missing: {relative}")
        if item.get("artifact_type") == "directory-tree":
            descriptor = describe_directory(target, media_type=item.get("media_type"))
            digest = descriptor.root_sha256
        elif canonical in planned_lanes:
            planned_lane = planned_lanes[canonical]
            digest = hashlib.sha256(planned_lane).hexdigest()
        else:
            digest = _artifact_sha(target, item)
        if item.get("sha256") != digest:
            if item.get("descriptor_path") or item.get("artifact_type") == "chunked-file":
                raise ValueError(f"Artifact descriptor is stale for {relative}; regenerate it with scripts/describe_artifact.py")
            item["sha256"] = digest
            if "size_bytes" in item:
                if item.get("artifact_type") == "directory-tree":
                    item["size_bytes"] = descriptor.total_bytes
                elif canonical in planned_lanes:
                    item["size_bytes"] = len(planned_lanes[canonical])
                else:
                    item["size_bytes"] = target.stat().st_size
            if item.get("artifact_type") == "directory-tree" and "entry_count" in item:
                item["entry_count"] = descriptor.entry_count
            changed.append(relative)
        else:
            unchanged += 1
        by_path[canonical] = item

    excluded = set(EXCLUDED_NAMES)
    unclassified = []
    added = []
    for target in sorted(run_dir.rglob("*")):
        if not target.is_file():
            continue
        relative = target.relative_to(run_dir).as_posix()
        canonical = _canonical_relative(relative)
        _inside(run_dir, canonical)
        if "__pycache__" in PurePosixPath(canonical).parts or target.suffix == ".pyc":
            continue
        if (
            canonical in archived_sources or canonical in by_path or canonical in excluded
            or target.name in excluded or _is_deterministic_review_file(target)
            or canonical.startswith("logs/") or canonical.startswith(".review/")
            or "review-rounds" in PurePosixPath(canonical).parts
            or any(part in {"review", "reviews"} for part in PurePosixPath(canonical).parts)
        ):
            continue
        if _is_review_flow_file(target):
            continue
        kind = _kind(canonical, overrides, default_kind)
        if kind is None:
            unclassified.append(relative)
            continue
        planned_lane = planned_lanes.get(canonical)
        item = {"path": relative, "kind": kind, "sha256": hashlib.sha256(planned_lane).hexdigest() if planned_lane is not None else _sha(target)}
        if canonical.startswith("lanes/"):
            item["size_bytes"] = len(planned_lane) if planned_lane is not None else target.stat().st_size
        artifacts.append(item)
        by_path[canonical] = item
        added.append(relative)
    if unclassified:
        raise ValueError("Unclassified files: " + ", ".join(unclassified) + "; classify each with --kind PATH=KIND or --default-kind KIND")

    manifest["artifacts"] = artifacts
    code_by_path = {_canonical_relative(str(item.get("path"))): item for item in manifest["code"] if isinstance(item, dict) and item.get("path")}
    for path in sorted(run_dir.glob("*.py")):
        relative = path.relative_to(run_dir).as_posix()
        digest = _sha(path)
        canonical = _canonical_relative(relative)
        if canonical in code_by_path:
            code_by_path[canonical]["sha256"] = digest
        else:
            entry = {"path": relative, "sha256": digest}
            manifest["code"].append(entry)
            code_by_path[canonical] = entry
    superseded = manifest.get("superseded_executions", [])
    if not isinstance(superseded, list):
        raise ValueError("Manifest superseded_executions must be a list")
    active_ids = {
        item.get("id") for item in manifest["executions"]
        if isinstance(item, dict) and item.get("id") is not None
    }
    if any(
        isinstance(item, dict) and item.get("id") in active_ids
        for item in superseded
    ):
        raise ValueError("Manifest execution id appears in both executions lists")
    executions_added = 0
    execution_log = run_dir / "execution-log.jsonl"
    if execution_log.exists():
        comparable_fields = ("command", "started_at", "ended_at", "exit_code", "log_path", "log_sha256")
        known: dict[Any, list[dict[str, Any]]] = {}
        for item in [*manifest["executions"], *superseded]:
            if isinstance(item, dict) and item.get("id") is not None:
                known.setdefault(item["id"], []).append(item)
        with execution_log.open(encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                entry = json.loads(line)
                entry_id = entry.get("id")
                if entry_id is not None and entry_id in known:
                    for recorded in known[entry_id]:
                        if any(
                            key in entry and key in recorded and entry[key] != recorded[key]
                            for key in comparable_fields
                        ):
                            raise ValueError(
                                f"Conflicting execution record for id {entry_id}"
                            )
                    continue
                new_entry = {key: entry[key] for key in ("id", "command", "started_at", "ended_at", "exit_code", "log_path", "log_sha256") if key in entry}
                manifest["executions"].append(new_entry)
                if entry_id is not None:
                    known.setdefault(entry_id, []).append(new_entry)
                executions_added += 1
    executions = manifest["executions"]
    superseded_failures = 0
    remaining_executions = []
    for index, execution in enumerate(executions):
        if not isinstance(execution, dict) or type(execution.get("exit_code")) is not int or execution["exit_code"] == 0:
            remaining_executions.append(execution)
            continue
        command = execution.get("command")
        if not isinstance(command, str):
            remaining_executions.append(execution)
            continue
        successful_retry = next((
            candidate
            for candidate_index, candidate in enumerate(executions)
            if isinstance(candidate, dict)
            and candidate.get("command") == command
            and type(candidate.get("exit_code")) is int
            and candidate["exit_code"] == 0
            and candidate.get("id") is not None
            and _execution_is_later(candidate, candidate_index, execution, index)
        ), None)
        if successful_retry is None:
            remaining_executions.append(execution)
            continue
        superseded.append({**execution, "superseded_by": successful_retry["id"]})
        superseded_failures += 1
    manifest["executions"] = remaining_executions
    manifest["superseded_executions"] = superseded
    _atomic_commit(run_dir, lane_updates, manifest, archive_moves)
    if review_archive:
        print(f"Archived prior review files to {review_archive}")
    archived_deterministic = {_canonical_relative(source) for source, _destination in archive_moves}
    stale_deterministic_review = [
        path.relative_to(run_dir).as_posix() for path in deterministic_files
        if _canonical_relative(path.relative_to(run_dir).as_posix()) not in archived_deterministic
    ]
    return {"added": added, "rehashed_changed": changed,
            "unchanged_count": unchanged, "lanes_updated": lanes_updated, "executions_added": executions_added,
            "code_entries": len(manifest["code"]), "review_archive": review_archive,
            "superseded_failures": superseded_failures,
            "stale_deterministic_review": stale_deterministic_review}


def prepare_review(
    run_dir: Path, *, tier: str, modes: list[str] | None = None,
    questions: list[str] | None = None, new_round: bool = False,
    kind_overrides: list[tuple[str, str]] | None = None,
    default_kind: str | None = None,
) -> dict[str, Any]:
    """Refresh, record existing checks, refresh their outputs, and build a packet."""
    from codex_science.reviewer_runtime import build_review_packet
    run_dir = run_dir.resolve()
    problems: list[dict[str, Any]] = []
    outputs: list[str] = []
    packet_path = run_dir / "review-task.json"
    packet_existed = packet_path.exists()
    generated_kinds = [("citation-trace.json", "citation-trace"),
                       ("claim-sufficiency.json", "claim-sufficiency")]
    refresh_kinds = [*(kind_overrides or []), *generated_kinds]
    # Refuse before run_exec writes its execution log when current review evidence
    # exists and the caller did not explicitly start a new round.
    manifest_path = _write_target(run_dir, "manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts = manifest.get("artifacts", [])
    review = manifest.get("review", {})
    if not new_round and (
        any(isinstance(item, dict) and item.get("kind") in REVIEW_KINDS for item in artifacts)
        or (isinstance(review, dict) and review.get("status", "pending") != "pending")
        or _review_flow_files(run_dir)
    ):
        raise ValueError(
            "Run has independent review evidence; any change invalidates the independent review. "
            "Start a new review round with --new-round (which archives prior review files), "
            "or register a passed receipt with --register-receipt."
        )

    def recorded_json(prefix: str, script: str, arguments: list[str], output_name: str) -> dict[str, Any]:
        manifest_now = json.loads(manifest_path.read_text(encoding="utf-8"))
        used = {
            str(item.get("id")) for item in manifest_now.get("executions", [])
            if isinstance(item, dict) and item.get("id") is not None
        }
        log_file = run_dir / "execution-log.jsonl"
        if log_file.exists():
            used.update(
                str(item.get("id")) for item in
                (json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines() if line.strip())
                if isinstance(item, dict) and item.get("id") is not None
            )
        number = 1
        while f"{prefix}-{number:03d}" in used or (run_dir / "logs" / f"{prefix}-{number:03d}.log").exists():
            number += 1
        identifier = f"{prefix}-{number:03d}"
        command = [sys.executable, str(Path(__file__).resolve().parents[2] / "scripts" / script), *arguments]
        with contextlib.redirect_stdout(io.StringIO()):
            code = run_exec(run_dir, command, identifier)
        log_path = run_dir / "logs" / f"{identifier}.log"
        try:
            payload = json.loads(log_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"{script} did not produce valid JSON: {error}") from error
        return {"exit_code": code, "result": payload, "output_name": output_name}

    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            initial_refresh = refresh(
                run_dir,
                refresh_kinds,
                invalidate_review=new_round,
                default_kind=default_kind,
            )
        outputs.append("manifest.json")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        problems.append({"stage": "refresh", "phase": "initial", "error": str(error)})
        stale_packet = packet_path.is_file()
        # Read-only previews so one call lists every problem; a preview failure must not mask the refresh error.
        from codex_science.citation_trace import trace_citations
        from codex_science.claim_sufficiency import check_sufficiency
        try:
            preview = trace_citations(run_dir)
            failure = "no_report_examined" if preview["reports_examined"] == 0 else (
                "orphan_citations" if preview["orphans"] else None)
            if failure:
                problems.append({"stage": "citation-trace", "preview": True,
                                 "findings": preview["orphans"], "error": failure})
        except Exception as preview_error:  # noqa: BLE001 - preview only
            problems.append({"stage": "citation-trace", "preview": True, "findings": [],
                             "error": {"code": "invalid_input", "message": str(preview_error)}})
        try:
            advisory = [item for item in check_sufficiency(run_dir, tier=tier).get("claims", [])
                        if item.get("verdict") in {"insufficient", "contradicted_unresolved"}]
            if advisory:
                problems.append({"stage": "claim-sufficiency", "preview": True, "advisory": advisory})
        except Exception:  # noqa: BLE001 - stale manifest; preview is best-effort
            pass
        return {"schema": "prepare-review-v1", "problems": problems, "outputs_written": outputs,
                "review_task_stale": stale_packet, "refresh": {"initial": None, "final": None},
                "next": "fix the listed findings and rerun prepare-review once"}

    trace = recorded_json("prepare-review-citations", "trace_citations.py",
                          ["--run-dir", str(run_dir), "--require-traced"], "citation-trace.json")
    trace_result = trace["result"]
    if trace["exit_code"] != 0 or trace_result.get("orphans"):
        problems.append({"stage": "citation-trace", "findings": trace_result.get("orphans", []),
                         "error": trace_result.get("error") or trace_result.get("require_traced_failure")})
    sufficiency = recorded_json("prepare-review-sufficiency", "check_claim_sufficiency.py",
                                ["--run-dir", str(run_dir), "--tier", tier], "claim-sufficiency.json")
    sufficiency_result = sufficiency["result"]
    if sufficiency["exit_code"] != 0:
        problems.append({"stage": "claim-sufficiency", "error": sufficiency_result.get("error")})
    else:
        advisory = [item for item in sufficiency_result.get("claims", [])
                    if item.get("verdict") in {"insufficient", "contradicted_unresolved"}]
        if advisory:
            problems.append({"stage": "claim-sufficiency", "advisory": advisory})
    for result in (trace, sufficiency):
        _atomic_write(run_dir, result["output_name"],
                      (json.dumps(result["result"], indent=2, sort_keys=True) + "\n").encode())
        outputs.append(result["output_name"])
    final_refresh = None
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            final_refresh = refresh(run_dir, refresh_kinds, default_kind=default_kind)
        outputs.append("manifest.json")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        problems.append({"stage": "refresh", "phase": "final", "error": str(error)})
    deterministic = None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        sidecars = validate_bundle(manifest, run_dir)
        deterministic = review_manifest(manifest, run_dir, sidecars=sidecars)
        _atomic_write(run_dir, "deterministic-review.json", (json.dumps(deterministic, indent=2, sort_keys=True) + "\n").encode())
        outputs.append("deterministic-review.json")
        if deterministic.get("findings"):
            problems.append({"stage": "deterministic-review", "findings": deterministic["findings"]})
    except (OSError, ValueError, json.JSONDecodeError) as error:
        problems.append({"stage": "deterministic-review", "error": str(error)})
    blocking = any(item.get("stage") != "claim-sufficiency" or "error" in item for item in problems)
    packet_written = False
    if not blocking:
        try:
            packet = build_review_packet(manifest_path, review_modes=modes or ["record", "source", "method"],
                                         review_questions=questions, tier=tier)
            _atomic_write(run_dir, "review-task.json", (json.dumps(packet, indent=2, sort_keys=True) + "\n").encode())
            outputs.append("review-task.json")
            packet_written = True
        except (OSError, ValueError, json.JSONDecodeError) as error:
            problems.append({"stage": "packet", "error": str(error)})
    stale_packet = False
    if packet_path.is_file():
        try:
            current_digest = _sha(manifest_path)
            packet_payload = json.loads(packet_path.read_text(encoding="utf-8"))
            stale_packet = packet_payload.get("source_manifest_sha256") != current_digest
        except (OSError, UnicodeError, json.JSONDecodeError, AttributeError):
            stale_packet = True
    elif packet_existed and not packet_written:
        stale_packet = True
    if packet_existed and not packet_written and problems:
        stale_packet = True
    return {"schema": "prepare-review-v1", "problems": problems, "outputs_written": list(dict.fromkeys(outputs)),
            "review_task_stale": stale_packet, "refresh": {"initial": initial_refresh, "final": final_refresh},
            "next": "spawn the independent reviewer with review-task.json" if packet_written else "fix the listed findings and rerun prepare-review once"}
