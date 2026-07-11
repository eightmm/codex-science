import json
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ComputeProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository_root = Path(__file__).resolve().parents[1]
        self.script = self.repository_root / "scripts" / "compute_probe.py"

    def test_probe_reports_safe_machine_capabilities(self) -> None:
        result = subprocess.run(
            [sys.executable, str(self.script)],
            cwd=self.repository_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(1, report["schema_version"])
        self.assertEqual({"system", "release", "machine"}, set(report["platform"]))
        self.assertEqual(
            {"cpu_count", "memory_bytes", "disk_free_bytes"},
            set(report["resources"]),
        )
        for tool in (
            "python",
            "uv",
            "R",
            "julia",
            "jupyter",
            "docker",
            "podman",
            "nvidia-smi",
            "rocm-smi",
            "ssh",
            "rsync",
            "sbatch",
            "squeue",
            "sacct",
        ):
            self.assertIn(tool, report["tools"])
            self.assertIn("available", report["tools"][tool])
        serialized = json.dumps(report).lower()
        self.assertNotIn("environment", serialized)
        self.assertNotIn("hostname", serialized)

    def test_probe_writes_private_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            output = Path(tempdir) / "nested" / "compute.json"
            result = subprocess.run(
                [sys.executable, str(self.script), "--output", str(output)],
                cwd=self.repository_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(output.is_file())
            self.assertEqual(0o600, stat.S_IMODE(output.stat().st_mode))
            self.assertEqual(json.loads(result.stdout), json.loads(output.read_text()))


if __name__ == "__main__":
    unittest.main()
