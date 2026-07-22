import json
import tempfile
import unittest
from pathlib import Path

from codex_science.artifacts import validate_bundle
from codex_science.review import review_manifest

ROOT = Path(__file__).resolve().parents[1]


class QuantitativeAcceptanceTests(unittest.TestCase):
    def test_quantitative_acceptance_is_hash_valid_and_reviewed(self) -> None:
        from importlib.util import module_from_spec, spec_from_file_location

        script = ROOT / "scripts" / "run_quantitative_acceptance.py"
        spec = spec_from_file_location("run_quantitative_acceptance", script)
        assert spec is not None and spec.loader is not None
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tempdir:
            output = Path(tempdir) / "run"
            manifest_path = module.run(ROOT / "examples" / "quantitative-research" / "input.json", output)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            sidecars = validate_bundle(manifest, output)
            review = review_manifest(manifest, output, sidecars=sidecars)
            self.assertEqual("passed", review["status"], json.dumps(review, indent=2))
            self.assertEqual(1, len(sidecars["research_designs"]))
            self.assertEqual(1, len(sidecars["statistical_analyses"]))
            self.assertEqual(1, len(sidecars["numerical_verifications"]))
            self.assertEqual(1, len(sidecars["dimension_checks"]))
            self.assertEqual(1, len(sidecars["uncertainty_propagations"]))
            self.assertEqual(6, len(sidecars["mathematical_claims"]))
            self.assertEqual(2, len(sidecars["counterexample_receipts"]))
            self.assertEqual([], sidecars["advanced_findings"])
            report = (output / "report.md").read_text(encoding="utf-8")
            self.assertIn("No p-value, convergence plot, or bounded search is promoted", report)

    def test_changed_quantitative_artifact_invalidates_bundle(self) -> None:
        from importlib.util import module_from_spec, spec_from_file_location

        script = ROOT / "scripts" / "run_quantitative_acceptance.py"
        spec = spec_from_file_location("run_quantitative_acceptance_tamper", script)
        assert spec is not None and spec.loader is not None
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tempdir:
            output = Path(tempdir) / "run"
            manifest_path = module.run(ROOT / "examples" / "quantitative-research" / "input.json", output)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            path = output / "statistical-analysis.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["effect"]["estimate"] = 999
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                validate_bundle(manifest, output)


if __name__ == "__main__":
    unittest.main()
