import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codex_science.experiment_planner import plan_discriminating_experiment


class DiscoveryPlannerTests(unittest.TestCase):
    def candidate_input(self, *, cost=.1, control_cost=.2, budget=.3, gap_end=.3, resolution=.1):
        return {"hypotheses": [{"id": "h1"}, {"id": "h2"}], "budget": budget,
                "candidates": [{"id": "x", "cost": cost, "control_cost": control_cost,
                                "resolution": resolution, "controls": ["matched"],
                                "predictions": {"h1": [.2, .2], "h2": [gap_end, gap_end]}}]}

    def test_prefers_resolved_interval_with_required_controls_and_budget(self):
        plan = plan_discriminating_experiment({"hypotheses": [{"id": "h1"}, {"id": "h2"}], "budget": 2, "candidates": [{"id": "blurred", "cost": 1, "resolution": .1, "controls": ["matched"], "predictions": {"h1": [0, .2], "h2": [.1, .3]}}, {"id": "separating", "cost": 2, "resolution": .1, "controls": ["matched"], "predictions": {"h1": [.2, .4], "h2": [-.2, 0]}}]})
        self.assertEqual("separating", plan["selected"]["id"])
        self.assertEqual(["h1", "h2"], plan["selected"]["distinguishable_pairs"][0])

    def test_does_not_select_over_budget_candidate(self):
        plan = plan_discriminating_experiment({"hypotheses": [{"id": "a"}, {"id": "b"}], "budget": 1, "candidates": [{"id": "x", "cost": 2, "resolution": .1, "controls": ["c"], "predictions": {"a": [1, 2], "b": [3, 4]}}]})
        self.assertIsNone(plan["selected"])
        self.assertIn("budget", plan["ranked"][0]["reasons"])

    def test_decimal_cost_boundary_includes_controls_without_tolerance(self):
        for cost, control_cost, budget, selected in [
            (.1, .2, .3, True), (0, 0, 0, True),
            (.1, .20000000000000004, .3, False), (1, 2, 2.99, False),
        ]:
            with self.subTest(cost=cost, control_cost=control_cost, budget=budget):
                proposal = plan_discriminating_experiment(self.candidate_input(
                    cost=cost, control_cost=control_cost, budget=budget, gap_end=.4))
                self.assertEqual(selected, proposal["selected"] is not None)
                if selected:
                    self.assertEqual(budget, proposal["selected"]["total_cost"])
                else:
                    self.assertIn("budget", proposal["ranked"][0]["reasons"])
        for cost in (-1, "bad", float("inf"), 10 ** 400):
            with self.subTest(cost=cost), self.assertRaises(ValueError):
                plan_discriminating_experiment(self.candidate_input(cost=cost))

    def test_decimal_interval_gap_includes_exact_resolution_boundary(self):
        for gap_end, selected in ((.3, True), (.29999999999999993, False), (.2, False), (.4, True)):
            with self.subTest(gap_end=gap_end):
                payload = self.candidate_input(cost=0, control_cost=0, gap_end=gap_end)
                for reverse in (False, True):
                    if reverse:
                        payload["candidates"][0]["predictions"] = dict(zip(
                            ("h2", "h1"), payload["candidates"][0]["predictions"].values()))
                    proposal = plan_discriminating_experiment(payload)
                    self.assertEqual(selected, proposal["selected"] is not None)
                    self.assertEqual([["h1", "h2"]] if selected else [],
                                     proposal["ranked"][0]["distinguishable_pairs"])
        for resolution in (0, -1, "bad", float("inf")):
            with self.subTest(resolution=resolution), self.assertRaises(ValueError):
                plan_discriminating_experiment(self.candidate_input(resolution=resolution))
        payload = self.candidate_input()
        payload["candidates"][0]["predictions"]["h2"] = []
        with self.assertRaisesRegex(ValueError, "interval"):
            plan_discriminating_experiment(payload)

    def test_computed_costs_preserve_exact_feasibility_and_finite_output(self):
        for cost, control_cost, budget, selected in (
            (0, 0, 0, True), (.1, .2, .3, True), (.3, 1e-18, .3, False),
            (sys.float_info.max, 0, sys.float_info.max, True),
        ):
            with self.subTest(cost=cost, control_cost=control_cost):
                plan = plan_discriminating_experiment(self.candidate_input(
                    cost=cost, control_cost=control_cost, budget=budget))
                self.assertEqual(selected, plan["selected"] is not None)
                self.assertEqual(budget, plan["ranked"][0]["total_cost"])
                self.assertEqual([] if selected else ["budget"], plan["ranked"][0]["reasons"])
        with self.assertRaisesRegex(ValueError, "candidate total cost must be finite"):
            plan_discriminating_experiment(self.candidate_input(
                cost=sys.float_info.max, control_cost=sys.float_info.max, budget=sys.float_info.max))
        for value in (True, "0.1", "", None, [], {}, float("nan"), float("inf")):
            for field in ("cost", "control_cost", "budget", "resolution"):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    plan_discriminating_experiment(self.candidate_input(**{field: value}))

    def test_discovery_cli_preserves_exact_cost_and_resolution_boundaries(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "science_project.py"
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp) / "input.json", Path(tmp) / "plan.json"
            source.write_text(json.dumps(self.candidate_input()))
            result = subprocess.run([sys.executable, str(script), "discovery", "plan",
                                     "--input", str(source), "--output", str(output)],
                                    capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stderr)
            proposal = json.loads(output.read_text())
            self.assertEqual("x", proposal["selected"]["id"])
            self.assertEqual(.3, proposal["selected"]["total_cost"])
            self.assertEqual([["h1", "h2"]], proposal["selected"]["distinguishable_pairs"])


if __name__ == "__main__":
    unittest.main()
