import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from pathlib import Path

from codex_science.checkpoints import (
    advance_checkpoint, budget_status, create_checkpoint, escalate_checkpoint,
    finish_partial, load_checkpoint, record_attempt, record_review, validate_checkpoint,
    verify_criterion,
)
from codex_science.completion_report import report_completion


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.run = Path(self.temp.name) / "run"

    def tearDown(self): self.temp.cleanup()

    def create(self, *, rigor_tier="standard", **kwargs):
        return create_checkpoint(self.run, goal="g", deliverable="d", done_criteria=["c"], steps=[("s", "step")],
            next_action="work", session_key="a" * 64, rigor_tier=rigor_tier, budget_policy="tier-v1", **kwargs)

    def write_partial_artifact(self):
        artifact = self.run / "partial-result.json"
        artifact.write_text(json.dumps({"schema_version": 1, "status": "partial", "result_refs": [],
            "unmet_criteria": ["criterion-1"], "unfinished_steps": ["s"], "caveats": ["incomplete"], "review_status": "not reviewed"}))
        return artifact

    def test_opt_in_budget_defaults_and_deadline(self):
        with patch("codex_science.checkpoints._now", return_value=datetime(2019, 1, 1, tzinfo=timezone.utc)):
            cp = self.create(deadline_at="2020-01-01T00:00:00Z")
        self.assertEqual((2, 1), (cp["run_budget"]["max_failed_attempts_per_class"], cp["run_budget"]["max_review_rounds"]))
        self.assertTrue(budget_status(self.run)["deadline_passed"])

    def test_init_rejects_deadline_at_or_before_now_without_writing(self):
        fixed_now = datetime(2026, 10, 21, tzinfo=timezone.utc)
        for deadline in ("2026-10-20T23:59:59Z", "2026-10-21T00:00:00Z"):
            with self.subTest(deadline=deadline), patch("codex_science.checkpoints._now", return_value=fixed_now):
                with self.assertRaisesRegex(ValueError, "deadline-at must be in the future"):
                    self.create(deadline_at=deadline)
                self.assertFalse((self.run / "checkpoint.json").exists())

    def test_remaining_seconds_is_floored_and_null_without_deadline(self):
        fixed_now = datetime(2026, 10, 21, tzinfo=timezone.utc)
        with patch("codex_science.checkpoints._now", return_value=fixed_now):
            self.create(deadline_at="2026-10-21T00:00:03.900000Z")
        status = budget_status(self.run, now=fixed_now)
        self.assertEqual(3, status["remaining_seconds"])
        self.assertEqual(0, budget_status(self.run, now=datetime(2026, 10, 21, 0, 0, 4, tzinfo=timezone.utc))["remaining_seconds"])
        self.temp.cleanup()
        self.temp = tempfile.TemporaryDirectory()
        self.run = Path(self.temp.name) / "run"
        self.create()
        self.assertIsNone(budget_status(self.run, now=fixed_now)["remaining_seconds"])

    def test_partial_finish_and_report_hash_tampering(self):
        with patch("codex_science.checkpoints._now", return_value=datetime(2019, 1, 1, tzinfo=timezone.utc)):
            self.create(deadline_at="2020-01-01T00:00:00Z")
        artifact = self.run / "partial-result.json"
        artifact.write_text(json.dumps({"schema_version": 1, "status": "partial", "result_refs": [],
            "unmet_criteria": ["criterion-1"], "unfinished_steps": ["s"], "caveats": ["incomplete"], "review_status": "not reviewed"}))
        finished = finish_partial(self.run, artifact_ref="partial-result.json")
        self.assertEqual("abandoned", finished["state"])
        report = report_completion(self.run.parent, now=datetime.now(timezone.utc), stale_after=timedelta(days=1))
        self.assertEqual(("terminal_inconclusive", "budget_exhausted"), (report["runs"][0]["outcome"], report["runs"][0]["stop_reason"]["code"]))
        artifact.write_text("tampered")
        report = report_completion(self.run.parent, now=datetime.now(timezone.utc), stale_after=timedelta(days=1))
        self.assertEqual("invalid", report["runs"][0]["outcome"])

    def test_report_rejects_tampered_partial_even_when_rehashed(self):
        with patch("codex_science.checkpoints._now", return_value=datetime(1999, 1, 1, tzinfo=timezone.utc)):
            self.create(deadline_at="2000-01-01T00:00:00Z")
        artifact = self.write_partial_artifact()
        finish_partial(self.run, artifact_ref="partial-result.json")
        changed = json.dumps({"schema_version": 1, "status": "partial", "result_refs": [],
            "unmet_criteria": [], "unfinished_steps": ["s"], "caveats": ["incomplete"], "review_status": "not reviewed"}).encode()
        artifact.write_bytes(changed)
        checkpoint = load_checkpoint(self.run)
        checkpoint["termination"]["artifact_sha256"] = hashlib.sha256(changed).hexdigest()
        (self.run / "checkpoint.json").write_text(json.dumps(checkpoint))
        report = report_completion(self.run.parent, now=datetime.now(timezone.utc), stale_after=timedelta(days=1))
        self.assertEqual("invalid", report["runs"][0]["outcome"])

    def test_not_exhausted_rejected(self):
        self.create()
        with self.assertRaisesRegex(ValueError, "not exhausted"):
            finish_partial(self.run, artifact_ref="partial-result.json")

    def test_passed_review_at_standard_limit_is_not_exhaustion(self):
        self.create()
        (self.run / "review.json").write_text(json.dumps({"status": "passed", "reviewer": "reviewer", "independent": True, "findings": []}))
        record_review(self.run, artifact_ref="review.json")
        self.assertFalse(budget_status(self.run)["exhausted"])
        with self.assertRaisesRegex(ValueError, "not exhausted"):
            finish_partial(self.run, artifact_ref="partial-result.json")

    def test_full_review_limit_requires_passed_independent_review(self):
        self.create(rigor_tier="full")
        failed = self.run / "review-failed.json"
        failed.write_text(json.dumps({"status": "failed", "reviewer": "reviewer", "independent": True, "findings": ["needs work"]}))
        record_review(self.run, artifact_ref="review-failed.json")
        passed_nonindependent = self.run / "review-passed.json"
        passed_nonindependent.write_text(json.dumps({"status": "passed", "reviewer": "reviewer", "independent": False, "findings": []}))
        record_review(self.run, artifact_ref="review-passed.json")
        status = budget_status(self.run)
        self.assertTrue(status["exhausted"])
        self.assertIn("review_rounds", status["exhausted_limits"])
        self.write_partial_artifact()
        finished = finish_partial(self.run, artifact_ref="partial-result.json")
        self.assertEqual("abandoned", finished["state"])

    def test_attempt_class_exhaustion_is_a_decision_point(self):
        self.create()
        for index in range(2):
            record_attempt(self.run, failure_class="network", approach=f"route-{index}", outcome="failed", next_action="try a different route")
        before = load_checkpoint(self.run)
        with self.assertRaisesRegex(RuntimeError, "retry budget exhausted for network; change the hypothesis to a different route, open a decision gate, or finish-partial if no in-scope route remains"):
            record_attempt(self.run, failure_class="network", approach="route-3", outcome="failed", next_action="blocked")
        self.assertEqual(before, load_checkpoint(self.run))
        record_attempt(self.run, failure_class="measurement", approach="new kind of route", outcome="failed", next_action="continue")
        self.assertEqual(3, len(load_checkpoint(self.run)["attempts"]))

    def test_escalation_expands_limits_without_resetting_attempts(self):
        self.create()
        record_attempt(self.run, failure_class="network", approach="route-1", outcome="failed", next_action="try again")
        record_attempt(self.run, failure_class="network", approach="route-2", outcome="failed", next_action="try again")
        escalated = escalate_checkpoint(self.run, tier="full", reason="scope expanded")
        self.assertEqual({"tier": "full", "max_failed_attempts_per_class": 3, "max_review_rounds": 2},
            {key: escalated["run_budget"][key] for key in ("tier", "max_failed_attempts_per_class", "max_review_rounds")})
        self.assertEqual(2, sum(item["failure_class"] == "network" for item in escalated["attempts"]))
        record_attempt(self.run, failure_class="network", approach="route-3", outcome="failed", next_action="continue")
        self.assertEqual(3, len(load_checkpoint(self.run)["attempts"]))

    def test_escalation_never_reduces_existing_limits(self):
        self.create()
        checkpoint = load_checkpoint(self.run)
        checkpoint["run_budget"]["max_failed_attempts_per_class"] = 5
        checkpoint["run_budget"]["max_review_rounds"] = 4
        (self.run / "checkpoint.json").write_text(json.dumps(checkpoint))
        escalated = escalate_checkpoint(self.run, tier="full", reason="scope expanded")
        self.assertEqual((5, 4), (escalated["run_budget"]["max_failed_attempts_per_class"], escalated["run_budget"]["max_review_rounds"]))

    def test_finish_partial_refuses_local_completion(self):
        self.create()
        record_attempt(self.run, failure_class="network", approach="route-1", outcome="failed", next_action="try again")
        record_attempt(self.run, failure_class="network", approach="route-2", outcome="failed", next_action="try again")
        (self.run / "evidence.json").write_text("{}")
        verify_criterion(self.run, "criterion-1", ["evidence.json"])
        advance_checkpoint(self.run, completed_step="s", next_step=None, next_action="complete")
        (self.run / "review.json").write_text(json.dumps({"status": "passed", "reviewer": "reviewer", "independent": True, "findings": []}))
        record_review(self.run, artifact_ref="review.json")
        with self.assertRaisesRegex(ValueError, "complete it instead"):
            finish_partial(self.run, artifact_ref="partial-result.json")
        self.assertEqual("active", load_checkpoint(self.run)["state"])

    def test_termination_requires_schema_v4_and_run_budget(self):
        with patch("codex_science.checkpoints._now", return_value=datetime(1999, 1, 1, tzinfo=timezone.utc)):
            checkpoint = self.create(deadline_at="2000-01-01T00:00:00Z")
        checkpoint["state"] = "abandoned"
        checkpoint["current_step"] = None
        checkpoint["steps"][0]["status"] = "pending"
        checkpoint["next_action"] = ""
        checkpoint["termination_reason"] = "budget_exhausted"
        checkpoint["termination"] = {"kind": "partial", "reason_code": "budget_exhausted", "exhausted_limit": "deadline", "recorded_at": "2026-10-21T00:00:00Z", "artifact_ref": "partial-result.json", "artifact_sha256": "a" * 64}
        validate_checkpoint(checkpoint)
        mismatched_reason = dict(checkpoint)
        mismatched_reason["termination"] = dict(checkpoint["termination"])
        mismatched_reason["termination"]["reason_code"] = "deadline_passed"
        with self.assertRaisesRegex(ValueError, "termination_reason must match termination.reason_code"):
            validate_checkpoint(mismatched_reason)
        without_budget = dict(checkpoint)
        without_budget.pop("run_budget")
        without_budget.pop("review_rounds")
        with self.assertRaisesRegex(ValueError, "partial termination is invalid"):
            validate_checkpoint(without_budget)
        old_schema = dict(checkpoint)
        old_schema["schema_version"] = 3
        with self.assertRaisesRegex(ValueError, "run_budget is invalid"):
            validate_checkpoint(old_schema)

    def test_budget_cli_returns_json_and_expected_exit_codes(self):
        with patch("codex_science.checkpoints._now", return_value=datetime(1999, 1, 1, tzinfo=timezone.utc)):
            self.create(deadline_at="2000-01-01T00:00:00Z")
        cli = Path(__file__).resolve().parents[1] / "scripts" / "science_checkpoint.py"
        status = subprocess.run([sys.executable, str(cli), "budget-status", str(self.run)], capture_output=True, text=True)
        self.assertEqual(0, status.returncode, status.stderr)
        self.assertTrue(json.loads(status.stdout)["exhausted"])
        incomplete = subprocess.run([sys.executable, str(cli), "finish-partial", str(self.run), "--artifact-ref", "missing.json"], capture_output=True, text=True)
        self.assertEqual(2, incomplete.returncode)

        (self.run / "partial-result.json").write_text(json.dumps({"schema_version": 1, "status": "partial", "result_refs": [],
            "unmet_criteria": ["criterion-1"], "unfinished_steps": ["s"], "caveats": ["incomplete"], "review_status": "not reviewed"}))
        partial = subprocess.run([sys.executable, str(cli), "finish-partial", str(self.run), "--artifact-ref", "partial-result.json"], capture_output=True, text=True)
        self.assertEqual(0, partial.returncode, partial.stderr)
        self.assertEqual("abandoned", json.loads(partial.stdout)["state"])


if __name__ == "__main__": unittest.main()
