import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DISPATCH = ROOT / "scripts" / "science_hook_dispatch.py"
RUNTIME_STATE = ROOT / "scripts" / "science_runtime_state.py"


def load_runtime_state():
    spec = importlib.util.spec_from_file_location("science_runtime_state_test", RUNTIME_STATE)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load runtime state helper")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


STATE = load_runtime_state()


def load_dispatch():
    spec = importlib.util.spec_from_file_location("science_hook_dispatch_test", DISPATCH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load hook dispatcher")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


DISPATCH_MODULE = load_dispatch()


class HookDispatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.codex_home = self.root / "codex"
        self.plugin_data = self.root / "plugin-data"
        self.environment = {
            **os.environ,
            "CODEX_HOME": str(self.codex_home),
            "CODEX_SCIENCE_PLUGIN_DATA": str(self.plugin_data),
            "PLUGIN_DATA": str(self.plugin_data),
            "CODEX_SCIENCE_AUTO_UPDATE": "apply",
        }

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def make_runtime(
        self,
        marker: str,
        version: str,
        *,
        session_source: str | None = None,
        stop_source: str | None = None,
    ) -> tuple[Path, str, Path]:
        source = self.root / f"source-{marker}"
        for directory in (
            source / ".agents" / "plugins",
            source / ".codex-plugin",
            source / "catalog",
            source / "hooks",
            source / "release",
            source / "runtime-skills" / "codex-science",
            source / "scripts",
            source / "skills",
        ):
            directory.mkdir(parents=True, exist_ok=True)
        (source / ".codex-plugin" / "plugin.json").write_text(
            json.dumps({"version": "0.5.0+codex.20260803040000"}) + "\n",
            encoding="utf-8",
        )
        (source / ".mcp.json").write_text("{}\n", encoding="utf-8")
        (source / ".agents" / "plugins" / "marketplace.json").write_text(
            "{}\n", encoding="utf-8"
        )
        (source / "hooks" / "hooks.json").write_text("{}\n", encoding="utf-8")
        (source / "skills" / "host-skill.md").write_text(
            "host skill\n", encoding="utf-8"
        )
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
        skill = source / "runtime-skills" / "codex-science" / "SKILL.md"
        skill.write_text(f"# live coordinator {marker}\n", encoding="utf-8")
        shutil.copy2(RUNTIME_STATE, source / "scripts" / "science_runtime_state.py")
        for script in ("python_runtime.sh", "science_update_hook.py"):
            (source / "scripts" / script).write_text(
                f"# {script} bootstrap\n", encoding="utf-8"
            )
        shutil.copy2(DISPATCH, source / "scripts" / "science_hook_dispatch.py")
        (source / "scripts" / "science_update_entry.py").write_text(
            "import json, os, pathlib, subprocess, sys\n"
            "json.load(sys.stdin)\n"
            "root = pathlib.Path(__file__).resolve().parents[1]\n"
            "marker = os.environ.get('UPDATE_ENTRY_MARKER')\n"
            "pathlib.Path(marker).touch() if marker else None\n"
            "commit = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'], "
            "capture_output=True, text=True, check=True).stdout.strip()\n"
            "print(json.dumps({'status': 'updated', 'runtime_root': str(root), "
            "'runtime_commit': commit, 'updated': True, "
            "'message': 'Codex Science · runtime ready'}))\n",
            encoding="utf-8",
        )
        (source / "scripts" / "science_mcp_proxy.py").write_text(
            "# stable placeholder\n", encoding="utf-8"
        )
        (source / "scripts" / "science_mcp.py").write_text(
            "# stable placeholder\n", encoding="utf-8"
        )
        default_session_source = (
            "import json\n"
            "payload = json.load(__import__('sys').stdin)\n"
            f"print(json.dumps({{'hookSpecificOutput': {{'hookEventName': payload['hook_event_name'], "
            f"'additionalContext': 'session hook from runtime {marker}'}}}}))\n"
        )
        (source / "scripts" / "science_session_hook.py").write_text(
            session_source if session_source is not None else default_session_source,
            encoding="utf-8",
        )
        (source / "scripts" / "science_stop_hook.py").write_text(
            stop_source
            if stop_source is not None
            else f"import json\nprint(json.dumps({{'systemMessage': 'stop from runtime {marker}'}}))\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "init", "-q", str(source)], check=True)
        subprocess.run(
            ["git", "-C", str(source), "config", "user.email", "hook@test.invalid"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(source), "config", "user.name", "Hook Test"],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(source),
                "remote",
                "add",
                "origin",
                "https://github.com/eightmm/codex-science.git",
            ],
            check=True,
        )
        subprocess.run(["git", "-C", str(source), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(source), "commit", "-q", "-m", f"runtime {marker}"],
            check=True,
        )
        commit = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "HEAD"],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        runtime, reason = STATE.install_runtime_append_only(
            source, self.environment, plugin_data=self.plugin_data
        )
        self.assertIsNotNone(runtime, reason)
        assert runtime is not None
        return source, commit, runtime.root

    def make_bootstrap(self, source: Path, commit: str, *, updated: bool = True) -> Path:
        self.assertTrue(updated)
        actual = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        self.assertEqual(commit, actual)
        return source

    def run_dispatch(self, bootstrap: Path, payload: dict, **extra_env: str):
        result = subprocess.run(
            [sys.executable, str(bootstrap / "scripts" / "science_hook_dispatch.py")],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
            env={
                **self.environment,
                "CODEX_SCIENCE_HOME": str(self.current_source),
                "PLUGIN_ROOT": str(bootstrap),
                **extra_env,
            },
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else None

    def test_first_activation_updates_then_pins_registered_cache_in_same_event(self) -> None:
        source, commit, cache = self.make_runtime("B", "0.5.0+codex.20260803050000")
        self.current_source = source
        bootstrap = self.make_bootstrap(source, commit)
        output = self.run_dispatch(
            bootstrap,
            {
                "hook_event_name": "UserPromptSubmit",
                "session_id": "same-event",
                "prompt": "Start Codex Science",
            },
        )

        assert output is not None
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("session hook from runtime B", context)
        self.assertIn(str(cache), context)
        self.assertNotIn(str(source / "runtime-skills"), context)
        marker = STATE.activation_path(self.plugin_data, "same-event")
        record = STATE.read_activation_record(marker)
        self.assertIsNotNone(record)
        assert record is not None and record.runtime_pin is not None
        self.assertEqual(commit, record.runtime_pin.runtime_commit)
        self.assertNotIn("same-event", marker.name)
        self.assertNotIn("same-event", marker.read_text(encoding="utf-8"))

    def test_inactive_ordinary_prompt_does_not_run_updater_or_dispatch_runtime(self) -> None:
        source, commit, _ = self.make_runtime("B", "0.5.0+codex.20260803050004")
        self.current_source = source
        bootstrap = self.make_bootstrap(source, commit)
        update_marker = self.root / "updater-ran"

        output = self.run_dispatch(
            bootstrap,
            {
                "hook_event_name": "UserPromptSubmit",
                "session_id": "inactive",
                "prompt": "ordinary project question",
            },
            UPDATE_ENTRY_MARKER=str(update_marker),
        )

        self.assertIsNone(output)
        self.assertFalse(update_marker.exists())

    def test_active_prompt_and_stop_stay_on_pin_without_running_updater(self) -> None:
        source, commit, cache = self.make_runtime("B", "0.5.0+codex.20260803050001")
        self.current_source = source
        bootstrap = self.make_bootstrap(source, commit)
        session = "active-pin"
        self.run_dispatch(
            bootstrap,
            {"hook_event_name": "UserPromptSubmit", "session_id": session, "prompt": "Start Codex Science"},
        )
        update_marker = self.root / "updater-ran"

        output = self.run_dispatch(
            bootstrap,
            {"hook_event_name": "UserPromptSubmit", "session_id": session, "prompt": "계속 진행"},
            UPDATE_ENTRY_MARKER=str(update_marker),
        )
        assert output is not None
        self.assertIn(str(cache), output["hookSpecificOutput"]["additionalContext"])
        self.assertFalse(update_marker.exists())

        stop = self.run_dispatch(
            bootstrap,
            {"hook_event_name": "Stop", "session_id": session, "cwd": str(self.root)},
            UPDATE_ENTRY_MARKER=str(update_marker),
        )
        self.assertEqual("stop from runtime B", stop["systemMessage"])
        self.assertFalse(update_marker.exists())
        self.assertIsNotNone(STATE.read_activation_record(STATE.activation_path(self.plugin_data, session)))

    def test_active_prompt_blocks_when_pinned_handler_exits_nonzero(self) -> None:
        session_source = (
            "import json, sys\n"
            "payload = json.load(sys.stdin)\n"
            "if payload.get('prompt') == 'trigger handler failure':\n"
            "    raise SystemExit(7)\n"
            "print(json.dumps({'hookSpecificOutput': {'hookEventName': "
            "payload['hook_event_name'], 'additionalContext': 'active context'}}))\n"
        )
        source, commit, _ = self.make_runtime(
            "prompt-failure",
            "0.5.0+codex.20260803050005",
            session_source=session_source,
        )
        self.current_source = source
        bootstrap = self.make_bootstrap(source, commit)
        session = "active-prompt-failure"
        self.run_dispatch(
            bootstrap,
            {
                "hook_event_name": "UserPromptSubmit",
                "session_id": session,
                "prompt": "Start Codex Science",
            },
        )

        output = self.run_dispatch(
            bootstrap,
            {
                "hook_event_name": "UserPromptSubmit",
                "session_id": session,
                "prompt": "trigger handler failure",
            },
        )

        self.assertEqual("block", output["decision"])
        self.assertIn("handler-exit-7", output["reason"])
        self.assertIn("고정된 runtime 훅", output["systemMessage"])

    def test_active_stop_blocks_when_pinned_handler_emits_invalid_json(self) -> None:
        source, commit, _ = self.make_runtime(
            "stop-failure",
            "0.5.0+codex.20260803050006",
            stop_source="print('not-json')\n",
        )
        self.current_source = source
        bootstrap = self.make_bootstrap(source, commit)
        session = "active-stop-failure"
        self.run_dispatch(
            bootstrap,
            {
                "hook_event_name": "UserPromptSubmit",
                "session_id": session,
                "prompt": "Start Codex Science",
            },
        )

        output = self.run_dispatch(
            bootstrap,
            {"hook_event_name": "Stop", "session_id": session, "cwd": str(self.root)},
        )

        self.assertEqual("block", output["decision"])
        self.assertIn("handler-invalid-json", output["reason"])
        self.assertIn("고정된 runtime 훅", output["systemMessage"])

    def test_active_stop_preserves_deliberate_empty_noop(self) -> None:
        source, commit, _ = self.make_runtime(
            "stop-noop",
            "0.5.0+codex.20260803050007",
            stop_source="# deliberate successful no-op\n",
        )
        self.current_source = source
        bootstrap = self.make_bootstrap(source, commit)
        session = "active-stop-noop"
        self.run_dispatch(
            bootstrap,
            {
                "hook_event_name": "UserPromptSubmit",
                "session_id": session,
                "prompt": "Start Codex Science",
            },
        )

        output = self.run_dispatch(
            bootstrap,
            {"hook_event_name": "Stop", "session_id": session, "cwd": str(self.root)},
        )

        self.assertIsNone(output)
        marker = STATE.activation_path(self.plugin_data, session)
        self.assertIsNotNone(STATE.read_activation_record(marker))

    def test_active_stop_blocks_when_runtime_pin_can_no_longer_verify(self) -> None:
        source, commit, cache = self.make_runtime(
            "pin-damage", "0.5.0+codex.20260803050008"
        )
        self.current_source = source
        bootstrap = self.make_bootstrap(source, commit)
        session = "active-pin-damage"
        self.run_dispatch(
            bootstrap,
            {
                "hook_event_name": "UserPromptSubmit",
                "session_id": session,
                "prompt": "Start Codex Science",
            },
        )
        (cache / "scripts" / "science_stop_hook.py").unlink()

        output = self.run_dispatch(
            bootstrap,
            {"hook_event_name": "Stop", "session_id": session, "cwd": str(self.root)},
        )

        self.assertEqual("block", output["decision"])
        self.assertIn("runtime-pin-verification-failed", output["reason"])
        self.assertIn("고정된 runtime 훅", output["systemMessage"])

    def test_event_runner_distinguishes_noop_from_execution_failures(self) -> None:
        runtime = self.root / "direct-runtime"
        scripts = runtime / "scripts"
        scripts.mkdir(parents=True)
        resolution = {"runtime_root": str(runtime), "runtime_commit": "a" * 40}
        payload = {"hook_event_name": "UserPromptSubmit"}

        missing = DISPATCH_MODULE._run_event(payload, resolution, self.environment)
        self.assertEqual("handler-missing", missing.failure)

        (scripts / "science_session_hook.py").write_text("# test handler\n", encoding="utf-8")
        cases = (
            (
                "empty-noop",
                {"return_value": subprocess.CompletedProcess([], 0, "", "")},
                None,
            ),
            (
                "nonzero",
                {"return_value": subprocess.CompletedProcess([], 9, "{}", "failed")},
                "handler-exit-9",
            ),
            (
                "invalid-json",
                {"return_value": subprocess.CompletedProcess([], 0, "not-json", "")},
                "handler-invalid-json",
            ),
            (
                "non-object-json",
                {"return_value": subprocess.CompletedProcess([], 0, "[]", "")},
                "handler-invalid-json",
            ),
            (
                "timeout",
                {"side_effect": subprocess.TimeoutExpired(["handler"], 15)},
                "handler-timeout",
            ),
            ("launch-error", {"side_effect": OSError("unavailable")}, "handler-launch-failed"),
        )
        for name, patch_options, expected in cases:
            with self.subTest(name=name), mock.patch.object(
                DISPATCH_MODULE, "_run", **patch_options
            ):
                result = DISPATCH_MODULE._run_event(payload, resolution, self.environment)
            self.assertEqual(expected, result.failure)
            self.assertEqual({}, result.output)

    def test_active_explicit_update_installs_for_new_tasks_but_dispatches_old_pin(self) -> None:
        source, commit, _ = self.make_runtime("B", "0.5.0+codex.20260803050002")
        self.current_source = source
        bootstrap = self.make_bootstrap(source, commit)
        session = "explicit-update"
        self.run_dispatch(
            bootstrap,
            {"hook_event_name": "UserPromptSubmit", "session_id": session, "prompt": "Start Codex Science"},
        )
        update_marker = self.root / "updater-ran"
        output = self.run_dispatch(
            bootstrap,
            {"hook_event_name": "UserPromptSubmit", "session_id": session, "prompt": "Codex Science 업데이트"},
            UPDATE_ENTRY_MARKER=str(update_marker),
        )
        self.assertTrue(update_marker.is_file())
        self.assertIn("현재 활성 run", output["systemMessage"])
        self.assertIn("session hook from runtime B", output["hookSpecificOutput"]["additionalContext"])

    def test_corrupt_existing_marker_fails_closed_without_updater(self) -> None:
        source, commit, _ = self.make_runtime("B", "0.5.0+codex.20260803050003")
        self.current_source = source
        bootstrap = self.make_bootstrap(source, commit)
        marker = STATE.activation_path(self.plugin_data, "corrupt")
        marker.parent.mkdir(parents=True)
        marker.write_text("not-json", encoding="utf-8")
        update_marker = self.root / "updater-ran"
        output = self.run_dispatch(
            bootstrap,
            {"hook_event_name": "UserPromptSubmit", "session_id": "corrupt", "prompt": "Start Codex Science"},
            UPDATE_ENTRY_MARKER=str(update_marker),
        )
        self.assertEqual("block", output["decision"])
        self.assertIn("activation-marker-invalid", output["reason"])
        self.assertIn("고정된 runtime 훅", output["systemMessage"])
        self.assertEqual("not-json", marker.read_text(encoding="utf-8"))
        self.assertFalse(update_marker.exists())

    def test_hook_manifest_uses_one_stable_dispatcher_per_event(self) -> None:
        hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        for event in ("SessionStart", "UserPromptSubmit", "Stop"):
            commands = [
                hook["command"]
                for group in hooks["hooks"][event]
                for hook in group["hooks"]
            ]
            self.assertEqual(1, len(commands), (event, commands))
            self.assertIn("science_hook_dispatch.py", commands[0])
            self.assertIn("$PLUGIN_ROOT/scripts/python_runtime.sh", commands[0])


if __name__ == "__main__":
    unittest.main()
