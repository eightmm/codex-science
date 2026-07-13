import json
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codex_science.checkpoints import (
    advance_checkpoint,
    block_checkpoint,
    complete_checkpoint,
    create_checkpoint,
    load_checkpoint,
    record_attempt,
    request_decision,
    resume_checkpoint,
)


class CheckpointTests(unittest.TestCase):
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
        )

    def test_create_writes_private_atomic_checkpoint(self) -> None:
        checkpoint = self.create()
        path = self.run_dir / "checkpoint.json"

        self.assertEqual("active", checkpoint["state"])
        self.assertEqual("orient", checkpoint["current_step"])
        self.assertEqual(0o600, stat.S_IMODE(path.stat().st_mode))
        self.assertEqual(checkpoint, json.loads(path.read_text(encoding="utf-8")))

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


if __name__ == "__main__":
    unittest.main()
