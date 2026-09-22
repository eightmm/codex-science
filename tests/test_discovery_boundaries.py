"""Parent-authored adversarial tests of discovery's scientific state boundaries."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from codex_science.artifacts import validate_bundle
from codex_science.discovery import attach_cycle, plan_cycle
from codex_science.research_cycle import apply_cycle_event, load_cycle, new_cycle, save_cycle, validate_history
from tests.test_discovery_integration import prepare, execution_ref


class DiscoveryBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "run"
        self.input = prepare(self.root)
        self.input["evaluation"]["primary_metric"]["json_pointer"] = "/metric"
        save_cycle(new_cycle(self.input), self.root)
        self.cycle = load_cycle(self.root)

    def event(self, kind, **kwargs):
        self.cycle = apply_cycle_event(self.cycle, {"kind": kind, **kwargs}, self.root)
        save_cycle(self.cycle, self.root)
        self.cycle = load_cycle(self.root)
        return self.cycle

    def running(self):
        self.event("reserve", experiment_id="e1", request_id="r1")
        return self.event("running", experiment_id="e1", request_id="r1")

    def observation(self, value=0.5):
        path = self.root / "metrics.json"
        path.write_text(json.dumps({"metric": value, "favorable_secondary": 1.0}))
        return {"artifact_ref": {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()},
                "json_pointer": "/metric", "value": value}

    def complete(self, value=0.5):
        observations = [self.observation(value)]
        receipt = execution_ref(self.root, self.cycle, "e1", observations)
        return self.event("complete", experiment_id="e1", request_id="r1", outcome="Actual fixed metric", observations=observations, execution_refs=[receipt])

    def test_forged_status_with_unrelated_event_is_rejected(self):
        self.running()
        observations = [self.observation(0.5)]
        receipt = execution_ref(self.root, self.cycle, "e1", observations)
        candidate = apply_cycle_event(self.cycle, {"kind": "complete", "experiment_id": "e1", "request_id": "r1", "outcome": "actual", "observations": observations, "execution_refs": [receipt]}, self.root)
        candidate["experiments"][0]["verification"] = "passed"
        with self.assertRaises(ValueError):
            save_cycle(candidate, self.root)

    def test_full_replay_rejects_extra_hypothesis_without_proposal(self):
        candidate = apply_cycle_event(self.cycle, {"kind": "reserve", "experiment_id": "e1", "request_id": "r1"}, self.root)
        candidate["hypotheses"].append({"id": "posthoc", "statement": "Added without event", "conditions": "all", "falsifier": "none observed"})
        with self.assertRaisesRegex(ValueError, "replay"):
            save_cycle(candidate, self.root)

    def test_recomputed_snapshot_digest_cannot_rewrite_history(self):
        self.event("reserve", experiment_id="e1", request_id="r1")
        paths = sorted((self.root / "discovery/revisions").glob("*.json"))
        snapshots = [json.loads(path.read_text()) for path in paths]
        snapshots[-1]["problem"]["interpreted"] = "post-hoc explanation"
        material = {key: value for key, value in snapshots[-1].items() if key != "cycle_hash"}
        snapshots[-1]["cycle_hash"] = hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        with self.assertRaises(ValueError):
            validate_history(snapshots, self.root)

    def test_stale_sibling_cannot_replace_current_revision(self):
        stale = self.cycle
        self.event("reserve", experiment_id="e1", request_id="r1")
        candidate = apply_cycle_event(stale, {"kind": "reserve", "experiment_id": "e1", "request_id": "r2"}, self.root)
        with self.assertRaises(ValueError):
            save_cycle(candidate, self.root)

    def test_metric_locator_cannot_switch_to_favorable_secondary(self):
        self.running()
        observation = self.observation()
        observation.update(json_pointer="/favorable_secondary", value=1.0)
        with self.assertRaises(ValueError):
            self.event("complete", experiment_id="e1", request_id="r1", outcome="cherry-picked", observations=[observation])

    def test_nonpositive_result_cannot_conclude_improved(self):
        self.running()
        self.complete(0.5)
        self.assertEqual("nonpositive", self.cycle["experiments"][0]["method_effect"])
        with self.assertRaises(ValueError):
            self.event("conclude", status="improved", rationale="mislabelled")

    def test_correct_execution_envelope_cannot_relabel_wrong_candidate_output(self):
        self.running()
        path = self.root / "wrong-method.json"
        path.write_text(json.dumps({"metric": 1.0, "candidate_sha256": "0" * 64}))
        observations = [{"artifact_ref": {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()},
                         "json_pointer": "/metric", "value": 1.0}]
        receipt = execution_ref(self.root, self.cycle, "e1", observations)
        with self.assertRaisesRegex(ValueError, "measurement candidate hash"):
            self.event("complete", experiment_id="e1", request_id="r1", outcome="wrong candidate", observations=observations, execution_refs=[receipt])

    def test_reserved_and_ambiguous_jobs_cannot_disappear_at_completion(self):
        self.event("reserve", experiment_id="e1", request_id="r1")
        with self.assertRaises(ValueError):
            apply_cycle_event(self.cycle, {"kind": "conclude", "status": "inconclusive", "rationale": "lost submission"}, self.root)
        self.event("ambiguous", experiment_id="e1", request_id="r1")
        before = copy.deepcopy(self.cycle)
        repeated = apply_cycle_event(self.cycle, {"kind": "reserve", "experiment_id": "e1", "request_id": "r1"}, self.root)
        self.assertEqual(before, repeated)
        self.complete(0.5)
        self.assertEqual("completed", self.cycle["experiments"][0]["state"])

    def test_retry_of_unresolved_experiment_is_rejected(self):
        self.running()
        duplicate = copy.deepcopy(self.input["experiments"][0])
        duplicate.update(id="e2", retry_of="e1")
        with self.assertRaises(ValueError):
            apply_cycle_event(self.cycle, {"kind": "propose", "rationale": "repeat", "experiments": [duplicate]}, self.root)

    def test_control_cost_counts_towards_budget(self):
        other = Path(self.temp.name) / "control-budget"
        payload = prepare(other)
        payload["experiments"][0]["control_cost"] = 3
        cycle = new_cycle(payload)
        with self.assertRaisesRegex(ValueError, "budget"):
            apply_cycle_event(cycle, {"kind": "reserve", "experiment_id": "e1", "request_id": "r1"}, other)

    def test_nonfinite_and_boolean_budget_rejected(self):
        for invalid in (True, float("nan"), float("inf"), -1):
            with self.subTest(invalid=invalid):
                payload = copy.deepcopy(self.input)
                payload["evaluation"]["budget"] = invalid
                with self.assertRaises(ValueError):
                    new_cycle(payload)

    def test_evidence_symlink_and_traversal_rejected(self):
        payload = copy.deepcopy(self.input)
        payload["methods"][0]["code_refs"][0]["path"] = "../outside.py"
        with self.assertRaises(ValueError):
            new_cycle(payload)
        model = self.root / "model.py"
        outside = Path(self.temp.name) / "outside.py"
        outside.write_bytes(model.read_bytes())
        model.unlink()
        model.symlink_to(outside)
        with self.assertRaises(ValueError):
            load_cycle(self.root)

    def test_unregistered_evidence_not_accepted_as_complete_bundle(self):
        manifest = attach_cycle(self.root)
        manifest["artifacts"] = [item for item in manifest["artifacts"] if item["path"] != "model.py"]
        with self.assertRaisesRegex(ValueError, "registered"):
            validate_bundle(manifest, self.root)

    def test_planner_excludes_reserved_experiments_and_uses_remaining_budget(self):
        plan = plan_cycle(self.cycle, self.root)
        self.assertEqual("e1", plan["selected"]["id"])
        self.event("reserve", experiment_id="e1", request_id="r1")
        plan = plan_cycle(self.cycle, self.root)
        self.assertIsNone(plan["selected"])
        self.assertEqual(2, plan["remaining_budget"])

    def test_code_free_idea_cannot_be_reserved(self):
        payload = copy.deepcopy(self.input)
        payload["methods"][0]["code_refs"] = []
        cycle = new_cycle(payload)
        with self.assertRaisesRegex(ValueError, "code refs"):
            apply_cycle_event(cycle, {"kind": "reserve", "experiment_id": "e1", "request_id": "r1"}, self.root)


if __name__ == "__main__":
    unittest.main()
