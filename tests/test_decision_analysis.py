import copy
import hashlib
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
GOLDEN_RECEIPTS = ROOT / "tests" / "fixtures" / "decision_analysis" / "base_receipts.json"


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def criteria_by_name(receipt: dict) -> dict[str, dict]:
    return {item["criterion"]: item for item in receipt["criterion_results"]}


def scores_by_action(result: dict) -> dict[str, float]:
    return {item["action"]: item["value"] for item in result["scores"]}


def table_problem(matrix: dict, **options) -> dict:
    problem = load_fixture()
    problem.pop("sensitivity")
    problem["experiments"] = []
    problem["actions"] = [{"id": action} for action in matrix]
    problem["states"] = [{"id": state, "prior": 0.5} for state in ("s", "t")]
    problem["values"] = [
        {"action": action, "state": state, "value": value}
        for action, row in matrix.items()
        for state, value in zip(("s", "t"), row)
    ]
    problem.update(options)
    return problem


def base_receipt_problems() -> tuple[dict, dict]:
    problems = {
        name: load_fixture()
        for name in ("fixture", "near-normalized", "permuted", "uninformative", "rare-signal", "unreachable", "utility", "payoff")
    }
    near = problems["near-normalized"]
    probabilities = (0.49377654070971555, 0.5062234594836474)
    for state, prior in zip(near["states"], probabilities):
        state["prior"] = prior
    for cell in near["values"]:
        cell["value"] = 1e12
    for outcome, probability in zip(near["experiments"][0]["outcomes"], probabilities):
        outcome["likelihoods"] = {state["id"]: probability for state in near["states"]}
    permuted = problems["permuted"]
    for field in ("actions", "states", "values", "experiments"):
        permuted[field].reverse()
    for experiment in permuted["experiments"]:
        experiment["outcomes"].reverse()
    for name, probabilities in (
        ("uninformative", (0.5, 0.5)),
        ("rare-signal", (1.0 - 1e-12, 1e-12)),
        ("unreachable", (1.0, 0.0)),
    ):
        problem = problems[name]
        for index, (outcome, probability) in enumerate(zip(problem["experiments"][0]["outcomes"], probabilities)):
            outcome["likelihoods"] = {state["id"]: probability for state in problem["states"]}
            if name == "rare-signal":
                outcome["id"] = ("common", "rare")[index]
    for name, criterion, rationale, attitude in (
        ("utility", "expected-utility", "Cardinal utility is explicitly encoded.", "encoded-in-utility"),
        ("payoff", "expected-payoff", "Linear monetary value is accepted under risk neutrality.", "risk-neutral"),
    ):
        problem = problems[name]
        problem["criterion"] = criterion
        problem["criterion_rationale"] = rationale
        problem["scale"] = {"kind": name, "unit": name + "-point", "risk_attitude": attitude}
        for cell in problem["values"]:
            cell["value"] = -cell["value"] if name == "utility" else 10.0 - cell["value"]
    for name, sign in (("ordinary-positive", 1), ("ordinary-negative", -1)):
        problems[name] = table_problem(
            {"a": [sign * 1.1, sign * 1.4], "b": [sign * 1.3, sign * 1.2]},
            experiments=[{"id": "e", "outcomes": [
                {"id": "u", "likelihoods": {"s": 0.8, "t": 0.2}},
                {"id": "v", "likelihoods": {"s": 0.2, "t": 0.8}},
            ]}],
        )
    numeric = table_problem({1: [0, 1], 2: [1, 0]})
    for index, state in enumerate(numeric["states"], 1):
        state["id"] = index
        state["label"] = index
    for cell in numeric["values"]:
        cell["state"] = 1 if cell["state"] == "s" else 2
    numeric["experiments"] = [{"id": 3, "label": 3, "outcomes": [
        {"id": 4, "likelihoods": {"1": 1.0, "2": 1.0}},
    ]}]
    problems["numeric-ids"] = numeric
    for name, likelihood in (("component-zero", 0.0), ("component-underflow", 1e-200), ("component-subnormal", 1e-120)):
        problem = table_problem(
            {"a": [4, 0], "b": [0, 1]}, criterion="expected-payoff",
            scale={"kind": "payoff", "unit": "point", "risk_attitude": "risk-neutral"},
            experiments=[{"id": "e", "outcomes": [
                {"id": "rare", "likelihoods": {"s": likelihood, "t": 0.5}},
                {"id": "common", "likelihoods": {"s": 1.0, "t": 0.5}},
            ]}],
        )
        problem["states"][0]["prior"] = 1e-200
        problem["states"][1]["prior"] = 1.0
        problems[name] = problem
    rejected = {
        "incomplete": (load_fixture(), "values must contain exactly one cell for every action/state pair (6)"),
        "bad-prior": (load_fixture(), "state priors must sum to 1; observed 1.1"),
        "bad-likelihood": (load_fixture(), "experiment bounded-assay likelihoods for state mechanism-1 must sum to 1; observed 1.1"),
        "endogenous": (load_fixture(), "state_model must be exogenous for the finite one-stage runtime"),
        "non-expected": (load_fixture(), "experiments require bayes-risk, expected-utility, or expected-payoff"),
        "payoff-attitude": (copy.deepcopy(problems["payoff"]), "scale.risk_attitude must be risk-neutral for payoff values"),
    }
    rejected["incomplete"][0]["values"].pop()
    rejected["bad-prior"][0]["states"][0]["prior"] = 0.7
    rejected["bad-likelihood"][0]["experiments"][0]["outcomes"][0]["likelihoods"]["mechanism-1"] = 0.9
    rejected["endogenous"][0]["state_model"] = "action-dependent"
    rejected["non-expected"][0]["criterion"] = "minimax-loss"
    rejected["payoff-attitude"][0]["scale"]["risk_attitude"] = "encoded-in-utility"
    return problems, rejected


class DecisionAnalysisTests(unittest.TestCase):
    def test_sensitivity_preserves_narrow_probability_regions(self) -> None:
        problem = table_problem(
            {"a": [0, 1], "b": [1999, 0]}, tie_tolerance=0.001,
            sensitivity={"two_state_prior": {"state_id": "s"}},
        )
        result = run_decision_analysis(problem)["sensitivity"]
        self.assertTrue(result["decision_changes_within_range"])
        self.assertEqual(["b"], result["regions"][0]["optimal_actions"])
        self.assertEqual(0.0005, result["regions"][0]["maximum"])
        for region in result["regions"]:
            self.assertGreater(region["maximum"], region["minimum"])
        problem["sensitivity"]["two_state_prior"].update(minimum=0.00025, maximum=0.00075)
        clipped = run_decision_analysis(problem)["sensitivity"]
        self.assertEqual(0.00025, clipped["regions"][0]["minimum"])
        self.assertEqual(0.00075, clipped["regions"][-1]["maximum"])
        for minimum, maximum in ((0, 0), (0.5, 0.5), (0, "bad"), (-1, 1)):
            problem["sensitivity"]["two_state_prior"].update(minimum=minimum, maximum=maximum)
            with self.assertRaises(ValueError):
                run_decision_analysis(problem)

    def test_sensitivity_splits_at_exact_crossings_and_retains_direct_ties(self) -> None:
        for kind, criterion, attitude in (
            ("loss", "bayes-risk", "encoded-in-loss"),
            ("payoff", "expected-payoff", "risk-neutral"),
        ):
            problem = table_problem(
                {"a": [0, 1], "b": [1, 0]}, tie_tolerance=0.001,
                criterion=criterion,
                scale={"kind": kind, "unit": "point", "risk_attitude": attitude},
                sensitivity={"two_state_prior": {"state_id": "s"}},
            )
            result = run_decision_analysis(problem)["sensitivity"]
            self.assertEqual(2, len(result["regions"]))
            self.assertEqual(0.5, result["regions"][0]["maximum"])
            self.assertEqual(0.5, result["regions"][1]["minimum"])
            self.assertEqual(["a", "b"], result["boundaries"][1]["optimal_actions"])
            for region in result["regions"]:
                for fraction in (0.01, 0.25, 0.5, 0.75, 0.99):
                    prior = region["minimum"] + fraction * (region["maximum"] - region["minimum"])
                    problem["states"][0]["prior"] = prior
                    problem["states"][1]["prior"] = 1.0 - prior
                    direct = run_decision_analysis(problem)["recommendation"]
                    self.assertEqual(region["optimal_actions"], direct["optimal_actions"])
            problem["states"][0]["prior"] = 0.5001
            problem["states"][1]["prior"] = 0.4999
            self.assertEqual(["a", "b"], run_decision_analysis(problem)["recommendation"]["optimal_actions"])
        constant = table_problem(
            {"a": [0, 0], "b": [0, 0]},
            sensitivity={"two_state_prior": {"state_id": "s"}},
        )
        self.assertEqual(
            [{"minimum": 0.0, "maximum": 1.0, "optimal_actions": ["a", "b"]}],
            run_decision_analysis(constant)["sensitivity"]["regions"],
        )
        self.assertEqual(["a"], run_decision_analysis(table_problem({"a": [0, 0]}))["recommendation"]["optimal_actions"])
        never_optimal = table_problem(
            {"a": [0, 0], "b": [0, 0], "c": [2, 1], "d": [1, 2]},
            sensitivity={"two_state_prior": {"state_id": "s"}},
        )
        self.assertEqual(
            [0.0, 1.0],
            [row["prior"] for row in run_decision_analysis(never_optimal)["sensitivity"]["boundaries"]],
        )

    def test_endpoint_tie_does_not_change_interior_policy_or_status(self) -> None:
        problem = table_problem(
            {"a": [0, 0], "b": [1, 0]},
            sensitivity={"two_state_prior": {"state_id": "s"}},
        )
        result = run_decision_analysis(problem)
        self.assertEqual("completed", result["status"])
        self.assertEqual("completed", result["recommendation"]["status"])
        self.assertEqual(
            [{"minimum": 0.0, "maximum": 1.0, "optimal_actions": ["a"]}],
            result["sensitivity"]["regions"],
        )
        self.assertFalse(result["sensitivity"]["decision_changes_within_range"])
        self.assertEqual(["a", "b"], result["sensitivity"]["boundaries"][0]["optimal_actions"])

    def test_existing_payloads_are_byte_identical_to_base_receipts(self) -> None:
        goldens = json.loads(GOLDEN_RECEIPTS.read_text(encoding="utf-8"))
        problems, rejected = base_receipt_problems()
        self.assertEqual(set(problems), set(goldens))
        # Digests were generated from commit 41161a3's base module using these UTF-8 JSON bytes.
        for name, problem in problems.items():
            with self.subTest(payload=name):
                actual = run_decision_analysis(problem)
                rendered = json.dumps(actual, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
                self.assertEqual(goldens[name], hashlib.sha256(rendered.encode("utf-8")).hexdigest())
                validate_decision_analysis(actual)
        for name, (problem, error) in rejected.items():
            with self.subTest(payload=name):
                with self.assertRaises(ValueError) as caught:
                    run_decision_analysis(problem)
                self.assertEqual(error, str(caught.exception))

    def test_rounded_prior_one_ties_preserve_completed_status(self) -> None:
        for kind, criterion, attitude in (
            ("loss", "bayes-risk", "encoded-in-loss"),
            ("payoff", "expected-payoff", "risk-neutral"),
        ):
            for focus, other_a, other_b, loss_action in (
                (2.1, 4.4, -0.8, "b"),
                (1.7, -1.3, -0.6, "a"),
                (0.9, -1.1, -3.3, "b"),
                (9.8, -1.7, -1.8, "b"),
                (-9.8, 1.7, 1.8, "a"),
            ):
                with self.subTest(kind=kind, focus=focus):
                    result = run_decision_analysis(table_problem(
                        {"a": [focus, other_a], "b": [focus, other_b]},
                        criterion=criterion,
                        scale={"kind": kind, "unit": "point", "risk_attitude": attitude},
                        sensitivity={"two_state_prior": {"state_id": "s"}},
                    ))
                    self.assertEqual("completed", result["status"])
                    action = loss_action if kind == "loss" else "b" if loss_action == "a" else "a"
                    self.assertEqual(
                        [{"minimum": 0.0, "maximum": 1.0, "optimal_actions": [action]}],
                        result["sensitivity"]["regions"],
                    )
                    self.assertFalse(result["sensitivity"]["decision_changes_within_range"])
                    self.assertEqual(1.0, result["sensitivity"]["boundaries"][-1]["prior"])
                    self.assertEqual(["a", "b"], result["sensitivity"]["boundaries"][-1]["optimal_actions"])

    def test_coincident_crossings_do_not_create_roundoff_regions(self) -> None:
        result = run_decision_analysis(table_problem(
            {"a": [-1.6, 0.3], "b": [-0.4, -0.2142857142857143], "c": [-2.8, 0.8142857142857143]},
            sensitivity={"two_state_prior": {"state_id": "s"}},
        ))["sensitivity"]
        self.assertEqual(2, len(result["regions"]))
        self.assertEqual([["b"], ["c"]], [row["optimal_actions"] for row in result["regions"]])
        self.assertEqual(3, len(result["boundaries"]))
        self.assertEqual(["a", "b", "c"], result["boundaries"][1]["optimal_actions"])
        for region in result["regions"]:
            self.assertGreaterEqual(region["maximum"] - region["minimum"], 8.0 * math.ulp(1.0))

    def test_prior_range_respects_probability_rounding_resolution(self) -> None:
        problem = table_problem(
            {"a": [0, 0]}, sensitivity={"two_state_prior": {"state_id": "s"}},
        )
        resolution = 8.0 * math.ulp(1.0)
        route = problem["sensitivity"]["two_state_prior"]
        for maximum in (0.0, math.nextafter(resolution, 0.0), "bad", []):
            with self.subTest(maximum=maximum):
                route["maximum"] = maximum
                with self.assertRaises(ValueError):
                    run_decision_analysis(problem)
        route["maximum"] = resolution
        self.assertEqual(
            [{"minimum": 0.0, "maximum": resolution, "optimal_actions": ["a"]}],
            run_decision_analysis(problem)["sensitivity"]["regions"],
        )
        at_endpoint_resolution = table_problem(
            {"a": [0, 0], "b": [1.0 - resolution, -resolution]},
            sensitivity={"two_state_prior": {"state_id": "s"}},
        )
        self.assertEqual(
            [{"minimum": 0.0, "maximum": 1.0, "optimal_actions": ["a"]}],
            run_decision_analysis(at_endpoint_resolution)["sensitivity"]["regions"],
        )

    def test_underflowed_component_with_normal_marginal_keeps_base_posterior(self) -> None:
        problem = table_problem(
            {"a": [4, 0], "b": [0, 1]}, criterion="expected-payoff",
            scale={"kind": "payoff", "unit": "point", "risk_attitude": "risk-neutral"},
        )
        problem["states"][0]["prior"] = 1e-200
        problem["states"][1]["prior"] = 1.0
        for likelihood in (0.0, 1e-200, 1e-120):
            problem["experiments"] = [{"id": "e", "outcomes": [
                {"id": "rare", "likelihoods": {"s": likelihood, "t": 0.5}},
                {"id": "common", "likelihoods": {"s": 1.0, "t": 0.5}},
            ]}]
            outcomes = run_decision_analysis(problem)["information_value"]["experiments"][0]["outcome_policy"]
            rare = next(row for row in outcomes if row["outcome"] == "rare")
            self.assertEqual("reachable", rare["status"])
            self.assertEqual(0.5, rare["probability"])
            self.assertEqual(1e-200 * likelihood / 0.5, rare["posterior"]["s"])
            self.assertEqual(1.0, rare["posterior"]["t"])
            self.assertEqual(["b"], rare["optimal_actions"])

    def test_numeric_identifiers_and_labels_keep_base_coercion(self) -> None:
        problem = table_problem({1: [0, 1], 2: [1, 0]})
        for index, state in enumerate(problem["states"], 1):
            state["id"] = index
            state["label"] = index
        for cell in problem["values"]:
            cell["state"] = 1 if cell["state"] == "s" else 2
        problem["experiments"] = [{"id": 3, "label": 3, "outcomes": [
            {"id": 4, "likelihoods": {"1": 1.0, "2": 1.0}},
        ]}]
        result = run_decision_analysis(problem)
        self.assertEqual(["1", "2"], [row["id"] for row in result["problem"]["actions"]])
        self.assertEqual(["1", "2"], [row["id"] for row in result["problem"]["states"]])
        self.assertEqual("3", result["problem"]["experiments"][0]["id"])
        self.assertEqual("4", result["problem"]["experiments"][0]["outcomes"][0]["id"])
        validate_decision_analysis(result)

    def test_information_value_survives_common_consequence_offset(self) -> None:
        experiment = {"id": "e", "cost_in_scale_units": 1.5, "outcomes": [
            {"id": "u", "likelihoods": {"s": 0.75, "t": 0.25}},
            {"id": "v", "likelihoods": {"s": 0.25, "t": 0.75}},
        ]}
        for offset in (0.0, 2.0 ** 28 - 4.0, 2.0 ** 28, -2.0 ** 28 - 4.0, 1e16, -1e16):
            result = run_decision_analysis(table_problem(
                {"a": [offset, offset + 4], "b": [offset + 4, offset]},
                experiments=[experiment],
            ))["information_value"]
            self.assertEqual(2.0, result["evpi"])
            self.assertEqual(1.0, result["experiments"][0]["gross_evsi"])
            self.assertEqual(-0.5, result["experiments"][0]["net_evsi"])
            self.assertEqual("not-worth-cost", result["experiments"][0]["decision"])

    def test_overflow_is_refused_before_cli_json_write(self) -> None:
        problem = table_problem(
            {"a": [-1e308, 1.7e308], "b": [1e308, -1e308]},
            criterion="minimax-regret",
        )
        with self.assertRaisesRegex(ValueError, "regret.*must be finite"):
            run_decision_analysis(problem)
        with tempfile.TemporaryDirectory() as tempdir:
            source = Path(tempdir) / "input.json"
            output = Path(tempdir) / "output.json"
            source.write_text(json.dumps(problem), encoding="utf-8")
            result = subprocess.run(
                [str(ROOT / "scripts" / "python_runtime.sh"),
                 str(ROOT / "scripts" / "run_decision_analysis.py"),
                 str(source), "--output", str(output)],
                cwd=ROOT, capture_output=True, text=True, check=False,
            )
            self.assertEqual(1, result.returncode, result.stdout)
            self.assertIn("regret", result.stderr)
            self.assertIn("must be finite", result.stderr)
            self.assertFalse(output.exists())
        finite = run_decision_analysis(table_problem({"a": [0, 1.7e308], "b": [1e308, 0]}))
        json.dumps(finite, allow_nan=False)
        with self.assertRaisesRegex(ValueError, "value.*must be finite"):
            run_decision_analysis(table_problem({"a": [10 ** 1000, 0]}))

    def test_subnormal_likelihood_preserves_prior_and_policy(self) -> None:
        problem = table_problem(
            {"a": [4, 0], "b": [0, 1]}, criterion="expected-payoff",
            scale={"kind": "payoff", "unit": "point", "risk_attitude": "risk-neutral"},
        )
        problem["states"][0]["prior"] = 0.25
        problem["states"][1]["prior"] = 0.75
        for likelihood in (5e-324, 1e-320, 0.0):
            problem["experiments"] = [{"id": "e", "outcomes": [
                {"id": "rare", "likelihoods": {"s": likelihood, "t": likelihood}},
                {"id": "common", "likelihoods": {"s": 1.0, "t": 1.0}},
            ]}]
            outcomes = run_decision_analysis(problem)["information_value"]["experiments"][0]["outcome_policy"]
            rare = next(row for row in outcomes if row["outcome"] == "rare")
            if likelihood == 0.0:
                self.assertEqual("unreachable", rare["status"])
                self.assertIsNone(rare["posterior"])
            else:
                self.assertEqual({"s": 0.25, "t": 0.75}, rare["posterior"])
                self.assertEqual(["a"], rare["optimal_actions"])
                self.assertEqual(likelihood, rare["probability"])
        problem["states"][0]["prior"] = 5e-324
        problem["states"][1]["prior"] = 1.0
        for other_likelihood in (0.0, 1.0):
            problem["experiments"][0]["outcomes"][0]["likelihoods"] = {"s": 5e-324, "t": other_likelihood}
            problem["experiments"][0]["outcomes"][1]["likelihoods"] = {"s": 1.0, "t": 1.0 - other_likelihood}
            if other_likelihood == 0.0:
                with self.assertRaisesRegex(ValueError, "outcome rare posterior normalization lost precision"):
                    run_decision_analysis(problem)
            else:
                outcomes = run_decision_analysis(problem)["information_value"]["experiments"][0]["outcome_policy"]
                rare = next(row for row in outcomes if row["outcome"] == "rare")
                self.assertEqual({"s": 0.0, "t": 1.0}, rare["posterior"])

    def test_required_fields_reject_wrong_types(self) -> None:
        for value in (True, 1.0, "1", None, 0):
            with self.subTest(schema_version=value):
                with self.assertRaisesRegex(ValueError, "unsupported decision-analysis input schema"):
                    run_decision_analysis(table_problem({"a": [0, 0]}, schema_version=value))
        for field in ("question", "information_boundary", "criterion_rationale"):
            for value in ({}, [], False, 0, "", " ", None):
                with self.subTest(field=field, value=value):
                    with self.assertRaisesRegex(ValueError, field):
                        run_decision_analysis(table_problem({"a": [0, 0]}, **{field: value}))

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
        self.assertEqual([], review_decision_analysis(receipt))

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
        self.assertEqual("decision-sensitive", sidecars["decision_analyses"][0]["status"])
        self.assertEqual([], review_quantitative_sidecars(sidecars))

    def test_hand_written_receipt_error_names_the_producing_script(self) -> None:
        for kind, script in (
            ("statistical-analysis", "run_statistical_analysis.py"),
            ("decision-analysis", "run_decision_analysis.py"),
        ):
            with self.assertRaises(ValueError) as caught:
                validate_quantitative_sidecar(kind, {"p_value": 0.01}, empty_quantitative_sidecars())
            self.assertIn(f"scripts/{script} --output", str(caught.exception))
            self.assertIn("package_run.py refresh --kind PATH=KIND", str(caught.exception))
        with self.assertRaises(ValueError) as caught:
            validate_quantitative_sidecar("proof-receipt", {}, empty_quantitative_sidecars())
        self.assertNotIn("scripts/", str(caught.exception))

    def test_statistical_design_missing_names_the_design_script(self) -> None:
        findings = review_quantitative_sidecars(
            {"statistical_analyses": [{"analysis_id": "A1", "design_id": "D-none"}]}
        )
        message = next(f["message"] for f in findings if f["code"] == "statistical-design-missing")
        self.assertIn("scripts/validate_research_design.py --output", message)
        self.assertIn("kind research-design", message)


if __name__ == "__main__":
    unittest.main()
