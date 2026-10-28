import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from codex_science.formal_proof import run_formal_proof_check
from codex_science.math_contracts import validate_proof_receipt


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = "examples/formal-theorem-proving/input.json"
SEEDED_FAILURE_TESTS = {
    "sorry-placeholder": "test_sorry_placeholder_is_refused",
    "admit-placeholder": "test_admit_placeholder_is_refused",
    "unsafe-declaration": "test_unsafe_declaration_is_refused",
    "nonzero-kernel-exit": "test_nonzero_kernel_exit_is_refused",
    "source-mutation": "test_source_mutation_is_refused",
    "checker-timeout": "test_checker_timeout_is_refused",
}


class FormalTheoremProvingAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.payload = json.loads((ROOT / FIXTURE).read_text(encoding="utf-8"))
        self.theorem = self.workspace / self.payload["theorem_file"]
        shutil.copyfile((ROOT / FIXTURE).parent / self.payload["theorem_file"], self.theorem)
        self.input_path = self.root / "input.json"
        self.output_path = self.root / "receipt.json"
        self.bin_path = self.root / "bin"
        self.bin_path.mkdir()
        self.lean = self.bin_path / "lean"
        self._write_lean("exit 0\n")

    def _write_lean(self, body: str) -> None:
        self.lean.write_text(
            "#!/bin/sh\n"
            'if [ "$1" = "--version" ]; then\n'
            "  printf '%s\\n' 'Lean acceptance stub (no real kernel)'\n"
            "  exit 0\n"
            "fi\n"
            + body,
            encoding="utf-8",
        )
        self.lean.chmod(0o755)

    def _invoke_cli(self) -> subprocess.CompletedProcess[str]:
        self.input_path.write_text(json.dumps(self.payload), encoding="utf-8")
        # An isolated PATH prevents accidental use of any installed Lean/Lake.
        environment = {
            "PATH": str(self.bin_path),
            "HOME": str(self.root),
            "TMPDIR": str(self.root),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        return subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/check_formal_proof.py"),
                str(self.input_path),
                "--workspace", str(self.workspace),
                "--output", str(self.output_path),
                "--require-passed",
            ],
            cwd=self.root,
            env=environment,
            capture_output=True,
            text=True,
            timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120")),
            check=False,
        )

    def _read_receipt(self) -> dict:
        result = json.loads(self.output_path.read_text(encoding="utf-8"))
        validate_proof_receipt(result["proof_receipt"])
        return result

    def _assert_failed_cli(self, fragment: str) -> dict:
        completed = self._invoke_cli()
        self.assertEqual(1, completed.returncode, completed.stderr)
        result = self._read_receipt()
        self.assertEqual("failed", result["status"])
        receipt = result["proof_receipt"]
        self.assertEqual("failed", receipt["status"])
        self.assertFalse(receipt["checker"]["kernel_checked"])
        self.assertIn(fragment, json.dumps(receipt))
        return result

    def test_fixture_passes_public_cli_with_hashed_receipt(self) -> None:
        completed = self._invoke_cli()
        self.assertEqual(0, completed.returncode, completed.stderr)
        result = self._read_receipt()
        receipt = result["proof_receipt"]
        self.assertEqual("passed", result["status"])
        self.assertEqual("passed", receipt["status"])
        self.assertEqual(self.payload["check_id"], result["check_id"])
        self.assertEqual(self.payload["claim_id"], result["claim_id"])
        self.assertEqual(self.payload["receipt_id"], receipt["receipt_id"])
        self.assertEqual("formal-kernel", receipt["kind"])
        self.assertEqual(["lean", "Main.lean"], result["command"])
        self.assertEqual("lean", result["command_mode"])
        source_hash = hashlib.sha256(self.theorem.read_bytes()).hexdigest()
        statement_hash = hashlib.sha256(self.payload["statement"].encode("utf-8")).hexdigest()
        self.assertEqual(source_hash, result["theorem_file_sha256"])
        self.assertEqual(statement_hash, result["statement_sha256"])
        self.assertEqual(statement_hash, receipt["statement_sha256"])
        self.assertEqual([{"path": "Main.lean", "sha256": source_hash}], receipt["evidence"])
        self.assertEqual([], receipt["admitted_constructs"])
        self.assertEqual([], receipt["axioms"])
        self.assertEqual([], receipt["limitations"])
        checker = receipt["checker"]
        self.assertTrue(checker["kernel_checked"])
        self.assertTrue(checker["source_unchanged"])
        self.assertFalse(checker["timed_out"])
        self.assertEqual(0, checker["exit_code"])
        self.assertEqual("lean", checker["tool"])
        self.assertEqual("Lean acceptance stub (no real kernel)", checker["tool_version"])
        for field in ("stdout_sha256", "stderr_sha256"):
            self.assertEqual(hashlib.sha256(b"").hexdigest(), checker[field])

    def test_sorry_placeholder_is_refused(self) -> None:
        self.theorem.write_text(self.theorem.read_text(encoding="utf-8").replace("rfl", "sorry"), encoding="utf-8")
        result = self._assert_failed_cli("admitted or placeholder proof constructs")
        self.assertEqual(["sorry"], result["admitted_constructs"])
        self.assertEqual(0, result["proof_receipt"]["checker"]["exit_code"])

    def test_admit_placeholder_is_refused(self) -> None:
        self.theorem.write_text(self.theorem.read_text(encoding="utf-8").replace("rfl", "admit"), encoding="utf-8")
        result = self._assert_failed_cli("admitted or placeholder proof constructs")
        self.assertEqual(["admit"], result["admitted_constructs"])
        self.assertEqual(0, result["proof_receipt"]["checker"]["exit_code"])

    def test_unsafe_declaration_is_refused(self) -> None:
        with self.theorem.open("a", encoding="utf-8") as handle:
            handle.write("unsafe def unchecked : Nat := 0\n")
        result = self._assert_failed_cli("source contains unsafe declarations")
        self.assertEqual(1, result["unsafe_declaration_count"])
        self.assertEqual(0, result["proof_receipt"]["checker"]["exit_code"])

    def test_nonzero_kernel_exit_is_refused(self) -> None:
        self.theorem.write_text(self.theorem.read_text(encoding="utf-8").replace("rfl", "exact True.intro"), encoding="utf-8")
        self._write_lean("printf '%s\\n' 'error: type mismatch' >&2\nexit 1\n")
        result = self._assert_failed_cli("error: type mismatch")
        self.assertEqual(1, result["proof_receipt"]["checker"]["exit_code"])
        self.assertEqual([], result["admitted_constructs"])

    def test_source_mutation_is_refused(self) -> None:
        self._write_lean("printf '%s\\n' '-- changed during checking' >> Main.lean\nexit 0\n")
        result = self._assert_failed_cli("theorem source changed during checking")
        checker = result["proof_receipt"]["checker"]
        self.assertEqual(0, checker["exit_code"])
        self.assertFalse(checker["source_unchanged"])
        self.assertNotEqual(result["theorem_file_sha256"], hashlib.sha256(self.theorem.read_bytes()).hexdigest())

    def test_checker_timeout_is_refused(self) -> None:
        # Inject the timeout event so the test has no sleep or timing race.
        def runner(command: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
            self.assertEqual(self.workspace, cwd)
            if command[-1] == "--version":
                return subprocess.CompletedProcess(command, 0, "Lean acceptance stub\n", "")
            self.assertEqual(self.payload["timeout_seconds"], timeout)
            raise subprocess.TimeoutExpired(command, timeout)

        with mock.patch("codex_science.formal_proof.shutil.which", return_value=str(self.lean)):
            result = run_formal_proof_check(self.payload, workspace=self.workspace, runner=runner)
        receipt = result["proof_receipt"]
        validate_proof_receipt(receipt)
        self.assertEqual("failed", result["status"])
        self.assertEqual("failed", receipt["status"])
        self.assertIn("checker exceeded the declared timeout", " ".join(receipt["limitations"]))
        self.assertTrue(receipt["checker"]["timed_out"])
        self.assertEqual(124, receipt["checker"]["exit_code"])
        self.assertFalse(receipt["checker"]["kernel_checked"])

    def test_missing_lean_is_unavailable(self) -> None:
        self.lean.unlink()
        completed = self._invoke_cli()
        self.assertEqual(1, completed.returncode, completed.stderr)
        result = self._read_receipt()
        self.assertEqual("unavailable", result["status"])
        self.assertEqual("unavailable", result["proof_receipt"]["status"])
        self.assertFalse(result["tool_available"])
        checker = result["proof_receipt"]["checker"]
        self.assertFalse(checker["kernel_checked"])
        self.assertIsNone(checker["exit_code"])
        self.assertIn("Lean executable is unavailable", " ".join(result["proof_receipt"]["limitations"]))

    def test_declared_axiom_is_a_limitation_not_a_seeded_failure(self) -> None:
        with self.theorem.open("a", encoding="utf-8") as handle:
            handle.write("axiom extra_assumption : True\n")
        completed = self._invoke_cli()
        self.assertEqual(0, completed.returncode, completed.stderr)
        result = self._read_receipt()
        self.assertEqual("passed", result["status"])
        self.assertEqual(["extra_assumption"], result["declared_axioms"])
        self.assertEqual(["extra_assumption"], result["proof_receipt"]["axioms"])
        self.assertIn("explicit trust-boundary review", " ".join(result["proof_receipt"]["limitations"]))

    def test_quality_declaration_names_executable_seeded_tests(self) -> None:
        quality = json.loads((ROOT / "authored-skills/formal-theorem-proving/quality.json").read_text(encoding="utf-8"))
        self.assertEqual("L4", quality["declared_maturity"])
        self.assertEqual([FIXTURE], quality["acceptance_fixtures"])
        self.assertEqual(set(SEEDED_FAILURE_TESTS), set(quality["seeded_failures"]))
        self.assertEqual(len(SEEDED_FAILURE_TESTS), len(quality["seeded_failures"]))
        self.assertIn("tests/test_math_research_runtime.py", quality["test_files"])
        self.assertIn("tests/test_formal_theorem_proving_acceptance.py", quality["test_files"])
        self.assertIn("deterministic software validation", " ".join(quality["limitations"]))
        discovered = unittest.defaultTestLoader.getTestCaseNames(type(self))
        for name, method in SEEDED_FAILURE_TESTS.items():
            with self.subTest(seeded_failure=name):
                self.assertIn(method, discovered)
                self.assertTrue(callable(getattr(type(self), method, None)))


if __name__ == "__main__":
    unittest.main()
