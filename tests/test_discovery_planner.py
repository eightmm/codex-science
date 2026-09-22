import unittest

from codex_science.experiment_planner import plan_discriminating_experiment


class DiscoveryPlannerTests(unittest.TestCase):
    def test_prefers_resolved_interval_with_required_controls_and_budget(self):
        plan = plan_discriminating_experiment({"hypotheses": [{"id": "h1"}, {"id": "h2"}], "budget": 2, "candidates": [{"id": "blurred", "cost": 1, "resolution": .1, "controls": ["matched"], "predictions": {"h1": [0, .2], "h2": [.1, .3]}}, {"id": "separating", "cost": 2, "resolution": .1, "controls": ["matched"], "predictions": {"h1": [.2, .4], "h2": [-.2, 0]}}]})
        self.assertEqual("separating", plan["selected"]["id"])
        self.assertEqual(["h1", "h2"], plan["selected"]["distinguishable_pairs"][0])

    def test_does_not_select_over_budget_candidate(self):
        plan = plan_discriminating_experiment({"hypotheses": [{"id": "a"}, {"id": "b"}], "budget": 1, "candidates": [{"id": "x", "cost": 2, "resolution": .1, "controls": ["c"], "predictions": {"a": [1, 2], "b": [3, 4]}}]})
        self.assertIsNone(plan["selected"])
        self.assertIn("budget", plan["ranked"][0]["reasons"])


if __name__ == "__main__":
    unittest.main()
