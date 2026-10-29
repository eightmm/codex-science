import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codex_science.model_registry_v2 import (
    build_model_receipt_v2,
    canonical_sha256,
    load_registry_v2,
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

    def test_registry_requires_nonblank_string_fields(self) -> None:
        missing = object()
        fields = (
            (("registry_revision",), "registry_revision"),
            (("models", 0, "id"), "model 0 id"),
            (("models", 0, "status"), "model deterministic-translation-baseline status"),
            *((("models", 0, field), f"model deterministic-translation-baseline {field}")
              for field in ("family", "skill", "acceptance_contract")),
            (("models", 0, "implementation", "repository"), "model deterministic-translation-baseline repository"),
            (("models", 0, "license", "code"), "model deterministic-translation-baseline code license"),
            (("models", 0, "license", "weights"), "model deterministic-translation-baseline weights license"),
        )
        for path, label in fields:
            for value in (missing, None, "", " \t", 0, 1, False, True, 1.5, [], {}):
                payload = copy.deepcopy(self.registry)
                record = payload
                for key in path[:-1]:
                    record = record[key]
                if value is missing:
                    record.pop(path[-1])
                else:
                    record[path[-1]] = value
                before = copy.deepcopy(payload)
                with self.subTest(field=path, value=value):
                    with self.assertRaises(ValueError) as error:
                        validate_registry_v2(payload)
                    self.assertEqual(f"{label} is required", str(error.exception))
                    self.assertEqual(before, payload)
        for field, label in (("implementation", "repository"), ("license", "code license")):
            payload = copy.deepcopy(self.registry)
            payload["models"][0][field] = {}
            with self.subTest(empty=field), self.assertRaisesRegex(ValueError, f"{label} is required"):
                select_models(payload, task="acceptance-fixture", modality="protein-ligand")

    def _acceptance_registry(self):
        payload = copy.deepcopy(self.registry)
        model = payload["models"][0]
        model["status"] = "acceptance-tested"
        model["implementation"]["commit_sha256"] = "a" * 64
        model["acceptance"] = {
            "status": "passed", "bundle": "examples/sbdd-executable/input.json",
            "bundle_sha256": hashlib.sha256((self.root / "examples/sbdd-executable/input.json").read_bytes()).hexdigest(),
        }
        return payload

    def _write_registry(self, root, payload):
        registry_path = root / "models" / "registry-v2.json"
        registry_path.parent.mkdir(exist_ok=True)
        registry_path.write_text(json.dumps(payload), encoding="utf-8")
        return registry_path

    def _registry_cli(self, path, *arguments):
        return subprocess.run(
            [sys.executable, str(self.root / "scripts/validate_model_registry_v2.py"), "--registry", str(path), *arguments],
            capture_output=True, text=True,
        )

    def test_acceptance_bundle_requires_safe_relative_text_path(self) -> None:
        missing = object()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for value in (missing, None, "", " \t", 0, False, [], {}, "../x.json", "examples/../x.json",
                          str(root / "outside.json"), "C:/outside.json", "C:outside.json", "\\\\server\\share\\x.json",
                          "..\\x.json", "bad\x00path", " ../x.json ", " /outside.json "):
                payload = self._acceptance_registry()
                if value is missing:
                    payload["models"][0]["acceptance"].pop("bundle")
                else:
                    payload["models"][0]["acceptance"]["bundle"] = value
                with self.subTest(bundle=value):
                    with self.assertRaisesRegex(ValueError, "deterministic-translation-baseline.*acceptance bundle"):
                        validate_registry_v2(payload)
                    registry_path = self._write_registry(root, payload)
                    with self.assertRaises(ValueError):
                        load_registry_v2(registry_path)
                    result = self._registry_cli(registry_path)
                    self.assertEqual(2, result.returncode, result.stderr)
                    self.assertIn("acceptance bundle", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)

    def test_acceptance_bundle_file_must_exist_and_match_in_loader_and_cli(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = self._acceptance_registry()
            bundle = payload["models"][0]["acceptance"]["bundle"]
            bundle_path = root / bundle
            bundle_path.parent.mkdir(parents=True)
            for case in ("missing", "wrong-digest", "directory", "escaping-symlink", "symlink-loop"):
                payload["models"][0]["status"] = " acceptance-tested " if case == "missing" else "acceptance-tested"
                if case == "wrong-digest":
                    bundle_path.write_bytes(b"different bytes")
                elif case == "directory":
                    bundle_path.mkdir()
                elif case == "escaping-symlink":
                    bundle_path.symlink_to(self.root / bundle)
                elif case == "symlink-loop":
                    bundle_path.symlink_to(bundle_path.name)
                registry_path = self._write_registry(root, payload)
                with self.subTest(case=case):
                    self.assertTrue(validate_registry_v2(payload))
                    with self.assertRaisesRegex(ValueError, f"deterministic-translation-baseline.*{bundle}"):
                        load_registry_v2(registry_path)
                    for arguments in ((), ("--receipt", str(root / "absent-receipt.json"))):
                        result = self._registry_cli(registry_path, *arguments)
                        self.assertEqual(2, result.returncode, result.stderr)
                        self.assertIn("deterministic-translation-baseline", result.stderr)
                        self.assertIn(bundle, result.stderr)
                        self.assertNotIn("Traceback", result.stderr)
                if bundle_path.is_dir():
                    bundle_path.rmdir()
                elif bundle_path.exists() or bundle_path.is_symlink():
                    bundle_path.unlink()

            payload = self._acceptance_registry()
            bundle = payload["models"][0]["acceptance"]["bundle"]
            bundle_path.write_bytes((self.root / bundle).read_bytes())
            registry_path = self._write_registry(root, payload)
            self.assertEqual(payload, load_registry_v2(registry_path))
            self.assertEqual(0, self._registry_cli(registry_path).returncode)
            outside_directory = root / "other"
            outside_directory.mkdir()
            outside_registry = outside_directory / registry_path.name
            outside_registry.write_text(json.dumps(payload), encoding="utf-8")
            registry_alias = registry_path.parent / "alias.json"
            registry_alias.symlink_to(outside_registry)
            for path in (outside_registry, registry_alias):
                with self.subTest(registry=path):
                    with self.assertRaisesRegex(ValueError, "deterministic-translation-baseline.*models/"):
                        load_registry_v2(path)
                    for arguments in ((), ("--receipt", str(root / "absent-receipt.json"))):
                        result = self._registry_cli(path, *arguments)
                        self.assertEqual(2, result.returncode, result.stderr)
                        self.assertIn("models/", result.stderr)
                        self.assertNotIn("Traceback", result.stderr)
            for padding in (" ", "\t"):
                payload["models"][0]["acceptance"]["bundle"] = f"{padding}{bundle}{padding}"
                registry_path = self._write_registry(root, payload)
                with self.subTest(padding=padding):
                    self.assertEqual(payload, load_registry_v2(registry_path))
                    result = self._registry_cli(registry_path)
                    self.assertEqual(0, result.returncode, result.stderr)

            for status in ("cataloged", "experimental", "smoke-tested", "contract-tested", "degraded", "deprecated", "license-blocked"):
                for bundle in (None, "../absent.json", str(root / "absent.json"), 0):
                    payload = copy.deepcopy(self.registry)
                    payload["models"][0]["status"] = status
                    payload["models"][0]["acceptance"]["bundle"] = bundle
                    with self.subTest(status=status, bundle=bundle):
                        registry_path = self._write_registry(root, payload)
                        self.assertEqual(payload, load_registry_v2(registry_path))
                        result = self._registry_cli(registry_path)
                        self.assertEqual(0, result.returncode, result.stderr)
                        outside_registry.write_text(json.dumps(payload), encoding="utf-8")
                        self.assertEqual(payload, load_registry_v2(outside_registry))
                        result = self._registry_cli(outside_registry)
                        self.assertEqual(0, result.returncode, result.stderr)
            payload = dict(self.registry, models=[])
            outside_registry.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(payload, load_registry_v2(outside_registry))
            result = self._registry_cli(outside_registry)
            self.assertEqual(0, result.returncode, result.stderr)

    def test_acceptance_bundle_matching_example_and_empty_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = self._acceptance_registry()
            bundle = payload["models"][0]["acceptance"]["bundle"]
            bundle_path = root / bundle
            bundle_path.parent.mkdir(parents=True)
            example_bytes = (self.root / bundle).read_bytes()
            for content in (example_bytes, b"", b"x" * (1024 * 1024), b"x" * (1024 * 1024 + 1)):
                bundle_path.write_bytes(content)
                payload["models"][0]["acceptance"]["bundle_sha256"] = hashlib.sha256(content).hexdigest()
                registry_path = self._write_registry(root, payload)
                self.assertEqual(payload, load_registry_v2(registry_path))
                model = validate_registry_v2(payload)["deterministic-translation-baseline"]
                receipt = build_model_receipt_v2(
                    model, registry_sha256_value=registry_sha256(payload), code_revision="code-a",
                    weight_revision="not-applicable", database_revisions={}, configuration_sha256="a" * 64,
                    input_sha256="b" * 64, acceptance_bundle_sha256=model["acceptance"]["bundle_sha256"],
                )
                receipt_path = root / "receipt.json"
                receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
                for arguments in ((), ("--receipt", str(receipt_path))):
                    result = self._registry_cli(registry_path, *arguments)
                    self.assertEqual(0, result.returncode, result.stderr)
            bundle_path.write_bytes(b"changed after receipt")
            result = self._registry_cli(registry_path, "--receipt", str(receipt_path))
            self.assertEqual(2, result.returncode, result.stderr)
            self.assertIn(bundle, result.stderr)

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

    def test_receipt_builder_requires_string_revision_pins(self) -> None:
        arguments = dict(
            registry_sha256_value=registry_sha256(self.registry),
            code_revision=" c ", weight_revision="not-applicable", database_revisions={},
            configuration_sha256="a" * 64, input_sha256="b" * 64,
        )
        model = self.models["autodock-vina"]
        receipt = build_model_receipt_v2(model, **arguments)
        self.assertEqual("c", receipt["code_revision"])
        self.assertEqual({}, receipt["database_revisions"])
        self.assertEqual([], validate_model_receipt_v2(receipt, self.registry))
        for field in ("code_revision", "weight_revision", "database_revisions"):
            omitted = dict(arguments)
            omitted.pop(field)
            with self.subTest(omitted=field), self.assertRaises(TypeError):
                build_model_receipt_v2(model, **omitted)
        for value in (None, "", " ", 0, 1, False, [], {}):
            for field in ("code_revision", "weight_revision", "database_revisions"):
                override = {"db": value} if field == "database_revisions" else value
                changed = dict(arguments, **{field: override})
                before = copy.deepcopy(changed)
                with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, "revision"):
                    build_model_receipt_v2(model, **changed)
                self.assertEqual(before, changed)
        for value in (None, [], "db"):
            with self.subTest(mapping=value), self.assertRaisesRegex(ValueError, "database_revisions"):
                build_model_receipt_v2(model, **dict(arguments, database_revisions=value))
        pinned = build_model_receipt_v2(model, **dict(arguments, database_revisions={"db": "v"}))
        self.assertEqual({"db": "v"}, pinned["database_revisions"])
        self.assertEqual([], validate_model_receipt_v2(pinned, self.registry))

    def test_receipt_cli_refuses_missing_and_invalid_revision_pins(self) -> None:
        missing = object()
        cases = [dict(self._receipt())]
        for field in ("code_revision", "weight_revision", "database_revisions"):
            cases[0].pop(field)
            values = (missing, None, "", " ", 0, 1, False, [], {})
            if field == "database_revisions":
                values = (missing, None, [], "db") + tuple({"db": value} for value in values[1:])
            for value in values:
                receipt = self._receipt()
                if value is missing:
                    receipt.pop(field)
                else:
                    receipt[field] = value
                cases.append(receipt)
        with tempfile.TemporaryDirectory() as directory:
            receipt_path = Path(directory) / "receipt.json"
            command = [sys.executable, str(self.root / "scripts" / "validate_model_registry_v2.py"), "--receipt", str(receipt_path)]
            for receipt in cases:
                receipt.pop("fingerprint")
                receipt["fingerprint"] = canonical_sha256(receipt)
                before = copy.deepcopy(receipt)
                with self.subTest(receipt=receipt):
                    findings = validate_model_receipt_v2(receipt, self.registry)
                    self.assertEqual(["invalid-model-receipt-v2"], [item["code"] for item in findings])
                    self.assertEqual("critical", findings[0]["severity"])
                    self.assertIn("revision", findings[0]["message"])
                    self.assertEqual(before, receipt)
                    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
                    result = subprocess.run(command, capture_output=True, text=True)
                    self.assertEqual(1, result.returncode, result.stderr)
                    self.assertEqual(findings[0]["message"], json.loads(result.stdout)["message"])
                    self.assertNotIn("Traceback", result.stderr)

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


    def test_registry_cli_refuses_malformed_loader_inputs(self) -> None:
        from loader_cases import assert_refused, malformed_json
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            for contents in malformed_json():
                path.write_bytes(contents)
                with self.subTest(contents=contents):
                    assert_refused(self, "validate_model_registry_v2.py", ["--registry", path], 2)
            path.unlink()
            for candidate in (path, Path(directory)):
                assert_refused(self, "validate_model_registry_v2.py", ["--registry", candidate], 2)

    def test_registry_schema_rejects_boolean_and_float(self) -> None:
        for value in (True, 2.0, 0):
            payload = dict(self.registry, schema_version=value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_registry_v2(payload)


if __name__ == "__main__":
    unittest.main()
