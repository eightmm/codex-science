import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codex_science.artifacts import validate_bundle
from codex_science.review import review_manifest

ROOT = Path(__file__).resolve().parents[1]


class QuantitativeAcceptanceTests(unittest.TestCase):
    def test_cli_invalid_inputs_leave_no_partial_output(self) -> None:
        fixture = json.loads((ROOT / "examples" / "quantitative-research" / "input.json").read_text())
        required = ("research_design", "statistical_analysis", "numerical_verification", "dimension_check",
                    "uncertainty_propagation", "false_statement_search", "finite_statement_search")
        cases = [(key, {name: value for name, value in fixture.items() if name != key}) for key in required]
        cases.extend([("empty", {}), ("zero", {**fixture, "schema_version": 0}),
                      ("malformed", "{"), ("invalid-dimension", {**fixture, "dimension_check": {}})])
        cases.extend(("schema-type", {**fixture, "schema_version": value})
                     for value in (None, "", True, False, 1.0, "1", [], {}))
        cases.extend(("run-id-type", {**fixture, "run_id": value})
                     for value in (None, "", " ", 0, True, [], {}))
        for label, payload in cases:
            for existing in (False, True):
                with self.subTest(label=label, existing=existing), tempfile.TemporaryDirectory() as tempdir:
                    root = Path(tempdir)
                    source = root / "input.json"
                    source.write_text(payload if isinstance(payload, str) else json.dumps(payload))
                    original = source.read_bytes()
                    output = root / "run"
                    if existing:
                        output.mkdir()
                    entries = set(root.rglob("*"))
                    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_quantitative_acceptance.py"), str(source), str(output)],
                                            capture_output=True, text=True,
                                            timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120")))
                    self.assertEqual(1, result.returncode, result.stderr)
                    self.assertTrue(result.stderr.startswith("error:"), result.stderr)
                    if label in required:
                        self.assertIn(f"missing required input key: {label}", result.stderr)
                    self.assertEqual("", result.stdout)
                    self.assertEqual(entries, set(root.rglob("*")))
                    self.assertEqual(original, source.read_bytes())

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

    def test_report_marks_unavailable_numerical_order(self) -> None:
        from importlib.util import module_from_spec, spec_from_file_location

        script = ROOT / "scripts" / "run_quantitative_acceptance.py"
        spec = spec_from_file_location("run_quantitative_acceptance_no_order", script)
        assert spec is not None and spec.loader is not None
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        fixture = json.loads((ROOT / "examples" / "quantitative-research" / "input.json").read_text(encoding="utf-8"))
        numerical = fixture["numerical_verification"]
        numerical["reference_value"] = None
        numerical["refinements"] = numerical["refinements"][:2]
        numerical["thresholds"].pop("minimum_order")
        with tempfile.TemporaryDirectory() as tempdir:
            source = Path(tempdir) / "input.json"
            source.write_text(json.dumps(fixture), encoding="utf-8")
            module.run(source, Path(tempdir) / "run")
            report = (Path(tempdir) / "run" / "report.md").read_text(encoding="utf-8")
            self.assertIn("- Minimum observed numerical order: not available\n", report)

    def test_formal_check_record_must_be_a_writer_shaped_passed_record(self) -> None:
        from codex_science.math_contracts import build_proof_receipt
        from codex_science.quantitative_sidecars import empty_quantitative_sidecars, validate_quantitative_sidecar

        receipt = build_proof_receipt(
            receipt_id="P", claim_id="C", statement="fake statement", kind="formal-kernel",
            status="passed", assumptions=[], checker={"kernel_checked": True, "tool": "lean", "tool_version": "4"},
        )
        record = {"schema_version": 1, "check_id": "chk", "preview_fingerprint": "a" * 64,
                  "status": "passed", "proof_receipt": receipt}
        validate_quantitative_sidecar("formal-proof-check", record, empty_quantitative_sidecars())
        failed = build_proof_receipt(
            receipt_id="P", claim_id="C", statement="fake statement", kind="formal-kernel",
            status="failed", assumptions=[], checker={"kernel_checked": True, "tool": "lean", "tool_version": "4"},
        )
        validate_quantitative_sidecar("formal-proof-check", {**record, "status": "failed", "proof_receipt": failed},
                                      empty_quantitative_sidecars())
        refused = [
            {"proof_receipt": receipt},
            {**record, "status": "failed", "tool_available": False},
            {**record, "status": "unavailable", "tool_available": False},
            {**record, "status": "preview"},
            {**record, "status": None},
            {**record, "status": []},
            {**record, "status": {}},
            {**record, "schema_version": "zzz"},
            {**record, "schema_version": True},
            {**record, "check_id": None},
            {**record, "check_id": "  "},
            {**record, "preview_fingerprint": "bad"},
            {**record, "preview_fingerprint": None},
        ]
        for index, bad in enumerate(refused):
            with self.subTest(index=index), self.assertRaises(ValueError):
                validate_quantitative_sidecar("formal-proof-check", bad, empty_quantitative_sidecars())

    def test_duplicate_ids_compare_stripped_like_cross_links(self) -> None:
        from codex_science.quantitative_sidecars import review_quantitative_sidecars

        sidecars = {"research_designs": [
            {"design_id": "d1", "note": "first"}, {"design_id": "d1 ", "note": "second"},
        ]}
        codes = [item["code"] for item in review_quantitative_sidecars(sidecars)]
        self.assertIn("quantitative-duplicate-id", codes)

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
