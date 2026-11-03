import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

from codex_science.campaign_execution import (
    capture_runtime_identity, compare_runtime_identities, read_json, run_campaign,
)


class CampaignExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.state = self.root / "state"
        (self.workspace / "input.txt").write_text("3")
        (self.workspace / "first.py").write_text("from pathlib import Path\nPath('a.txt').write_text(str(int(Path('input.txt').read_text())*2))\n")
        (self.workspace / "second.py").write_text("from pathlib import Path\nPath('b.txt').write_text(str(int(Path('a.txt').read_text())+1))\n")
        self.payload = {"schema": "campaign-execution-v1", "review_paths": ["review.json"], "stages": [
            {"id": "first", "command": [sys.executable, "first.py"], "inputs": ["input.txt"], "code": ["first.py"], "outputs": ["a.txt"]},
            {"id": "second", "depends_on": ["first"], "command": [sys.executable, "second.py"], "inputs": ["a.txt"], "code": ["second.py"], "outputs": ["b.txt"]},
        ]}

    def run_pipeline(self, **kwargs):
        return run_campaign(self.payload, self.workspace, self.state, execute=True, **kwargs)

    def test_real_execution_reuse_and_changed_input_rerun_preserves_artifacts(self):
        planned = run_campaign(self.payload, self.workspace, self.state)
        self.assertFalse(planned["executed"])
        self.assertFalse(self.state.exists())
        first = self.run_pipeline()
        self.assertEqual(first["status"], "completed")
        self.assertEqual((self.workspace / "b.txt").read_text(), "7")
        reused = self.run_pipeline()
        self.assertEqual([s["status"] for s in reused["stages"].values()], ["reused", "reused"])
        (self.workspace / "input.txt").write_text("4")
        changed = self.run_pipeline()
        self.assertEqual(changed["status"], "completed")
        self.assertNotEqual(first["stages"]["first"]["job_id"], changed["stages"]["first"]["job_id"])
        self.assertEqual(changed["invalidated_review_receipts"], ["review.json"])
        self.assertEqual((self.workspace / "b.txt").read_text(), "9")
        self.assertIn("7", [p.read_text() for p in (self.state / "artifacts" / "second").glob("*/b.txt")])

    def test_selective_rerun_code_and_asset_change(self):
        self.payload["stages"].append({"id": "independent", "command": [sys.executable, "-c", "from pathlib import Path; Path('c.txt').write_text('constant')"], "outputs": ["c.txt"]})
        (self.workspace / "weights.bin").write_bytes(b"v1")
        self.payload["stages"][0]["assets"] = {"weights": "weights.bin"}
        self.run_pipeline()
        (self.workspace / "weights.bin").write_bytes(b"v2")
        changed = self.run_pipeline()
        self.assertEqual(changed["stages"]["independent"]["status"], "reused")
        self.assertEqual(changed["stages"]["first"]["status"], "completed")
        self.assertEqual(changed["stages"]["second"]["status"], "completed")
        with (self.workspace / "second.py").open("a") as stream:
            stream.write("# changed code\n")
        changed = self.run_pipeline()
        self.assertEqual(changed["stages"]["first"]["status"], "reused")
        self.assertEqual(changed["stages"]["second"]["status"], "completed")

    def test_interrupted_driver_resumes_existing_backend_job(self):
        (self.workspace / "first.py").write_text("import time\ntime.sleep(0.25)\nfrom pathlib import Path\nPath('a.txt').write_text('6')\n")
        pending = self.run_pipeline(wait_seconds=0.01)
        self.assertEqual(pending["stages"]["first"]["status"], "running")
        saved = read_json(self.state / "campaign.json")
        saved["stages"]["first"][-1].pop("job_id")
        saved["stages"]["first"][-1]["phase"] = "submitting"
        (self.state / "campaign.json").write_text(json.dumps(saved))
        resumed = self.run_pipeline()
        self.assertEqual(resumed["status"], "completed")
        self.assertEqual(resumed["stages"]["first"]["job_id"], pending["stages"]["first"]["job_id"])
        self.assertEqual(len(list((self.state / "backend" / "jobs").iterdir())), 2)

    def test_missing_submission_is_ambiguous_never_resubmitted(self):
        self.run_pipeline()
        saved = read_json(self.state / "campaign.json")
        saved["stages"]["first"][-1].update(phase="submitting", job_name="unmatched-reservation")
        (self.state / "campaign.json").write_text(json.dumps(saved))
        result = self.run_pipeline()
        self.assertEqual(result["stages"]["first"]["status"], "ambiguous")
        self.assertEqual(len(list((self.state / "backend" / "jobs").iterdir())), 2)

    def test_failed_stage_requires_explicit_retry_and_keeps_attempt(self):
        (self.workspace / "first.py").write_text("raise SystemExit(3)\n")
        self.assertEqual(self.run_pipeline()["stages"]["first"]["status"], "failed")
        self.assertEqual(self.run_pipeline()["stages"]["first"]["reason"], "explicit retry required")
        (self.workspace / "first.py").write_text("from pathlib import Path\nPath('a.txt').write_text('6')\n")
        self.assertEqual(self.run_pipeline(retry_failed=True)["status"], "completed")
        saved = read_json(self.state / "campaign.json")
        self.assertEqual([x["phase"] for x in saved["stages"]["first"]], ["failed", "completed"])

    def test_invalid_paths_cycles_collisions_and_missing_dependencies(self):
        cases = []
        for field, value in (("inputs", ["../outside"]), ("outputs", ["input.txt"]),
                             ("outputs", ["./input.txt"]), ("outputs", ["a//b.txt"]),
                             ("depends_on", ["second"])):
            item = copy.deepcopy(self.payload)
            item["stages"][0][field] = value
            cases.append(item)
        item = copy.deepcopy(self.payload)
        item["stages"][1]["depends_on"] = []
        cases.append(item)
        item = copy.deepcopy(self.payload)
        item["stages"][1]["outputs"] = ["a.txt"]
        cases.append(item)
        for item in cases:
            with self.subTest(item=item), self.assertRaises(ValueError):
                run_campaign(item, self.workspace, self.state)
        (self.workspace / "link").symlink_to(self.root)
        self.payload["stages"][0]["inputs"] = ["link/outside"]
        with self.assertRaises(ValueError):
            run_campaign(self.payload, self.workspace, self.state)

    def test_missing_or_tampered_output_is_not_reused(self):
        self.run_pipeline()
        (self.workspace / "a.txt").write_text("100")
        result = self.run_pipeline()
        self.assertEqual(result["stages"]["first"]["status"], "completed")
        self.assertEqual((self.workspace / "b.txt").read_text(), "7")

    def test_actual_runtime_identity_detects_changed_asset(self):
        asset = self.workspace / "model.bin"
        asset.write_bytes(b"one")
        first = capture_runtime_identity(sys.executable, {"model": str(asset)})
        asset.write_bytes(b"two")
        second = capture_runtime_identity(sys.executable, {"model": str(asset)})
        self.assertEqual(compare_runtime_identities(first, second)["changed"], ["assets"])
        with self.assertRaises(ValueError):
            capture_runtime_identity("missing-campaign-executable")

    def test_prior_output_cannot_satisfy_successful_no_output_attempt(self):
        self.run_pipeline()
        (self.workspace / "first.py").write_text("pass\n")
        result = self.run_pipeline()
        self.assertEqual(result["stages"]["first"]["status"], "failed")
        self.assertEqual(result["stages"]["second"]["status"], "blocked")
        self.assertFalse((self.workspace / "a.txt").exists())
        self.assertIn("6", [p.read_text() for p in (self.state / "artifacts" / "first").glob("*/a.txt")])

    def test_stdout_analysis_handoff_and_resume(self):
        self.payload = {"schema": "campaign-execution-v1", "stages": [{"id": "json-analysis",
            "command": [sys.executable, "-c", "import json; print(json.dumps({'value': 4}))"],
            "outputs": ["result.json"], "stdout_output": "result.json"}]}
        self.assertEqual(self.run_pipeline()["status"], "completed")
        self.assertEqual(json.loads((self.workspace / "result.json").read_text()), {"value": 4})
        self.assertEqual(self.run_pipeline()["stages"]["json-analysis"]["status"], "reused")

    def test_removed_active_stage_cannot_race_reassigned_outputs(self):
        (self.workspace / "first.py").write_text("import time\ntime.sleep(0.2)\nfrom pathlib import Path\nPath('a.txt').write_text('6')\n")
        self.run_pipeline(wait_seconds=0.01)
        old_plan = copy.deepcopy(self.payload)
        self.payload["stages"][0]["id"] = "renamed"
        self.payload["stages"][1]["depends_on"] = ["renamed"]
        with self.assertRaisesRegex(ValueError, "unresolved stage removed"):
            self.run_pipeline()
        self.payload = old_plan
        self.assertEqual(self.run_pipeline()["status"], "completed")

    def test_asset_alias_and_stdout_overwrite_are_rejected_before_mutation(self):
        for change in ({"assets": {"weight": "a.txt"}}, {"stdout_output": "input.txt"}):
            plan = copy.deepcopy(self.payload)
            plan["stages"][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                run_campaign(plan, self.workspace, self.state, execute=True)
            self.assertEqual((self.workspace / "input.txt").read_text(), "3")
