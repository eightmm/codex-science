import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codex_science.checkpoints import (
    create_checkpoint,
    escalate_checkpoint,
    load_checkpoint,
    validate_checkpoint,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "science_checkpoint.py"
SKILL = ROOT / "runtime-skills" / "codex-science" / "SKILL.md"


class RigorCheckpointContractTests(unittest.TestCase):
    session_key = "a" * 64

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.run_dir = Path(self.tempdir.name) / "artifacts" / "run"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def create(self, *, tier=None):
        return create_checkpoint(
            self.run_dir,
            goal="Answer the question",
            deliverable="Evidence report",
            done_criteria=["Evidence recorded"],
            steps=[("work", "Do work")],
            next_action="Inspect evidence",
            session_key=self.session_key,
            rigor_tier=tier,
            rigor_decision_sha256="b" * 64 if tier else None,
        )

    def test_init_with_and_without_tier_and_quick_rejected(self):
        plain = self.create()
        self.assertNotIn("rigor", plain)
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = create_checkpoint(
                Path(directory) / "artifacts" / "run", goal="g", deliverable="d", done_criteria=["c"],
                steps=[("s", "step")], next_action="next", session_key=self.session_key,
                rigor_tier="standard", rigor_decision_sha256="c" * 64,
            )
            self.assertEqual("standard", checkpoint["rigor"]["tier"])
            self.assertEqual("c" * 64, checkpoint["rigor"]["history"][0]["decision_sha256"])
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "rigor_tier"):
                create_checkpoint(
                    Path(directory) / "artifacts" / "run", goal="g", deliverable="d", done_criteria=["c"],
                    steps=[("s", "step")], next_action="next", session_key=self.session_key,
                    rigor_tier="quick",
                )

    def test_escalate_standard_to_full_and_refuse_equal_or_downgrade(self):
        self.create(tier="standard")
        updated = escalate_checkpoint(self.run_dir, tier="full", reason="scope expanded")
        self.assertEqual(["standard", "full"], [entry["tier"] for entry in updated["rigor"]["history"]])
        for tier in ("full", "standard"):
            with self.assertRaisesRegex(ValueError, "higher"):
                escalate_checkpoint(self.run_dir, tier=tier, reason="no change")

    def test_legacy_schema_one_through_four_validate_and_legacy_four_escalates(self):
        for version in (1, 2, 3, 4):
            with tempfile.TemporaryDirectory() as directory:
                run_dir = Path(directory) / "artifacts" / "run"
                checkpoint = create_checkpoint(
                    run_dir, goal="g", deliverable="d", done_criteria=["c"],
                    steps=[("s", "step")], next_action="next", session_key=self.session_key,
                )
                checkpoint["schema_version"] = version
                if version == 1:
                    for field in ("session_key", "continuation_count", "idle_continuations", "continuation_budget", "outer_goal", "review_receipt", "wait", "termination_reason", "revision"):
                        checkpoint.pop(field)
                    checkpoint["done_criteria"] = ["c"]
                elif version == 2:
                    for field in ("continuation_budget", "outer_goal", "review_receipt", "wait", "termination_reason", "revision"):
                        checkpoint.pop(field)
                    checkpoint["done_criteria"] = ["c"]
                elif version == 3:
                    checkpoint["outer_goal"].pop("task_key", None)
                    checkpoint["outer_goal"].pop("receipt", None)
                validate_checkpoint(checkpoint)
                (run_dir / "checkpoint.json").write_text(json.dumps(checkpoint), encoding="utf-8")
                self.assertEqual(version, load_checkpoint(run_dir)["schema_version"])
                if version == 4:
                    updated = escalate_checkpoint(run_dir, tier="standard", reason="legacy run adopted")
                    self.assertEqual("standard", updated["rigor"]["tier"])

    def test_malformed_rigor_rejected_and_terminal_refused(self):
        checkpoint = self.create(tier="standard")
        for rigor in (
            {"tier": "quick", "history": [{"tier": "quick", "at": "now", "reason": "x"}]},
            {"tier": "full", "history": []},
            {"tier": "full", "history": [{"tier": "full", "at": "now", "reason": "x"}, {"tier": "standard", "at": "later", "reason": "x"}]},
            {"tier": "full", "history": [{"tier": "standard", "at": "now", "reason": "x"}]},
        ):
            altered = dict(checkpoint, rigor=rigor)
            with self.assertRaises(ValueError):
                validate_checkpoint(altered)
        checkpoint["state"] = "abandoned"
        checkpoint["steps"][0]["status"] = "completed"
        checkpoint["current_step"] = None
        checkpoint["next_action"] = ""
        checkpoint["termination_reason"] = "done"
        (self.run_dir / "checkpoint.json").write_text(json.dumps(checkpoint), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "terminal"):
            escalate_checkpoint(self.run_dir, tier="full", reason="too late")

    def test_cli_init_and_escalate(self):
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONDONTWRITEBYTECODE="1")
        base = [sys.executable, str(SCRIPT)]
        init = subprocess.run(
            base + ["init", str(self.run_dir), "--goal", "g", "--deliverable", "d", "--done", "c", "--step", "s=step", "--next-action", "next", "--session-key", self.session_key, "--rigor-tier", "standard"],
            check=True, capture_output=True, text=True, env=env,
        )
        self.assertEqual("standard", json.loads(init.stdout)["rigor"]["tier"])
        escalated = subprocess.run(
            base + ["escalate", str(self.run_dir), "--tier", "full", "--reason", "more sources", "--rigor-decision-sha256", "d" * 64],
            check=True, capture_output=True, text=True, env=env,
        )
        self.assertEqual("full", json.loads(escalated.stdout)["rigor"]["tier"])
        self.assertEqual("d" * 64, load_checkpoint(self.run_dir)["rigor"]["history"][-1]["decision_sha256"])
        with tempfile.TemporaryDirectory() as directory:
            legacy_cli_dir = Path(directory) / "artifacts" / "run"
            no_tier = subprocess.run(
                base + ["init", str(legacy_cli_dir), "--goal", "g", "--deliverable", "d", "--done", "c", "--step", "s=step", "--next-action", "next", "--session-key", self.session_key],
                check=True, capture_output=True, text=True, env=env,
            )
            self.assertNotIn("rigor", json.loads(no_tier.stdout))

    def test_coordinator_documents_tier_contract(self):
        content = " ".join(SKILL.read_text(encoding="utf-8").split())
        self.assertIn("### Rigor tier", content)
        self.assertIn("classify_rigor.py", content)
        self.assertIn("never lower it", content)
        self.assertIn("Tiers never relax the audit", content)


if __name__ == "__main__":
    unittest.main()
