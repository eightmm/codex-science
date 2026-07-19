import copy
import json
import unittest
from pathlib import Path

from codex_science.models import (
    build_model_receipt,
    changed_model_contracts,
    load_registry,
    validate_model_receipt,
    validate_registry,
)


class ModelRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository_root = Path(__file__).resolve().parents[1]
        self.registry_path = self.repository_root / "models" / "registry.json"
        self.registry = load_registry(self.registry_path)
        self.models = validate_registry(self.registry)

    def test_registry_contains_docking_and_structure_acceptance_contracts(self) -> None:
        self.assertIn("autodock-vina", self.models)
        self.assertIn("diffdock", self.models)
        self.assertIn("alphafold3", self.models)
        for model in self.models.values():
            self.assertTrue(model["acceptance_contract"].endswith("SKILL.md"))
            self.assertTrue(model["leakage_risks"])
            self.assertTrue(model["confidence_semantics"]["not_equivalent_to"])

    def test_model_receipt_fingerprint_changes_with_scientific_dependencies(self) -> None:
        model = self.models["autodock-vina"]
        base = build_model_receipt(
            model,
            code_revision="code-a",
            weight_revision="not-applicable",
            database_revisions={"receptor-set": "db-a"},
            configuration_sha256="a" * 64,
            input_sha256="b" * 64,
        )
        validate_model_receipt(base, model)

        code_changed = build_model_receipt(
            model,
            code_revision="code-b",
            weight_revision="not-applicable",
            database_revisions={"receptor-set": "db-a"},
            configuration_sha256="a" * 64,
            input_sha256="b" * 64,
        )
        database_changed = build_model_receipt(
            model,
            code_revision="code-a",
            weight_revision="not-applicable",
            database_revisions={"receptor-set": "db-b"},
            configuration_sha256="a" * 64,
            input_sha256="b" * 64,
        )
        self.assertNotEqual(base["fingerprint"], code_changed["fingerprint"])
        self.assertNotEqual(base["fingerprint"], database_changed["fingerprint"])

    def test_registry_contract_change_invalidates_receipt(self) -> None:
        model = self.models["diffdock"]
        receipt = build_model_receipt(
            model,
            code_revision="code-a",
            weight_revision="weights-a",
            database_revisions={},
            configuration_sha256="c" * 64,
            input_sha256="d" * 64,
        )
        changed_model = copy.deepcopy(model)
        changed_model["contract_revision"] += 1
        with self.assertRaisesRegex(ValueError, "stale"):
            validate_model_receipt(receipt, changed_model)

        changed_registry = copy.deepcopy(self.registry)
        next(item for item in changed_registry["models"] if item["id"] == "diffdock")[
            "contract_revision"
        ] += 1
        self.assertIn("diffdock", changed_model_contracts(self.registry, changed_registry))


if __name__ == "__main__":
    unittest.main()
