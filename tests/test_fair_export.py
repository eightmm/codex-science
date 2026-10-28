import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codex_science.artifact_store import describe_directory
from codex_science.artifacts import add_artifact, new_manifest, write_manifest
from codex_science.fair_export import export_run


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
                              f"export destination already exists: {str(receipt)!r}; "
                              "choose a new versioned output directory or archive the old export explicitly")

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
                                  f"export destination already exists: {str(destination)!r}; "
                                  "choose a new versioned output directory or archive the old export explicitly")
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
                    self._refused(manifest, output, receipt, root)

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
            self.assertIn("result.csv", ids)
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


if __name__ == "__main__":
    unittest.main()
