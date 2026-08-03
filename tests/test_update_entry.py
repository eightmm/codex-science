import importlib.util
import io
import json
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
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
        candidate_path = cls.root / "scripts" / "candidate_contract_check.py"
        candidate_spec = importlib.util.spec_from_file_location(
            "candidate_contract_check", candidate_path
        )
        if candidate_spec is None or candidate_spec.loader is None:
            raise RuntimeError("could not load candidate_contract_check")
        cls.candidate = importlib.util.module_from_spec(candidate_spec)
        candidate_spec.loader.exec_module(cls.candidate)

    def test_hooks_use_one_stable_dispatcher_per_event(self) -> None:
        hooks = json.loads((self.root / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        for event in ("SessionStart", "UserPromptSubmit", "Stop"):
            commands = [
                item["command"]
                for group in hooks["hooks"][event]
                for item in group["hooks"]
            ]
            self.assertEqual(1, len(commands))
            self.assertIn("science_hook_dispatch.py", commands[0])

        dispatcher = (self.root / "scripts" / "science_hook_dispatch.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("science_update_entry.py", dispatcher)
        self.assertIn("--resolve-runtime", dispatcher)

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
        self.assertEqual(600, run.call_args.kwargs["timeout"])

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

    def test_candidate_contract_hides_successful_child_output(self) -> None:
        completed = subprocess.CompletedProcess(
            ["child-check"], 0, '{"large": "machine report"}\n', ""
        )
        output = io.StringIO()
        with (
            mock.patch.object(self.candidate.subprocess, "run", return_value=completed),
            redirect_stdout(output),
        ):
            self.candidate.run(["child-check"], cwd=self.root)

        self.assertEqual("", output.getvalue())

    def test_candidate_contract_preserves_failed_child_diagnostics(self) -> None:
        completed = subprocess.CompletedProcess(
            ["child-check"], 1, "validation summary\n", "specific failure\n"
        )
        with mock.patch.object(self.candidate.subprocess, "run", return_value=completed):
            with self.assertRaises(SystemExit) as raised:
                self.candidate.run(["child-check"], cwd=self.root)

        message = str(raised.exception)
        self.assertIn("candidate check failed: child-check", message)
        self.assertIn("validation summary", message)
        self.assertIn("specific failure", message)


if __name__ == "__main__":
    unittest.main()
