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

from codex_science.artifact_store import describe_directory, describe_external_reference, describe_file
from codex_science.artifacts import (
    _validate_descriptor_path,
    add_artifact,
    new_manifest,
    validate_manifest,
    validate_bundle,
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

    def test_local_code_digest_mismatch_blocks_passed_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            source = run / "code/deep/analysis.R"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"changed code\n")
            manifest = new_manifest("code-digest", "Question", [])
            manifest["code"] = [{"path": "code/deep/analysis.R", "sha256": "0" * 64}]
            add_artifact(manifest, "code/deep/analysis.R", kind="code",
                         sha256=hashlib.sha256(source.read_bytes()).hexdigest())
            manifest_path = run / "manifest.json"
            manifest_path.write_text(json.dumps(manifest))
            output = run / "review-output.json"
            cli = Path(__file__).resolve().parents[1] / "scripts/validate_artifact.py"
            result = subprocess.run([sys.executable, str(cli), str(manifest_path),
                                     "--review-output", str(output), "--require-passed-review"],
                                    text=True, capture_output=True, check=False)
            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            finding = next(item for item in json.loads(output.read_text())["findings"]
                           if item["code"] == "code-digest-mismatch")
            self.assertEqual("major", finding["severity"])
            for content in (b"", b"changed code\n"):
                source.write_bytes(content)
                digest = hashlib.sha256(content).hexdigest()
                manifest["code"][0]["sha256"] = digest.upper()
                manifest["artifacts"][0]["sha256"] = digest
                self.assertEqual("passed", review_manifest(manifest, run)["status"])
            manifest["code"][0].pop("sha256")
            manifest["code"][0]["revision"] = "v1"
            self.assertEqual("passed", review_manifest(manifest, run)["status"])
            for value in ("", "0", None, 0, "z" * 64):
                with self.subTest(value=value):
                    manifest["code"][0]["sha256"] = value
                    self.assertIn("code-digest-mismatch", {item["code"] for item in review_manifest(manifest, run)["findings"]})

    def test_lane_output_digest_mismatch_blocks_passed_review(self) -> None:
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "run"
            from codex_science.evidence import validate_sidecars
            self.assertEqual({}, validate_sidecars({}, run, {})["lane_by_id"])
            example = Path(__file__).resolve().parents[1] / "examples/literature-review-reviewed-run"
            shutil.copytree(example, run)
            manifest = json.loads((run / "manifest.json").read_text())
            lane_path = run / "lanes/pubmed-search.json"
            lane = json.loads(lane_path.read_text())
            lane["output_sha256"] = {"./report.md": "0" * 64}
            lane_path.write_text(json.dumps(lane))
            record = next(item for item in manifest["artifacts"] if item["path"] == "lanes/pubmed-search.json")
            record["sha256"] = hashlib.sha256(lane_path.read_bytes()).hexdigest()
            findings = review_manifest(manifest, run)["findings"]
            finding = next(item for item in findings if item["code"] == "lane-output-digest-mismatch")
            self.assertEqual("major", finding["severity"])
            self.assertIn("report.md", finding["message"])
            manifest_path = run / "manifest.json"
            manifest_path.write_text(json.dumps(manifest))
            output = Path(tmp) / "review-output.json"
            cli = example.parents[1] / "scripts/validate_artifact.py"
            result = subprocess.run([sys.executable, str(cli), str(manifest_path),
                                     "--review-output", str(output), "--require-passed-review"],
                                    text=True, capture_output=True, check=False)
            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            self.assertIn("lane-output-digest-mismatch", {item["code"] for item in json.loads(output.read_text())["findings"]})
            for hashes in ({}, {"./report.md": hashlib.sha256((run / "report.md").read_bytes()).hexdigest().upper()}):
                lane["output_sha256"] = hashes
                lane_path.write_text(json.dumps(lane))
                record["sha256"] = hashlib.sha256(lane_path.read_bytes()).hexdigest()
                self.assertEqual("passed", review_manifest(manifest, run)["status"])
            for target, content in (("unregistered.txt", b"changed bytes"), ("empty.txt", b""),
                                    ("missing.txt", None), ("", None), ("../outside.txt", None)):
                with self.subTest(target=target):
                    if content is not None:
                        (run / target).write_bytes(content)
                    lane["output_sha256"] = {target: "0" * 64}
                    lane_path.write_text(json.dumps(lane))
                    record["sha256"] = hashlib.sha256(lane_path.read_bytes()).hexdigest()
                    self.assertEqual("passed", review_manifest(manifest, run)["status"])
            for hashes in (None, [], {"report.md": None}, {"report.md": ""}, {"report.md": "z" * 64}):
                with self.subTest(hashes=hashes):
                    lane["output_sha256"] = hashes
                    lane_path.write_text(json.dumps(lane))
                    record["sha256"] = hashlib.sha256(lane_path.read_bytes()).hexdigest()
                    with self.assertRaises(ValueError):
                        validate_bundle(manifest, run)
            from codex_science.fair_export import export_run
            tree = run / "tree"
            tree.mkdir()
            directory_record = {"path": "tree", "kind": "data", "artifact_type": "directory-tree"}
            manifest["artifacts"].append(directory_record)
            lane["outputs"].append("tree")
            for index, content in enumerate((None, b"", b"changed bytes")):
                with self.subTest(directory_content=content):
                    if content is not None:
                        (tree / "data.bin").write_bytes(content)
                    descriptor = describe_directory(tree)
                    directory_record.update(sha256=descriptor.root_sha256, size_bytes=descriptor.total_bytes,
                                            entry_count=descriptor.entry_count)
                    lane["output_sha256"] = {"./tree/": descriptor.root_sha256}
                    lane_path.write_text(json.dumps(lane))
                    record["sha256"] = hashlib.sha256(lane_path.read_bytes()).hexdigest()
                    self.assertEqual("passed", review_manifest(manifest, run)["status"])
                    manifest_path.write_text(json.dumps(manifest))
                    self.assertEqual("generated", export_run(manifest_path, Path(tmp) / f"tree-export-{index}")["status"])
                    lane["output_sha256"]["./tree/"] = "0" * 64
                    lane_path.write_text(json.dumps(lane))
                    record["sha256"] = hashlib.sha256(lane_path.read_bytes()).hexdigest()
                    finding = next(item for item in review_manifest(manifest, run)["findings"]
                                   if item["code"] == "lane-output-digest-mismatch")
                    self.assertEqual("major", finding["severity"])
                    manifest_path.write_text(json.dumps(manifest))
                    rejected = Path(tmp) / f"tree-rejected-{index}"
                    with self.assertRaisesRegex(ValueError, "Bundle digest mismatch"):
                        export_run(manifest_path, rejected)
                    self.assertFalse(rejected.exists())
                    for invalid in (None, "", "z" * 64):
                        lane["output_sha256"]["./tree/"] = invalid
                        lane_path.write_text(json.dumps(lane))
                        record["sha256"] = hashlib.sha256(lane_path.read_bytes()).hexdigest()
                        with self.assertRaises(ValueError):
                            validate_bundle(manifest, run)
            for raw_path in ([], {}, 0, None):
                with self.subTest(raw_path=raw_path):
                    relative = str(raw_path)
                    target = run / relative
                    target.write_bytes(b"legacy path bytes")
                    digest = hashlib.sha256(target.read_bytes()).hexdigest()
                    manifest["artifacts"].append({"path": raw_path, "kind": "data", "sha256": digest})
                    lane["outputs"].append(relative)
                    lane["output_sha256"] = {relative: digest}
                    lane_path.write_text(json.dumps(lane))
                    record["sha256"] = hashlib.sha256(lane_path.read_bytes()).hexdigest()
                    self.assertEqual("passed", review_manifest(manifest, run)["status"])

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

    def test_bundle_refuses_external_descriptor_with_false_size(self) -> None:
        payload = describe_external_reference(uri="s3://bucket/data", version="v1", sha256=self.digest, size_bytes=999).to_dict()
        self.write_descriptor(payload)
        with self.assertRaisesRegex(ValueError, "do not match descriptor"):
            validate_bundle(self.manifest(), self.run_dir)

    def test_descriptor_symlink_must_remain_inside_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / "descriptor.json"
            external.write_text(json.dumps(describe_file(self.data).to_dict()), encoding="utf-8")
            link = self.run_dir / "data.descriptor.json"
            link.symlink_to(external)
            with self.assertRaisesRegex(ValueError, "descriptor resolves outside"):
                validate_bundle(self.manifest(), self.run_dir)
            link.unlink()
            internal = self.run_dir / "internal.json"
            internal.write_text(external.read_text(encoding="utf-8"), encoding="utf-8")
            link.symlink_to(internal)
            validate_bundle(self.manifest(), self.run_dir)

    def test_bundle_and_index_refuse_contradictory_descriptor_sidecars(self) -> None:
        dataset = self.run_dir / "tree"
        dataset.mkdir()
        (dataset / "a").write_bytes(b"abc")
        for descriptor in (describe_file(self.data), describe_directory(dataset)):
            payload = descriptor.to_dict()
            payload["root_sha256"] = "0" * 64
            self.write_descriptor(payload)
            manifest = new_manifest("run-001", "Question", [])
            digest = hashlib.sha256((self.run_dir / "data.descriptor.json").read_bytes()).hexdigest()
            add_artifact(manifest, "data.descriptor.json", kind="artifact-descriptor", sha256=digest)
            for action in (validate_bundle, render_markdown, render_html):
                with self.subTest(kind=descriptor.artifact_type, action=action.__name__), self.assertRaises(ValueError):
                    action(manifest, self.run_dir)

    def test_bundle_refuses_noninteger_metadata_without_truncation(self) -> None:
        self.write_descriptor(describe_file(self.data).to_dict())
        for field, valid in (("size_bytes", len(b"payload")), ("entry_count", 1)):
            for value in (valid + 0.9, float(valid), True, "3", "", None, -1):
                manifest = self.manifest()
                manifest["artifacts"][0][field] = value
                with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, "non-negative integer"):
                    validate_bundle(manifest, self.run_dir)
                if value is not None:
                    with self.subTest(field=field, value=value, caller="add_artifact"), self.assertRaisesRegex(ValueError, "non-negative integer"):
                        add_artifact(new_manifest("run-002", "Question", []), "data.bin", kind="blob", sha256=self.digest, **{field: value})
            manifest = self.manifest()
            manifest["artifacts"][0][field] = valid
            validate_bundle(manifest, self.run_dir)
        self.data.write_bytes(b"")
        self.digest = hashlib.sha256(b"").hexdigest()
        self.write_descriptor(describe_file(self.data).to_dict())
        manifest = self.manifest()
        manifest["artifacts"][0].update(size_bytes=0, entry_count=1)
        validate_bundle(manifest, self.run_dir)

    def test_bundle_and_index_refuse_canonical_duplicate_paths(self) -> None:
        manifest = new_manifest("run-001", "Question", [])
        add_artifact(manifest, "data.bin", kind="metrics", sha256=self.digest)
        add_artifact(manifest, "./data.bin", kind="report", sha256=self.digest)
        for action in (validate_bundle, render_markdown, render_html):
            with self.subTest(action=action.__name__), self.assertRaisesRegex(ValueError, "Duplicate artifact path"):
                action(manifest, self.run_dir)

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
    def test_cli_preserves_recorded_code_and_execution_provenance(self) -> None:
        for field in ("code", "missing-code", "executions", "superseded_executions", "journal"):
            for output in ("index.md", "index.html"):
                with self.subTest(field=field, output=output), tempfile.TemporaryDirectory() as tempdir:
                    manifest_path = self._make_run(Path(tempdir))
                    run = manifest_path.parent
                    source = run / ("execution-log.jsonl" if field == "journal" else output)
                    content = b'{"id":"E1"}\n' if field == "journal" else b""
                    if field != "missing-code":
                        source.write_bytes(content)
                    manifest = json.loads(manifest_path.read_text())
                    digest = hashlib.sha256(content).hexdigest()
                    if field in ("code", "missing-code"):
                        manifest["code"] = [{"path": source.name, "sha256": digest}]
                    else:
                        record = {"id": "E1", "exit_code": 0}
                        if field != "journal":
                            record.update(log_path=source.name, log_sha256=digest)
                        manifest["executions" if field == "journal" else field] = [record]
                    if field == "journal":
                        (run / output).symlink_to(source)
                    write_manifest(manifest, manifest_path)
                    self.assertEqual("passed", review_manifest(manifest, run)["status"])
                    before = {p.relative_to(run): p.read_bytes() for p in run.rglob("*") if p.is_file()}
                    result = subprocess.run(
                        [sys.executable, str(self.script), str(manifest_path), "--html"],
                        capture_output=True, text=True,
                        timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120")),
                    )
                    self.assertEqual(1, result.returncode, result.stderr)
                    self.assertIn("output path would overwrite input", result.stderr)
                    self.assertEqual("", result.stdout)
                    self.assertEqual(before, {p.relative_to(run): p.read_bytes() for p in run.rglob("*") if p.is_file()})
                    self.assertEqual("passed", review_manifest(manifest, run)["status"])
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = self._make_run(Path(tempdir))
            manifest = json.loads(manifest_path.read_text())
            manifest["code"] = [None, 0, {}, {"path": 0, "sha256": "0" * 64}]
            for value in ("", "missing.py", "https://example.test/code.py", "../outside.py"):
                manifest["code"].append({"path": value, "sha256": "0" * 64})
            manifest["code"].append({"path": str(manifest_path.parent / "index.md"), "sha256": "0" * 64})
            manifest["executions"] = [{"id": "no-log", "exit_code": 0}]
            for value in (None, 0, "", "missing.log", "https://example.test/log", "bad\x00path", "../outside.log"):
                manifest["executions"].append({"exit_code": 0, "log_path": value, "log_sha256": "0" * 64})
            write_manifest(manifest, manifest_path)
            result = subprocess.run(
                [sys.executable, str(self.script), str(manifest_path), "--html"],
                capture_output=True, text=True,
                timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120")),
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((manifest_path.parent / "index.md").is_file())
            self.assertTrue((manifest_path.parent / "index.html").is_file())

    def test_cli_protects_numeric_manifest_paths_before_writing_indexes(self) -> None:
        for field in ("path", "descriptor_path"):
            for value in (0, 123):
                for alias in ("symlink", "hardlink"):
                    with self.subTest(field=field, value=value, alias=alias), tempfile.TemporaryDirectory() as tempdir:
                        manifest_path = self._make_run(Path(tempdir))
                        run = manifest_path.parent
                        manifest = json.loads(manifest_path.read_text())
                        numeric = run / str(value)
                        if field == "path":
                            numeric.write_bytes(b"numeric artifact")
                            manifest["artifacts"].append({"path": value, "kind": "result",
                                                          "sha256": hashlib.sha256(numeric.read_bytes()).hexdigest()})
                        else:
                            numeric.write_text(json.dumps(describe_file(run / "report.md").to_dict()))
                            manifest["artifacts"][-1][field] = value
                        write_manifest(manifest, manifest_path)
                        validate_bundle(manifest, run)
                        output = run / "index.html"
                        if alias == "symlink":
                            output.symlink_to(numeric)
                        else:
                            os.link(numeric, output)
                        entries = set(run.rglob("*"))
                        before = {path.relative_to(run): path.read_bytes() for path in entries if path.is_file()}
                        result = subprocess.run([sys.executable, str(self.script), str(manifest_path), "--html"],
                                                capture_output=True, text=True,
                                                timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120")))
                        self.assertEqual(1, result.returncode, result.stderr)
                        self.assertTrue(result.stderr.startswith("error:"), result.stderr)
                        self.assertIn("would overwrite input", result.stderr)
                        self.assertNotIn("Traceback", result.stderr)
                        self.assertEqual("", result.stdout)
                        self.assertEqual(entries, set(run.rglob("*")))
                        self.assertEqual(before, {path.relative_to(run): path.read_bytes() for path in entries if path.is_file()})

    def test_preflight_refuses_loops_in_protected_path_components(self) -> None:
        from codex_science.cli_io import preflight_output_paths

        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            loop = root / "loop"
            loop.symlink_to(loop)
            first = root / "first"
            second = root / "second"
            first.symlink_to(second)
            second.symlink_to(first)
            indirect = root / "indirect"
            indirect.symlink_to(loop / "missing")
            looping_paths = (loop, loop / "missing" / "nested", first, second / "child",
                             indirect / "child", root / "absent" / ".." / "loop")
            before = set(root.iterdir())
            for keyword in ("inputs", "protected_dirs"):
                for path in looping_paths:
                    with self.subTest(keyword=keyword, path=path), self.assertRaisesRegex(ValueError, "invalid protected input path"):
                        preflight_output_paths(root / "output", **{keyword: [path]})
                dangling = root / (keyword + "-dangling")
                dangling.symlink_to(root / "missing-target")
                preflight_output_paths(root / "output", **{keyword: [dangling / "child"]})
                dangling.unlink()
                directory = root / (keyword + "-directory")
                directory.mkdir()
                alias = root / (keyword + "-alias")
                alias.symlink_to(directory, target_is_directory=True)
                preflight_output_paths(root / "output", **{keyword: [alias / "child"]})
                alias.unlink()
                directory.rmdir()
            self.assertEqual(before, set(root.iterdir()))

    def test_preflight_protects_inputs_and_directory_trees(self) -> None:
        from codex_science.cli_io import preflight_output_paths

        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            source = root / "source"
            source.write_bytes(b"original")
            symbolic = root / "symbolic"
            symbolic.symlink_to(source)
            hard = root / "hard"
            os.link(source, hard)
            for destination in (source, symbolic, hard, root):
                with self.subTest(destination=destination), self.assertRaises(ValueError):
                    preflight_output_paths(destination, inputs=[source])
            # Missing inputs still reserve their resolved spelling and ancestors.
            for destination in (root / "missing", root / "missing" / "input"):
                with self.subTest(destination=destination), self.assertRaises(ValueError):
                    preflight_output_paths(destination, inputs=[root / "missing" / "input"])
            preflight_output_paths(None, root / "new", inputs=[])
            preflight_output_paths(root / "source-other", inputs=[source])
            preflight_output_paths(root / "new", inputs=[symbolic, hard])
            unavailable = root / "unavailable"
            original_resolve = Path.resolve

            def guarded_resolve(path, *args, **kwargs):
                if path == unavailable:
                    raise PermissionError("unreadable protected path")
                return original_resolve(path, *args, **kwargs)

            with mock.patch.object(Path, "resolve", guarded_resolve):
                preflight_output_paths(root / "new", inputs=[unavailable], protected_dirs=[unavailable])
            with mock.patch.object(Path, "is_symlink", side_effect=PermissionError("unreadable link probe")):
                preflight_output_paths(root / "new", inputs=[unavailable], protected_dirs=[unavailable])
            with mock.patch("codex_science.cli_io.os.path.samefile", side_effect=PermissionError("unreadable identity")):
                preflight_output_paths(root / "new", inputs=[source])
            for destination in (root / "tree", root / "tree" / "child", root / "tree" / "nested" / "file"):
                with self.subTest(protected=destination), self.assertRaises(ValueError):
                    preflight_output_paths(destination, protected_dirs=[root / "tree"])
            preflight_output_paths(root / "tree-other", protected_dirs=[root / "tree"])
            tree = root / "tree"
            tree.mkdir()
            preflight_output_paths(root / "new", protected_dirs=[tree])
            child = tree / "0"
            child.write_bytes(b"protected child")
            alias = root / "child-alias"
            os.link(child, alias)
            preflight_output_paths(alias, protected_dirs=[tree])
            with self.assertRaisesRegex(ValueError, "would overwrite input"):
                preflight_output_paths(alias, inputs=[child], protected_dirs=[tree])
            (tree / "back").symlink_to(tree, target_is_directory=True)
            preflight_output_paths(root / "new", protected_dirs=[tree])
            (tree / "loop").symlink_to(tree / "loop")
            preflight_output_paths(root / "new", protected_dirs=[tree])
            (tree / "loop").unlink()
            with self.assertRaises(ValueError):
                preflight_output_paths(root / "tree", protected_dirs=[root / "tree" / "nested"])
            with self.assertRaises(ValueError):
                preflight_output_paths(root / "bad\x00", inputs=[source])
            loop = root / "loop"
            loop.symlink_to(loop)
            for keywords in ({"inputs": [loop]}, {"protected_dirs": [loop]}):
                with self.subTest(keywords=keywords), self.assertRaises(ValueError):
                    preflight_output_paths(root / "new", **keywords)
            self.assertEqual(b"original", source.read_bytes())

    def test_cli_refuses_index_input_conflicts_before_either_write(self) -> None:
        for conflict in ("manifest-md", "manifest-html", "artifact-md", "artifact-html",
                         "symlink", "hardlink", "outputs-alias", "html-directory", "input-md",
                         "input-tree", "input-loop", "manifest-loop", "input-unreadable", "input-ancestor"):
            with self.subTest(conflict=conflict), tempfile.TemporaryDirectory() as tempdir:
                manifest_path = self._make_run(Path(tempdir))
                run = manifest_path.parent
                if conflict.startswith("manifest-"):
                    renamed = run / ("index.md" if conflict.endswith("md") else "index.html")
                    manifest_path.rename(renamed)
                    manifest_path = renamed
                elif conflict.startswith("artifact-"):
                    artifact = run / ("index.md" if conflict.endswith("md") else "index.html")
                    artifact.write_bytes(b"registered result")
                    manifest = json.loads(manifest_path.read_text())
                    add_artifact(manifest, artifact.name, kind="result", sha256=hashlib.sha256(artifact.read_bytes()).hexdigest())
                    write_manifest(manifest, manifest_path)
                elif conflict in ("symlink", "hardlink"):
                    destination = run / "index.html"
                    if conflict == "symlink":
                        destination.symlink_to(run / "report.md")
                    else:
                        os.link(run / "report.md", destination)
                elif conflict == "outputs-alias":
                    (run / "index.md").write_bytes(b"previous view")
                    os.link(run / "index.md", run / "index.html")
                elif conflict == "html-directory":
                    (run / "index.html").mkdir()
                elif conflict.startswith("input-"):
                    source = run / ("index.md" if conflict == "input-md" else "source")
                    if conflict in ("input-tree", "input-unreadable"):
                        source.mkdir()
                        child = source / "data"
                        child.write_bytes(b"declared input")
                        if conflict == "input-tree":
                            os.link(child, run / "index.html")
                        else:
                            (source / "unreadable").mkdir()
                    elif conflict == "input-ancestor":
                        source = Path(tempdir)
                    elif conflict == "input-loop":
                        source.symlink_to(source)
                    else:
                        source.write_bytes(b"declared input")
                    manifest = json.loads(manifest_path.read_text())
                    manifest["inputs"].append({"path": str(source) if conflict == "input-ancestor" else source.name})
                    write_manifest(manifest, manifest_path)
                elif conflict == "manifest-loop":
                    manifest_path = run / "manifest-loop"
                    manifest_path.symlink_to(manifest_path)
                before = {path.relative_to(run): path.read_bytes() for path in run.rglob("*") if path.is_file()}
                entries = set(run.rglob("*"))
                command = [sys.executable, str(self.script), str(manifest_path), "--html"]
                if conflict == "input-unreadable":
                    launcher = (
                        "import runpy, sys; from pathlib import Path; original = Path.iterdir; "
                        "blocked = Path(sys.argv.pop(1)); "
                        "Path.iterdir = lambda path: (_ for _ in ()).throw(PermissionError('unreadable')) "
                        "if path == blocked else original(path); "
                        "script = sys.argv[1]; sys.argv = sys.argv[1:]; runpy.run_path(script, run_name='__main__')"
                    )
                    command = [sys.executable, "-c", launcher, str(source / "unreadable"), *command[1:]]
                result = subprocess.run(command,
                                        capture_output=True, text=True,
                                        timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120")))
                if conflict in ("input-tree", "input-unreadable", "input-ancestor"):
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertTrue((run / "index.md").is_file())
                    self.assertTrue((run / "index.html").is_file())
                    for relative, content in before.items():
                        if relative != Path("index.html"):
                            self.assertEqual(content, (run / relative).read_bytes())
                    continue
                self.assertEqual(1, result.returncode, result.stderr)
                self.assertTrue(result.stderr.startswith("error:"), result.stderr)
                self.assertEqual("", result.stdout)
                self.assertEqual(entries, set(run.rglob("*")))
                self.assertEqual(before, {path.relative_to(run): path.read_bytes() for path in run.rglob("*") if path.is_file()})

    def test_preflight_registered_tree_uses_containment_without_listing(self) -> None:
        from codex_science.cli_io import preflight_output_paths

        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            tree = root / "registered-tree"
            tree.mkdir()
            (tree / "link").symlink_to(Path("/"), target_is_directory=True)
            with mock.patch.object(Path, "iterdir", side_effect=AssertionError("preflight must not list trees")):
                preflight_output_paths(root / "index.md", inputs=[tree], protected_dirs=[tree])
                with self.assertRaisesRegex(ValueError, "overlaps protected directory"):
                    preflight_output_paths(tree / "index.md", protected_dirs=[tree])

    def test_preflight_symlink_containment_uses_resolved_ancestry(self) -> None:
        from codex_science.cli_io import preflight_output_paths

        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir).resolve()
            tree = root / "protected"
            tree.mkdir()
            outside = root / "outside"
            outside.mkdir()
            escape = tree / "escape"
            escape.symlink_to(outside, target_is_directory=True)
            entrance = outside / "entrance"
            entrance.symlink_to(tree, target_is_directory=True)
            before = set(root.rglob("*"))
            with mock.patch.object(Path, "iterdir", side_effect=AssertionError("preflight must not list trees")):
                with self.subTest(shape="output escapes protected tree"):
                    preflight_output_paths(escape / "report.json", protected_dirs=[tree])
                with self.subTest(shape="output enters protected tree"), self.assertRaisesRegex(
                    ValueError, "output path overlaps protected directory"
                ):
                    preflight_output_paths(entrance / "report.json", protected_dirs=[tree])
                with self.subTest(shape="escaping output is unrelated to input"):
                    preflight_output_paths(escape / "future", inputs=[tree / "future" / "input.json"])
                with self.subTest(shape="entering output is an input ancestor"), self.assertRaisesRegex(
                    ValueError, "output path is an input ancestor"
                ):
                    preflight_output_paths(entrance / "future", inputs=[tree / "future" / "input.json"])
                with self.subTest(shape="input escapes into output ancestry"), self.assertRaisesRegex(
                    ValueError, "output path is an input ancestor"
                ):
                    preflight_output_paths(outside / "future", inputs=[escape / "future" / "input.json"])
                with self.subTest(shape="input enters unrelated tree"):
                    preflight_output_paths(outside / "future", inputs=[entrance / "future" / "input.json"])
                with mock.patch("codex_science.cli_io.os.stat", side_effect=PermissionError("identity unavailable")):
                    preflight_output_paths(outside / "0.json", tree / "1.json")
            self.assertEqual(before, set(root.rglob("*")))

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

    def test_renderer_marks_changed_code_review_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run = Path(tempdir)
            source = run / "analysis.py"
            source.write_bytes(b"original code\n")
            manifest = new_manifest("integrity", "Is the recorded review current?", [])
            manifest.pop("runtime_history", None)
            manifest.pop("runtime_span", None)
            manifest["code"] = [{
                "path": source.name,
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            }]
            manifest["review"] = {"status": "passed", "findings": []}
            manifest_path = run / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            clean_hashes = {
                render_markdown: "a22c1923fd8904bdd93a789b1f9f375859d5280e8e31c04b0664c939dd6156b2",
                render_html: "6165fa2a7eae7497487e0491461871fb5f767d9519b961ec67890bf35c40f813",
            }
            for renderer, expected in clean_hashes.items():
                self.assertEqual(expected, hashlib.sha256(
                    renderer(manifest, run).encode("utf-8")
                ).hexdigest())
            for content in (b"changed code\n", b""):
                with self.subTest(content=content):
                    source.write_bytes(content)
                    findings = validate_bundle(manifest, run)["digest_findings"]
                    self.assertEqual(["code-digest-mismatch"], [item["code"] for item in findings])
                    result = subprocess.run(
                        [sys.executable, "-I", "-S", str(self.script), str(manifest_path), "--html"],
                        capture_output=True, text=True, check=False,
                        timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120")),
                    )
                    self.assertEqual(0, result.returncode, result.stderr)
                    for name in ("index.md", "index.html"):
                        rendered = (run / name).read_text(encoding="utf-8")
                        self.assertIn("Stale (recorded:", rendered)
                        self.assertIn("Current integrity findings", rendered)
                        for finding in findings:
                            self.assertIn(finding["code"], rendered)
                            self.assertIn(finding["severity"], rendered)
                            self.assertIn(finding["message"], rendered)
                    self.assertEqual("passed", manifest["review"]["status"])
            source.write_bytes(b"original code\n")
            for renderer, expected in clean_hashes.items():
                self.assertEqual(expected, hashlib.sha256(
                    renderer(manifest, run).encode("utf-8")
                ).hexdigest())

    def test_renderer_lists_lane_digest_findings(self) -> None:
        import shutil

        with tempfile.TemporaryDirectory() as tempdir:
            run = Path(tempdir) / "run"
            shutil.copytree(self.repository_root / "examples/literature-review-reviewed-run", run)
            manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
            lane_path = run / "lanes/pubmed-search.json"
            lane = json.loads(lane_path.read_text(encoding="utf-8"))
            lane["output_sha256"] = {"./report.md": "0" * 64, "studies.json": "0" * 64}
            lane_path.write_text(json.dumps(lane), encoding="utf-8")
            record = next(item for item in manifest["artifacts"] if item["path"] == "lanes/pubmed-search.json")
            record["sha256"] = hashlib.sha256(lane_path.read_bytes()).hexdigest()
            findings = validate_bundle(manifest, run)["digest_findings"]
            self.assertEqual(["lane-output-digest-mismatch"] * 2, [item["code"] for item in findings])
            for renderer in (render_markdown, render_html):
                with self.subTest(renderer=renderer.__name__):
                    rendered = renderer(manifest, run)
                    self.assertIn("Stale (recorded:", rendered)
                    for finding in findings:
                        self.assertIn(finding["code"], rendered)
                        self.assertIn(finding["severity"], rendered)
                        self.assertIn(finding["message"], rendered)

    def test_renderer_rejects_malformed_claim_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run = Path(tempdir)
            manifest = new_manifest("claim-shape", "A claim", [])
            manifest["claims"] = [{"id": "C1", "text": "a claim"}]
            manifest_path = run / "manifest.json"
            for evidence in (None, 0, False, "", "report.md", {}, {"path": "report.md"}):
                for existing_outputs in (False, True):
                    with self.subTest(evidence=evidence, existing_outputs=existing_outputs):
                        manifest["claims"][0]["evidence"] = evidence
                        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                        for name in ("index.md", "index.html"):
                            if existing_outputs:
                                (run / name).write_bytes(b"existing index\n")
                            else:
                                (run / name).unlink(missing_ok=True)
                        result = subprocess.run(
                            [sys.executable, "-I", "-S", str(self.script), str(manifest_path), "--html"],
                            capture_output=True, text=True, check=False,
                            timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120")),
                        )
                        self.assertEqual(1, result.returncode)
                        self.assertEqual("", result.stdout)
                        self.assertIn("error: Claim evidence must be a list: C1", result.stderr)
                        self.assertNotIn("Traceback", result.stderr)
                        for name in ("index.md", "index.html"):
                            if existing_outputs:
                                self.assertEqual(b"existing index\n", (run / name).read_bytes())
                            else:
                                self.assertFalse((run / name).exists())
                        for renderer in (render_markdown, render_html):
                            with self.assertRaisesRegex(ValueError, "Claim evidence must be a list: C1"):
                                renderer(manifest, run)
            for evidence in ([], ["report.md"]):
                manifest["claims"][0]["evidence"] = evidence
                for renderer in (render_markdown, render_html):
                    self.assertIn("a claim", renderer(manifest, run))
            manifest["claims"][0].pop("evidence")
            for renderer in (render_markdown, render_html):
                self.assertIn("a claim", renderer(manifest, run))

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

    def test_validate_artifact_and_completion_canonicalize_registered_computed_claim_ids(self) -> None:
        from codex_science.checkpoints import _check_completion_bundle

        with tempfile.TemporaryDirectory() as temporary:
            manifest_path = self._make_run(Path(temporary))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            claim = manifest["claims"][0]
            base_artifacts = manifest["artifacts"][:]
            output = manifest_path.parent / "computed-review.json"
            validator = self.repository_root / "scripts" / "validate_artifact.py"
            for claim_id, canonical in (("C1", "C1"), (" C1 ", "C1"),
                                        ("\tC1\n", "C1"), (0, "0"), (" 0 ", "0")):
                for graph_kind in (None, "evidence-graph", "evidence-graph-v2"):
                    claim["id"] = claim_id
                    registered = {**claim, "id": f" {canonical} ", "status": "supported",
                        "required_evidence": ["computed"], "required_support": 0,
                        "falsifier": "Recomputation disagrees with the saved result."}
                    register = manifest_path.parent / "claims.json"
                    register.write_text(json.dumps({"schema_version": 1, "claims": [registered]}), encoding="utf-8")
                    manifest["artifacts"] = base_artifacts[:]
                    add_artifact(manifest, "claims.json", kind="claim-register",
                                 sha256=hashlib.sha256(register.read_bytes()).hexdigest())
                    if graph_kind:
                        graph_path = manifest_path.parent / "evidence_graph.json"
                        graph_path.write_text(json.dumps({
                            "schema_version": 2 if graph_kind == "evidence-graph-v2" else 1,
                            "nodes": [{"id": f" {canonical} ", "type": "claim"},
                                      {"id": " saved-result ", "type": "artifact", "path": claim["evidence"][0]}],
                            "edges": [{"source": "saved-result", "target": f"\t{canonical}\n", "relation": "supports"}],
                        }), encoding="utf-8")
                        add_artifact(manifest, "evidence_graph.json", kind=graph_kind,
                                     sha256=hashlib.sha256(graph_path.read_bytes()).hexdigest())
                    for executions, passed in (
                        ([], False),
                        ([{"exit_code": 0, "outputs": [claim["evidence"][0]]}], True),
                    ):
                        with self.subTest(claim_id=claim_id, graph=graph_kind, executions=executions):
                            manifest["executions"] = executions
                            write_manifest(manifest, manifest_path)
                            result = subprocess.run(
                                [sys.executable, "-I", "-S", str(validator), str(manifest_path),
                                 "--review-output", str(output), "--require-passed-review"],
                                cwd=self.repository_root, capture_output=True, text=True, check=False,
                            )
                            self.assertEqual(0 if passed else 1, result.returncode, result.stderr)
                            self.assertIn("artifact bundle: valid", result.stdout)
                            self.assertNotIn("Traceback", result.stderr)
                            review = json.loads(output.read_text(encoding="utf-8"))
                            findings = [item for item in review["findings"]
                                        if item["code"] == "computed-claim-without-execution"]
                            self.assertEqual([] if passed else [canonical], [item["claim_id"] for item in findings])
                            if passed:
                                _check_completion_bundle(manifest_path.parent)
                            else:
                                with self.assertRaisesRegex(ValueError, "computed-claim-without-execution"):
                                    _check_completion_bundle(manifest_path.parent)

    def test_validate_artifact_checks_falsy_computed_claim_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest_path = self._make_run(Path(temporary))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            claim = manifest["claims"][0]
            claim["required_evidence"] = ["computed"]
            output = manifest_path.parent / "computed-review.json"
            validator = self.repository_root / "scripts" / "validate_artifact.py"
            for claim_id in (0, 0.0, False, None, [], {}, "C1"):
                for executions, passed in (
                    ([], False),
                    ([{"exit_code": 0, "outputs": [claim["evidence"][0]]}], True),
                ):
                    with self.subTest(claim_id=claim_id, executions=executions):
                        claim["id"] = claim_id
                        manifest["executions"] = executions
                        write_manifest(manifest, manifest_path)
                        result = subprocess.run(
                            [sys.executable, "-I", "-S", str(validator), str(manifest_path),
                             "--review-output", str(output), "--require-passed-review"],
                            cwd=self.repository_root, capture_output=True, text=True, check=False,
                        )
                        self.assertEqual(0 if passed else 1, result.returncode, result.stderr)
                        self.assertIn("artifact bundle: valid", result.stdout)
                        self.assertNotIn("Traceback", result.stderr)
                        review = json.loads(output.read_text(encoding="utf-8"))
                        self.assertEqual("passed" if passed else "findings", review["status"])
                        findings = [item for item in review["findings"]
                                    if item["code"] == "computed-claim-without-execution"]
                        self.assertEqual([] if passed else [str(claim_id)],
                                         [item["claim_id"] for item in findings])
            for invalid in ("", " \t\n"):
                with self.subTest(invalid_id=invalid):
                    claim["id"] = invalid
                    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                    output.unlink(missing_ok=True)
                    result = subprocess.run(
                        [sys.executable, "-I", "-S", str(validator), str(manifest_path),
                         "--review-output", str(output), "--require-passed-review"],
                        cwd=self.repository_root, capture_output=True, text=True, check=False,
                    )
                    self.assertEqual(1, result.returncode)
                    self.assertIn("Claim id is required", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertFalse(output.exists())

    def test_validate_artifact_accepts_safe_computed_output_path_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest_path = self._make_run(Path(temporary))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            claim = manifest["claims"][0]
            claim["required_evidence"] = ["computed"]
            output = manifest_path.parent / "computed-review.json"
            validator = self.repository_root / "scripts" / "validate_artifact.py"
            for artifact_path, output_path, directory, passed in (
                ("./report.md", "report.md", False, True),
                ("report.md", "./report.md", False, True),
                ("tables/", "tables", True, True),
                ("tables", "./tables/", True, True),
                ("./tables//./", "tables", True, True),
                ("report.md", "../report.md", False, False),
            ):
                with self.subTest(artifact=artifact_path, output=output_path):
                    artifact = manifest_path.parent / artifact_path
                    digest = (describe_directory(artifact).root_sha256 if directory
                              else hashlib.sha256(artifact.read_bytes()).hexdigest())
                    manifest["artifacts"] = [{"path": artifact_path, "kind": "table",
                        "sha256": digest, "artifact_type": "directory-tree" if directory else "file"}]
                    claim["evidence"] = [artifact_path]
                    manifest["executions"] = [{"exit_code": 0,
                        "outputs": [{"path": output_path, "sha256": digest}]}]
                    write_manifest(manifest, manifest_path)
                    result = subprocess.run(
                        [sys.executable, "-I", "-S", str(validator), str(manifest_path),
                         "--review-output", str(output), "--require-passed-review"],
                        cwd=self.repository_root, capture_output=True, text=True, check=False,
                    )
                    self.assertEqual(0 if passed else 1, result.returncode, result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                    review = json.loads(output.read_text(encoding="utf-8"))
                    self.assertEqual("passed" if passed else "findings", review["status"])

    def test_validate_artifact_writes_structured_review_for_null_computed_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest_path = self._make_run(Path(temporary))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["claims"][0].update(required_evidence=["computed"], evidence=None)
            manifest["executions"] = [{"exit_code": 0, "outputs": ["report.md"]}]
            write_manifest(manifest, manifest_path)
            output = manifest_path.parent / "computed-review.json"
            validator = self.repository_root / "scripts" / "validate_artifact.py"
            result = subprocess.run(
                [sys.executable, "-I", "-S", str(validator), str(manifest_path),
                 "--review-output", str(output), "--require-passed-review"],
                cwd=self.repository_root, capture_output=True, text=True, check=False,
            )
            self.assertEqual(1, result.returncode, result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn("artifact bundle: valid", result.stdout)
            self.assertTrue(output.is_file())
            review = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual("findings", review["status"])
            self.assertIn("unsupported-claim", {item["code"] for item in review["findings"]})

    def test_validate_artifact_requires_computed_execution_without_graph(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest_path = self._make_run(Path(temporary))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            claim = manifest["claims"][0]
            claim["required_evidence"] = ["computed"]
            output = manifest_path.parent / "computed-review.json"
            validator = self.repository_root / "scripts" / "validate_artifact.py"
            for executions, passed in (
                ([], False),
                ([{"exit_code": 0, "outputs": [claim["evidence"][0]]}], True),
                ([{"exit_code": 1, "outputs": [claim["evidence"][0]]}], False),
                ([{"exit_code": 0, "outputs": []}], False),
            ):
                with self.subTest(executions=executions):
                    manifest["executions"] = executions
                    write_manifest(manifest, manifest_path)
                    result = subprocess.run(
                        [sys.executable, "-I", "-S", str(validator), str(manifest_path),
                         "--review-output", str(output), "--require-passed-review"],
                        cwd=self.repository_root, capture_output=True, text=True, check=False,
                    )
                    self.assertEqual(0 if passed else 1, result.returncode, result.stderr)
                    review = json.loads(output.read_text(encoding="utf-8"))
                    self.assertEqual("passed" if passed else "findings", review["status"])
                    self.assertIn("artifact bundle: valid", result.stdout)
                    codes = {item["code"] for item in review["findings"]}
                    self.assertEqual(not passed, "computed-claim-without-execution" in codes)

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
