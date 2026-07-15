import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codex_science.checkpoints import create_checkpoint, request_decision
from codex_science.sessions import session_key


class ScienceStopHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository_root = Path(__file__).resolve().parents[1]
        self.session_script = self.repository_root / "scripts" / "science_session_hook.py"
        self.stop_script = self.repository_root / "scripts" / "science_stop_hook.py"
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.plugin_data = self.root / "plugin-data"
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.run_dir = self.workspace / "artifacts" / "run-001"
        self.session_id = "session-A"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def env(self, *, idle_limit: int = 3) -> dict[str, str]:
        env = os.environ.copy()
        env["PLUGIN_DATA"] = str(self.plugin_data)
        env["CODEX_SCIENCE_MAX_IDLE_CONTINUATIONS"] = str(idle_limit)
        return env

    def activate(self) -> None:
        payload = {
            "cwd": str(self.workspace),
            "hook_event_name": "UserPromptSubmit",
            "model": "test-model",
            "permission_mode": "default",
            "session_id": self.session_id,
            "transcript_path": None,
            "prompt": "Start Codex Science",
            "turn_id": "turn-1",
        }
        result = subprocess.run(
            [sys.executable, str(self.session_script)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=self.env(),
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        output = json.loads(result.stdout)
        context = output["hookSpecificOutput"]["additionalContext"]
        match = re.search(r"--session-key ([0-9a-f]{64})", context)
        self.assertIsNotNone(match)
        self.active_key = match.group(1)

    def create(self) -> None:
        create_checkpoint(
            self.run_dir,
            goal="Review the evidence",
            deliverable="Verified report",
            done_criteria=["Sources checked", "Review complete"],
            steps=[("discover", "Discover"), ("review", "Review")],
            next_action="Search the second primary source",
            session_key=getattr(self, "active_key", session_key(self.session_id)),
        )

    def stop(self, *, session_id: str | None = None, idle_limit: int = 3):
        payload = {
            "cwd": str(self.workspace),
            "hook_event_name": "Stop",
            "model": "test-model",
            "permission_mode": "default",
            "session_id": session_id or self.session_id,
            "transcript_path": None,
            "turn_id": "turn-1",
            "stop_hook_active": False,
        }
        result = subprocess.run(
            [sys.executable, str(self.stop_script)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=self.env(idle_limit=idle_limit),
            check=False,
        )
        output = json.loads(result.stdout) if result.stdout.strip() else None
        return result, output

    def test_active_checkpoint_blocks_stop_and_supplies_next_action(self) -> None:
        self.activate()
        self.create()

        result, output = self.stop()

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("block", output["decision"])
        self.assertIn("Search the second primary source", output["reason"])
        self.assertIn(str(self.run_dir / "checkpoint.json"), output["reason"])
        self.assertIn("auto-continue 1/3", output["systemMessage"])

    def test_inactive_or_foreign_session_never_blocks(self) -> None:
        self.create()
        _, inactive = self.stop()
        self.assertIsNone(inactive)

        self.activate()
        _, foreign = self.stop(session_id="session-B")
        self.assertIsNone(foreign)

    def test_approval_gate_allows_stop_for_user_input(self) -> None:
        self.activate()
        self.create()
        request_decision(
            self.run_dir,
            questions=["Approve remote compute?"],
            reason="This allocates paid resources",
        )

        _, output = self.stop()

        self.assertIsNone(output)

    def test_idle_guard_has_escape_hatch_instead_of_infinite_loop(self) -> None:
        self.activate()
        self.create()

        _, first = self.stop(idle_limit=2)
        _, second = self.stop(idle_limit=2)
        _, exhausted = self.stop(idle_limit=2)

        self.assertEqual("block", first["decision"])
        self.assertEqual("block", second["decision"])
        self.assertNotIn("decision", exhausted)
        self.assertIn("safety limit", exhausted["systemMessage"])

    def test_corrupt_or_symlinked_checkpoint_fails_open(self) -> None:
        self.activate()
        self.run_dir.mkdir(parents=True)
        outside = self.root / "outside.json"
        outside.write_text("not-json", encoding="utf-8")
        (self.run_dir / "checkpoint.json").symlink_to(outside)

        result, output = self.stop()

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIsNone(output)

    def test_oversized_checkpoint_is_not_loaded_automatically(self) -> None:
        self.activate()
        self.create()
        path = self.run_dir / "checkpoint.json"
        path.write_text(path.read_text(encoding="utf-8") + (" " * 1_100_000), encoding="utf-8")

        result, output = self.stop()

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIsNone(output)


if __name__ == "__main__":
    unittest.main()
