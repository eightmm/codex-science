#!/usr/bin/env python3
"""Maintain task-scoped Codex Science activation for plugin lifecycle hooks."""

from __future__ import annotations

import json
import os
import re
import stat
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.checkpoints import abandon_checkpoint, find_nonterminal_checkpoint  # noqa: E402
from codex_science.sessions import (  # noqa: E402
    activation_path,
    new_activation_generation,
    read_activation_generation,
    session_key,
    write_activation_generation,
)

INACTIVE_CONTEXT = (
    "Codex Science is inactive for this Codex task. Do not invoke $codex-science unless a later "
    "user prompt explicitly activates it."
)
STATE_TTL_SECONDS = 180 * 24 * 60 * 60
STATE_FILE_PATTERN = re.compile(r"^[0-9a-f]{64}$")

ACTIVATION_PATTERNS = (
    re.compile(r"(?:^|\s)\$codex-science\b", re.IGNORECASE),
    re.compile(
        r"^\s*(?:please\s+)?(?:start|activate|enable|enter|load)\s+(?:the\s+)?"
        r"codex[ -]science\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*codex[ -]science\s+(?:start|activate|enable|enter|load)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*codex[ -]science(?:를)?\s*(?:(?:한\s*번|한번)\s*)?"
        r"(?:시작|활성화|켜|로드)",
        re.IGNORECASE,
    ),
)
DEACTIVATION_PATTERNS = (
    re.compile(
        r"^\s*\$codex-science\s+(?:stop|end|disable|deactivate|exit|종료|중지|비활성화|꺼)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*(?:please\s+)?(?:stop|end|disable|deactivate|exit)\s+(?:the\s+)?"
        r"codex[ -]science\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*codex[ -]science\s+(?:stop|end|disable|deactivate|exit)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*(?:이제\s*)?codex[ -]science(?:를)?\s*(?:종료|중지|비활성화|꺼)",
        re.IGNORECASE,
    ),
)


def _matches(prompt: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(prompt) for pattern in patterns)


def _active_context(session_id: str, generation: str) -> str:
    key = session_key(session_id, generation)
    goal_key = session_key(session_id)
    return (
        "Codex Science is active for this Codex task. On this turn, implicitly invoke "
        "$codex-science and apply its coordinator workflow even when the user does not mention it. "
        "Do not require the user to activate it again. Continue working until completion, a genuine "
        "blocker, or an approval gate; do not stop at setup or a progress update, and do not ask for "
        "non-blocking preferences. For each non-trivial run, pass --session-key "
        f"{key} to science_checkpoint.py init or claim so the Stop guard can safely auto-continue "
        "this activation generation only. When native Goal mode is explicitly requested, call "
        f"get_goal at each automatic continuation, use --outer-goal native --goal-task-key {goal_key}, "
        "and do not mark the "
        "Goal complete before the checkpoint reaches completion_pending. Keep all approval, audit, "
        "provenance, and review gates in force. Only when migrating a pre-generation schema-v2/v3 "
        f"run owned by this same task, pass --previous-session-key {goal_key}; never infer another key."
    )


def _activate(path: Path) -> str:
    generation = read_activation_generation(path, refresh=True)
    if generation is not None:
        return generation
    generation = new_activation_generation()
    write_activation_generation(path, generation)
    return generation


def _deactivate(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _prune_expired(state_dir: Path) -> None:
    """Delete regular activation markers after 180 days without use."""
    try:
        entries = tuple(state_dir.iterdir())
    except (FileNotFoundError, NotADirectoryError, PermissionError):
        return

    cutoff = time.time() - STATE_TTL_SECONDS
    for path in entries:
        if not STATE_FILE_PATTERN.fullmatch(path.name):
            continue
        try:
            metadata = path.lstat()
            if stat.S_ISREG(metadata.st_mode) and metadata.st_mtime < cutoff:
                path.unlink()
        except (FileNotFoundError, PermissionError):
            continue


def _active(path: Path) -> str | None:
    """Return the active generation and refresh its inactivity TTL."""
    return read_activation_generation(path, refresh=True)


def _abandon_owned_run(cwd: object, key: str, reason: str) -> None:
    if not isinstance(cwd, str) or not cwd:
        return
    try:
        run_dir = find_nonterminal_checkpoint(Path(cwd), key)
        if run_dir is not None:
            abandon_checkpoint(run_dir, reason=reason)
    except (FileNotFoundError, PermissionError, OSError, UnicodeError, ValueError, json.JSONDecodeError):
        return


def _emit(event_name: str, context: str) -> None:
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": event_name,
                "additionalContext": context,
            }
        },
        sys.stdout,
        ensure_ascii=False,
    )
    sys.stdout.write("\n")


def _load_input() -> dict[str, Any] | None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def main() -> int:
    payload = _load_input()
    if payload is None:
        return 0

    event_name = payload.get("hook_event_name")
    session_id = payload.get("session_id")
    plugin_data_value = os.environ.get("PLUGIN_DATA") or os.environ.get("CLAUDE_PLUGIN_DATA")
    if (
        event_name not in {"UserPromptSubmit", "SessionStart"}
        or not isinstance(session_id, str)
        or not session_id
        or not plugin_data_value
    ):
        return 0

    state_path = activation_path(Path(plugin_data_value), session_id)
    _prune_expired(state_path.parent)

    if event_name == "UserPromptSubmit":
        prompt = payload.get("prompt")
        if not isinstance(prompt, str):
            return 0
        if _matches(prompt, DEACTIVATION_PATTERNS):
            generation = _active(state_path)
            if generation is not None:
                _abandon_owned_run(
                    payload.get("cwd"),
                    session_key(session_id, generation),
                    "Codex Science explicitly deactivated",
                )
            _deactivate(state_path)
            _emit(event_name, INACTIVE_CONTEXT)
        elif _matches(prompt, ACTIVATION_PATTERNS):
            generation = _activate(state_path)
            _emit(event_name, _active_context(session_id, generation))
        elif (generation := _active(state_path)) is not None:
            _emit(event_name, _active_context(session_id, generation))
        return 0

    source = payload.get("source")
    if source == "clear":
        generation = _active(state_path)
        if generation is not None:
            _abandon_owned_run(
                payload.get("cwd"),
                session_key(session_id, generation),
                "Codex task context cleared",
            )
        _deactivate(state_path)
        _emit(event_name, INACTIVE_CONTEXT)
    elif source in {"resume", "compact", "startup"}:
        generation = _active(state_path)
        if generation is not None:
            _emit(event_name, _active_context(session_id, generation))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
