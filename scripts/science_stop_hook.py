#!/usr/bin/env python3
"""Continue active Codex Science checkpoints when a turn tries to stop early."""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.checkpoints import find_active_checkpoint, request_continuation  # noqa: E402
from codex_science.sessions import activation_path, session_key  # noqa: E402


DEFAULT_IDLE_LIMIT = 3
MAX_IDLE_LIMIT = 20


def _load_input() -> dict[str, Any] | None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _active_marker(path: Path) -> bool:
    try:
        return stat.S_ISREG(path.lstat().st_mode) and not path.is_symlink()
    except (FileNotFoundError, PermissionError, OSError):
        return False


def _idle_limit() -> int:
    raw = os.environ.get("CODEX_SCIENCE_MAX_IDLE_CONTINUATIONS", "")
    try:
        value = int(raw) if raw else DEFAULT_IDLE_LIMIT
    except ValueError:
        return DEFAULT_IDLE_LIMIT
    return min(max(value, 1), MAX_IDLE_LIMIT)


def _bounded(value: object, limit: int = 1000) -> str:
    text = str(value).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _emit(value: dict[str, object]) -> None:
    json.dump(value, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


def main() -> int:
    payload = _load_input()
    if payload is None or payload.get("hook_event_name") != "Stop":
        return 0
    session_id = payload.get("session_id")
    cwd = payload.get("cwd")
    plugin_data_value = os.environ.get("PLUGIN_DATA") or os.environ.get("CLAUDE_PLUGIN_DATA")
    if (
        not isinstance(session_id, str)
        or not session_id
        or not isinstance(cwd, str)
        or not cwd
        or not plugin_data_value
    ):
        return 0

    key = session_key(session_id)
    if not _active_marker(activation_path(Path(plugin_data_value), session_id)):
        return 0
    try:
        run_dir = find_active_checkpoint(Path(cwd), key)
        if run_dir is None:
            return 0
        result = request_continuation(run_dir, session_key=key, idle_limit=_idle_limit())
    except (
        FileNotFoundError,
        PermissionError,
        OSError,
        UnicodeError,
        ValueError,
        json.JSONDecodeError,
    ):
        return 0
    checkpoint = result["checkpoint"]
    if not result["continue"]:
        _emit(
            {
                "systemMessage": (
                    "Codex Science auto-continue safety limit reached without a checkpoint "
                    "heartbeat. The run remains active; inspect it before the next continuation."
                )
            }
        )
        return 0

    checkpoint_path = run_dir / "checkpoint.json"
    criteria = "; ".join(_bounded(item, 300) for item in checkpoint["done_criteria"][:5])
    reason = (
        "Continue the active Codex Science run instead of returning a progress-only answer. "
        f"Reload {_bounded(checkpoint_path, 1500)} with science_checkpoint.py show. "
        f"Goal: {_bounded(checkpoint['goal'])}. "
        f"Current step: {_bounded(checkpoint['current_step'])}. "
        f"Next action: {_bounded(checkpoint['next_action'])}. "
        f"Done criteria: {criteria}. "
        "Perform the next safe in-scope action now. Before the next stop, update the checkpoint "
        "with heartbeat, advance, attempt, gate, block, or complete. Ask the user only through a "
        "real approval gate; never claim completion while planned steps or verification remain."
    )
    _emit(
        {
            "decision": "block",
            "reason": reason,
            "systemMessage": (
                "Codex Science auto-continue "
                f"{checkpoint['idle_continuations']}/{_idle_limit()}: "
                f"{_bounded(checkpoint['next_action'], 240)}"
            ),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
