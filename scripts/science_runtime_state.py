#!/usr/bin/env python3
"""Private runtime-pin and immutable-store verification helpers.

This module is part of the small host-loaded bootstrap.  It intentionally uses
only the Python standard library so an old Codex task can verify and dispatch a
newer registered runtime without importing code from the mutable managed
checkout first.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterator, Mapping


PLUGIN_NAME = "codex-science"
MARKETPLACE_NAME = "codex-science"
PLUGIN_DATA_DIRECTORY = f"{PLUGIN_NAME}-{MARKETPLACE_NAME}"
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
VERSION_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z.+_-]{0,127}$")
SESSION_FILE_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_MARKER_BYTES = 4096
MAX_RECEIPT_BYTES = 8 * 1024 * 1024
PIN_TTL_SECONDS = 180 * 24 * 60 * 60
RUNTIME_LOCK_TIMEOUT_SECONDS = 130.0
OFFICIAL_REMOTES = frozenset(
    {
        "https://github.com/eightmm/codex-science.git",
        "https://github.com/eightmm/codex-science",
        "git@github.com:eightmm/codex-science.git",
        "ssh://git@github.com/eightmm/codex-science.git",
    }
)
REQUIRED_RUNTIME_FILES = (
    ".codex-plugin/plugin.json",
    ".mcp.json",
    "release/manifest.json",
    "scripts/science_hook_dispatch.py",
    "scripts/science_mcp.py",
    "scripts/science_mcp_proxy.py",
    "scripts/science_runtime_state.py",
    "scripts/science_session_hook.py",
    "scripts/science_stop_hook.py",
    "runtime-skills/codex-science/SKILL.md",
    "catalog/inventory.json",
)
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
POLICY_PATHS = frozenset(
    {
        "release/manifest.json",
        "scripts/science_runtime_state.py",
        "scripts/science_update_hook.py",
        "scripts/validate_release.py",
        "src/codex_science/release.py",
        "src/codex_science/version.py",
    }
)
RUNTIME_CONSUMED_PREFIXES = ("docs/", "examples/")
BOOTSTRAP_FILES = frozenset(
    {
        ".agents/plugins/marketplace.json",
        ".mcp.json",
        "scripts/python_runtime.sh",
        "scripts/science_hook_dispatch.py",
        "scripts/science_mcp_proxy.py",
        "scripts/science_runtime_state.py",
        "scripts/science_update_entry.py",
        "scripts/science_update_hook.py",
    }
)
BOOTSTRAP_PREFIXES = (".codex-plugin/", "hooks/", "skills/")


@dataclass(frozen=True)
class RuntimePin:
    runtime_version: str
    runtime_commit: str
    receipt_sha256: str

    def as_dict(self) -> dict[str, str]:
        return {
            "runtime_version": self.runtime_version,
            "runtime_commit": self.runtime_commit,
            "receipt_sha256": self.receipt_sha256,
        }


@dataclass(frozen=True)
class ActivationRecord:
    generation: str
    runtime_pin: RuntimePin | None


@dataclass(frozen=True)
class VerifiedRuntime:
    root: Path
    pin: RuntimePin


def codex_home(environment: Mapping[str, str]) -> Path:
    return Path(environment.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()


def canonical_plugin_data(environment: Mapping[str, str]) -> Path:
    """Return the PluginStore data path used by bundled MCP servers.

    Codex injects ``PLUGIN_DATA`` into hooks but not into plugin MCP processes.
    ``CODEX_SCIENCE_PLUGIN_DATA`` is therefore an explicit test/development
    override; production MCP resolution follows Codex's PluginStore naming
    rule under ``CODEX_HOME``.
    """

    override = environment.get("CODEX_SCIENCE_PLUGIN_DATA")
    if override:
        return Path(override).expanduser()
    return codex_home(environment) / "plugins" / "data" / PLUGIN_DATA_DIRECTORY


def hook_plugin_data(environment: Mapping[str, str]) -> Path | None:
    value = environment.get("PLUGIN_DATA") or environment.get("CLAUDE_PLUGIN_DATA")
    return Path(value).expanduser() if value else None


def runtime_store_root(plugin_data: Path) -> Path:
    """Return the project-owned store that Codex's PluginStore never prunes."""

    return Path(plugin_data) / "runtime-cache"


def session_key(session_id: str) -> str:
    if not isinstance(session_id, str) or not session_id:
        raise ValueError("session id must be non-empty")
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()


def activation_path(plugin_data: Path, session_id: str) -> Path:
    return Path(plugin_data) / "science-sessions" / session_key(session_id)


def _runtime_pin(value: object) -> RuntimePin | None:
    if not isinstance(value, dict):
        return None
    version = value.get("runtime_version")
    commit = value.get("runtime_commit")
    receipt = value.get("receipt_sha256")
    if (
        not isinstance(version, str)
        or VERSION_RE.fullmatch(version) is None
        or not isinstance(commit, str)
        or COMMIT_RE.fullmatch(commit) is None
        or not isinstance(receipt, str)
        or DIGEST_RE.fullmatch(receipt) is None
    ):
        return None
    return RuntimePin(version, commit, receipt)


def read_activation_record(
    path: Path,
    *,
    refresh: bool = False,
    now: float | None = None,
) -> ActivationRecord | None:
    """Read schema-v1/v2 state without following links or exposing session ids."""

    status, record = inspect_activation_record(path, now=now)
    if status != "valid" or record is None:
        return None
    if refresh:
        try:
            os.utime(path, None, follow_symlinks=False)
        except OSError:
            return None
    return record


def inspect_activation_record(
    path: Path, *, now: float | None = None
) -> tuple[str, ActivationRecord | None]:
    """Distinguish missing, expired, and corrupt state for fail-closed callers."""

    try:
        metadata = path.lstat()
        current = time.time() if now is None else now
        if (
            path.is_symlink()
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_size > MAX_MARKER_BYTES
        ):
            return "invalid", None
        payload = json.loads(path.read_text(encoding="utf-8"))
        generation = payload.get("generation") if isinstance(payload, dict) else None
        if not isinstance(generation, str) or DIGEST_RE.fullmatch(generation) is None:
            return "invalid", None
        schema = payload.get("schema_version", 1)
        pin = _runtime_pin(payload.get("runtime_pin")) if schema == 2 else None
        if schema not in {1, 2} or (schema == 2 and pin is None):
            return "invalid", None
        record = ActivationRecord(generation, pin)
        if metadata.st_mtime < current - PIN_TTL_SECONDS:
            return "expired", record
        return "valid", record
    except FileNotFoundError:
        return "missing", None
    except (PermissionError, OSError, UnicodeError, json.JSONDecodeError):
        return "invalid", None


def receipt_path(plugin_data: Path, runtime_version: str) -> Path:
    if VERSION_RE.fullmatch(runtime_version) is None:
        raise ValueError("invalid runtime version")
    key = hashlib.sha256(runtime_version.encode("utf-8")).hexdigest()
    return Path(plugin_data) / "runtime-receipts" / f"{key}.json"


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    metadata = path.parent.lstat()
    if path.parent.is_symlink() or not stat.S_ISDIR(metadata.st_mode):
        raise OSError("runtime state directory is not private regular storage")
    path.parent.chmod(0o700)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o600)
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_activation_record(path: Path, record: ActivationRecord) -> None:
    if (
        DIGEST_RE.fullmatch(record.generation) is None
        or record.runtime_pin is None
        or _runtime_pin(record.runtime_pin.as_dict()) != record.runtime_pin
    ):
        raise ValueError("a pinned activation record is required")
    _atomic_json(
        path,
        {
            "schema_version": 2,
            "generation": record.generation,
            "runtime_pin": record.runtime_pin.as_dict(),
        },
    )


@contextmanager
def _flock(path: Path, operation: int, timeout: float) -> Iterator[None]:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    metadata = path.parent.lstat()
    if path.parent.is_symlink() or not stat.S_ISDIR(metadata.st_mode):
        raise OSError("runtime state directory is not private regular storage")
    path.parent.chmod(0o700)
    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    os.fchmod(descriptor, 0o600)
    handle = os.fdopen(descriptor, "r+")
    deadline = time.monotonic() + max(timeout, 0.0)
    try:
        while True:
            try:
                fcntl.flock(handle, operation | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"timed out waiting for runtime lock: {path}")
                time.sleep(0.05)
        yield
    finally:
        try:
            fcntl.flock(handle, fcntl.LOCK_UN)
        finally:
            handle.close()


@contextmanager
def activation_lock(path: Path, *, timeout: float = 10.0) -> Iterator[None]:
    with _flock(path.with_name(f".{path.name}.lock"), fcntl.LOCK_EX, timeout):
        yield


@contextmanager
def runtime_cache_lock(
    environment: Mapping[str, str],
    *,
    plugin_data: Path | None = None,
    exclusive: bool = False,
    timeout: float = RUNTIME_LOCK_TIMEOUT_SECONDS,
) -> Iterator[None]:
    path = (plugin_data or canonical_plugin_data(environment)) / "runtime-cache.lock"
    operation = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
    with _flock(path, operation, timeout):
        yield


def attach_runtime_pin(path: Path, generation: str, pin: RuntimePin) -> bool:
    """CAS-upgrade a legacy activation while preserving its generation."""

    with activation_lock(path):
        current = read_activation_record(path)
        if current is None or current.generation != generation:
            return False
        if current.runtime_pin is not None:
            return current.runtime_pin == pin
        write_activation_record(path, ActivationRecord(generation, pin))
        return True


def claim_runtime_activation(path: Path, pin: RuntimePin) -> ActivationRecord:
    """Atomically claim a pinned generation or return the concurrent winner."""

    if _runtime_pin(pin.as_dict()) != pin:
        raise ValueError("invalid runtime pin")
    with activation_lock(path):
        status, current = inspect_activation_record(path)
        if status == "valid" and current is not None:
            if current.runtime_pin is None:
                current = ActivationRecord(current.generation, pin)
                write_activation_record(path, current)
            return current
        if status == "invalid":
            raise ValueError("existing activation marker is invalid")
        if status == "expired" and current is not None:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        state = ActivationRecord(secrets.token_hex(32), pin)
        write_activation_record(path, state)
        return state


def remove_activation_record(path: Path, expected_generation: str) -> bool:
    if DIGEST_RE.fullmatch(expected_generation) is None:
        return False
    with activation_lock(path):
        status, current = inspect_activation_record(path)
        if status not in {"valid", "expired"} or current is None:
            return False
        if current.generation != expected_generation:
            return False
        try:
            path.unlink()
        except FileNotFoundError:
            return False
        return True


def _run_git(root: Path, *arguments: str, timeout: int = 30) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *arguments],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout if result.returncode == 0 else None


def _safe_relative(value: str) -> bool:
    if not value or "\\" in value or "\0" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_manifest(path: Path) -> dict[str, str] | None:
    manifest: dict[str, str] = {}
    try:
        for current, directories, files in os.walk(path, followlinks=False):
            base = Path(current)
            directories[:] = sorted(directories)
            for name in sorted(files):
                item = base / name
                relative = item.relative_to(path).as_posix()
                metadata = item.lstat()
                if stat.S_ISLNK(metadata.st_mode):
                    manifest[relative] = f"link:{os.readlink(item)}"
                elif stat.S_ISREG(metadata.st_mode):
                    manifest[relative] = _sha256_file(item)
                else:
                    return None
    except OSError:
        return None
    return manifest


def _bootstrap_digest(root: Path) -> str | None:
    selected: dict[str, str] = {}
    try:
        for relative in sorted(BOOTSTRAP_FILES):
            path = root / relative
            metadata = path.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                selected[relative] = f"link:{os.readlink(path)}"
            elif stat.S_ISREG(metadata.st_mode):
                selected[relative] = _sha256_file(path)
            else:
                return None
        for prefix in BOOTSTRAP_PREFIXES:
            directory = root / prefix.rstrip("/")
            metadata = directory.lstat()
            if directory.is_symlink() or not stat.S_ISDIR(metadata.st_mode):
                return None
            for current, directories, files in os.walk(directory, followlinks=False):
                base = Path(current)
                directories[:] = sorted(
                    name for name in directories if name != "__pycache__"
                )
                for name in sorted(files):
                    path = base / name
                    relative = path.relative_to(root).as_posix()
                    if _ignored_generated(relative):
                        continue
                    item_metadata = path.lstat()
                    if stat.S_ISLNK(item_metadata.st_mode):
                        selected[relative] = f"link:{os.readlink(path)}"
                    elif stat.S_ISREG(item_metadata.st_mode):
                        selected[relative] = _sha256_file(path)
                    else:
                        return None
                if any((base / name).is_symlink() for name in directories):
                    return None
    except OSError:
        return None
    return _manifest_digest(selected)


def tracked_manifest(root: Path) -> dict[str, str] | None:
    listed = _run_git(root, "ls-files", "--recurse-submodules", "-z")
    if listed is None:
        return None
    manifest: dict[str, str] = {}
    try:
        for relative in listed.split("\0"):
            if not relative:
                continue
            if not _safe_relative(relative):
                return None
            path = root / relative
            metadata = path.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                manifest[relative] = f"link:{os.readlink(path)}"
            elif stat.S_ISREG(metadata.st_mode):
                manifest[relative] = _sha256_file(path)
            else:
                return None
    except OSError:
        return None
    return manifest


def _runtime_version(root: Path) -> str | None:
    try:
        payload = json.loads(
            (root / "release" / "manifest.json").read_text(encoding="utf-8")
        )
        # Schema-v1 releases used the host plugin cachebuster as runtime identity.
        version = payload.get("runtime_version", payload.get("plugin_version"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return version if isinstance(version, str) and VERSION_RE.fullmatch(version) else None


def _plugin_version(root: Path) -> str | None:
    try:
        payload = json.loads(
            (root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        version = payload.get("version")
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return version if isinstance(version, str) and VERSION_RE.fullmatch(version) else None


def _host_bootstrap_version(environment: Mapping[str, str]) -> str | None:
    explicit = environment.get("CODEX_SCIENCE_BOOTSTRAP_VERSION")
    if isinstance(explicit, str) and VERSION_RE.fullmatch(explicit):
        return explicit
    root = environment.get("PLUGIN_ROOT")
    return _plugin_version(Path(root).expanduser()) if root else None


def _source_matches_host_bootstrap(
    source: Path, environment: Mapping[str, str]
) -> bool:
    host = _host_bootstrap_version(environment)
    return host is None or _plugin_version(source) == host


def _manifest_digest(files: Mapping[str, str]) -> str:
    encoded = json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _critical_extra(path: str) -> bool:
    return path == ".mcp.json" or any(path.startswith(prefix) for prefix in CRITICAL_PREFIXES)


def _ignored_generated(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return "__pycache__" in parts and path.endswith((".pyc", ".pyo"))


def _verify_manifest(root: Path, files: Mapping[str, str]) -> bool:
    for relative, expected in files.items():
        if not _safe_relative(relative) or not isinstance(expected, str):
            return False
        path = root / relative
        try:
            metadata = path.lstat()
            if expected.startswith("link:"):
                if not stat.S_ISLNK(metadata.st_mode) or f"link:{os.readlink(path)}" != expected:
                    return False
                if _critical_extra(relative):
                    return False
            elif not stat.S_ISREG(metadata.st_mode) or _sha256_file(path) != expected:
                return False
        except OSError:
            return False

    expected_paths = set(files)
    for prefix in CRITICAL_PREFIXES:
        directory = root / prefix.rstrip("/")
        try:
            directory_metadata = directory.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            return False
        if directory.is_symlink() or not stat.S_ISDIR(directory_metadata.st_mode):
            return False
        try:
            for current, directories, names in os.walk(directory, followlinks=False):
                base = Path(current)
                directories[:] = sorted(directories)
                for name in names:
                    relative = (base / name).relative_to(root).as_posix()
                    if relative not in expected_paths and not _ignored_generated(relative):
                        return False
                for name in tuple(directories):
                    item = base / name
                    if item.is_symlink():
                        return False
        except OSError:
            return False
    return True


def _copy_manifest(source: Path, destination: Path, files: Mapping[str, str]) -> bool:
    try:
        for relative in sorted(files):
            source_path = source / relative
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            metadata = source_path.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                os.symlink(os.readlink(source_path), target)
            elif stat.S_ISREG(metadata.st_mode):
                shutil.copy2(source_path, target, follow_symlinks=False)
            else:
                return False
    except OSError:
        return False
    return _verify_manifest(destination, files)


def _neutral_policy(root: Path) -> tuple[frozenset[str], tuple[str, ...]] | None:
    try:
        payload = json.loads((root / "release" / "manifest.json").read_text(encoding="utf-8"))
        files = payload.get("cache_neutral_files")
        prefixes = payload.get("cache_neutral_prefixes")
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(files, list) or not isinstance(prefixes, list):
        return None
    file_set: set[str] = set()
    prefix_values: list[str] = []
    for value in files:
        if (
            not isinstance(value, str)
            or not _safe_relative(value)
            or value.endswith("/")
        ):
            return None
        file_set.add(value)
    for value in prefixes:
        if (
            not isinstance(value, str)
            or not value.endswith("/")
            or not _safe_relative(value[:-1])
        ):
            return None
        prefix_values.append(value)
    return frozenset(file_set), tuple(prefix_values)


def _neutral(path: str, policy: tuple[frozenset[str], tuple[str, ...]]) -> bool:
    files, prefixes = policy
    return (
        path not in POLICY_PATHS
        and not any(path.startswith(prefix) for prefix in RUNTIME_CONSUMED_PREFIXES)
        and (
        path in files or any(path.startswith(prefix) for prefix in prefixes)
        )
    )


def _runtime_equivalent(
    source: Path,
    source_files: Mapping[str, str],
    target: Path,
    target_files: Mapping[str, str],
) -> bool:
    source_policy = _neutral_policy(source)
    target_policy = _neutral_policy(target)
    if source_policy is None or target_policy is None:
        return False
    for path in set(source_files) | set(target_files):
        if _neutral(path, source_policy) and _neutral(path, target_policy):
            continue
        if source_files.get(path) != target_files.get(path):
            return False
    return True


def _exact_runtime_root(
    plugin_data: Path, runtime_version: str
) -> Path | None:
    if VERSION_RE.fullmatch(runtime_version) is None:
        return None
    parent = runtime_store_root(plugin_data)
    candidate = parent / runtime_version
    try:
        parent_metadata = parent.lstat()
        candidate_metadata = candidate.lstat()
        if (
            parent.is_symlink()
            or not stat.S_ISDIR(parent_metadata.st_mode)
            or candidate.is_symlink()
            or not stat.S_ISDIR(candidate_metadata.st_mode)
        ):
            return None
        resolved_parent = parent.resolve(strict=True)
        resolved = candidate.resolve(strict=True)
        if resolved.parent != resolved_parent or resolved.name != runtime_version:
            return None
    except OSError:
        return None
    return resolved


def write_runtime_receipt(
    source: Path,
    environment: Mapping[str, str],
    *,
    plugin_data: Path | None = None,
) -> RuntimePin | None:
    """Verify an immutable runtime copy against trusted git content and issue a receipt."""

    source = source.expanduser().resolve()
    data = plugin_data or canonical_plugin_data(environment)
    version = _runtime_version(source)
    bootstrap_version = _plugin_version(source)
    bootstrap_digest = _bootstrap_digest(source)
    cache = _exact_runtime_root(data, version or "")
    if (
        version is None
        or bootstrap_version is None
        or bootstrap_digest is None
        or cache is None
        or not _source_matches_host_bootstrap(source, environment)
    ):
        return None
    remote = (_run_git(source, "remote", "get-url", "origin") or "").strip().rstrip("/")
    head = (_run_git(source, "rev-parse", "HEAD") or "").strip().lower()
    dirty = _run_git(source, "status", "--porcelain", "--untracked-files=no")
    if remote not in OFFICIAL_REMOTES or COMMIT_RE.fullmatch(head) is None or dirty != "":
        return None
    files = tracked_manifest(source)
    if files is None or not _verify_manifest(cache, files):
        return None
    if _runtime_version(cache) != version:
        return None
    receipt = {
        "schema_version": 2,
        "bootstrap_version": bootstrap_version,
        "bootstrap_sha256": bootstrap_digest,
        "runtime_version": version,
        "runtime_commit": head,
        "files": files,
    }
    receipt_digest = hashlib.sha256(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    receipt["receipt_sha256"] = receipt_digest
    _atomic_json(receipt_path(data, version), receipt)
    return RuntimePin(version, head, receipt_digest)


def _read_receipt(path: Path) -> dict[str, Any] | None:
    try:
        metadata = path.lstat()
        if (
            path.is_symlink()
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_size > MAX_RECEIPT_BYTES
        ):
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _repair_pin_for_staging(
    source: Path,
    staging: Path,
    receipt: Mapping[str, Any],
    *,
    version: str,
    head: str,
) -> RuntimePin | None:
    """Accept repair bytes only when they exactly reproduce a signed receipt."""

    payload = dict(receipt)
    recorded_digest = payload.pop("receipt_sha256", None)
    actual_digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    pin = _runtime_pin(receipt)
    files = receipt.get("files")
    if (
        pin is None
        or recorded_digest != actual_digest
        or pin.receipt_sha256 != actual_digest
        or receipt.get("schema_version") != 2
        or pin.runtime_version != version
        or pin.runtime_commit != head
        or receipt.get("bootstrap_version") != _plugin_version(source)
        or receipt.get("bootstrap_sha256") != _bootstrap_digest(source)
        or not isinstance(files, dict)
        or _runtime_version(staging) != version
        or not _verify_manifest(staging, files)
    ):
        return None
    return pin


def verify_runtime_pin(
    pin: RuntimePin,
    environment: Mapping[str, str],
    *,
    plugin_data: Path | None = None,
) -> VerifiedRuntime | None:
    data = plugin_data or canonical_plugin_data(environment)
    receipt = _read_receipt(receipt_path(data, pin.runtime_version))
    if receipt is None:
        return None
    recorded_digest = receipt.pop("receipt_sha256", None)
    actual_digest = hashlib.sha256(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if recorded_digest != actual_digest or actual_digest != pin.receipt_sha256:
        return None
    if (
        receipt.get("schema_version") != 2
        or not isinstance(receipt.get("bootstrap_version"), str)
        or not isinstance(receipt.get("bootstrap_sha256"), str)
        or DIGEST_RE.fullmatch(receipt.get("bootstrap_sha256", "")) is None
        or receipt.get("runtime_version") != pin.runtime_version
        or receipt.get("runtime_commit") != pin.runtime_commit
        or not isinstance(receipt.get("files"), dict)
    ):
        return None
    host_bootstrap = _host_bootstrap_version(environment)
    if (
        host_bootstrap is not None
        and receipt.get("bootstrap_version") != host_bootstrap
    ):
        return None
    host_root = environment.get("PLUGIN_ROOT")
    if host_root and _bootstrap_digest(Path(host_root).expanduser()) != receipt.get(
        "bootstrap_sha256"
    ):
        return None
    cache = _exact_runtime_root(data, pin.runtime_version)
    if cache is None or _runtime_version(cache) != pin.runtime_version:
        return None
    if any(not (cache / relative).is_file() for relative in REQUIRED_RUNTIME_FILES):
        return None
    files = receipt["files"]
    if not all(
        isinstance(path, str) and isinstance(digest, str)
        for path, digest in files.items()
    ):
        return None
    if not _verify_manifest(cache, files):
        return None
    return VerifiedRuntime(cache, pin)


def ensure_runtime(
    source: Path,
    environment: Mapping[str, str],
    *,
    plugin_data: Path,
    allow_create: bool = True,
) -> VerifiedRuntime | None:
    """Resolve an immutable runtime, optionally issuing a receipt for trusted input."""

    version = _runtime_version(source)
    if version is None or not _source_matches_host_bootstrap(source, environment):
        return None
    existing = _read_receipt(receipt_path(plugin_data, version))
    if isinstance(existing, dict):
        pin = _runtime_pin(existing)
        # Receipts store the same three public identity fields at top level.
        if pin is not None:
            verified = verify_runtime_pin(pin, environment, plugin_data=plugin_data)
            if verified is not None:
                return verified
    if not allow_create:
        return None
    pin = write_runtime_receipt(source, environment, plugin_data=plugin_data)
    return (
        verify_runtime_pin(pin, environment, plugin_data=plugin_data)
        if pin is not None
        else None
    )


def install_runtime_append_only(
    source: Path,
    environment: Mapping[str, str],
    *,
    plugin_data: Path | None = None,
    repair_existing: bool = False,
) -> tuple[VerifiedRuntime | None, str]:
    """Atomically add a runtime, optionally repairing exact receipted bytes."""

    source = source.expanduser().resolve()
    version = _runtime_version(source)
    remote = (_run_git(source, "remote", "get-url", "origin") or "").strip().rstrip("/")
    head = (_run_git(source, "rev-parse", "HEAD") or "").strip().lower()
    dirty = _run_git(source, "status", "--porcelain", "--untracked-files=no")
    files = tracked_manifest(source)
    if (
        version is None
        or remote not in OFFICIAL_REMOTES
        or COMMIT_RE.fullmatch(head) is None
        or dirty != ""
        or files is None
    ):
        return None, "plugin source is not a clean official checkout"
    data = plugin_data or canonical_plugin_data(environment)
    cache_parent = runtime_store_root(data)
    try:
        cache_parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        metadata = cache_parent.lstat()
        if cache_parent.is_symlink() or not stat.S_ISDIR(metadata.st_mode):
            return None, "runtime store root is not a regular directory"
        staging = Path(tempfile.mkdtemp(prefix=f".{version}.", dir=cache_parent))
    except OSError as error:
        return None, f"could not stage runtime: {error}"
    target = cache_parent / version
    created = False
    try:
        if not _copy_manifest(source, staging, files) or _runtime_version(staging) != version:
            return None, "staged runtime verification failed"
        with runtime_cache_lock(environment, plugin_data=data, exclusive=True):
            if target.exists() or target.is_symlink():
                if target.is_symlink() or not target.is_dir():
                    return None, "runtime version path is unsafe"
                receipt_file = receipt_path(data, version)
                receipt_existed = os.path.lexists(receipt_file)
                receipt = _read_receipt(receipt_file) if receipt_existed else None
                existing = ensure_runtime(
                    target,
                    environment,
                    plugin_data=data,
                    allow_create=False,
                )
                if existing is None:
                    # A process can be killed after the cache directory becomes
                    # visible but before its receipt is committed. Repair only
                    # when the trusted source exactly verifies that directory;
                    # never guess an identity for different same-version bytes.
                    pin = write_runtime_receipt(source, environment, plugin_data=data)
                    existing = (
                        verify_runtime_pin(pin, environment, plugin_data=data)
                        if pin is not None
                        else None
                    )
                if (
                    existing is None
                    and receipt_existed
                    and repair_existing
                    and isinstance(receipt, dict)
                ):
                    repair_pin = _repair_pin_for_staging(
                        source,
                        staging,
                        receipt,
                        version=version,
                        head=head,
                    )
                    if repair_pin is not None:
                        quarantine = cache_parent / (
                            f".{version}.corrupt.{secrets.token_hex(8)}"
                        )
                        os.replace(target, quarantine)
                        _fsync_directory(cache_parent)
                        try:
                            os.replace(staging, target)
                            _fsync_directory(cache_parent)
                            existing = verify_runtime_pin(
                                repair_pin,
                                environment,
                                plugin_data=data,
                            )
                            if existing is None:
                                raise OSError("repaired runtime did not verify")
                        except OSError:
                            if target.exists() and not target.is_symlink():
                                shutil.rmtree(target, ignore_errors=True)
                            os.replace(quarantine, target)
                            _fsync_directory(cache_parent)
                            raise
                        shutil.rmtree(quarantine, ignore_errors=True)
                        _fsync_directory(cache_parent)
                        return existing, "runtime repaired from exact official receipt bytes"
                if existing is None and not receipt_existed:
                    # An unreceipted target is never selectable. If main moved
                    # by cache-neutral bytes after a crash, replace that orphan
                    # with the already verified staging tree so retries do not
                    # wedge forever.
                    shutil.rmtree(target)
                    os.replace(staging, target)
                    _fsync_directory(cache_parent)
                    created = True
                    pin = write_runtime_receipt(source, environment, plugin_data=data)
                    existing = (
                        verify_runtime_pin(pin, environment, plugin_data=data)
                        if pin is not None
                        else None
                    )
                if existing is None:
                    return None, "existing runtime version has no valid receipt"
                receipt = _read_receipt(receipt_path(data, version))
                target_files = receipt.get("files") if isinstance(receipt, dict) else None
                if not isinstance(target_files, dict) or not _runtime_equivalent(
                    source, files, target, target_files
                ):
                    return None, "existing runtime version has different runtime content"
                return existing, "runtime already present"
            os.replace(staging, target)
            _fsync_directory(cache_parent)
            created = True
            pin = write_runtime_receipt(source, environment, plugin_data=data)
            verified = (
                verify_runtime_pin(pin, environment, plugin_data=data)
                if pin is not None
                else None
            )
            if verified is None:
                shutil.rmtree(target, ignore_errors=True)
                created = False
                return None, "runtime receipt verification failed"
            return verified, "runtime added"
    except (OSError, TimeoutError) as error:
        if created:
            shutil.rmtree(target, ignore_errors=True)
        return None, f"could not install runtime: {error}"
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def read_pinned_runtime(
    plugin_data: Path,
    session_id: str,
    environment: Mapping[str, str],
    *,
    refresh: bool = False,
) -> tuple[ActivationRecord, VerifiedRuntime] | None:
    record = read_activation_record(
        activation_path(plugin_data, session_id), refresh=refresh
    )
    if record is None or record.runtime_pin is None:
        return None
    verified = verify_runtime_pin(record.runtime_pin, environment, plugin_data=plugin_data)
    return (record, verified) if verified is not None else None
