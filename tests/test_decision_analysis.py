import copy
import json
import math
import subprocess
import tempfile
import unittest
from pathlib import Path

from codex_science.decision_analysis import (
    render_decision_analysis,
    review_decision_analysis,
    run_decision_analysis,
    validate_decision_analysis,
)
from codex_science.safe_expression import canonical_sha256
from codex_science.quantitative_sidecars import (
    empty_quantitative_sidecars,
    review_quantitative_sidecars,
    validate_quantitative_sidecar,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "statistical-decision-analysis" / "input.json"


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def criteria_by_name(receipt: dict) -> dict[str, dict]:
    return {item["criterion"]: item for item in receipt["criterion_results"]}


def scores_by_action(result: dict) -> dict[str, float]:
    return {item["action"]: item["value"] for item in result["scores"]}


class DecisionAnalysisTests(unittest.TestCase):
    def test_loss_fixture_covers_criteria_information_and_sensitivity(self) -> None:
        receipt = run_decision_analysis(load_fixture())
        validate_decision_analysis(receipt)
        criteria = criteria_by_name(receipt)

        bayes = criteria["bayes-risk"]
        self.assertEqual(["risky", "safe"], bayes["optimal_actions"])
        self.assertEqual(
            {"dominated": 6.8, "risky": 4.0, "safe": 4.0},
            scores_by_action(bayes),
        )
        self.assertEqual(["safe"], criteria["minimax-loss"]["optimal_actions"])
        self.assertEqual(["safe"], criteria["minimax-regret"]["optimal_actions"])
        self.assertEqual(
            [{"action": "dominated", "dominated_by": ["safe"]}],
            receipt["dominated_actions"],
        )

        information = receipt["information_value"]
        self.assertAlmostEqual(1.6, information["perfect_information_value"])
        self.assertAlmostEqual(2.4, information["evpi"])
        experiment = information["experiments"][0]
        self.assertAlmostEqual(1.44, experiment["gross_evsi"])
        self.assertAlmostEqual(0.94, experiment["net_evsi"])
        self.assertEqual("worth-cost", experiment["decision"])
        policy = {item["outcome"]: item for item in experiment["outcome_policy"]}
        self.assertAlmostEqual(0.56, policy["signal-1"]["probability"])
        self.assertAlmostEqual(0.44, policy["signal-2"]["probability"])
        self.assertEqual(["risky"], policy["signal-1"]["optimal_actions"])
        self.assertEqual(["safe"], policy["signal-2"]["optimal_actions"])

        sensitivity = receipt["sensitivity"]
        self.assertTrue(sensitivity["decision_changes_within_range"])
        self.assertEqual(
            [
                {"minimum": 0.0, "maximum": 0.6, "optimal_actions": ["safe"]},
                {"minimum": 0.6, "maximum": 1.0, "optimal_actions": ["risky"]},
            ],
            sensitivity["regions"],
        )
        self.assertEqual([0.0, 0.6, 1.0], [item["prior"] for item in sensitivity["boundaries"]])
        self.assertEqual(["risky", "safe"], sensitivity["boundaries"][1]["optimal_actions"])
        self.assertEqual("decision-sensitive", receipt["status"])
        self.assertEqual({"decision-sensitive"}, {item["code"] for item in review_decision_analysis(receipt)})

    def test_uninformative_and_unreachable_signals_do_not_fabricate_value(self) -> None:
        uninformative = load_fixture()
        for outcome in uninformative["experiments"][0]["outcomes"]:
            outcome["likelihoods"] = {"mechanism-1": 0.5, "mechanism-2": 0.5}
        receipt = run_decision_analysis(uninformative)
        experiment = receipt["information_value"]["experiments"][0]
        self.assertAlmostEqual(0.0, experiment["gross_evsi"])
        self.assertAlmostEqual(-0.5, experiment["net_evsi"])
        self.assertEqual("not-worth-cost", experiment["decision"])

        rare_but_reachable = load_fixture()
        outcomes = rare_but_reachable["experiments"][0]["outcomes"]
        outcomes[0]["id"] = "common"
        outcomes[0]["likelihoods"] = {
            "mechanism-1": 1.0 - 1e-12,
            "mechanism-2": 1.0 - 1e-12,
        }
        outcomes[1]["id"] = "rare"
        outcomes[1]["likelihoods"] = {
            "mechanism-1": 1e-12,
            "mechanism-2": 1e-12,
        }
        receipt = run_decision_analysis(rare_but_reachable)
        policy = {
            item["outcome"]: item
            for item in receipt["information_value"]["experiments"][0]["outcome_policy"]
        }
        self.assertEqual("reachable", policy["rare"]["status"])
        self.assertAlmostEqual(1e-12, policy["rare"]["probability"])
        self.assertEqual({"mechanism-1": 0.6, "mechanism-2": 0.4}, policy["rare"]["posterior"])

        unreachable = load_fixture()
        outcomes = unreachable["experiments"][0]["outcomes"]
        outcomes[0]["likelihoods"] = {"mechanism-1": 1.0, "mechanism-2": 1.0}
        outcomes[1]["likelihoods"] = {"mechanism-1": 0.0, "mechanism-2": 0.0}
        receipt = run_decision_analysis(unreachable)
        policy = {item["outcome"]: item for item in receipt["information_value"]["experiments"][0]["outcome_policy"]}
        self.assertEqual("unreachable", policy["signal-2"]["status"])
        self.assertIsNone(policy["signal-2"]["posterior"])
        self.assertEqual([], policy["signal-2"]["optimal_actions"])
        self.assertAlmostEqual(0.0, receipt["information_value"]["experiments"][0]["gross_evsi"])

    def test_utility_dual_and_risk_neutral_payoff_preserve_policy(self) -> None:
        loss = run_decision_analysis(load_fixture())

        utility_input = load_fixture()
        utility_input["criterion"] = "expected-utility"
        utility_input["criterion_rationale"] = "Cardinal utility is explicitly encoded."
        utility_input["scale"] = {
            "kind": "utility",
            "unit": "utility-point",
            "risk_attitude": "encoded-in-utility",
        }
        for cell in utility_input["values"]:
            cell["value"] = -cell["value"]
        utility = run_decision_analysis(utility_input)
        self.assertEqual(
            loss["recommendation"]["optimal_actions"],
            utility["recommendation"]["optimal_actions"],
        )
        self.assertAlmostEqual(loss["information_value"]["evpi"], utility["information_value"]["evpi"])
        self.assertAlmostEqual(
            loss["information_value"]["experiments"][0]["gross_evsi"],
            utility["information_value"]["experiments"][0]["gross_evsi"],
        )

        payoff_input = load_fixture()
        payoff_input["criterion"] = "expected-payoff"
        payoff_input["criterion_rationale"] = "Linear monetary value is accepted under risk neutrality."
        payoff_input["scale"] = {
            "kind": "payoff",
            "unit": "payoff-point",
            "risk_attitude": "risk-neutral",
        }
        for cell in payoff_input["values"]:
            cell["value"] = 10.0 - cell["value"]
        payoff = run_decision_analysis(payoff_input)
        self.assertEqual(loss["recommendation"]["optimal_actions"], payoff["recommendation"]["optimal_actions"])
        self.assertAlmostEqual(loss["information_value"]["evpi"], payoff["information_value"]["evpi"])

        payoff_input["scale"]["risk_attitude"] = "encoded-in-utility"
        with self.assertRaisesRegex(ValueError, "risk_attitude must be risk-neutral"):
            run_decision_analysis(payoff_input)

    def test_contract_rejects_incomplete_or_non_stochastic_inputs(self) -> None:
        incomplete = load_fixture()
        incomplete["values"].pop()
        with self.assertRaisesRegex(ValueError, "exactly one cell"):
            run_decision_analysis(incomplete)

        bad_prior = load_fixture()
        bad_prior["states"][0]["prior"] = 0.7
        with self.assertRaisesRegex(ValueError, "priors must sum to 1"):
            run_decision_analysis(bad_prior)

        bad_likelihood = load_fixture()
        bad_likelihood["experiments"][0]["outcomes"][0]["likelihoods"]["mechanism-1"] = 0.9
        with self.assertRaisesRegex(ValueError, "likelihoods for state mechanism-1 must sum to 1"):
            run_decision_analysis(bad_likelihood)

        near_normalized = load_fixture()
        for cell in near_normalized["values"]:
            cell["value"] = 1e12
        near_normalized["states"][0]["prior"] = 0.49377654070971555
        near_normalized["states"][1]["prior"] = 0.5062234594836474
        near_normalized["experiments"][0]["outcomes"][0]["likelihoods"] = {
            "mechanism-1": 0.49377654070971555,
            "mechanism-2": 0.49377654070971555,
        }
        near_normalized["experiments"][0]["outcomes"][1]["likelihoods"] = {
            "mechanism-1": 0.5062234594836474,
            "mechanism-2": 0.5062234594836474,
        }
        receipt = run_decision_analysis(near_normalized)
        validate_decision_analysis(receipt)
        normalized_outcomes = receipt["problem"]["experiments"][0]["outcomes"]
        for state in ("mechanism-1", "mechanism-2"):
            self.assertEqual(
                1.0,
                math.fsum(outcome["likelihoods"][state] for outcome in normalized_outcomes),
            )
        self.assertAlmostEqual(
            0.0,
            receipt["information_value"]["experiments"][0]["gross_evsi"],
        )

        endogenous = load_fixture()
        endogenous["state_model"] = "action-dependent"
        with self.assertRaisesRegex(ValueError, "state_model must be exogenous"):
            run_decision_analysis(endogenous)

        non_expected = load_fixture()
        non_expected["criterion"] = "minimax-loss"
        with self.assertRaisesRegex(ValueError, "experiments require"):
            run_decision_analysis(non_expected)

    def test_permutations_are_normalized_and_tampering_is_recomputed(self) -> None:
        original = load_fixture()
        permuted = copy.deepcopy(original)
        permuted["actions"].reverse()
        permuted["states"].reverse()
        permuted["values"].reverse()
        permuted["experiments"].reverse()
        for experiment in permuted["experiments"]:
            experiment["outcomes"].reverse()
        self.assertEqual(run_decision_analysis(original), run_decision_analysis(permuted))

        receipt = run_decision_analysis(original)
        receipt["recommendation"]["optimal_actions"] = ["dominated"]
        material = dict(receipt)
        material.pop("fingerprint")
        receipt["fingerprint"] = canonical_sha256(material)
        with self.assertRaisesRegex(ValueError, "deterministic recomputation"):
            validate_decision_analysis(receipt)

    def test_cli_writes_json_and_human_report(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            output = Path(tempdir) / "decision-analysis.json"
            report = Path(tempdir) / "decision-analysis.md"
            result = subprocess.run(
                [
                    str(ROOT / "scripts" / "python_runtime.sh"),
                    str(ROOT / "scripts" / "run_decision_analysis.py"),
                    str(FIXTURE),
                    "--output",
                    str(output),
                    "--report",
                    str(report),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            receipt = json.loads(output.read_text(encoding="utf-8"))
            validate_decision_analysis(receipt)
            rendered = report.read_text(encoding="utf-8")
            self.assertEqual(render_decision_analysis(receipt), rendered)
            self.assertIn("Conditional action set", rendered)
            self.assertIn("net EVSI", rendered)
            self.assertIn("## Dominance", rendered)
            self.assertIn("Outcome `signal-1`", rendered)
            self.assertIn("posterior P(mechanism-1)", rendered)
            self.assertIn("Exact evaluated boundaries", rendered)
            self.assertIn("P(mechanism-1)=0.6: Risky candidate, Safe candidate", rendered)

    def test_decision_receipt_is_a_validated_quantitative_sidecar(self) -> None:
        receipt = run_decision_analysis(load_fixture())
        sidecars = empty_quantitative_sidecars()
        validate_quantitative_sidecar("decision-analysis", receipt, sidecars)
        self.assertEqual([receipt], sidecars["decision_analyses"])
        self.assertEqual(
            {"decision-sensitive"},
            {item["code"] for item in review_quantitative_sidecars(sidecars)},
        )


if __name__ == "__main__":
    unittest.main()
