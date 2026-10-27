import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "statistical-inference-experimental-design" / "input.json"
RUNNER_PATH = ROOT / "scripts" / "validate_research_design.py"
_SPEC = importlib.util.spec_from_file_location("validate_research_design_acceptance", RUNNER_PATH)
assert _SPEC is not None and _SPEC.loader is not None
runner = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(runner)

SEEDED_FAILURE_TESTS = {
    "pseudoreplication": "test_detects_pseudoreplication",
    "optional-stopping": "test_detects_optional_stopping",
    "uncontrolled-multiplicity": "test_detects_uncontrolled_multiplicity",
    "causal-identification-gap": "test_detects_causal_identification_gap",
}


class StatisticalInferenceExperimentalDesignAcceptanceTests(unittest.TestCase):
    def run_design(self, design: dict) -> tuple[int, dict]:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "input.json"
            output = root / "output.json"
            source.write_text(json.dumps(design), encoding="utf-8")
            with patch.object(sys, "argv", [str(RUNNER_PATH), str(source), "--output", str(output), "--require-clean"]):
                exit_code = runner.main()
            return exit_code, json.loads(output.read_text(encoding="utf-8"))

    def test_acceptance_fixture_passes_design_audit(self) -> None:
        design = json.loads(FIXTURE.read_text(encoding="utf-8"))
        exit_code, result = self.run_design(design)
        self.assertEqual(0, exit_code)
        self.assertEqual("passed", result["audit_status"])
        self.assertEqual([], result["audit_findings"])
        self.assertEqual(64, len(result["fingerprint"]))

    def assert_seeded_failure(self, mutate, fragment: str) -> None:
        design = json.loads(FIXTURE.read_text(encoding="utf-8"))
        mutate(design)
        exit_code, result = self.run_design(design)
        self.assertEqual(1, exit_code)
        messages = [item["message"] for item in result["audit_findings"]]
        self.assertTrue(any(fragment in message for message in messages), messages)

    def test_detects_pseudoreplication(self) -> None:
        self.assert_seeded_failure(
            lambda design: design.update(
                experimental_unit="animal",
                observational_unit="cell",
                analysis={"method": "cell-level difference in means", "aggregation_unit": "cell"},
            ),
            "nested below the experimental unit",
        )

    def test_detects_optional_stopping(self) -> None:
        self.assert_seeded_failure(
            lambda design: design.update(stopping={"planned_looks": 4}),
            "Repeated outcome looks lack an alpha-spending",
        )

    def test_detects_uncontrolled_multiplicity(self) -> None:
        def add_endpoint(design: dict) -> None:
            design["primary_endpoints"].append(
                {"id": "secondary-primary", "decision_threshold": "report estimate"}
            )
            design["multiplicity"] = {"method": "none", "family_size": 2}

        self.assert_seeded_failure(
            add_endpoint,
            "Multiple primary hypotheses are declared without a multiplicity strategy",
        )

    def test_detects_causal_identification_gap(self) -> None:
        def declare_causal(design: dict) -> None:
            design["estimand"]["causal"] = True

        self.assert_seeded_failure(
            declare_causal,
            "A causal estimand is declared without explicit identification assumptions",
        )

    def test_quality_seeded_failures_have_matching_tests(self) -> None:
        quality = json.loads(
            (ROOT / "authored-skills" / "statistical-inference-experimental-design" / "quality.json").read_text(encoding="utf-8")
        )
        self.assertEqual(set(quality["seeded_failures"]), set(SEEDED_FAILURE_TESTS))
        for method_name in SEEDED_FAILURE_TESTS.values():
            with self.subTest(method=method_name):
                self.assertTrue(callable(getattr(self, method_name, None)))


if __name__ == "__main__":
    unittest.main()
