import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock


class UpdateEntryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        path = cls.root / "scripts" / "science_update_entry.py"
        spec = importlib.util.spec_from_file_location("science_update_entry", path)
        if spec is None or spec.loader is None:
            raise RuntimeError("could not load science_update_entry")
        cls.entry = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.entry)

    def test_hooks_use_strict_entry_and_preserve_stable_updater_marker(self) -> None:
        hooks = json.loads((self.root / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        commands = [
            item["command"]
            for event in ("SessionStart", "UserPromptSubmit")
            for group in hooks["hooks"][event]
            for item in group["hooks"]
        ]
        update_commands = [command for command in commands if "science_update_entry.py" in command]
        self.assertTrue(update_commands)
        self.assertTrue(
            all("CODEX_SCIENCE_STABLE_UPDATER" in command for command in update_commands)
        )
        self.assertTrue(
            all("science_update_hook.py" in command for command in update_commands)
        )

    def test_strict_candidate_runs_stable_check_then_complete_contract(self) -> None:
        candidate = self.root
        with (
            mock.patch.object(self.entry, "_original_candidate_self_check", return_value=True) as stable,
            mock.patch.object(
                self.entry.module,
                "_run",
                return_value=subprocess.CompletedProcess([], 0, "candidate contract: ok\n", ""),
            ) as run,
        ):
            self.assertTrue(self.entry.strict_candidate_self_check(candidate))
        stable.assert_called_once_with(candidate.resolve())
        command = run.call_args.args[0]
        self.assertEqual(sys.executable, command[0])
        self.assertIn("candidate_contract_check.py", command[1])
        self.assertEqual(["--root", str(candidate.resolve())], command[-2:])
        self.assertEqual(300, run.call_args.kwargs["timeout"])

    def test_stable_candidate_failure_short_circuits_contract(self) -> None:
        with (
            mock.patch.object(self.entry, "_original_candidate_self_check", return_value=False),
            mock.patch.object(self.entry.module, "_run") as run,
        ):
            self.assertFalse(self.entry.strict_candidate_self_check(self.root))
        run.assert_not_called()

    def test_bootstrap_uses_same_candidate_contract(self) -> None:
        bootstrap = (self.root / "scripts" / "bootstrap.sh").read_text(encoding="utf-8")
        self.assertIn("candidate_contract_check.py", bootstrap)


if __name__ == "__main__":
    unittest.main()
