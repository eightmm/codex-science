import json
import sys
import tempfile
import unittest
from pathlib import Path

from codex_science.compute_backends import (
    JobSpec,
    LocalBackend,
    SlurmBackend,
    build_approval_receipt,
    validate_approval_receipt,
)


def local_spec(working: Path, *, command: list[str], outputs: list[str], timeout: int = 10) -> JobSpec:
    return JobSpec.from_payload(
        {
            "schema_version": 1,
            "backend": "local",
            "name": "fixture-job",
            "command": command,
            "working_directory": str(working),
            "environment": {"OMP_NUM_THREADS": "1"},
            "inherit_environment": True,
            "inputs": [],
            "outputs": outputs,
            "resources": {"cpus": 1, "memory_mb": 256, "gpus": 0, "wall_time_seconds": timeout},
            "timeout_seconds": timeout,
            "cost_cap": None,
            "approval_required": False,
            "scientific_run_id": "run-fixture",
            "checkpoint_paths": [],
        }
    )


class ComputeBackendTests(unittest.TestCase):
    def test_local_job_is_durable_and_outputs_are_hash_collected(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working = root / "work"
            working.mkdir()
            state_dir = root / "state"
            spec = local_spec(
                working,
                command=[sys.executable, "-c", "from pathlib import Path; Path('result.json').write_text('{\\\"value\\\": 7}\\n')"],
                outputs=["result.json"],
            )
            backend = LocalBackend(state_dir)
            preflight = backend.preflight(spec)
            self.assertTrue(preflight["ready"])
            submitted = backend.submit(spec)
            self.assertEqual("submitted", submitted["state"])
            terminal = backend.wait(submitted["job_id"], timeout_seconds=15, poll_seconds=0.05)
            self.assertEqual("completed", terminal["state"], json.dumps(terminal, indent=2))
            self.assertEqual(0, terminal["exit_code"])
            collected = backend.collect(submitted["job_id"])
            self.assertEqual("file", collected["outputs"][0]["artifact_type"])
            self.assertEqual(64, len(collected["outputs"][0]["sha256"]))
            self.assertEqual(1, collected["outputs"][0]["entry_count"])
            self.assertTrue((state_dir / "jobs" / submitted["job_id"] / "stdout.log").is_file())
            self.assertTrue((state_dir / "jobs" / submitted["job_id"] / "stderr.log").is_file())

    def test_timeout_remains_a_distinct_terminal_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working = root / "work"
            working.mkdir()
            backend = LocalBackend(root / "state")
            spec = local_spec(
                working,
                command=[sys.executable, "-c", "import time; time.sleep(2)"],
                outputs=[],
                timeout=1,
            )
            submitted = backend.submit(spec)
            terminal = backend.wait(submitted["job_id"], timeout_seconds=10, poll_seconds=0.05)
            self.assertEqual("timed-out", terminal["state"])
            self.assertEqual("wall-time", terminal["failure_class"])

    def test_approval_is_bound_to_exact_spec(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            working = Path(tempdir)
            spec = JobSpec.from_payload(
                {
                    "backend": "slurm",
                    "name": "approved-job",
                    "command": ["python", "analysis.py"],
                    "working_directory": str(working),
                    "environment": {},
                    "inputs": [],
                    "outputs": ["result.json"],
                    "resources": {"cpus": 2, "memory_mb": 1024, "gpus": 1, "gpu_type": "a100", "wall_time_seconds": 600, "partition": "gpu"},
                    "timeout_seconds": 600,
                    "approval_required": True,
                }
            )
            receipt = build_approval_receipt(spec, approved_by="jaemin", target="cluster-a", approved_at="2026-07-21T00:00:00Z")
            validate_approval_receipt(receipt, spec)
            changed = JobSpec.from_payload({**spec.to_dict(), "timeout_seconds": 601})
            with self.assertRaisesRegex(ValueError, "different job spec"):
                validate_approval_receipt(receipt, changed)

    def test_slurm_render_is_nonexecuting_and_resource_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            spec = JobSpec.from_payload(
                {
                    "backend": "slurm",
                    "name": "dock",
                    "command": ["python", "dock.py", "--input", "input.json"],
                    "working_directory": str(root),
                    "environment": {"OMP_NUM_THREADS": "4"},
                    "inputs": [],
                    "outputs": ["poses.sdf"],
                    "resources": {"cpus": 4, "memory_mb": 8192, "gpus": 1, "gpu_type": "a100", "wall_time_seconds": 7200, "partition": "gpu", "account": "science"},
                    "timeout_seconds": 7200,
                    "approval_required": True,
                }
            )
            backend = SlurmBackend(root / "state")
            script = backend.render_script(spec, job_id="preview")
            self.assertIn("#SBATCH --cpus-per-task=4", script)
            self.assertIn("#SBATCH --mem=8192M", script)
            self.assertIn("#SBATCH --gres=gpu:a100:1", script)
            self.assertIn("#SBATCH --partition=gpu", script)
            self.assertIn("#SBATCH --account=science", script)
            self.assertIn("timeout --signal=TERM 7200s", script)
            self.assertIn("python dock.py --input input.json", script)

    def test_secret_like_environment_keys_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            with self.assertRaisesRegex(ValueError, "secret-like"):
                JobSpec.from_payload(
                    {
                        "backend": "local",
                        "name": "bad",
                        "command": ["echo", "x"],
                        "working_directory": tempdir,
                        "environment": {"API_TOKEN": "secret"},
                        "outputs": [],
                    }
                )


if __name__ == "__main__":
    unittest.main()
