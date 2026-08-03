"""Record which verified Codex Science runtime wrote durable scientific state."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
RECEIPT_RE = re.compile(r"^[0-9a-f]{64}$")
VERSION_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z.+_-]{0,127}$")
MAX_RECEIPT_BYTES = 8 * 1024 * 1024
CRITICAL_PREFIXES = (
    ".codex-plugin/",
    "authored-skills/",
    "catalog/",
    "connectors/",
    "hooks/",
    "runtime-skills/",
    "scripts/",
    "skills/",
    "src/",
)
REQUIRED_IDENTITY_FILES = frozenset(
    {
        ".codex-plugin/plugin.json",
        ".mcp.json",
        "catalog/inventory.json",
        "release/manifest.json",
        "runtime-skills/codex-science/SKILL.md",
        "scripts/science_hook_dispatch.py",
        "scripts/science_mcp.py",
        "scripts/science_mcp_proxy.py",
        "scripts/science_runtime_state.py",
        "scripts/science_session_hook.py",
        "scripts/science_stop_hook.py",
        "src/codex_science/runtime_identity.py",
    }
)

def _safe_relative(value: str) -> bool:
    if not value or "\\" in value or "\0" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and all(
        part not in {"", ".", ".."} for part in path.parts
    )


def _sha256_file(path: Path) -> str | None:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            metadata = os.fstat(handle.fileno())
            if not stat.S_ISREG(metadata.st_mode):
                return None
            digest = hashlib.sha256()
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
            return digest.hexdigest()
    except OSError:
        return None


def _private_directory(path: Path, *, owner_only: bool = False) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    if path.is_symlink() or not stat.S_ISDIR(metadata.st_mode):
        return False
    if owner_only and metadata.st_mode & 0o077:
        return False
    return not hasattr(os, "getuid") or metadata.st_uid == os.getuid()


def _private_runtime_layout(root: Path) -> tuple[Path, Path] | None:
    """Return (resolved root, plugin data) only for the canonical private store."""

    try:
        resolved = root.resolve(strict=True)
    except OSError:
        return None
    cache = resolved.parent
    plugin_data = cache.parent
    if cache.name != "runtime-cache":
        return None
    if not _private_directory(cache, owner_only=True):
        return None
    if not _private_directory(resolved, owner_only=True):
        return None
    return resolved, plugin_data


def _receipt_path(plugin_data: Path, runtime_version: str) -> Path:
    key = hashlib.sha256(runtime_version.encode("utf-8")).hexdigest()
    return plugin_data / "runtime-receipts" / f"{key}.json"


def _read_private_receipt(path: Path) -> dict[str, Any] | None:
    if not _private_directory(path.parent, owner_only=True):
        return None
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            metadata = os.fstat(handle.fileno())
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_size > MAX_RECEIPT_BYTES
                or metadata.st_mode & 0o077
                or (hasattr(os, "getuid") and metadata.st_uid != os.getuid())
            ):
                return None
            payload = json.loads(handle.read(MAX_RECEIPT_BYTES + 1).decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _ignored_generated(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return "__pycache__" in parts and path.endswith((".pyc", ".pyo"))


def _verify_runtime_files(root: Path, files: dict[str, Any]) -> bool:
    for relative, expected in files.items():
        if (
            not isinstance(relative, str)
            or not _safe_relative(relative)
            or not isinstance(expected, str)
        ):
            return False
        path = root / relative
        try:
            metadata = path.lstat()
            if expected.startswith("link:"):
                if (
                    not stat.S_ISLNK(metadata.st_mode)
                    or f"link:{os.readlink(path)}" != expected
                    or relative == ".mcp.json"
                    or any(relative.startswith(prefix) for prefix in CRITICAL_PREFIXES)
                ):
                    return False
            elif not stat.S_ISREG(metadata.st_mode) or _sha256_file(path) != expected:
                return False
        except OSError:
            return False

    expected_paths = set(files)
    for prefix in CRITICAL_PREFIXES:
        directory = root / prefix.rstrip("/")
        try:
            metadata = directory.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            return False
        if directory.is_symlink() or not stat.S_ISDIR(metadata.st_mode):
            return False
        try:
            for current, directories, names in os.walk(directory, followlinks=False):
                base = Path(current)
                directories[:] = sorted(directories)
                if any((base / name).is_symlink() for name in directories):
                    return False
                for name in names:
                    relative = (base / name).relative_to(root).as_posix()
                    if relative not in expected_paths and not _ignored_generated(relative):
                        return False
        except OSError:
            return False
    return True


def _verified_private_identity(root: Path) -> dict[str, str] | None:
    layout = _private_runtime_layout(root)
    if layout is None:
        return None
    resolved, plugin_data = layout
    version = _runtime_version(resolved)
    if version == "unversioned" or resolved.name != version:
        return None
    receipt = _read_private_receipt(_receipt_path(plugin_data, version))
    if receipt is None:
        return None
    recorded_digest = receipt.pop("receipt_sha256", None)
    actual_digest = hashlib.sha256(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    commit = receipt.get("runtime_commit")
    files = receipt.get("files")
    if (
        receipt.get("schema_version") != 2
        or receipt.get("runtime_version") != version
        or not isinstance(commit, str)
        or COMMIT_RE.fullmatch(commit) is None
        or not isinstance(recorded_digest, str)
        or RECEIPT_RE.fullmatch(recorded_digest) is None
        or recorded_digest != actual_digest
        or not isinstance(receipt.get("bootstrap_version"), str)
        or VERSION_RE.fullmatch(receipt["bootstrap_version"]) is None
        or not isinstance(receipt.get("bootstrap_sha256"), str)
        or RECEIPT_RE.fullmatch(receipt["bootstrap_sha256"]) is None
        or not isinstance(files, dict)
        or not REQUIRED_IDENTITY_FILES.issubset(files)
        or not _verify_runtime_files(resolved, files)
    ):
        return None
    return {
        "commit": commit,
        "receipt_sha256": recorded_digest,
        "runtime_version": version,
    }


def _runtime_version(root: Path) -> str:
    try:
        payload = json.loads(
            (root / "release" / "manifest.json").read_text(encoding="utf-8")
        )
        # Schema-v1 releases used the host plugin cachebuster as runtime identity.
        value = (
            payload.get("runtime_version", payload.get("plugin_version"))
            if isinstance(payload, dict)
            else None
        )
        if isinstance(value, str) and VERSION_RE.fullmatch(value) is not None:
            return value
    except (OSError, UnicodeError, json.JSONDecodeError):
        pass
    try:
        payload = json.loads(
            (root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        value = payload.get("version") if isinstance(payload, dict) else None
        if isinstance(value, str) and VERSION_RE.fullmatch(value) is not None:
            return value
    except (OSError, UnicodeError, json.JSONDecodeError):
        pass
    return "unversioned"


@lru_cache(maxsize=1)
def current_runtime_identity() -> dict[str, str]:
    """Return a verified private pin, or an explicit development identity.

    Runtime pin environment variables are transport hints rather than a trust
    root.  A direct CLI process does not inherit the hook child's environment,
    while callers can freely forge their own environment.  Recover private
    runtime identity from the canonical receipt store and exact cached bytes.
    """

    verified = _verified_private_identity(ROOT)
    if verified is not None:
        version = verified["runtime_version"]
        commit = verified["commit"]
        receipt = verified["receipt_sha256"]
    else:
        if _private_runtime_layout(ROOT) is not None:
            raise RuntimeError("private Codex Science runtime identity is not verified")
        version = _runtime_version(ROOT)
        commit = ""
        receipt = ""
    try:
        if not commit:
            result = subprocess.run(
                ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            candidate = result.stdout.strip().lower()
            if result.returncode == 0 and COMMIT_RE.fullmatch(candidate):
                commit = candidate
    except (OSError, subprocess.TimeoutExpired):
        pass
    if not commit:
        commit = "cache:" + version
    source_id = hashlib.sha256(str(ROOT.resolve()).encode("utf-8")).hexdigest()[:16]
    return {
        "commit": commit,
        "receipt_sha256": receipt,
        "runtime_version": version,
        "source_id": source_id,
    }


def _identity_values(item: dict[str, Any]) -> tuple[str, str, str, str]:
    def text(value: object) -> str:
        return value.strip() if isinstance(value, str) else ""

    commit = text(item.get("commit"))
    version_value = item.get("runtime_version")
    if version_value is None:
        version_value = item.get("plugin_version")
    version = text(version_value)
    receipt = text(item.get("receipt_sha256"))
    source_id = text(item.get("source_id"))
    return commit, version, receipt, source_id


def record_runtime_identity(record: dict[str, Any]) -> None:
    """Append the current identity once and derive an explicit span flag."""
    identity = current_runtime_identity()
    history = record.setdefault("runtime_history", [])
    if not isinstance(history, list):
        raise ValueError("runtime_history must be a list")
    key = _identity_values(identity)
    observed = {
        _identity_values(item)
        for item in history
        if isinstance(item, dict)
    }
    if key not in observed:
        history.append(identity)
        observed.add(key)
    releases = {
        (commit, version, receipt)
        for commit, version, receipt, _source_id in observed
    }
    record["runtime_span"] = len(releases) > 1


def validate_runtime_history(record: dict[str, Any]) -> None:
    history = record.get("runtime_history")
    span = record.get("runtime_span")
    if history is None and span is None:
        return
    if not isinstance(history, list) or not history:
        raise ValueError("runtime_history must be a non-empty list")
    identities: set[tuple[str, str, str, str]] = set()
    for item in history:
        if not isinstance(item, dict):
            raise ValueError("runtime_history entries must be objects")
        values = _identity_values(item)
        commit, version, receipt, source_id = values
        if not commit or not version or not source_id:
            raise ValueError(
                "runtime_history entries require commit, runtime_version, and source_id"
            )
        if VERSION_RE.fullmatch(version) is None:
            raise ValueError("runtime_history runtime versions must be valid")
        if receipt and RECEIPT_RE.fullmatch(receipt) is None:
            raise ValueError("runtime_history receipt digests must be valid")
        identities.add(values)
    releases = {
        (commit, version, receipt)
        for commit, version, receipt, _source_id in identities
    }
    if not isinstance(span, bool) or span != (len(releases) > 1):
        raise ValueError("runtime_span must match the recorded runtime identities")
