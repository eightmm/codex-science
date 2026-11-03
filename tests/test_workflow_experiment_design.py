"""Offline synthetic acceptance and refusal cases for the workflow pack."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codex_science.experiment_design_pack import STAGES, validate_experiment_design_pack


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/workflow-experiment-design"
RUNNER = ROOT / "scripts/validate_experiment_design_pack.py"
CALL_TIMEOUT = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "60"))
CASES = json.loads((EXAMPLE / "negative-cases.json").read_text())["cases"]


class ExperimentDesignPackTests(unittest.TestCase):
    def cli(self, path: Path, mode: str = "preregister") -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(RUNNER), str(path), "--mode", mode], capture_output=True, text=True, timeout=CALL_TIMEOUT)

    def assert_case(self, code: str) -> None:
        case = next(case for case in CASES if case["id"] == code)
        result = self.cli(EXAMPLE / case["input"], case["mode"])
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn(code + ":", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual("", result.stdout)

    def altered(self, record_name: str, mutate, *, mode: str = "preregister") -> subprocess.CompletedProcess:
        # Each call has its own directory; parallel tests cannot rewrite fixtures.
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for source in EXAMPLE.glob("*.json"):
                (directory / source.name).write_bytes(source.read_bytes())
            bundle_path = directory / ("audit.json" if mode == "audit" else "preregister.json")
            bundle = json.loads(bundle_path.read_text())
            if record_name == "bundle":
                mutate(bundle)
            else:
                target = directory / bundle[record_name]["path"]
                record = json.loads(target.read_text())
                mutate(record)
                raw = (json.dumps(record, sort_keys=True) + "\n").encode()
                target.write_bytes(raw)
                bundle[record_name]["sha256"] = hashlib.sha256(raw).hexdigest()
                if record_name in ("question", "power", "randomisation", "analysis_plan", "controls"):
                    hand_path = directory / bundle["handoff"]["path"]
                    hand = json.loads(hand_path.read_text())
                    hand["inputs"][record_name] = copy.deepcopy(bundle[record_name])
                    if record_name == "analysis_plan":
                        hand["analysis_plan"] = copy.deepcopy(bundle[record_name])
                    raw_hand = (json.dumps(hand, sort_keys=True) + "\n").encode()
                    hand_path.write_bytes(raw_hand)
                    bundle["handoff"]["sha256"] = hashlib.sha256(raw_hand).hexdigest()
            bundle_path.write_text(json.dumps(bundle))
            return self.cli(bundle_path, mode)

    def test_synthetic_preregistration_and_finished_audit(self) -> None:
        for name, mode in (("preregister", "preregister"), ("computational-preregister", "preregister"), ("audit", "audit")):
            with self.subTest(mode=mode):
                result = self.cli(EXAMPLE / f"{name}.json", mode)
                self.assertEqual(0, result.returncode, result.stderr)
                actual = json.loads(result.stdout)
                expected = json.loads((EXAMPLE / f"expected-{name}.json").read_text())
                self.assertEqual(expected, actual)
                self.assertEqual(list(STAGES), actual["stage_ids"])
                self.assertGreater(actual["power"]["achieved_power"], 0.8)
                self.assertEqual(120, actual["power"]["planned_units"])
                self.assertEqual(240, actual["power"]["planned_cost"])

    def test_existing_statistics_runtime_smoke_keeps_independent_units(self) -> None:
        # This tiny synthetic calculation is independent of the planning fixture;
        # it demonstrates runtime composition, not achievement of planned power.
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "statistical-analysis.json"
            result = subprocess.run([sys.executable, str(ROOT / "scripts/run_statistical_analysis.py"), str(EXAMPLE / "statistical-input.json"), "--output", str(output)], capture_output=True, text=True, timeout=CALL_TIMEOUT)
            self.assertEqual(0, result.returncode, result.stderr)
            receipt = json.loads(output.read_text())
            self.assertEqual("completed", receipt["status"])
            self.assertEqual(1729, receipt["seed"])
            self.assertEqual(0, receipt["effect"]["estimate"])
            self.assertEqual(1, receipt["test"]["p_value"])

    def test_validation_is_repeatable_and_does_not_write_inputs(self) -> None:
        before = {path.name: path.read_bytes() for path in EXAMPLE.iterdir() if path.is_file()}
        first = validate_experiment_design_pack(EXAMPLE / "audit.json", mode="audit")
        second = validate_experiment_design_pack(EXAMPLE / "audit.json", mode="audit")
        self.assertEqual(first, second)
        self.assertEqual(before, {path.name: path.read_bytes() for path in EXAMPLE.iterdir() if path.is_file()})

    def test_refuses_plan_hash_mismatch(self) -> None:
        self.assert_case("plan-hash-mismatch")

    def test_refuses_pseudoreplication(self) -> None:
        self.assert_case("pseudoreplication")

    def test_refuses_own_result_effect(self) -> None:
        self.assert_case("own-result-effect")

    def test_refuses_unlabelled_outcome_or_threshold(self) -> None:
        self.assert_case("unlabelled-deviation")

    def test_refuses_ignored_multiplicity(self) -> None:
        self.assert_case("multiplicity-ignored")

    def test_refuses_unaccounted_allocation_or_attrition(self) -> None:
        self.assert_case("allocation-attrition")

    def test_refuses_absent_sequential_stopping_rule(self) -> None:
        self.assert_case("stopping-rule-absent")

    def test_refuses_omitted_negative_or_null_result(self) -> None:
        self.assert_case("omitted-result")

    def test_every_detected_deviation_needs_its_own_exploratory_label(self) -> None:
        result = self.cli(EXAMPLE / "exploratory-audit.json", "audit")
        self.assertEqual(0, result.returncode, result.stderr)
        deviations = json.loads(result.stdout)["deviations"]
        self.assertEqual({"changed-outcome", "changed-threshold", "added-comparison", "dropped-comparison", "post-hoc-exclusion"}, {row["kind"] for row in deviations})
        for index in range(len(deviations)):
            with self.subTest(deviation=deviations[index]):
                with tempfile.TemporaryDirectory() as temporary:
                    directory = Path(temporary)
                    for source in EXAMPLE.glob("*.json"):
                        (directory / source.name).write_bytes(source.read_bytes())
                    bundle = json.loads((directory / "exploratory-audit.json").read_text())
                    analysis_path = directory / bundle["analysis"]["path"]
                    analysis = json.loads(analysis_path.read_text())
                    target = deviations[index]
                    analysis["deviations"] = [row for row in analysis["deviations"] if (row["kind"], row["target"]) != (target["kind"], target["target"])]
                    raw = json.dumps(analysis).encode()
                    analysis_path.write_bytes(raw)
                    bundle["analysis"]["sha256"] = hashlib.sha256(raw).hexdigest()
                    (directory / "exploratory-audit.json").write_text(json.dumps(bundle))
                    refused = self.cli(directory / "exploratory-audit.json", "audit")
                    self.assertEqual(1, refused.returncode)
                    self.assertIn("unlabelled-deviation:", refused.stderr)

    def test_family_threshold_and_power_edges(self) -> None:
        def threshold(value):
            return lambda plan: plan["primary_family"][0].update(threshold=value)
        for value in (0.025, 0.025001, 0, "bad", None, True):
            with self.subTest(threshold=value):
                result = self.altered("analysis_plan", threshold(value))
                self.assertEqual(0 if value == 0.025 else 1, result.returncode, result.stderr)
        for value in ([], None, ["bad"]):
            with self.subTest(family=value):
                self.assertEqual(1, self.altered("analysis_plan", lambda plan: plan.update(primary_family=value)).returncode)
        def singleton(plan):
            plan["primary_family"] = plan["primary_family"][:1]
            plan["multiplicity"] = "none"
            plan["primary_family"][0]["threshold"] = plan["alpha"]
        self.assertEqual(0, self.altered("analysis_plan", singleton).returncode)
        for value in (0, 1, "", None, True):
            with self.subTest(alpha=value):
                self.assertEqual(1, self.altered("analysis_plan", lambda plan: plan.update(alpha=value)).returncode)
        for field in ("assumed_effect", "variance", "target_power"):
            for value in (0, "bad", None, True, float("nan"), float("inf")):
                with self.subTest(field=field, value=value):
                    self.assertEqual(1, self.altered("power", lambda power: power.update({field: value})).returncode)
        rejected = self.altered("power", lambda power: power.update(target_power=0.99999))
        self.assertIn("insufficient-power:", rejected.stderr)
        self.assertEqual(1, self.altered("power", lambda power: power.update(target_power=1)).returncode)
        exact = validate_experiment_design_pack(EXAMPLE / "preregister.json")["power"]["achieved_power"]
        self.assertEqual(0, self.altered("power", lambda power: power.update(target_power=exact)).returncode)

    def test_allocation_attrition_cost_seed_and_blinding_edges(self) -> None:
        for value in (0, 0.2, 0.20001, 1, -0.1, "bad", None, True):
            with self.subTest(attrition=value):
                result = self.altered("power", lambda power: power["arms"][0].update(attrition=value))
                self.assertEqual(0 if type(value) in (int, float) and value in (0, 0.2) else 1, result.returncode, result.stderr)
        mismatch = self.altered("power", lambda power: power["arms"][1].update(allocation=1))
        self.assertIn("allocation-attrition:", mismatch.stderr)
        for field in ("allocation", "required_analyzable", "planned", "cost_per_unit"):
            for value in (0, "bad", None, True):
                with self.subTest(field=field, value=value):
                    result = self.altered("power", lambda power: power["arms"][0].update({field: value}))
                    self.assertEqual(0 if field == "cost_per_unit" and type(value) is int and value == 0 else 1, result.returncode, result.stderr)
        for value in (0, 1729, -1, "bad", None, True):
            with self.subTest(seed=value):
                result = self.altered("randomisation", lambda assignment: assignment.update(assignment_seed=value, blinding_seed=value))
                self.assertEqual(0 if type(value) is int and value >= 0 else 1, result.returncode, result.stderr)
        self.assertEqual(1, self.altered("randomisation", lambda assignment: assignment.update(blinding="")).returncode)

    def test_failed_controls_and_missing_results_remain_distinct(self) -> None:
        for removed in range(4):
            with self.subTest(removed=removed):
                result = self.altered("analysis", lambda analysis: analysis["reported_results"].pop(removed), mode="audit")
                self.assertEqual(1, result.returncode)
                self.assertIn("omitted-result:", result.stderr)
        omitted = self.altered("results", lambda results: results["results"].pop(), mode="audit")
        self.assertIn("incomplete-results:", omitted.stderr)

    def test_sequential_rules_and_other_post_hoc_rules(self) -> None:
        sequential = self.altered("analysis_plan", lambda plan: plan.update(sequential=True, sequential_error_control="prespecified external alpha-spending schedule"))
        self.assertEqual(0, sequential.returncode, sequential.stderr)
        missing = self.altered("analysis_plan", lambda plan: plan.update(sequential=True, sequential_error_control=""))
        self.assertEqual(1, missing.returncode)
        for field in ("method", "missing_data_rule", "stopping_rule", "multiplicity"):
            with self.subTest(rule=field):
                value = "none" if field == "multiplicity" else "post-hoc changed rule"
                def change(analysis):
                    analysis[field] = value
                refused = self.altered("analysis", change, mode="audit")
                self.assertIn("unlabelled-deviation:", refused.stderr)
                def label(analysis):
                    change(analysis)
                    analysis["deviations"] = [{"kind": "changed-analysis-rule", "target": field, "label": "exploratory", "reason": "Synthetic sensitivity only"}]
                accepted = self.altered("analysis", label, mode="audit")
                self.assertEqual(0, accepted.returncode, accepted.stderr)

    def test_inference_boundaries_are_refusals(self) -> None:
        for evidence, assertion in (("association", "causality"), ("numerical-agreement", "physical-validity"), ("numerical-agreement", "clinical-validity"), ("unavailable", "negative-evidence"), ("review-approval", "truth")):
            with self.subTest(evidence=evidence):
                result = self.altered("question", lambda question: question.update(claims=[{"evidence": evidence, "assertion": assertion}]))
                self.assertEqual(1, result.returncode)
                self.assertIn("inference-boundary:", result.stderr)

    def test_review_timing_and_modes(self) -> None:
        for change, code in (({"reviewer": "fixture-producer"}, "independent-review-required"), ({"status": "reviewed"}, "independent-review-required"), ({"handed_off_at": "2026-01-04T00:00:00Z"}, "stage-order"), ({"handed_off_at": "bad"}, "invalid-record")):
            with self.subTest(change=change):
                result = self.altered("handoff", lambda hand: hand.update(change), mode="audit")
                self.assertEqual(1, result.returncode)
                self.assertIn(code + ":", result.stderr)
        equal = self.altered("bundle", lambda bundle: bundle.update(data_collection_started_at="2026-01-01T01:00:00Z"), mode="audit")
        self.assertIn("stage-order:", equal.stderr)
        self.assertEqual(0, self.altered("handoff", lambda hand: hand.update(handed_off_at="2026-01-01T00:00:00Z")).returncode)
        self.assertEqual(1, self.cli(EXAMPLE / "audit.json").returncode)
        with self.assertRaisesRegex(ValueError, "invalid-mode:"):
            validate_experiment_design_pack(EXAMPLE / "preregister.json", mode="bad")

    def test_hash_paths_malformed_inputs_and_cli_help(self) -> None:
        for value in ("", "../outside.json", "/outside.json", "missing.json"):
            with self.subTest(path=value):
                result = self.altered("bundle", lambda bundle: bundle["power"].update(path=value))
                self.assertEqual(1, result.returncode)
                self.assertNotIn("Traceback", result.stderr)
        mismatch = self.altered("bundle", lambda bundle: bundle["power"].update(sha256="0" * 64))
        self.assertIn("artifact-hash-mismatch:", mismatch.stderr)
        for digest in ("", "0" * 63, "0" * 65, "z" * 64, 0, None):
            with self.subTest(digest=digest):
                self.assertEqual(1, self.altered("bundle", lambda bundle: bundle["power"].update(sha256=digest)).returncode)
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            bundle = json.loads((EXAMPLE / "preregister.json").read_text())
            (directory / "escape.json").symlink_to(EXAMPLE / "question.json")
            bundle["question"]["path"] = "escape.json"
            path = directory / "pack.json"
            path.write_text(json.dumps(bundle))
            self.assertIn("unavailable-artifact:", self.cli(path).stderr)
        with tempfile.TemporaryDirectory() as temporary:
            malformed = Path(temporary) / "malformed.json"
            for raw in ("", "0", "[]", "{", '{"schema": null}'):
                malformed.write_text(raw)
                result = self.cli(malformed)
                self.assertEqual(1, result.returncode)
                self.assertNotIn("Traceback", result.stderr)
        help_result = subprocess.run([sys.executable, str(RUNNER), "--help"], capture_output=True, text=True, timeout=CALL_TIMEOUT)
        self.assertEqual(0, help_result.returncode)
        self.assertIn("--mode", help_result.stdout)

    def test_quality_benchmark_and_plan_use_existing_contracts(self) -> None:
        skill = ROOT / "authored-skills/workflow-experiment-design"
        quality = json.loads((skill / "quality.json").read_text())
        self.assertEqual("L4", quality["declared_maturity"])
        self.assertEqual({row["id"] for row in CASES}, set(quality["seeded_failures"]))
        for section in ("Decision contract", "Reference usage", "Workflow", "Outputs", "Boundaries"):
            self.assertIn(f"## {section}", (skill / "SKILL.md").read_text())
        plan = json.loads((skill / "references/plan.json").read_text())["plan"]
        self.assertEqual(list(STAGES), [step["id"] for step in plan])
        for step in plan:
            self.assertEqual({"id", "description", "status"}, set(step))
            self.assertEqual("pending", step["status"])
        tasks = json.loads((ROOT / "benchmarks/workflow-experiment-design/tasks.json").read_text())["tasks"]
        self.assertEqual({row["id"] for row in CASES}, {row["id"] for row in tasks if row["expected"] == "refuse"})
        self.assertTrue(all(row["budget"]["network_calls"] == 0 for row in tasks))


if __name__ == "__main__":
    unittest.main()
