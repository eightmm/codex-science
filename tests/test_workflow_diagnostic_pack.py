"""Synthetic diagnostic fixtures, hand calculations and deterministic adversarial checks."""
import copy
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/workflow-diagnostic-accuracy"
CLI = ROOT / "scripts/validate_diagnostic_accuracy_pack.py"
CALL_TIMEOUT = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "30"))


class FixtureCase(unittest.TestCase):
    def setUp(self):
        self.api = importlib.import_module("codex_science.diagnostic_accuracy_pack")
        self.pack = json.loads((FIXTURE / "pack.json").read_bytes())
        self.protocol = json.loads((FIXTURE / "protocol.json").read_bytes())
        self.cases = json.loads((FIXTURE / "cases.json").read_bytes())

    def folder(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        folder = Path(temporary.name) / "parent" / "bundle"
        folder.mkdir(parents=True)
        self.reset_bundle(folder)
        return folder

    def reset_bundle(self, folder):
        self.pack = json.loads((FIXTURE / "pack.json").read_bytes())
        for path in FIXTURE.glob("*.json"):
            shutil.copyfile(path, folder / path.name)

    def write(self, folder, name, value):
        raw = (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode()
        (folder / name).write_bytes(raw)
        return {"path": name, "sha256": hashlib.sha256(raw).hexdigest()}

    def run_pack(self, folder):
        self.write(folder, "pack.json", self.pack)
        return self.api.validate_diagnostic_accuracy_pack(folder / "pack.json")

    def change_input(self, folder, name, value):
        identity = self.write(folder, name + ".json", value)
        self.pack["inputs"][name] = identity
        if name == "protocol":
            self.pack["frozen_protocol_sha256"] = identity["sha256"]

    def negative(self, name):
        index = json.loads((FIXTURE / "negative-cases.json").read_bytes())
        case = next(case for case in index["cases"] if case["id"] == name)
        with self.assertRaisesRegex(ValueError, "^" + case["finding"] + ":"):
            self.api.validate_diagnostic_accuracy_pack(FIXTURE / case["path"])


class DiagnosticComputationTests(FixtureCase):
    def test_fixture_and_hand_calculations(self):
        result = self.api.validate_diagnostic_accuracy_pack(FIXTURE / "pack.json")
        expected = json.loads((FIXTURE / "expected.json").read_bytes())
        self.assertEqual(expected, result)
        self.assertEqual(result, self.api.validate_diagnostic_accuracy_pack(FIXTURE / "pack.json"))
        metrics = result["metrics"]
        self.assertEqual({"tp": 3, "fp": 1, "tn": 3, "fn": 1}, metrics["confusion"])
        self.assertEqual(3 / 4, metrics["sensitivity"]["estimate"])
        self.assertEqual(3 / 4, metrics["specificity"]["estimate"])
        # Of 16 case-control pairs, only score 0.4 versus score 0.6 is discordant.
        self.assertEqual(15 / 16, metrics["auc"]["estimate"])
        self.assertAlmostEqual(0.30064184258240184, metrics["sensitivity"]["interval"][0])
        self.assertAlmostEqual(0.9544127391902995, metrics["specificity"]["interval"][1])
        self.assertEqual("statistical-only", result["evidence_level"])
        self.assertEqual("unavailable", result["review"])
        self.assertEqual(list(self.api.STAGES), result["stages"])
        for record in result["predictive_values"]:
            self.assertEqual(0.5, record["assumed_prevalence"])
            self.assertEqual(0.75, record["value"])

    def test_exact_ties_direction_and_inclusive_threshold(self):
        self.protocol.update(minimum_cases=2, minimum_controls=2)
        self.protocol["threshold"]["value"] = 1
        self.cases["rows"] = self.cases["rows"][:4]
        for row, score, label in zip(self.cases["rows"], [2, 1, 1, 0], [1, 1, 0, 0]):
            row.update(score=score, reference_label=label)
        first = self.api.reference_computation(self.protocol, self.cases)
        self.assertEqual(3.5 / 4, first["auc"]["estimate"])
        self.assertEqual({"tp": 2, "fp": 1, "tn": 1, "fn": 0}, first["confusion"])
        self.protocol["direction"] = "lower"
        second = self.api.reference_computation(self.protocol, self.cases)
        self.assertEqual(0.5 / 4, second["auc"]["estimate"])
        self.assertEqual({"tp": 1, "fp": 2, "tn": 0, "fn": 1}, second["confusion"])
        for row in self.cases["rows"]:
            row["score"] *= 1e-100
        self.protocol["threshold"]["value"] = 1e-100
        self.assertEqual(second["auc"]["estimate"], self.api.reference_computation(self.protocol, self.cases)["auc"]["estimate"])

    def test_training_selection_never_uses_evaluation_labels(self):
        self.protocol["threshold"] = {"method": "youden-training", "chosen_on": "training", "value": None}
        self.cases["rows"] += [dict(row, subject_id="train-" + row["subject_id"], split="training") for row in self.cases["rows"]]
        first = self.api.reference_computation(self.protocol, self.cases)
        self.assertEqual(0.4, first["threshold"])
        for row in self.cases["rows"][:8]:
            row["reference_label"] = 1 - row["reference_label"]
        second = self.api.reference_computation(self.protocol, self.cases)
        self.assertEqual(first["threshold"], second["threshold"])
        self.protocol["direction"] = "lower"
        for row in self.cases["rows"]:
            row["score"] = -row["score"]
        third = self.api.reference_computation(self.protocol, self.cases)
        self.assertEqual(-0.7, third["threshold"])

    def test_disclosed_unblinding_and_unavailable_claim(self):
        folder = self.folder()
        self.protocol["unblinded_reference_disclosed"] = True
        self.cases["rows"][0]["blinded"] = False
        self.change_input(folder, "protocol", self.protocol)
        self.change_input(folder, "cases", self.cases)
        self.pack["claims"][0].update(status="unavailable", support=[], text="Independent evidence is unavailable.")
        result = self.run_pack(folder)
        self.assertEqual(["fixture-0"], result["metrics"]["unblinded_subjects"])
        self.assertEqual("unavailable", result["claims"][0]["status"])

    def test_predictive_prevalence_edges_and_undefined_denominators(self):
        folder = self.folder()
        for prevalence in (0, 0.2, 1):
            sensitivity = specificity = 0.75
            for record in self.pack["predictive_values"]:
                numerator = sensitivity * prevalence if record["metric"] == "ppv" else specificity * (1 - prevalence)
                other = 0.25 * (1 - prevalence) if record["metric"] == "ppv" else 0.25 * prevalence
                record.update(value=numerator / (numerator + other), assumed_prevalence=prevalence, applied_prevalence=prevalence)
            self.assertEqual("statistical-only", self.run_pack(folder)["evidence_level"])
        self.protocol["threshold"]["value"] = 2
        self.change_input(folder, "protocol", self.protocol)
        self.pack["predictive_values"][0].update(assumed_prevalence=1, applied_prevalence=1)
        with self.assertRaisesRegex(ValueError, "^predictive-undefined:"):
            self.run_pack(folder)

    def test_bootstrap_failure_counts_and_only_specific_error_is_swallowed(self):
        original = self.api._require
        calls = 0

        def fail_draw(condition, code, message):
            nonlocal calls
            if code == "bootstrap-degenerate":
                calls += 1
                condition = calls % 2 == 0
            return original(condition, code, message)

        with patch.object(self.api, "_require", side_effect=fail_draw), self.assertRaisesRegex(ValueError, "^bootstrap-success:"):
            self.api.reference_computation(self.protocol, self.cases)
        calls = 0
        self.protocol["intervals"]["minimum_success_fraction"] = 0.5
        with patch.object(self.api, "_require", side_effect=fail_draw):
            result = self.api.reference_computation(self.protocol, self.cases)
        self.assertEqual(100, result["auc"]["successful_draws"])
        with patch.object(self.api, "_auc", side_effect=ValueError("unexpected: injected")), self.assertRaisesRegex(ValueError, "^unexpected:"):
            self.api.reference_computation(self.protocol, self.cases)

    def test_cli_success_failure_and_no_writes(self):
        folder = self.folder()
        before = {str(path.relative_to(folder)): path.read_bytes() for path in folder.rglob("*") if path.is_file()}
        for name, code in (("pack.json", 0), ("negative.subject-leakage.pack.json", 2)):
            result = subprocess.run([sys.executable, str(CLI), str(folder / name)], capture_output=True, text=True, timeout=CALL_TIMEOUT)
            self.assertEqual(code, result.returncode, result.stderr)
            if code == 0:
                self.assertEqual("unavailable", json.loads(result.stdout)["review"])
                self.assertEqual("", result.stderr)
            else:
                self.assertTrue(json.loads(result.stderr)["finding"].startswith("subject-leakage:"))
                self.assertEqual("", result.stdout)
                self.assertNotIn("Traceback", result.stderr)
        after = {str(path.relative_to(folder)): path.read_bytes() for path in folder.rglob("*") if path.is_file()}
        self.assertEqual(before, after)


class DiagnosticSeededRefusalTests(FixtureCase):
    def test_evaluation_threshold(self):
        self.negative("evaluation-threshold")

    def test_verification_bias(self):
        self.negative("verification-bias")

    def test_score_selected_verification(self):
        self.negative("score-selected-verification")

    def test_incorporation_bias(self):
        self.negative("incorporation-bias")

    def test_subject_leakage(self):
        self.negative("subject-leakage")

    def test_insufficient_cases(self):
        self.negative("insufficient-cases")

    def test_insufficient_controls(self):
        self.negative("insufficient-controls")

    def test_missing_prevalence(self):
        self.negative("missing-prevalence")

    def test_prevalence_transfer(self):
        self.negative("prevalence-transfer")

    def test_wrong_predictive_value(self):
        self.negative("wrong-predictive-value")

    def test_constant_scores(self):
        self.negative("constant-scores")

    def test_undefined_class(self):
        self.negative("undefined-class")

    def test_missing_reference(self):
        self.negative("missing-reference")

    def test_unblinded_reference(self):
        self.negative("unblinded-reference")

    def test_post_outcome_freeze(self):
        self.negative("post-outcome-freeze")

    def test_clinical_utility(self):
        self.negative("clinical-utility")

    def test_screening_recommendation(self):
        self.negative("screening-recommendation")

    def test_causal(self):
        self.negative("causal")

    def test_physical_validity(self):
        self.negative("physical-validity")

    def test_review_approval(self):
        self.negative("review-approval")

    def test_computed_kind(self):
        self.negative("computed-kind")

    def test_computed_result(self):
        self.negative("computed-result")

    def test_empty_evidence(self):
        self.negative("empty-evidence")

    def test_unavailable_positive(self):
        self.negative("unavailable-positive")

    def test_outside_alias(self):
        self.negative("outside-alias")


class DiagnosticHardeningTests(FixtureCase):
    def test_unavailable_support_requires_unavailable_status(self):
        folder = self.folder()
        evidence = json.loads((folder / "evidence.json").read_bytes())
        available = copy.deepcopy(self.pack["claims"][0]["support"][0])
        for fields in (("kind",), ("result",), ("kind", "result")):
            record = dict(evidence, **{field: "unavailable" for field in fields})
            identity = self.write(folder, "unavailable.json", record)
            missing = dict(identity, origin="study")
            for support in ([missing], [available, missing], [missing, available]):
                for status in ("supported", "replicated", "suggestive", "unsupported",
                               "planned", "conflicting", "withdrawn", "unavailable"):
                    self.pack["claims"][0].update(
                        status=status, support=support, text="Evidence availability is recorded.")
                    with self.subTest(fields=fields, count=len(support), first=support[0]["path"], status=status):
                        if status == "unavailable":
                            result = self.run_pack(folder)
                            self.assertEqual(status, result["claims"][0]["status"])
                        else:
                            with self.assertRaisesRegex(ValueError, "^unavailable-evidence:"):
                                self.run_pack(folder)
        self.pack["claims"][0].update(status="replicated", support=[available])
        with self.assertRaisesRegex(ValueError, "^claim-replication:"):
            self.run_pack(folder)

    def test_cli_refuses_unavailable_support_without_writes(self):
        folder = self.folder()
        evidence = json.loads((folder / "evidence.json").read_bytes())
        identity = self.write(folder, "unavailable.json", dict(evidence, result="unavailable"))
        self.pack["claims"][0].update(status="unsupported", support=[dict(identity, origin="study")])
        self.write(folder, "pack.json", self.pack)
        before = {path.name: path.read_bytes() for path in folder.iterdir()}
        result = subprocess.run([sys.executable, str(CLI), str(folder / "pack.json")],
                                capture_output=True, text=True, timeout=CALL_TIMEOUT)
        self.assertEqual(2, result.returncode, result.stdout)
        self.assertEqual("", result.stdout)
        self.assertEqual("refused", json.loads(result.stderr)["status"])
        self.assertTrue(json.loads(result.stderr)["finding"].startswith("unavailable-evidence:"))
        self.assertEqual(before, {path.name: path.read_bytes() for path in folder.iterdir()})

    def test_total_input_budgets_before_reading(self):
        path = FIXTURE / "pack.json"
        with patch.object(self.api, "MAX_ARTIFACTS", 4):
            self.api.validate_diagnostic_accuracy_pack(path)
        for bound in (0, 3):
            with patch.object(self.api, "MAX_ARTIFACTS", bound), self.assertRaisesRegex(ValueError, "^input-limit:"):
                self.api.validate_diagnostic_accuracy_pack(path)
        size = sum((FIXTURE / name).stat().st_size for name in ("pack.json", "protocol.json", "cases.json", "evidence.json"))
        with patch.object(self.api, "MAX_TOTAL_BYTES", size):
            self.api.validate_diagnostic_accuracy_pack(path)
        for bound in (0, size - 1):
            with patch.object(self.api, "MAX_TOTAL_BYTES", bound), self.assertRaisesRegex(ValueError, "^input-limit:"):
                self.api.validate_diagnostic_accuracy_pack(path)

    def test_json_node_budget_is_checked_before_parse_and_across_the_bundle(self):
        with patch.object(self.api, "MAX_NODES", 64), patch.object(self.api.json, "loads", side_effect=AssertionError("parsed")):
            with self.assertRaisesRegex(ValueError, "^input-limit:"):
                self.api._json(b"{" + b",".join(b'"k%d":[]' % index for index in range(70)) + b"}")
        path = FIXTURE / "pack.json"
        with patch.object(self.api, "MAX_NODES", 138):
            self.api.validate_diagnostic_accuracy_pack(path)
        with patch.object(self.api, "MAX_NODES", 137), self.assertRaisesRegex(ValueError, "^input-limit:"):
            self.api.validate_diagnostic_accuracy_pack(path)

    def test_bad_bundle_path_is_labelled(self):
        with self.assertRaisesRegex(ValueError, "^input-path:"):
            self.api.validate_diagnostic_accuracy_pack("bad\x00directory/pack.json")

    def test_protocol_freeze_is_checked_before_case_labels_are_opened(self):
        folder = self.folder()
        self.pack["freeze_before_labels"] = False
        (folder / "cases.json").unlink()
        with self.assertRaisesRegex(ValueError, "^protocol-freeze:"):
            self.run_pack(folder)

    def test_remaining_dimension_edges_and_record_integer_versions(self):
        folder = self.folder()
        for name, raw, expected in (
                ("MAX_ITEMS", b'{"x":[]}', {"x": []}),
                ("MAX_NODES", b'{}', {}),
                ("MAX_DEPTH", b'{}', {})):
            bound = 0 if name == "MAX_DEPTH" else 1
            with self.subTest(name=name), patch.object(self.api, name, bound):
                self.assertEqual(expected, self.api._json(raw)[0])
                oversized = b'{"x":[]}' if name != "MAX_ITEMS" else b'{"x":[],"y":[]}'
                with self.assertRaisesRegex(ValueError, "^(input-limit|invalid-json):"):
                    self.api._json(oversized)
        for key in ("minimum_cases", "minimum_controls"):
            protocol = copy.deepcopy(self.protocol)
            protocol[key] = 0
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                self.api.reference_computation(protocol, self.cases)
        for draws in (1,):
            protocol = copy.deepcopy(self.protocol)
            protocol["intervals"]["draws"] = draws
            for seed in (0, -2**63, 2**63 - 1):
                protocol["intervals"]["seed"] = seed
                self.assertEqual(1, self.api.reference_computation(protocol, self.cases)["auc"]["successful_draws"])
        for value in (0, 1.1, [], True):
            protocol = copy.deepcopy(self.protocol)
            protocol["intervals"]["minimum_success_fraction"] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                self.api.reference_computation(protocol, self.cases)
        original = copy.deepcopy(self.pack)
        evidence = json.loads((folder / "evidence.json").read_bytes())
        for version in (True, 1.0, "1", [], 0):
            self.pack = copy.deepcopy(original)
            identity = self.write(folder, "evidence.json", dict(evidence, schema_version=version))
            self.pack["study_outputs"] = [identity]
            self.pack["claims"][0]["support"] = [dict(identity, origin="study")]
            with self.subTest(version=version), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                self.run_pack(folder)
            self.pack["claims"] = []
            with self.subTest(version=version, unused=True), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                self.run_pack(folder)
        self.reset_bundle(folder)
        self.pack["claims"] *= self.api.MAX_CLAIMS + 1
        with self.assertRaisesRegex(ValueError, "^input-limit:"):
            self.run_pack(folder)
        for value in ([], {}, None, [original["predictive_values"][0]], original["predictive_values"] * 2):
            self.pack = copy.deepcopy(original)
            self.pack["predictive_values"] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "^(input-limit|predictive-prevalence):"):
                self.run_pack(folder)

    def test_integer_fields_and_key_types(self):
        folder = self.folder()
        for key in ("schema_version", "minimum_cases", "minimum_controls"):
            for value in (True, 1.0, "1", None, [], {}):
                protocol = copy.deepcopy(self.protocol)
                protocol[key] = value
                self.change_input(folder, "protocol", protocol)
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                    self.run_pack(folder)
        for key in ("draws", "seed"):
            for value in (True, 1729.0, "1729", None, [], {}):
                protocol = copy.deepcopy(self.protocol)
                protocol["intervals"][key] = value
                self.change_input(folder, "protocol", protocol)
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                    self.run_pack(folder)
        self.change_input(folder, "protocol", self.protocol)
        for key in ("schema_version", "reference_label"):
            for value in (True, 1.0, "1", [], {}):
                cases = copy.deepcopy(self.cases)
                target = cases if key == "schema_version" else cases["rows"][0]
                target[key] = value
                self.change_input(folder, "cases", cases)
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                    self.run_pack(folder)
        self.change_input(folder, "cases", self.cases)
        baseline = copy.deepcopy(self.pack)
        for key in ("status", "kind", "id"):
            self.pack = copy.deepcopy(baseline)
            self.pack["claims"][0][key] = []
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                self.run_pack(folder)
        self.pack = copy.deepcopy(baseline)
        for key in ("schema_version",):
            self.pack[key] = 1.0
            with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                self.run_pack(folder)

    def test_numeric_and_row_limits(self):
        for minimum in (0, -1, [], 1.5):
            protocol = copy.deepcopy(self.protocol)
            protocol["minimum_cases"] = minimum
            with self.subTest(minimum=minimum), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                self.api.reference_computation(protocol, self.cases)
        for draws in (0, self.api.MAX_DRAWS + 1, "200", []):
            protocol = copy.deepcopy(self.protocol)
            protocol["intervals"]["draws"] = draws
            with self.subTest(draws=draws), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                self.api.reference_computation(protocol, self.cases)
        with patch.object(self.api, "MAX_DRAWS", 200):
            self.api.reference_computation(self.protocol, self.cases)
        with patch.object(self.api, "MAX_DRAWS", 199), self.assertRaisesRegex(ValueError, "^invalid-record:"):
            self.api.reference_computation(self.protocol, self.cases)
        with patch.object(self.api, "MAX_ROWS", 8):
            self.api.reference_computation(self.protocol, self.cases)
        with patch.object(self.api, "MAX_ROWS", 7), self.assertRaisesRegex(ValueError, "^input-limit:"):
            self.api.reference_computation(self.protocol, self.cases)
        for rows in ([], {}, [dict(self.cases["rows"][0], subject_id=f"oversize-{i}") for i in range(self.api.MAX_ROWS + 1)]):
            with self.subTest(size=len(rows)), self.assertRaisesRegex(ValueError, "^input-limit:"):
                self.api.reference_computation(self.protocol, dict(self.cases, rows=rows))
        for score in (True, "0.5", [], None, float("nan"), float("inf"), 10**101):
            cases = copy.deepcopy(self.cases)
            cases["rows"][0]["score"] = score
            with self.subTest(score=score), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                self.api.reference_computation(self.protocol, cases)

    def test_claim_and_support_limits_before_record_scans(self):
        folder = self.folder()
        for limit in ("MAX_CLAIMS", "MAX_SUPPORT"):
            with patch.object(self.api, limit, 1):
                self.run_pack(folder)
            with patch.object(self.api, limit, 0), self.assertRaisesRegex(ValueError, "^input-limit:"):
                self.run_pack(folder)
        self.pack["claims"] = []
        self.run_pack(folder)
        self.pack["claims"] = {}
        with self.assertRaisesRegex(ValueError, "^input-limit:"):
            self.run_pack(folder)

    def test_claim_wording_all_statuses_whole_words_and_sources(self):
        folder = self.folder()
        original = copy.deepcopy(self.pack)
        for status in ("supported", "replicated", "suggestive", "unavailable"):
            for word in ("causality", "mechanism", "therapeutic", "clinical", "efficacy", "effective", "treatment",
                         "cure", "prevention", "recommendation", "prescription", "binding", "affinity", "inhibition",
                         "activation", "regulation", "drive", "drives", "driven", "induction", "truth"):
                self.pack = copy.deepcopy(original)
                self.pack["claims"][0].update(status=status, text=word.upper())
                with self.subTest(status=status, word=word), self.assertRaisesRegex(ValueError, "^claim-boundary:"):
                    self.run_pack(folder)
        for word in ("supported", "replicated", "suggestive", "significant"):
            self.pack = copy.deepcopy(original)
            self.pack["claims"][0].update(status="unavailable", support=[], text=word)
            with self.subTest(word=word), self.assertRaisesRegex(ValueError, "^unavailable-positive:"):
                self.run_pack(folder)
        self.pack = copy.deepcopy(original)
        self.pack["claims"][0]["text"] = "Synthetic xbinding and xclinical labels are associated with scores."
        self.run_pack(folder)
        for origin in ("external", "independent", "preregistered"):
            identity = self.pack["claims"][0]["support"][0]
            identity["origin"] = origin
            copied = folder / "alias.json"
            shutil.copyfile(folder / "evidence.json", copied)
            identity["path"] = "alias.json"
            with self.subTest(origin=origin), self.assertRaisesRegex(ValueError, "^evidence-independence:"):
                self.run_pack(folder)

    def test_json_duplicates_nonfinite_roots_depth_strings_and_huge_numbers(self):
        folder = self.folder()
        samples = [b'{}{}', b'[]', b'null', b'{"x":1,"x":2}', b'{"x":{"y":1,"y":2}}',
                   b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e1000}', b'{"x":' + b'9' * 5000 + b'}',
                   b'{"x":' + b'[' * 1200 + b'0' + b']' * 1200 + b'}', b'\xff',
                   json.dumps({"x": "x" * (self.api.MAX_TEXT + 1)}).encode()]
        for raw in samples:
            (folder / "pack.json").write_bytes(raw)
            with self.subTest(raw=raw[:35]), self.assertRaisesRegex(ValueError, "^(invalid-json|invalid-record|input-limit):"):
                self.api.validate_diagnostic_accuracy_pack(folder / "pack.json")
        self.assertEqual({"x": "abc"}, self.api._json(b'{"x":"abc"}')[0])
        with patch.object(self.api, "MAX_TEXT", 3):
            self.api._json(b'{"x":"abc"}')
            with self.assertRaisesRegex(ValueError, "^input-limit:"):
                self.api._json(b'{"x":"abcd"}')
        with patch.object(self.api, "MAX_DEPTH", 0), self.assertRaisesRegex(ValueError, "^invalid-json:"):
            self.api._json(b'{"x":[]}')

    def test_paths_hashes_and_special_files(self):
        folder = self.folder()
        original = copy.deepcopy(self.pack)
        for name in ("../protocol.json", "./protocol.json", "a//b", "a\\b", "/tmp/fixture.json", "C:/fixture.json", ""):
            self.pack = copy.deepcopy(original)
            self.pack["inputs"]["protocol"]["path"] = name
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "^(input-path|invalid-record):"):
                self.run_pack(folder)
        self.pack = copy.deepcopy(original)
        self.pack["inputs"]["protocol"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "^input-hash:"):
            self.run_pack(folder)
        for name, make in (("fifo", lambda path: os.mkfifo(path)), ("directory", lambda path: path.mkdir()),
                           ("link", lambda path: path.symlink_to("protocol.json"))):
            target = folder / name
            make(target)
            self.pack = copy.deepcopy(original)
            self.pack["inputs"]["protocol"]["path"] = name
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "^(input-file|input-changed):"):
                self.run_pack(folder)
        (folder / "linked-parent").symlink_to(folder, target_is_directory=True)
        self.pack["inputs"]["protocol"]["path"] = "linked-parent/protocol.json"
        with self.assertRaisesRegex(ValueError, "^input-file:"):
            self.run_pack(folder)

    def test_byte_limit_exact_zero_and_growth(self):
        folder = self.folder()
        raw = (folder / "protocol.json").read_bytes()
        bundle = self.api._Bundle(folder / "pack.json")
        self.addCleanup(bundle.close)
        relative = self.api._relative("protocol.json")
        with patch.object(self.api, "MAX_BYTES", len(raw)):
            self.assertEqual(raw, bundle._read(relative)[0])
        for bound in (0, len(raw) - 1):
            with patch.object(self.api, "MAX_BYTES", bound), self.assertRaisesRegex(ValueError, "^input-file:"):
                bundle._read(relative)
        real_fstat = os.fstat
        calls = 0

        def grow(descriptor):
            nonlocal calls
            info = real_fstat(descriptor)
            if stat_is_file(info.st_mode):
                calls += 1
                if calls == 2:
                    with (folder / "protocol.json").open("ab") as handle:
                        handle.write(b" ")
                    return real_fstat(descriptor)
            return info

        import stat
        stat_is_file = stat.S_ISREG
        with patch.object(self.api.os, "fstat", side_effect=grow), self.assertRaisesRegex(ValueError, "^input-changed:"):
            bundle._read(relative)

    def test_input_replacement_and_hash_recheck(self):
        folder = self.folder()
        original = self.api._claims

        def replace(*args):
            result = original(*args)
            target = folder / "cases.json"
            raw = target.read_bytes()
            target.unlink()
            target.write_bytes(raw)
            return result

        with patch.object(self.api, "_claims", side_effect=replace), self.assertRaisesRegex(ValueError, "^input-changed:"):
            self.run_pack(folder)

    def test_root_and_ancestor_symlink_swap_at_open(self):
        real_open = os.open
        for component in ("root", "ancestor"):
            folder = self.folder()
            target = folder if component == "root" else folder.parent
            moved = target.with_name(target.name + "-moved")
            changed = False

            def swap(path, flags, *args, **kwargs):
                nonlocal changed
                if path == target.name and "dir_fd" in kwargs and not changed:
                    changed = True
                    target.rename(moved)
                    target.symlink_to(moved, target_is_directory=True)
                return real_open(path, flags, *args, **kwargs)

            with self.subTest(component=component), patch.object(self.api.os, "open", side_effect=swap), self.assertRaisesRegex(
                    ValueError, "^(input-file|input-changed|input-path):"):
                self.api.validate_diagnostic_accuracy_pack(folder / "pack.json")
            self.assertTrue(changed)

    def test_replaced_root_at_final_recheck(self):
        folder = self.folder()
        original = self.api._claims

        def replace(*args):
            result = original(*args)
            moved = folder.with_name("moved")
            folder.rename(moved)
            shutil.copytree(moved, folder)
            return result

        with patch.object(self.api, "_claims", side_effect=replace), self.assertRaisesRegex(ValueError, "^input-changed:"):
            self.run_pack(folder)

    def test_root_replacement_during_final_hash_reads(self):
        folder = self.folder()
        original = self.api._Bundle._read
        counts = {}

        def replace(bundle, relative):
            raw = original(bundle, relative)
            name = relative.as_posix()
            counts[name] = counts.get(name, 0) + 1
            if name == "cases.json" and counts[name] == 2:
                moved = folder.with_name("moved-during-recheck")
                folder.rename(moved)
                shutil.copytree(moved, folder)
            return raw

        with patch.object(self.api._Bundle, "_read", new=replace), self.assertRaisesRegex(ValueError, "^input-changed:"):
            self.run_pack(folder)

    def test_read_once_parse_cache_and_final_verification(self):
        folder = self.folder()
        counts = {}
        original = self.api._Bundle._read

        def read(bundle, relative):
            name = relative.as_posix()
            counts[name] = counts.get(name, 0) + 1
            return original(bundle, relative)

        with patch.object(self.api._Bundle, "_read", new=read):
            self.run_pack(folder)
        self.assertEqual({"pack.json": 2, "protocol.json": 2, "cases.json": 2, "evidence.json": 2}, counts)


if __name__ == "__main__":
    unittest.main()
