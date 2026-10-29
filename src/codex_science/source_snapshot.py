"""Immutable, content-bound Git source bundles for durable jobs."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Mapping, Sequence

from codex_science.artifact_store import stream_sha256


SOURCE_ARCHIVE_NAME = "source.tar"
SOURCE_RECEIPT_NAME = "source-receipt.json"
MAX_SOURCE_CONTENT_BYTES = 480 * 1024 * 1024
MAX_SOURCE_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_SOURCE_ENTRIES = 32_000


class SourceSnapshotError(ValueError):
    """A strict source snapshot could not be proven safe and reproducible."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _fingerprint(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _object_id(value: Any, label: str) -> str:
    text = str(value).strip().lower()
    if len(text) not in {40, 64} or any(character not in "0123456789abcdef" for character in text):
        raise SourceSnapshotError(f"{label} must be an exact 40- or 64-hex Git object ID")
    return text


def _sha256(value: Any, label: str) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise SourceSnapshotError(f"{label} must be a SHA-256 digest")
    return text


def _safe_relative(value: Any, label: str, *, allow_dot: bool = False) -> str:
    text = str(value)
    pure = PurePosixPath(text)
    if not text.strip() or "\0" in text or pure.is_absolute() or ".." in pure.parts:
        raise SourceSnapshotError(f"{label} must be a safe relative path")
    normalized = pure.as_posix()
    if normalized == "." and not allow_dot:
        raise SourceSnapshotError(f"{label} cannot name the source root")
    if ".git" in pure.parts:
        raise SourceSnapshotError(f"{label} cannot include Git metadata")
    return normalized


def _git_environment() -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    return environment


def _run_git(working: Path, *arguments: str, binary: bool = False) -> str | bytes:
    completed = subprocess.run(
        ["git", "-c", "core.fsmonitor=false", "-C", str(working), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_git_environment(),
        text=not binary,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr if isinstance(completed.stderr, str) else os.fsdecode(completed.stderr)
        raise SourceSnapshotError(f"git {' '.join(arguments)} failed: {stderr.strip() or 'unknown error'}")
    return completed.stdout


def _git_identity(
    working_directory: Path,
    expected_commit: str,
    *,
    allowed_untracked_path: Path | None = None,
) -> dict[str, Any]:
    working = working_directory.resolve(strict=True)
    root_output = _run_git(working, "rev-parse", "--show-toplevel", binary=True)
    assert isinstance(root_output, bytes)
    root = Path(os.fsdecode(root_output.removesuffix(b"\n"))).resolve(strict=True)
    if not working.is_relative_to(root):
        raise SourceSnapshotError("working_directory is outside its Git worktree")
    head = _object_id(str(_run_git(working, "rev-parse", "--verify", "HEAD")).strip(), "Git HEAD")
    if head != expected_commit:
        raise SourceSnapshotError(f"Git HEAD moved: expected {expected_commit}, found {head}")
    status_output = _run_git(
        working,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--ignore-submodules=none",
        binary=True,
    )
    assert isinstance(status_output, bytes)
    if status_output and allowed_untracked_path is not None:
        allowed = allowed_untracked_path.resolve()
        if allowed.is_relative_to(root):
            prefix = os.fsencode(allowed.relative_to(root).as_posix())
            records = [record for record in status_output.split(b"\0") if record]
            if all(
                record.startswith(b"?? ")
                and (record[3:] == prefix or record[3:].startswith(prefix + b"/"))
                for record in records
            ):
                status_output = b""
    if status_output:
        raise SourceSnapshotError("Git worktree is dirty (tracked or untracked changes present)")
    tree = _object_id(str(_run_git(working, "rev-parse", "--verify", "HEAD^{tree}")).strip(), "Git tree")
    listing = _run_git(working, "ls-tree", "-r", "-l", "-z", "--full-tree", head, binary=True)
    assert isinstance(listing, bytes)
    entry_count = 0
    tracked_bytes = 0
    entries: list[dict[str, Any]] = []
    directory_paths: set[tuple[str, ...]] = set()
    for raw in listing.split(b"\0"):
        if not raw:
            continue
        metadata, separator, path_raw = raw.partition(b"\t")
        if not separator:
            raise SourceSnapshotError("Git tree contains an invalid entry")
        fields = metadata.split()
        if len(fields) != 4:
            raise SourceSnapshotError("Git tree contains invalid size metadata")
        mode, _kind, object_raw, size_raw = fields
        path = os.fsdecode(path_raw)
        _safe_relative(path, "Git tree entry")
        path_parts = PurePosixPath(path).parts
        directory_paths.update(path_parts[:index] for index in range(1, len(path_parts)))
        if mode == b"120000":
            raise SourceSnapshotError(f"tracked symbolic links are forbidden: {path}")
        if mode == b"160000":
            raise SourceSnapshotError(f"Git submodules are forbidden: {path}")
        if mode not in {b"100644", b"100755"}:
            raise SourceSnapshotError(f"unsupported Git tree mode {os.fsdecode(mode)}: {path}")
        try:
            size = int(size_raw)
            tracked_bytes += size
        except ValueError as error:
            raise SourceSnapshotError(f"Git tree entry has no bounded blob size: {path}") from error
        if tracked_bytes > MAX_SOURCE_CONTENT_BYTES:
            raise SourceSnapshotError("committed source content exceeds the bounded bundle limit")
        entry_count += 1
        if entry_count > MAX_SOURCE_ENTRIES:
            raise SourceSnapshotError(f"source exceeds the {MAX_SOURCE_ENTRIES}-entry limit")
        entries.append(
            {
                "path": path,
                "mode": os.fsdecode(mode),
                "object": _object_id(os.fsdecode(object_raw), f"Git blob for {path}"),
                "size": size,
            }
        )
    tracked_entry_count = entry_count + len(directory_paths)
    if tracked_entry_count > MAX_SOURCE_ENTRIES:
        raise SourceSnapshotError(f"source exceeds the {MAX_SOURCE_ENTRIES}-entry limit")
    relative_cwd = working.relative_to(root).as_posix() or "."
    return {
        "root": root,
        "working": working,
        "commit": head,
        "tree": tree,
        "worktree_relative_cwd": relative_cwd,
        "tracked_entry_count": tracked_entry_count,
        "tracked_file_count": entry_count,
        "tracked_bytes": tracked_bytes,
        "entries": entries,
        "directory_paths": directory_paths,
    }


def _checked_input_path(working: Path, relative: str) -> Path:
    normalized = _safe_relative(relative, "input path")
    current = working
    for part in PurePosixPath(normalized).parts:
        current = current / part
        try:
            metadata = current.lstat()
        except FileNotFoundError as error:
            raise SourceSnapshotError(f"input path is missing: {relative}") from error
        if stat.S_ISLNK(metadata.st_mode):
            raise SourceSnapshotError(f"symbolic links are forbidden in source inputs: {relative}")
    if not (current.is_file() or current.is_dir()):
        raise SourceSnapshotError(f"unsupported source input object: {relative}")
    return current


def _regular_file_sha256(path: Path) -> tuple[str, int]:
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
        )
    except OSError as error:
        raise SourceSnapshotError(f"source input could not be opened safely: {path}: {error}") from error
    with os.fdopen(descriptor, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise SourceSnapshotError(f"source input must remain a regular file: {path}")
        digest = hashlib.sha256()
        size = 0
        while chunk := handle.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_SOURCE_CONTENT_BYTES:
                raise SourceSnapshotError("source input content exceeds the bounded bundle limit")
            digest.update(chunk)
    return digest.hexdigest(), size


def _scan_regular_tree(root: Path) -> dict[str, Any]:
    entries = 0
    total_bytes = 0
    directories: set[tuple[str, ...]] = set()
    files: list[dict[str, Any]] = []
    pending = [(root, ())]
    while pending:
        directory, relative_directory = pending.pop()
        with os.scandir(directory) as iterator:
            children = sorted(iterator, key=lambda item: item.name)
        for child in children:
            if child.name == ".git":
                raise SourceSnapshotError("source inputs cannot include Git metadata")
            metadata = child.stat(follow_symlinks=False)
            if stat.S_ISLNK(metadata.st_mode):
                raise SourceSnapshotError(f"symbolic links are forbidden in source inputs: {child.path}")
            entries += 1
            if entries > MAX_SOURCE_ENTRIES:
                raise SourceSnapshotError(f"source exceeds the {MAX_SOURCE_ENTRIES}-entry limit")
            if stat.S_ISDIR(metadata.st_mode):
                child_relative = (*relative_directory, child.name)
                directories.add(child_relative)
                pending.append((Path(child.path), child_relative))
            elif stat.S_ISREG(metadata.st_mode):
                relative_file = PurePosixPath(*relative_directory, child.name).as_posix()
                digest, size = _regular_file_sha256(Path(child.path))
                total_bytes += size
                if total_bytes > MAX_SOURCE_CONTENT_BYTES:
                    raise SourceSnapshotError("source input content exceeds the bounded bundle limit")
                files.append({"path": relative_file, "size": size, "sha256": digest})
            else:
                raise SourceSnapshotError(f"unsupported filesystem object in source input: {child.path}")
    files.sort(key=lambda item: str(item["path"]))
    material = {"algorithm": "sha256-merkle-v1", "entries": files}
    return {
        "entry_count": entries,
        "total_bytes": total_bytes,
        "directories": directories,
        "files": files,
        "root_sha256": hashlib.sha256(_canonical_bytes(material)).hexdigest(),
    }


def _verify_inputs(working: Path, inputs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    verified: list[dict[str, Any]] = []
    path_parts: list[tuple[str, tuple[str, ...]]] = []
    for item in inputs:
        input_id = str(item.get("id", "")).strip()
        if not input_id:
            raise SourceSnapshotError("every source input requires an ID")
        if item.get("path") is None:
            verified.append(
                {
                    "id": input_id,
                    "path": None,
                    "target": None,
                    "entry_count": 0,
                    "file_count": 0,
                    "file_manifest": {},
                    "directory_paths": set(),
                    "size_bytes": 0,
                }
            )
            continue
        relative = _safe_relative(item["path"], f"input {input_id} path")
        parts = PurePosixPath(relative).parts
        for other_id, other_parts in path_parts:
            shared = min(len(parts), len(other_parts))
            if parts[:shared] == other_parts[:shared]:
                raise SourceSnapshotError(f"strict source inputs overlap: {other_id} and {input_id}")
        path_parts.append((input_id, parts))
        target = _checked_input_path(working, relative)
        target_metadata = target.lstat()
        if stat.S_ISREG(target_metadata.st_mode):
            expected = item.get("sha256")
            if expected is None:
                raise SourceSnapshotError(f"strict source input {input_id} requires sha256")
            actual, size = _regular_file_sha256(target)
            if actual != _sha256(expected, f"input {input_id} sha256"):
                raise SourceSnapshotError(f"strict source input {input_id} digest mismatch: {actual}")
            if size > MAX_SOURCE_CONTENT_BYTES:
                raise SourceSnapshotError("source input content exceeds the bounded bundle limit")
            kind = "file"
            entry_count = 1
            file_count = 1
            file_manifest = {"": {"path": "", "size": size, "sha256": actual}}
            directory_paths = {parts[:index] for index in range(1, len(parts))}
        elif stat.S_ISDIR(target_metadata.st_mode):
            expected = item.get("root_sha256")
            if expected is None:
                raise SourceSnapshotError(f"strict source input {input_id} requires root_sha256")
            descriptor = _scan_regular_tree(target)
            size = int(descriptor["total_bytes"])
            file_count = len(descriptor["files"])
            entry_count = int(descriptor["entry_count"]) + 1
            directory_paths = {parts[:index] for index in range(1, len(parts) + 1)}
            directory_paths.update((*parts, *nested) for nested in descriptor["directories"])
            if descriptor["root_sha256"] != _sha256(expected, f"input {input_id} root_sha256"):
                raise SourceSnapshotError(
                    f"strict source input {input_id} digest mismatch: {descriptor['root_sha256']}"
                )
            kind = "directory"
            file_manifest = {str(entry["path"]): dict(entry) for entry in descriptor["files"]}
        else:
            raise SourceSnapshotError(f"source input changed type while verifying: {relative}")
        verified.append(
            {
                "id": input_id,
                "path": relative,
                "target": target,
                "kind": kind,
                "entry_count": entry_count,
                "file_count": file_count,
                "file_manifest": file_manifest,
                "directory_paths": directory_paths,
                "size_bytes": size,
            }
        )
    return verified


def _enforce_aggregate_limit(identity: Mapping[str, Any], inputs: Sequence[Mapping[str, Any]]) -> None:
    directories = set(identity["directory_paths"])
    cwd_parts = () if identity["worktree_relative_cwd"] == "." else PurePosixPath(
        identity["worktree_relative_cwd"]
    ).parts
    for item in inputs:
        directories.update((*cwd_parts, *parts) for parts in item["directory_paths"])
    entries = (
        int(identity["tracked_file_count"])
        + sum(int(item["file_count"]) for item in inputs)
        + len(directories)
    )
    size = int(identity["tracked_bytes"]) + sum(int(item["size_bytes"]) for item in inputs)
    if entries > MAX_SOURCE_ENTRIES:
        raise SourceSnapshotError(f"committed source plus inputs exceeds the {MAX_SOURCE_ENTRIES}-entry limit")
    if size > MAX_SOURCE_CONTENT_BYTES:
        raise SourceSnapshotError("committed source plus inputs exceeds the bounded bundle limit")


def preflight_git_source(
    working_directory: Path,
    commit: str,
    inputs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return one fail-closed readiness check for a strict Git source route."""

    try:
        expected = _object_id(commit, "source_snapshot commit")
        identity = _git_identity(working_directory, expected)
        verified = _verify_inputs(identity["working"], inputs)
        _enforce_aggregate_limit(identity, verified)
    except (OSError, SourceSnapshotError, ValueError) as error:
        return {"name": "source-snapshot", "ready": False, "detail": str(error)}
    return {
        "name": "source-snapshot",
        "ready": True,
        "detail": {
            "mode": "git-archive",
            "commit": identity["commit"],
            "tree": identity["tree"],
            "worktree_relative_cwd": identity["worktree_relative_cwd"],
            "input_ids": [item["id"] for item in verified],
        },
    }


def _safe_extract(archive: BinaryIO, destination: Path) -> None:
    entries = 0
    total_bytes = 0
    seen: set[str] = set()
    with tarfile.open(fileobj=archive, mode="r:") as bundle:
        for member in bundle:
            relative = _safe_relative(member.name, "source archive member")
            if relative in seen:
                raise SourceSnapshotError(f"duplicate source archive member: {relative}")
            seen.add(relative)
            entries += 1
            if entries > MAX_SOURCE_ENTRIES:
                raise SourceSnapshotError(f"source exceeds the {MAX_SOURCE_ENTRIES}-entry limit")
            target = destination.joinpath(*PurePosixPath(relative).parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True, mode=0o700)
                target.chmod(member.mode & 0o777)
                continue
            if not member.isfile():
                raise SourceSnapshotError(f"unsupported source archive member: {relative}")
            total_bytes += member.size
            if total_bytes > MAX_SOURCE_CONTENT_BYTES:
                raise SourceSnapshotError("source content exceeds the bounded bundle limit")
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            extracted = bundle.extractfile(member)
            if extracted is None:
                raise SourceSnapshotError(f"could not read source archive member: {relative}")
            with target.open("xb") as output:
                shutil.copyfileobj(extracted, output, length=1024 * 1024)
            target.chmod(member.mode & 0o777)


def _git_blob_digest(path: Path, size: int, object_id: str) -> str:
    algorithm = "sha1" if len(object_id) == 40 else "sha256"
    digest = hashlib.new(algorithm, usedforsecurity=False)
    digest.update(f"blob {size}\0".encode("ascii"))
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _materialize_git_tree(identity: Mapping[str, Any], destination: Path) -> None:
    working = Path(identity["working"])
    for item in identity["entries"]:
        relative = _safe_relative(item["path"], "Git tree entry")
        target = destination.joinpath(*PurePosixPath(relative).parts)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with target.open("xb") as output:
            completed = subprocess.run(
                [
                    "git",
                    "-c",
                    "core.fsmonitor=false",
                    "-C",
                    str(working),
                    "cat-file",
                    "blob",
                    str(item["object"]),
                ],
                stdout=output,
                stderr=subprocess.PIPE,
                env=_git_environment(),
                check=False,
            )
        if completed.returncode != 0:
            stderr = os.fsdecode(completed.stderr)
            raise SourceSnapshotError(f"git cat-file blob failed: {stderr.strip() or 'unknown error'}")
        if target.stat().st_size != int(item["size"]):
            raise SourceSnapshotError(f"Git blob size mismatch while materializing: {relative}")
        if _git_blob_digest(target, int(item["size"]), str(item["object"])) != item["object"]:
            raise SourceSnapshotError(f"Git blob object ID mismatch while materializing: {relative}")
        target.chmod(0o755 if item["mode"] == "100755" else 0o644)
    for directory in sorted(
        (path for path in destination.rglob("*") if path.is_dir()),
        key=lambda path: len(path.relative_to(destination).parts),
        reverse=True,
    ):
        directory.chmod(0o755)


def _ensure_overlay_directory(path: Path) -> None:
    if path.exists() or path.is_symlink():
        metadata = path.lstat()
        if not stat.S_ISDIR(metadata.st_mode):
            raise SourceSnapshotError(f"source input conflicts with committed source: {path}")
        return
    _ensure_overlay_directory(path.parent)
    path.mkdir(mode=0o700)
    path.chmod(0o700)


def _copy_file(
    source: Path,
    target: Path,
    *,
    expected_sha256: str,
    expected_size: int,
) -> None:
    metadata = source.lstat()
    if not stat.S_ISREG(metadata.st_mode):
        raise SourceSnapshotError(f"source input changed type while bundling: {source}")
    if metadata.st_size != expected_size:
        raise SourceSnapshotError(f"source input changed size while bundling: {source}")
    _ensure_overlay_directory(target.parent)
    target_mode = 0o600
    if target.exists() or target.is_symlink():
        target_metadata = target.lstat()
        if not stat.S_ISREG(target_metadata.st_mode):
            raise SourceSnapshotError(f"source input conflicts with committed source: {target}")
        target_mode = stat.S_IMODE(target_metadata.st_mode)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".input-", dir=target.parent)
    temporary = Path(temporary_name)
    source_descriptor = -1
    try:
        source_descriptor = os.open(
            source,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
        )
        source_metadata = os.fstat(source_descriptor)
        if (
            not stat.S_ISREG(source_metadata.st_mode)
            or source_metadata.st_dev != metadata.st_dev
            or source_metadata.st_ino != metadata.st_ino
            or source_metadata.st_size != expected_size
        ):
            raise SourceSnapshotError(f"source input changed type while bundling: {source}")
        with os.fdopen(descriptor, "wb") as output, os.fdopen(source_descriptor, "rb") as input_handle:
            descriptor = -1
            source_descriptor = -1
            digest = hashlib.sha256()
            copied = 0
            while True:
                remaining = expected_size - copied
                chunk = input_handle.read(min(1024 * 1024, remaining + 1))
                if not chunk:
                    break
                copied += len(chunk)
                if copied > expected_size or copied > MAX_SOURCE_CONTENT_BYTES:
                    raise SourceSnapshotError(f"source input grew while bundling: {source}")
                digest.update(chunk)
                output.write(chunk)
            if copied != expected_size or digest.hexdigest() != _sha256(
                expected_sha256, "copied source input sha256"
            ):
                raise SourceSnapshotError(f"source input changed while bundling: {source}")
            output.flush()
            os.fsync(output.fileno())
        temporary.chmod(target_mode)
        os.replace(temporary, target)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if source_descriptor >= 0:
            os.close(source_descriptor)
        temporary.unlink(missing_ok=True)


def _overlay_input(
    source: Path,
    target: Path,
    *,
    expected_files: Mapping[str, Mapping[str, Any]],
    seen: set[str],
    relative_parts: tuple[str, ...] = (),
    root: bool = True,
) -> bool:
    source_metadata = source.lstat()
    if stat.S_ISREG(source_metadata.st_mode):
        relative = "" if not relative_parts else PurePosixPath(*relative_parts).as_posix()
        expected = expected_files.get(relative)
        if expected is None:
            raise SourceSnapshotError(f"unexpected source input file while bundling: {relative}")
        _copy_file(
            source,
            target,
            expected_sha256=str(expected["sha256"]),
            expected_size=int(expected["size"]),
        )
        seen.add(relative)
        return True
    if not stat.S_ISDIR(source_metadata.st_mode):
        raise SourceSnapshotError(f"unsupported filesystem object in source input: {source}")
    with os.scandir(source) as iterator:
        children = sorted(iterator, key=lambda item: item.name)
    materialized = False
    target_existed = target.is_dir() and not target.is_symlink()
    if root or target_existed:
        _ensure_overlay_directory(target)
        materialized = True
    for child in children:
        if child.name == ".git":
            raise SourceSnapshotError("source inputs cannot include Git metadata")
        metadata = child.stat(follow_symlinks=False)
        child_source = Path(child.path)
        child_target = target / child.name
        child_relative = (*relative_parts, child.name)
        if stat.S_ISDIR(metadata.st_mode):
            materialized = _overlay_input(
                child_source,
                child_target,
                expected_files=expected_files,
                seen=seen,
                relative_parts=child_relative,
                root=False,
            ) or materialized
        elif stat.S_ISREG(metadata.st_mode):
            materialized = _overlay_input(
                child_source,
                child_target,
                expected_files=expected_files,
                seen=seen,
                relative_parts=child_relative,
                root=False,
            ) or materialized
        else:
            raise SourceSnapshotError(f"unsupported filesystem object in source input: {child.path}")
    return materialized


def _write_deterministic_tar(source_root: Path, destination: Path) -> tuple[str, int]:
    descriptor, temporary_name = tempfile.mkstemp(prefix=".source-", suffix=".tar", dir=destination.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        entries = 0
        total_bytes = 0
        with tarfile.open(temporary, mode="w", format=tarfile.PAX_FORMAT, dereference=False) as bundle:
            for path in sorted(source_root.rglob("*"), key=lambda item: item.relative_to(source_root).as_posix()):
                relative = path.relative_to(source_root).as_posix()
                metadata = path.lstat()
                if stat.S_ISLNK(metadata.st_mode):
                    raise SourceSnapshotError(f"symbolic links are forbidden in source bundle: {relative}")
                entries += 1
                if entries > MAX_SOURCE_ENTRIES:
                    raise SourceSnapshotError(f"source exceeds the {MAX_SOURCE_ENTRIES}-entry limit")
                info = tarfile.TarInfo(relative)
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                info.mtime = 0
                info.mode = metadata.st_mode & 0o777
                if stat.S_ISDIR(metadata.st_mode):
                    info.type = tarfile.DIRTYPE
                    bundle.addfile(info)
                elif stat.S_ISREG(metadata.st_mode):
                    total_bytes += metadata.st_size
                    if total_bytes > MAX_SOURCE_CONTENT_BYTES:
                        raise SourceSnapshotError("source content exceeds the bounded bundle limit")
                    info.size = metadata.st_size
                    with path.open("rb") as handle:
                        bundle.addfile(info, handle)
                else:
                    raise SourceSnapshotError(f"unsupported filesystem object in source bundle: {relative}")
        size = temporary.stat().st_size
        if size > MAX_SOURCE_ARCHIVE_BYTES:
            raise SourceSnapshotError("source archive exceeds the bounded bundle limit")
        digest, measured_size = stream_sha256(temporary)
        if measured_size != size:
            raise SourceSnapshotError("source archive size changed while hashing")
        temporary.chmod(0o600)
        os.replace(temporary, destination)
        return digest, size
    finally:
        temporary.unlink(missing_ok=True)


def create_git_source_bundle(
    *,
    working_directory: Path,
    commit: str,
    inputs: Sequence[Mapping[str, Any]],
    job_spec_sha256: str,
    job_dir: Path,
    allowed_untracked_path: Path | None = None,
) -> dict[str, Any]:
    """Create and fingerprint an exact-commit source bundle in ``job_dir``."""

    expected = _object_id(commit, "source_snapshot commit")
    if allowed_untracked_path is not None:
        allowed = allowed_untracked_path.resolve()
        if allowed != job_dir.resolve():
            raise SourceSnapshotError("allowed untracked staging path must be the managed job directory")
        allowed_metadata = allowed.lstat()
        if not stat.S_ISDIR(allowed_metadata.st_mode) or stat.S_IMODE(allowed_metadata.st_mode) & 0o077:
            raise SourceSnapshotError("allowed untracked staging directory must be owner-only")
    identity = _git_identity(
        working_directory,
        expected,
        allowed_untracked_path=allowed_untracked_path,
    )
    verified = _verify_inputs(identity["working"], inputs)
    _enforce_aggregate_limit(identity, verified)
    job_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    job_dir.chmod(0o700)
    stage = Path(tempfile.mkdtemp(prefix=".source-stage-", dir=job_dir))
    stage.chmod(0o700)
    archive_path = stage.with_name(stage.name + ".tar")
    try:
        _materialize_git_tree(identity, stage)
        cwd_root = stage.joinpath(*PurePosixPath(identity["worktree_relative_cwd"]).parts)
        if not cwd_root.is_dir():
            raise SourceSnapshotError("committed working_directory is absent from the source archive")
        for item in verified:
            if item["path"] is not None:
                target = cwd_root.joinpath(*PurePosixPath(item["path"]).parts)
                seen: set[str] = set()
                _overlay_input(
                    item["target"],
                    target,
                    expected_files=item["file_manifest"],
                    seen=seen,
                )
                if seen != set(item["file_manifest"]):
                    raise SourceSnapshotError(f"source input changed while bundling: {item['id']}")
        # Bind copied bytes, not merely the earlier live-path observation.
        _verify_inputs(cwd_root, inputs)
        # Detect a source or input mutation during materialization.
        repeated = _git_identity(
            identity["working"],
            expected,
            allowed_untracked_path=allowed_untracked_path,
        )
        _verify_inputs(repeated["working"], inputs)
        archive_sha256, archive_size = _write_deterministic_tar(stage, archive_path)
        # Prove the archive round trip preserves the declared input Merkle roots.
        shutil.rmtree(stage)
        stage.mkdir(mode=0o700)
        stage.chmod(0o700)
        with archive_path.open("rb") as archive:
            _safe_extract(archive, stage)
        restored_cwd = stage.joinpath(*PurePosixPath(identity["worktree_relative_cwd"]).parts)
        _verify_inputs(restored_cwd, inputs)
        os.replace(archive_path, job_dir / SOURCE_ARCHIVE_NAME)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        archive_path.unlink(missing_ok=True)
    material = {
        "schema_version": 1,
        "mode": "git-archive",
        "job_spec_sha256": _sha256(job_spec_sha256, "job spec fingerprint"),
        "commit": identity["commit"],
        "tree": identity["tree"],
        "worktree_relative_cwd": identity["worktree_relative_cwd"],
        "archive": {
            "path": SOURCE_ARCHIVE_NAME,
            "sha256": archive_sha256,
            "size_bytes": archive_size,
        },
        "input_ids": [item["id"] for item in verified],
    }
    receipt = {**material, "fingerprint": _fingerprint(material)}
    validate_source_receipt(receipt, expected_job_spec_sha256=job_spec_sha256)
    return receipt


def validate_source_receipt(
    receipt: Mapping[str, Any],
    *,
    expected_job_spec_sha256: str | None = None,
) -> dict[str, Any]:
    if receipt.get("schema_version") != 1 or receipt.get("mode") != "git-archive":
        raise SourceSnapshotError("invalid source snapshot receipt")
    _object_id(receipt.get("commit"), "source receipt commit")
    _object_id(receipt.get("tree"), "source receipt tree")
    _safe_relative(receipt.get("worktree_relative_cwd"), "source receipt cwd", allow_dot=True)
    spec_digest = _sha256(receipt.get("job_spec_sha256"), "source receipt job spec fingerprint")
    if expected_job_spec_sha256 is not None and spec_digest != _sha256(
        expected_job_spec_sha256, "expected job spec fingerprint"
    ):
        raise SourceSnapshotError("source receipt covers a different job spec")
    archive = receipt.get("archive")
    if not isinstance(archive, Mapping):
        raise SourceSnapshotError("source receipt archive descriptor is required")
    path = _safe_relative(archive.get("path"), "source archive path")
    if path != SOURCE_ARCHIVE_NAME:
        raise SourceSnapshotError("source receipt must use the managed source archive path")
    _sha256(archive.get("sha256"), "source archive sha256")
    size = int(archive.get("size_bytes", -1))
    if size <= 0 or size > MAX_SOURCE_ARCHIVE_BYTES:
        raise SourceSnapshotError("source archive size is outside the bounded limit")
    input_ids = receipt.get("input_ids")
    if not isinstance(input_ids, list) or any(not str(item).strip() for item in input_ids):
        raise SourceSnapshotError("source receipt input_ids must be a list of non-empty IDs")
    if len({str(item) for item in input_ids}) != len(input_ids):
        raise SourceSnapshotError("source receipt input_ids must be unique")
    material = dict(receipt)
    fingerprint = str(material.pop("fingerprint", "")).lower()
    if _fingerprint(material) != fingerprint:
        raise SourceSnapshotError("source receipt fingerprint mismatch")
    return dict(receipt)


def materialize_source_bundle(
    job_dir: Path,
    receipt: Mapping[str, Any],
    *,
    expected_job_spec_sha256: str,
) -> Path:
    validated = validate_source_receipt(receipt, expected_job_spec_sha256=expected_job_spec_sha256)
    archive_record = validated["archive"]
    archive_path = job_dir / str(archive_record["path"])
    try:
        archive_descriptor = os.open(
            archive_path,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
        )
    except FileNotFoundError as error:
        raise SourceSnapshotError("source archive is missing") from error
    except OSError as error:
        raise SourceSnapshotError(f"source archive could not be opened safely: {error}") from error
    with os.fdopen(archive_descriptor, "rb") as mutable_archive, tempfile.TemporaryFile(
        mode="w+b", dir=job_dir
    ) as stable_archive:
        if not stat.S_ISREG(os.fstat(mutable_archive.fileno()).st_mode):
            raise SourceSnapshotError("source archive must be a regular file")
        digest = hashlib.sha256()
        actual_size = 0
        while chunk := mutable_archive.read(1024 * 1024):
            actual_size += len(chunk)
            if actual_size > MAX_SOURCE_ARCHIVE_BYTES:
                raise SourceSnapshotError("source archive exceeds the bounded bundle limit")
            digest.update(chunk)
            stable_archive.write(chunk)
        if actual_size != int(archive_record["size_bytes"]) or digest.hexdigest() != archive_record["sha256"]:
            raise SourceSnapshotError("source archive integrity check failed")
        stable_archive.flush()
        stable_archive.seek(0)
        source_root = job_dir / "source"
        if source_root.exists() or source_root.is_symlink():
            raise SourceSnapshotError("source materialization directory already exists")
        source_root.mkdir(mode=0o700)
        try:
            _safe_extract(stable_archive, source_root)
            cwd = source_root.joinpath(*PurePosixPath(validated["worktree_relative_cwd"]).parts)
            if not cwd.is_dir():
                raise SourceSnapshotError("source snapshot working directory is missing")
            return cwd
        except BaseException:
            shutil.rmtree(source_root, ignore_errors=True)
            raise


def materialized_working_directory(job_dir: Path, receipt: Mapping[str, Any]) -> Path:
    validated = validate_source_receipt(receipt)
    job_root = job_dir.resolve()
    source_path = job_dir / "source"
    try:
        source_metadata = source_path.lstat()
    except FileNotFoundError as error:
        raise SourceSnapshotError("materialized source directory is missing") from error
    if not stat.S_ISDIR(source_metadata.st_mode) or stat.S_ISLNK(source_metadata.st_mode):
        raise SourceSnapshotError("materialized source must be a real directory")
    root = source_path.resolve()
    if not root.is_relative_to(job_root):
        raise SourceSnapshotError("materialized source escapes the job directory")
    cwd_path = root.joinpath(*PurePosixPath(validated["worktree_relative_cwd"]).parts)
    try:
        cwd_metadata = cwd_path.lstat()
    except FileNotFoundError as error:
        raise SourceSnapshotError("materialized working directory is missing") from error
    if not stat.S_ISDIR(cwd_metadata.st_mode) or stat.S_ISLNK(cwd_metadata.st_mode):
        raise SourceSnapshotError("materialized working directory must be a real directory")
    cwd = cwd_path.resolve()
    if not cwd.is_relative_to(root):
        raise SourceSnapshotError("materialized working directory escapes the job source root")
    return cwd
