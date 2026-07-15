"""Session-scoped identifiers shared by Codex Science hooks."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import stat
from pathlib import Path


GENERATION_PATTERN = re.compile(r"^[0-9a-f]{64}$")
MAX_MARKER_BYTES = 4096


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


def read_activation_generation(path: Path, *, refresh: bool = False) -> str | None:
    """Read a private regular marker and optionally refresh its inactivity TTL."""
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
        if refresh:
            os.utime(path, None, follow_symlinks=False)
        return generation
    except (FileNotFoundError, PermissionError, OSError, UnicodeError, json.JSONDecodeError):
        return None


def write_activation_generation(path: Path, generation: str) -> None:
    """Atomically persist only the activation generation."""
    if not GENERATION_PATTERN.fullmatch(generation):
        raise ValueError("generation must be a 64-character lowercase hex token")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(temporary, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"schema_version": 1, "generation": generation}) + "\n")
        temporary.replace(path)
        path.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)
