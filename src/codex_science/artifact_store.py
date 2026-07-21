"""Streaming and Merkle-hashed descriptors for large scientific artifacts."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterator, Mapping

DEFAULT_CHUNK_SIZE = 8 * 1024 * 1024
ARTIFACT_TYPES = {"file", "chunked-file", "directory-tree", "external-reference"}


def _hex_sha256(value: Any, label: str) -> str:
    text = str(value).lower().strip()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"{label} must be a SHA-256 digest")
    return text


def stream_sha256(path: Path, *, block_size: int = 1024 * 1024) -> tuple[str, int]:
    if block_size <= 0:
        raise ValueError("block_size must be positive")
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while chunk := handle.read(block_size):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def iter_chunk_hashes(path: Path, *, chunk_size: int = DEFAULT_CHUNK_SIZE) -> Iterator[dict[str, Any]]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    offset = 0
    index = 0
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            yield {
                "index": index,
                "offset": offset,
                "size": len(chunk),
                "sha256": hashlib.sha256(chunk).hexdigest(),
            }
            index += 1
            offset += len(chunk)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _validate_relative(value: str) -> str:
    pure = PurePosixPath(value)
    if not value or pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"artifact entry must be a safe relative path: {value}")
    return pure.as_posix()


@dataclass(frozen=True)
class ArtifactDescriptor:
    schema_version: int
    artifact_type: str
    root_sha256: str
    total_bytes: int
    entry_count: int
    media_type: str | None
    entries: tuple[dict[str, Any], ...]
    external: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["entries"] = [dict(item) for item in self.entries]
        return payload


def describe_file(
    path: Path,
    *,
    media_type: str | None = None,
    chunk_size: int | None = None,
) -> ArtifactDescriptor:
    if not path.is_file():
        raise ValueError(f"not a file: {path}")
    digest, size = stream_sha256(path)
    if chunk_size is None:
        entries = ({"path": path.name, "size": size, "sha256": digest},)
        artifact_type = "file"
    else:
        chunks = tuple(iter_chunk_hashes(path, chunk_size=chunk_size))
        entries = (
            {
                "path": path.name,
                "size": size,
                "sha256": digest,
                "chunk_size": chunk_size,
                "chunks": list(chunks),
            },
        )
        artifact_type = "chunked-file"
    return ArtifactDescriptor(1, artifact_type, digest, size, 1, media_type, entries)


def _directory_entries(root: Path, *, follow_symlinks: bool) -> tuple[dict[str, Any], ...]:
    entries: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            if not follow_symlinks:
                raise ValueError(f"symbolic links are forbidden in directory artifacts: {relative}")
            target = path.resolve()
            if not target.is_relative_to(root.resolve()):
                raise ValueError(f"symbolic link escapes directory artifact: {relative}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError(f"unsupported directory artifact entry: {relative}")
        digest, size = stream_sha256(path)
        entries.append({"path": _validate_relative(relative), "size": size, "sha256": digest})
    return tuple(entries)


def describe_directory(
    root: Path,
    *,
    media_type: str | None = None,
    follow_symlinks: bool = False,
) -> ArtifactDescriptor:
    if not root.is_dir():
        raise ValueError(f"not a directory: {root}")
    entries = _directory_entries(root, follow_symlinks=follow_symlinks)
    material = {"algorithm": "sha256-merkle-v1", "entries": list(entries)}
    root_digest = hashlib.sha256(_canonical_bytes(material)).hexdigest()
    return ArtifactDescriptor(
        1,
        "directory-tree",
        root_digest,
        sum(int(item["size"]) for item in entries),
        len(entries),
        media_type,
        entries,
    )


def describe_external_reference(
    *,
    uri: str,
    version: str,
    sha256: str,
    size_bytes: int | None = None,
    media_type: str | None = None,
    license: str | None = None,
) -> ArtifactDescriptor:
    if not uri.strip() or not version.strip():
        raise ValueError("external reference requires uri and version")
    digest = _hex_sha256(sha256, "sha256")
    external = {
        "uri": uri,
        "version": version,
        "sha256": digest,
        "size_bytes": size_bytes,
        "license": license,
    }
    return ArtifactDescriptor(
        1,
        "external-reference",
        digest,
        int(size_bytes or 0),
        0,
        media_type,
        (),
        external,
    )


def validate_descriptor(payload: Mapping[str, Any], path: Path | None = None) -> ArtifactDescriptor:
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported artifact descriptor schema")
    artifact_type = str(payload.get("artifact_type", ""))
    if artifact_type not in ARTIFACT_TYPES:
        raise ValueError(f"unsupported artifact type: {artifact_type}")
    root_sha256 = _hex_sha256(payload.get("root_sha256"), "root_sha256")
    total_bytes = int(payload.get("total_bytes", 0))
    entry_count = int(payload.get("entry_count", 0))
    entries_raw = payload.get("entries", [])
    if not isinstance(entries_raw, (list, tuple)):
        raise ValueError("entries must be a list")
    entries = tuple(dict(item) for item in entries_raw if isinstance(item, Mapping))
    if len(entries) != len(entries_raw):
        raise ValueError("every descriptor entry must be an object")
    for item in entries:
        _validate_relative(str(item.get("path", "")))
        _hex_sha256(item.get("sha256"), "entry sha256")
        if int(item.get("size", -1)) < 0:
            raise ValueError("entry size must be non-negative")
        chunks = item.get("chunks")
        if chunks is not None:
            if not isinstance(chunks, list):
                raise ValueError("chunks must be a list")
            expected_offset = 0
            for index, chunk in enumerate(chunks):
                if not isinstance(chunk, Mapping):
                    raise ValueError("chunk record must be an object")
                if int(chunk.get("index", -1)) != index:
                    raise ValueError("chunk indexes must be contiguous")
                if int(chunk.get("offset", -1)) != expected_offset:
                    raise ValueError("chunk offsets must be contiguous")
                size = int(chunk.get("size", -1))
                if size <= 0:
                    raise ValueError("chunk size must be positive")
                _hex_sha256(chunk.get("sha256"), "chunk sha256")
                expected_offset += size
            if expected_offset != int(item["size"]):
                raise ValueError("chunk sizes do not sum to entry size")
    descriptor = ArtifactDescriptor(
        1,
        artifact_type,
        root_sha256,
        total_bytes,
        entry_count,
        None if payload.get("media_type") is None else str(payload.get("media_type")),
        entries,
        None if payload.get("external") is None else dict(payload.get("external")),
    )
    if artifact_type == "external-reference":
        external = descriptor.external
        if not isinstance(external, dict):
            raise ValueError("external-reference requires external metadata")
        if _hex_sha256(external.get("sha256"), "external sha256") != root_sha256:
            raise ValueError("external reference digest does not match root_sha256")
        if not str(external.get("uri", "")).strip() or not str(external.get("version", "")).strip():
            raise ValueError("external reference requires uri and version")
        if entries or entry_count != 0:
            raise ValueError("external reference cannot contain local entries")
        external_size = external.get("size_bytes")
        if external_size is not None and int(external_size) != total_bytes:
            raise ValueError("external reference size does not match total_bytes")
    else:
        if len(entries) != entry_count:
            raise ValueError("entry_count does not match entries")
        if sum(int(item.get("size", 0)) for item in entries) != total_bytes:
            raise ValueError("total_bytes does not match entries")
    if path is not None:
        if artifact_type == "directory-tree":
            actual = describe_directory(path, media_type=descriptor.media_type)
        elif artifact_type in {"file", "chunked-file"}:
            actual = describe_file(
                path,
                media_type=descriptor.media_type,
                chunk_size=int(entries[0].get("chunk_size")) if artifact_type == "chunked-file" else None,
            )
        else:
            actual = descriptor
        if actual.root_sha256 != descriptor.root_sha256 or actual.entries != descriptor.entries:
            raise ValueError("artifact bytes do not match descriptor")
    return descriptor


def write_descriptor(path: Path, descriptor: ArtifactDescriptor) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(descriptor.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


class ContentAddressedStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.objects = root / "objects" / "sha256"

    def object_path(self, digest: str) -> Path:
        digest = _hex_sha256(digest, "digest")
        return self.objects / digest[:2] / digest[2:]

    def add_file(self, source: Path) -> tuple[str, Path]:
        digest, _size = stream_sha256(source)
        destination = self.object_path(digest)
        if destination.is_file():
            existing, _ = stream_sha256(destination)
            if existing != digest:
                raise ValueError("content-addressed store corruption")
            return digest, destination
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=".incoming-", dir=destination.parent)
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            shutil.copyfile(source, temporary)
            copied, _ = stream_sha256(temporary)
            if copied != digest:
                raise ValueError("copied object digest mismatch")
            temporary.chmod(0o444)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
        return digest, destination

    def verify(self, digest: str) -> bool:
        path = self.object_path(digest)
        if not path.is_file():
            return False
        actual, _ = stream_sha256(path)
        return actual == digest
