import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codex_science.artifact_store import describe_file
from codex_science.artifacts import add_artifact, new_manifest, validate_bundle, write_manifest
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
    def test_cli_protects_numeric_manifest_paths_before_creating_draft(self) -> None:
        for field in ("path", "descriptor_path", "input"):
            for value in (0, 123):
                for alias in ("symlink", "hardlink"):
                    with self.subTest(field=field, value=value, alias=alias), tempfile.TemporaryDirectory() as tempdir:
                        root = Path(tempdir)
                        manifest_path = reviewed_run(root)
                        run = manifest_path.parent
                        manifest = json.loads(manifest_path.read_text())
                        numeric = run / str(value)
                        if field == "descriptor_path":
                            numeric.write_text(json.dumps(describe_file(run / "result.json").to_dict()))
                            manifest["artifacts"][0][field] = value
                        else:
                            numeric.write_bytes(b"numeric input")
                            digest = hashlib.sha256(numeric.read_bytes()).hexdigest()
                            if field == "path":
                                manifest["artifacts"].append({"path": value, "kind": "result", "sha256": digest})
                            else:
                                manifest["inputs"].append({"id": "numeric", "path": value, "sha256": digest})
                        write_manifest(manifest, manifest_path)
                        validate_bundle(manifest, run)
                        receipt = root / "receipt.json"
                        if alias == "symlink":
                            receipt.symlink_to(numeric)
                        else:
                            os.link(numeric, receipt)
                        entries = set(root.rglob("*"))
                        before = {path.relative_to(root): path.read_bytes() for path in entries if path.is_file()}
                        script = Path(__file__).resolve().parents[1] / "scripts" / "promote_run_to_skill.py"
                        result = subprocess.run([sys.executable, str(script), str(manifest_path), str(root / "draft"),
                                                 "--name", "fixture-pipeline", "--description", "Bounded workflow.",
                                                 "--receipt", str(receipt)], capture_output=True, text=True,
                                                timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120")))
                        self.assertEqual(1, result.returncode, result.stderr)
                        self.assertTrue(result.stderr.startswith("error:"), result.stderr)
                        self.assertIn("would overwrite input", result.stderr)
                        self.assertNotIn("Traceback", result.stderr)
                        self.assertEqual("", result.stdout)
                        self.assertEqual(entries, set(root.rglob("*")))
                        self.assertEqual(before, {path.relative_to(root): path.read_bytes() for path in entries if path.is_file()})

    def test_cli_refuses_receipt_conflicts_before_creating_draft(self) -> None:
        for conflict in ("skill", "nested", "manifest", "input", "artifact", "symlink", "hardlink",
                         "commands", "bad-ancestor", "invalid-commands", "manifest-alias", "manifest-loop", "input-ancestor"):
            with self.subTest(conflict=conflict), tempfile.TemporaryDirectory() as tempdir:
                root = Path(tempdir)
                manifest = reviewed_run(root)
                draft = root / "draft"
                receipt = draft / "SKILL.md"
                extra = []
                if conflict == "nested":
                    receipt = draft / "nested" / "receipt.json"
                elif conflict in ("manifest", "artifact"):
                    receipt = manifest if conflict == "manifest" else manifest.parent / "result.json"
                elif conflict == "input":
                    receipt = manifest.parent / "source.dat"
                    receipt.write_bytes(b"original input")
                    payload = json.loads(manifest.read_text())
                    payload["inputs"] = [{"id": "input", "path": receipt.name,
                                          "sha256": hashlib.sha256(receipt.read_bytes()).hexdigest()}]
                    write_manifest(payload, manifest)
                elif conflict in ("symlink", "hardlink"):
                    receipt = root / "alias"
                    if conflict == "symlink":
                        receipt.symlink_to(manifest)
                    else:
                        os.link(manifest, receipt)
                elif conflict in ("commands", "invalid-commands"):
                    commands = root / "commands.json"
                    commands.write_text(json.dumps([["python", "analysis.py"]] if conflict == "commands" else [0]))
                    receipt = commands if conflict == "commands" else root / "receipt.json"
                    extra = ["--commands", str(commands)]
                elif conflict == "bad-ancestor":
                    receipt = manifest / "receipt.json"
                elif conflict == "manifest-alias":
                    alias = root / "manifest-alias.json"
                    alias.symlink_to(manifest)
                    receipt = manifest.parent / "result.json"
                    manifest = alias
                elif conflict == "manifest-loop":
                    manifest = root / "manifest-loop"
                    manifest.symlink_to(manifest)
                    receipt = root / "receipt.json"
                elif conflict == "input-ancestor":
                    payload = json.loads(manifest.read_text())
                    payload["inputs"].append({"path": str(root)})
                    write_manifest(payload, manifest)
                    receipt = root / "receipt.json"
                before = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}
                entries = set(root.rglob("*"))
                script = Path(__file__).resolve().parents[1] / "scripts" / "promote_run_to_skill.py"
                result = subprocess.run([sys.executable, str(script), str(manifest), str(draft),
                                         "--name", "fixture-pipeline", "--description", "Bounded workflow.",
                                         "--receipt", str(receipt), *extra],
                                        capture_output=True, text=True,
                                        timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120")))
                if conflict == "input-ancestor":
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertTrue((draft / "SKILL.md").is_file())
                    for relative, content in before.items():
                        self.assertEqual(content, (root / relative).read_bytes())
                    continue
                self.assertEqual(1, result.returncode, result.stderr)
                self.assertTrue(result.stderr.startswith("error:"), result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual("", result.stdout)
                self.assertEqual(entries, set(root.rglob("*")))
                self.assertEqual(before, {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()})

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
