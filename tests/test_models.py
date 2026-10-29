import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import codex_science.models as model_module
from codex_science.models import (
    build_model_receipt,
    changed_model_contracts,
    load_registry,
    registry_sha256,
    review_model_receipt,
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

    def test_receipt_builder_requires_string_revision_pins(self) -> None:
        arguments = dict(
            code_revision=" c ", weight_revision="not-applicable", database_revisions={},
            configuration_sha256="a" * 64, input_sha256="b" * 64,
        )
        model = self.models["autodock-vina"]
        receipt = build_model_receipt(model, **arguments)
        self.assertEqual("c", receipt["code_revision"])
        self.assertEqual({}, receipt["database_revisions"])
        validate_model_receipt(receipt, model)
        for field in ("code_revision", "weight_revision", "database_revisions"):
            omitted = dict(arguments)
            omitted.pop(field)
            with self.subTest(omitted=field), self.assertRaises(TypeError):
                build_model_receipt(model, **omitted)
        for value in (None, "", " ", 0, 1, False, [], {}):
            for field in ("code_revision", "weight_revision", "database_revisions"):
                override = {"db": value} if field == "database_revisions" else value
                changed = dict(arguments, **{field: override})
                before = copy.deepcopy(changed)
                with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, "revision"):
                    build_model_receipt(model, **changed)
                self.assertEqual(before, changed)
        for value in (None, [], "db"):
            with self.subTest(mapping=value), self.assertRaisesRegex(ValueError, "database_revisions"):
                build_model_receipt(model, **dict(arguments, database_revisions=value))
        pinned = build_model_receipt(model, **dict(arguments, database_revisions={"db": "v"}))
        self.assertEqual({"db": "v"}, pinned["database_revisions"])
        validate_model_receipt(pinned, model)

    def test_receipt_review_refuses_missing_and_invalid_revision_pins(self) -> None:
        valid = build_model_receipt(
            self.models["autodock-vina"], code_revision="c", weight_revision="w",
            database_revisions={}, configuration_sha256="a" * 64, input_sha256="b" * 64,
        )
        missing = object()
        for field in ("code_revision", "weight_revision", "database_revisions"):
            values = (missing, None, "", " ", 0, 1, False, [], {})
            if field == "database_revisions":
                values = (missing, None, [], "db") + tuple({"db": value} for value in values[1:])
            for value in values:
                receipt = copy.deepcopy(valid)
                if value is missing:
                    receipt.pop(field)
                else:
                    receipt[field] = value
                material = {key: item for key, item in receipt.items() if key not in ("schema_version", "fingerprint")}
                receipt["fingerprint"] = model_module._canonical_sha256(material)
                before = copy.deepcopy(receipt)
                with self.subTest(field=field, value=value):
                    findings = review_model_receipt(receipt)
                    self.assertEqual(["invalid-model-receipt"], [item["code"] for item in findings])
                    self.assertIn("revision", findings[0]["message"])
                    self.assertEqual(before, receipt)

    def test_registry_validation_refuses_invalid_shapes_and_values_without_mutation(self) -> None:
        valid_model = copy.deepcopy(self.registry["models"][0])

        def registry_with(change) -> dict:
            registry = copy.deepcopy(self.registry)
            change(registry)
            return registry

        invalid_cases = [
            (None, "Model registry must be an object"),
            (registry_with(lambda value: value.update(schema_version=2)), "schema version"),
            (registry_with(lambda value: value.update(registry_revision=" ")), "registry revision"),
            (registry_with(lambda value: value.update(models={})), "models must be a list"),
            (registry_with(lambda value: value.update(models=[None])), "record 0 must be an object"),
            (registry_with(lambda value: value["models"][0].update(id=" ")), "record 0 id"),
            (
                registry_with(lambda value: value["models"].append(copy.deepcopy(value["models"][0]))),
                "Duplicate model id",
            ),
            (registry_with(lambda value: value["models"][0].update(skill=" ")), "skill"),
            (registry_with(lambda value: value["models"][0].update(family="unknown")), "Invalid model family"),
            (registry_with(lambda value: value["models"][0].update(contract_revision=True)), "positive integer"),
            (registry_with(lambda value: value["models"][0].update(contract_revision=0)), "positive integer"),
            (registry_with(lambda value: value["models"][0].update(implementation=[])), "implementation must be an object"),
            (
                registry_with(lambda value: value["models"][0]["implementation"].update(repository=" ")),
                "repository",
            ),
            (
                registry_with(lambda value: value["models"][0]["implementation"].update(revision_policy="unknown")),
                "Invalid revision policy",
            ),
            (registry_with(lambda value: value["models"][0].update(weights=[])), "weights must be an object"),
            (
                registry_with(lambda value: value["models"][0]["weights"].update(revision_policy="unknown")),
                "Invalid weights policy",
            ),
            (registry_with(lambda value: value["models"][0].update(license=[])), "license must be an object"),
            (registry_with(lambda value: value["models"][0]["license"].update(code=" ")), "code license"),
            (registry_with(lambda value: value["models"][0]["license"].update(weights=" ")), "weights license"),
            (registry_with(lambda value: value["models"][0].update(modalities={})), "modalities must be a list"),
            (
                registry_with(lambda value: value["models"][0].update(required_databases={})),
                "required_databases must be a list",
            ),
            (registry_with(lambda value: value["models"][0].update(hardware=[])), "hardware must be an object"),
            (
                registry_with(lambda value: value["models"][0].update(confidence_semantics=[])),
                "confidence_semantics must be an object",
            ),
            (
                registry_with(lambda value: value["models"][0]["confidence_semantics"].update(outputs={})),
                "confidence outputs must be a list",
            ),
            (
                registry_with(
                    lambda value: value["models"][0]["confidence_semantics"].update(not_equivalent_to={})
                ),
                "confidence not_equivalent_to must be a list",
            ),
            (registry_with(lambda value: value["models"][0].update(leakage_risks={})), "leakage_risks must be a list"),
            (
                registry_with(lambda value: value["models"][0].update(validated_tasks={})),
                "validated_tasks must be a list",
            ),
            (
                registry_with(lambda value: value["models"][0].update(acceptance_contract=" ")),
                "acceptance_contract",
            ),
        ]
        for invalid, message in invalid_cases:
            with self.subTest(message=message):
                before = copy.deepcopy(invalid)
                with self.assertRaisesRegex(ValueError, message):
                    validate_registry(invalid)
                self.assertEqual(before, invalid)

        self.assertEqual({}, validate_registry({"schema_version": 1, "registry_revision": "r1", "models": []}))
        self.assertEqual(valid_model, self.registry["models"][0])
        minimum_revision = copy.deepcopy(self.registry)
        minimum_revision["models"][0]["contract_revision"] = 1
        self.assertEqual(1, validate_registry(minimum_revision)[valid_model["id"]]["contract_revision"])

    def test_registry_load_and_digest_are_canonical_and_validate_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            path.write_text(json.dumps(self.registry), encoding="utf-8")
            self.assertEqual(self.registry, load_registry(path))

        reordered = {"models": self.registry["models"], "registry_revision": self.registry["registry_revision"], "schema_version": 1}
        self.assertEqual(registry_sha256(self.registry), registry_sha256(reordered))
        invalid = copy.deepcopy(self.registry)
        invalid["schema_version"] = 99
        before = copy.deepcopy(invalid)
        with self.assertRaisesRegex(ValueError, "schema version"):
            registry_sha256(invalid)
        self.assertEqual(before, invalid)

    def test_receipt_builder_returns_normalized_fingerprint_and_rejects_invalid_inputs(self) -> None:
        model = self.models["autodock-vina"]
        receipt = build_model_receipt(
            model,
            code_revision=" code-a ",
            weight_revision=" weights-a ",
            database_revisions={"z-db": "z1", "a-db": "a1"},
            configuration_sha256="A" * 64,
            input_sha256="B" * 64,
        )
        self.assertEqual("code-a", receipt["code_revision"])
        self.assertEqual("weights-a", receipt["weight_revision"])
        self.assertEqual(["a-db", "z-db"], list(receipt["database_revisions"]))
        self.assertEqual("a" * 64, receipt["configuration_sha256"])
        self.assertEqual("b" * 64, receipt["input_sha256"])
        self.assertEqual(64, len(receipt["fingerprint"]))
        validate_model_receipt(receipt, model)

        bad_inputs = [
            ({"code_revision": " "}, "code_revision"),
            ({"weight_revision": " "}, "weight_revision"),
            ({"configuration_sha256": "f" * 63}, "configuration_sha256"),
            ({"configuration_sha256": "g" * 64}, "configuration_sha256"),
            ({"input_sha256": "f" * 63}, "input_sha256"),
            ({"database_revisions": {" ": "db1"}}, "database revision name"),
            ({"database_revisions": {"db": " "}}, "database revision db"),
        ]
        for overrides, message in bad_inputs:
            with self.subTest(message=message):
                arguments = {
                    "code_revision": "code-a",
                    "weight_revision": "weights-a",
                    "database_revisions": {"db": "db1"},
                    "configuration_sha256": "c" * 64,
                    "input_sha256": "d" * 64,
                }
                arguments.update(overrides)
                before = copy.deepcopy(arguments)
                with self.assertRaisesRegex(ValueError, message):
                    build_model_receipt(model, **arguments)
                self.assertEqual(before, arguments)

    def test_receipt_validation_refuses_invalid_contracts_without_mutation(self) -> None:
        model = self.models["autodock-vina"]
        valid = build_model_receipt(
            model,
            code_revision="code-a",
            weight_revision="weights-a",
            database_revisions={"db": "v1"},
            configuration_sha256="c" * 64,
            input_sha256="d" * 64,
        )
        invalid_cases = [(None, "Model receipt must be an object")]
        for field, value, message in [
            ("schema_version", 2, "schema version"),
            ("model_id", " ", "model_id"),
            ("registry_contract_revision", True, "positive integer"),
            ("registry_contract_revision", 0, "positive integer"),
            ("code_revision", " ", "code_revision"),
            ("weight_revision", " ", "weight_revision"),
            ("database_revisions", [], "database_revisions must be an object"),
            ("configuration_sha256", "x", "configuration_sha256"),
            ("input_sha256", "x", "input_sha256"),
            ("fingerprint", "x", "fingerprint"),
        ]:
            changed = copy.deepcopy(valid)
            changed[field] = value
            invalid_cases.append((changed, message))
        for field, value, message in [
            ("database_revisions", {" ": "v1"}, "database revision name"),
            ("database_revisions", {"db": " "}, "database revision db"),
        ]:
            changed = copy.deepcopy(valid)
            changed[field] = value
            invalid_cases.append((changed, message))
        changed = copy.deepcopy(valid)
        changed["input_sha256"] = "e" * 64
        invalid_cases.append((changed, "fingerprint mismatch"))
        for invalid, message in invalid_cases:
            with self.subTest(message=message):
                before = copy.deepcopy(invalid)
                with self.assertRaisesRegex(ValueError, message):
                    validate_model_receipt(invalid)
                self.assertEqual(before, invalid)

        wrong_model = build_model_receipt(
            self.models["diffdock"],
            code_revision="code-a",
            weight_revision="weights-a",
            database_revisions={"db": "v1"},
            configuration_sha256="c" * 64,
            input_sha256="d" * 64,
        )
        with self.assertRaisesRegex(ValueError, "wrong registry model"):
            validate_model_receipt(wrong_model, model)
        stale_model = copy.deepcopy(model)
        stale_model["contract_revision"] += 1
        with self.assertRaisesRegex(ValueError, "stale"):
            validate_model_receipt(valid, stale_model)

    def test_receipt_review_reports_invalid_unavailable_unknown_stale_and_current(self) -> None:
        model = self.models["autodock-vina"]
        receipt = build_model_receipt(
            model,
            code_revision="code-a",
            weight_revision="weights-a",
            database_revisions={},
            configuration_sha256="c" * 64,
            input_sha256="d" * 64,
        )
        invalid = copy.deepcopy(receipt)
        invalid["fingerprint"] = "0" * 64
        before_invalid = copy.deepcopy(invalid)
        finding = review_model_receipt(invalid)
        self.assertEqual("invalid-model-receipt", finding[0]["code"])
        self.assertIn("fingerprint mismatch", finding[0]["message"])
        self.assertEqual(before_invalid, invalid)

        with tempfile.TemporaryDirectory() as directory:
            missing_path = Path(directory) / "missing-registry.json"
            with patch.object(model_module, "default_registry_path", return_value=missing_path):
                finding = review_model_receipt(receipt)
        self.assertEqual("model-registry-unavailable", finding[0]["code"])
        self.assertIn("unavailable", finding[0]["message"])

        unknown_model = copy.deepcopy(model)
        unknown_model["id"] = "missing-model"
        unknown = build_model_receipt(
            unknown_model,
            code_revision="code-a",
            weight_revision="weights-a",
            database_revisions={},
            configuration_sha256="c" * 64,
            input_sha256="d" * 64,
        )
        self.assertEqual("unknown-model", review_model_receipt(unknown)[0]["code"])

        stale_model = copy.deepcopy(model)
        stale_model["contract_revision"] += 1
        stale = build_model_receipt(
            stale_model,
            code_revision="code-a",
            weight_revision="weights-a",
            database_revisions={},
            configuration_sha256="c" * 64,
            input_sha256="d" * 64,
        )
        finding = review_model_receipt(stale)
        self.assertEqual("stale-model-receipt", finding[0]["code"])
        self.assertIn("does not match registry revision", finding[0]["message"])
        self.assertEqual([], review_model_receipt(receipt))

    def test_changed_contracts_reports_added_removed_and_modified_ids_in_order(self) -> None:
        previous = copy.deepcopy(self.registry)
        current = copy.deepcopy(self.registry)
        current_models = {item["id"]: item for item in current["models"]}
        current_models["diffdock"]["contract_revision"] += 1
        current["models"] = [item for item in current["models"] if item["id"] != "alphafold3"]
        added = copy.deepcopy(current_models["autodock-vina"])
        added["id"] = "added-model"
        current["models"].append(added)
        before_previous = copy.deepcopy(previous)
        before_current = copy.deepcopy(current)
        self.assertEqual(["added-model", "alphafold3", "diffdock"], changed_model_contracts(previous, current))
        self.assertEqual(before_previous, previous)
        self.assertEqual(before_current, current)
        self.assertEqual([], changed_model_contracts(previous, copy.deepcopy(previous)))


    def test_cli_refuses_malformed_registry_and_inventory(self) -> None:
        from loader_cases import assert_refused, malformed_json, nested_values
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            for option in ("--registry", "--inventory"):
                payloads = malformed_json()
                if option == "--inventory":
                    payloads += [json.dumps({"schema_version": 2, "skills": [value]}).encode() for value in nested_values()]
                for contents in payloads:
                    path.write_bytes(contents)
                    with self.subTest(option=option, contents=contents):
                        assert_refused(self, "validate_models.py", [option, path], 1)
                path.unlink()
                for candidate in (path, Path(directory)):
                    assert_refused(self, "validate_models.py", [option, candidate], 1)

    def test_registry_required_text_and_schema_are_typed(self) -> None:
        for value in (None, True, [], {}, float("nan"), float("inf"), "", " ", "\ud800"):
            for field in ("registry_revision", "id", "skill"):
                payload = copy.deepcopy(self.registry)
                target = payload if field == "registry_revision" else payload["models"][0]
                target[field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    validate_registry(payload)
        for value in (True, 1.0, 0):
            payload = dict(self.registry, schema_version=value)
            with self.subTest(schema=value), self.assertRaises(ValueError):
                validate_registry(payload)

    def test_registry_legacy_numeric_text_preserves_records_and_cli_output(self) -> None:
        from codex_science.models import _text
        import os
        import subprocess
        import sys
        fields = (("registry_revision",), ("models", 0, "id"), ("models", 0, "skill"),
                  ("models", 0, "implementation", "repository"),
                  ("models", 0, "license", "code"), ("models", 0, "license", "weights"),
                  ("models", 0, "acceptance_contract"))
        for value in (0, 123, -1, 1.5, 10**400):
            self.assertEqual(str(value), _text(value, "value"))
            for path in fields:
                payload = copy.deepcopy(self.registry)
                target = payload
                for part in path[:-1]:
                    target = target[part]
                target[path[-1]] = value
                with self.subTest(path=path, value=value):
                    before = copy.deepcopy(payload)
                    records = validate_registry(payload)
                    self.assertEqual(len(self.models), len(records))
                    self.assertEqual(before, payload)
        payload = dict(self.registry, registry_revision=20261029)
        self.assertEqual(8, len(validate_registry(payload)))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry_path = root / "registry.json"
            registry_path.write_text(json.dumps(payload), encoding="utf-8")
            command = [sys.executable, str(self.repository_root / "scripts/validate_models.py"), "--registry", str(registry_path)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "30")))
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(f"model registry: valid (8 models, sha256={registry_sha256(payload)})\n", result.stdout)
            model = copy.deepcopy(payload["models"][0])
            model["skill"] = 123
            payload["models"] = [model]
            registry_path.write_text(json.dumps(payload), encoding="utf-8")
            inventory_path = root / "inventory.json"
            inventory_path.write_text(json.dumps({"schema_version": 2, "skills": [{"name": 123, "status": "active"}]}), encoding="utf-8")
            result = subprocess.run(command + ["--inventory", str(inventory_path)], capture_output=True, text=True, timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "30")))
            self.assertEqual(0, result.returncode, result.stderr)


if __name__ == "__main__":
    unittest.main()
