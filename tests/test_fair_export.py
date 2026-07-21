import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from codex_science.artifacts import add_artifact, new_manifest, write_manifest
from codex_science.fair_export import export_run


class FairExportTests(unittest.TestCase):
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
