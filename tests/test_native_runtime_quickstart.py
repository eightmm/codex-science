"""Run the first three native runtime quickstart examples offline."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "NATIVE_RUNTIME_QUICKSTART.md"


class NativeRuntimeQuickstartTests(unittest.TestCase):
    def test_sections_one_through_three_run_from_prepared_inputs(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        for restricted_path in (False, True):
            with self.subTest(restricted_path=restricted_path):
                self._run_document(text, restricted_path=restricted_path)

    def test_removing_section_one_preparation_block_fails(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        section = re.search(r"(?ms)^## 1\..*?(?=^## |\Z)", text).group()
        preparation = re.search(r"(?ms)^```bash\s*\n.*?^```\s*\n", section).group()
        mutated = text.replace(preparation, "", 1)
        with self.assertRaisesRegex(AssertionError, "section 1 must prepare and hash the PDB first"):
            self._run_document(mutated)

    def test_removing_pdb_heredoc_fails(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        mutated, count = re.subn(
            r"(?ms)^cat > artifacts/run/receptor\.pdb <<'PDB'(?: \|\| exit 1)?\n.*?^PDB\n",
            "",
            text,
            count=1,
        )
        self.assertEqual(1, count)
        with self.assertRaises(AssertionError):
            self._run_document(mutated)

    def test_changed_pdb_content_uses_documented_digest_output(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("11.000  12.000  13.000", text)
        self._run_document(text.replace("11.000  12.000  13.000", "14.000  15.000  16.000", 1))

    def test_preexisting_preparation_destinations_are_preserved(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        sections = self._sections(text)
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            plugin_root = base / "plugin root"
            plugin_root.symlink_to(ROOT, target_is_directory=True)

            workspace_parent = base / "workspace-parent"
            workspace_parent.mkdir()
            workspace = workspace_parent / "codex-science-quickstart"
            workspace.mkdir()
            workspace_marker = workspace / "marker.txt"
            workspace_marker.write_bytes(b"existing workspace")
            workspace_setup = re.findall(
                r"(?ms)^```bash\s*\n(.*?)^```",
                text.split("## 1.", 1)[0],
            )[0]
            result = subprocess.run(
                ["bash", "-e", "-c", workspace_setup], cwd=workspace_parent,
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertEqual(b"existing workspace", workspace_marker.read_bytes())

            cases = (
                (1, Path("artifacts/run/receptor.pdb"), b"existing PDB"),
                (2, Path("artifacts/run-001/fixture.txt"), b"existing fixture"),
                (3, Path("artifacts/run/job-spec.json"), b"existing job spec"),
            )
            for section_number, relative_path, original_bytes in cases:
                work = base / f"collision-{section_number}"
                work.mkdir()
                destination = work / relative_path
                destination.parent.mkdir(parents=True)
                destination.write_bytes(original_bytes)
                preparation = re.findall(
                    r"(?ms)^```bash\s*\n(.*?)^```",
                    sections[section_number - 1],
                )[0].replace("<plugin-root>", str(plugin_root))
                result = subprocess.run(
                    ["bash", "-e", "-c", preparation], cwd=work,
                    capture_output=True, text=True, check=False,
                )
                self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertEqual(original_bytes, destination.read_bytes())

    def _run_document(self, text: str, *, restricted_path: bool = False) -> None:
        sections = self._sections(text)
        self.assertEqual(3, len(sections), "quickstart sections 1-3 must exist")
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(ROOT / "src")
        environment["CODEX_SCIENCE_PYTHON"] = sys.executable
        environment["PYTHONDONTWRITEBYTECODE"] = "1"

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            if restricted_path:
                shim = base / "bin"
                shim.mkdir()
                for name in ("bash", "mkdir", "cat", "cp"):
                    executable = shutil.which(name)
                    self.assertIsNotNone(executable, name)
                    (shim / name).symlink_to(executable)
                environment["PATH"] = str(shim)
                self.assertIsNone(shutil.which("python3", path=environment["PATH"]))
            plugin_root = base / "plugin root"
            plugin_root.symlink_to(ROOT, target_is_directory=True)
            preamble = re.findall(
                r"(?ms)^```bash\s*\n(.*?)^```",
                text.split("## 1.", 1)[0],
            )
            self.assertEqual(1, len(preamble), "quickstart workspace setup is required")
            result = subprocess.run(
                ["bash", "-e", "-c", preamble[0]], cwd=base, env=environment,
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            work = base / "codex-science-quickstart"
            self.assertTrue(work.is_dir())
            executed_commands = 1
            for index, section in enumerate(sections, start=1):
                scripts = re.findall(r"(?ms)^```bash\s*\n(.*?)^```", section)
                self.assertTrue(scripts, f"section {index} has no bash examples")
                if index == 1:
                    self.assertIn(
                        '"<plugin-root>/scripts/python_runtime.sh" -c \'import hashlib; print(hashlib.sha256(open("artifacts/run/receptor.pdb", "rb").read()).hexdigest(), " artifacts/run/receptor.pdb")\'', scripts[0],
                        "section 1 must prepare and hash the PDB first",
                    )
                for script in scripts:
                    for option, value in re.findall(
                        r"--(output|state-dir|database|spec|manifest)\s+([^\s\\]+)",
                        script,
                    ):
                        self.assertFalse(
                            Path(value).is_absolute(),
                            f"section {index} writes or reads outside its temporary directory via --{option}",
                        )
                job_id = None
                for script_index, script in enumerate(scripts):
                    script = script.replace("<plugin-root>", str(plugin_root))
                    for command in (part for part in script.split("\n\n") if part.strip()):
                        if index == 1 and script_index > 0:
                            command = command.replace("<manifest-sha256>", digest)
                        if job_id:
                            command = command.replace("<job-id>", job_id)
                        result = subprocess.run(
                            ["bash", "-e", "-c", command], cwd=work, env=environment,
                            capture_output=True, text=True, check=False,
                        )
                        executed_commands += 1
                        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                        if index == 1 and '"<plugin-root>/scripts/python_runtime.sh" -c \'import hashlib; print(hashlib.sha256(open("artifacts/run/receptor.pdb", "rb").read()).hexdigest(), " artifacts/run/receptor.pdb")\''.replace("<plugin-root>", str(plugin_root)) in command:
                            digest = result.stdout.split()[0]
                        if index == 3 and " wait " in f" {command} ":
                            terminal = json.loads((work / "artifacts/run/terminal.json").read_text())
                            self.assertEqual("completed", terminal["state"])
                            self.assertEqual(0, terminal["exit_code"])
                        if index == 3 and " collect " in f" {command} ":
                            collected = json.loads((work / "artifacts/run/collected.json").read_text())
                            self.assertEqual("completed", collected["state"])
                            self.assertEqual(0, collected["exit_code"])
                        if index == 3 and " submit " in f" {command} ":
                            submitted = json.loads((work / "artifacts/run/submitted.json").read_text())
                            job_id = submitted["job_id"]
        self.assertEqual(15, executed_commands)

    @staticmethod
    def _sections(text: str) -> list[str]:
        sections = {
            match.group(1).split(". ", 1)[0]: match.group(2)
            for match in re.finditer(r"(?ms)^## ([^\n]+)\n(.*?)(?=^## |\Z)", text)
        }
        return [sections.get(str(index), "") for index in range(1, 4)]


if __name__ == "__main__":
    unittest.main()
