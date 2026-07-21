import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from codex_science.artifacts import add_artifact, new_manifest, write_manifest
from codex_science.pipeline_compiler import compile_pipeline_draft


def make_run(root: Path) -> Path:
    run = root / "run"
    run.mkdir()
    output = run / "result.json"
    output.write_text('{"ok": true}\n', encoding="utf-8")
    manifest = new_manifest(
        "secure-source-run",
        "Can the reviewed workflow be represented without copying private inputs?",
        [{"id": "run", "description": "Run fixture", "status": "completed"}],
    )
    manifest["inputs"] = [
        {
            "id": "private-input",
            "path": "/private/patient/data.csv",
            "sha256": "a" * 64,
            "token": "must-not-propagate"
        }
    ]
    manifest["environment"] = {
        "python": "3.12",
        "API_TOKEN": "must-not-propagate",
        "nested": {"client_secret": "must-not-propagate", "threads": 4}
    }
    manifest["claims"] = [{"id": "C1", "text": "The fixture completed.", "evidence": ["result.json"]}]
    manifest["review"] = {"status": "passed", "findings": []}
    add_artifact(manifest, "result.json", kind="result", sha256=hashlib.sha256(output.read_bytes()).hexdigest())
    path = run / "manifest.json"
    write_manifest(manifest, path)
    return path


class PipelineCompilerSecurityTests(unittest.TestCase):
    def test_private_input_values_and_environment_secrets_are_not_copied(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            manifest = make_run(root)
            output = root / "draft"
            compile_pipeline_draft(
                manifest_path=manifest,
                output_dir=output,
                name="secure-draft",
                description="Secure draft.",
                command_contract=[["python", "analysis.py"]],
                generated_at="2026-07-21T00:00:00Z",
            )
            schema = (output / "input.schema.json").read_text(encoding="utf-8")
            reference = (output / "references" / "pipeline.md").read_text(encoding="utf-8")
            self.assertNotIn("/private/patient/data.csv", schema)
            self.assertNotIn("must-not-propagate", schema)
            self.assertNotIn("must-not-propagate", reference)
            self.assertIn("[REDACTED]", reference)
            payload = json.loads(schema)
            self.assertEqual(1, payload["x-source-run-input-count"])
            self.assertIn("path", payload["x-source-run-input-fields"])

    def test_credential_bearing_argv_and_urls_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            manifest = make_run(root)
            cases = [
                [["tool", "--token", "secret-value"]],
                [["tool", "--api-key=secret-value"]],
                [["curl", "https://example.org/data?token=secret-value"]]
            ]
            for index, commands in enumerate(cases):
                with self.subTest(commands=commands), self.assertRaisesRegex(ValueError, "credential"):
                    compile_pipeline_draft(
                        manifest_path=manifest,
                        output_dir=root / f"draft-{index}",
                        name=f"secure-draft-{index}",
                        description="Secure draft.",
                        command_contract=commands,
                    )


if __name__ == "__main__":
    unittest.main()
