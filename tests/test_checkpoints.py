import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codex_science.checkpoints import (
    advance_checkpoint,
    block_checkpoint,
    claim_checkpoint,
    complete_checkpoint,
    create_checkpoint,
    find_active_checkpoint,
    heartbeat_checkpoint,
    load_checkpoint,
    record_review,
    record_attempt,
    request_continuation,
    request_decision,
    resume_checkpoint,
    verify_criterion,
)


class CheckpointTests(unittest.TestCase):
    session_key = "a" * 64

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.run_dir = Path(self.tempdir.name) / "artifacts" / "run-001"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def create(self) -> dict[str, object]:
        return create_checkpoint(
            self.run_dir,
            goal="Answer the research question",
            deliverable="Reviewed evidence report",
            done_criteria=["Analysis verified", "Independent review complete"],
            steps=[("orient", "Orient"), ("analyze", "Analyze"), ("review", "Review")],
            next_action="Inspect the available inputs",
            session_key=self.session_key,
        )

    def satisfy_completion_contract(self) -> None:
        evidence = self.run_dir / "verification.json"
        evidence.write_text('{"status": "passed"}\n', encoding="utf-8")
        review = self.run_dir / "review.json"
        review.write_text(
            '{"status": "passed", "reviewer": "independent-test-reviewer", '
            '"independent": true, "findings": []}\n',
            encoding="utf-8",
        )
        checkpoint = load_checkpoint(self.run_dir)
        for criterion in checkpoint["done_criteria"]:
            verify_criterion(self.run_dir, criterion["id"], ["verification.json"])
        record_review(self.run_dir, artifact_ref="review.json")

    def test_create_writes_private_atomic_checkpoint(self) -> None:
        checkpoint = self.create()
        path = self.run_dir / "checkpoint.json"

        self.assertEqual("active", checkpoint["state"])
        self.assertEqual(4, checkpoint["schema_version"])
        self.assertEqual(self.session_key, checkpoint["session_key"])
        self.assertEqual("orient", checkpoint["current_step"])
        self.assertEqual(0o600, stat.S_IMODE(path.stat().st_mode))
        self.assertEqual(checkpoint, json.loads(path.read_text(encoding="utf-8")))

    def test_atomic_checkpoint_write_never_follows_a_precreated_temp_symlink(self) -> None:
        self.run_dir.mkdir(parents=True)
        victim = Path(self.tempdir.name) / "victim"
        victim.write_text("protected", encoding="utf-8")
        temporary = self.run_dir / f".checkpoint.json.{os.getpid()}.tmp"
        temporary.symlink_to(victim)

        with self.assertRaises(FileExistsError):
            self.create()

        self.assertEqual("protected", victim.read_text(encoding="utf-8"))

    def test_advance_marks_one_step_complete_and_starts_the_next(self) -> None:
        self.create()
        checkpoint = advance_checkpoint(
            self.run_dir,
            completed_step="orient",
            next_step="analyze",
            next_action="Run the smallest discriminating analysis",
        )

        statuses = {step["id"]: step["status"] for step in checkpoint["steps"]}
        self.assertEqual("completed", statuses["orient"])
        self.assertEqual("in_progress", statuses["analyze"])
        self.assertEqual("analyze", checkpoint["current_step"])

    def test_retry_budget_requires_a_changed_decision_after_three_attempts(self) -> None:
        self.create()
        for index in range(3):
            record_attempt(
                self.run_dir,
                failure_class="network-timeout",
                approach=f"approach-{index}",
                outcome="timed out",
                next_action="Try a materially different method",
            )

        with self.assertRaisesRegex(RuntimeError, "retry budget exhausted"):
            record_attempt(
                self.run_dir,
                failure_class="network-timeout",
                approach="approach-3",
                outcome="timed out",
                next_action="Try again",
            )
        self.assertEqual(3, len(load_checkpoint(self.run_dir)["attempts"]))

    def test_decisions_are_batched_and_resume_clears_the_gate(self) -> None:
        self.create()
        gated = request_decision(
            self.run_dir,
            questions=["Approve the GPU budget?", "Allow the new data host?"],
            reason="Remote execution changes cost and data movement",
        )

        self.assertEqual("approval_required", gated["state"])
        self.assertEqual(2, len(gated["pending_decisions"]))
        resumed = resume_checkpoint(self.run_dir, next_action="Launch the approved remote run")
        self.assertEqual("active", resumed["state"])
        self.assertEqual([], resumed["pending_decisions"])

    def test_genuine_blocker_records_the_unblock_condition(self) -> None:
        self.create()
        blocked = block_checkpoint(
            self.run_dir,
            reason="The required input file is unavailable",
            next_action="Resume when the input file is attached",
        )

        self.assertEqual("blocked", blocked["state"])
        self.assertEqual("The required input file is unavailable", blocked["blocker"])
        resumed = resume_checkpoint(self.run_dir, next_action="Validate the attached input")
        self.assertEqual("active", resumed["state"])
        self.assertEqual("", resumed["blocker"])

    def test_stop_continuations_are_bounded_until_progress_heartbeat(self) -> None:
        self.create()

        first = request_continuation(self.run_dir, session_key=self.session_key, idle_limit=2)
        second = request_continuation(self.run_dir, session_key=self.session_key, idle_limit=2)
        exhausted = request_continuation(self.run_dir, session_key=self.session_key, idle_limit=2)

        self.assertTrue(first["continue"])
        self.assertTrue(second["continue"])
        self.assertFalse(exhausted["continue"])
        progress = self.run_dir / "progress.json"
        progress.write_text('{"step": 2}\n', encoding="utf-8")
        heartbeat = heartbeat_checkpoint(
            self.run_dir,
            next_action="Inspect the second evidence source",
            progress_ref="progress.json",
        )
        self.assertEqual(0, heartbeat["idle_continuations"])
        resumed = request_continuation(self.run_dir, session_key=self.session_key, idle_limit=2)
        self.assertTrue(resumed["continue"])

    def test_heartbeat_requires_a_new_concrete_next_action(self) -> None:
        self.create()

        with self.assertRaisesRegex(ValueError, "heartbeat must change next_action"):
            heartbeat_checkpoint(
                self.run_dir,
                next_action="Inspect the available inputs",
            )

    def test_session_key_prevents_another_task_from_claiming_or_continuing_run(self) -> None:
        self.create()

        with self.assertRaisesRegex(ValueError, "belongs to another Codex task"):
            request_continuation(self.run_dir, session_key="b" * 64, idle_limit=2)
        with self.assertRaisesRegex(ValueError, "belongs to another Codex task"):
            claim_checkpoint(self.run_dir, session_key="b" * 64)

    def test_legacy_checkpoint_can_be_claimed_without_losing_progress(self) -> None:
        checkpoint = self.create()
        checkpoint["schema_version"] = 1
        checkpoint["done_criteria"] = [item["text"] for item in checkpoint["done_criteria"]]
        for field in (
            "session_key",
            "continuation_count",
            "idle_continuations",
            "continuation_budget",
            "outer_goal",
            "review_receipt",
            "wait",
            "termination_reason",
            "revision",
        ):
            checkpoint.pop(field)
        (self.run_dir / "checkpoint.json").write_text(
            json.dumps(checkpoint),
            encoding="utf-8",
        )

        claimed = claim_checkpoint(self.run_dir, session_key=self.session_key)

        self.assertEqual(4, claimed["schema_version"])
        self.assertEqual("orient", claimed["current_step"])
        self.assertEqual(self.session_key, claimed["session_key"])

    def test_schema_v2_owner_rotation_requires_explicit_previous_key(self) -> None:
        checkpoint = self.create()
        old_key = "b" * 64
        checkpoint["schema_version"] = 2
        checkpoint["session_key"] = old_key
        checkpoint["done_criteria"] = [item["text"] for item in checkpoint["done_criteria"]]
        for field in (
            "continuation_budget",
            "outer_goal",
            "review_receipt",
            "wait",
            "termination_reason",
            "revision",
        ):
            checkpoint.pop(field)
        (self.run_dir / "checkpoint.json").write_text(json.dumps(checkpoint), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "another Codex task"):
            claim_checkpoint(self.run_dir, session_key=self.session_key)

        claimed = claim_checkpoint(
            self.run_dir,
            session_key=self.session_key,
            previous_session_key=old_key,
        )
        self.assertEqual(4, claimed["schema_version"])
        self.assertEqual(self.session_key, claimed["session_key"])

    def test_active_checkpoint_discovery_is_session_scoped_and_ignores_symlinks(self) -> None:
        self.create()
        foreign = self.run_dir.parent / "foreign"
        create_checkpoint(
            foreign,
            goal="Other task",
            deliverable="Other report",
            done_criteria=["Done"],
            steps=[("work", "Work")],
            next_action="Continue elsewhere",
            session_key="b" * 64,
        )
        outside = Path(self.tempdir.name) / "outside"
        outside.mkdir()
        (self.run_dir.parent / "linked").symlink_to(outside, target_is_directory=True)

        found = find_active_checkpoint(Path(self.tempdir.name), self.session_key)

        self.assertEqual(self.run_dir, found)

    def test_completion_requires_every_planned_step(self) -> None:
        self.create()
        with self.assertRaisesRegex(ValueError, "unfinished steps"):
            complete_checkpoint(self.run_dir)

        advance_checkpoint(
            self.run_dir,
            completed_step="orient",
            next_step="analyze",
            next_action="Analyze",
        )
        advance_checkpoint(
            self.run_dir,
            completed_step="analyze",
            next_step="review",
            next_action="Review",
        )
        advance_checkpoint(
            self.run_dir,
            completed_step="review",
            next_step=None,
            next_action="Finalize the checkpoint",
        )
        self.satisfy_completion_contract()
        completed = complete_checkpoint(self.run_dir)

        self.assertEqual("complete", completed["state"])
        self.assertIsNone(completed["current_step"])
        self.assertEqual("", completed["next_action"])

    def test_completion_cannot_bypass_an_open_decision_gate(self) -> None:
        self.create()
        advance_checkpoint(
            self.run_dir,
            completed_step="orient",
            next_step="analyze",
            next_action="Analyze",
        )
        advance_checkpoint(
            self.run_dir,
            completed_step="analyze",
            next_step="review",
            next_action="Review",
        )
        advance_checkpoint(
            self.run_dir,
            completed_step="review",
            next_step=None,
            next_action="Request release approval",
        )
        request_decision(
            self.run_dir,
            questions=["Release the reviewed result?"],
            reason="Release is a write-capable action",
        )

        with self.assertRaisesRegex(ValueError, "only an active checkpoint can complete"):
            complete_checkpoint(self.run_dir)

    def test_cli_initializes_and_shows_checkpoint(self) -> None:
        root = Path(__file__).resolve().parents[1]
        script = root / "scripts" / "science_checkpoint.py"
        completed = subprocess.run(
            [
                sys.executable,
                str(script),
                "init",
                str(self.run_dir),
                "--goal",
                "Question",
                "--deliverable",
                "Report",
                "--done",
                "Verified",
                "--step",
                "orient=Orient",
                "--next-action",
                "Inspect inputs",
                "--session-key",
                self.session_key,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(0, completed.returncode, completed.stderr)
        shown = subprocess.run(
            [sys.executable, str(script), "show", str(self.run_dir)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, shown.returncode, shown.stderr)
        self.assertEqual("Question", json.loads(shown.stdout)["goal"])

        (self.run_dir / "progress.json").write_text('{"step": 2}\n', encoding="utf-8")

        heartbeat = subprocess.run(
            [
                sys.executable,
                str(script),
                "heartbeat",
                str(self.run_dir),
                "--next-action",
                "Continue analysis",
                "--progress-ref",
                "progress.json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, heartbeat.returncode, heartbeat.stderr)


if __name__ == "__main__":
    unittest.main()
