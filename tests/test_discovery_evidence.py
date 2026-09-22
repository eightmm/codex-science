import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from codex_science.discovery import attach_cycle, finite_decision
from codex_science.discovery_evidence import assess_cycle, cycle_graph
from codex_science.research_cycle import apply_cycle_event, load_cycle, new_cycle, save_cycle
from codex_science.review_receipts import build_review_receipt
from codex_science.reviewer_runtime import build_review_packet
from tests.test_discovery_integration import ROOT, execution_ref, prepare


def write_ref(root, name, payload):
    path = root / name
    path.write_text(json.dumps(payload))
    return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


class DiscoveryEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "run"
        self.payload = prepare(self.root)

    def start(self):
        save_cycle(new_cycle(self.payload), self.root)
        return load_cycle(self.root)

    def review_ref(self, cycle, modes, status="passed", independent=True, omit_snapshot=False, name="review"):
        manifest = attach_cycle(self.root)
        covered = [{"path": item["path"], "sha256": item["sha256"]} for item in manifest["artifacts"]
                   if not omit_snapshot or item["kind"] != "research-cycle"]
        receipt = build_review_receipt(review_id=name, reviewer="separate reviewer", independent=independent,
                                       review_modes=modes, status=status, covered_artifacts=covered,
                                       covered_claim_ids=[], findings=[])
        return write_ref(self.root, name + ".json", receipt)

    def test_axes_do_not_promote_record_review_to_method_or_reproduction(self):
        cycle = self.start()
        ref = self.review_ref(cycle, ["record"])
        before = copy.deepcopy(cycle)
        result = assess_cycle(cycle, self.root, {"review_refs": [ref]})
        self.assertEqual("passed_in_review_scope", result["review_axes"]["record"]["status"])
        self.assertFalse(result["review_scope"]["authoritative_overall_pass"])
        self.assertEqual("pending", result["review_axes"]["method"]["status"])
        self.assertEqual("pending", result["review_axes"]["reproduction"]["status"])
        self.assertEqual("unassessed", result["novelty"]["status"])
        self.assertEqual(before, load_cycle(self.root))

    def test_nonindependent_incomplete_and_stale_reviews_do_not_pass(self):
        cycle = self.start()
        for kwargs in ({"independent": False}, {"omit_snapshot": True}):
            with self.subTest(kwargs=kwargs):
                ref = self.review_ref(cycle, ["method"], **kwargs)
                self.assertEqual("pending", assess_cycle(cycle, self.root, {"review_refs": [ref]})["review_axes"]["method"]["status"])
        ref = self.review_ref(cycle, ["method"])
        save_cycle(apply_cycle_event(cycle, {"kind": "reserve", "experiment_id": "e1", "request_id": "r1"}, self.root), self.root)
        result = assess_cycle(load_cycle(self.root), self.root, {"review_refs": [ref]})
        self.assertEqual("pending", result["review_axes"]["method"]["status"])

    def test_conflicting_reviews_preserved_and_tampered_receipt_rejected(self):
        cycle = self.start()
        good = self.review_ref(cycle, ["method"], name="pass")
        bad = self.review_ref(cycle, ["method"], status="findings", name="findings")
        result = assess_cycle(cycle, self.root, {"review_refs": [good, bad]})
        self.assertEqual("conflicting", result["review_axes"]["method"]["status"])
        (self.root / good["path"]).write_text("{}")
        with self.assertRaises(ValueError):
            assess_cycle(cycle, self.root, {"review_refs": [good]})

    def test_registered_findings_cannot_be_hidden_by_supplying_only_pass(self):
        from codex_science.artifacts import add_artifact
        cycle = self.start()
        good = self.review_ref(cycle, ["method"], name="pass")
        bad = self.review_ref(cycle, ["method"], status="findings", name="findings")
        path = self.root / "manifest.json"
        manifest = json.loads(path.read_text())
        add_artifact(manifest, bad["path"], kind="review-receipt", sha256=bad["sha256"])
        path.write_text(json.dumps(manifest))
        result = assess_cycle(cycle, self.root, {"review_refs": [good]})
        self.assertEqual("conflicting", result["review_axes"]["method"]["status"])

    def test_reviewer_packet_contains_cycle_and_redacts_producer_fields(self):
        self.payload["problem"]["producer_rationale"] = "hidden rationale sentinel"
        cycle = self.start()
        attach_cycle(self.root)
        packet = build_review_packet(self.root / "manifest.json", review_modes=["method"])
        self.assertEqual(cycle["hypotheses"], packet["research_cycles"][0]["hypotheses"])
        self.assertNotIn("hidden rationale sentinel", json.dumps(packet))

    def test_failed_execution_has_no_refutation_graph_edge(self):
        cycle = self.start()
        cycle = apply_cycle_event(cycle, {"kind": "reserve", "experiment_id": "e1", "request_id": "r1"}, self.root)
        cycle = apply_cycle_event(cycle, {"kind": "failure", "experiment_id": "e1", "request_id": "r1",
                                          "failure_kind": "implementation", "outcome": "broken shape"}, self.root)
        graph = cycle_graph(cycle, self.root)
        self.assertFalse(any(item["relation"] in {"supports", "contradicts"} for item in graph["edges"]))

    def test_novelty_comparison_is_not_novelty_proof(self):
        cycle = self.start()
        ref = write_ref(self.root, "primary-source.json", {"source": "local test source"})
        result = assess_cycle(cycle, self.root, {"novelty_comparison": {
            "scope": "one declared source", "search_cutoff": "2026-09-18", "difference": "unreviewed claimed difference",
            "limitations": "fixture only", "source_refs": [ref]}})
        self.assertEqual("comparison_recorded", result["novelty"]["status"])

    def test_observed_decision_requires_preregistered_mapping_and_measured_artifact(self):
        contract = json.loads((ROOT / "examples/statistical-decision-analysis/input.json").read_text())
        assumption_ref = write_ref(self.root, "assumptions.json", contract)
        payload = {"state_model_rationale": "Explicit exogenous states", "assumption_refs": [assumption_ref],
                   "decision_contract": contract}
        prior = dict(payload, observation_bindings=[{"cycle_experiment_id": "e1", "decision_experiment_id": "bounded-assay", "json_pointer": "/signal", "artifact_path": "measurement.json"}])
        prior_ref = write_ref(self.root, "prior-decision.json", prior)
        self.payload["evaluation"]["artifact_refs"].append(prior_ref)
        cycle = self.start()
        for kind in ("reserve", "running"):
            cycle = apply_cycle_event(cycle, {"kind": kind, "experiment_id": "e1", "request_id": "r1"}, self.root)
        measured_ref = write_ref(self.root, "measurement.json", {"accuracy": .5, "signal": "signal-1"})
        other_ref = write_ref(self.root, "alternative.json", {"accuracy": .5, "signal": "signal-2"})
        observations = [{"artifact_ref": ref, "json_pointer": "/accuracy", "value": .5} for ref in (measured_ref, other_ref)]
        receipt = execution_ref(self.root, cycle, "e1", observations)
        cycle = apply_cycle_event(cycle, {"kind": "complete", "experiment_id": "e1", "request_id": "r1",
                                         "outcome": "measured", "observations": observations, "execution_refs": [receipt]}, self.root)
        # Store every event through replay, as the normal CLI does.
        latest = load_cycle(self.root)
        for event in cycle["events"]:
            latest = apply_cycle_event(latest, event, self.root)
            save_cycle(latest, self.root)
            latest = load_cycle(self.root)
        payload["observed_outcome"] = {"cycle_experiment_id": "e1", "decision_experiment_id": "bounded-assay",
                                       "artifact_ref": measured_ref, "json_pointer": "/signal", "preregistered_decision_ref": prior_ref}
        result = finite_decision(latest, payload, self.root)
        posterior = result["observed_policy"]["conditional_policy"]["posterior"]
        self.assertAlmostEqual(6 / 7, posterior["mechanism-1"])
        altered = copy.deepcopy(payload)
        altered["observed_outcome"]["json_pointer"] = "/accuracy"
        with self.assertRaisesRegex(ValueError, "preregistered"):
            finite_decision(latest, altered, self.root)
        altered = copy.deepcopy(payload)
        altered["decision_contract"]["states"][0]["prior"] = .5
        altered["decision_contract"]["states"][1]["prior"] = .5
        with self.assertRaisesRegex(ValueError, "preregistration"):
            finite_decision(latest, altered, self.root)
        altered = copy.deepcopy(payload)
        altered["observed_outcome"]["artifact_ref"] = other_ref
        with self.assertRaisesRegex(ValueError, "preregistered"):
            finite_decision(latest, altered, self.root)


if __name__ == "__main__":
    unittest.main()
