import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from codex_science.checkpoints import (
    abandon_checkpoint, block_checkpoint, create_checkpoint, request_decision,
    wait_checkpoint, verify_criterion, advance_checkpoint, record_review, complete_checkpoint,
)
from codex_science.completion_report import report_completion


NOW = datetime(2026, 10, 21, tzinfo=timezone.utc)


class CompletionReportTests(unittest.TestCase):
    def make(self, root, name, state="active"):
        run = root / name
        create_checkpoint(run, goal="goal", deliverable="result", done_criteria=["criterion"], steps=[("s", "step")], next_action="continue", session_key=(name.encode().hex() + "0" * 64)[:64])
        if state == "gate": request_decision(run, questions=["approve?"], reason="approval")
        elif state == "wait": wait_checkpoint(run, reason="external", next_action="resume", poll_interval_seconds=5, terminal_rule="event")
        elif state == "block": block_checkpoint(run, reason="blocked", next_action="fix")
        elif state == "abandon": abandon_checkpoint(run, reason="stopped")
        return run

    def test_states_invalid_tiers_inconclusive_symlinks_and_determinism(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "runs"; root.mkdir()
            self.make(root, "active"); self.make(root, "gate", "gate"); self.make(root, "wait", "wait")
            self.make(root, "block", "block"); self.make(root, "abandon", "abandon")
            self.make(root, "stale")
            stale_record = json.loads((root / "stale" / "checkpoint.json").read_text()); stale_record["updated_at"] = "2020-01-01T00:00:00Z"; (root / "stale" / "checkpoint.json").write_text(json.dumps(stale_record))
            fresh = json.loads((root / "active" / "checkpoint.json").read_text()); fresh["rigor"] = {"tier": "full", "history": [{"tier": "full", "at": fresh["updated_at"], "reason": "test"}]}; (root / "active" / "checkpoint.json").write_text(json.dumps(fresh))
            (root / "active" / "manifest.json").write_text(json.dumps({"claims": [{"status": "inconclusive"}]}))
            (root / "bad").mkdir(); (root / "bad" / "checkpoint.json").write_text("{")
            outside = Path(tmp) / "outside"; outside.mkdir(); (outside / "checkpoint.json").write_text("{}"); (root / "linked").symlink_to(outside, target_is_directory=True)
            a = report_completion(root, now=NOW, stale_after=timedelta(days=1)); b = report_completion(root, now=NOW, stale_after=timedelta(days=1))
            self.assertEqual(a, b)
            by_name = {r["run_id"]: r for r in a["runs"]}
            self.assertEqual({"active": "active", "gate": "approval_required", "wait": "waiting_external", "block": "blocked", "abandon": "abandoned", "stale": "stale_active", "bad": "invalid"}, {k: by_name[k]["outcome"] for k in ("active", "gate", "wait", "block", "abandon", "stale", "bad")})
            self.assertEqual("full", by_name["active"]["tier"])
            self.assertNotIn("linked", by_name)

    def test_completed_and_terminal_inconclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = self.make(root, "done")
            (run / "evidence.txt").write_text("evidence")
            verify_criterion(run, "criterion-1", ["evidence.txt"])
            advance_checkpoint(run, completed_step="s", next_step=None, next_action="finishing")
            (run / "review.json").write_text(json.dumps({"status": "passed", "reviewer": "reviewer", "independent": True, "findings": []}))
            record_review(run, artifact_ref="review.json")
            complete_checkpoint(run)
            manifest = run / "manifest.json"
            manifest.write_text(json.dumps({"claims": [{"status": "conflicting"}]}))
            report = report_completion(root, now=NOW, stale_after=timedelta(days=1))
            self.assertEqual("terminal_inconclusive", report["runs"][0]["outcome"])
            manifest.unlink()
            self.assertEqual("completed", report_completion(root, now=NOW, stale_after=timedelta(days=1))["runs"][0]["outcome"])

    def test_cli_formats_and_no_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.make(root, "run")
            before = {str(p.relative_to(root)): p.read_bytes() if p.is_file() else None for p in root.rglob("*")}
            script = Path(__file__).resolve().parents[1] / "scripts" / "report_completion.py"
            for fmt in ("json", "markdown"):
                result = subprocess.run([sys.executable, str(script), str(root), "--now", NOW.isoformat(), "--format", fmt], capture_output=True, text=True)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertTrue(json.loads(result.stdout)["schema"] == "completion-report-v1" if fmt == "json" else result.stdout.startswith("# Completion report"))
                if fmt == "json": self.assertTrue(result.stdout.endswith("\n"))
            after = {str(p.relative_to(root)): p.read_bytes() if p.is_file() else None for p in root.rglob("*")}
            self.assertEqual(before, after)

    def test_malformed_tiers_and_invalid_denominator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, tier in (("number-tier", 7), ("unknown-tier", "quick")):
                run = self.make(root, name)
                record = json.loads((run / "checkpoint.json").read_text())
                record["rigor"] = {"tier": tier}
                (run / "checkpoint.json").write_text(json.dumps(record))
            self.make(root, "active")
            report = report_completion(root, now=NOW, stale_after=timedelta(days=1))
            records = {record["run_id"]: record for record in report["runs"]}
            for name in ("number-tier", "unknown-tier"):
                self.assertEqual("invalid", records[name]["outcome"])
                self.assertEqual("invalid_record", records[name]["stop_reason"]["code"])
                self.assertIn("rigor", records[name]["invalid"])
            self.assertEqual(2, report["aggregate"]["completion_denominator"])
            self.assertEqual(0, report["aggregate"]["completion_numerator"])
            self.assertEqual(1, report["aggregate"]["by_outcome"]["in_progress"])
            self.assertEqual(1, report["aggregate"]["in_progress"])
            self.assertNotIn("active", report["aggregate"]["by_outcome"])
            self.assertIn("invalid runs count as non-completions", report["aggregate"]["denominator_rule"])

    def test_legacy_stray_wait_and_review_fragment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = self.make(root, "legacy")
            record = json.loads((run / "checkpoint.json").read_text())
            record["schema_version"] = 2
            record["done_criteria"] = [item["text"] for item in record["done_criteria"]]
            for field in ("continuation_budget", "outer_goal", "review_receipt", "wait", "termination_reason", "revision"):
                record.pop(field, None)
            record["wait"] = ["malformed legacy extra"]
            (run / "checkpoint.json").write_text(json.dumps(record))
            legacy = report_completion(root, now=NOW, stale_after=timedelta(days=1))["runs"][0]
            self.assertEqual("active", legacy["outcome"])
            self.assertEqual("legacy", legacy["tier"])

            completed = self.make(root, "reviewed")
            (completed / "evidence.txt").write_text("evidence")
            verify_criterion(completed, "criterion-1", ["evidence.txt"])
            advance_checkpoint(completed, completed_step="s", next_step=None, next_action="finishing")
            (completed / "review.json").write_text(json.dumps({"status": "passed", "reviewer": "reviewer", "independent": True, "findings": []}))
            record_review(completed, artifact_ref="review.json")
            complete_checkpoint(completed)
            receipt_record = json.loads((completed / "checkpoint.json").read_text())
            receipt_record["review_receipt"]["artifact_ref"] = "review.json#review"
            (completed / "checkpoint.json").write_text(json.dumps(receipt_record))
            reviewed = {record["run_id"]: record for record in report_completion(root, now=NOW, stale_after=timedelta(days=1))["runs"]}["reviewed"]
            self.assertIn("review.json", reviewed["evidence_refs"])
            self.assertNotIn("review.json#review", reviewed["evidence_refs"])

    def test_cli_rejects_missing_root_and_nonpositive_staleness_as_json(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "report_completion.py"
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing"
            result = subprocess.run([sys.executable, str(script), str(missing)], capture_output=True, text=True)
            self.assertEqual(2, result.returncode)
            self.assertIn("does not exist", json.loads(result.stderr)["error"])
            root = Path(tmp)
            result = subprocess.run([sys.executable, str(script), str(root), "--stale-after-hours", "nan"], capture_output=True, text=True)
            self.assertEqual(2, result.returncode)
            self.assertIn("finite and positive", json.loads(result.stderr)["error"])
            file_path = root / "file"; file_path.write_text("not a directory")
            result = subprocess.run([sys.executable, str(script), str(file_path)], capture_output=True, text=True)
            self.assertEqual(2, result.returncode)
            self.assertIn("not a directory", json.loads(result.stderr)["error"])


if __name__ == "__main__":
    unittest.main()
