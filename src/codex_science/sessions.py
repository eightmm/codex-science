"""Session-scoped identifiers shared by Codex Science hooks."""

from __future__ import annotations

import hashlib
from pathlib import Path


def session_key(session_id: str) -> str:
    """Return a non-reversible key without persisting the raw session id."""
    if not session_id:
        raise ValueError("session_id must be non-empty")
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()


def activation_path(plugin_data: Path, session_id: str) -> Path:
    """Return the private activation marker path for one Codex task."""
    return Path(plugin_data) / "science-sessions" / session_key(session_id)
