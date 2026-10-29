import copy
import hashlib
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codex_science.experiment_planner import plan_next_experiment, validate_experiment_proposal


INPUT = {
    "schema_version": 1,
    "decision": "Select the next compound batch to discriminate potency and solubility hypotheses.",
    "objectives": [
        {"name": "potency", "direction": "maximize", "weight": 0.6, "required": True},
        {"name": "solubility", "direction": "maximize", "weight": 0.4, "required": True}
    ],
    "candidates": [
        {"id": "control", "properties": {"potency": 0.2, "solubility": 0.9}, "cost": 2, "uncertainty": 0.1, "diversity_group": "control", "control": True},
        {"id": "a1", "properties": {"potency": 0.95, "solubility": 0.3}, "cost": 4, "uncertainty": 0.8, "diversity_group": "A"},
        {"id": "a2", "properties": {"potency": 0.85, "solubility": 0.4}, "cost": 3, "uncertainty": 0.2, "diversity_group": "A"},
        {"id": "b1", "properties": {"potency": 0.6, "solubility": 0.85}, "cost": 3, "uncertainty": 0.7, "diversity_group": "B"},
        {"id": "c1", "properties": {"potency": 0.55, "solubility": 0.7}, "cost": 10, "uncertainty": 0.5, "diversity_group": "C"},
        {"id": "excluded", "properties": {"potency": 1.0, "solubility": 1.0}, "cost": 1, "uncertainty": 1.0, "diversity_group": "X", "eligible": False, "exclusion_reason": "reactive-substructure"}
    ],
    "constraints": {"batch_size": 3, "budget": 10, "diversity_group_cap": 1, "minimum_controls": 1},
    "uncertainty_weight": 0.25,
    "diversity_bonus": 0.2,
    "claim_ids": ["C-potency", "C-solubility"]
}


class ExperimentPlannerTests(unittest.TestCase):
    def simple_input(self, candidates=None, **limits):
        return {
            "decision": "Choose next measurements",
            "objectives": [{"name": "score", "direction": "maximize"}],
            "candidates": candidates if candidates is not None else [
                {"id": "a", "properties": {"score": 1}, "cost": 1}],
            "constraints": {"batch_size": 2, "budget": 3, **limits},
        }

    def test_controls_budget_diversity_and_pareto_ranking_are_explicit(self) -> None:
        proposal = plan_next_experiment(INPUT, created_at="2026-07-21T00:00:00Z")
        validate_experiment_proposal(proposal)
        selected = [item["id"] for item in proposal["selected"]]
        self.assertEqual("control", selected[0])
        self.assertEqual(3, len(selected))
        self.assertLessEqual(proposal["total_cost"], 10)
        self.assertEqual(1, proposal["diversity_groups"]["control"])
        self.assertTrue(all(count <= 1 for count in proposal["diversity_groups"].values()))
        self.assertTrue(proposal["required_controls_satisfied"])
        self.assertFalse(proposal["executed"])
        excluded = next(item for item in proposal["rejected"] if item["id"] == "excluded")
        self.assertIn("reactive-substructure", excluded["reasons"])
        self.assertIn("expected_information_gain_proxy", proposal)

    def test_result_is_deterministic_for_same_contract(self) -> None:
        first = plan_next_experiment(INPUT, created_at="2026-07-21T00:00:00Z")
        second = plan_next_experiment(copy.deepcopy(INPUT), created_at="2026-07-21T00:00:00Z")
        self.assertEqual(first, second)

    def test_required_controls_and_required_objectives_fail_closed(self) -> None:
        no_controls = copy.deepcopy(INPUT)
        no_controls["candidates"] = [item for item in no_controls["candidates"] if not item.get("control")]
        with self.assertRaisesRegex(ValueError, "minimum_controls"):
            plan_next_experiment(no_controls)
        missing = copy.deepcopy(INPUT)
        del missing["candidates"][1]["properties"]["solubility"]
        with self.assertRaisesRegex(ValueError, "lacks required objectives"):
            plan_next_experiment(missing)

    def test_required_controls_that_exceed_budget_are_not_silently_removed(self) -> None:
        constrained = copy.deepcopy(INPUT)
        constrained["constraints"]["budget"] = 1
        with self.assertRaisesRegex(ValueError, "required controls"):
            plan_next_experiment(constrained)

    def test_required_controls_skip_full_groups_in_cost_id_order(self):
        candidates = [
            {"id": ident, "properties": {"score": 1}, "cost": cost,
             "diversity_group": group, "control": True}
            for ident, cost, group in [("b", 1, "A"), ("a", 1, "A"), ("c", 2, "B")]
        ]
        payload = self.simple_input(candidates, minimum_controls=2, diversity_group_cap=1)
        proposal = plan_next_experiment(payload, created_at="fixed")
        self.assertEqual(["a", "c"], [item["id"] for item in proposal["selected"]])
        self.assertEqual(3, proposal["total_cost"])
        self.assertEqual(proposal, plan_next_experiment(copy.deepcopy(payload), created_at="fixed"))
        for limits in ({"budget": 2}, {"batch_size": 1}, {"minimum_controls": 4}):
            with self.subTest(limits=limits), self.assertRaisesRegex(ValueError, "controls"):
                plan_next_experiment({**payload, "constraints": {**payload["constraints"], **limits}})
        candidates.pop()
        with self.assertRaisesRegex(ValueError, "diversity_group_cap"):
            plan_next_experiment(payload)

    def test_decimal_cost_totals_obey_exact_budget_with_and_without_controls(self):
        for required in (0, 2):
            for costs, budget, expected in [
                ((.1, .2), .3, 2), ((0, 0), 0, 2),
                ((.1, .20000000000000004), .3, 1), ((1, 2), 2.99, 1),
            ]:
                with self.subTest(required=required, costs=costs, budget=budget):
                    candidates = [{"id": str(i), "properties": {"score": 1},
                                   "cost": cost, "control": bool(required)}
                                  for i, cost in enumerate(costs)]
                    payload = self.simple_input(candidates, budget=budget, minimum_controls=required)
                    if required > expected:
                        with self.assertRaisesRegex(ValueError, "required controls"):
                            plan_next_experiment(payload)
                    else:
                        proposal = plan_next_experiment(payload)
                        validate_experiment_proposal(proposal)
                        self.assertEqual(expected, proposal["selected_count"])
                        if expected == 2:
                            self.assertEqual(budget, proposal["total_cost"])
                            self.assertEqual(0, proposal["remaining_budget"])

    def test_excluded_candidates_may_lack_required_objectives(self):
        payload = self.simple_input()
        payload["candidates"].append({"id": "excluded", "properties": {}, "eligible": False,
                                      "exclusion_reason": "measurement failed"})
        proposal = plan_next_experiment(payload)
        rejected = proposal["rejected"][0]
        self.assertEqual("excluded", rejected["id"])
        self.assertEqual({}, rejected["candidate"]["properties"])
        self.assertEqual(["measurement failed"], rejected["reasons"])
        payload["candidates"][1]["eligible"] = True
        with self.assertRaisesRegex(ValueError, "lacks required objectives"):
            plan_next_experiment(payload)
        payload["candidates"] = []
        with self.assertRaisesRegex(ValueError, "non-empty"):
            plan_next_experiment(payload)
        payload["candidates"] = [{"id": "excluded", "properties": {}, "eligible": False}]
        with self.assertRaisesRegex(ValueError, "no eligible"):
            plan_next_experiment(payload)

    def test_count_constraints_require_integers_without_truncation(self):
        for field in ("batch_size", "diversity_group_cap", "scaffold_cap", "minimum_controls"):
            for value in (1.9, -.5, .9, 2.0, -1, True, "2", "", None, [], float("nan"), float("inf")):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    plan_next_experiment(self.simple_input(**{field: value}))
        for field in ("batch_size", "diversity_group_cap", "scaffold_cap"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                plan_next_experiment(self.simple_input(**{field: 0}))
        proposal = plan_next_experiment(self.simple_input(batch_size=1, diversity_group_cap=1, minimum_controls=0))
        self.assertEqual(1, proposal["selected_count"])

    def test_candidate_flags_require_booleans(self):
        for flag in ("control", "eligible"):
            for value in ("false", "true", "", 0, 1, None, [], {}):
                with self.subTest(flag=flag, value=value), self.assertRaisesRegex(ValueError, flag + ".*boolean"):
                    plan_next_experiment(self.simple_input([{"id": "a", "properties": {"score": 1}, flag: value}]))
        for value in (False, True):
            proposal = plan_next_experiment(self.simple_input([
                {"id": "a", "properties": {"score": 1}, "control": value, "eligible": True}]))
            self.assertIs(value, proposal["selected"][0]["control"])

    def test_extreme_objective_values_produce_finite_scores(self):
        for direction in ("maximize", "minimize"):
            payload = self.simple_input([
                {"id": str(i), "properties": {"score": value}}
                for i, value in enumerate((-1e308, 0, 1e308))], batch_size=3)
            payload["objectives"][0]["direction"] = direction
            proposal = plan_next_experiment(payload)
            validate_experiment_proposal(proposal)
            scores = {item["id"]: item["normalized_objectives"]["score"] for item in proposal["selected"]}
            self.assertEqual({"0": 0., "1": .5, "2": 1.} if direction == "maximize"
                             else {"0": 1., "1": .5, "2": 0.}, scores)
            self.assertTrue(all(math.isfinite(item["base_utility"]) for item in proposal["selected"]))

    def test_validator_rejects_nonfinite_numbers_even_with_matching_fingerprint(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            for field in ("total_cost", "base_utility", "metadata"):
                with self.subTest(value=value, field=field):
                    proposal = plan_next_experiment(self.simple_input())
                    material = {key: item for key, item in proposal.items() if key not in {"fingerprint", "proposal_id"}}
                    if field == "total_cost":
                        material[field] = value
                    elif field == "metadata":
                        material["selected"][0][field] = {"nested": [value]}
                    else:
                        material["selected"][0][field] = value
                    encoded = json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
                    digest = hashlib.sha256(encoded).hexdigest()
                    with self.assertRaises(ValueError):
                        validate_experiment_proposal({**material, "fingerprint": digest,
                                                      "proposal_id": "experiment-" + digest[:20]})

    def test_overflowing_utility_is_refused(self):
        payload = self.simple_input()
        payload["objectives"] = [{"name": name, "direction": "maximize", "weight": 1e308}
                                 for name in ("score", "other")]
        payload["candidates"][0]["properties"]["other"] = 1
        with self.assertRaisesRegex(ValueError, "finite"):
            plan_next_experiment(payload)
        payload = self.simple_input()
        payload["uncertainty_weight"] = 1e308
        payload["diversity_bonus"] = 1e308
        payload["candidates"][0]["uncertainty"] = 1
        with self.assertRaisesRegex(ValueError, "finite"):
            plan_next_experiment(payload)

    def test_legacy_cli_allows_excluded_missing_measurements_and_rejects_bad_counts(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "plan_next_experiment.py"
        help_result = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, text=True)
        self.assertEqual(0, help_result.returncode, help_result.stderr)
        self.assertIn("for eligible candidates", help_result.stdout)
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp) / "input.json", Path(tmp) / "proposal.json"
            payload = self.simple_input()
            payload["candidates"].append({"id": "excluded", "properties": {}, "eligible": False,
                                          "exclusion_reason": "measurement failed"})
            source.write_text(json.dumps(payload))
            command = [sys.executable, str(script), str(source), "--output", str(output)]
            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(0, first.returncode, first.stderr)
            validate_experiment_proposal(json.loads(output.read_text()))
            payload["constraints"]["batch_size"] = 1.9
            source.write_text(json.dumps(payload))
            before = output.read_bytes()
            refused = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(1, refused.returncode, refused.stderr)
            self.assertIn("integers", refused.stderr)
            self.assertEqual(before, output.read_bytes())


if __name__ == "__main__":
    unittest.main()
