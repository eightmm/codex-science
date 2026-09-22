import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codex_science.discovery import attach_cycle
from codex_science.project_store import ProjectStore
from codex_science.research_cycle import apply_cycle_event, load_cycle, new_cycle, save_cycle
from tests.test_discovery_integration import ROOT, prepare
from tests import test_discovery_design as design_fixtures


class DiscoveryWorkbenchTests(unittest.TestCase):
    def test_readonly_cli_views_and_project_memory_preserve_scientific_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run"
            save_cycle(new_cycle(prepare(root)), root)
            attach_cycle(root)
            before = (root / "discovery/revisions/000001.json").read_bytes()
            command = [sys.executable, str(ROOT / "scripts/science_project.py")]
            for action in ("audit", "next", "graph", "assess"):
                with self.subTest(action=action):
                    result = subprocess.run(command + ["discovery", action, "--run-dir", str(root)], capture_output=True, text=True)
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertIsInstance(json.loads(result.stdout), dict)
            database = Path(temporary) / "project.sqlite"
            store = ProjectStore(database)
            store.create_project(project_id="p", title="Discovery", question="Why?")
            store.import_run(project_id="p", manifest_path=root / "manifest.json")
            result = subprocess.run(command + ["--database", str(database), "discovery", "memory", "--project-id", "p"], capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(2, len(json.loads(result.stdout)["comparable_evidence_groups"]))
            self.assertEqual(before, (root / "discovery/revisions/000001.json").read_bytes())

    def test_strict_revision_appends_new_assumption_and_requires_actual_learning(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cycle = design_fixtures.DiscoveryDesignTests().designed(root)
            cycle["design_policy"] = "required-for-reservation"
            cycle["experiments"] = [{"id": "e1", "method_id": "m1", "cost": 1,
                                      "predictions": {"h1": [0, 1]}, "resolution": .1,
                                      "controls": ["same input"]}]
            save_cycle(new_cycle(cycle), root)
            for event in ({"kind": "reserve", "experiment_id": "e1", "request_id": "r1"},
                          {"kind": "failure", "experiment_id": "e1", "request_id": "r1",
                           "failure_kind": "implementation", "outcome": "nonfinite feature"}):
                save_cycle(apply_cycle_event(load_cycle(root), event, root), root)
            cycle = load_cycle(root)
            event = {"kind": "revise", "source_experiment_id": "e1", "rationale": "Need a finite-feature assumption",
                     "assumptions": [{"id": "finite", "statement": "Inputs are finite", "category": "data", "status": "untested"}]}
            with self.assertRaisesRegex(ValueError, "lesson"):
                apply_cycle_event(cycle, event, root)
            event["lesson"] = {"observation": "The feature computation failed before measurement",
                               "interpretation": "Execution failure does not test h1", "limitation": "No valid metric",
                               "change": "Add explicit finite input assumption", "next_test": "Repair and confirm finite features"}
            changed = apply_cycle_event(cycle, event, root)
            save_cycle(changed, root)
            result = load_cycle(root)
            self.assertEqual(cycle["problem"]["assumptions"], result["problem"]["assumptions"][:-1])
            self.assertEqual("finite", result["problem"]["assumptions"][-1]["id"])
            no_change = copy.deepcopy(event)
            no_change.pop("assumptions")
            with self.assertRaisesRegex(ValueError, "append a changed"):
                apply_cycle_event(result, no_change, root)
            with self.assertRaisesRegex(ValueError, "unique"):
                apply_cycle_event(result, event, root)

    def test_cli_cannot_overwrite_unregistered_review_input(self):
        import hashlib
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run"
            save_cycle(new_cycle(prepare(root)), root)
            attach_cycle(root)
            receipt = root / "review.json"
            receipt.write_text('{"sentinel":"must stay intact"}')
            before = receipt.read_bytes()
            payload = root / "assessment.json"
            payload.write_text(json.dumps({"review_refs": [{"path": receipt.name,
                                                           "sha256": hashlib.sha256(before).hexdigest()}]}))
            result = subprocess.run([sys.executable, str(ROOT / "scripts/science_project.py"), "discovery", "assess",
                                     "--run-dir", str(root), "--input", str(payload), "--output", str(receipt)], capture_output=True, text=True)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("cannot overwrite referenced input evidence", result.stderr)
            self.assertEqual(before, receipt.read_bytes())


if __name__ == "__main__":
    unittest.main()
