import hashlib
import contextlib
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

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
from codex_science.artifacts import new_manifest, validate_bundle
from codex_science.review_receipts import build_review_receipt
from codex_science.review import review_manifest
from science_checkpoint import _early_check, _pre_review_advisories


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

    @staticmethod
    def validation_projection(sidecars: dict[str, object]) -> dict[str, object]:
        # validate_bundle includes self-referential lookup structures, so compare
        # its gate-relevant values rather than recursively comparing the object.
        keys = ("paths", "artifact_hashes", "claim_by_id", "node_by_id", "edges", "study_by_id", "lane_by_id")
        return {key: sidecars.get(key) for key in keys}

    def test_pre_review_advisories_report_lane_support_mismatch(self) -> None:
        example = Path(__file__).resolve().parents[1] / "examples/literature-review-reviewed-run"
        manifest = json.loads((example / "manifest.json").read_text(encoding="utf-8"))
        sidecars = validate_bundle(manifest, example)
        validation_before = self.validation_projection(sidecars)
        before = review_manifest(manifest, example, sidecars=sidecars)
        lane = dict(sidecars["lane_receipts"][0], supported_claim_ids=["claim-method-effect"])
        graph = dict(sidecars["evidence_graph"], edges=[])
        triggering = dict(sidecars, lane_receipts=[lane], evidence_graph=graph, edges=[])

        findings = _pre_review_advisories(triggering, manifest)

        self.assertIn("lane-claim-without-support-edge", {item["code"] for item in findings})
        empty_lane = dict(lane, included_records=[])
        empty_findings = _pre_review_advisories(
            dict(sidecars, lane_receipts=[empty_lane]), manifest
        )
        self.assertNotIn("lane-claim-without-support-edge", {item["code"] for item in empty_findings})
        self.assertEqual(validation_before, self.validation_projection(validate_bundle(manifest, example)))
        self.assertEqual(before, review_manifest(manifest, example, sidecars=sidecars))

    def test_pre_review_advisories_report_stale_lane_output_hash(self) -> None:
        manifest = new_manifest("run-001", "Question", [])
        manifest["artifacts"] = [{"path": "result.json", "sha256": "a" * 64, "kind": "report"}]
        manifest["executions"] = [{"outputs": [{"path": "result.json", "sha256": "b" * 64}]}]
        sidecars = {"lane_receipts": [{"lane_id": "lane-1", "outputs": ["result.json"]}]}

        example = Path(__file__).resolve().parents[1] / "examples/literature-review-reviewed-run"
        gate_manifest = json.loads((example / "manifest.json").read_text(encoding="utf-8"))
        gate_sidecars = validate_bundle(gate_manifest, example)
        validation_before = self.validation_projection(gate_sidecars)
        review_before = review_manifest(gate_manifest, example, sidecars=gate_sidecars)
        findings = _pre_review_advisories(sidecars, manifest)

        self.assertIn("lane-output-hash-stale", {item["code"] for item in findings})
        for executions, expected in (
            ([{"outputs": [{"path": "result.json", "sha256": "b" * 64}]}, {}], True),
            ([{"outputs": [{"path": "result.json", "sha256": "b" * 64}]}, {"outputs": ["legacy-output"]}], True),
            ([{"outputs": [{"path": "result.json", "sha256": "b" * 64}]},
              {"outputs": [{"path": "result.json", "sha256": "a" * 64}]}], False),
        ):
            with self.subTest(executions=executions):
                manifest["executions"] = executions
                codes = {item["code"] for item in _pre_review_advisories(sidecars, manifest)}
                self.assertEqual("lane-output-hash-stale" in codes, expected)
        self.assertEqual(validation_before, self.validation_projection(validate_bundle(gate_manifest, example)))
        self.assertEqual(review_before, review_manifest(gate_manifest, example, sidecars=gate_sidecars))

    def test_pre_review_advisories_are_clean_for_reviewed_example_and_safe_on_malformed_data(self) -> None:
        example = Path(__file__).resolve().parents[1] / "examples/literature-review-reviewed-run"
        manifest = json.loads((example / "manifest.json").read_text(encoding="utf-8"))
        sidecars = validate_bundle(manifest, example)
        self.assertEqual([], _pre_review_advisories(sidecars, manifest))
        self.assertEqual([], _pre_review_advisories({"lane_receipts": [None], "study_table": None}, []))
        early = _early_check(example)
        self.assertNotIn("lane-claim-without-support-edge", {item["code"] for item in early["findings"]})
        self.assertNotIn("lane-output-hash-stale", {item["code"] for item in early["findings"]})

    def test_create_writes_private_atomic_checkpoint(self) -> None:
        checkpoint = self.create()
        path = self.run_dir / "checkpoint.json"

        self.assertEqual("active", checkpoint["state"])
        self.assertEqual(4, checkpoint["schema_version"])
        self.assertEqual(self.session_key, checkpoint["session_key"])
        self.assertEqual("orient", checkpoint["current_step"])
        self.assertEqual(0o600, stat.S_IMODE(path.stat().st_mode))
        self.assertEqual(checkpoint, json.loads(path.read_text(encoding="utf-8")))

    def test_passed_review_accepts_open_minor_findings(self) -> None:
        self.create()
        (self.run_dir / "review.json").write_text(json.dumps({
            "status": "passed", "reviewer": "reviewer", "independent": True,
            "findings": [{"severity": "minor"}, {"severity": "suggestion"}],
        }), encoding="utf-8")

        result = record_review(self.run_dir, artifact_ref="review.json")

        self.assertEqual("passed", result["review_receipt"]["verdict"])

    def test_record_review_registers_and_updates_manifest_receipt(self) -> None:
        self.create()
        receipt = self.run_dir / "review.json"
        failed_receipt = self.run_dir / "failed-review.json"
        evidence = self.run_dir / "verification.json"
        evidence.write_text("{}", encoding="utf-8")
        failed_receipt.write_text(
            '{"status":"failed","reviewer":"reviewer","independent":true,"findings":[]}',
            encoding="utf-8",
        )
        receipt.write_text(
            json.dumps(build_review_receipt(
                review_id="review-1", reviewer="reviewer", independent=True,
                review_modes=["record"], status="passed",
                covered_artifacts=[{
                    "path": "verification.json",
                    "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
                }],
                covered_claim_ids=[], findings=[], limitations=["fixture"],
            )),
            encoding="utf-8",
        )
        manifest = new_manifest("run-001", "Question", [])
        manifest["custom"] = {"kept": True}
        manifest_path = self.run_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        unchanged_manifest = manifest_path.read_bytes()
        failed = record_review(self.run_dir, artifact_ref="failed-review.json")
        self.assertEqual(
            {"status": "skipped", "reason": "receipt verdict is not passed"},
            failed["manifest_registration"],
        )
        self.assertEqual(unchanged_manifest, manifest_path.read_bytes())
        self.assertEqual("failed", load_checkpoint(self.run_dir)["review_receipt"]["verdict"])

        result = record_review(self.run_dir, artifact_ref="review.json")
        first = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual({"status": "registered", "path": "review.json", "kind": "review-receipt-v2"}, result["manifest_registration"])
        self.assertEqual(["review.json"], [item["path"] for item in first["artifacts"]])
        self.assertEqual(hashlib.sha256(receipt.read_bytes()).hexdigest(), first["artifacts"][0]["sha256"])

        first["artifacts"][0]["path"] = "./review.json"
        manifest_path.write_text(json.dumps(first, indent=2) + "\n", encoding="utf-8")
        result = record_review(self.run_dir, artifact_ref="review.json")
        normalized = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual("updated", result["manifest_registration"]["status"])
        self.assertEqual(["review.json"], [item["path"] for item in normalized["artifacts"]])
        first = normalized
        original_order = list(first)
        first["artifacts"][0].update({
            "size_bytes": receipt.stat().st_size,
            "entry_count": 1,
            "artifact_type": "file",
            "descriptor_path": "stale-descriptor.json",
            "media_type": "application/json",
            "stale_metadata": "remove-me",
        })
        manifest_path.write_text(json.dumps(first, indent=2) + "\n", encoding="utf-8")
        receipt.write_text(
            json.dumps(build_review_receipt(
                review_id="review-2", reviewer="reviewer", independent=True,
                review_modes=["record"], status="passed",
                covered_artifacts=[{
                    "path": "verification.json",
                    "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
                }],
                covered_claim_ids=[], findings=[], limitations=["updated fixture receipt"],
            )),
            encoding="utf-8",
        )

        result = record_review(self.run_dir, artifact_ref="review.json")
        second = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual("updated", result["manifest_registration"]["status"])
        self.assertEqual(["review.json"], [item["path"] for item in second["artifacts"]])
        self.assertEqual(sorted(original_order), list(second))
        self.assertEqual({"kept": True}, second["custom"])
        self.assertEqual(receipt.stat().st_size, second["artifacts"][0]["size_bytes"])
        self.assertEqual({"path", "kind", "sha256", "size_bytes"}, set(second["artifacts"][0]))
        validate_bundle(second, self.run_dir)

    def test_manifest_write_failure_is_reported_after_checkpoint_recording(self) -> None:
        self.create()
        (self.run_dir / "review.json").write_text(
            '{"status":"passed","reviewer":"reviewer","independent":true,"findings":[]}',
            encoding="utf-8",
        )
        manifest_path = self.run_dir / "manifest.json"
        manifest_path.write_text(json.dumps(new_manifest("run-001", "Question", [])), encoding="utf-8")
        import scripts.science_checkpoint as science_checkpoint_cli
        output = io.StringIO()
        error_output = io.StringIO()
        with mock.patch("sys.argv", ["science_checkpoint.py", "review", str(self.run_dir), "--artifact-ref", "review.json"]), \
                mock.patch("codex_science.checkpoints.write_text_atomic", side_effect=OSError("disk full")), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(error_output):
            exit_code = science_checkpoint_cli.main()
        self.assertEqual(0, exit_code)
        self.assertEqual("passed", load_checkpoint(self.run_dir)["review_receipt"]["verdict"])
        result = json.loads(output.getvalue())
        self.assertEqual(
            {"status": "failed", "reason": "disk full", "checkpoint_recorded": True},
            result["manifest_registration"],
        )
        self.assertEqual(
            "warning: review recorded; manifest registration failed: disk full\n",
            error_output.getvalue(),
        )

    def test_record_review_skips_missing_or_malformed_manifest(self) -> None:
        cases = [
            (None, "manifest.json is missing"),
            (b"{", "manifest.json is malformed or unreadable"),
            (b"[]", "manifest.json is not an object"),
            (b'{"artifacts": {}}', "manifest artifacts is not a list"),
        ]
        for index, (manifest_bytes, expected) in enumerate(cases):
            with self.subTest(manifest=manifest_bytes):
                self.run_dir = Path(self.tempdir.name) / "artifacts" / f"run-{index}"
                self.session_key = f"{index + 1:064x}"
                self.create()
                (self.run_dir / "review.json").write_text(
                    '{"status":"passed","reviewer":"reviewer","independent":true,"findings":[]}',
                    encoding="utf-8",
                )
                manifest_path = self.run_dir / "manifest.json"
                if manifest_bytes is not None:
                    manifest_path.write_bytes(manifest_bytes)
                result = record_review(self.run_dir, artifact_ref="review.json")
                self.assertEqual("skipped", result["manifest_registration"]["status"])
                self.assertEqual(expected, result["manifest_registration"]["reason"])
                self.assertEqual("passed", load_checkpoint(self.run_dir)["review_receipt"]["verdict"])

        self.run_dir = Path(self.tempdir.name) / "artifacts" / "run-invalid-schema"
        self.session_key = "f" * 64
        self.create()
        (self.run_dir / "review.json").write_text(
            '{"status":"passed","reviewer":"reviewer","independent":true,"findings":[]}',
            encoding="utf-8",
        )
        manifest_path = self.run_dir / "manifest.json"
        manifest_path.write_text('{"artifacts": []}', encoding="utf-8")
        result = record_review(self.run_dir, artifact_ref="review.json")
        self.assertEqual("skipped", result["manifest_registration"]["status"])
        self.assertTrue(result["manifest_registration"]["reason"].startswith("Missing manifest fields:"))
        self.assertEqual("passed", load_checkpoint(self.run_dir)["review_receipt"]["verdict"])

    def test_passed_review_rejects_unresolved_major_finding(self) -> None:
        self._assert_passed_review_findings_rejected([{"severity": "major"}])

    def test_passed_review_accepts_resolved_major_finding(self) -> None:
        self.create()
        (self.run_dir / "review.json").write_text(json.dumps({
            "status": "passed", "reviewer": "reviewer", "independent": True,
            "findings": [{"severity": "major", "resolution_status": "resolved"}],
        }), encoding="utf-8")

        result = record_review(self.run_dir, artifact_ref="review.json")

        self.assertEqual("passed", result["review_receipt"]["verdict"])

    def test_passed_review_rejects_finding_without_severity(self) -> None:
        self._assert_passed_review_findings_rejected([{}])

    def _assert_passed_review_findings_rejected(self, findings: list[dict[str, str]]) -> None:
        self.create()
        (self.run_dir / "review.json").write_text(json.dumps({
            "status": "passed", "reviewer": "reviewer", "independent": True,
            "findings": findings,
        }), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "passed review artifact cannot retain unresolved critical or major findings"):
            record_review(self.run_dir, artifact_ref="review.json")

    def test_runtime_switch_is_durably_marked_on_next_checkpoint_write(self) -> None:
        runtime_b = {
            "commit": "b" * 40,
            "receipt_sha256": "b" * 64,
            "runtime_version": "1.0.0+codex.b",
            "source_id": "b" * 16,
        }
        runtime_c = {
            "commit": "c" * 40,
            "receipt_sha256": "c" * 64,
            "runtime_version": "1.0.0+codex.c",
            "source_id": "c" * 16,
        }
        with mock.patch(
            "codex_science.runtime_identity.current_runtime_identity",
            side_effect=[runtime_b, runtime_c],
        ):
            created = self.create()
            (self.run_dir / "runtime-switch.json").write_text(
                '{"status":"observed"}\n', encoding="utf-8"
            )
            changed = heartbeat_checkpoint(
                self.run_dir,
                next_action="Continue with the new verified runtime",
                progress_ref="runtime-switch.json",
            )

        self.assertFalse(created["runtime_span"])
        self.assertTrue(changed["runtime_span"])
        self.assertEqual([runtime_b, runtime_c], changed["runtime_history"])

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

    def test_cli_step_error_includes_correct_format_and_bad_value(self) -> None:
        script = Path(__file__).resolve().parents[1] / "scripts" / "science_checkpoint.py"
        bad_value = "protocol|Freeze protocol"
        completed = subprocess.run(
            [
                sys.executable, str(script), "init", str(self.run_dir),
                "--goal", "Question", "--deliverable", "Report", "--done", "Verified",
                "--step", bad_value, "--next-action", "Inspect inputs", "--hookless",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(2, completed.returncode)
        self.assertIn("--step retrieval='Retrieve and screen sources'", completed.stderr)
        self.assertIn(f"got {bad_value}", completed.stderr)

    def test_cli_advance_reports_advisory_findings_without_changing_checkpoint(self) -> None:
        self.create()
        manifest = new_manifest("run-001", "Question", [{"id": "later", "description": "Later", "status": "pending"}])
        manifest["claims"].append({"id": "c1", "text": "Claim", "evidence": ["missing.json"]})
        (self.run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        script = Path(__file__).resolve().parents[1] / "scripts" / "science_checkpoint.py"
        completed = subprocess.run(
            [sys.executable, str(script), "advance", str(self.run_dir), "--complete", "orient", "--next-action", "Continue"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        output = json.loads(completed.stdout)
        check = output.pop("early_check")
        self.assertEqual("findings", check["status"])
        self.assertTrue(check["advisory"])
        codes = {finding["code"] for finding in check["findings"]}
        self.assertIn("missing-evidence", codes)
        self.assertNotIn("incomplete-plan", codes)
        self.assertEqual(load_checkpoint(self.run_dir), output)

    def test_cli_advance_skips_absent_and_malformed_manifests(self) -> None:
        script = Path(__file__).resolve().parents[1] / "scripts" / "science_checkpoint.py"
        for manifest_text, reason in ((None, "manifest-not-found"), ("{", "invalid-json")):
            with self.subTest(reason=reason):
                self.run_dir = Path(self.tempdir.name) / reason
                self.create()
                if manifest_text is not None:
                    (self.run_dir / "manifest.json").write_text(manifest_text, encoding="utf-8")
                completed = subprocess.run(
                    [sys.executable, str(script), "advance", str(self.run_dir), "--complete", "orient", "--next-action", "Continue"],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(0, completed.returncode, completed.stderr)
                early = json.loads(completed.stdout)["early_check"]
                self.assertEqual("skipped", early["status"])
                self.assertEqual(reason, early["reason"])


if __name__ == "__main__":
    unittest.main()
