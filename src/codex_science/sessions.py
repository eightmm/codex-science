"""Session-scoped identifiers shared by Codex Science hooks."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import stat
import fcntl
import tempfile
import time
from dataclasses import dataclass
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Mapping


GENERATION_PATTERN = re.compile(r"^[0-9a-f]{64}$")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
VERSION_PATTERN = re.compile(r"^[0-9A-Za-z][0-9A-Za-z.+_-]{0,127}$")
MAX_MARKER_BYTES = 4096


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
class ActivationState:
    generation: str
    runtime_pin: RuntimePin | None = None


def session_key(session_id: str, generation: str | None = None) -> str:
    """Return a non-reversible task or activation-generation owner key."""
    if not session_id:
        raise ValueError("session_id must be non-empty")
    if generation is None:
        payload = session_id.encode("utf-8")
    else:
        if not GENERATION_PATTERN.fullmatch(generation):
            raise ValueError("generation must be a 64-character lowercase hex token")
        payload = session_id.encode("utf-8") + b"\0" + generation.encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def new_activation_generation() -> str:
    """Create an unguessable generation without persisting the raw session id."""
    return secrets.token_hex(32)


def activation_path(plugin_data: Path, session_id: str) -> Path:
    """Return the private activation marker path for one Codex task."""
    return Path(plugin_data) / "science-sessions" / session_key(session_id)


def _runtime_pin(value: object) -> RuntimePin | None:
    if not isinstance(value, dict):
        return None
    version = value.get("runtime_version")
    commit = value.get("runtime_commit")
    receipt = value.get("receipt_sha256")
    if (
        not isinstance(version, str)
        or VERSION_PATTERN.fullmatch(version) is None
        or not isinstance(commit, str)
        or COMMIT_PATTERN.fullmatch(commit) is None
        or not isinstance(receipt, str)
        or GENERATION_PATTERN.fullmatch(receipt) is None
    ):
        return None
    return RuntimePin(version, commit, receipt)


def parse_runtime_pin(value: object) -> RuntimePin | None:
    """Validate a runtime pin received from the stable hook dispatcher."""

    return _runtime_pin(value)


def read_activation_state(path: Path, *, refresh: bool = False) -> ActivationState | None:
    """Read a private schema-v1/v2 marker and optionally refresh its TTL."""
    try:
        metadata = path.lstat()
        if (
            path.is_symlink()
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_size > MAX_MARKER_BYTES
        ):
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        generation = payload.get("generation") if isinstance(payload, dict) else None
        if not isinstance(generation, str) or not GENERATION_PATTERN.fullmatch(generation):
            return None
        schema = payload.get("schema_version", 1)
        runtime_pin = _runtime_pin(payload.get("runtime_pin")) if schema == 2 else None
        if schema not in {1, 2} or (schema == 2 and runtime_pin is None):
            return None
        if refresh:
            os.utime(path, None, follow_symlinks=False)
        return ActivationState(generation, runtime_pin)
    except (FileNotFoundError, PermissionError, OSError, UnicodeError, json.JSONDecodeError):
        return None


def read_activation_generation(path: Path, *, refresh: bool = False) -> str | None:
    """Return the generation from either supported activation-marker schema."""

    state = read_activation_state(path, refresh=refresh)
    return state.generation if state is not None else None


def _atomic_state(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    metadata = path.parent.lstat()
    if path.parent.is_symlink() or not stat.S_ISDIR(metadata.st_mode):
        raise OSError("activation state directory is not private regular storage")
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


@contextmanager
def _activation_lock(path: Path, timeout: float = 10.0) -> Iterator[None]:
    lock = path.with_name(f".{path.name}.lock")
    lock.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    metadata = lock.parent.lstat()
    if lock.parent.is_symlink() or not stat.S_ISDIR(metadata.st_mode):
        raise OSError("activation state directory is not private regular storage")
    lock.parent.chmod(0o700)
    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(lock, flags, 0o600)
    os.fchmod(descriptor, 0o600)
    handle = os.fdopen(descriptor, "r+")
    deadline = time.monotonic() + max(timeout, 0.0)
    try:
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("activation state is busy")
                time.sleep(0.05)
        yield
    finally:
        try:
            fcntl.flock(handle, fcntl.LOCK_UN)
        finally:
            handle.close()


def write_activation_generation(path: Path, generation: str) -> None:
    """Atomically persist only the activation generation."""
    if not GENERATION_PATTERN.fullmatch(generation):
        raise ValueError("generation must be a 64-character lowercase hex token")
    _atomic_state(path, {"schema_version": 1, "generation": generation})


def claim_activation(path: Path, runtime_pin: RuntimePin | None) -> ActivationState:
    """Create one activation generation atomically, preserving a racing winner."""

    with _activation_lock(path):
        current = read_activation_state(path, refresh=True)
        if current is not None:
            if current.runtime_pin is None and runtime_pin is not None:
                current = ActivationState(current.generation, runtime_pin)
                write_activation_state(path, current)
            return current
        try:
            path.lstat()
        except FileNotFoundError:
            pass
        else:
            raise ValueError("existing activation marker is invalid")
        if runtime_pin is None:
            raise ValueError("new activation requires a verified runtime pin")
        state = ActivationState(new_activation_generation(), runtime_pin)
        write_activation_state(path, state)
        return state


def write_activation_state(path: Path, state: ActivationState) -> None:
    if (
        not GENERATION_PATTERN.fullmatch(state.generation)
        or state.runtime_pin is None
        or _runtime_pin(state.runtime_pin.as_dict()) != state.runtime_pin
    ):
        raise ValueError("a valid pinned activation state is required")
    _atomic_state(
        path,
        {
            "schema_version": 2,
            "generation": state.generation,
            "runtime_pin": state.runtime_pin.as_dict(),
        },
    )


def remove_activation(path: Path, expected_generation: str) -> bool:
    """Remove only the activation generation observed by the caller."""

    if not GENERATION_PATTERN.fullmatch(expected_generation):
        return False
    with _activation_lock(path):
        current = read_activation_state(path)
        if current is None or current.generation != expected_generation:
            return False
        try:
            path.unlink()
        except FileNotFoundError:
            return False
        return True
