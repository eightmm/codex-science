import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import unquote, urljoin, urlsplit

from codex_science.artifact_store import describe_directory
from codex_science.artifacts import add_artifact, new_manifest, write_manifest
from codex_science.fair_export import _write_json, export_run


CLI = Path(__file__).resolve().parents[1] / "scripts" / "export_scientific_run.py"
EXPORT_FILES = ("ro-crate-metadata.json", "prov.json", "scientific-bom.json", "export-receipt.json")


class FairExportTests(unittest.TestCase):
    def _bundle(self, root: Path, artifact_name: str = "result.csv") -> Path:
        run = root / "run"
        run.mkdir()
        artifact = run / artifact_name
        artifact.write_bytes(b"recorded artifact\n")
        manifest = new_manifest("run-fair", "Q", [])
        add_artifact(manifest, artifact_name, kind="result", sha256=hashlib.sha256(artifact.read_bytes()).hexdigest())
        path = run / "manifest.json"
        write_manifest(manifest, path)
        return path

    def _snapshot(self, root: Path) -> dict[str, bytes | None]:
        return {str(path.relative_to(root)): path.read_bytes() if path.is_file() else None
                for path in root.rglob("*")}

    def _refused(self, manifest: Path, output: Path, receipt: Path, root: Path,
                 error: str = "export destination overlaps protected bundle path:") -> None:
        before = self._snapshot(root)
        result = subprocess.run(
            [sys.executable, str(CLI), str(manifest), str(output), "--receipt", str(receipt)],
            capture_output=True, text=True, check=False,
            timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120")),
        )
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertEqual("", result.stdout)
        self.assertEqual(1, len(result.stderr.splitlines()), result.stderr)
        self.assertIn("error: " + error, result.stderr)
        self.assertEqual(before, self._snapshot(root))

    def _descriptor_bundle(self, root: Path, name: str = "descriptor.json", *, external: bool = False) -> Path:
        manifest_path = self._bundle(root)
        tree = manifest_path.parent / "tree"
        tree.mkdir()
        (tree / "frame.bin").write_bytes(b"recorded frame\n")
        descriptor = describe_directory(tree)
        descriptor_path = manifest_path.parent / name
        if external:
            target = root / "external-descriptor.json"
            descriptor_path.symlink_to(target)
        descriptor_path.write_text(json.dumps(descriptor.to_dict()))
        manifest = json.loads(manifest_path.read_text())
        add_artifact(manifest, "tree", kind="result", artifact_type="directory-tree",
                     sha256=descriptor.root_sha256, descriptor_path=name)
        write_manifest(manifest, manifest_path)
        return manifest_path

    def test_existing_export_destinations_are_refused_before_any_writes(self) -> None:
        for name in EXPORT_FILES:
            for content in (b"", b"0", b"{", None):
                with self.subTest(name=name, content=content), tempfile.TemporaryDirectory() as tempdir:
                    root = Path(tempdir)
                    manifest = self._bundle(root)
                    output = root / "export"
                    output.mkdir()
                    destination = output / name
                    if content is None:
                        destination.mkdir()
                    else:
                        destination.write_bytes(content)
                    self._refused(manifest, output, root / "receipts" / "extra.json", root,
                                  f"export destination already exists: {str(destination)!r}; "
                                  "choose a new versioned output directory or archive the old export explicitly")

    def test_existing_receipt_path_is_refused_before_any_writes(self) -> None:
        for content in (b"", b"0", b"{"):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as tempdir:
                root = Path(tempdir)
                manifest = self._bundle(root)
                receipt = root / "receipt.json"
                receipt.write_bytes(content)
                self._refused(manifest, root / "absent" / "export", receipt, root,
                              f"receipt destination already exists: {str(receipt)!r}; "
                              "choose a fresh --receipt path or archive the old receipt explicitly")

    def test_cli_receipt_collision_advice_recovers_with_fresh_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            manifest = self._bundle(root)
            output = root / "export"
            receipt = root / "receipt.json"
            receipt.write_bytes(b"old receipt\n")
            self._refused(manifest, output, receipt, root,
                          f"receipt destination already exists: {str(receipt)!r}; "
                          "choose a fresh --receipt path or archive the old receipt explicitly")
            self._refused(manifest, root / "export-v2", receipt, root,
                          "receipt destination already exists:")
            fresh = root / "receipt-v2.json"
            command = [sys.executable, str(CLI), str(manifest), str(output), "--receipt", str(fresh)]
            recovered = subprocess.run(command, capture_output=True, text=True,
                                       timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120")))
            self.assertEqual(0, recovered.returncode, recovered.stderr)
            self.assertEqual(b"old receipt\n", receipt.read_bytes())
            self.assertEqual((output / "export-receipt.json").read_bytes(), fresh.read_bytes())
            self._refused(manifest, output, fresh, root, "export destination already exists:")

    def test_non_directory_ancestors_are_refused_before_any_writes(self) -> None:
        for destination in ("output", "receipt"):
            for alias in (("file", "symlink") if destination == "output" else ("file", "symlink", "dangling")):
                for depth in (0, 1):
                    for content in (b"", b"0", b"{"):
                        with self.subTest(destination=destination, alias=alias, depth=depth, content=content), tempfile.TemporaryDirectory() as tempdir:
                            root = Path(tempdir)
                            manifest = self._bundle(root)
                            blocker = root / "blocker"
                            if alias == "file":
                                blocker.write_bytes(content)
                            else:
                                target = root / "target"
                                if alias == "symlink":
                                    target.write_bytes(content)
                                blocker.symlink_to(target)
                            parent = blocker / "missing" if depth else blocker
                            output = parent if destination == "output" else root / "absent" / "export"
                            receipt = parent / "receipt.json" if destination == "receipt" else root / "extra.json"
                            self._refused(manifest, output, receipt, root,
                                          "export destination has non-directory ancestor:")

    def test_existing_destination_symlinks_are_refused_before_any_writes(self) -> None:
        for name in (*EXPORT_FILES, "receipt.json"):
            for dangling in (False, True):
                with self.subTest(name=name, dangling=dangling), tempfile.TemporaryDirectory() as tempdir:
                    root = Path(tempdir)
                    manifest = self._bundle(root)
                    output = root / "export"
                    output.mkdir()
                    target = root / "older.json"
                    if not dangling:
                        target.write_bytes(b"older export\n")
                    receipt = root / "receipt.json"
                    destination = receipt if name == "receipt.json" else output / name
                    destination.symlink_to(target)
                    self._refused(manifest, output, receipt, root,
                                  (f"receipt destination already exists: {str(destination)!r}; "
                                   "choose a fresh --receipt path or archive the old receipt explicitly")
                                  if name == "receipt.json" else
                                  (f"export destination already exists: {str(destination)!r}; "
                                   "choose a new versioned output directory or archive the old export explicitly"))
                    self.assertTrue(destination.is_symlink())
                    self.assertEqual(target, destination.readlink())

    def test_repeated_export_refuses_first_existing_destination(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            manifest = self._bundle(root)
            output = root / "export"
            receipt = root / "receipt.json"
            export_run(manifest, output, receipt_path=receipt)
            first = output / EXPORT_FILES[0]
            self._refused(manifest, output, receipt, root,
                          f"export destination already exists: {str(first)!r}; "
                          "choose a new versioned output directory or archive the old export explicitly")

    def test_fresh_exports_preserve_unrelated_files_and_identical_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            manifest = self._bundle(root)
            baseline = root / "baseline"
            timestamp = "2026-07-21T00:00:00Z"
            expected = export_run(manifest, baseline, exported_at=timestamp)
            for state in ("missing", "empty", "unrelated"):
                with self.subTest(state=state):
                    output = root / state
                    if state != "missing":
                        output.mkdir()
                    unrelated = output / "notes.txt"
                    if state == "unrelated":
                        unrelated.write_bytes(b"retain these notes\n")
                    receipt = root / "receipts" / f"{state}.json"
                    actual = export_run(manifest, output, exported_at=timestamp, receipt_path=receipt)
                    self.assertEqual(expected, actual)
                    for name in EXPORT_FILES:
                        self.assertEqual((baseline / name).read_bytes(), (output / name).read_bytes())
                    self.assertEqual((baseline / "export-receipt.json").read_bytes(), receipt.read_bytes())
                    if state == "unrelated":
                        self.assertEqual(b"retain these notes\n", unrelated.read_bytes())

    def test_descriptor_destinations_are_refused_before_any_writes(self) -> None:
        for destination in ("receipt", "output"):
            for external in (False, True):
                with self.subTest(destination=destination, external=external), tempfile.TemporaryDirectory() as tempdir:
                    root = Path(tempdir)
                    name = "prov.json" if destination == "output" else "descriptor.json"
                    manifest = self._descriptor_bundle(root, name, external=external)
                    receipt = root / "receipt.json"
                    output = manifest.parent if destination == "output" else root / "absent" / "export"
                    if destination == "receipt":
                        receipt = (manifest.parent / name).resolve()
                    self._refused(manifest, output, receipt, root, *(["Artifact descriptor resolves outside the run bundle:"] if external else []))

    def test_hard_links_refuse_all_protected_bundle_files(self) -> None:
        for target in ("manifest.json", "result.csv", "descriptor.json", "tree/frame.bin"):
            for destination in ("receipt", *EXPORT_FILES):
                with self.subTest(target=target, destination=destination), tempfile.TemporaryDirectory() as tempdir:
                    root = Path(tempdir)
                    manifest = self._descriptor_bundle(root)
                    output = root / "export"
                    receipt = root / "receipt.json"
                    linked = receipt
                    if destination != "receipt":
                        output.mkdir()
                        linked = output / destination
                    os.link(manifest.parent / target, linked)
                    self._refused(manifest, output, receipt, root)

    def test_receipt_refuses_own_export_output_files(self) -> None:
        for name in EXPORT_FILES:
            for alias in ("direct", "symlink", "hardlink"):
                for content in (b"", b"0", b"{"):
                    with self.subTest(name=name, alias=alias, content=content), tempfile.TemporaryDirectory() as tempdir:
                        root = Path(tempdir)
                        manifest = self._bundle(root)
                        output = root / "export"
                        output.mkdir()
                        target = output / name
                        target.write_bytes(content)
                        receipt = target
                        if alias != "direct":
                            receipt = root / "receipt-alias.json"
                            if alias == "symlink":
                                receipt.symlink_to(target)
                            else:
                                os.link(target, receipt)
                        self._refused(manifest, output, receipt, root,
                                      "receipt destination overlaps export output:")
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            manifest = self._bundle(root)
            output = root / "absent" / "export"
            self._refused(manifest, output, output / "prov.json", root,
                          "receipt destination overlaps export output:")

    def test_receipt_refuses_export_ancestor_collisions_before_any_writes(self) -> None:
        cases = [
            ("export", "export"),
            ("export", "export/extra.json"),
            ("receipt.json/export", "receipt.json"),
            *(("export", f"export/{name}/receipt.json") for name in EXPORT_FILES),
        ]
        for output_name, receipt_name in cases:
            for alias in ("direct", "receipt", "output"):
                with self.subTest(output=output_name, receipt=receipt_name, alias=alias), tempfile.TemporaryDirectory() as tempdir:
                    root = Path(tempdir)
                    manifest = self._bundle(root)
                    parent = root / "paths"
                    alias_parent = parent
                    if alias != "direct":
                        parent.mkdir()
                        alias_parent = root / "alias"
                        alias_parent.symlink_to(parent, target_is_directory=True)
                    output = (alias_parent if alias == "output" else parent) / output_name
                    receipt = (alias_parent if alias == "receipt" else parent) / receipt_name
                    self._refused(manifest, output, receipt, root,
                                  f"receipt destination has ancestor/descendant overlap with export output: {str(receipt)!r}")

    def test_receipt_refuses_existing_directories_before_any_writes(self) -> None:
        for empty in (False, True):
            for alias in (False, True):
                with self.subTest(empty=empty, alias=alias), tempfile.TemporaryDirectory() as tempdir:
                    root = Path(tempdir)
                    manifest = self._bundle(root)
                    directory = root / "receipts"
                    directory.mkdir()
                    if not empty:
                        (directory / "record.json").write_bytes(b"0")
                    receipt = directory
                    if alias:
                        receipt = root / "receipt-alias"
                        receipt.symlink_to(directory, target_is_directory=True)
                    self._refused(manifest, root / "absent" / "export", receipt, root,
                                  "receipt destination is an existing directory:")

    def test_receipt_refuses_manifest_and_artifact_before_any_writes(self) -> None:
        for name in ("manifest.json", "result.csv"):
            for alias in (False, True):
                with self.subTest(name=name, alias=alias), tempfile.TemporaryDirectory() as tempdir:
                    root = Path(tempdir)
                    manifest = self._bundle(root)
                    receipt = manifest.parent / name
                    if alias:
                        receipt = root / "receipt-alias.json"
                        receipt.symlink_to(manifest.parent / name)
                    self._refused(manifest, root / "absent" / "export", receipt, root)

    def test_bundle_output_refuses_each_listed_export_artifact(self) -> None:
        for name in EXPORT_FILES:
            for alias in (False, True):
                with self.subTest(name=name, alias=alias), tempfile.TemporaryDirectory() as tempdir:
                    root = Path(tempdir)
                    manifest = self._bundle(root, name)
                    output = manifest.parent
                    if alias:
                        output = root / "output-alias"
                        output.symlink_to(manifest.parent, target_is_directory=True)
                    self._refused(manifest, output, root / "receipt.json", root)

    def test_export_file_symlinks_refuse_manifest_and_artifact(self) -> None:
        for name in EXPORT_FILES:
            for target in ("manifest.json", "result.csv"):
                with self.subTest(name=name, target=target), tempfile.TemporaryDirectory() as tempdir:
                    root = Path(tempdir)
                    manifest = self._bundle(root)
                    output = root / "export"
                    output.mkdir()
                    (output / name).symlink_to(manifest.parent / target)
                    self._refused(manifest, output, root / "receipt.json", root)

    def test_directory_artifact_refuses_export_and_receipt_inside_it(self) -> None:
        for empty in (False, True):
            for destination in ("output", "receipt", "directory-itself"):
                with self.subTest(empty=empty, destination=destination), tempfile.TemporaryDirectory() as tempdir:
                    root = Path(tempdir)
                    manifest_path = self._bundle(root)
                    tree = manifest_path.parent / "tree"
                    tree.mkdir()
                    if not empty:
                        (tree / "prov.json").write_bytes(b"recorded tree entry\n")
                    manifest = json.loads(manifest_path.read_text())
                    add_artifact(manifest, "tree", kind="result", artifact_type="directory-tree",
                                 sha256=describe_directory(tree).root_sha256)
                    write_manifest(manifest, manifest_path)
                    output = tree / "new-export" if destination == "output" else root / "export"
                    receipt = root / "receipt.json"
                    if destination == "receipt":
                        receipt = tree / "receipt.json"
                    elif destination == "directory-itself":
                        receipt = tree
                    self._refused(manifest_path, output, receipt, root)

    def test_empty_artifact_list_protects_manifest_and_allows_honest_export(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            manifest_path = self._bundle(root)
            manifest = json.loads(manifest_path.read_text())
            manifest["artifacts"] = []
            write_manifest(manifest, manifest_path)
            before = manifest_path.read_bytes()
            for malformed in (b"", b"0", b"{"):
                with self.subTest(malformed=malformed):
                    manifest_path.write_bytes(malformed)
                    snapshot = self._snapshot(root)
                    result = subprocess.run(
                        [sys.executable, str(CLI), str(manifest_path), str(root / "export"),
                         "--receipt", str(root / "receipt.json")],
                        capture_output=True, text=True, check=False,
                        timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120")),
                    )
                    self.assertEqual(1, result.returncode, result.stderr)
                    self.assertEqual("", result.stdout)
                    self.assertEqual(1, len(result.stderr.splitlines()), result.stderr)
                    self.assertTrue(result.stderr.startswith("error: "), result.stderr)
                    self.assertEqual(snapshot, self._snapshot(root))
            manifest_path.write_bytes(before)
            self._refused(manifest_path, root / "export", manifest_path, root)
            # Exporting beside the manifest is safe when no listed path collides.
            result = subprocess.run(
                [sys.executable, str(CLI), str(manifest_path), str(manifest_path.parent),
                 "--receipt", str(root / "receipts" / "extra.json")],
                capture_output=True, text=True, check=False,
                timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120")),
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("", result.stderr)
            self.assertEqual(before, manifest_path.read_bytes())
            self.assertEqual((manifest_path.parent / "export-receipt.json").read_bytes(),
                             (root / "receipts" / "extra.json").read_bytes())
            for name in EXPORT_FILES:
                self.assertTrue((manifest_path.parent / name).is_file())

    def test_validated_run_exports_ro_crate_prov_bom_and_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            run = root / "run"
            run.mkdir()
            result = run / "result.csv"
            result.write_text("metric,value\neffect,0.7\n", encoding="utf-8")
            digest = hashlib.sha256(result.read_bytes()).hexdigest()
            manifest = new_manifest(
                "run-fair",
                "Does the recorded effect satisfy the acceptance contract?",
                [{"id": "compute", "description": "Compute the effect", "status": "completed"}],
            )
            manifest["inputs"] = [{"id": "dataset", "identifier": "doi:10.1000/dataset", "source": "repository", "release": "1"}]
            manifest["code"] = [{"path": "analysis.py", "revision": "abc123"}]
            manifest["executions"] = [{"id": "exec-1", "command": "python analysis.py", "exit_code": 0}]
            manifest["environment"] = {"python": "3.12", "container_digest": "sha256:" + "a" * 64, "packages": [{"name": "numpy", "version": "2"}]}
            manifest["claims"] = [{"id": "C1", "text": "The recorded effect is 0.7.", "evidence": ["result.csv"]}]
            manifest["review"] = {"status": "passed", "findings": []}
            add_artifact(manifest, "result.csv", kind="result-table", sha256=digest)
            manifest_path = run / "manifest.json"
            write_manifest(manifest, manifest_path)

            output = root / "export"
            receipt = export_run(manifest_path, output, exported_at="2026-07-21T00:00:00Z")
            self.assertFalse(receipt["certified"])
            self.assertFalse(receipt["regulatory_compliance_claimed"])
            self.assertEqual(3, len(receipt["exports"]))
            for filename in ("ro-crate-metadata.json", "prov.json", "scientific-bom.json", "export-receipt.json"):
                self.assertTrue((output / filename).is_file())

            crate = json.loads((output / "ro-crate-metadata.json").read_text(encoding="utf-8"))
            self.assertEqual("https://w3id.org/ro/crate/1.1/context", crate["@context"])
            ids = {item["@id"] for item in crate["@graph"]}
            self.assertIn("../run/result.csv", ids)
            self.assertIn("#claim-C1", ids)

            prov = json.loads((output / "prov.json").read_text(encoding="utf-8"))
            self.assertIn("run:run-fair", prov["activity"])
            self.assertIn("artifact:result.csv", prov["entity"])

            bom = json.loads((output / "scientific-bom.json").read_text(encoding="utf-8"))
            component_types = {item["component_type"] for item in bom["components"]}
            self.assertIn("code", component_types)
            self.assertIn("dataset", component_types)
            self.assertIn("package", component_types)
            self.assertIn("container_digest", component_types)

    def test_write_time_collisions_preserve_sources_and_competing_files(self) -> None:
        for name in (*EXPORT_FILES, "extra.json"):
            for alias in ("symlink", "hardlink", "file"):
                with self.subTest(name=name, alias=alias), tempfile.TemporaryDirectory() as tempdir:
                    root = Path(tempdir)
                    manifest = self._bundle(root, "prov.json")
                    source = manifest.parent / "prov.json"
                    before = source.read_bytes()
                    output = manifest.parent / "exports"
                    extra = root / "extra.json"
                    destination = extra if name == "extra.json" else output / name

                    def competing_write(path: Path, payload: object) -> None:
                        if path == destination:
                            path.parent.mkdir(parents=True, exist_ok=True)
                            if alias == "symlink":
                                path.symlink_to(source)
                            elif alias == "hardlink":
                                os.link(source, path)
                            else:
                                path.write_bytes(b"competing export")
                        _write_json(path, payload)

                    with patch("codex_science.fair_export._write_json", side_effect=competing_write):
                        with self.assertRaises(FileExistsError):
                            export_run(manifest, output, receipt_path=extra)
                    self.assertEqual(before, source.read_bytes())
                    self.assertEqual(before if alias != "file" else b"competing export",
                                     destination.read_bytes())
                    if name != "extra.json":
                        self.assertFalse(extra.exists())

    def test_prov_records_run_inputs_without_inventing_execution_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            path = self._bundle(root)
            manifest = json.loads(path.read_text())
            manifest["inputs"] = [{"id": "dataset", "path": "sample.csv"}]
            executions = [
                {"id": "version", "command": "python --version", "exit_code": 0},
                {"id": "analysis", "command": "python analysis.py", "exit_code": 1},
            ]
            for records in ([], executions):
                with self.subTest(executions=records):
                    manifest["executions"] = records
                    write_manifest(manifest, path)
                    output = root / f"export-{len(records)}"
                    export_run(path, output)
                    prov = json.loads((output / "prov.json").read_text())
                    self.assertEqual([{"prov:activity": "run:run-fair", "prov:entity": "input:dataset"}],
                                     list(prov["used"].values()))

    def test_prov_omits_run_end_time(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            path = self._bundle(root)
            for index, timestamp in enumerate(("2026-07-21T00:00:00Z", "2026-07-22T00:00:00Z")):
                output = root / f"export-{index}"
                export_run(path, output, exported_at=timestamp)
                activity = json.loads((output / "prov.json").read_text())["activity"]["run:run-fair"]
                self.assertNotIn("prov:endedAtTime", activity)

    def test_prov_preserves_colliding_fallback_records_and_zero_ids(self) -> None:
        cases = [
            (
                [{"path": "sample.csv"}, {"identifier": "fixture:dataset"},
                 {"path": "preferred.csv", "identifier": "fixture:other"},
                 {"path": "", "identifier": "fixture:blank"},
                 {"path": 0, "identifier": "fixture:zero"}, {}],
                [{"command": "python --version", "exit_code": 0}],
                ["sample.csv", "fixture:dataset", "preferred.csv", "fixture:blank", "fixture:zero", "input-5"],
                ["0"],
            ),
            (
                [{"path": "sample.csv"}, {"id": "sample.csv"},
                 {"id": "@input-0"}, {"id": "@input-0:"}, {"id": 0}, {},
                 {"path": "repeat.csv"}, {"path": "repeat.csv"},
                 {"identifier": "fixture:repeat"}, {"identifier": "fixture:repeat"},
                 {"identifier": "fixture:reserved"}, {"id": "fixture:reserved"}],
                [{"id": "1", "command": "python --version", "exit_code": 0},
                 {"command": "python analysis.py", "exit_code": 1},
                 {"id": "@execution-1", "exit_code": 0}, {"id": 0, "exit_code": 0}],
                ["sample.csv", "@input-0", "@input-0:", "0", "repeat.csv", "fixture:repeat", "fixture:reserved"],
                ["1", "@execution-1", "0"],
            ),
        ]
        for input_records, execution_records, input_ids, execution_ids in cases:
            with self.subTest(inputs=input_records), tempfile.TemporaryDirectory() as tempdir:
                root = Path(tempdir)
                path = self._bundle(root)
                manifest = json.loads(path.read_text())
                manifest["inputs"] = input_records
                manifest["executions"] = execution_records
                write_manifest(manifest, path)
                outputs = []
                for name in ("first", "second"):
                    output = root / name
                    export_run(path, output, exported_at="2026-07-21T00:00:00Z")
                    outputs.append(json.loads((output / "prov.json").read_text()))
                self.assertEqual(outputs[0], outputs[1])
                prov = outputs[0]
                inputs = {key: item for key, item in prov["entity"].items() if key.startswith("input:")}
                self.assertEqual(len(input_records), len(inputs))
                self.assertCountEqual(input_records, [item["codex:record"] for item in inputs.values()])
                for identifier in input_ids:
                    self.assertIn("input:" + identifier, inputs)
                executions = {key: item for key, item in prov["activity"].items() if key.startswith("execution:")}
                self.assertEqual(len(execution_records), len(executions))
                self.assertEqual(sum(item["exit_code"] == 1 for item in execution_records),
                                 sum(item["codex:exitCode"] == 1 for item in executions.values()))
                for identifier in execution_ids:
                    self.assertIn("execution:" + identifier, executions)

    def test_duplicate_or_malformed_explicit_ids_refuse_before_writes(self) -> None:
        for field, kind in (("inputs", "input"), ("executions", "execution")):
            for records, reason in (
                ([{"id": "same"}, {"id": "same"}], "duplicate explicit"),
                ([{"id": 0}, {"id": "0"}], "duplicate explicit"),
                ([{"id": ""}], "invalid explicit"),
                ([{"id": "   "}], "invalid explicit"),
                ([{"id": None}], "invalid explicit"),
                ([{"id": []}], "invalid explicit"),
                ([{"id": {}}], "invalid explicit"),
                ([{"id": False}], "invalid explicit"),
            ):
                with self.subTest(field=field, records=records), tempfile.TemporaryDirectory() as tempdir:
                    root = Path(tempdir)
                    path = self._bundle(root)
                    manifest = json.loads(path.read_text())
                    manifest[field] = records
                    write_manifest(manifest, path)
                    self._refused(path, root / "export", root / "receipt.json", root,
                                  f"{reason} {kind} id")

    def test_ro_crate_references_resolve_from_written_metadata(self) -> None:
        for artifact_name in ("result#1.json", "result space%.json", "résultat?.json", "result:1.json"):
            for location in ("exports", "exports/nested", "elsewhere"):
                with self.subTest(artifact=artifact_name, location=location), tempfile.TemporaryDirectory() as tempdir:
                    root = Path(tempdir)
                    original = self._bundle(root, artifact_name)
                    path = original.with_name("record #1.json")
                    original.rename(path)
                    manifest = json.loads(path.read_text())
                    manifest["claims"] = [{"id": "C1", "text": "Recorded result", "evidence": [artifact_name]}]
                    write_manifest(manifest, path)
                    output = root / "elsewhere" if location == "elsewhere" else path.parent / location
                    export_run(path, output)
                    metadata = output / "ro-crate-metadata.json"
                    graph = json.loads(metadata.read_text())["@graph"]
                    dataset = next(item for item in graph if item["@id"] == "./")
                    artifact = next(item for item in graph if item.get("name") == artifact_name)
                    self.assertEqual([{"@id": artifact["@id"]}], dataset["hasPart"])
                    claim = next(item for item in graph if item["@id"] == "#claim-C1")
                    self.assertEqual([{"@id": artifact["@id"]}], claim["citation"])
                    for reference, target in ((artifact["@id"], path.parent / artifact_name),
                                              (dataset["mainEntity"]["@id"], path)):
                        parts = urlsplit(reference)
                        self.assertEqual(("", "", "", ""), (parts.scheme, parts.netloc, parts.query, parts.fragment))
                        self.assertFalse(Path(unquote(parts.path)).is_absolute())
                        resolved = Path(unquote(urlsplit(urljoin(metadata.as_uri(), reference)).path))
                        self.assertEqual(target, resolved)
                        self.assertTrue(resolved.is_file())
                        self.assertIn(reference, {item["@id"] for item in graph})

    def test_changed_artifact_bytes_prevent_export(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            result = root / "result.json"
            result.write_text('{"value": 1}\n', encoding="utf-8")
            manifest = new_manifest(
                "run-bad",
                "Q",
                [{"id": "x", "description": "X", "status": "completed"}],
            )
            manifest["claims"] = [{"id": "C", "text": "Claim", "evidence": ["result.json"]}]
            manifest["review"] = {"status": "passed", "findings": []}
            add_artifact(manifest, "result.json", kind="result", sha256=hashlib.sha256(result.read_bytes()).hexdigest())
            path = root / "manifest.json"
            write_manifest(manifest, path)
            result.write_text('{"value": 2}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                export_run(path, root / "export")
        for variant in ("code", "lane"):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as tempdir:
                root = Path(tempdir)
                path = self._bundle(root)
                manifest = json.loads(path.read_text())
                if variant == "code":
                    source = path.parent / "code/analysis.py"
                    source.parent.mkdir()
                    source.write_bytes(b"changed code\n")
                    manifest["code"] = [{"path": "code/analysis.py", "sha256": "0" * 64}]
                else:
                    example = CLI.parents[1] / "examples/literature-review-reviewed-run/lanes/pubmed-search.json"
                    lane = json.loads(example.read_text())
                    for field in ("claim_ids", "queries", "supported_claim_ids", "contradicted_claim_ids"):
                        lane[field] = []
                    lane["outputs"] = ["result.csv"]
                    lane["output_sha256"] = {"result.csv": "0" * 64}
                    source = path.parent / "lane.json"
                    source.write_text(json.dumps(lane))
                    add_artifact(manifest, "lane.json", kind="lane-receipt",
                                 sha256=hashlib.sha256(source.read_bytes()).hexdigest())
                write_manifest(manifest, path)
                before = self._snapshot(root)
                with self.assertRaisesRegex(ValueError, "Bundle digest mismatch"):
                    export_run(path, root / "export", receipt_path=root / "receipt.json")
                self.assertEqual(before, self._snapshot(root))
                self._refused(path, root / "export", root / "receipt.json", root,
                              error="Bundle digest mismatch:")
                if variant == "code":
                    manifest["code"][0].pop("sha256")
                else:
                    lane["output_sha256"] = {"result.csv": hashlib.sha256((path.parent / "result.csv").read_bytes()).hexdigest(),
                                             "unregistered.txt": "0" * 64}
                    source.write_text(json.dumps(lane))
                    manifest["artifacts"][-1]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
                write_manifest(manifest, path)
                self.assertEqual("generated", export_run(path, root / "export")["status"])


if __name__ == "__main__":
    unittest.main()
