import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "authored-skills/binder-design-campaign"
SCRIPT = ROOT / "scripts/check_binder_campaign.py"
SPEC = importlib.util.spec_from_file_location("binder_campaign_checker", SCRIPT)
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


class BinderDesignCampaignTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory())) / "campaign"
        shutil.copytree(ROOT / "examples/binder-design-campaign", self.directory)
        self.record = json.loads((self.directory / "campaign.json").read_text())

    def save(self, name, value):
        path = self.directory / name
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if name == "contract.json":
            self.record["contract"]["sha256"] = digest
        else:
            for ref in self.record["artifacts"].values():
                if ref["path"] == name:
                    ref["sha256"] = digest

    def edit(self, name, change):
        value = json.loads((self.directory / name).read_text())
        change(value)
        self.save(name, value)

    def check(self):
        path = self.directory / "campaign.json"
        path.write_text(json.dumps(self.record))
        return CHECKER.validate_campaign(path)

    def recorded_contract(self):
        # Exercise recorded-mode policy with local test records, never a model run.
        self.record["mode"] = "recorded_campaign"
        for ref in list(self.record["artifacts"].values()):
            self.edit(ref["path"], lambda payload: payload.pop("synthetic", None))

    def test_fixture_preserves_failed_and_missing_denominators_without_scientific_claim(self):
        result = self.check()
        self.assertEqual("synthetic_only", result["outcome"])
        self.assertEqual({"attempted": 3, "generated": 2, "failed": 1, "candidates": 3,
                          "retained": 1, "excluded": 1, "unevaluable": 1}, result["funnel"])

    def test_add_method_without_changing_route_code(self):
        self.edit("method.json", lambda m: m.update(id="new-documented-vhh-method"))
        self.edit("contract.json", lambda c: c.update(route="new-documented-vhh-method"))
        self.assertEqual("new-documented-vhh-method", self.check()["route"])

    def test_discovery_does_not_admit_unreviewed_or_incompatible_method(self):
        self.edit("method.json", lambda m: m.update(review_state="discovered"))
        with self.assertRaisesRegex(ValueError, "not admitted"):
            self.check()
        self.edit("method.json", lambda m: m.update(review_state="documented", formats=["minibinder"]))
        with self.assertRaisesRegex(ValueError, "incompatible"):
            self.check()

    def test_seed_methods_are_usable_only_for_documented_formats(self):
        seeds = json.loads((SKILL / "references/methods.json").read_text())["methods"]
        for method in seeds:
            with self.subTest(method=method["id"]):
                self.assertEqual("not_run", method["execution"])
                self.save("method.json", method)
                self.edit("contract.json", lambda c: c.update(route=method["id"]))
                if "vhh" in method["formats"]:
                    self.assertEqual("vhh", self.check()["binder_format"])
                else:
                    with self.assertRaisesRegex(ValueError, "incompatible"):
                        self.check()

    def test_minibinder_routes_do_not_require_an_antibody_scaffold(self):
        seeds = json.loads((SKILL / "references/methods.json").read_text())["methods"]
        for method in (m for m in seeds if "minibinder" in m["formats"]):
            with self.subTest(method=method["id"]):
                self.save("method.json", method)
                self.edit("contract.json", lambda c: c.update(binder_format="minibinder", route=method["id"]))
                self.assertEqual("minibinder", self.check()["binder_format"])

    def test_paired_fv_requires_light_chain_and_its_cdr_contract(self):
        self.edit("contract.json", lambda c: c.update(binder_format="paired_fv"))
        with self.assertRaisesRegex(ValueError, "H/L"):
            self.check()
        for name in ("scaffold.json", "candidate-1.json", "candidate-2.json", "candidate-3.json"):
            def add_light(payload):
                light = json.loads(json.dumps(payload["residues"]))
                for row in light:
                    row["chain"] = "L"
                    row["source_id"] = row["source_id"].replace("H", "L")
                    row["region"] = row["region"].replace("H", "L")
                payload["residues"].extend(light)
            self.edit(name, add_light)
        def add_map(payload):
            rows = json.loads(json.dumps(payload["scaffold_residue_map"]))
            for row in rows:
                for key in row:
                    row[key] = row[key].replace("H", "L")
            payload["scaffold_residue_map"].extend(rows)
        self.edit("mapping.json", add_map)
        self.edit("contract.json", lambda c: c["cdr_lengths"].update({"L1": [2, 2], "L2": [1, 1], "L3": [2, 3]}))
        self.assertEqual("paired_fv", self.check()["binder_format"])

    def test_framework_cdr_and_source_mapping_violations(self):
        for name, change, message in (
            ("candidate-1.json", lambda p: p["residues"][0].update(aa="A"), "framework/protected"),
            ("candidate-1.json", lambda p: p["residues"][2].update(source_id="original-H:2"), "duplicate source"),
            ("contract.json", lambda p: p["cdr_lengths"].update(H3=[3, 3]), "CDR length"),
            ("mapping.json", lambda p: p["scaffold_residue_map"].pop(), "mapping loss"),
            ("method.json", lambda p: p.update(framework_cdr_aware=False), "framework/CDR"),
        ):
            with self.subTest(message=message):
                before = (self.directory / name).read_text()
                self.edit(name, change)
                with self.assertRaisesRegex(ValueError, message):
                    self.check()
                self.save(name, json.loads(before))

    def test_stale_hash_and_confined_paths(self):
        (self.directory / "target.json").write_text("tampered")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.check()
        self.record["artifacts"]["target"]["path"] = "../outside"
        with self.assertRaisesRegex(ValueError, "inside campaign"):
            self.check()
        outside = self.directory.parent / "outside.json"
        outside.write_text("private fixture")
        (self.directory / "escape.json").symlink_to(outside)
        self.record["artifacts"]["target"]["path"] = "escape.json"
        with self.assertRaisesRegex(ValueError, "escapes"):
            self.check()

    def test_framework_reordering_and_displaced_cdr_are_refused(self):
        original = json.loads((self.directory / "candidate-1.json").read_text())
        changed = json.loads(json.dumps(original))
        rows = changed["residues"]
        rows[3], rows[5] = rows[5], rows[3]
        for position, row in enumerate(rows, 1):
            row["position"] = position
        self.save("candidate-1.json", changed)
        with self.assertRaisesRegex(ValueError, "source residue order"):
            self.check()
        changed = json.loads(json.dumps(original))
        row = changed["residues"].pop(1)
        row["source_id"] = None
        changed["residues"].append(row)
        for position, row in enumerate(changed["residues"], 1):
            row["position"] = position
        self.save("candidate-1.json", changed)
        with self.assertRaisesRegex(ValueError, "segment order"):
            self.check()

    def test_authorized_cdr_insertion_preserves_source_order(self):
        payload = json.loads((self.directory / "candidate-1.json").read_text())
        payload["residues"].insert(8, {"chain": "H", "position": 9, "source_id": None,
                                     "aa": "A", "region": "H3", "protected": False})
        for position, row in enumerate(payload["residues"], 1):
            row["position"] = position
        self.save("candidate-1.json", payload)
        self.assertEqual("synthetic_only", self.check()["outcome"])

    def test_broken_lineage_lost_denominator_and_missing_metric(self):
        candidate = self.record["candidates"][0]
        candidate["parent_artifact"] = "backbone-2"
        with self.assertRaisesRegex(ValueError, "parent lineage"):
            self.check()
        candidate["parent_artifact"] = "backbone-1"
        self.record["funnel"]["attempted"] = 2
        with self.assertRaisesRegex(ValueError, "denominator"):
            self.check()
        self.record["funnel"]["attempted"] = 3
        self.edit("candidate-1.json", lambda p: p["metrics"].clear())
        with self.assertRaisesRegex(ValueError, "frozen filters"):
            self.check()

    def test_failed_essential_control_is_retained_but_blocks_positive_screen(self):
        self.recorded_contract()
        self.record["controls"][0]["status"] = "failed"
        with self.assertRaisesRegex(ValueError, "control evidence mismatch"):
            self.check()
        self.edit("positive-control.json", lambda p: p.update(status="failed"))
        self.assertEqual("controls_failed", self.check()["outcome"])
        self.record["claims"][1]["status"] = "supported"
        with self.assertRaisesRegex(ValueError, "unsupported computational"):
            self.check()

    def test_zero_survivors_is_an_honest_result(self):
        self.recorded_contract()
        self.edit("candidate-1.json", lambda p: p["metrics"].update(interface_proxy=0.2))
        self.record["candidates"][0].update(status="excluded", reason="Below frozen filter")
        self.record["funnel"].update(retained=0, excluded=2)
        self.assertEqual("no_survivors", self.check()["outcome"])

    def test_conditioned_or_same_model_rescore_is_not_distinct_support(self):
        self.edit("contract.json", lambda c: c.update(validation_support="distinct-model"))
        with self.assertRaisesRegex(ValueError, "false distinct"):
            self.check()
        self.edit("contract.json", lambda c: c["models"]["validation"].update(conditioned=False))
        self.check()
        self.edit("contract.json", lambda c: c["models"]["validation"].update(sha256=c["models"]["design"]["sha256"]))
        with self.assertRaisesRegex(ValueError, "false distinct"):
            self.check()

    def test_invalid_numbers_budgets_and_experimental_claims_are_refused(self):
        self.edit("contract.json", lambda c: c["budget"].update(max_attempts=True))
        with self.assertRaisesRegex(ValueError, "budget"):
            self.check()
        self.edit("contract.json", lambda c: c["budget"].update(max_attempts=3))
        self.edit("candidate-1.json", lambda p: p["metrics"].update(interface_proxy=float("nan")))
        with self.assertRaisesRegex(ValueError, "non-finite"):
            self.check()
        self.edit("candidate-1.json", lambda p: p["metrics"].update(interface_proxy=0.8))
        self.record["claims"].append({"kind": "experimental_binding", "status": "supported"})
        with self.assertRaisesRegex(ValueError, "unsupported claim"):
            self.check()

    def test_cli_is_read_only_and_reports_synthetic_scope(self):
        before = {p.name: p.read_bytes() for p in self.directory.iterdir()}
        result = subprocess.run([sys.executable, str(SCRIPT), str(self.directory / "campaign.json")],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("synthetic_only", json.loads(result.stdout)["outcome"])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.directory.iterdir()})

    def test_fixture_cannot_be_relabelled_as_executed_or_pilot_verified(self):
        self.record["mode"] = "recorded_campaign"
        with self.assertRaisesRegex(ValueError, "synthetic artifact mislabeled"):
            self.check()
        self.record["mode"] = "synthetic_fixture"
        self.edit("method.json", lambda m: m.update(review_state="pilot_verified"))
        with self.assertRaisesRegex(ValueError, "cannot be pilot verified"):
            self.check()


if __name__ == "__main__":
    unittest.main()
