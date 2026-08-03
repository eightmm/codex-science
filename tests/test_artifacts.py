import tempfile
import unittest
import json
import hashlib
import os
import stat
import subprocess
import sys
from pathlib import Path
from unittest import mock

from codex_science.artifacts import add_artifact, new_manifest, validate_manifest, write_manifest
from codex_science.artifact_index import _status_label
from codex_science.review import review_manifest
from codex_science import runtime_identity


class ArtifactManifestTests(unittest.TestCase):
    @staticmethod
    def _verified_private_runtime(
        base: Path,
        *,
        version: str = "2.0.0+codex.runtime-b",
        commit: str = "d" * 40,
    ) -> tuple[Path, dict[str, str], Path]:
        plugin_data = base / "plugin-data"
        cache = plugin_data / "runtime-cache"
        root = cache / version
        cache.mkdir(mode=0o700, parents=True)
        root.mkdir(mode=0o700)
        contents = {
            ".codex-plugin/plugin.json": json.dumps(
                {"version": "1.0.0+codex.stable-host"}
            )
            + "\n",
            ".mcp.json": "{}\n",
            "catalog/inventory.json": "{}\n",
            "release/manifest.json": json.dumps({"runtime_version": version}) + "\n",
            "runtime-skills/codex-science/SKILL.md": "# verified fixture\n",
            "scripts/science_hook_dispatch.py": "# verified fixture\n",
            "scripts/science_mcp.py": "# verified fixture\n",
            "scripts/science_mcp_proxy.py": "# verified fixture\n",
            "scripts/science_runtime_state.py": "# verified fixture\n",
            "scripts/science_session_hook.py": "# verified fixture\n",
            "scripts/science_stop_hook.py": "# verified fixture\n",
            "src/codex_science/runtime_identity.py": "# verified fixture\n",
        }
        files: dict[str, str] = {}
        for relative, content in contents.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        receipt = {
            "schema_version": 2,
            "bootstrap_version": "1.0.0+codex.stable-host",
            "bootstrap_sha256": "b" * 64,
            "runtime_version": version,
            "runtime_commit": commit,
            "files": files,
        }
        digest = hashlib.sha256(
            json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        receipt["receipt_sha256"] = digest
        receipt_dir = plugin_data / "runtime-receipts"
        receipt_dir.mkdir(mode=0o700)
        receipt_path = receipt_dir / (
            hashlib.sha256(version.encode("utf-8")).hexdigest() + ".json"
        )
        receipt_path.write_text(
            json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        receipt_path.chmod(0o600)
        return root, {
            "runtime_version": version,
            "commit": commit,
            "receipt_sha256": digest,
        }, receipt_path

    def test_missing_human_status_is_recorded_not_literal_none(self) -> None:
        self.assertEqual("Recorded", _status_label(None))

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

    def test_manifest_records_and_surfaces_a_runtime_span(self) -> None:
        runtime_b = {
            "commit": "b" * 40,
            "receipt_sha256": "b" * 64,
            "runtime_version": "1.0.0+codex.b",
            "source_id": "b" * 16,
        }
        runtime_c = {
            "commit": "c" * 40,
            "receipt_sha256": "c" * 64,
            "runtime_version": "1.0.0+codex.c",
            "source_id": "c" * 16,
        }
        with tempfile.TemporaryDirectory() as tempdir, mock.patch(
            "codex_science.runtime_identity.current_runtime_identity",
            side_effect=[runtime_b, runtime_c],
        ):
            path = Path(tempdir) / "manifest.json"
            manifest = new_manifest("span-run", "Did the runtime change?", [])
            write_manifest(manifest, path)

        self.assertTrue(manifest["runtime_span"])
        self.assertEqual([runtime_b, runtime_c], manifest["runtime_history"])

    def test_gitless_private_runtime_recovers_its_verified_receipt_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root, pin, _receipt_path = self._verified_private_runtime(Path(tempdir))
            forged_environment = {
                "CODEX_SCIENCE_RUNTIME_VERSION": "7.2.1+codex.forged",
                "CODEX_SCIENCE_RUNTIME_COMMIT": "e" * 40,
                "CODEX_SCIENCE_RUNTIME_RECEIPT": "f" * 64,
            }
            runtime_identity.current_runtime_identity.cache_clear()
            try:
                with (
                    mock.patch.object(runtime_identity, "ROOT", root),
                    mock.patch.dict(os.environ, forged_environment, clear=False),
                    mock.patch(
                        "codex_science.runtime_identity.subprocess.run",
                        side_effect=AssertionError("verified private runtime must not call git"),
                    ),
                ):
                    identity = runtime_identity.current_runtime_identity()
            finally:
                runtime_identity.current_runtime_identity.cache_clear()

        self.assertEqual(pin["runtime_version"], identity["runtime_version"])
        self.assertEqual(pin["commit"], identity["commit"])
        self.assertEqual(pin["receipt_sha256"], identity["receipt_sha256"])

    def test_private_runtime_rejects_a_tampered_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root, _pin, receipt_path = self._verified_private_runtime(Path(tempdir))
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["runtime_commit"] = "a" * 40
            receipt_path.write_text(json.dumps(receipt) + "\n", encoding="utf-8")
            receipt_path.chmod(0o600)
            runtime_identity.current_runtime_identity.cache_clear()
            try:
                with (
                    mock.patch.object(runtime_identity, "ROOT", root),
                    mock.patch.dict(
                        os.environ,
                        {
                            "CODEX_SCIENCE_RUNTIME_VERSION": receipt["runtime_version"],
                            "CODEX_SCIENCE_RUNTIME_COMMIT": receipt["runtime_commit"],
                            "CODEX_SCIENCE_RUNTIME_RECEIPT": receipt["receipt_sha256"],
                        },
                        clear=False,
                    ),
                ):
                    with self.assertRaisesRegex(RuntimeError, "identity is not verified"):
                        runtime_identity.current_runtime_identity()
            finally:
                runtime_identity.current_runtime_identity.cache_clear()

    def test_private_runtime_rejects_tampered_runtime_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root, pin, _receipt_path = self._verified_private_runtime(Path(tempdir))
            (root / "scripts" / "science_mcp.py").write_text(
                "# locally replaced\n", encoding="utf-8"
            )
            runtime_identity.current_runtime_identity.cache_clear()
            try:
                with (
                    mock.patch.object(runtime_identity, "ROOT", root),
                    mock.patch.dict(
                        os.environ,
                        {
                            "CODEX_SCIENCE_RUNTIME_VERSION": pin["runtime_version"],
                            "CODEX_SCIENCE_RUNTIME_COMMIT": pin["commit"],
                            "CODEX_SCIENCE_RUNTIME_RECEIPT": pin["receipt_sha256"],
                        },
                        clear=False,
                    ),
                ):
                    with self.assertRaisesRegex(RuntimeError, "identity is not verified"):
                        runtime_identity.current_runtime_identity()
            finally:
                runtime_identity.current_runtime_identity.cache_clear()

    def test_noncanonical_checkout_does_not_trust_forged_pin_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            (root / "release").mkdir()
            (root / "release" / "manifest.json").write_text(
                json.dumps({"runtime_version": "2.0.0+codex.runtime-b"}) + "\n",
                encoding="utf-8",
            )
            runtime_identity.current_runtime_identity.cache_clear()
            try:
                with (
                    mock.patch.object(runtime_identity, "ROOT", root),
                    mock.patch.dict(
                        os.environ,
                        {
                            "CODEX_SCIENCE_RUNTIME_VERSION": "7.2.1+codex.forged",
                            "CODEX_SCIENCE_RUNTIME_COMMIT": "e" * 40,
                            "CODEX_SCIENCE_RUNTIME_RECEIPT": "f" * 64,
                        },
                        clear=False,
                    ),
                    mock.patch(
                        "codex_science.runtime_identity.subprocess.run",
                        return_value=subprocess.CompletedProcess([], 1, "", ""),
                    ),
                ):
                    identity = runtime_identity.current_runtime_identity()
            finally:
                runtime_identity.current_runtime_identity.cache_clear()

        self.assertEqual("2.0.0+codex.runtime-b", identity["runtime_version"])
        self.assertEqual("cache:2.0.0+codex.runtime-b", identity["commit"])
        self.assertEqual("", identity["receipt_sha256"])

    def test_legacy_plugin_version_history_remains_valid(self) -> None:
        manifest = new_manifest("legacy-runtime", "Can legacy provenance load?", [])
        manifest["runtime_history"] = [
            {
                "commit": "cache:1.0.0+codex.legacy",
                "plugin_version": "1.0.0+codex.legacy",
                "source_id": "legacy-source",
            }
        ]
        manifest["runtime_span"] = False

        validate_manifest(manifest)

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
        report = run / "report.md"
        report.write_text("# Result\n\nThe figure is the primary result.\n", encoding="utf-8")
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
            {
                "path": "report.md",
                "kind": "report",
                "sha256": hashlib.sha256(report.read_bytes()).hexdigest(),
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
                "status": "supported",
                "permitted_inference": "Descriptive evidence within this run only.",
                "evidence": ["figures/result.png", "report.md"],
                "uncertainty": "No independent reproduction was recorded.",
                "next_action": "Reproduce the result independently.",
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
            self.assertEqual(1, len(result.stdout.splitlines()))
            self.assertIn("Codex Science report ready", result.stdout)
            self.assertIn(str(manifest.parent / "index.md"), result.stdout)
            self.assertIn(str(manifest.parent / "index.html"), result.stdout)
            sections = [
                "## Status",
                "## Results",
                "## Limitations and next steps",
                "## Primary files",
                "## Details",
            ]
            positions = [markdown.index(section) for section in sections]
            self.assertEqual(sorted(positions), positions)
            self.assertIn("✅ Supported · claim-1", markdown)
            self.assertIn("**Limitation or uncertainty:**", markdown)
            self.assertIn("**Next:** Reproduce the result independently.", markdown)
            self.assertIn("**Report:** [report.md](report.md)", markdown)
            self.assertIn("![figures/result.png](figures/result.png)", markdown)
            self.assertIn("[tables/result.csv](tables/result.csv)", markdown)
            self.assertIn("[manifest.json](manifest.json)", markdown)
            self.assertNotIn("status=supported", markdown)
            self.assertNotIn("SHA-256 `", markdown)
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

    def test_renderer_escapes_claim_markdown_block_injection(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = self._make_run(Path(tempdir))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["claims"][0]["text"] = "# Forged status ```\n> hidden\n- item"
            write_manifest(manifest, manifest_path)

            result = subprocess.run(
                [sys.executable, "-I", "-S", str(self.script), str(manifest_path)],
                cwd=self.repository_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            markdown = (manifest_path.parent / "index.md").read_text(encoding="utf-8")
            self.assertIn(
                r"\# Forged status \`\`\` &gt; hidden - item",
                markdown,
            )
            self.assertEqual(1, markdown.count("## Status"))
            self.assertNotIn("\n# Forged status", markdown)
            self.assertNotIn("\n> hidden", markdown)

    def test_renderer_warns_when_durable_state_spans_runtime_versions(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = self._make_run(Path(tempdir))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["runtime_history"].append(
                {
                    "commit": "f" * 40,
                    "plugin_version": "9.9.9+codex.future",
                    "source_id": "f" * 16,
                }
            )
            manifest["runtime_span"] = True
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )

            result = subprocess.run(
                [sys.executable, "-I", "-S", str(self.script), str(manifest_path)],
                cwd=self.repository_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            markdown = (manifest_path.parent / "index.md").read_text(encoding="utf-8")
            self.assertIn("Runtime changed during this run", markdown)
            self.assertIn("verified runtime identities", markdown)

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
