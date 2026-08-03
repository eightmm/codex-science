import importlib.util
import json
import os
import select
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROXY = ROOT / "scripts" / "science_mcp_proxy.py"
RUNTIME_STATE = ROOT / "scripts" / "science_runtime_state.py"


def load_runtime_state():
    spec = importlib.util.spec_from_file_location("science_runtime_state_proxy_test", RUNTIME_STATE)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load runtime state helper")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


STATE = load_runtime_state()


class MCPProxyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.codex_home = self.root / "codex"
        self.plugin_data = self.root / "plugin-data"
        self.call_log = self.root / "tool-calls.log"
        self.environment = {
            **os.environ,
            "CODEX_HOME": str(self.codex_home),
            "CODEX_SCIENCE_PLUGIN_DATA": str(self.plugin_data),
            "MCP_CALL_LOG": str(self.call_log),
        }
        self.processes: list[subprocess.Popen[str]] = []

    def tearDown(self) -> None:
        for process in self.processes:
            if process.stdin is not None and not process.stdin.closed:
                try:
                    process.stdin.close()
                except BrokenPipeError:
                    pass
            if process.poll() is None:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    process.wait(timeout=5)
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()
        self.tempdir.cleanup()

    def make_runtime(
        self,
        marker: str,
        version: str,
        *,
        tool_description: str = "stable echo tool",
    ):
        source = self.root / f"source-{marker}-{version[-2:]}"
        for directory in (
            source / ".agents" / "plugins",
            source / ".codex-plugin",
            source / "catalog",
            source / "hooks",
            source / "release",
            source / "runtime-skills" / "codex-science",
            source / "scripts",
            source / "skills" / "codex-science",
        ):
            directory.mkdir(parents=True, exist_ok=True)
        (source / ".agents" / "plugins" / "marketplace.json").write_text(
            "{}\n", encoding="utf-8"
        )
        (source / ".codex-plugin" / "plugin.json").write_text(
            json.dumps({"version": "0.5.0+codex.20260803040000"}) + "\n",
            encoding="utf-8",
        )
        (source / ".mcp.json").write_text("{}\n", encoding="utf-8")
        (source / "catalog" / "inventory.json").write_text("{}\n", encoding="utf-8")
        (source / "release" / "manifest.json").write_text(
            json.dumps(
                {
                    "runtime_version": version,
                    "cache_neutral_files": ["README.md"],
                    "cache_neutral_prefixes": ["docs/"],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (source / "runtime-skills" / "codex-science" / "SKILL.md").write_text(
            f"# runtime {marker}\n", encoding="utf-8"
        )
        (source / "hooks" / "hooks.json").write_text("{}\n", encoding="utf-8")
        (source / "skills" / "codex-science" / "SKILL.md").write_text(
            "# stable bootstrap\n", encoding="utf-8"
        )
        shutil.copy2(RUNTIME_STATE, source / "scripts" / "science_runtime_state.py")
        for name in (
            "python_runtime.sh",
            "science_hook_dispatch.py",
            "science_mcp_proxy.py",
            "science_session_hook.py",
            "science_stop_hook.py",
            "science_update_entry.py",
            "science_update_hook.py",
        ):
            (source / "scripts" / name).write_text("# stable placeholder\n", encoding="utf-8")
        (source / "scripts" / "science_mcp.py").write_text(
            "import json, os, pathlib, sys, time\n"
            f"marker = {marker!r}\n"
            f"description = {tool_description!r}\n"
            "count = 0\n"
            "for raw in sys.stdin:\n"
            "    count += 1\n"
            "    request = json.loads(raw)\n"
            "    method = request.get('method')\n"
            "    if method == 'notifications/initialized':\n"
            "        continue\n"
            "    if method == 'initialize':\n"
            "        result = {'protocolVersion': '2025-06-18', 'capabilities': {'tools': {}}, "
            "                  'serverInfo': {'name': 'codex-science-test', 'version': marker}}\n"
            "    elif method == 'tools/list':\n"
            "        result = {'tools': [{'name': 'science_echo', 'description': description, "
            "                  'inputSchema': {'type': 'object', 'properties': {}}, "
            "                  'annotations': {'readOnlyHint': True}}]}\n"
            "    elif method == 'tools/call':\n"
            "        pathlib.Path(os.environ['MCP_CALL_LOG']).open('a').write(marker + '\\n')\n"
            "        time.sleep(float(os.environ.get('MCP_TOOL_DELAY', '0')))\n"
            "        result = {'runtime': marker, 'pid': os.getpid(), 'count': count, 'request': request, "
            "                  'runtime_env': {name: os.environ.get(name) for name in "
            "                  ('CODEX_SCIENCE_RUNTIME_VERSION', 'CODEX_SCIENCE_RUNTIME_COMMIT', "
            "                   'CODEX_SCIENCE_RUNTIME_RECEIPT')}}\n"
            "    else:\n"
            "        result = {'runtime': marker, 'pid': os.getpid(), 'count': count, 'request': request, "
            "                  'runtime_env': {name: os.environ.get(name) for name in "
            "                  ('CODEX_SCIENCE_RUNTIME_VERSION', 'CODEX_SCIENCE_RUNTIME_COMMIT', "
            "                   'CODEX_SCIENCE_RUNTIME_RECEIPT')}}\n"
            "    if 'id' in request:\n"
            "        print(json.dumps({'jsonrpc': '2.0', 'id': request['id'], 'result': result}, separators=(',', ':')), flush=True)\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "init", "-q", str(source)], check=True)
        subprocess.run(
            ["git", "-C", str(source), "config", "user.email", "proxy@test.invalid"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(source), "config", "user.name", "Proxy Test"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(source), "remote", "add", "origin", "https://github.com/eightmm/codex-science.git"],
            check=True,
        )
        subprocess.run(["git", "-C", str(source), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(source), "commit", "-q", "-m", f"runtime {marker}"],
            check=True,
        )
        runtime, reason = STATE.install_runtime_append_only(
            source, self.environment, plugin_data=self.plugin_data
        )
        self.assertIsNotNone(runtime, reason)
        return runtime

    def pin(self, session_id: str, runtime, *, generation: str = "a" * 64) -> None:
        STATE.write_activation_record(
            STATE.activation_path(self.plugin_data, session_id),
            STATE.ActivationRecord(generation, runtime.pin),
        )

    def start_proxy(self, plugin_root: Path) -> subprocess.Popen[str]:
        process = subprocess.Popen(
            [sys.executable, str(PROXY)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env={**self.environment, "PLUGIN_ROOT": str(plugin_root)},
        )
        self.processes.append(process)
        return process

    @staticmethod
    def send(process: subprocess.Popen[str], payload: dict) -> None:
        assert process.stdin is not None
        process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
        process.stdin.flush()

    def response(self, process: subprocess.Popen[str]) -> dict:
        assert process.stdout is not None
        ready, _, _ = select.select([process.stdout], [], [], 5)
        self.assertTrue(ready, "proxy did not return an MCP response")
        line = process.stdout.readline()
        self.assertTrue(line, "proxy closed stdout before returning an MCP response")
        return json.loads(line)

    def discover(self, process: subprocess.Popen[str]) -> None:
        self.send(
            process,
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        )
        self.assertIn("result", self.response(process))
        self.send(
            process,
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        )
        self.send(process, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        self.assertEqual("science_echo", self.response(process)["result"]["tools"][0]["name"])

    @staticmethod
    def call(
        request_id: int,
        session_id: str,
        *,
        thread_id: str = "thread-root",
        turn_id: str = "turn-1",
    ) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": "science_echo",
                "arguments": {},
                "_meta": {
                    "threadId": thread_id,
                    "x-codex-turn-metadata": {
                        "session_id": session_id,
                        "thread_id": thread_id,
                        "turn_id": turn_id,
                    },
                },
            },
        }

    def test_first_call_handoffs_from_loaded_a_to_pinned_b_and_replays_discovery(self) -> None:
        runtime_a = self.make_runtime("A", "0.5.0+codex.20260803051000")
        runtime_b = self.make_runtime("B", "0.5.0+codex.20260803051001")
        self.pin("session-b", runtime_b)
        process = self.start_proxy(runtime_a.root)
        self.discover(process)

        self.send(process, self.call(3, "session-b"))
        result = self.response(process)["result"]
        self.assertEqual("B", result["runtime"])
        self.assertEqual(4, result["count"])
        self.assertEqual(
            {
                "CODEX_SCIENCE_RUNTIME_VERSION": runtime_b.pin.runtime_version,
                "CODEX_SCIENCE_RUNTIME_COMMIT": runtime_b.pin.runtime_commit,
                "CODEX_SCIENCE_RUNTIME_RECEIPT": runtime_b.pin.receipt_sha256,
            },
            result["runtime_env"],
        )
        self.assertEqual(["B"], self.call_log.read_text(encoding="utf-8").splitlines())

    def test_same_root_binding_respawns_with_pin_environment(self) -> None:
        runtime = self.make_runtime("A", "0.5.0+codex.20260803051002")
        self.pin("session-a", runtime)
        self.environment.update(
            {
                "CODEX_SCIENCE_RUNTIME_VERSION": "stale-version",
                "CODEX_SCIENCE_RUNTIME_COMMIT": "1" * 40,
                "CODEX_SCIENCE_RUNTIME_RECEIPT": "2" * 64,
            }
        )
        process = self.start_proxy(runtime.root)
        self.discover(process)

        self.send(
            process,
            {"jsonrpc": "2.0", "id": 3, "method": "science/debug", "params": {}},
        )
        discovery = self.response(process)["result"]
        self.assertEqual(
            {
                "CODEX_SCIENCE_RUNTIME_VERSION": None,
                "CODEX_SCIENCE_RUNTIME_COMMIT": None,
                "CODEX_SCIENCE_RUNTIME_RECEIPT": None,
            },
            discovery["runtime_env"],
        )

        self.send(process, self.call(4, "session-a"))
        bound = self.response(process)["result"]
        self.assertNotEqual(discovery["pid"], bound["pid"])
        self.assertEqual(
            {
                "CODEX_SCIENCE_RUNTIME_VERSION": runtime.pin.runtime_version,
                "CODEX_SCIENCE_RUNTIME_COMMIT": runtime.pin.runtime_commit,
                "CODEX_SCIENCE_RUNTIME_RECEIPT": runtime.pin.receipt_sha256,
            },
            bound["runtime_env"],
        )

    def test_bound_session_stays_on_b_across_home_changes_and_subagent_threads(self) -> None:
        runtime_a = self.make_runtime("A", "0.5.0+codex.20260803051100")
        runtime_b = self.make_runtime("B", "0.5.0+codex.20260803051101")
        self.pin("shared-session", runtime_b)
        process = self.start_proxy(runtime_a.root)
        self.discover(process)
        self.send(process, self.call(3, "shared-session"))
        first = self.response(process)["result"]
        (self.root / "managed-home-C").mkdir()

        self.send(
            process,
            self.call(4, "shared-session", thread_id="thread-subagent", turn_id="turn-2"),
        )
        second = self.response(process)["result"]
        self.assertEqual("B", second["runtime"])
        self.assertEqual(first["pid"], second["pid"])

    def test_same_session_rebinds_after_explicit_deactivation_and_reactivation(self) -> None:
        runtime_a = self.make_runtime("A", "0.5.0+codex.20260803051110")
        runtime_b = self.make_runtime("B", "0.5.0+codex.20260803051111")
        session_id = "reactivated-session"
        first_generation = "a" * 64
        second_generation = "b" * 64
        self.pin(session_id, runtime_a, generation=first_generation)
        process = self.start_proxy(runtime_a.root)
        self.discover(process)

        self.send(process, self.call(3, session_id))
        first = self.response(process)["result"]
        marker = STATE.activation_path(self.plugin_data, session_id)
        self.assertTrue(STATE.remove_activation_record(marker, first_generation))
        self.pin(session_id, runtime_b, generation=second_generation)

        self.send(process, self.call(4, session_id, turn_id="turn-2"))
        second = self.response(process)["result"]
        self.assertEqual("B", second["runtime"])
        self.assertNotEqual(first["pid"], second["pid"])
        self.assertEqual(
            {
                "CODEX_SCIENCE_RUNTIME_VERSION": runtime_b.pin.runtime_version,
                "CODEX_SCIENCE_RUNTIME_COMMIT": runtime_b.pin.runtime_commit,
                "CODEX_SCIENCE_RUNTIME_RECEIPT": runtime_b.pin.receipt_sha256,
            },
            second["runtime_env"],
        )

    def test_reactivation_with_incompatible_contract_never_runs_tool(self) -> None:
        runtime_a = self.make_runtime("A", "0.5.0+codex.20260803051120")
        runtime_b = self.make_runtime(
            "B",
            "0.5.0+codex.20260803051121",
            tool_description="incompatible description",
        )
        session_id = "incompatible-reactivation"
        first_generation = "c" * 64
        self.pin(session_id, runtime_a, generation=first_generation)
        process = self.start_proxy(runtime_a.root)
        self.discover(process)
        self.send(process, self.call(3, session_id))
        self.assertEqual("A", self.response(process)["result"]["runtime"])

        marker = STATE.activation_path(self.plugin_data, session_id)
        self.assertTrue(STATE.remove_activation_record(marker, first_generation))
        self.pin(session_id, runtime_b, generation="d" * 64)
        self.send(process, self.call(4, session_id, turn_id="turn-2"))

        self.assertIn("unexpectedly", self.response(process)["error"]["message"])
        self.assertEqual(["A"], self.call_log.read_text(encoding="utf-8").splitlines())

    def test_missing_or_mismatched_metadata_fails_closed_without_poisoning_valid_bind(self) -> None:
        runtime_a = self.make_runtime("A", "0.5.0+codex.20260803051200")
        runtime_b = self.make_runtime("B", "0.5.0+codex.20260803051201")
        self.pin("valid-session", runtime_b)
        process = self.start_proxy(runtime_a.root)
        self.discover(process)

        malformed = self.call(3, "valid-session")
        del malformed["params"]["_meta"]
        self.send(process, malformed)
        self.assertIn("metadata", self.response(process)["error"]["message"])

        mismatch = self.call(4, "valid-session")
        mismatch["params"]["_meta"]["threadId"] = "other-thread"
        self.send(process, mismatch)
        self.assertIn("does not agree", self.response(process)["error"]["message"])

        encoded = self.call(5, "valid-session")
        encoded["params"]["_meta"]["x-codex-turn-metadata"] = json.dumps(
            encoded["params"]["_meta"]["x-codex-turn-metadata"]
        )
        self.send(process, encoded)
        self.assertIn("malformed", self.response(process)["error"]["message"])

        self.send(process, self.call(6, "valid-session"))
        self.assertEqual("B", self.response(process)["result"]["runtime"])

    def test_connection_rejects_second_session_but_keeps_original_bound(self) -> None:
        runtime_a = self.make_runtime("A", "0.5.0+codex.20260803051300")
        runtime_b = self.make_runtime("B", "0.5.0+codex.20260803051301")
        self.pin("session-one", runtime_b)
        self.pin("session-two", runtime_b, generation="b" * 64)
        process = self.start_proxy(runtime_a.root)
        self.discover(process)
        self.send(process, self.call(3, "session-one"))
        first = self.response(process)["result"]

        self.send(process, self.call(4, "session-two"))
        self.assertIn("another Codex task", self.response(process)["error"]["message"])
        self.send(process, self.call(5, "session-one", turn_id="turn-3"))
        self.assertEqual(first["pid"], self.response(process)["result"]["pid"])

    def test_deactivation_waits_for_authorized_tool_call_boundary(self) -> None:
        runtime = self.make_runtime("A", "0.5.0+codex.20260803051310")
        session_id = "serialized-deactivation"
        generation = "e" * 64
        self.pin(session_id, runtime, generation=generation)
        self.environment["MCP_TOOL_DELAY"] = "0.5"
        process = self.start_proxy(runtime.root)
        self.discover(process)
        self.send(process, self.call(3, session_id))

        deadline = time.monotonic() + 2
        while not self.call_log.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(self.call_log.exists(), "tool body did not start")
        marker = STATE.activation_path(self.plugin_data, session_id)
        removed: list[bool] = []
        remover = threading.Thread(
            target=lambda: removed.append(
                STATE.remove_activation_record(marker, generation)
            )
        )
        remover.start()
        time.sleep(0.1)
        self.assertTrue(remover.is_alive())
        self.assertTrue(marker.exists())

        self.assertEqual("A", self.response(process)["result"]["runtime"])
        remover.join(timeout=2)
        self.assertEqual([True], removed)
        self.assertFalse(marker.exists())

        self.send(process, self.call(4, session_id, turn_id="turn-2"))
        self.assertIn("not active", self.response(process)["error"]["message"])

    def test_schema_incompatible_pin_never_executes_tool_body(self) -> None:
        runtime_a = self.make_runtime("A", "0.5.0+codex.20260803051400")
        runtime_b = self.make_runtime(
            "B", "0.5.0+codex.20260803051401", tool_description="changed schema"
        )
        self.pin("incompatible", runtime_b)
        process = self.start_proxy(runtime_a.root)
        self.discover(process)
        self.send(process, self.call(3, "incompatible"))
        error = self.response(process)["error"]["message"]
        self.assertIn("incompatible", error)
        self.assertFalse(self.call_log.exists())

    def test_inactive_session_cannot_call_tools(self) -> None:
        runtime = self.make_runtime("A", "0.5.0+codex.20260803051500")
        process = self.start_proxy(runtime.root)
        self.discover(process)
        self.send(process, self.call(3, "inactive"))
        self.assertIn("not active", self.response(process)["error"]["message"])
        self.assertFalse(self.call_log.exists())

    def test_plugin_configuration_uses_the_stable_proxy(self) -> None:
        config = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))[
            "mcpServers"
        ]["codex-science"]
        self.assertEqual("./scripts/python_runtime.sh", config["command"])
        self.assertEqual(["./scripts/science_mcp_proxy.py"], config["args"])


if __name__ == "__main__":
    unittest.main()
