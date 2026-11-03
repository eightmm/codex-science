import copy
from pathlib import Path
import unittest

from codex_science.campaign_execution import read_json
from codex_science.campaign_handoffs import screening_to_lead
from codex_science.virtual_screening import fingerprint


class CampaignHandoffTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.screen = read_json(root / "examples/virtual-screening-campaign/screening.json")
        self.handoff = read_json(root / "examples/campaign-execution/screening-to-lead.json")

    def test_handoff_preserves_scores_compounds_denominators_and_computational_kind(self):
        result = screening_to_lead(self.screen, self.handoff)
        self.assertEqual(result["lead_analysis"]["candidate_count"], 4)
        self.assertEqual(result["lead_analysis"]["proposal"]["selected"][0]["id"], "compound-1")
        prop = result["lead_input"]["candidates"][0]["properties"]["screening_score"]
        self.assertEqual(prop, {"value": -8.9, "unit": "synthetic-score-unit", "source_kind": "computed", "assay_id": "supplied_synthetic_energy"})
        self.assertIn("upstream_denominators", result)

    def test_stale_target_contract_or_input_refused(self):
        for key in ("source_input_sha256", "source_contract_sha256", "target_id"):
            contract = copy.deepcopy(self.handoff)
            contract[key] = "wrong"
            with self.subTest(key=key), self.assertRaises(ValueError):
                screening_to_lead(self.screen, contract)

    def test_test_partition_cannot_be_relabeled_prospective(self):
        self.handoff["selection_context"] = "prospective"
        with self.assertRaisesRegex(ValueError, "test-screen"):
            screening_to_lead(self.screen, self.handoff)

    def test_failed_upstream_controls_block_downstream_proposal(self):
        self.screen["controls"][0]["status"] = "failed"
        self.handoff["source_input_sha256"] = fingerprint(self.screen)
        result = screening_to_lead(self.screen, self.handoff)
        self.assertIsNone(result["lead_analysis"]["proposal"])
        self.assertEqual(result["lead_analysis"]["candidate_count"], 4)

    def test_external_properties_cannot_overwrite_score_or_change_molecular_identity(self):
        for values in ({"unknown": {}}, {"compound-1": {"screening_score": {"value": -100}}}):
            self.handoff["additional_properties"] = values
            with self.subTest(values=values), self.assertRaises(ValueError):
                screening_to_lead(self.screen, self.handoff)

    def test_non_evaluation_partition_is_retained_but_never_selected(self):
        row = copy.deepcopy(self.screen["compounds"][0])
        row.update(id="validation-only", chemical_identity="validation-identity", scaffold_group="validation-scaffold", partition="validation")
        self.screen["compounds"].append(row)
        self.screen["states"].append({"id": "validation-state", "compound_id": "validation-only", "state_identity": "validation-state-identity"})
        self.screen["planned_attempts"].append({"id": "validation-attempt", "state_id": "validation-state"})
        self.screen["results"].append({"id": "validation-attempt", "status": "ok", "score": -100})
        self.handoff["source_input_sha256"] = fingerprint(self.screen)
        result = screening_to_lead(self.screen, self.handoff)
        self.assertEqual(len(result["upstream_compounds"]), 5)
        self.assertEqual(result["excluded_partitions"][0]["id"], "validation-only")
        self.assertNotIn("validation-only", [x["id"] for x in result["lead_analysis"]["proposal"]["selected"]])
