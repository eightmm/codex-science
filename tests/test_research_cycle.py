import hashlib
import json
import copy
import tempfile
import unittest
from pathlib import Path

from codex_science.research_cycle import apply_cycle_event, load_cycle, new_cycle, save_cycle, validate_cycle


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ResearchCycleTests(unittest.TestCase):
    def make_cycle(self, root: Path) -> dict:
        (root / "code.py").write_text("x = 1\n")
        (root / "evaluation.json").write_text("{}")
        return new_cycle({"problem": {"observed": "loss", "interpreted": "information may be lost"}, "evaluation": {"evaluator": "deterministic", "baseline": "base", "split": "heldout", "primary_metric": {"name": "delta", "direction": "maximize"}, "threshold": {"op": ">=", "value": 0.1}, "budget": 2, "budget_rule": "sum reserved cost", "artifact_refs": [{"path": "evaluation.json", "sha256": digest(root / "evaluation.json")} ]}, "hypotheses": [{"id": "h1", "statement": "information matters", "conditions": "matched capacity", "falsifier": "matched control"}, {"id": "h2", "statement": "capacity matters", "conditions": "matched capacity", "falsifier": "matched control"}], "methods": [{"id": "m", "definition": "preserve feature", "code_refs": [{"path": "code.py", "sha256": digest(root / "code.py")}], "correctness_checks": ["unit"]}], "experiments": [{"id": "e", "method_id": "m", "cost": 1, "predictions": {"h1": [0.2, 0.5], "h2": [-0.1, 0.0]}, "resolution": 0.05, "controls": ["matched"]}]})

    def completion_event(self, root: Path, cycle: dict, value: float = .3) -> dict:
        result = root / "result.json"
        result.write_text(json.dumps({"metric": value}))
        experiment = cycle["experiments"][0]
        code_refs = cycle["methods"][0]["code_refs"]
        evaluation_refs = cycle["evaluation"]["artifact_refs"]
        measurement_refs = [{"path": result.name, "sha256": digest(result)}]
        receipt = root / "receipt.json"
        receipt.write_text(json.dumps({"schema_version": 1, "experiment_id": "e", "experiment_fingerprint": experiment["fingerprint"], "method_id": "m", "code_refs": code_refs, "evaluation_refs": evaluation_refs, "measurement_refs": measurement_refs, "exit_code": 0, "candidate_sha256": code_refs[0]["sha256"], "evaluator_sha256": evaluation_refs[0]["sha256"]}))
        return {"kind": "complete", "experiment_id": "e", "request_id": "r", "outcome": "done", "observations": [{"artifact_ref": measurement_refs[0], "json_pointer": "/metric", "value": value}], "execution_refs": [{"path": receipt.name, "sha256": digest(receipt)}]}

    def test_save_is_idempotent_and_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); cycle = self.make_cycle(root)
            first = save_cycle(cycle, root); self.assertEqual(first, save_cycle(cycle, root))
            saved = load_cycle(root); self.assertEqual(1, saved["revision"])
            first.write_text("{}")
            with self.assertRaisesRegex(ValueError, "lineage|hash"):
                load_cycle(root)

    def test_missing_cycle_error_names_discovery_init(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, r"research cycle is missing; create it with .*discovery init --run-dir RUN --input GENESIS"):
                load_cycle(Path(temporary))

    def test_reservation_failure_retains_budget_and_execution_failure_does_not_refute(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); cycle = self.make_cycle(root)
            reserved = apply_cycle_event(cycle, {"kind": "reserve", "experiment_id": "e", "request_id": "r"})
            self.assertEqual(reserved, apply_cycle_event(reserved, {"kind": "reserve", "experiment_id": "e", "request_id": "r"}))
            failed = apply_cycle_event(reserved, {"kind": "failure", "experiment_id": "e", "request_id": "r", "failure_kind": "execution", "outcome": "exit 1"})
            self.assertEqual("failed", failed["experiments"][0]["state"])
            self.assertNotIn("explanation_support", failed["experiments"][0])

    def test_transition_errors_name_experiment_state_and_required_prior_event(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); cycle = self.make_cycle(root)
            reserved = apply_cycle_event(cycle, {"kind": "reserve", "experiment_id": "e", "request_id": "r"})
            with self.assertRaisesRegex(ValueError, r"only matching running experiments can complete: experiment e is reserved \(request_id 'r'\); record a running event with request_id 'r' first"):
                apply_cycle_event(reserved, {"kind": "complete", "experiment_id": "e", "request_id": "r"})
            with self.assertRaisesRegex(ValueError, r"only matching reservations can run: experiment e is reserved \(request_id 'r'\); use that request_id, not 'x'"):
                apply_cycle_event(reserved, {"kind": "running", "experiment_id": "e", "request_id": "x"})
            with self.assertRaisesRegex(ValueError, r"only matching reservations can run: experiment e is planned \(no request_id\); record a reserve event"):
                apply_cycle_event(cycle, {"kind": "running", "experiment_id": "e", "request_id": "r"})
            with self.assertRaisesRegex(ValueError, r"only planned experiments can be reserved: experiment e is reserved \(request_id 'r'\)"):
                apply_cycle_event(reserved, {"kind": "reserve", "experiment_id": "e", "request_id": "y"})
            running = apply_cycle_event(reserved, {"kind": "running", "experiment_id": "e", "request_id": "r"})
            with self.assertRaises(ValueError) as caught:
                apply_cycle_event(running, {"kind": "reserve", "experiment_id": "e", "request_id": "y"})
            self.assertNotIn("first", str(caught.exception))
            done = apply_cycle_event(running, self.completion_event(root, running), root)
            with self.assertRaises(ValueError) as caught:
                apply_cycle_event(done, {"kind": "failure", "experiment_id": "e", "request_id": "r", "outcome": "late"}, root)
            self.assertRegex(str(caught.exception), r"experiment e is completed \(request_id 'r'\); it accepts no further transitions$")
            self.assertNotIn("first", str(caught.exception))

    def test_saved_transition_rejects_stale_parent(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); original = self.make_cycle(root); save_cycle(original, root)
            current = load_cycle(root)
            advanced = apply_cycle_event(current, {"kind": "reserve", "experiment_id": "e", "request_id": "r"})
            save_cycle(advanced, root)
            stale = apply_cycle_event(current, {"kind": "reserve", "experiment_id": "e", "request_id": "other"})
            with self.assertRaisesRegex(ValueError, "stale"):
                save_cycle(stale, root)

    def test_save_rejects_forged_completed_state_not_replayed_from_event(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); save_cycle(self.make_cycle(root), root)
            reserved = apply_cycle_event(load_cycle(root), {"kind": "reserve", "experiment_id": "e", "request_id": "r"}, root)
            result = root / "result.json"; result.write_text(json.dumps({"metric": 0.5}))
            forged = dict(reserved); forged["experiments"] = [dict(reserved["experiments"][0])]
            forged["experiments"][0].update({"state": "completed", "method_effect": "positive", "verification": "pending", "novelty": "unassessed", "outcome": "forged", "observations": [{"artifact_ref": {"path": "result.json", "sha256": digest(result)}, "json_pointer": "/metric", "value": .5}], "evidence_refs": [{"path": "result.json", "sha256": digest(result)}], "explanation_support": {"h1": "inconclusive", "h2": "contradicted"}})
            forged["status"] = "improved"; forged["rationale"] = "forged"
            with self.assertRaisesRegex(ValueError, "execution_refs|replay"):
                save_cycle(forged, root)

    def test_observation_must_match_hashed_json_locator(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); cycle = self.make_cycle(root)
            running = apply_cycle_event(apply_cycle_event(cycle, {"kind": "reserve", "experiment_id": "e", "request_id": "r"}), {"kind": "running", "experiment_id": "e", "request_id": "r"})
            event = self.completion_event(root, running)
            done = apply_cycle_event(running, event, root)
            self.assertEqual("positive", done["experiments"][0]["method_effect"])
            self.assertEqual(done, apply_cycle_event(done, event, root))
            bad = dict(event); bad["observations"] = [{**event["observations"][0], "value": 0.4}]
            with self.assertRaisesRegex(ValueError, "does not match|conflicting replay"):
                apply_cycle_event(done, bad, root)

    def test_proposed_experiment_cannot_arrive_precompleted(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); cycle = self.make_cycle(root)
            event = {"kind": "propose", "rationale": "new idea", "experiments": [{"id": "e2", "method_id": "m", "cost": 1, "predictions": {"h1": [0, 1]}, "resolution": .1, "controls": ["matched"], "state": "completed", "method_effect": "positive"}]}
            with self.assertRaisesRegex(ValueError, "unobserved"):
                apply_cycle_event(cycle, event, root)

    def test_complete_rejects_receipt_with_swapped_candidate_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cycle = self.make_cycle(root)
            running = apply_cycle_event(
                apply_cycle_event(cycle, {"kind": "reserve", "experiment_id": "e", "request_id": "r"}),
                {"kind": "running", "experiment_id": "e", "request_id": "r"},
            )
            event = self.completion_event(root, running)
            receipt = root / event["execution_refs"][0]["path"]
            payload = json.loads(receipt.read_text())
            payload["candidate_sha256"] = "f" * 64
            receipt.write_text(json.dumps(payload))
            event["execution_refs"][0]["sha256"] = digest(receipt)
            with self.assertRaisesRegex(ValueError, "candidate hash mismatch"):
                apply_cycle_event(running, event, root)

    def test_new_cycle_rejects_preobserved_genesis_and_invalid_metric_pointer(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            forged = self.make_cycle(root)
            forged["experiments"][0]["state"] = "completed"
            with self.assertRaisesRegex(ValueError, "observations|genesis"):
                new_cycle(forged)
            invalid = copy.deepcopy(self.make_cycle(root))
            invalid["evaluation"]["primary_metric"]["json_pointer"] = "metric"
            with self.assertRaisesRegex(ValueError, "json_pointer"):
                new_cycle(invalid)

    def test_load_rejects_noncanonical_revision_name_and_symlink_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            revision = save_cycle(self.make_cycle(root), root)
            revision.rename(revision.with_name("one.json"))
            with self.assertRaisesRegex(ValueError, "noncanonical"):
                load_cycle(root)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            external = root / "outside"
            external.mkdir()
            (root / "discovery").symlink_to(external, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                load_cycle(root)


if __name__ == "__main__":
    unittest.main()
