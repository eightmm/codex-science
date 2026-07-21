import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from codex_science.artifacts import add_artifact, new_manifest, write_manifest
from codex_science.pipeline_compiler import compile_pipeline_draft


def reviewed_run(root: Path, *, review_status: str = "passed") -> Path:
    run = root / "run"
    run.mkdir()
    table = run / "result.json"
    table.write_text('{"value": 7}\n', encoding="utf-8")
    digest = hashlib.sha256(table.read_bytes()).hexdigest()
    manifest = new_manifest(
        "source-run",
        "Does the fixture satisfy the prespecified threshold?",
        [{"id": "compute", "description": "Compute the fixture result", "status": "completed"}],
    )
    manifest["inputs"] = [{"id": "input", "identifier": "fixture:input"}]
    manifest["code"] = [{"path": "analysis.py", "revision": "abc"}]
    manifest["executions"] = [{"command": "python analysis.py", "exit_code": 0}]
    manifest["environment"] = {"python": ">=3.11", "seed": 0}
    manifest["claims"] = [{"id": "C1", "text": "The result is seven.", "evidence": ["result.json"]}]
    manifest["review"] = {"status": review_status, "findings": []}
    add_artifact(manifest, "result.json", kind="result", sha256=digest)
    path = run / "manifest.json"
    write_manifest(manifest, path)
    return path


class PipelineCompilerTests(unittest.TestCase):
    def test_passed_run_generates_nonactive_progressive_skill_draft(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            manifest = reviewed_run(root)
            output = root / "draft"
            receipt = compile_pipeline_draft(
                manifest_path=manifest,
                output_dir=output,
                name="fixture-pipeline",
                description="Run the reviewed fixture workflow on new approved inputs.",
                command_contract=[["python", "analysis.py", "--input", "input.json", "--output", "result.json"]],
                generated_at="2026-07-21T00:00:00Z",
            )
            self.assertEqual("draft", receipt["status"])
            self.assertFalse(receipt["activated"])
            self.assertFalse(receipt["cataloged"])
            self.assertTrue((output / "SKILL.md").is_file())
            self.assertTrue((output / "input.schema.json").is_file())
            self.assertTrue((output / "output.schema.json").is_file())
            index = json.loads((output / "references" / "index.json").read_text(encoding="utf-8"))
            self.assertEqual("pipeline", index["references"][0]["id"])
            skill = (output / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("not active", skill.lower())
            self.assertIn("references/pipeline.md", skill)
            reference = (output / "references" / "pipeline.md").read_text(encoding="utf-8")
            self.assertIn("## Command contract", reference)
            self.assertIn("## Validation and promotion", reference)
            self.assertIn('["python", "analysis.py"', reference)

    def test_nonpassed_or_incomplete_run_cannot_be_promoted(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            manifest = reviewed_run(root, review_status="findings")
            with self.assertRaisesRegex(ValueError, "passed"):
                compile_pipeline_draft(
                    manifest_path=manifest,
                    output_dir=root / "draft",
                    name="fixture-pipeline",
                    description="Fixture.",
                )

    def test_existing_nonempty_output_and_invalid_name_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            manifest = reviewed_run(root)
            output = root / "draft"
            output.mkdir()
            (output / "keep.txt").write_text("do not overwrite", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not empty"):
                compile_pipeline_draft(
                    manifest_path=manifest,
                    output_dir=output,
                    name="fixture-pipeline",
                    description="Fixture.",
                )
            with self.assertRaisesRegex(ValueError, "kebab-case"):
                compile_pipeline_draft(
                    manifest_path=manifest,
                    output_dir=root / "other",
                    name="Invalid Name",
                    description="Fixture.",
                )


if __name__ == "__main__":
    unittest.main()
