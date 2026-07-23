import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class PythonRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repository_root = Path(__file__).resolve().parents[1]
        cls.launcher = cls.repository_root / "scripts" / "python_runtime.sh"

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.runtime_file = self.root / "runtime-python"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def executable(self, name: str, body: str) -> Path:
        path = self.bin / name
        path.write_text(f"#!/bin/sh\n{body}", encoding="utf-8")
        path.chmod(0o755)
        return path

    def environment(self) -> dict[str, str]:
        return {
            **os.environ,
            "CODEX_SCIENCE_RUNTIME_FILE": str(self.runtime_file),
            "PATH": f"{self.bin}:/usr/bin:/bin",
        }

    def test_launcher_prefers_recorded_managed_python(self) -> None:
        managed = self.executable(
            "managed-python",
            'if [ "${1:-}" = "-c" ]; then exit 0; fi\nprintf "managed:%s\\n" "$*"',
        )
        self.executable(
            "python3",
            'if [ "${1:-}" = "-c" ]; then exit 0; fi\nprintf "system:%s\\n" "$*"',
        )
        self.runtime_file.write_text(f"{managed}\n", encoding="utf-8")

        result = subprocess.run(
            ["bash", str(self.launcher), "example.py", "--flag"],
            capture_output=True,
            text=True,
            check=False,
            env=self.environment(),
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("managed:example.py --flag", result.stdout.strip())

    def test_launcher_rejects_python38_fallback(self) -> None:
        self.executable(
            "python3",
            'if [ "${1:-}" = "-c" ]; then exit 1; fi\nexit 97',
        )

        result = subprocess.run(
            ["bash", str(self.launcher), "example.py"],
            capture_output=True,
            text=True,
            check=False,
            env=self.environment(),
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("Python 3.11+", result.stderr)
        self.assertIn("installer", result.stderr)

    def test_runtime_contract_avoids_path_python_for_plugin_commands(self) -> None:
        installer = (self.repository_root / "scripts" / "install.sh").read_text(
            encoding="utf-8"
        )
        bootstrap = (self.repository_root / "scripts" / "bootstrap.sh").read_text(
            encoding="utf-8"
        )
        hooks = (self.repository_root / "hooks" / "hooks.json").read_text(
            encoding="utf-8"
        )
        mcp = (self.repository_root / ".mcp.json").read_text(encoding="utf-8")

        self.assertIn("uv python install", installer)
        self.assertIn("uv python find", installer)
        self.assertNotIn('python3 "$INSTALL_DIR/scripts/', installer)
        self.assertIn("python_runtime.sh", bootstrap)
        self.assertNotIn("python3", hooks)
        self.assertIn("python_runtime.sh", hooks)
        self.assertNotIn('"command": "python3"', mcp)
        self.assertIn("python_runtime.sh", mcp)


if __name__ == "__main__":
    unittest.main()
