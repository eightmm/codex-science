import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
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

    def _invoke_cli(self, output: Path | None = None) -> subprocess.CompletedProcess[str]:
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
                "--output", str(output or self.output_path),
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

    def _check_source(self, source: str | bytes, *, execute: bool = True) -> dict:
        self.theorem.write_bytes(source.encode("utf-8") if isinstance(source, str) else source)

        def runner(command: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
            self.assertEqual(self.workspace, cwd)
            output = "Lean acceptance stub\n" if command[-1] == "--version" else ""
            return subprocess.CompletedProcess(command, 0, output, "")

        with mock.patch("codex_science.formal_proof.shutil.which", return_value="lean"):
            result = run_formal_proof_check(self.payload, workspace=self.workspace, execute=execute, runner=runner)
        if execute:
            validate_proof_receipt(result["proof_receipt"])
            self.assertEqual(0, result["proof_receipt"]["checker"]["exit_code"])
        return result

    def test_admitted_code_is_refused_across_lexical_boundaries(self) -> None:
        cases = (
            ("theorem bad : False := sorryAx False true", "sorryAx"),
            ("/- note -/ theorem t : True := sorry", "sorry"),
            ("/- /- -/ -/ theorem t : True := sorry", "sorry"),
            ("/- /- -/ sorry", "sorry"),
            ('def s := "--" theorem t : True := sorry', "sorry"),
            ("theorem t' : True := sorry", "sorry"),
            ("theorem t : True := by\n  admit", "admit"),
        )
        for source, admitted in cases:
            with self.subTest(source=source):
                result = self._check_source(source)
                self.assertEqual("failed", result["status"])
                self.assertEqual([admitted], result["admitted_constructs"])
                self.assertFalse(result["proof_receipt"]["checker"]["kernel_checked"])

    def test_code_requires_at_least_one_theorem_lemma_or_example(self) -> None:
        for source in ("", " \r\n\t", "-- comment\n-- another comment\n", "def x := 0",
                       "def x := 0 theorem t : True := trivial", "theorems t : True := trivial",
                       "@[simp theorem t : True := trivial",
                       '/- /--/ -/ #eval " -/ theorem t : True := trivial " -- "\n',
                       '/-/- -/ -- -/ theorem t : True := trivial\n'):
            with self.subTest(source=source):
                result = self._check_source(source)
                self.assertEqual("failed", result["status"])
                self.assertFalse(result["proof_receipt"]["checker"]["kernel_checked"])
                self.assertIn("No theorem declaration was found", " ".join(result["proof_receipt"]["limitations"]))

    def test_raw_line_declaration_heuristic_accepts_modifiers_and_comment_text(self) -> None:
        fixture = self.theorem.read_text(encoding="utf-8")
        for prefix in ("", "  ", "@[] ", "@[simp] ", "private ", "protected ", "noncomputable ", "nonrec ",
                       "@[simp] private noncomputable "):
            with self.subTest(prefix=prefix):
                result = self._check_source(prefix + fixture)
                self.assertEqual("passed", result["status"])
                self.assertEqual([], result["proof_receipt"]["limitations"])
        # This raw-line heuristic deliberately accepts a declaration that appears only in a comment.
        result = self._check_source("/-\ntheorem only_in_comment : True := trivial\n-/\ndef x := 0")
        self.assertEqual("passed", result["status"])
        self.assertEqual([], result["proof_receipt"]["limitations"])

    def test_raw_admission_scans_include_comments_and_strings(self) -> None:
        fixture = self.theorem.read_text(encoding="utf-8")
        for prefix, admitted in (
            ("-- no sorry here\n/- uses admit-free tactics -/\n", ["admit", "sorry"]),
            ("/-- sorry /- admit -/ sorryAx -/\n/-! admit -/\n", ["admit", "sorry", "sorryAx"]),
            ('#eval "sorry admit sorryAx -- /-"\n', ["admit", "sorry", "sorryAx"]),
            ('#eval "escaped \\\" sorry \\\\ admit"\n', ["admit", "sorry"]),
            ("/- outer /- inner -/ sorry -/", ["sorry"]),
        ):
            with self.subTest(prefix=prefix):
                result = self._check_source(prefix + fixture)
                self.assertEqual("failed", result["status"])
                self.assertEqual(admitted, result["admitted_constructs"])
                self.assertFalse(result["proof_receipt"]["checker"]["kernel_checked"])
        for prefix in ('/- -/\n#eval ""\n', '/-- -/\n/-! -/\n',
                       '/- outer /-- inner -/ -/\n', '#eval "plain -- /-"\n'):
            with self.subTest(prefix=prefix):
                result = self._check_source(prefix + fixture)
                self.assertEqual("passed", result["status"])
                self.assertEqual([], result["admitted_constructs"])
                self.assertEqual([], result["proof_receipt"]["limitations"])
        for declaration in ("lemma", "example"):
            with self.subTest(declaration=declaration):
                result = self._check_source(fixture.replace("theorem nat_add_zero", declaration + (" t" if declaration == "lemma" else "")))
                self.assertEqual("passed", result["status"])

    def test_doc_comment_overlap_cannot_hide_admitted_code(self) -> None:
        suffix = '/--/ " -/ theorem t : False := sorry -- "'
        for source in (suffix, "theorem ok : True := trivial\n" + suffix):
            with self.subTest(source=source):
                result = self._check_source(source)
                self.assertEqual("failed", result["status"])
                self.assertEqual(["sorry"], result["admitted_constructs"])
                self.assertFalse(result["proof_receipt"]["checker"]["kernel_checked"])

    def test_source_hashes_use_raw_bytes_in_preview_and_receipt(self) -> None:
        fixture = (ROOT / FIXTURE).parent.joinpath(self.payload["theorem_file"]).read_bytes()
        lf_hash = hashlib.sha256(fixture).hexdigest()
        for source in (fixture, fixture.replace(b"\n", b"\r\n")):
            with self.subTest(source=source):
                digest = hashlib.sha256(source).hexdigest()
                preview = self._check_source(source, execute=False)
                self.assertEqual(digest, preview["theorem_file_sha256"])
                result = self._check_source(source)
                self.assertEqual("passed", result["status"])
                self.assertEqual(digest, result["theorem_file_sha256"])
                self.assertEqual([{"path": self.payload["theorem_file"], "sha256": digest}], result["proof_receipt"]["evidence"])
                self.assertTrue(result["proof_receipt"]["checker"]["source_unchanged"])
        self.assertEqual(lf_hash, self._check_source(fixture)["theorem_file_sha256"])

    def test_checker_sorry_warning_is_refused(self) -> None:
        warning = "Main.lean:1:8: warning: declaration uses 'sorry'\n"
        for stdout, stderr, refused in (
            (warning, "", True), ("", warning, True), (warning, warning, True),
            ("", "", False), ("Main.lean:1:8: warning: unused variable `n`\n", "", False),
        ):
            def runner(command: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
                if command[-1] == "--version":
                    return subprocess.CompletedProcess(command, 0, "Lean acceptance stub\n", "")
                return subprocess.CompletedProcess(command, 0, stdout, stderr)

            with self.subTest(stdout=stdout, stderr=stderr):
                with mock.patch("codex_science.formal_proof.shutil.which", return_value="lean"):
                    result = run_formal_proof_check(self.payload, workspace=self.workspace, runner=runner)
                receipt = result["proof_receipt"]
                validate_proof_receipt(receipt)
                self.assertEqual(0, receipt["checker"]["exit_code"])
                self.assertEqual([], result["admitted_constructs"])
                if refused:
                    self.assertEqual("failed", result["status"])
                    self.assertEqual("failed", receipt["status"])
                    self.assertFalse(receipt["checker"]["kernel_checked"])
                    self.assertEqual(["sorry"], receipt["admitted_constructs"])
                    self.assertIn("declaration that uses 'sorry'", " ".join(receipt["limitations"]))
                else:
                    self.assertEqual("passed", result["status"])
                    self.assertEqual([], receipt["admitted_constructs"])

    def test_axiom_and_unsafe_scans_accept_declaration_prefixes(self) -> None:
        fixture = self.theorem.read_text(encoding="utf-8")
        for prefix in ("", "  ", "@[] ", "@[simp] ", "private ", "protected ", "noncomputable ", "@[simp] private noncomputable "):
            for keyword in ("axiom", "opaque"):
                with self.subTest(prefix=prefix, keyword=keyword):
                    result = self._check_source(fixture + f"{prefix}{keyword} trusted : Nat\n")
                    self.assertEqual("passed", result["status"])
                    self.assertEqual(["trusted"], result["declared_axioms"])
                    self.assertEqual(["trusted"], result["proof_receipt"]["axioms"])
            with self.subTest(prefix=prefix, keyword="unsafe"):
                result = self._check_source(fixture + f"{prefix}unsafe def unchecked : Nat := 0\n")
                self.assertEqual("failed", result["status"])
                self.assertEqual(1, result["unsafe_declaration_count"])
        for suffix in ("def axiom_like : Nat := 0\n", "-- axiom trusted : Nat\n", "privateaxiom trusted : Nat\n"):
            with self.subTest(suffix=suffix):
                result = self._check_source(fixture + suffix)
                self.assertEqual("passed", result["status"])
                self.assertEqual([], result["declared_axioms"])

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

    def test_timeout_after_output_kills_process_group_and_keeps_failed_receipt(self) -> None:
        sleep = shutil.which("sleep")
        if sleep is None or not hasattr(os, "killpg"):
            self.skipTest("requires POSIX sleep and process groups")
        pid_file = self.root / "grandchild.pid"
        self.payload["timeout_seconds"] = 1
        self._write_lean(
            f"'{sleep}' 600 &\n"
            f"printf '%s' \"$!\" > '{pid_file}'\n"
            "printf 'partial output \\377\\n'\n"
            f"exec '{sleep}' 600\n"
        )

        def cleanup() -> None:
            if pid_file.exists():
                try:
                    os.kill(int(pid_file.read_text(encoding="utf-8")), 9)
                except (ProcessLookupError, ValueError):
                    pass

        self.addCleanup(cleanup)
        result = self._assert_failed_cli("checker exceeded the declared timeout")
        checker = result["proof_receipt"]["checker"]
        self.assertTrue(checker["timed_out"])
        self.assertEqual(124, checker["exit_code"])
        self.assertIn("partial output \ufffd", checker["stdout_excerpt"])
        pid = int(pid_file.read_text(encoding="utf-8"))
        deadline = time.monotonic() + float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120"))
        while True:
            try:
                os.kill(pid, 0)
                state = Path(f"/proc/{pid}/stat")
                if state.exists() and state.read_text(encoding="utf-8").rsplit(")", 1)[-1].split()[0] == "Z":
                    break
            except (ProcessLookupError, FileNotFoundError):
                break
            self.assertLess(time.monotonic(), deadline, "grandchild survived the checker timeout")
            time.sleep(0.05)

    def test_timeout_records_timed_out_when_process_group_kill_is_refused(self) -> None:
        sleep = shutil.which("sleep")
        if sleep is None:
            self.skipTest("requires POSIX sleep")
        self.payload["timeout_seconds"] = 1
        self._write_lean(f"exec '{sleep}' {int(float(os.environ.get('OMS_TEST_CALL_TIMEOUT', '120')))}\n")
        with mock.patch.dict(os.environ, {"PATH": str(self.bin_path)}), \
                mock.patch("codex_science.formal_proof.os.killpg", side_effect=PermissionError("refused"), create=True):
            result = run_formal_proof_check(self.payload, workspace=self.workspace)
        receipt = result["proof_receipt"]
        validate_proof_receipt(receipt)
        self.assertEqual("failed", receipt["status"])
        self.assertTrue(receipt["checker"]["timed_out"])
        self.assertEqual(124, receipt["checker"]["exit_code"])
        self.assertNotIn("checker could not be started", " ".join(receipt["limitations"]))

    def test_timeout_with_byte_output_keeps_failed_receipt(self) -> None:
        def runner(command: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
            if command[-1] == "--version":
                return subprocess.CompletedProcess(command, 0, "Lean acceptance stub\n", "")
            raise subprocess.TimeoutExpired(command, timeout, output=b"warning: declaration uses 'sorry'\n\xff", stderr=b"\xfe")

        with mock.patch("codex_science.formal_proof.shutil.which", return_value="lean"):
            result = run_formal_proof_check(self.payload, workspace=self.workspace, runner=runner)
        receipt = result["proof_receipt"]
        validate_proof_receipt(receipt)
        self.assertEqual("failed", receipt["status"])
        self.assertTrue(receipt["checker"]["timed_out"])
        self.assertEqual(["sorry"], receipt["admitted_constructs"])
        self.assertEqual("\ufffd", receipt["checker"]["stderr_excerpt"])

    def test_version_probe_failure_is_recorded_once_and_start_failure_keeps_receipt(self) -> None:
        for version_error, recorded in (
            (subprocess.TimeoutExpired(["lean", "--version"], 30), "unavailable"),
            (OSError("probe failed"), "unavailable"),
            (None, "unknown"),
        ):
            calls: list[list[str]] = []

            def runner(command: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
                calls.append(command)
                if command[-1] == "--version" and version_error is not None:
                    raise version_error
                return subprocess.CompletedProcess(command, 0, "", "")

            with self.subTest(error=type(version_error).__name__):
                with mock.patch("codex_science.formal_proof.shutil.which", return_value="lean"):
                    result = run_formal_proof_check(self.payload, workspace=self.workspace, runner=runner)
                self.assertEqual(1, sum(command[-1] == "--version" for command in calls))
                receipt = result["proof_receipt"]
                validate_proof_receipt(receipt)
                self.assertEqual(recorded, receipt["checker"]["tool_version"])
                self.assertEqual("failed", receipt["status"])
                self.assertFalse(receipt["checker"]["kernel_checked"])
                self.assertIn("checker version could not be determined", " ".join(receipt["limitations"]))

        def missing(command: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
            raise FileNotFoundError(command[0])

        with mock.patch("codex_science.formal_proof.shutil.which", return_value="lean"):
            result = run_formal_proof_check(self.payload, workspace=self.workspace, runner=missing)
        receipt = result["proof_receipt"]
        validate_proof_receipt(receipt)
        self.assertEqual("failed", receipt["status"])
        self.assertIsNone(receipt["checker"]["exit_code"])
        self.assertIn("checker could not be started", " ".join(receipt["limitations"]))

    def test_admitted_constructs_in_workspace_imports_are_refused(self) -> None:
        fixture = self.theorem.read_text(encoding="utf-8")
        (self.workspace / "Sub").mkdir()
        (self.workspace / "Helper.lean").write_text("import Sub.Deep\ntheorem helper : True := trivial\n", encoding="utf-8")
        deep = self.workspace / "Sub" / "Deep.lean"
        deep.write_text("import Helper\ntheorem deep : False := sorry\n", encoding="utf-8")
        result = self._check_source("import Mathlib.Tactic\nimport Helper\n" + fixture)
        self.assertEqual("failed", result["status"])
        self.assertEqual(["sorry"], result["admitted_constructs"])
        self.assertEqual(["sorry"], result["proof_receipt"]["admitted_constructs"])
        self.assertIn("imported workspace module Sub/Deep.lean contains admitted", " ".join(result["proof_receipt"]["limitations"]))
        self.assertEqual(["sorry"], self._check_source("import Helper\n" + fixture, execute=False)["admitted_constructs"])
        dotted = self.workspace / "a.b.lean"
        dotted.write_text("theorem dotted : False := sorry\n", encoding="utf-8")
        result = self._check_source("import «a.b»\n" + fixture)
        self.assertEqual("failed", result["status"])
        self.assertIn("imported workspace module a.b.lean contains admitted", " ".join(result["proof_receipt"]["limitations"]))
        dotted.unlink()

        deep.write_text("theorem deep : True := trivial\n", encoding="utf-8")
        result = self._check_source("import Mathlib.Tactic\nimport Helper\n" + fixture)
        self.assertEqual("passed", result["status"])
        self.assertEqual([], result["proof_receipt"]["limitations"])

        outside = self.root / "Outside.lean"
        outside.write_text("theorem outside : False := sorry\n", encoding="utf-8")
        (self.workspace / "Linked.lean").symlink_to(outside)
        (self.workspace / "Away").symlink_to(self.root, target_is_directory=True)
        for source, unscanned in (("import Linked\n", "Linked.lean"), ("import Away.Outside\n", "Away/Outside.lean")):
            with self.subTest(source=source):
                result = self._check_source(source + fixture)
                self.assertEqual("failed", result["status"])
                self.assertFalse(result["proof_receipt"]["checker"]["kernel_checked"])
                self.assertIn(f"{unscanned} could not be scanned", " ".join(result["proof_receipt"]["limitations"]))
        for source in ("import Outside\n", "import «..».Outside\n", "import Away.Missing\n"):
            with self.subTest(source=source):
                self.assertEqual("passed", self._check_source(source + fixture)["status"])

        deep.write_bytes(b"-- " + b"x" * (2 * 1024 * 1024 - 2) + b"\n")
        result = self._check_source("import Helper\n" + fixture)
        self.assertEqual("failed", result["status"])
        self.assertIn("Sub/Deep.lean could not be scanned", " ".join(result["proof_receipt"]["limitations"]))
        deep.write_bytes(b"-- " + b"x" * (2 * 1024 * 1024 - 4) + b"\n")
        self.assertEqual("passed", self._check_source("import Helper\n" + fixture)["status"])

    def test_declaration_scans_stay_linear_on_blank_lines(self) -> None:
        script = (
            "import time\n"
            "from codex_science import formal_proof as f\n"
            "start = time.perf_counter()\n"
            "for source in ('\\n' * 200_000, 'private\\n' * 200_000):\n"
            "    for name in ('THEOREM_RE', 'AXIOM_RE', 'UNSAFE_RE', 'ADMITTED_RE', 'IMPORT_RE'):\n"
            "        getattr(f, name).findall(source)\n"
            "print(time.perf_counter() - start)\n"
        )
        completed = subprocess.run(
            [sys.executable, "-c", script],
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            capture_output=True,
            text=True,
            timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120")),
            check=True,
        )
        self.assertLess(float(completed.stdout), 1.0)
        result = self._check_source("@[simp,\n  reducible]\nprivate\n  noncomputable axiom split : Nat\nprivate\ntheorem t : True := trivial\n")
        self.assertEqual("passed", result["status"])
        self.assertEqual(["split"], result["declared_axioms"])
        self.assertEqual(1, self._check_source("theorem t : True := trivial\nprivate\nunsafe def u : Nat := 0\n")["unsafe_declaration_count"])

    def test_assumptions_must_be_a_list_of_non_empty_strings(self) -> None:
        for value in ("trusted", None, 7, [7], [""], ["  "], {"axiom x": True}):
            for execute in (False, True):
                with self.subTest(value=value, execute=execute):
                    with self.assertRaisesRegex(ValueError, "assumptions must be a list of non-empty strings"):
                        run_formal_proof_check({**self.payload, "assumptions": value}, workspace=self.workspace, execute=execute)
        result = self._check_source(self.theorem.read_text(encoding="utf-8"))
        self.assertEqual([], result["proof_receipt"]["assumptions"])
        self.payload["assumptions"] = ["axiom trusted : Nat"]
        self.assertEqual(["axiom trusted : Nat"], self._check_source(self.theorem.read_text(encoding="utf-8"))["proof_receipt"]["assumptions"])

    def test_non_utf8_output_and_deleted_source_keep_failed_receipt(self) -> None:
        self._write_lean("printf 'error: bad \\377\\n' >&2\nexit 1\n")
        result = self._assert_failed_cli("error: bad \\ufffd")
        self.assertEqual(1, result["proof_receipt"]["checker"]["exit_code"])
        remove = shutil.which("rm")
        if remove is None:
            self.skipTest("requires POSIX rm")
        self._write_lean(f"'{remove}' Main.lean\nexit 0\n")
        result = self._assert_failed_cli("theorem source changed during checking")
        self.assertFalse(result["proof_receipt"]["checker"]["source_unchanged"])

    def test_output_cannot_replace_theorem_or_input(self) -> None:
        original = self.theorem.read_bytes()
        for target, label in ((self.theorem, "theorem"), (self.input_path, "input")):
            with self.subTest(target=label):
                completed = self._invoke_cli(target)
                self.assertEqual(1, completed.returncode)
                self.assertIn("output path would overwrite input", completed.stderr)
                self.assertEqual(original, self.theorem.read_bytes())
                self.assertEqual(self.payload, json.loads(self.input_path.read_text(encoding="utf-8")))
        self.assertFalse(self.output_path.exists())

    def test_query_placeholders_are_refused_at_line_and_file_end(self) -> None:
        for source, admitted in (
            ("theorem t : True := by exact?", "exact?"),
            ("theorem t : True := by exact?\n", "exact?"),
            ("theorem t : True := by exact ?\n", "exact ?"),
            ("theorem t : True := by\n  by_contra' ?", "by_contra' ?"),
            ("theorem t : True := by (exact?)", "exact?"),
        ):
            with self.subTest(source=source):
                result = self._check_source(source)
                self.assertEqual("failed", result["status"])
                self.assertEqual([admitted], result["admitted_constructs"])
        self.assertEqual("passed", self._check_source("theorem t : True := by exact?_x trivial\n")["status"])

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
