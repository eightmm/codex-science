import copy
import json
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

    def test_selection_prefers_stronger_nonexperimental_contracts(self) -> None:
        selected = select_models(self.registry, task="redocking", modality="protein-ligand", available_vram_gb=8)
        self.assertEqual("autodock-vina", selected[0]["id"])
        self.assertNotIn("diffdock", {item["id"] for item in selected})
        experimental = select_models(self.registry, task="pose-generation", modality="protein-ligand", available_vram_gb=16, allow_experimental=True)
        self.assertIn("diffdock", {item["id"] for item in experimental})


if __name__ == "__main__":
    unittest.main()
