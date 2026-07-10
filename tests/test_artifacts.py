import tempfile
import unittest
import json
from pathlib import Path

from codex_science.artifacts import add_artifact, new_manifest, validate_manifest, write_manifest
from codex_science.review import review_manifest


class ArtifactManifestTests(unittest.TestCase):
    def test_complete_manifest_is_valid_and_round_trips(self) -> None:
        manifest = new_manifest(
            run_id="run-001",
            question="Does the method improve the baseline?",
            plan=[{"id": "step-1", "description": "Run baseline", "status": "completed"}],
        )
        manifest["executions"].append({"command": "python baseline.py", "exit_code": 0})
        manifest["environment"] = {"python": "3.11.15", "packages": []}
        manifest["claims"].append(
            {"id": "claim-1", "text": "The baseline ran.", "evidence": ["results/baseline.json"]}
        )
        add_artifact(manifest, "results/baseline.json", kind="table", sha256="a" * 64)

        validate_manifest(manifest)

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "manifest.json"
            write_manifest(manifest, output)
            self.assertIn('"schema_version": 1', output.read_text(encoding="utf-8"))

    def test_artifact_path_must_be_relative_and_cannot_traverse(self) -> None:
        manifest = new_manifest("run-001", "Question", [])

        with self.assertRaises(ValueError):
            add_artifact(manifest, "/tmp/result.csv", kind="table", sha256="a" * 64)
        with self.assertRaises(ValueError):
            add_artifact(manifest, "../result.csv", kind="table", sha256="a" * 64)

    def test_missing_required_fields_fail_validation(self) -> None:
        manifest = new_manifest("run-001", "Question", [])
        del manifest["review"]

        with self.assertRaises(ValueError):
            validate_manifest(manifest)

    def test_checked_in_example_is_valid_and_reviewed(self) -> None:
        path = Path(__file__).resolve().parents[1] / "examples" / "reviewed-run" / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))

        validate_manifest(manifest)
        self.assertEqual("passed", manifest["review"]["status"])
        self.assertEqual("passed", review_manifest(manifest)["status"])


if __name__ == "__main__":
    unittest.main()
