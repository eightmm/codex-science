import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from codex_science.discovery import attach_cycle, finite_decision
from codex_science.discovery_evidence import assess_cycle, classify_revisions, cycle_graph
from codex_science.discovery_synthesis import summarize_cycle
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

    def test_assessment_checks_finding_evidence_outside_review_coverage(self):
        from codex_science.artifacts import add_artifact, validate_bundle

        cycle = self.start()
        ref = self.review_ref(cycle, ["method"])
        path = self.root / "manifest.json"
        manifest = json.loads(path.read_text())
        add_artifact(manifest, ref["path"], kind="review-receipt", sha256=ref["sha256"])
        counter = write_ref(self.root, "counter.json", {"count": 0})
        add_artifact(manifest, counter["path"], kind="data", sha256=counter["sha256"])
        original = json.loads((self.root / ref["path"]).read_text())
        for registered in (True, False):
            for stale in (True, False):
                with self.subTest(registered=registered, stale=stale):
                    receipt = copy.deepcopy(original)
                    receipt.pop("fingerprint")
                    receipt["findings"] = [{"id": "counter", "code": "counter-check", "severity": "major",
                                            "message": "Counter checked", "resolution_status": "resolved",
                                            "evidence": [{"artifact_path": counter["path"],
                                                          "artifact_sha256": "0" * 64 if stale else counter["sha256"]}]}]
                    ref = write_ref(self.root, ref["path"], build_review_receipt(**{
                        key: value for key, value in receipt.items() if key != "schema_version"}))
                    manifest["artifacts"] = [item for item in manifest["artifacts"] if item["path"] != ref["path"]]
                    if registered:
                        add_artifact(manifest, ref["path"], kind="review-receipt", sha256=ref["sha256"])
                    path.write_text(json.dumps(manifest))
                    bundle = validate_bundle(manifest, self.root)
                    bundle_stale = any(item["code"] == "stale-review-receipt" for item in bundle["advanced_findings"])
                    self.assertEqual(registered and stale, bundle_stale)
                    result = assess_cycle(cycle, self.root, {} if registered else {"review_refs": [ref]})
                    method = result["review_axes"]["method"]
                    self.assertEqual("pending" if stale else "passed_in_review_scope", method["status"])
                    self.assertEqual(not stale, method["receipts"][0]["qualified_coverage"])
                    self.assertEqual(stale, bool(method["receipts"][0]["integrity_findings"]))
        receipt["findings"][0]["evidence"][0]["artifact_sha256"] = "0" * 64
        ref = write_ref(self.root, ref["path"], build_review_receipt(**{
            key: value for key, value in receipt.items() if key != "schema_version"}))
        path.unlink()
        self.assertEqual("passed_in_review_scope", assess_cycle(cycle, self.root, {"review_refs": [ref]})["review_axes"]["method"]["status"])

    def test_assessment_uses_the_bundle_model_registry_digest(self):
        from codex_science.artifacts import validate_bundle
        from codex_science.model_registry_v2 import load_registry_v2, registry_sha256

        cycle = self.start()
        ref = self.review_ref(cycle, ["method"])
        original = json.loads((self.root / ref["path"]).read_text())
        current = registry_sha256(load_registry_v2(ROOT / "models/registry-v2.json"))
        for digest in (current, "0" * 64):
            with self.subTest(current=digest == current):
                receipt = copy.deepcopy(original)
                receipt.pop("fingerprint")
                receipt["covered_registry_sha256"] = digest
                ref = write_ref(self.root, ref["path"], build_review_receipt(**{
                    key: value for key, value in receipt.items() if key != "schema_version"}))
                manifest_path = self.root / "manifest.json"
                manifest = json.loads(manifest_path.read_text())
                manifest["artifacts"] = [item for item in manifest["artifacts"] if item["path"] != ref["path"]]
                manifest["artifacts"].append({**ref, "kind": "review-receipt"})
                manifest_path.write_text(json.dumps(manifest))
                bundle = validate_bundle(manifest, self.root)
                method = assess_cycle(cycle, self.root)["review_axes"]["method"]
                self.assertEqual("passed_in_review_scope" if digest == current else "pending", method["status"])
                self.assertEqual(bundle["advanced_findings"], method["receipts"][0]["integrity_findings"])

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

    def test_assess_adds_revision_outcomes_without_changing_prior_keys(self):
        result = assess_cycle(self.start(), self.root)
        self.assertEqual({"schema_version", "cycle_hash", "revision", "execution_integrity", "review_axes", "novelty",
                          "review_scope", "method_effects", "evidence_boundary", "revision_outcomes"}, set(result))
        self.assertEqual([], result["revision_outcomes"]["revisions"])

    def test_rewritten_snapshot_with_stale_cycle_hash_is_refused_by_views(self):
        cycle = self.start()
        cycle["problem"]["observed"] = "edited after saving"
        snapshot = self.root / "discovery/revisions/000001.json"
        snapshot.write_text(json.dumps(cycle))
        for view in (assess_cycle, summarize_cycle):
            with self.subTest(view=view.__name__), self.assertRaisesRegex(ValueError, "research cycle hash mismatch"):
                view(cycle, self.root)
        with self.assertRaisesRegex(ValueError, "research cycle hash mismatch"):
            load_cycle(self.root)


class RevisionOutcomeTests(unittest.TestCase):
    LESSON = {"observation": "o", "interpretation": "i", "limitation": "l", "change": "c", "next_test": "n"}

    def classify(self, state, **fields):
        event = dict({"kind": "revise", "source_experiment_id": "e1"}, **fields)
        cycle = {"experiments": [{"id": "e1", "state": state}], "events": [{"kind": "reserve"}, event]}
        return classify_revisions(cycle)["revisions"][0]

    def test_each_category_and_event_index(self):
        method = [{"id": "m2"}]
        cases = [
            ("completed", {"methods": method}, "insufficient_evidence"),
            ("completed", {"lesson": self.LESSON}, "insufficient_evidence"),
            ("completed", {"lesson": self.LESSON, "methods": []}, "insufficient_evidence"),
            ("failed", {"lesson": self.LESSON, "experiments": [{"id": "x", "retry_of": "e1"}]}, "repetition"),
            ("failed", {"lesson": self.LESSON, "methods": method}, "necessary_repair_candidate"),
            ("failed", {"lesson": self.LESSON, "experiments": [{"id": "x"}]}, "necessary_repair_candidate"),
            ("completed", {"lesson": self.LESSON, "hypotheses": [{"id": "h"}]}, "substantive_progress_candidate"),
            ("completed", {"lesson": self.LESSON, "experiments": [{"id": "x"}]}, "substantive_progress_candidate"),
            ("completed", {"lesson": self.LESSON, "methods": method, "experiments": [{"id": "x", "retry_of": "e1"}]},
             "substantive_progress_candidate"),
        ]
        for state, fields, expected in cases:
            with self.subTest(state=state, fields=sorted(fields), expected=expected):
                item = self.classify(state, **fields)
                self.assertEqual(expected, item["category"])
                self.assertEqual((1, "e1", state), (item["event_index"], item["source_experiment_id"], item["source_state"]))
                self.assertTrue(item["basis"])

    def test_rule_precedence_and_unresolved_source(self):
        self.assertEqual("insufficient_evidence", self.classify("failed", methods=[{"id": "m2"}])["category"])
        self.assertEqual("repetition", self.classify("completed", lesson=self.LESSON,
                                                      experiments=[{"id": "x", "retry_of": "e1"}])["category"])
        self.assertEqual("insufficient_evidence", self.classify("planned", lesson=self.LESSON, methods=[{"id": "m"}])["category"])

    def test_counts_boundary_and_empty(self):
        empty = classify_revisions({"experiments": [], "events": []})
        self.assertEqual([], empty["revisions"])
        self.assertEqual(0, sum(empty["counts"].values()))
        self.assertIn("not judgments", empty["evidence_boundary"])
        cycle = {"experiments": [{"id": "e1", "state": "failed"}],
                 "events": [{"kind": "revise", "source_experiment_id": "e1", "lesson": self.LESSON, "methods": [{"id": "m"}]},
                            {"kind": "revise", "source_experiment_id": "e1"}]}
        counts = classify_revisions(cycle)["counts"]
        self.assertEqual((1, 1), (counts["necessary_repair_candidate"], counts["insufficient_evidence"]))


if __name__ == "__main__":
    unittest.main()
