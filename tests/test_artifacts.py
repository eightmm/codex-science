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

from codex_science.artifact_store import describe_file
from codex_science.artifacts import (
    _validate_descriptor_path,
    add_artifact,
    new_manifest,
    validate_manifest,
    verify_bundle_artifacts,
    write_manifest,
)
from codex_science.artifact_index import _status_label, render_html, render_markdown
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

    def test_error_object_artifact_is_a_major_finding(self) -> None:
        manifest = new_manifest("run-001", "Question", [])
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp)
            payloads = {"claim-sufficiency": '{"schema":"claim-sufficiency-error-v1","error":{}}', "citation-trace": '{"schema":"citation-trace-v1"}', "other": '{"schema":"x-error-v1"}'}
            for kind, text in payloads.items():
                (run / f"{kind}.json").write_text(text, encoding="utf-8")
                manifest["artifacts"].append({"path": f"{kind}.json", "kind": kind})
            findings = review_manifest(manifest, run, sidecars={})["findings"]
        self.assertEqual([(f["code"], f["severity"]) for f in findings], [("error-object-artifact", "major")])
        self.assertIn("claim-sufficiency.json", findings[0]["message"])

    def test_oversized_or_unreadable_generated_artifact_is_a_major_finding(self) -> None:
        from codex_science import review as review_module
        manifest = new_manifest("run-001", "Question", [])
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp)
            (run / "claim-sufficiency.json").write_text('{"schema":"claim-sufficiency-error-v1"}', encoding="utf-8")
            (run / "citation-trace.json").write_text("{", encoding="utf-8")
            for name in ("claim-sufficiency", "citation-trace"):
                manifest["artifacts"].append({"path": f"{name}.json", "kind": name})
            size = (run / "claim-sufficiency.json").stat().st_size
            with mock.patch.object(review_module, "_MAX_INSPECTED_ARTIFACT_BYTES", size):
                at_limit = {(f["code"], f["message"].split()[1]) for f in review_manifest(manifest, run, sidecars={})["findings"]}
            with mock.patch.object(review_module, "_MAX_INSPECTED_ARTIFACT_BYTES", size - 1):
                over = {(f["code"], f["message"].split()[1]) for f in review_manifest(manifest, run, sidecars={})["findings"]}
        self.assertEqual(at_limit, {("error-object-artifact", "claim-sufficiency.json"), ("uninspectable-generated-artifact", "citation-trace.json")})
        self.assertEqual(over, {("uninspectable-generated-artifact", "claim-sufficiency.json"), ("uninspectable-generated-artifact", "citation-trace.json")})


class ValidateManifestRejectionTests(unittest.TestCase):
    @staticmethod
    def base() -> dict:
        manifest = new_manifest("run-001", "Question", [])
        manifest["artifacts"].append({"path": "a.csv", "kind": "table", "sha256": "a" * 64})
        manifest["claims"].append({"id": "c1", "text": "t", "evidence": []})
        return manifest

    def assertRejects(self, manifest, message: str) -> None:
        with self.assertRaisesRegex(ValueError, message):
            validate_manifest(manifest)

    def test_baseline_is_valid(self) -> None:
        validate_manifest(self.base())

    def test_top_level_shape_is_checked(self) -> None:
        self.assertRejects([], "must be a JSON object")
        cases = (
            ("schema_version", 2, "Unsupported artifact schema version"),
            ("question", "  ", "run_id and question are required"),
            ("claims", {}, "must be a list: claims"),
            ("environment", [], "environment must be an object"),
            ("review", [], "review must be an object"),
        )
        for key, value, message in cases:
            with self.subTest(key=key):
                manifest = self.base()
                manifest[key] = value
                self.assertRejects(manifest, message)
        manifest = self.base()
        del manifest["review"]
        self.assertRejects(manifest, "Missing manifest fields: review")

    def test_artifact_records_are_checked(self) -> None:
        duplicate = self.base()
        duplicate["artifacts"].append(dict(duplicate["artifacts"][0]))
        self.assertRejects(duplicate, "Duplicate artifact path: a.csv")
        good = {"path": "b", "kind": "t", "sha256": "a" * 64}
        cases = (
            ("not-an-object", "Artifact records must be objects"),
            ({**good, "kind": " "}, "kind is required"),
            ({**good, "sha256": "xyz"}, "Invalid artifact sha256"),
            ({**good, "sha256": "a" * 63}, "Invalid artifact sha256"),
            ({**good, "artifact_type": "external-reference"}, "Unsupported local artifact_type"),
            ({**good, "size_bytes": -1}, "size_bytes must be"),
            ({**good, "entry_count": True}, "entry_count must be"),
            ({**good, "path": "../b"}, "inside the run bundle"),
            ({**good, "descriptor_path": "/abs.json"}, "inside the run bundle"),
        )
        for record, message in cases:
            with self.subTest(message=message, record=record):
                manifest = self.base()
                manifest["artifacts"].append(record)
                self.assertRejects(manifest, message)

    def test_claim_records_are_checked(self) -> None:
        cases = (
            ({"id": "c1", "text": "again"}, "Duplicate manifest claim id: c1"),
            ({"id": " "}, "Claim id is required"),
            ("c2", "Claim records must be objects"),
        )
        for claim, message in cases:
            with self.subTest(message=message):
                manifest = self.base()
                manifest["claims"].append(claim)
                self.assertRejects(manifest, message)


class DescriptorPathRejectionTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.run_dir = Path(tmp.name)
        self.data = self.run_dir / "data.bin"
        self.data.write_bytes(b"payload")
        self.digest = hashlib.sha256(b"payload").hexdigest()

    def manifest(self) -> dict:
        manifest = new_manifest("run-001", "Question", [])
        add_artifact(
            manifest, "data.bin", kind="blob", sha256=self.digest,
            descriptor_path="data.descriptor.json",
        )
        return manifest

    def write_descriptor(self, payload) -> None:
        (self.run_dir / "data.descriptor.json").write_text(json.dumps(payload), encoding="utf-8")

    def test_matching_descriptor_is_accepted(self) -> None:
        self.write_descriptor(describe_file(self.data).to_dict())
        verify_bundle_artifacts(self.manifest(), self.run_dir)

    def test_missing_descriptor_file_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Artifact descriptor is missing: data.descriptor.json"):
            verify_bundle_artifacts(self.manifest(), self.run_dir)

    def test_non_object_descriptor_is_rejected(self) -> None:
        self.write_descriptor([1, 2])
        with self.assertRaisesRegex(ValueError, "Artifact descriptor must be an object"):
            verify_bundle_artifacts(self.manifest(), self.run_dir)

    def test_descriptor_root_must_match_record_digest(self) -> None:
        # verify_bundle_artifacts checks the record digest against the bytes first,
        # so the root-mismatch branch is only reachable by calling the helper.
        self.write_descriptor(describe_file(self.data).to_dict())
        record = {"path": "data.bin", "sha256": "b" * 64, "descriptor_path": "data.descriptor.json"}
        with self.assertRaisesRegex(ValueError, "Artifact descriptor root mismatch: data.bin"):
            _validate_descriptor_path(record, self.run_dir, self.data)


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
            self.assertIn(
                "### ✅ Supported — The generated figure is the primary result. (claim-1)",
                markdown,
            )
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

    def test_markdown_index_summarizes_claims_runtime_actions_and_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = self._make_run(Path(tempdir))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["claims"] = [
                {
                    "id": "claim-1",
                    "text": "Animal studies compare LNP delivery vs. 3.5 units in target tissue. The conclusion is supported.",
                    "status": "supported",
                    "uncertainty": "The animal evidence has limited generalizability.",
                    "next_action": "Replicate the analysis independently.",
                },
                {
                    "id": "claim-2",
                    "text": "A second claim uses the same next step.",
                    "status": "supported",
                    "uncertainty": "The second claim has a separate limitation.",
                    "next_action": "Replicate the analysis independently.",
                },
                {
                    "id": "claim-3",
                    "text": "An independent check is needed.",
                    "status": "supported",
                    "next_action": "Independently validate the uncertainty bounds.",
                },
                {
                    "id": "claim-4",
                    "text": "A fourth claim shares the replication action.",
                    "status": "supported",
                    "next_action": "Replicate the analysis independently.",
                },
            ]
            manifest["plan"] = [
                {"id": "S1", "description": "Freeze the analysis protocol", "status": "complete"},
                {"id": "S2", "title": "Check evidence sidecars", "status": "pending"},
                {"id": "S3", "status": "pending"},
            ]
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )

            rendered = render_markdown(manifest, manifest_path.parent)

            results = rendered.split("## Results", 1)[1].split("## Limitations and next steps", 1)[0]
            details = rendered.split("## Details", 1)[1]
            self.assertNotIn("**Runtime:**", results)
            self.assertIn("**Runtime:**", details)
            self.assertIn(
                "### ✅ Supported — Animal studies compare LNP delivery vs. 3.5 units in target tissue. (claim-1)",
                rendered,
            )
            self.assertIn(
                "Animal studies compare LNP delivery vs. 3.5 units in target tissue. The conclusion is supported.",
                rendered,
            )
            self.assertIn(
                "**Next step for claim-1, claim-2, claim-4:** Replicate the analysis independently.",
                rendered,
            )
            self.assertEqual(1, rendered.count("Replicate the analysis independently."))
            self.assertIn(
                "- **claim-3**\n  - **Next:** Independently validate the uncertainty bounds.",
                rendered,
            )
            self.assertNotIn("- **claim-4**\n", rendered)
            self.assertIn("**✅ Complete:** Freeze the analysis protocol", details)
            self.assertIn("**⏳ Pending:** Check evidence sidecars", details)
            self.assertIn("**⏳ Pending:** S3", details)

    def test_in_process_renderers_summarize_validated_literature_bundle(self) -> None:
        manifest_path = (
            Path(__file__).resolve().parents[1]
            / "examples"
            / "literature-review-reviewed-run"
            / "manifest.json"
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        markdown = render_markdown(manifest, manifest_path.parent)
        rendered_html = render_html(manifest, manifest_path.parent)

        self.assertIn("### Evidence graph", markdown)
        self.assertIn("### Evidence and execution lanes", markdown)
        self.assertIn("### Query ledger", markdown)
        self.assertIn("[Open the evidence graph]", markdown)
        self.assertIn("Evidence graph", rendered_html)
        self.assertIn("Evidence and execution lanes", rendered_html)
        self.assertIn("Query ledger", rendered_html)
        self.assertIn("No raster image artifacts recorded.", rendered_html)

    def test_in_process_renderers_reject_invalid_artifact_without_writing_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = self._make_run(Path(tempdir))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"][0]["sha256"] = "b" * 64
            write_manifest(manifest, manifest_path)
            before = {
                path.relative_to(manifest_path.parent): path.read_bytes()
                for path in manifest_path.parent.rglob("*")
                if path.is_file()
            }

            for renderer in (render_markdown, render_html):
                with self.subTest(renderer=renderer.__name__):
                    with self.assertRaisesRegex(ValueError, "Artifact digest mismatch: figures/result.png"):
                        renderer(manifest, manifest_path.parent)

            after = {
                path.relative_to(manifest_path.parent): path.read_bytes()
                for path in manifest_path.parent.rglob("*")
                if path.is_file()
            }
            self.assertEqual(before, after)
            self.assertFalse((manifest_path.parent / "index.md").exists())
            self.assertFalse((manifest_path.parent / "index.html").exists())

    def test_in_process_renderers_handle_empty_manifest_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir) / "empty-run"
            run_dir.mkdir()
            manifest = new_manifest("empty-run", "Empty bundle", [])

            markdown = render_markdown(manifest, run_dir)
            rendered_html = render_html(manifest, run_dir)

        self.assertIn("No recorded plan", markdown)
        self.assertIn("No claims recorded.", markdown)
        self.assertIn("No claim-specific limitations", markdown)
        self.assertIn("No report, result, figure", markdown)
        self.assertIn("No plan steps recorded.", markdown)
        self.assertIn("No claims recorded.", rendered_html)
        self.assertIn("No raster image artifacts recorded.", rendered_html)

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

    def test_validate_artifact_reports_digest_errors_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            manifest_path = self._make_run(root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"][0]["sha256"] = "b" * 64
            write_manifest(manifest, manifest_path)
            validator = self.repository_root / "scripts" / "validate_artifact.py"
            result = subprocess.run(
                [sys.executable, "-I", "-S", str(validator), str(manifest_path)],
                cwd=self.repository_root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(1, result.returncode)
            self.assertTrue(result.stderr.startswith("error:"), result.stderr)
            self.assertIn("package_run.py refresh --run-dir", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_validate_artifact_help_lists_sidecar_values_and_example(self) -> None:
        from codex_science import evidence

        validator = self.repository_root / "scripts" / "validate_artifact.py"
        result = subprocess.run(
            [sys.executable, "-I", "-S", str(validator), "--help"],
            cwd=tempfile.gettempdir(),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        values = set().union(
            evidence.SIDECAR_KINDS,
            evidence.RELATIONS,
            evidence.NODE_TYPES,
            evidence.CLAIM_STATUSES,
            evidence.QUERY_STATUSES,
            evidence.EVIDENCE_TYPES,
            evidence.CONFIDENCE_LEVELS,
        )
        help_text = " ".join(result.stdout.split())
        for value in sorted(values):
            self.assertIn(value, help_text)
        example = "examples/literature-review-reviewed-run/"
        self.assertIn(example, help_text)
        self.assertTrue((self.repository_root / example).is_dir())
        skill = (self.repository_root / "runtime-skills" / "science-provenance" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn(example, skill)
        lane = "lanes/pubmed-search.json"
        self.assertTrue((self.repository_root / example / lane).is_file())
        literature_skill = (self.repository_root / "authored-skills" / "literature-review" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        for text in (help_text, skill, literature_skill):
            self.assertIn(lane, text)

    def test_user_facing_plugin_scripts_do_not_require_project_install(self) -> None:
        example = self.repository_root / "examples" / "reviewed-run" / "manifest.json"
        commands = (
            [sys.executable, "-I", "-S", str(self.repository_root / "scripts" / "validate_artifact.py"), str(example)],
            [sys.executable, "-I", "-S", str(self.repository_root / "scripts" / "search_skills.py"), "sympy"],
            [sys.executable, "-I", "-S", str(self.repository_root / "scripts" / "plan_life_science_research.py"), "BRCA1 variant"],
            [sys.executable, "-I", "-S", str(self.repository_root / "scripts" / "science_tool.py"), "science_search_skills", "--query", "sympy"],
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
