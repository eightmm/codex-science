#!/usr/bin/env python3
"""Stable MCP stdio proxy bound to one task-scoped Science runtime pin."""

from __future__ import annotations

import hashlib
import json
import os
import select
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any, Callable, Mapping


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from science_runtime_state import (  # noqa: E402
    RuntimePin,
    VerifiedRuntime,
    activation_lock,
    activation_path,
    canonical_plugin_data,
    inspect_activation_record,
    runtime_cache_lock,
    verify_runtime_pin,
)


CHILD_STOP_TIMEOUT_SECONDS = 2
CHILD_RESPONSE_TIMEOUT_SECONDS = 120
MAX_TURN_METADATA_BYTES = 16 * 1024
MAX_PROTOCOL_EXCHANGES = 16


@dataclass(frozen=True)
class RuntimeSpec:
    root: Path
    script: Path
    inventory: Path
    identity: str
    pin: RuntimePin | None = None


@dataclass(frozen=True)
class CallIdentity:
    session_id: str
    thread_id: str
    turn_id: str


class BindingError(ValueError):
    pass


def _sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _runtime_version(root: Path) -> str:
    try:
        payload = json.loads(
            (root / "release" / "manifest.json").read_text(encoding="utf-8")
        )
        value = (
            payload.get("runtime_version", payload.get("plugin_version"))
            if isinstance(payload, dict)
            else None
        )
    except (OSError, UnicodeError, json.JSONDecodeError):
        return ""
    return value if isinstance(value, str) else ""


def _runtime_spec(
    root: Path,
    *,
    identity: str | None = None,
    pin: RuntimePin | None = None,
) -> RuntimeSpec | None:
    try:
        root = root.expanduser().resolve(strict=True)
        metadata = root.lstat()
    except OSError:
        return None
    if root.is_symlink() or not root.is_dir():
        return None
    script = root / "scripts" / "science_mcp.py"
    inventory = root / "catalog" / "inventory.json"
    script_digest = _sha256(script)
    inventory_digest = _sha256(inventory)
    if script_digest is None or inventory_digest is None:
        return None
    if identity is None:
        payload = {
            "inventory_sha256": inventory_digest,
            "runtime_version": _runtime_version(root),
            "root": str(root),
            "script_sha256": script_digest,
        }
        identity = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
    return RuntimeSpec(root, script, inventory, identity, pin)


def _pinned_runtime_spec(runtime: VerifiedRuntime) -> RuntimeSpec | None:
    return _runtime_spec(
        runtime.root,
        identity=runtime.pin.receipt_sha256,
        pin=runtime.pin,
    )


def runtime_candidates(environment: Mapping[str, str]) -> tuple[RuntimeSpec, ...]:
    """Return only host-loaded discovery runtimes, never the mutable managed home."""

    roots: list[Path] = []
    plugin_root = environment.get("PLUGIN_ROOT")
    if plugin_root:
        roots.append(Path(plugin_root).expanduser())
    roots.append(ROOT)
    candidates: list[RuntimeSpec] = []
    seen: set[Path] = set()
    for root in roots:
        try:
            resolved = root.resolve(strict=True)
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        candidate = _runtime_spec(resolved)
        if candidate is not None:
            candidates.append(candidate)
    return tuple(candidates)


def parse_call_identity(payload: Mapping[str, Any]) -> CallIdentity:
    if payload.get("method") != "tools/call":
        raise BindingError("runtime binding is only defined for tools/call")
    params = payload.get("params")
    meta = params.get("_meta") if isinstance(params, dict) else None
    if not isinstance(meta, dict):
        raise BindingError("Codex tools/call session metadata is missing")
    outer_thread = meta.get("threadId")
    nested = meta.get("x-codex-turn-metadata")
    if (
        not isinstance(outer_thread, str)
        or not outer_thread
        or len(outer_thread) > 1024
        or not isinstance(nested, dict)
    ):
        raise BindingError("Codex tools/call session metadata is malformed")
    try:
        encoded_size = len(
            json.dumps(nested, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        )
    except (TypeError, ValueError, UnicodeError) as error:
        raise BindingError("Codex tools/call turn metadata is malformed") from error
    if encoded_size > MAX_TURN_METADATA_BYTES:
        raise BindingError("Codex tools/call turn metadata is malformed")
    values: list[str] = []
    for key in ("session_id", "thread_id", "turn_id"):
        value = nested.get(key)
        if not isinstance(value, str) or not value or len(value) > 1024:
            raise BindingError(f"Codex tools/call {key} is missing")
        values.append(value)
    session_id, thread_id, turn_id = values
    if outer_thread != thread_id:
        raise BindingError("Codex tools/call thread metadata does not agree")
    return CallIdentity(session_id, thread_id, turn_id)


def _jsonrpc_error(request_id: object, message: str) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32603, "message": message},
    }


def _initialize_contract(response: Mapping[str, Any]) -> object:
    result = response.get("result")
    if not isinstance(result, dict):
        return {"error": response.get("error")}
    server_info = result.get("serverInfo")
    server_name = server_info.get("name") if isinstance(server_info, dict) else None
    return {
        "protocolVersion": result.get("protocolVersion"),
        "capabilities": result.get("capabilities"),
        "instructions": result.get("instructions"),
        "serverName": server_name,
    }


def _tools_contract(response: Mapping[str, Any]) -> object:
    result = response.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("tools"), list):
        return {"error": response.get("error")}
    return {"tools": result["tools"], "nextCursor": result.get("nextCursor")}


class MCPProxy:
    def __init__(
        self,
        *,
        environment: Mapping[str, str] = os.environ,
        resolver: Callable[[], tuple[RuntimeSpec, ...]] | None = None,
    ) -> None:
        self.environment = dict(environment)
        self.resolver = resolver or (lambda: runtime_candidates(self.environment))
        self.process: subprocess.Popen[str] | None = None
        self.runtime: RuntimeSpec | None = None
        self.initialize_line: str | None = None
        self.initialize_contract: object | None = None
        self.initialized_line: str | None = None
        self.tools_list_exchanges: list[tuple[str, object]] = []
        self.bound_session_id: str | None = None
        self.bound_generation: str | None = None
        self.bound_pin: RuntimePin | None = None
        self.binding_error: str | None = None

    @staticmethod
    def _terminate(process: subprocess.Popen[str] | None) -> None:
        if process is None:
            return
        if process.stdin is not None:
            try:
                process.stdin.close()
            except (BrokenPipeError, OSError):
                pass
        try:
            process.wait(timeout=CHILD_STOP_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=CHILD_STOP_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        if process.stdout is not None:
            process.stdout.close()

    def _stop_child(self) -> None:
        process = self.process
        self.process = None
        self.runtime = None
        self._terminate(process)

    def _spawn(self, runtime: RuntimeSpec) -> subprocess.Popen[str] | None:
        environment = dict(self.environment)
        environment["PYTHONUNBUFFERED"] = "1"
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment.pop("PYTHONPATH", None)
        environment.pop("PYTHONHOME", None)
        for name in (
            "CODEX_SCIENCE_RUNTIME_VERSION",
            "CODEX_SCIENCE_RUNTIME_COMMIT",
            "CODEX_SCIENCE_RUNTIME_RECEIPT",
        ):
            environment.pop(name, None)
        if runtime.pin is not None:
            environment["CODEX_SCIENCE_RUNTIME_VERSION"] = runtime.pin.runtime_version
            environment["CODEX_SCIENCE_RUNTIME_COMMIT"] = runtime.pin.runtime_commit
            environment["CODEX_SCIENCE_RUNTIME_RECEIPT"] = runtime.pin.receipt_sha256
        try:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-I",
                    str(runtime.script),
                    "--inventory",
                    str(runtime.inventory),
                ],
                cwd=runtime.root,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=None,
                text=True,
                encoding="utf-8",
                bufsize=1,
                env=environment,
            )
        except OSError:
            return None
        if process.stdin is None or process.stdout is None:
            self._terminate(process)
            return None
        return process

    @staticmethod
    def _readline(process: subprocess.Popen[str]) -> str | None:
        assert process.stdout is not None
        try:
            ready, _, _ = select.select(
                [process.stdout], [], [], CHILD_RESPONSE_TIMEOUT_SECONDS
            )
        except (OSError, ValueError):
            return None
        if not ready:
            return None
        line = process.stdout.readline()
        return line if line else None

    def _exchange(
        self, process: subprocess.Popen[str], line: str
    ) -> dict[str, Any] | None:
        assert process.stdin is not None
        try:
            request = json.loads(line)
            process.stdin.write(line + "\n")
            process.stdin.flush()
            response_line = self._readline(process)
            if response_line is None:
                return None
            response = json.loads(response_line)
        except (BrokenPipeError, OSError, UnicodeError, json.JSONDecodeError):
            return None
        if (
            not isinstance(request, dict)
            or not isinstance(response, dict)
            or response.get("id") != request.get("id")
        ):
            return None
        return response

    def _replay_protocol_state(self, process: subprocess.Popen[str]) -> bool:
        if self.initialize_line is None or self.initialize_contract is None:
            return False
        response = self._exchange(process, self.initialize_line)
        if response is None or _initialize_contract(response) != self.initialize_contract:
            return False
        assert process.stdin is not None
        try:
            if self.initialized_line is not None:
                process.stdin.write(self.initialized_line + "\n")
                process.stdin.flush()
            for request_line, expected in self.tools_list_exchanges:
                response = self._exchange(process, request_line)
                if response is None or _tools_contract(response) != expected:
                    return False
        except (BrokenPipeError, OSError):
            return False
        return True

    def _activate_child(self, runtime: RuntimeSpec, *, replay: bool) -> bool:
        process = self._spawn(runtime)
        if process is None:
            return False
        if replay and not self._replay_protocol_state(process):
            self._terminate(process)
            return False
        previous = self.process
        self.process = process
        self.runtime = runtime
        self._terminate(previous)
        return True

    def _ensure_discovery_child(self) -> bool:
        if self.bound_session_id is not None:
            return self.process is not None and self.process.poll() is None
        if self.process is not None and self.process.poll() is None:
            return True
        self._stop_child()
        for runtime in self.resolver():
            if self._activate_child(
                runtime, replay=self.initialize_line is not None
            ):
                return True
        return False

    def _bind_for_call(
        self,
        payload: Mapping[str, Any],
        *,
        plugin_data: Path | None = None,
    ) -> None:
        identity = parse_call_identity(payload)
        plugin_data = plugin_data or canonical_plugin_data(self.environment)
        status, record = inspect_activation_record(
            activation_path(plugin_data, identity.session_id)
        )
        if status != "valid" or record is None or record.runtime_pin is None:
            raise BindingError("Codex Science is not active with a verified runtime pin")
        verified = verify_runtime_pin(
            record.runtime_pin, self.environment, plugin_data=plugin_data
        )
        if verified is None:
            raise BindingError("Codex Science runtime pin verification failed")
        runtime = _pinned_runtime_spec(verified)
        if runtime is None:
            raise BindingError("Codex Science pinned MCP runtime is unavailable")

        if self.bound_session_id is not None:
            if identity.session_id != self.bound_session_id:
                raise BindingError("this MCP connection is already bound to another Codex task")
            if record.generation == self.bound_generation:
                if (
                    record.runtime_pin != self.bound_pin
                    or self.runtime is None
                    or self.runtime.identity != runtime.identity
                ):
                    raise BindingError("the active Codex Science runtime pin changed unexpectedly")
                if self.process is not None and self.process.poll() is None:
                    return
                if not self._activate_child(runtime, replay=True):
                    raise BindingError(
                        "the pinned Codex Science MCP runtime could not be restarted"
                    )
                return

            # Explicit deactivation removes the old generation. A subsequent
            # activation in the same Codex task intentionally creates a new
            # generation and may select a newer verified runtime. Rebind only
            # after replaying the exact discovery contract already shown to
            # Codex; an incompatible runtime never receives the tool call.
            if not self._activate_child(runtime, replay=True):
                raise BindingError("the active Codex Science runtime pin changed unexpectedly")
            self.bound_generation = record.generation
            self.bound_pin = record.runtime_pin
            return

        if (
            self.initialize_line is None
            or self.initialize_contract is None
            or not self.tools_list_exchanges
        ):
            raise BindingError("MCP discovery must complete before the first Science tool call")
        # Discovery intentionally runs without a task identity. Even when the
        # pinned runtime has the same root, respawn and replay so the bound
        # process receives the verified provenance environment atomically.
        if not self._activate_child(runtime, replay=True):
            raise BindingError(
                "pinned runtime is incompatible with the MCP contract already shown to Codex"
            )
        self.bound_session_id = identity.session_id
        self.bound_generation = record.generation
        self.bound_pin = record.runtime_pin

    @staticmethod
    def _emit_error(output: IO[str], request_id: object, message: str) -> None:
        output.write(
            json.dumps(_jsonrpc_error(request_id, message), separators=(",", ":")) + "\n"
        )
        output.flush()

    def _forward(self, line: str, output: IO[str]) -> None:
        stripped = line.rstrip("\r\n")
        try:
            payload = json.loads(stripped)
        except (json.JSONDecodeError, UnicodeError):
            payload = None
        method = payload.get("method") if isinstance(payload, dict) else None
        id_absent = isinstance(payload, dict) and "id" not in payload
        notification = (
            isinstance(method, str)
            and method.startswith("notifications/")
            and (id_absent or payload.get("id") is None)
        )
        if id_absent and not notification:
            return
        request_id = payload.get("id") if isinstance(payload, dict) else None
        if method == "initialize":
            if self.bound_session_id is not None:
                self._emit_error(output, request_id, "bound MCP runtime cannot be reinitialized")
                return
            self.initialize_line = None
            self.initialize_contract = None
            self.initialized_line = None
            self.tools_list_exchanges.clear()

        try:
            if method == "tools/call":
                if self.binding_error is not None:
                    raise BindingError(self.binding_error)
                plugin_data = canonical_plugin_data(self.environment)
                assert isinstance(payload, dict)
                identity = parse_call_identity(payload)
                with runtime_cache_lock(self.environment, plugin_data=plugin_data):
                    marker = activation_path(plugin_data, identity.session_id)
                    # Authorization and tool execution share the marker lock.
                    # Deactivation/reactivation therefore cannot invalidate a
                    # generation between pin verification and the tool result.
                    with activation_lock(marker):
                        self._bind_for_call(payload, plugin_data=plugin_data)
                        self._forward_to_child(
                            stripped, payload, output, notification=False
                        )
                return
            if not self._ensure_discovery_child():
                if not notification:
                    self._emit_error(output, request_id, "Codex Science MCP runtime is unavailable")
                return
            response = self._forward_to_child(stripped, payload, output, notification=notification)
        except (BindingError, OSError, TimeoutError) as error:
            if not notification:
                self._emit_error(output, request_id, str(error))
            return

        if notification or response is None:
            if method == "notifications/initialized":
                self.initialized_line = stripped
            return
        if method == "initialize":
            self.initialize_line = stripped
            self.initialize_contract = _initialize_contract(response)
        elif method == "tools/list":
            contract = _tools_contract(response)
            if len(self.tools_list_exchanges) >= MAX_PROTOCOL_EXCHANGES:
                self.binding_error = "too many MCP discovery exchanges to replay safely"
            else:
                self.tools_list_exchanges.append((stripped, contract))

    def _forward_to_child(
        self,
        stripped: str,
        payload: Mapping[str, Any] | None,
        output: IO[str],
        *,
        notification: bool,
    ) -> dict[str, Any] | None:
        process = self.process
        if process is None or process.stdin is None:
            raise BindingError("Codex Science MCP runtime is unavailable")
        request_id = payload.get("id") if isinstance(payload, dict) else None
        try:
            process.stdin.write(stripped + "\n")
            process.stdin.flush()
        except (BrokenPipeError, OSError) as error:
            self._stop_child()
            raise BindingError("Codex Science MCP runtime stopped unexpectedly") from error
        if notification:
            return None
        response_line = self._readline(process)
        if response_line is None:
            self._stop_child()
            raise BindingError("Codex Science MCP runtime did not return a response")
        try:
            response = json.loads(response_line)
        except (json.JSONDecodeError, UnicodeError) as error:
            self._stop_child()
            raise BindingError("Codex Science MCP runtime returned invalid JSON") from error
        if not isinstance(response, dict) or response.get("id") != request_id:
            self._stop_child()
            raise BindingError("Codex Science MCP runtime returned a mismatched response")
        output.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
        output.flush()
        return response

    def serve(self, source: IO[str] = sys.stdin, output: IO[str] = sys.stdout) -> None:
        try:
            for line in source:
                if line.strip():
                    self._forward(line, output)
        finally:
            self._stop_child()


def main() -> int:
    MCPProxy().serve()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
