import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codex_science.model_registry_v2 import (
    build_model_receipt_v2,
    registry_sha256,
    select_models,
    validate_model_receipt_v2,
    validate_registry_v2,
)


class ModelRegistryV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]
        self.registry = json.loads((self.root / "models" / "registry-v2.json").read_text(encoding="utf-8"))
        self.models = validate_registry_v2(self.registry)

    def test_registry_has_maturity_acceptance_and_confidence_contracts(self) -> None:
        self.assertIn("autodock-vina", self.models)
        for model in self.models.values():
            self.assertIn(model["status"], {"cataloged", "experimental", "smoke-tested", "contract-tested", "acceptance-tested", "degraded", "deprecated", "license-blocked"})
            self.assertTrue(model["contract_sha256"])
            self.assertTrue(model["leakage_risks"])
            self.assertTrue(model["confidence_semantics"]["not_equivalent_to"])

    def test_receipt_invalidates_on_registry_or_contract_change(self) -> None:
        model = self.models["autodock-vina"]
        receipt = build_model_receipt_v2(
            model,
            registry_sha256_value=registry_sha256(self.registry),
            code_revision="code-a",
            weight_revision="not-applicable",
            database_revisions={},
            configuration_sha256="a" * 64,
            input_sha256="b" * 64,
        )
        self.assertEqual([], validate_model_receipt_v2(receipt, self.registry))
        changed = copy.deepcopy(self.registry)
        next(item for item in changed["models"] if item["id"] == "autodock-vina")["tasks"].append("new-task")
        codes = {item["code"] for item in validate_model_receipt_v2(receipt, changed)}
        self.assertIn("stale-model-receipt-v2", codes)

    def _receipt(self, *, code_revision="code-a"):
        return build_model_receipt_v2(
            self.models["autodock-vina"], registry_sha256_value=registry_sha256(self.registry),
            code_revision=code_revision, weight_revision="weights-a", database_revisions={"db": "db-a", "old": "old-a"},
            configuration_sha256="a" * 64, input_sha256="b" * 64,
        )

    def test_current_revision_comparisons(self) -> None:
        receipt = self._receipt()
        current = {"code_revision": "code-a", "weight_revision": "weights-a", "database_revisions": {"db": "db-a"}}
        self.assertEqual([], validate_model_receipt_v2(receipt, self.registry, current_revisions=current))
        for field, value in (("code_revision", "code-b"), ("weight_revision", "weights-b")):
            changed = dict(current, **{field: value})
            findings = validate_model_receipt_v2(receipt, self.registry, current_revisions=changed)
            self.assertEqual([f"{field} changed: autodock-vina"], [item["message"] for item in findings])
        changed_db = dict(current, database_revisions={"db": "db-b"})
        self.assertEqual(1, len(validate_model_receipt_v2(receipt, self.registry, current_revisions=changed_db)))
        missing_db = dict(current, database_revisions={"missing": "db-x"})
        self.assertEqual(1, len(validate_model_receipt_v2(receipt, self.registry, current_revisions=missing_db)))

    def test_current_revision_input_validation_and_tampered_receipt(self) -> None:
        receipt = self._receipt()
        for invalid in ({"unknown": "x"}, {"code_revision": 1}, {"database_revisions": []}, {"database_revisions": {"db": 1}}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_model_receipt_v2(receipt, self.registry, current_revisions=invalid)
        tampered = dict(receipt, code_revision="tampered")
        findings = validate_model_receipt_v2(tampered, self.registry, current_revisions={"code_revision": "current"})
        self.assertEqual(["invalid-model-receipt-v2"], [item["code"] for item in findings])
        missing_fingerprint = {"schema_version": 2}
        findings = validate_model_receipt_v2(missing_fingerprint, self.registry)
        self.assertEqual(["invalid-model-receipt-v2"], [item["code"] for item in findings])
        self.assertEqual("critical", findings[0]["severity"])

    def test_receipt_cli_fresh_stale_and_malformed_revisions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt_path = root / "receipt.json"
            revisions_path = root / "revisions.json"
            receipt_path.write_text(json.dumps(self._receipt()), encoding="utf-8")
            command = [sys.executable, str(self.root / "scripts" / "validate_model_registry_v2.py"), "--receipt", str(receipt_path)]
            revisions_path.write_text(json.dumps({"code_revision": "code-a", "weight_revision": "weights-a", "database_revisions": {"db": "db-a"}}), encoding="utf-8")
            fresh = subprocess.run(command + ["--current-revisions", str(revisions_path)], capture_output=True, text=True)
            self.assertEqual(0, fresh.returncode, fresh.stderr)
            revisions_path.write_text(json.dumps({"code_revision": "code-b"}), encoding="utf-8")
            stale = subprocess.run(command + ["--current-revisions", str(revisions_path)], capture_output=True, text=True)
            self.assertEqual(1, stale.returncode, stale.stderr)
            self.assertIn('"code_revision changed: autodock-vina"', stale.stdout)
            revisions_path.write_text("{", encoding="utf-8")
            malformed = subprocess.run(command + ["--current-revisions", str(revisions_path)], capture_output=True, text=True)
            self.assertEqual(2, malformed.returncode)
            self.assertTrue(malformed.stderr)

    def test_receipt_cli_invalid_non_object_and_revisions_argument(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            invalid_path = root / "invalid.json"
            invalid_path.write_text(json.dumps({"schema_version": 2}), encoding="utf-8")
            command = [sys.executable, str(self.root / "scripts" / "validate_model_registry_v2.py")]
            invalid = subprocess.run(command + ["--receipt", str(invalid_path)], capture_output=True, text=True)
            self.assertEqual(1, invalid.returncode, invalid.stderr)
            finding = json.loads(invalid.stdout)
            self.assertEqual("invalid-model-receipt-v2", finding["code"])
            self.assertEqual("critical", finding["severity"])
            self.assertNotIn("Traceback", invalid.stderr)

            invalid_path.write_text("[]", encoding="utf-8")
            non_object = subprocess.run(command + ["--receipt", str(invalid_path)], capture_output=True, text=True)
            self.assertEqual(2, non_object.returncode)
            self.assertTrue(non_object.stderr)

            revisions_path = root / "revisions.json"
            revisions_path.write_text("{}", encoding="utf-8")
            revisions_without_receipt = subprocess.run(command + ["--current-revisions", str(revisions_path)], capture_output=True, text=True)
            self.assertEqual(2, revisions_without_receipt.returncode)
            self.assertIn("--current-revisions requires", revisions_without_receipt.stderr)

    def test_receipt_cli_finding_identifies_each_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first_path = root / "first.json"
            second_path = root / "second.json"
            first_path.write_text(json.dumps(self._receipt(code_revision="old-a")), encoding="utf-8")
            second_path.write_text(json.dumps(self._receipt(code_revision="old-b")), encoding="utf-8")
            revisions_path = root / "revisions.json"
            revisions_path.write_text(json.dumps({"code_revision": "code-a"}), encoding="utf-8")
            command = [sys.executable, str(self.root / "scripts" / "validate_model_registry_v2.py")]
            result = subprocess.run(
                command + ["--receipt", str(first_path), "--receipt", str(second_path), "--current-revisions", str(revisions_path)],
                capture_output=True, text=True,
            )
            self.assertEqual(1, result.returncode, result.stderr)
            findings = [json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual([str(first_path), str(second_path)], [item["receipt"] for item in findings])
            self.assertEqual(2, len(findings))

    def test_selection_prefers_stronger_nonexperimental_contracts(self) -> None:
        selected = select_models(self.registry, task="redocking", modality="protein-ligand", available_vram_gb=8)
        self.assertEqual("autodock-vina", selected[0]["id"])
        self.assertNotIn("diffdock", {item["id"] for item in selected})
        experimental = select_models(self.registry, task="pose-generation", modality="protein-ligand", available_vram_gb=16, allow_experimental=True)
        self.assertIn("diffdock", {item["id"] for item in experimental})


if __name__ == "__main__":
    unittest.main()
