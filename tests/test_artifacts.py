import tempfile
import unittest
import json
import hashlib
import stat
import subprocess
import sys
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


class ArtifactIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository_root = Path(__file__).resolve().parents[1]
        self.script = self.repository_root / "scripts" / "render_artifact_index.py"

    def _make_run(self, root: Path, *, include_missing: bool = False) -> Path:
        run = root / "artifacts" / "run-visual-001"
        (run / "figures").mkdir(parents=True)
        (run / "tables").mkdir()
        image = run / "figures" / "result.png"
        image.write_bytes(b"\x89PNG\r\n\x1a\nscientific-result")
        table = run / "tables" / "result.csv"
        table.write_text("x,y\n1,2\n", encoding="utf-8")
        manifest = new_manifest(
            "run-visual-001",
            "Does <script>alert('x')</script> remain escaped?",
            [{"id": "step-1", "description": "Create result", "status": "completed"}],
        )
        manifest["artifacts"] = [
            {
                "path": "figures/result.png",
                "kind": "figure",
                "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
            },
            {
                "path": "tables/result.csv",
                "kind": "table",
                "sha256": hashlib.sha256(table.read_bytes()).hexdigest(),
            },
        ]
        if include_missing:
            manifest["artifacts"].append(
                {"path": "figures/missing.png", "kind": "figure", "sha256": "a" * 64}
            )
        manifest["claims"] = [
            {
                "id": "claim-1",
                "text": "The generated figure is the primary result.",
                "evidence": ["figures/result.png"],
            }
        ]
        manifest["review"] = {"status": "passed", "findings": []}
        path = run / "manifest.json"
        write_manifest(manifest, path)
        return path

    def test_renderer_creates_markdown_and_offline_html_with_images(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest = self._make_run(Path(tempdir))
            result = subprocess.run(
                [sys.executable, "-I", "-S", str(self.script), str(manifest), "--html"],
                cwd=self.repository_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            markdown = (manifest.parent / "index.md").read_text(encoding="utf-8")
            html = (manifest.parent / "index.html").read_text(encoding="utf-8")
            self.assertIn("![figures/result.png](figures/result.png)", markdown)
            self.assertIn("[tables/result.csv](tables/result.csv)", markdown)
            self.assertIn('<img src="figures/result.png"', html)
            self.assertIn("tables/result.csv", html)
            self.assertNotIn("<script>alert", markdown)
            self.assertNotIn("<script>alert", html)
            self.assertIn("&lt;script&gt;", html)
            self.assertNotIn("http://", html)
            self.assertNotIn("https://", html)
            self.assertEqual(0o600, stat.S_IMODE((manifest.parent / "index.md").stat().st_mode))
            self.assertEqual(0o600, stat.S_IMODE((manifest.parent / "index.html").stat().st_mode))

    def test_renderer_rejects_missing_artifact_instead_of_creating_dead_link(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest = self._make_run(Path(tempdir), include_missing=True)
            result = subprocess.run(
                [sys.executable, "-I", "-S", str(self.script), str(manifest)],
                cwd=self.repository_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(0, result.returncode)
            self.assertIn("Artifact file is missing", result.stderr)
            self.assertFalse((manifest.parent / "index.md").exists())

    def test_renderer_rejects_digest_mismatch_and_external_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            manifest_path = self._make_run(root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"][0]["sha256"] = "b" * 64
            write_manifest(manifest, manifest_path)

            mismatch = subprocess.run(
                [sys.executable, "-I", "-S", str(self.script), str(manifest_path)],
                cwd=self.repository_root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(0, mismatch.returncode)
            self.assertIn("Artifact digest mismatch", mismatch.stderr)

            external = root / "external.png"
            external.write_bytes(b"external")
            link = manifest_path.parent / "figures" / "external.png"
            link.symlink_to(external)
            manifest["artifacts"] = [
                {
                    "path": "figures/external.png",
                    "kind": "figure",
                    "sha256": hashlib.sha256(external.read_bytes()).hexdigest(),
                }
            ]
            write_manifest(manifest, manifest_path)
            escaped = subprocess.run(
                [sys.executable, "-I", "-S", str(self.script), str(manifest_path)],
                cwd=self.repository_root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(0, escaped.returncode)
            self.assertIn("resolves outside the run bundle", escaped.stderr)

    def test_user_facing_plugin_scripts_do_not_require_project_install(self) -> None:
        example = self.repository_root / "examples" / "reviewed-run" / "manifest.json"
        commands = (
            [sys.executable, "-I", "-S", str(self.repository_root / "scripts" / "validate_artifact.py"), str(example)],
            [sys.executable, "-I", "-S", str(self.repository_root / "scripts" / "search_skills.py"), "sympy"],
        )

        for command in commands:
            with self.subTest(script=Path(command[3]).name):
                result = subprocess.run(
                    command,
                    cwd=tempfile.gettempdir(),
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(0, result.returncode, result.stderr)


if __name__ == "__main__":
    unittest.main()
