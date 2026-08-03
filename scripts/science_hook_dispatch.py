#!/usr/bin/env python3
"""Stable plugin hook bootstrap that dispatches to the activation-pinned runtime."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


BOOTSTRAP_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from science_runtime_state import (  # noqa: E402
    ActivationRecord,
    RuntimePin,
    VerifiedRuntime,
    activation_path,
    attach_runtime_pin,
    claim_runtime_activation,
    ensure_runtime,
    hook_plugin_data,
    inspect_activation_record,
    read_activation_record,
    remove_activation_record,
    runtime_cache_lock,
    verify_runtime_pin,
)


DEFAULT_HOME = Path.home() / ".codex-science"
# The host gives ordinary hook dispatch 1,800 seconds. Leave enough time for
# runtime-lock acquisition, the pinned handler, and process teardown after an
# update attempt instead of letting the host kill the bootstrap mid-handoff.
UPDATE_TIMEOUT_SECONDS = 1650
EVENT_TIMEOUT_SECONDS = 15
UPDATE_PATTERNS = (
    re.compile(
        r"^\s*(?:please\s+)?(?:update|upgrade)\s+codex[ -]science"
        r"(?:\s+now)?[.!]?\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*codex[ -]science(?:를)?\s*(?:업데이트|최신화|갱신)"
        r"(?:해\s*줘|해줘|해주세요|해)?[.!]?\s*$",
        re.IGNORECASE,
    ),
)
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


@dataclass(frozen=True)
class EventRun:
    """Result of invoking a pinned hook handler.

    An empty successful output is a valid no-op.  ``failure`` is populated only
    when the handler could not be trusted to make that decision itself.
    """

    output: dict[str, Any]
    failure: str | None = None


def _load_input() -> dict[str, Any] | None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _run(
    command: list[str],
    payload: Mapping[str, Any],
    *,
    environment: Mapping[str, str],
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
        env=dict(environment),
    )


def _allowed_roots(environment: Mapping[str, str]) -> tuple[Path, ...]:
    roots = [
        Path(environment.get("CODEX_SCIENCE_HOME", str(DEFAULT_HOME))).expanduser(),
        BOOTSTRAP_ROOT,
    ]
    plugin_root = environment.get("PLUGIN_ROOT")
    if plugin_root:
        roots.append(Path(plugin_root).expanduser())
    return tuple(dict.fromkeys(path.resolve(strict=False) for path in roots))


def _fallback_resolution(environment: Mapping[str, str], message: str) -> dict[str, Any]:
    plugin_root = environment.get("PLUGIN_ROOT")
    root = Path(plugin_root).expanduser() if plugin_root else BOOTSTRAP_ROOT
    return {
        "status": "bootstrap-fallback",
        "runtime_root": str(root.resolve()),
        "runtime_commit": "loaded-cache",
        "message": message,
        "updated": False,
    }


def _resolve_runtime(
    payload: Mapping[str, Any], environment: Mapping[str, str]
) -> dict[str, Any]:
    # Only the installed, user-trusted bootstrap may decide whether the managed
    # checkout is safe. Never execute updater code from that checkout first.
    entry = BOOTSTRAP_ROOT / "scripts" / "science_update_entry.py"
    if not entry.is_file():
        return _fallback_resolution(
            environment,
            "Codex Science · 업데이트 bootstrap을 찾지 못해 로드된 검증 버전으로 계속합니다.",
        )
    try:
        completed = _run(
            [sys.executable, str(entry), "--resolve-runtime"],
            payload,
            environment=environment,
            timeout=UPDATE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return _fallback_resolution(
            environment,
            f"Codex Science · 업데이트 확인을 마치지 못해 로드된 검증 버전으로 계속합니다: {error}",
        )
    try:
        resolution = json.loads(completed.stdout)
        root = Path(str(resolution["runtime_root"])).expanduser().resolve()
        if completed.returncode != 0 or root not in _allowed_roots(environment):
            raise ValueError("untrusted runtime root")
        if not isinstance(resolution.get("runtime_commit"), str):
            raise ValueError("runtime identity is missing")
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        detail = completed.stderr.strip()
        suffix = f": {detail}" if detail else ""
        return _fallback_resolution(
            environment,
            "Codex Science · 업데이트 결과를 확인할 수 없어 로드된 검증 버전으로 "
            f"계속합니다{suffix}",
        )
    resolution["runtime_root"] = str(root)
    return resolution


def _explicit_update(payload: Mapping[str, Any]) -> bool:
    prompt = payload.get("prompt")
    return (
        payload.get("hook_event_name") == "UserPromptSubmit"
        and isinstance(prompt, str)
        and any(pattern.fullmatch(prompt) for pattern in UPDATE_PATTERNS)
    )


def _activation_request(payload: Mapping[str, Any]) -> bool:
    prompt = payload.get("prompt")
    if payload.get("hook_event_name") != "UserPromptSubmit" or not isinstance(prompt, str):
        return False
    if any(pattern.search(prompt) for pattern in DEACTIVATION_PATTERNS):
        return False
    return any(pattern.search(prompt) for pattern in ACTIVATION_PATTERNS)


def _pinned_resolution(
    runtime: VerifiedRuntime,
    *,
    status: str = "pinned",
    message: str | None = None,
    updated: bool = False,
) -> dict[str, Any]:
    return {
        "status": status,
        "runtime_root": str(runtime.root),
        "runtime_commit": runtime.pin.runtime_commit,
        "runtime_version": runtime.pin.runtime_version,
        "runtime_receipt": runtime.pin.receipt_sha256,
        "message": message,
        "updated": updated,
    }


def _runtime_for_resolution(
    resolution: Mapping[str, Any],
    environment: Mapping[str, str],
    plugin_data: Path,
) -> VerifiedRuntime | None:
    try:
        source = Path(str(resolution["runtime_root"]))
    except (KeyError, TypeError, ValueError):
        return None
    return ensure_runtime(
        source,
        environment,
        plugin_data=plugin_data,
        allow_create=False,
    )


def _loaded_runtime(
    environment: Mapping[str, str], plugin_data: Path
) -> VerifiedRuntime | None:
    value = environment.get("PLUGIN_ROOT")
    source = Path(value).expanduser() if value else BOOTSTRAP_ROOT
    return ensure_runtime(
        source,
        environment,
        plugin_data=plugin_data,
        allow_create=False,
    )


def _active_runtime(
    record: ActivationRecord,
    environment: Mapping[str, str],
    plugin_data: Path,
    state_path: Path,
) -> VerifiedRuntime | None:
    if record.runtime_pin is not None:
        return verify_runtime_pin(record.runtime_pin, environment, plugin_data=plugin_data)
    loaded = _loaded_runtime(environment, plugin_data)
    if loaded is None:
        return None
    if not attach_runtime_pin(state_path, record.generation, loaded.pin):
        return None
    return loaded


def _event_script(event_name: str) -> str | None:
    if event_name in {"SessionStart", "UserPromptSubmit"}:
        return "science_session_hook.py"
    if event_name == "Stop":
        return "science_stop_hook.py"
    return None


def _run_event(
    payload: Mapping[str, Any],
    resolution: Mapping[str, Any],
    environment: Mapping[str, str],
) -> EventRun:
    event_name = str(payload.get("hook_event_name", ""))
    script_name = _event_script(event_name)
    if script_name is None:
        return EventRun({})
    runtime_root = Path(str(resolution["runtime_root"]))
    script = runtime_root / "scripts" / script_name
    if not script.is_file():
        return EventRun({}, "handler-missing")
    child_environment = {
        **environment,
        "CODEX_SCIENCE_RUNTIME_ROOT": str(runtime_root),
        "CODEX_SCIENCE_RUNTIME_COMMIT": str(resolution["runtime_commit"]),
    }
    version = resolution.get("runtime_version")
    receipt = resolution.get("runtime_receipt")
    if isinstance(version, str) and isinstance(receipt, str):
        child_environment["CODEX_SCIENCE_RUNTIME_VERSION"] = version
        child_environment["CODEX_SCIENCE_RUNTIME_RECEIPT"] = receipt
    try:
        completed = _run(
            [sys.executable, str(script)],
            payload,
            environment=child_environment,
            timeout=EVENT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return EventRun({}, "handler-timeout")
    except OSError:
        return EventRun({}, "handler-launch-failed")
    except UnicodeError:
        return EventRun({}, "handler-invalid-output")
    if completed.returncode != 0:
        return EventRun({}, f"handler-exit-{completed.returncode}")
    if not completed.stdout.strip():
        return EventRun({})
    try:
        output = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return EventRun({}, "handler-invalid-json")
    if not isinstance(output, dict):
        return EventRun({}, "handler-invalid-json")
    return EventRun(output)


def _event_failure_output(
    event_name: str, failure: str, *, block: bool
) -> dict[str, Any]:
    action = "차단했습니다" if block else "진행하지 않았습니다"
    message = (
        "Codex Science · 활성 작업에 고정된 runtime 훅을 정상 실행하지 못해 이번 경계를 "
        f"{action}. 관리 설치를 다시 실행한 뒤 같은 요청을 재시도하세요. "
        f"({failure})"
    )
    output: dict[str, Any] = {"systemMessage": message}
    if block:
        output.update(
            {
                "decision": "block",
                "reason": (
                    f"Codex Science pinned {event_name} handler failed ({failure}). "
                    "Reinstall the managed plugin and retry this hook boundary."
                ),
            }
        )
    return output


def _append_runtime_context(
    output: dict[str, Any],
    payload: Mapping[str, Any],
    resolution: Mapping[str, Any],
    *,
    active: bool,
) -> None:
    event_name = str(payload.get("hook_event_name", ""))
    if event_name not in {"SessionStart", "UserPromptSubmit"} or not active:
        return
    hook_output = output.get("hookSpecificOutput")
    if not isinstance(hook_output, dict) or not hook_output.get("additionalContext"):
        return
    root = str(resolution["runtime_root"])
    commit = str(resolution["runtime_commit"])
    live_skill = Path(root) / "runtime-skills" / "codex-science" / "SKILL.md"
    runtime_context = (
        "Codex Science pinned runtime is "
        f"{commit} at {root}. Before applying the coordinator on this turn, read {live_skill} "
        "completely and use that pinned file plus its root-relative resources. If cached plugin "
        "instructions differ, the pinned runtime controls this activation generation; higher-priority user and "
        "system instructions still win."
    )
    hook_output["hookEventName"] = event_name
    hook_output["additionalContext"] = (
        str(hook_output["additionalContext"]).rstrip() + " " + runtime_context
    )


def main() -> int:
    payload = _load_input()
    if payload is None:
        return 0
    environment = dict(os.environ)
    event_name = payload.get("hook_event_name")
    session_id = payload.get("session_id")
    plugin_data = hook_plugin_data(environment)
    if not isinstance(session_id, str) or not session_id or plugin_data is None:
        return 0
    state_path = activation_path(plugin_data, session_id)
    cache_lock_timeout = 1.5 if event_name == "Stop" else 30.0
    marker_status, record = inspect_activation_record(state_path)
    if marker_status == "expired" and record is not None:
        remove_activation_record(state_path, record.generation)
        marker_status, record = inspect_activation_record(state_path)
    if marker_status == "invalid":
        output = _event_failure_output(
            str(event_name),
            "activation-marker-invalid",
            block=event_name in {"UserPromptSubmit", "Stop"},
        )
        json.dump(output, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0
    if marker_status != "valid":
        record = None
    handler_required = record is not None or _activation_request(payload)
    if record is None and not (
        _activation_request(payload)
        or _explicit_update(payload)
        or (event_name == "SessionStart" and payload.get("source") == "startup")
    ):
        # An inactive ordinary prompt, resume, compaction, clear, or Stop has no
        # Science work to dispatch. In particular, do not turn every host hook
        # into an update check before the user activates the mode.
        return 0
    message: str | None = None

    try:
        if record is not None:
            with runtime_cache_lock(
                environment,
                plugin_data=plugin_data,
                timeout=cache_lock_timeout,
            ):
                pinned = _active_runtime(record, environment, plugin_data, state_path)
            if pinned is None:
                output = _event_failure_output(
                    str(event_name),
                    "runtime-pin-verification-failed",
                    block=event_name in {"UserPromptSubmit", "Stop"},
                )
                json.dump(output, sys.stdout, ensure_ascii=False)
                sys.stdout.write("\n")
                return 0
            resolution = _pinned_resolution(pinned)
            if event_name != "Stop" and _explicit_update(payload):
                update = _resolve_runtime(payload, environment)
                update_message = update.get("message")
                if update.get("updated"):
                    message = (
                        f"Codex Science · 새 버전 {str(update.get('runtime_commit', ''))[:8]}을 "
                        f"설치했습니다. 현재 활성 run은 검증된 {pinned.pin.runtime_commit[:8]}에 "
                        "고정되고, 새 작업부터 업데이트 버전을 사용합니다."
                    )
                elif isinstance(update_message, str):
                    message = update_message
        else:
            if event_name == "Stop":
                return 0
            update = _resolve_runtime(payload, environment)
            with runtime_cache_lock(
                environment,
                plugin_data=plugin_data,
                timeout=cache_lock_timeout,
            ):
                runtime = _runtime_for_resolution(update, environment, plugin_data)
                if runtime is None:
                    runtime = _loaded_runtime(environment, plugin_data)
                if runtime is None:
                    message = (
                        "Codex Science · private runtime을 검증하지 못했습니다. "
                        "관리 설치 명령을 다시 실행하세요."
                    )
                    output = {"systemMessage": message}
                    json.dump(output, sys.stdout, ensure_ascii=False)
                    sys.stdout.write("\n")
                    return 0
                resolution = _pinned_resolution(
                    runtime,
                    status=str(update.get("status", "current")),
                    message=(
                        update.get("message")
                        if isinstance(update.get("message"), str)
                        else None
                    ),
                    updated=bool(update.get("updated")),
                )
                message = resolution.get("message")
                if _activation_request(payload):
                    # Keep the same shared store barrier from verification through
                    # marker claim so an explicit bootstrap migration cannot pass
                    # its zero-activation gate in between.
                    claimed = claim_runtime_activation(state_path, runtime.pin)
                    if claimed.runtime_pin is None:
                        raise ValueError("activation winner has no runtime pin")
                    if claimed.runtime_pin != runtime.pin:
                        winner = verify_runtime_pin(
                            claimed.runtime_pin, environment, plugin_data=plugin_data
                        )
                        if winner is None:
                            raise ValueError("activation winner runtime is unavailable")
                        resolution = _pinned_resolution(
                            winner,
                            status="pinned",
                            message=message,
                            updated=bool(update.get("updated")),
                        )

        with runtime_cache_lock(
            environment,
            plugin_data=plugin_data,
            timeout=cache_lock_timeout,
        ):
            event_run = _run_event(payload, resolution, environment)
    except (OSError, TimeoutError, ValueError):
        status_message = (
            "Codex Science · runtime cache가 업데이트 중이거나 검증되지 않아 이번 경계를 "
            "안전하게 건너뛰었습니다. 잠시 후 다시 시도하세요."
        )
        output = {"systemMessage": status_message}
        if event_name == "Stop":
            output.update(
                {
                    "decision": "block",
                    "reason": (
                        "Codex Science runtime pin could not be checked before Stop. "
                        "Retry the Stop hook after the short cache update finishes."
                    ),
                }
            )
        json.dump(output, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    final_record = read_activation_record(state_path, refresh=True)
    active = final_record is not None and final_record.runtime_pin == RuntimePin(
        str(resolution.get("runtime_version", "")),
        str(resolution.get("runtime_commit", "")),
        str(resolution.get("runtime_receipt", "")),
    )
    if final_record is not None and final_record.runtime_pin is None:
        active = attach_runtime_pin(
            state_path,
            final_record.generation,
            RuntimePin(
                str(resolution.get("runtime_version", "")),
                str(resolution.get("runtime_commit", "")),
                str(resolution.get("runtime_receipt", "")),
            ),
        )
    output = event_run.output
    if event_run.failure is not None and handler_required:
        output = _event_failure_output(
            str(event_name),
            event_run.failure,
            block=event_name in {"UserPromptSubmit", "Stop"},
        )
    _append_runtime_context(output, payload, resolution, active=active)
    if isinstance(message, str) and message.strip():
        existing = str(output.get("systemMessage", "")).strip()
        output["systemMessage"] = message.strip() + (f"\n{existing}" if existing else "")
    if output:
        json.dump(output, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
