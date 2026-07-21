import copy
import unittest

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


if __name__ == "__main__":
    unittest.main()
