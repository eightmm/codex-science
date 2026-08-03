#!/usr/bin/env python3
"""Continue active Codex Science checkpoints when a turn tries to stop early."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.checkpoints import (  # noqa: E402
    find_active_checkpoint,
    load_checkpoint,
    request_continuation,
)
from codex_science.sessions import (  # noqa: E402
    activation_path,
    read_activation_generation,
    session_key,
)


DEFAULT_IDLE_LIMIT = 3
MAX_IDLE_LIMIT = 20


def _load_input() -> dict[str, Any] | None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _idle_limit() -> int:
    raw = os.environ.get("CODEX_SCIENCE_MAX_IDLE_CONTINUATIONS", "")
    try:
        value = int(raw) if raw else DEFAULT_IDLE_LIMIT
    except ValueError:
        return DEFAULT_IDLE_LIMIT
    return min(max(value, 1), MAX_IDLE_LIMIT)


def _blocking_enabled() -> bool:
    return os.environ.get("CODEX_SCIENCE_STOP_MODE", "warn").strip().lower() == "block"


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

    generation = read_activation_generation(
        activation_path(Path(plugin_data_value), session_id),
        refresh=True,
    )
    if generation is None:
        return 0
    key = session_key(session_id, generation)
    try:
        run_dir = find_active_checkpoint(Path(cwd), key)
        if run_dir is None:
            return 0
        if not _blocking_enabled():
            checkpoint = load_checkpoint(run_dir)
            _emit(
                {
                    "systemMessage": (
                        "Codex Science · 작업이 남아 있습니다 — "
                        f"{_bounded(checkpoint['current_step'], 180)} · 다음: "
                        f"{_bounded(checkpoint['next_action'], 320)}"
                    )
                }
            )
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
        reason = result.get("reason", "continuation_stopped")
        _emit(
            {
                "systemMessage": (
                    "Codex Science · 자동 계속을 안전하게 멈췄습니다 — "
                    f"{_bounded(reason, 240)} · 다음: 체크포인트 확인"
                )
            }
        )
        return 0

    checkpoint_path = run_dir / "checkpoint.json"
    reason = (
        "## Codex Science · 계속 진행\n\n"
        f"- **목표:** {_bounded(checkpoint['goal'], 500)}\n"
        f"- **현재:** {_bounded(checkpoint['current_step'], 300)}\n"
        f"- **다음:** {_bounded(checkpoint['next_action'], 500)}\n"
        f"- **체크포인트:** `{_bounded(checkpoint_path, 1200)}`\n\n"
        "체크포인트와 완료 기준을 다시 확인하고, 다음 안전한 행동을 실제로 수행하세요. "
        "멈추기 전에는 진행·단계·게이트·실패·완료 중 해당 상태를 기록하세요. "
        "사용자 입력은 실제 승인 게이트에서만 요청하고, 검증이 남아 있으면 완료라고 말하지 마세요."
    )
    _emit(
        {
            "decision": "block",
            "reason": reason,
            "systemMessage": (
                "Codex Science · 계속 진행 — "
                f"{_bounded(checkpoint['current_step'], 150)} · 다음: "
                f"{_bounded(checkpoint['next_action'], 240)}"
            ),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
