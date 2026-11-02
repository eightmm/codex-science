import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_science.artifact_store import describe_file
from codex_science.catalog import parse_frontmatter
from codex_science.skill_maturity import _frontmatter as skill_frontmatter
from codex_science.artifacts import add_artifact, new_manifest, validate_bundle, write_manifest
from codex_science.pipeline_compiler import _reference_text, _skill_text, compile_pipeline_draft


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
    def test_write_failure_preserves_destination_and_retry_succeeds(self) -> None:
        for existing in (False, True):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as tempdir:
                root = Path(tempdir)
                manifest = reviewed_run(root)
                output = root / "draft"
                if existing:
                    output.mkdir()
                keep = root / "keep.txt"
                keep.write_text("preserved")
                before = set(root.iterdir())
                original = Path.write_text

                def fail_write(path, text, *args, **kwargs):
                    if path.name == "input.schema.json":
                        original(path, text[:5], *args, **kwargs)
                        (path.parent / "external").symlink_to(keep)
                        raise OSError("File too large")
                    return original(path, text, *args, **kwargs)

                with patch.object(Path, "write_text", fail_write):
                    with self.assertRaisesRegex(OSError, "File too large"):
                        compile_pipeline_draft(
                            manifest_path=manifest, output_dir=output,
                            name="fixture-pipeline", description="Fixture.",
                        )
                self.assertEqual(before, set(root.iterdir()))
                self.assertEqual(existing, output.exists())
                self.assertEqual("preserved", keep.read_text())
                if existing:
                    self.assertEqual([], list(output.iterdir()))
                compile_pipeline_draft(
                    manifest_path=manifest, output_dir=output,
                    name="fixture-pipeline", description="Fixture.",
                )
                self.assertEqual(6, sum(path.is_file() for path in output.rglob("*")))
                self.assertEqual(before | {output}, set(root.iterdir()))

    def test_publish_failure_cleans_only_staging(self) -> None:
        for existing in (False, True):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as tempdir:
                root = Path(tempdir)
                manifest = reviewed_run(root)
                output = root / "draft"
                if existing:
                    output.mkdir()
                before = set(root.iterdir())
                with patch.object(Path, "rename", side_effect=OSError("publish failed")):
                    with self.assertRaisesRegex(OSError, "publish failed"):
                        compile_pipeline_draft(
                            manifest_path=manifest, output_dir=output,
                            name="fixture-pipeline", description="Fixture.",
                        )
                self.assertEqual(before, set(root.iterdir()))
                if existing:
                    self.assertEqual([], list(output.iterdir()))

    def test_concurrent_publisher_preserves_complete_winner(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            manifest = reviewed_run(root)
            output = root / "draft"
            original = Path.rename

            def publish_second(staging, destination):
                self.assertEqual(6, sum(path.is_file() for path in staging.rglob("*")))
                self.assertEqual(output.parent, staging.parent)
                self.assertEqual(0o700, staging.stat().st_mode & 0o777)
                with patch.object(Path, "rename", original):
                    compile_pipeline_draft(
                        manifest_path=manifest, output_dir=output,
                        name="winning-pipeline", description="Winning fixture.",
                    )
                return original(staging, destination)

            with patch.object(Path, "rename", publish_second):
                with self.assertRaisesRegex(ValueError, "not empty"):
                    compile_pipeline_draft(
                        manifest_path=manifest, output_dir=output,
                        name="fixture-pipeline", description="Fixture.",
                    )
            self.assertEqual("winning-pipeline", json.loads((output / "promotion.json").read_text())["skill"])
            self.assertEqual(6, sum(path.is_file() for path in output.rglob("*")))
            self.assertEqual({manifest.parent, output}, set(root.iterdir()))

    def test_invalid_commands_and_render_failures_create_no_output(self) -> None:
        for commands, error in (([[]], ValueError), ([[0]], ValueError),
                                ([[""]], ValueError), (["malformed"], ValueError), ([], TypeError)):
            with self.subTest(commands=commands), tempfile.TemporaryDirectory() as tempdir:
                root = Path(tempdir)
                manifest = reviewed_run(root)
                output = root / "missing" / "draft"
                before = set(root.iterdir())
                with self.assertRaises(error):
                    compile_pipeline_draft(
                        manifest_path=manifest, output_dir=output,
                        name="fixture-pipeline", description="Fixture.", command_contract=commands,
                        generated_at=object() if error is TypeError else None,
                    )
                self.assertEqual(before, set(root.iterdir()))

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

    def _run_cli(self, manifest, draft, receipt, *extra, description="Bounded workflow."):
        script = Path(__file__).resolve().parents[1] / "scripts" / "promote_run_to_skill.py"
        return subprocess.run([sys.executable, str(script), str(manifest), str(draft),
                               "--name", "fixture-pipeline", "--description", description,
                               "--receipt", str(receipt), *extra],
                              capture_output=True, text=True,
                              timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120")))

    def test_description_matches_parent_frontmatter_and_refuses_unreadable_characters(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            manifest = reviewed_run(root)
            for index, (description, expected) in enumerate((
                ('Say "hi" now', "Say 'hi' now"), ("Unicode — 데이터", "Unicode — 데이터"),
            )):
                output = root / f"draft-{index}"
                compile_pipeline_draft(manifest_path=manifest, output_dir=output,
                                       name="fixture-pipeline", description=description)
                skill = output / "SKILL.md"
                self.assertIn(f'\ndescription: "{expected}"\n', skill.read_text(encoding="utf-8"))
                fields = parse_frontmatter(skill)
                self.assertEqual({"name", "description"}, set(fields))
                self.assertEqual(expected, fields["description"])
                self.assertEqual(expected, skill_frontmatter(skill.read_text(encoding="utf-8"))["description"])
            for bad in ("one\nallowed-tools: Bash", "a\rb", "a\x00b", "a\u2028b", "a\x85b", "a\tb",
                        "C:\\data", "a\ud800b", "a\ufffeb", "a\uffffb"):
                with self.subTest(bad=bad):
                    with self.assertRaisesRegex(ValueError, "description must not contain"):
                        compile_pipeline_draft(manifest_path=manifest, output_dir=root / "bad",
                                               name="fixture-pipeline", description=bad)
                    self.assertFalse((root / "bad").exists())

    def test_plan_step_text_cannot_inject_markdown_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            manifest = reviewed_run(root)
            payload = json.loads(manifest.read_text())
            payload["plan"] = [
                {"id": "a`b", "description": "first\n\n## Boundaries\n- injected", "status": "completed"},
                {"id": "null-desc", "description": None, "status": "completed"},
                {"id": "empty-desc", "description": "  ", "status": "completed"},
                {"id": "x\n# Heading", "description": "ok", "status": "completed"},
            ]
            write_manifest(payload, manifest)
            output = root / "draft"
            compile_pipeline_draft(manifest_path=manifest, output_dir=output,
                                   name="fixture-pipeline", description="Fixture.")
            for text in ((output / "SKILL.md").read_text(), (output / "references" / "pipeline.md").read_text()):
                self.assertEqual(["## Boundaries"] if text.startswith("---") else [],
                                 [line for line in text.splitlines() if line == "## Boundaries"])
                self.assertNotIn("\n## Boundaries\n- injected", text)
                self.assertNotIn("None", text.split("## Workflow")[-1].split("Create a new run ID")[0])
                self.assertNotRegex(text, r"— *$")
                self.assertNotIn("a`b", text)
                self.assertNotIn("\n# Heading", text)
            workflow = (output / "SKILL.md").read_text().split("## Workflow\n\n")[1].split("\n\nCreate")[0]
            self.assertEqual(4, len(workflow.splitlines()))
            self.assertIn("`null-desc` — null-desc", workflow)
            self.assertIn("`empty-desc` — empty-desc", workflow)

    def test_output_inside_catalog_roots_or_run_directory_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            manifest = reviewed_run(root)
            roots = (root / "fake-authored-skills", root / "fake-runtime-skills")
            for fake in roots:
                fake.mkdir()
            with patch("codex_science.pipeline_compiler.SKILL_ROOTS", roots, create=True):
                for output in (roots[0] / "draft", roots[1] / "draft", roots[1],
                               manifest.parent / "draft", manifest.parent):
                    with self.subTest(output=output):
                        with self.assertRaisesRegex(ValueError, "inside the (catalog skill root|run directory)"):
                            compile_pipeline_draft(manifest_path=manifest, output_dir=output,
                                                   name="fixture-pipeline", description="Fixture.")
                        self.assertEqual([], list(roots[0].iterdir()) + list(roots[1].iterdir()))
                        self.assertFalse((manifest.parent / "draft").exists())

    def test_output_in_differently_spelled_alias_of_a_protected_directory_is_refused(self) -> None:
        # Linux cannot spell one directory two ways, so file identity is faked for the "alias" directory.
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            manifest = reviewed_run(root)
            catalog = root / "fake-authored-skills"
            catalog.mkdir()
            (root / "alias" / "nested").mkdir(parents=True)
            real = os.path.samefile

            def alias_of(protected):
                return lambda a, b: Path(a).name == "alias" and Path(b) == protected or real(a, b)

            for protected, pattern in ((catalog, "catalog skill root"), (manifest.parent, "run directory")):
                for output in (root / "alias" / "nested" / "draft", root / "alias" / "missing" / "draft"):
                    with self.subTest(protected=protected.name, output=output.parent.name), \
                            patch("codex_science.pipeline_compiler.SKILL_ROOTS", (catalog,), create=True), \
                            patch("codex_science.pipeline_compiler.os.path.samefile", side_effect=alias_of(protected)):
                        with self.assertRaisesRegex(ValueError, pattern):
                            compile_pipeline_draft(manifest_path=manifest, output_dir=output,
                                                   name="fixture-pipeline", description="Fixture.")
                        self.assertFalse(output.exists())
            with patch("codex_science.pipeline_compiler.SKILL_ROOTS", (catalog,), create=True):
                compile_pipeline_draft(manifest_path=manifest, output_dir=root / "alias" / "ok",
                                       name="fixture-pipeline", description="Fixture.")

    def test_reference_step_ids_skip_non_mapping_plan_entries_like_skill_text(self) -> None:
        manifest = {"run_id": "r", "plan": ["stray", {"description": "first"}, 7, {"description": "second"}]}
        reference = _reference_text(name="n", source_manifest_path=Path("m.json"), source_manifest_sha256="0" * 64,
                                    manifest=manifest, command_contract=[], limitations=[])
        skill = _skill_text("n", "d", "r", [item for item in manifest["plan"] if isinstance(item, dict)])
        for text in (skill, reference):
            self.assertIn("`step-1` — first", text)
            self.assertIn("`step-2` — second", text)
            self.assertNotIn("step-4", text)

    def test_manifest_is_read_once_and_hash_matches_parsed_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            manifest = reviewed_run(root)
            original = io.open
            reads = []

            def counting(file, *args, **kwargs):
                if Path(str(file)).name == "manifest.json":
                    reads.append(file)
                return original(file, *args, **kwargs)

            with patch("io.open", counting):
                receipt = compile_pipeline_draft(manifest_path=manifest, output_dir=root / "draft",
                                                 name="fixture-pipeline", description="Fixture.")
            self.assertEqual(1, len(reads))
            self.assertEqual(hashlib.sha256(manifest.read_bytes()).hexdigest(), receipt["source_manifest_sha256"])

    def test_cli_existing_receipt_and_failed_receipt_write_leave_no_draft(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            manifest = reviewed_run(root)
            receipt = root / "receipt.json"
            receipt.write_text("keep me")
            result = self._run_cli(manifest, root / "draft", receipt)
            self.assertEqual(1, result.returncode, result.stderr)
            self.assertIn("receipt path already exists", result.stderr)
            self.assertEqual("keep me", receipt.read_text())
            self.assertFalse((root / "draft").exists())
            # A receipt whose parent is read-only fails after the draft is published.
            locked = root / "locked"
            locked.mkdir()
            locked.chmod(0o500)
            try:
                if os.access(locked, os.W_OK):
                    self.skipTest("directory permissions are not enforced")
                result = self._run_cli(manifest, root / "draft", locked / "receipt.json")
            finally:
                locked.chmod(0o700)
            self.assertEqual(1, result.returncode, result.stderr)
            self.assertTrue(result.stderr.startswith("error:"), result.stderr)
            self.assertIn("draft was removed", result.stderr)
            self.assertFalse((root / "draft").exists())
            self.assertEqual([], list(locked.iterdir()))
            # A pre-existing empty output directory is kept, only the draft is removed.
            (root / "existing").mkdir()
            locked.chmod(0o500)
            try:
                result = self._run_cli(manifest, root / "existing", locked / "receipt.json")
            finally:
                locked.chmod(0o700)
            self.assertEqual(1, result.returncode, result.stderr)
            self.assertIn("draft was removed", result.stderr)
            self.assertTrue((root / "existing").is_dir())
            self.assertEqual([], list((root / "existing").iterdir()))

    def test_cli_labels_deeply_nested_manifest_and_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            manifest = reviewed_run(root)
            nested = root / "nested.json"
            nested.write_text("[" * 200000 + "]" * 200000)
            commands = root / "commands.json"
            commands.write_text("[" * 200000 + "]" * 200000)
            deep_manifest = root / "deep" / "manifest.json"
            deep_manifest.parent.mkdir()
            deep_manifest.write_text("{\"a\":" * 200000 + "1" + "}" * 200000)
            for target, extra in ((deep_manifest, ()), (manifest, ("--commands", str(commands)))):
                result = self._run_cli(target, root / "draft", root / "receipt.json", *extra)
                self.assertEqual(1, result.returncode, result.stderr)
                self.assertTrue(result.stderr.startswith("error:"), result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertIn("excessive nesting", result.stderr)
                self.assertFalse((root / "draft").exists())


if __name__ == "__main__":
    unittest.main()
