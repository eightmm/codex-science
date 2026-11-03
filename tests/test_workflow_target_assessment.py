"""Offline replay of labelled synthetic target-assessment fixtures."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from codex_science.target_assessment_pack import _Bundle
from codex_science.target_assessment_pack import validate_target_assessment_pack


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/workflow-target-assessment-dossier"
SCRIPT = ROOT / "scripts/validate_target_assessment_pack.py"
CALL_TIMEOUT = int(os.environ.get("OMS_TEST_CALL_TIMEOUT", "60"))


class TargetAssessmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.bundle = Path(self.temp.name) / "synthetic"
        shutil.copytree(EXAMPLE / "synthetic", self.bundle)
        network = patch("socket.socket", side_effect=AssertionError("offline fixture"))
        network.start()
        self.addCleanup(network.stop)

    def read(self, name):
        return json.loads((self.bundle / name).read_text(encoding="utf-8"))

    def write(self, name, data):
        (self.bundle / name).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def rehash(self):
        def refresh(value):
            if isinstance(value, dict):
                if set(value) == {"path", "sha256"}:
                    value["sha256"] = hashlib.sha256(
                        (self.bundle / value["path"]).read_bytes()
                    ).hexdigest()
                else:
                    for child in value.values():
                        refresh(child)
            elif isinstance(value, list):
                for child in value:
                    refresh(child)

        for name in [f"stage-{index}.json" for index in range(1, 7)] + ["dossier.json"]:
            data = self.read(name)
            refresh(data)
            self.write(name, data)

    def cli(self, path=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(path or self.bundle)],
            capture_output=True, text=True, timeout=CALL_TIMEOUT,
        )

    def defect(self, name):
        case = json.loads((EXAMPLE / "negative" / f"{name}.json").read_text())
        self.assertTrue(case["synthetic"])
        for change in case["changes"]:
            data = self.read(change["file"])
            parent = data
            parts = change["pointer"].strip("/").split("/")
            for part in parts[:-1]:
                parent = parent[int(part)] if isinstance(parent, list) else parent[part]
            final = int(parts[-1]) if isinstance(parent, list) else parts[-1]
            parent[final] = change["value"]
            self.write(change["file"], data)
        self.rehash()
        with self.assertRaisesRegex(ValueError, case["expected_code"]):
            validate_target_assessment_pack(self.bundle)
        result = self.cli()
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertEqual(case["expected_code"], json.loads(result.stdout)["finding"])
        self.assertNotIn("Traceback", result.stderr)

    def test_synthetic_replay(self):
        expected = json.loads((EXAMPLE / "expected-validation.json").read_text())
        self.assertEqual(expected, validate_target_assessment_pack(self.bundle))
        result = self.cli()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(expected, json.loads(result.stdout))

    def test_identity_mismatch(self):
        self.defect("identity-mismatch")

    def test_cohort_dependence(self):
        self.defect("cohort-dependence")

    def test_availability_overclaim(self):
        self.defect("availability-overclaim")

    def test_potency_mixing(self):
        self.defect("potency-mixing")

    def test_missing_record(self):
        self.defect("missing-record")

    def test_modality_direction(self):
        self.defect("modality-direction")

    def test_critical_liability(self):
        self.defect("critical-liability")

    def test_memo_overclaim(self):
        self.defect("memo-overclaim")

    def test_association_causality(self):
        self.defect("association-causality")

    def test_numerical_validity(self):
        self.defect("numerical-validity")

    def test_review_truth(self):
        self.defect("review-truth")

    def record_claim(self, record_kind, result, text, kind="descriptive", status="supported"):
        snapshots = self.read("snapshots.json")
        record = next(source for source in snapshots["sources"]
                      if source["records"] and source["records"][0]["id"] == "normalization-1")["records"][0]
        record.update(kind=record_kind, result=result, statement=text)
        self.write("snapshots.json", snapshots)
        memo = self.read("stage-6.json")
        memo["data"]["claims"][0].update(text=text, kind=kind, evidence=[record["id"]], status=status)
        self.write("stage-6.json", memo)
        register = self.read("claims.json")
        register["claims"][0].update(text=text, permitted_inference=kind, status=status)
        self.write("claims.json", register)
        self.rehash()

    def test_supported_claim_rejects_review_and_computed_records(self):
        for record_kind, result in (("review-approval", "review-approval"), ("computed", "numerical-agreement")):
            for kind in ("descriptive", "associational"):
                for text in ("Independent review confirmed this target is effective.",
                             "Synthetic fixture: the recorded check completed."):
                    with self.subTest(record_kind=record_kind, kind=kind, text=text):
                        self.record_claim(record_kind, result, text, kind=kind)
                        with self.assertRaisesRegex(ValueError, "MEMO_OVERCLAIM"):
                            validate_target_assessment_pack(self.bundle)
                        result_cli = self.cli()
                        self.assertEqual(1, result_cli.returncode, result_cli.stderr)
                        self.assertEqual("MEMO_OVERCLAIM", json.loads(result_cli.stdout)["finding"])
        self.record_claim("review-approval", "review-approval", "Synthetic fixture: review completed.",
                          status="suggestive")
        validate_target_assessment_pack(self.bundle)

    def test_supported_descriptive_claim_rejects_efficacy_wording(self):
        for word in ("efficacy", "effective", "effectiveness", "efficacious", "EFFECTIVE"):
            with self.subTest(word=word):
                self.record_claim("descriptive", "identity", f"Synthetic fixture: {word}.")
                with self.assertRaisesRegex(ValueError, "MEMO_OVERCLAIM"):
                    validate_target_assessment_pack(self.bundle)
        for text, status in (("Synthetic fixture: the effect was recorded.", "supported"),
                             ("Synthetic fixture: ineffective and effectivenesses.", "supported"),
                             ("Synthetic fixture: efficacy remains unestablished.", "suggestive")):
            with self.subTest(text=text, status=status):
                self.record_claim("descriptive", "identity", text, status=status)
                validate_target_assessment_pack(self.bundle)

    def test_patient_advice(self):
        self.defect("patient-advice")

    def test_failed_control(self):
        self.defect("failed-control")

    def test_self_review(self):
        self.defect("self-review")

    def test_identity_fields_and_empty_ledger(self):
        for field in ("species", "isoform", "uniprot", "ensembl", "hgnc", "indication_id"):
            with self.subTest(field=field):
                data = self.read("snapshots.json")
                original = data["sources"][0]["target"][field]
                data["sources"][0]["target"][field] = "synthetic-other"
                self.write("snapshots.json", data)
                self.rehash()
                with self.assertRaisesRegex(ValueError, "TARGET_IDENTITY"):
                    validate_target_assessment_pack(self.bundle)
                data["sources"][0]["target"][field] = original
                self.write("snapshots.json", data)
        self.rehash()
        data = self.read("stage-1.json")
        data["data"]["target"] = {}
        self.write("stage-1.json", data)
        self.rehash()
        with self.assertRaisesRegex(ValueError, "TARGET_IDENTITY"):
            validate_target_assessment_pack(self.bundle)

    def test_independence_edges(self):
        for count, accepted in ((0, True), (1, True), (2, False), (-1, False),
                                (True, False), (1.5, False), ("1", False), (None, False)):
            with self.subTest(count=count):
                data = self.read("stage-2.json")
                data["data"]["independent_support_count"] = count
                self.write("stage-2.json", data)
                memo = self.read("stage-6.json")
                memo["data"]["decision"] = "hold" if count == 0 else "go"
                self.write("stage-6.json", memo)
                self.rehash()
                if accepted:
                    validate_target_assessment_pack(self.bundle)
                else:
                    with self.assertRaisesRegex(ValueError, "GENETIC_DEPENDENCE"):
                        validate_target_assessment_pack(self.bundle)
        data = self.read("stage-2.json")
        data["data"]["independent_support_count"] = 0
        data["data"]["support_record_ids"] = []
        self.write("stage-2.json", data)
        memo = self.read("stage-6.json")
        memo["data"]["decision"] = "hold"
        self.write("stage-6.json", memo)
        self.rehash()
        validate_target_assessment_pack(self.bundle)
        memo["data"]["decision"] = "go"
        self.write("stage-6.json", memo)
        self.rehash()
        with self.assertRaisesRegex(ValueError, "GENETIC_DEPENDENCE"):
            validate_target_assessment_pack(self.bundle)

    def test_transitive_source_dependency(self):
        data = self.read("snapshots.json")
        data["sources"][1]["cohorts"] = ["synthetic-other-cohort"]
        data["sources"][1]["dependency_groups"].append("synthetic-second-dependency")
        data["sources"][2]["cohorts"] = ["synthetic-third-cohort"]
        data["sources"][2]["dependency_groups"] = ["synthetic-second-dependency"]
        third = dict(data["sources"][0]["records"][0], id="synthetic-third-genetic-record")
        data["sources"][2]["records"] = [third]
        self.write("snapshots.json", data)
        genetics = self.read("stage-2.json")
        genetics["data"]["support_record_ids"].append(third["id"])
        genetics["data"]["observations"][2].update(status="recorded", record_ids=[third["id"]])
        genetics["data"]["independent_support_count"] = 2
        self.write("stage-2.json", genetics)
        self.rehash()
        with self.assertRaisesRegex(ValueError, "GENETIC_DEPENDENCE"):
            validate_target_assessment_pack(self.bundle)
        genetics["data"]["independent_support_count"] = 1
        self.write("stage-2.json", genetics)
        self.rehash()
        validate_target_assessment_pack(self.bundle)

    def test_unknown_and_distinct_cohorts(self):
        data = self.read("snapshots.json")
        for source in data["sources"][:2]:
            source["cohorts"] = []
            source["dependency_groups"] = []
        genetics = self.read("stage-2.json")
        genetics["data"]["independent_support_count"] = 2
        self.write("stage-2.json", genetics)
        self.write("snapshots.json", data)
        self.rehash()
        with self.assertRaisesRegex(ValueError, "GENETIC_DEPENDENCE"):
            validate_target_assessment_pack(self.bundle)
        for index, source in enumerate(data["sources"][:2]):
            source["cohorts"] = [f"synthetic-independent-{index}"]
        self.write("snapshots.json", data)
        self.rehash()
        validate_target_assessment_pack(self.bundle)

    def test_expression_context_edges(self):
        data = self.read("snapshots.json")
        fields = data["sources"][5]["records"][0]["context"]
        for value, accepted in ((0, False), (1, True), (-1, False), (True, False), ("1", False), (None, False)):
            fields["donor_count"] = value
            self.write("snapshots.json", data)
            self.rehash()
            if accepted:
                validate_target_assessment_pack(self.bundle)
            else:
                with self.assertRaisesRegex(ValueError, "EXPRESSION_CONTEXT"):
                    validate_target_assessment_pack(self.bundle)
        fields["donor_count"] = 1
        for key in ("tissue", "cell_state", "assay", "unit", "normalisation"):
            original = fields[key]
            fields[key] = ""
            self.write("snapshots.json", data)
            self.rehash()
            with self.assertRaisesRegex(ValueError, "EXPRESSION_CONTEXT"):
                validate_target_assessment_pack(self.bundle)
            fields[key] = original

    def test_explicit_direction_rationale(self):
        memo = self.read("stage-6.json")
        memo["data"]["modality"] = "activation"
        for rationale in (None, {}, {"text": "", "evidence": ["ot-1", "gwas-1"]},
                          {"text": "Synthetic context-specific hypothesis", "evidence": ["ot-1", "gwas-1"]}):
            memo["data"]["direction_rationale"] = rationale
            self.write("stage-6.json", memo)
            self.rehash()
            if rationale and rationale["text"]:
                validate_target_assessment_pack(self.bundle)
            else:
                with self.assertRaisesRegex(ValueError, "MODALITY_DIRECTION"):
                    validate_target_assessment_pack(self.bundle)

    def test_liability_decision_edges(self):
        safety = self.read("stage-5.json")
        for decision, severity, status, accepted in (
            ("go", "critical", "closed", True), ("hold", "critical", "open", True),
            ("no-go", "critical", "open", True), ("go", "major", "open", True),
            ("go", "critical", "open", False), ("go", "critical", "unknown", False),
        ):
            safety["data"]["liabilities"][0].update(severity=severity, status=status)
            self.write("stage-5.json", safety)
            memo = self.read("stage-6.json")
            memo["data"]["decision"] = decision
            self.write("stage-6.json", memo)
            self.rehash()
            if accepted:
                validate_target_assessment_pack(self.bundle)
            else:
                with self.assertRaisesRegex(ValueError, "CRITICAL_LIABILITY|PACK_FORMAT"):
                    validate_target_assessment_pack(self.bundle)

    def test_potency_edges_and_normalisation(self):
        stage = self.read("stage-4.json")
        for groups, accepted in (([], True), ([{"record_ids": [], "normalisation": None}], False),
                                 ([{"record_ids": ["chembl-1"], "normalisation": None}], True)):
            stage["data"]["potency_groups"] = groups
            self.write("stage-4.json", stage)
            self.rehash()
            if accepted:
                validate_target_assessment_pack(self.bundle)
            else:
                with self.assertRaisesRegex(ValueError, "POTENCY_MIXING"):
                    validate_target_assessment_pack(self.bundle)
        stage["data"]["potency_groups"] = [{
            "record_ids": ["chembl-1", "pubchem-1"],
            "normalisation": {"rationale": "Synthetic assay model for review only",
                              "assay": "synthetic-common-endpoint", "unit": "nM",
                              "values": {"chembl-1": 0, "pubchem-1": 5}},
        }]
        self.write("stage-4.json", stage)
        self.rehash()
        validate_target_assessment_pack(self.bundle)
        stage["data"]["potency_groups"][0]["normalisation"]["values"]["chembl-1"] = -1
        self.write("stage-4.json", stage)
        self.rehash()
        with self.assertRaisesRegex(ValueError, "POTENCY_MIXING"):
            validate_target_assessment_pack(self.bundle)

    def test_potency_types_units_and_invalid_values(self):
        data = self.read("snapshots.json")
        source = next(s for s in data["sources"] if s["id"] == "chembl")
        potency = source["records"][0]["potency"]
        for value, accepted in ((0, True), (1, True), (-1, False), (True, False), ("1", False),
                                (None, False), (10 ** 400, False)):
            potency["value"] = value
            self.write("snapshots.json", data)
            self.rehash()
            if accepted:
                validate_target_assessment_pack(self.bundle)
            else:
                with self.assertRaisesRegex(ValueError, "POTENCY_MIXING"):
                    validate_target_assessment_pack(self.bundle)
        potency["value"] = 1
        for key in ("assay", "unit"):
            original = potency[key]
            for value in ("", None, []):
                potency[key] = value
                self.write("snapshots.json", data)
                self.rehash()
                with self.assertRaisesRegex(ValueError, "POTENCY_MIXING"):
                    validate_target_assessment_pack(self.bundle)
            potency[key] = original
        self.write("snapshots.json", data)
        stage = self.read("stage-4.json")
        stage["data"]["potency_groups"] = [{"record_ids": ["chembl-1", "pubchem-1"], "normalisation": None}]
        pubchem = next(s for s in data["sources"] if s["id"] == "pubchem")
        # An equal assay with different units still cannot be pooled.
        pubchem["records"][0]["potency"]["assay"] = "IC50"
        self.write("snapshots.json", data)
        self.write("stage-4.json", stage)
        self.rehash()
        with self.assertRaisesRegex(ValueError, "POTENCY_MIXING"):
            validate_target_assessment_pack(self.bundle)

    def test_hash_order_and_path_refusals(self):
        data = self.read("dossier.json")
        original = json.loads(json.dumps(data))
        for value in ("", "../outside.json", "/outside.json", "./snapshots.json"):
            data["snapshots"]["path"] = value
            self.write("dossier.json", data)
            with self.assertRaisesRegex(ValueError, "PACK_PATH"):
                validate_target_assessment_pack(self.bundle)
        data = original
        data["stages"].reverse()
        self.write("dossier.json", data)
        with self.assertRaisesRegex(ValueError, "STAGE_ORDER"):
            validate_target_assessment_pack(self.bundle)
        data["stages"].reverse()
        self.write("dossier.json", data)
        (self.bundle / "snapshots.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "PACK_HASH"):
            validate_target_assessment_pack(self.bundle)

    def test_malformed_and_missing_inputs_are_labelled(self):
        for content in ("", "null", "[]", "{", '{"schema": NaN}',
                        '{"schema": 1, "schema": 2}', '{"schema": 0}'):
            with self.subTest(content=content):
                (self.bundle / "dossier.json").write_text(content)
                with self.assertRaisesRegex(ValueError, "PACK_"):
                    validate_target_assessment_pack(self.bundle)
                result = self.cli()
                self.assertEqual(1, result.returncode)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual("refused", json.loads(result.stdout)["status"])
        result = self.cli(self.bundle / "missing")
        self.assertEqual(1, result.returncode)
        self.assertEqual("PACK_INPUT", json.loads(result.stdout)["finding"])

    def test_non_regular_artifacts_are_refused_before_open(self):
        target = self.bundle / "dossier.json"
        target.unlink()
        for kind in ("fifo", "directory"):
            with self.subTest(kind=kind):
                if kind == "fifo":
                    os.mkfifo(target)
                else:
                    target.mkdir()
                try:
                    with patch.object(Path, "read_bytes", side_effect=AssertionError("non-regular input opened")):
                        with self.assertRaisesRegex(ValueError, "PACK_INPUT"):
                            validate_target_assessment_pack(self.bundle)
                    result = self.cli()
                    self.assertEqual(1, result.returncode, result.stderr)
                    self.assertEqual("PACK_INPUT", json.loads(result.stdout)["finding"])
                finally:
                    target.rmdir() if kind == "directory" else target.unlink()

    def test_artifact_size_limit_and_same_bytes(self):
        target = self.bundle / "dossier.json"
        limit = 64 * 1024 * 1024
        reference = {"path": "dossier.json", "sha256": None}
        for size in (0, 1, limit, limit + 1):
            with self.subTest(size=size):
                content = b"{" if size == 1 else (b"{}" + b" " * (size - 2))[:size]
                target.write_bytes(content)
                bundle = _Bundle(self.bundle)
                if size > limit:
                    with patch.object(Path, "read_bytes", side_effect=AssertionError("oversized input opened")):
                        with self.assertRaisesRegex(ValueError, "PACK_INPUT"):
                            bundle.read(reference)
                    result = self.cli()
                    self.assertEqual(1, result.returncode, result.stderr)
                    self.assertEqual("PACK_INPUT", json.loads(result.stdout)["finding"])
                elif size < 2:
                    with self.assertRaisesRegex(ValueError, "PACK_FORMAT"):
                        bundle.read(reference)
                else:
                    self.assertEqual({}, bundle.read(reference))
                    self.assertEqual(hashlib.sha256(content).hexdigest(), bundle.reads["dossier.json"])
        target.write_bytes(b"{}")
        with patch.object(Path, "read_bytes", return_value=b" " * (limit + 1)):
            with self.assertRaisesRegex(ValueError, "PACK_INPUT"):
                _Bundle(self.bundle).read(reference)

    def test_changed_artifact_types_and_size_are_refused_before_open(self):
        target = self.bundle / "dossier.json"
        reference = {"path": "dossier.json", "sha256": None}
        for kind in ("fifo", "directory", "oversized"):
            with self.subTest(kind=kind):
                target.write_bytes(b"{}")
                bundle = _Bundle(self.bundle)
                bundle.read(reference)
                target.unlink()
                if kind == "fifo":
                    os.mkfifo(target)
                elif kind == "directory":
                    target.mkdir()
                else:
                    with target.open("wb") as stream:
                        stream.truncate(64 * 1024 * 1024 + 1)
                try:
                    with patch.object(Path, "read_bytes", side_effect=AssertionError("changed unsafe input opened")):
                        with self.assertRaisesRegex(ValueError, "PACK_CHANGED"):
                            bundle.unchanged()
                finally:
                    target.rmdir() if kind == "directory" else target.unlink()

    def test_malformed_nested_records_are_labelled(self):
        cases = (
            ("snapshots.json", ("sources",), None),
            ("snapshots.json", ("sources",), []),
            ("snapshots.json", ("sources", 0), None),
            ("snapshots.json", ("sources", 0, "records"), {}),
            ("snapshots.json", ("sources", 0, "records", 0, "kind"), []),
            ("snapshots.json", ("sources", 0, "cohorts"), [None]),
            ("stage-2.json", ("data", "support_record_ids"), ["nonexistent"]),
            ("stage-2.json", ("data", "support_record_ids"), ["ot-1", "ot-1"]),
            ("stage-4.json", ("data", "potency_groups"), None),
            ("stage-5.json", ("data", "liabilities"), None),
            ("stage-6.json", ("data", "claims"), []),
            ("stage-6.json", ("data", "claims", 0, "kind"), []),
            ("stage-6.json", ("data", "next_experiment"), {}),
            ("stage-6.json", ("data", "decision"), []),
            ("claims.json", ("claims",), []),
            ("checkpoint.json", ("steps",), []),
        )
        for filename, keys, value in cases:
            with self.subTest(file=filename, keys=keys):
                original = self.read(filename)
                data = json.loads(json.dumps(original))
                parent = data
                for key in keys[:-1]:
                    parent = parent[key]
                parent[keys[-1]] = value
                self.write(filename, data)
                self.rehash()
                with self.assertRaisesRegex(ValueError, r"^[A-Z_]+: "):
                    validate_target_assessment_pack(self.bundle)
                result = self.cli()
                self.assertEqual(1, result.returncode)
                self.assertNotIn("Traceback", result.stderr)
                self.write(filename, original)
                self.rehash()

    def test_symlink_and_broken_handoff(self):
        data = self.read("dossier.json")
        (self.bundle / "alias.json").symlink_to("snapshots.json")
        data["snapshots"]["path"] = "alias.json"
        self.write("dossier.json", data)
        with self.assertRaisesRegex(ValueError, "PACK_PATH"):
            validate_target_assessment_pack(self.bundle)
        data["snapshots"]["path"] = "snapshots.json"
        self.write("dossier.json", data)
        stage = self.read("stage-2.json")
        stage["inputs"] = []
        self.write("stage-2.json", stage)
        self.rehash()
        with self.assertRaisesRegex(ValueError, "STAGE_HANDOFF"):
            validate_target_assessment_pack(self.bundle)

    def test_concurrent_validation_and_changed_input(self):
        before = {p.name: p.read_bytes() for p in self.bundle.iterdir()}
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(validate_target_assessment_pack, [self.bundle, self.bundle]))
        self.assertEqual(results[0], results[1])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.bundle.iterdir()})
        original_read = Path.read_bytes

        def edit_during_read(path):
            if path == self.bundle / "claims.json":
                (self.bundle / "snapshots.json").write_bytes(b"{}")
            return original_read(path)

        with patch.object(Path, "read_bytes", edit_during_read):
            with self.assertRaisesRegex(ValueError, "PACK_CHANGED"):
                validate_target_assessment_pack(self.bundle)

    def test_pack_contract_and_frozen_tasks(self):
        from codex_science.reference_contract import validate_reference_index
        from codex_science.skill_maturity import evaluate_skill

        skill = ROOT / "authored-skills/workflow-target-assessment-dossier"
        self.assertEqual([], validate_reference_index(skill, strict=True)["findings"])
        quality = evaluate_skill(ROOT, skill)
        self.assertEqual("L4", quality["computed_maturity"])
        self.assertEqual([], quality["reasons"])
        plan = json.loads((skill / "references/plan.json").read_text())
        self.assertEqual([f"stage-{i:02d}" for i in range(1, 7)],
                         [step["id"] for step in plan["plan"]])
        for step in plan["plan"]:
            self.assertEqual({"id", "description", "status"}, set(step))
            self.assertEqual("pending", step["status"])
        tasks = json.loads((ROOT / "benchmarks/workflow-target-assessment-dossier/tasks.json").read_text())
        for task in tasks["tasks"]:
            self.assertTrue(task["synthetic"])
            self.assertTrue(task["acceptance_criteria"])
            self.assertEqual(0, task["budget"]["network_calls"])
            self.assertEqual(0, task["budget"]["gpu_seconds"])
            self.assertTrue((ROOT / task["fixture"]).is_file())


if __name__ == "__main__":
    unittest.main()
