from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from codex_science.binder_developability import analyze_binder_developability
from codex_science.virtual_screening import fingerprint

ROOT = Path(__file__).resolve().parents[1]


class BinderDevelopabilityTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / "examples/binder-developability/input.json").read_text())

    def freeze(self):
        self.data["contract_sha256"] = fingerprint(self.data["contract"])

    def test_sequence_observations_panel_and_all_candidates(self):
        result = analyze_binder_developability(self.data)
        self.assertEqual(result, json.loads((ROOT / "examples/binder-developability/expected.json").read_text()))
        self.assertEqual(result["candidate_count"], 2)
        self.assertEqual(result["retained_count"], 1)
        self.assertEqual(result["candidates"][1]["chain_observations"][0]["nglyco_sequons"], [{"position": 24, "sequence": "NAT"}])
        self.assertEqual(result["candidates"][0]["panel"]["margins"]["synthetic-off-target"], 6)

    def test_failed_and_absent_controls_do_not_erase_panel(self):
        for controls in ([], [{"id": "failed", "passed": False}]):
            self.data["controls"] = controls
            result = analyze_binder_developability(self.data)
            self.assertEqual(result["retained_count"], 0)
            self.assertEqual(result["candidates"][0]["panel"]["status"], "computed")
            self.assertFalse(result["candidates"][0]["panel"]["qualified_margin_comparison"])

    def test_framework_length_and_chain_identity(self):
        for mutation in (lambda d: d["candidates"][0]["chains"].update(H="A" + d["candidates"][0]["chains"]["H"][1:]),
                         lambda d: d["candidates"][0]["chains"].update(H=d["candidates"][0]["chains"]["H"] + "A"),
                         lambda d: d["candidates"][0]["chains"].update(L="AAA")):
            data = copy.deepcopy(self.data)
            mutation(data)
            with self.assertRaises(ValueError):
                analyze_binder_developability(data)

    def test_panel_endpoint_and_construct_identity(self):
        for field in ("construct_id", "assay_id", "unit", "source_kind", "metric", "target_id"):
            data = copy.deepcopy(self.data)
            data["candidates"][0]["panel_results"][0][field] = "wrong"
            with self.subTest(field=field), self.assertRaises(ValueError):
                analyze_binder_developability(data)

    def test_missing_off_target_is_unavailable_not_selective(self):
        self.data["candidates"][0]["panel_results"].pop()
        result = analyze_binder_developability(self.data)
        self.assertEqual(result["candidates"][0]["panel"]["status"], "unavailable")
        self.assertFalse(result["candidates"][0]["retained"])

    def test_lower_is_stronger_direction_and_predicted_panels(self):
        self.data["contract"]["panel"].update(direction="lower", source_kind="predicted")
        for row in self.data["candidates"]:
            for value in row["panel_results"]:
                value["source_kind"] = "predicted"
                value["value"] = -value["value"]
        self.freeze()
        result = analyze_binder_developability(self.data)
        self.assertEqual(result["candidates"][0]["panel"]["margins"]["synthetic-off-target"], 6)
        self.assertEqual(result["candidates"][0]["panel"]["source_kind"], "predicted")

    def test_duplicate_panel_and_construct_sequence_rejected(self):
        mutations = [lambda d: d["candidates"][0]["panel_results"].append(copy.deepcopy(d["candidates"][0]["panel_results"][0])),
                     lambda d: d["candidates"][1].update(construct_id=d["candidates"][0]["construct_id"]),
                     lambda d: d["candidates"][1].update(chains=d["candidates"][0]["chains"])]
        for mutation in mutations:
            data = copy.deepcopy(self.data)
            mutation(data)
            with self.assertRaises(ValueError):
                analyze_binder_developability(data)

    def test_nglyco_overlaps_and_no_cross_chain_motifs(self):
        data = {"schema_version": 1, "contract": {"binder_class": "minibinder", "target_id": "T", "limits": {}},
                "controls": [{"id": "C", "passed": True}], "candidates": [{"id": "A", "construct_id": "A", "chains": {"A": "NNST", "B": "NN", "C": "ST"}}]}
        data["contract_sha256"] = fingerprint(data["contract"])
        result = analyze_binder_developability(data)
        self.assertEqual(result["candidates"][0]["nglyco_sequon_count"], 2)
        self.assertEqual(result["candidates"][0]["panel"]["status"], "unavailable")

    def test_renamed_chains_do_not_hide_duplicate_molecular_sequences(self):
        data = {"schema_version": 1, "contract": {"binder_class": "minibinder", "target_id": "T"},
                "controls": [{"id": "C", "passed": True}], "candidates": [
                    {"id": "A", "construct_id": "A", "chains": {"A": "ACDE"}},
                    {"id": "B", "construct_id": "B", "chains": {"Z": "ACDE"}}]}
        data["contract_sha256"] = fingerprint(data["contract"])
        with self.assertRaisesRegex(ValueError, "duplicate binder sequence"):
            analyze_binder_developability(data)

    def test_nonfinite_unknown_metadata_is_rejected_by_api_and_cli(self):
        for value in (float("nan"), float("inf"), -float("inf")):
            self.data["candidates"][0]["extra"] = {"measurement": value}
            with self.assertRaises(ValueError):
                analyze_binder_developability(self.data)
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "bad.json"
                path.write_text(json.dumps(self.data))
                result = subprocess.run([sys.executable, str(ROOT / "scripts/analyze_binder_developability.py"), str(path)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 1)
                self.assertIn("nonfinite JSON", json.loads(result.stdout)["error"])
                self.assertFalse(result.stderr)

    def test_invalid_sequence_numbers_and_stale_contract(self):
        for sequence in ("", "AAA*", "aaA", "XAA"):
            data = copy.deepcopy(self.data)
            data["candidates"][0]["chains"]["H"] = sequence
            with self.assertRaises(ValueError):
                analyze_binder_developability(data)
        for value in (float("nan"), float("inf"), True, 10**1000):
            data = copy.deepcopy(self.data)
            data["candidates"][0]["panel_results"][0]["value"] = value
            with self.assertRaises(ValueError):
                analyze_binder_developability(data)
        self.data["contract"]["limits"]["max_nglyco_sequons"] = 99
        with self.assertRaisesRegex(ValueError, "hash"):
            analyze_binder_developability(self.data)

    def test_input_unchanged_and_cli_foreign_cwd_duplicate_keys(self):
        original = copy.deepcopy(self.data)
        analyze_binder_developability(self.data)
        self.assertEqual(self.data, original)
        with tempfile.TemporaryDirectory() as temporary:
            script = ROOT / "scripts/analyze_binder_developability.py"
            result = subprocess.run([sys.executable, str(script), str(ROOT / "examples/binder-developability/input.json")], cwd=temporary, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["retained_count"], 1)
            path = Path(temporary) / "bad.json"
            path.write_text('{"schema_version":1,"schema_version":2}')
            result = subprocess.run([sys.executable, str(script), str(path)], cwd=temporary, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("duplicate JSON key", json.loads(result.stdout)["error"])
            self.assertFalse(result.stderr)
