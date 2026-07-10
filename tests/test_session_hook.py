import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


class ScienceSessionHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository_root = Path(__file__).resolve().parents[1]
        self.script = self.repository_root / "scripts" / "science_session_hook.py"
        self.tempdir = tempfile.TemporaryDirectory()
        self.plugin_data = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def run_hook(
        self,
        event: str,
        *,
        session_id: str = "session-A",
        prompt: str | None = None,
        source: str | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object] | None]:
        payload: dict[str, object] = {
            "cwd": str(self.repository_root),
            "hook_event_name": event,
            "model": "test-model",
            "permission_mode": "default",
            "session_id": session_id,
            "transcript_path": None,
        }
        if prompt is not None:
            payload.update({"prompt": prompt, "turn_id": "turn-1"})
        if source is not None:
            payload["source"] = source
        env = os.environ.copy()
        env["PLUGIN_DATA"] = str(self.plugin_data)
        result = subprocess.run(
            [sys.executable, str(self.script)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        output = json.loads(result.stdout) if result.stdout.strip() else None
        return result, output

    def additional_context(self, output: dict[str, object]) -> str:
        hook_output = output["hookSpecificOutput"]
        self.assertIsInstance(hook_output, dict)
        return str(hook_output["additionalContext"])

    def test_explicit_invocation_activates_only_current_session(self) -> None:
        result, output = self.run_hook(
            "UserPromptSubmit",
            prompt="Use $codex-science to start a protein structure analysis",
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIsNotNone(output)
        context = self.additional_context(output)
        self.assertIn("Codex Science is active", context)
        self.assertIn("$codex-science", context)

        other_result, other_output = self.run_hook(
            "UserPromptSubmit",
            session_id="session-B",
            prompt="단백질 구조를 분석해줘",
        )
        self.assertEqual(0, other_result.returncode, other_result.stderr)
        self.assertIsNone(other_output)

    def test_later_prompt_self_invokes_without_repeated_activation(self) -> None:
        self.run_hook("UserPromptSubmit", prompt="Codex Science 시작")

        result, output = self.run_hook(
            "UserPromptSubmit",
            prompt="그 후보를 다른 구조 예측기로도 검증해줘",
        )

        self.assertEqual(0, result.returncode, result.stderr)
        context = self.additional_context(output)
        self.assertIn("implicitly invoke $codex-science", context)
        self.assertIn("Do not require the user to activate it again", context)

    def test_resume_and_compaction_restore_active_context(self) -> None:
        self.run_hook("UserPromptSubmit", prompt="activate Codex Science")

        for source in ("resume", "compact"):
            with self.subTest(source=source):
                result, output = self.run_hook("SessionStart", source=source)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn("Codex Science is active", self.additional_context(output))

    def test_stop_and_clear_remove_activation(self) -> None:
        self.run_hook("UserPromptSubmit", prompt="Codex Science 한 번 활성화")

        _, stop_output = self.run_hook(
            "UserPromptSubmit",
            prompt="이제 Codex Science 종료",
        )
        self.assertIn("Codex Science is inactive", self.additional_context(stop_output))
        _, later_output = self.run_hook(
            "UserPromptSubmit",
            prompt="이어서 분석해줘",
        )
        self.assertIsNone(later_output)

        self.run_hook("UserPromptSubmit", prompt="start Codex Science")
        _, clear_output = self.run_hook("SessionStart", source="clear")
        self.assertIn("Codex Science is inactive", self.additional_context(clear_output))
        _, after_clear = self.run_hook(
            "UserPromptSubmit",
            prompt="이어서 분석해줘",
        )
        self.assertIsNone(after_clear)

    def test_explicit_skill_stop_form_deactivates(self) -> None:
        self.run_hook("UserPromptSubmit", prompt="$codex-science 시작")

        _, output = self.run_hook(
            "UserPromptSubmit",
            prompt="$codex-science stop",
        )

        self.assertIn("Codex Science is inactive", self.additional_context(output))
        _, later_output = self.run_hook(
            "UserPromptSubmit",
            prompt="continue the analysis",
        )
        self.assertIsNone(later_output)

    def test_ordinary_discussion_does_not_activate_mode(self) -> None:
        result, output = self.run_hook(
            "UserPromptSubmit",
            prompt="Codex Science와 일반 Codex의 차이를 설명해줘",
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIsNone(output)

    def test_state_uses_hashed_session_name_and_never_stores_prompt(self) -> None:
        prompt = "$codex-science PRIVATE_EXPERIMENT_DESCRIPTION"
        result, _ = self.run_hook(
            "UserPromptSubmit",
            session_id="../../unsafe/session",
            prompt=prompt,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        files = [path for path in self.plugin_data.rglob("*") if path.is_file()]
        self.assertEqual(1, len(files))
        self.assertEqual(64, len(files[0].name))
        self.assertNotIn("..", files[0].as_posix())
        self.assertNotIn(prompt, files[0].read_text(encoding="utf-8"))
        self.assertEqual(0o600, stat.S_IMODE(files[0].stat().st_mode))

    def test_malformed_input_fails_closed_without_blocking_prompt(self) -> None:
        env = os.environ.copy()
        env["PLUGIN_DATA"] = str(self.plugin_data)
        result = subprocess.run(
            [sys.executable, str(self.script)],
            input="not-json",
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

        self.assertEqual(0, result.returncode)
        self.assertEqual("", result.stdout)
        self.assertEqual([], list(self.plugin_data.iterdir()))

    def test_inactive_markers_expire_without_reactivating_session(self) -> None:
        self.run_hook("UserPromptSubmit", prompt="Start Codex Science")
        marker = next(path for path in self.plugin_data.rglob("*") if path.is_file())
        expired = time.time() - (181 * 24 * 60 * 60)
        os.utime(marker, (expired, expired))

        _, output = self.run_hook(
            "UserPromptSubmit",
            prompt="continue the analysis",
        )

        self.assertIsNone(output)
        self.assertFalse(marker.exists())

    def test_plugin_bundles_session_hooks(self) -> None:
        config = json.loads(
            (self.repository_root / "hooks" / "hooks.json").read_text(encoding="utf-8")
        )

        self.assertEqual({"SessionStart", "UserPromptSubmit"}, set(config["hooks"]))
        serialized = json.dumps(config)
        self.assertIn("$PLUGIN_ROOT/scripts/science_session_hook.py", serialized)


if __name__ == "__main__":
    unittest.main()
