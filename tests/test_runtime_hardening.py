import hashlib
import tempfile
import unittest
from pathlib import Path

from codex_science.action_connectors import ActionSpec, build_preview
from codex_science.artifact_runtime import describe_runtime
from codex_science.compute_backends import JobSpec, LocalBackend
from codex_science.experiment_planner import plan_next_experiment
from codex_science.pipeline_compiler import _validate_command


class SecretAdapter:
    connector_name = "secret-provider"

    def snapshot(self, spec):
        return {"object": "x", "api_token": "must-not-record"}

    def preview(self, spec, before):
        return {"change": "none"}

    def execute(self, spec, preview):
        return {"after_state": {"object": "x"}}


class RuntimeHardeningTests(unittest.TestCase):
    def test_artifact_runtime_has_absolute_view_limits(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "data.txt"
            path.write_text("hello\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hard runtime ceiling"):
                describe_runtime(
                    path,
                    artifact_path="data.txt",
                    kind="text",
                    max_bytes=16 * 1024 * 1024 + 1,
                    max_records=10,
                )
            with self.assertRaisesRegex(ValueError, "hard runtime ceiling"):
                describe_runtime(
                    path,
                    artifact_path="data.txt",
                    kind="text",
                    max_bytes=100,
                    max_records=10_001,
                )

    def test_local_preflight_verifies_declared_input_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            work = root / "work"
            work.mkdir()
            data = work / "input.json"
            data.write_text('{"value": 1}\n', encoding="utf-8")
            good = hashlib.sha256(data.read_bytes()).hexdigest()
            spec = JobSpec.from_payload(
                {
                    "backend": "local",
                    "name": "input-check",
                    "command": ["python", "-c", "print('ok')"],
                    "working_directory": str(work),
                    "inputs": [{"id": "input", "path": "input.json", "sha256": good}],
                    "outputs": [],
                }
            )
            checks = LocalBackend(root / "state").preflight(spec)["checks"]
            input_check = next(item for item in checks if item["name"] == "input:input")
            self.assertTrue(input_check["ready"])
            stale = JobSpec.from_payload({**spec.to_dict(), "inputs": [{"id": "input", "path": "input.json", "sha256": "0" * 64}]})
            result = LocalBackend(root / "other-state").preflight(stale)
            input_check = next(item for item in result["checks"] if item["name"] == "input:input")
            self.assertFalse(input_check["ready"])
            self.assertFalse(result["ready"])

    def test_provider_state_with_secret_like_keys_is_rejected(self) -> None:
        spec = ActionSpec.from_payload(
            {
                "connector": "secret-provider",
                "operation": "read",
                "mode": "read",
                "target": "object/x",
                "parameters": {},
                "requested_scopes": ["object:read"],
                "idempotency_key": "secret-provider-read-x-v1",
            }
        )
        with self.assertRaisesRegex(ValueError, "credential-like"):
            build_preview(SecretAdapter(), spec)

    def test_boolean_integer_constraints_are_rejected(self) -> None:
        payload = {
            "decision": "Select candidates.",
            "objectives": [{"name": "score", "direction": "maximize", "weight": 1}],
            "candidates": [{"id": "x", "properties": {"score": 1}, "cost": 0, "uncertainty": 0}],
            "constraints": {"batch_size": True, "budget": 1, "diversity_group_cap": 1, "minimum_controls": 0},
        }
        with self.assertRaisesRegex(ValueError, "must be integers"):
            plan_next_experiment(payload)

    def test_any_credential_argument_flag_is_rejected(self) -> None:
        for command in (["tool", "--token"], ["tool", "--password=value"], ["curl", "https://example.test/?authorization=value"]):
            with self.subTest(command=command), self.assertRaisesRegex(ValueError, "credential"):
                _validate_command(command, 0)


if __name__ == "__main__":
    unittest.main()
