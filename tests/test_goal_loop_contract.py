import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codex_science.checkpoints import (
    abandon_checkpoint,
    complete_checkpoint,
    confirm_goal_complete,
    create_checkpoint,
    record_review,
    request_continuation,
    resume_checkpoint,
    verify_criterion,
    wait_checkpoint,
)


class GoalLoopCheckpointContractTests(unittest.TestCase):
    session_key = "a" * 64
    goal_task_key = "b" * 64

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tempdir.name)
        self.run_dir = self.workspace / "artifacts" / "run-001"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def create(self, *, outer_goal: str = "native", continuation_budget: int = 100):
        return create_checkpoint(
            self.run_dir,
            goal="Finish the scientific run",
            deliverable="Reviewed report",
            done_criteria=["Evidence is saved"],
            steps=[("work", "Do the work")],
            next_action="Produce the evidence",
            session_key=self.session_key,
            outer_goal=outer_goal,
            goal_task_key=self.goal_task_key if outer_goal == "native" else None,
            continuation_budget=continuation_budget,
        )

    def finish_local_contract(self) -> None:
        from codex_science.checkpoints import advance_checkpoint

        evidence = self.run_dir / "result.json"
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text('{"result": "ok"}\n', encoding="utf-8")
        review = self.run_dir / "review.json"
        review.write_text(
            '{"status": "passed", "reviewer": "independent-subagent", '
            '"independent": true, "findings": []}\n',
            encoding="utf-8",
        )
        advance_checkpoint(
            self.run_dir,
            completed_step="work",
            next_step=None,
            next_action="Verify completion evidence",
        )
        verify_criterion(self.run_dir, "criterion-1", ["result.json#/result"])
        record_review(self.run_dir, artifact_ref="review.json")

    def test_schema_v4_has_structured_criteria_and_bound_outer_goal(self) -> None:
        checkpoint = self.create()

        self.assertEqual(4, checkpoint["schema_version"])
        self.assertEqual(
            [{"id": "criterion-1", "text": "Evidence is saved", "status": "pending", "evidence_refs": [], "evidence_sha256": {}}],
            checkpoint["done_criteria"],
        )
        self.assertEqual(
            {
                "mode": "native",
                "phase": "running",
                "task_key": self.goal_task_key,
                "receipt": None,
            },
            checkpoint["outer_goal"],
        )
        self.assertEqual(100, checkpoint["continuation_budget"])

    def test_second_nonterminal_run_for_same_session_is_rejected(self) -> None:
        self.create()

        with self.assertRaisesRegex(ValueError, "nonterminal checkpoint"):
            create_checkpoint(
                self.workspace / "artifacts" / "run-002",
                goal="Competing run",
                deliverable="Other report",
                done_criteria=["Done"],
                steps=[("work", "Work")],
                next_action="Start",
                session_key=self.session_key,
            )

    def test_nested_artifact_roots_cannot_create_duplicate_nonterminal_run(self) -> None:
        self.create(outer_goal="none")

        with self.assertRaisesRegex(ValueError, "nonterminal checkpoint"):
            create_checkpoint(
                self.workspace / "sub" / "artifacts" / "run-002",
                goal="Competing nested run",
                deliverable="Other report",
                done_criteria=["Done"],
                steps=[("work", "Work")],
                next_action="Start",
                session_key=self.session_key,
            )

    def test_root_artifact_run_is_rejected_after_nested_run(self) -> None:
        create_checkpoint(
            self.workspace / "sub" / "artifacts" / "run-001",
            goal="Nested run",
            deliverable="Nested report",
            done_criteria=["Done"],
            steps=[("work", "Work")],
            next_action="Start",
            session_key=self.session_key,
        )

        with self.assertRaisesRegex(ValueError, "nonterminal checkpoint"):
            create_checkpoint(
                self.run_dir,
                goal="Competing root run",
                deliverable="Other report",
                done_criteria=["Done"],
                steps=[("work", "Work")],
                next_action="Start",
                session_key=self.session_key,
            )

    def test_native_goal_completion_requires_evidence_review_and_host_confirmation(self) -> None:
        self.create()

        with self.assertRaisesRegex(ValueError, "unfinished steps"):
            complete_checkpoint(self.run_dir)

        from codex_science.checkpoints import advance_checkpoint

        advance_checkpoint(
            self.run_dir,
            completed_step="work",
            next_step=None,
            next_action="Verify completion evidence",
        )
        with self.assertRaisesRegex(ValueError, "unsatisfied criteria"):
            complete_checkpoint(self.run_dir)

        evidence = self.run_dir / "result.json"
        evidence.write_text('{"result": "ok"}\n', encoding="utf-8")
        verify_criterion(self.run_dir, "criterion-1", ["result.json#/result"])
        with self.assertRaisesRegex(ValueError, "passed independent review"):
            complete_checkpoint(self.run_dir)

        review = self.run_dir / "review.json"
        review.write_text(
            '{"status": "passed", "reviewer": "independent-subagent", '
            '"independent": true, "findings": []}\n',
            encoding="utf-8",
        )
        record_review(self.run_dir, artifact_ref="review.json")
        pending = complete_checkpoint(self.run_dir)
        self.assertEqual("active", pending["state"])
        self.assertEqual("completion_pending", pending["outer_goal"]["phase"])
        self.assertIn("update_goal", pending["next_action"])

        goal_receipt = self.run_dir / "goal-complete.json"
        goal_receipt.write_text(
            json.dumps({"status": "complete", "task_key": self.goal_task_key}) + "\n",
            encoding="utf-8",
        )
        completed = confirm_goal_complete(self.run_dir, receipt_ref="goal-complete.json")
        self.assertEqual("complete", completed["state"])
        self.assertEqual("host_completion_attested", completed["outer_goal"]["phase"])
        self.assertEqual("goal-complete.json", completed["outer_goal"]["receipt"]["artifact_ref"])

    def test_goal_confirmation_receipt_must_match_bound_task(self) -> None:
        self.create()
        self.finish_local_contract()
        complete_checkpoint(self.run_dir)
        receipt = self.run_dir / "goal-complete.json"
        receipt.write_text(
            json.dumps({"status": "complete", "task_key": "c" * 64}) + "\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "task_key"):
            confirm_goal_complete(self.run_dir, receipt_ref="goal-complete.json")

    def test_evidence_must_be_an_existing_run_local_regular_file(self) -> None:
        self.create()
        outside = self.workspace / "outside.json"
        outside.write_text("{}\n", encoding="utf-8")

        for evidence_ref in ("missing.json", "../outside.json", str(outside)):
            with self.subTest(evidence_ref=evidence_ref):
                with self.assertRaisesRegex(ValueError, "evidence"):
                    verify_criterion(self.run_dir, "criterion-1", [evidence_ref])

        link = self.run_dir / "linked.json"
        link.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "evidence"):
            verify_criterion(self.run_dir, "criterion-1", ["linked.json"])

    def test_completion_rechecks_evidence_hashes(self) -> None:
        self.create(outer_goal="none")
        self.finish_local_contract()
        (self.run_dir / "result.json").write_text('{"result": "changed"}\n', encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "evidence changed"):
            complete_checkpoint(self.run_dir)

    def test_total_continuation_budget_is_absolute(self) -> None:
        self.create(outer_goal="none", continuation_budget=2)

        first = request_continuation(self.run_dir, session_key=self.session_key, idle_limit=10)
        second = request_continuation(self.run_dir, session_key=self.session_key, idle_limit=10)
        exhausted = request_continuation(self.run_dir, session_key=self.session_key, idle_limit=10)

        self.assertTrue(first["continue"])
        self.assertTrue(second["continue"])
        self.assertFalse(exhausted["continue"])
        self.assertEqual("continuation_budget_exhausted", exhausted["reason"])

    def test_waiting_external_and_abandoned_states_never_busy_loop(self) -> None:
        self.create(outer_goal="none")
        waiting = wait_checkpoint(
            self.run_dir,
            reason="Remote job is queued",
            next_action="Poll job 42 after the approved interval",
            poll_interval_seconds=300,
            terminal_rule="Stop after two hours or terminal scheduler status",
        )
        self.assertEqual("waiting_external", waiting["state"])
        self.assertFalse(
            request_continuation(self.run_dir, session_key=self.session_key, idle_limit=3)["continue"]
        )

        resumed = resume_checkpoint(self.run_dir, next_action="Poll job 42 now")
        self.assertEqual("active", resumed["state"])
        abandoned = abandon_checkpoint(self.run_dir, reason="Codex Science deactivated")
        self.assertEqual("abandoned", abandoned["state"])
        with self.assertRaisesRegex(ValueError, "cannot resume"):
            resume_checkpoint(self.run_dir, next_action="Do not resurrect")


class ActivationGenerationContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository_root = Path(__file__).resolve().parents[1]
        self.session_script = self.repository_root / "scripts" / "science_session_hook.py"
        self.stop_script = self.repository_root / "scripts" / "science_stop_hook.py"
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.plugin_data = self.root / "plugin-data"
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.session_id = "same-session"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def run_hook(self, event: str, **extra: object) -> dict[str, object] | None:
        payload: dict[str, object] = {
            "cwd": str(self.workspace),
            "hook_event_name": event,
            "model": "test-model",
            "permission_mode": "default",
            "session_id": self.session_id,
            "transcript_path": None,
        }
        payload.update(extra)
        env = os.environ.copy()
        env["PLUGIN_DATA"] = str(self.plugin_data)
        script = self.stop_script if event == "Stop" else self.session_script
        result = subprocess.run(
            [sys.executable, str(script)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else None

    @staticmethod
    def context_key(output: dict[str, object]) -> str:
        context = str(output["hookSpecificOutput"]["additionalContext"])
        match = re.search(r"--session-key ([0-9a-f]{64})", context)
        if match is None:
            raise AssertionError(context)
        return match.group(1)

    @staticmethod
    def goal_task_key(output: dict[str, object]) -> str:
        context = str(output["hookSpecificOutput"]["additionalContext"])
        match = re.search(r"--goal-task-key ([0-9a-f]{64})", context)
        if match is None:
            raise AssertionError(context)
        return match.group(1)

    def test_reactivation_rotates_owner_key_and_cannot_resurrect_old_run(self) -> None:
        first = self.run_hook(
            "UserPromptSubmit",
            prompt="Start Codex Science",
            turn_id="turn-1",
        )
        first_key = self.context_key(first)
        first_goal_key = self.goal_task_key(first)
        create_checkpoint(
            self.workspace / "artifacts" / "old-run",
            goal="Old run",
            deliverable="Old report",
            done_criteria=["Done"],
            steps=[("work", "Work")],
            next_action="Resurrected old action",
            session_key=first_key,
        )

        self.run_hook(
            "UserPromptSubmit",
            prompt="Stop Codex Science",
            turn_id="turn-2",
        )
        second = self.run_hook(
            "UserPromptSubmit",
            prompt="Start Codex Science",
            turn_id="turn-3",
        )
        second_key = self.context_key(second)
        self.assertNotEqual(first_key, second_key)
        self.assertEqual(first_goal_key, self.goal_task_key(second))
        context = str(second["hookSpecificOutput"]["additionalContext"])
        self.assertIn(f"--previous-session-key {first_goal_key}", context)

        stop = self.run_hook("Stop", turn_id="turn-3", stop_hook_active=False)
        self.assertIsNone(stop)

        marker = next(path for path in self.plugin_data.rglob("*") if path.is_file())
        self.assertNotEqual("active", marker.read_text(encoding="utf-8").strip())
        self.assertNotIn(self.session_id, marker.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
