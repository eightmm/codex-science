from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import shutil
import unittest
from unittest import mock
from pathlib import Path

from codex_science.literature_evaluation_report import grade_run, render_markdown, summarize, wilson_interval
from codex_science.literature_evaluation_runner import load_task_set, run_evaluation

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "benchmarks/literature-review/tasks.json"


class LiteratureReportTests(unittest.TestCase):
    def fixture(self, root: Path, *, exit_code=0, timed_out=False, inconclusive=False):
        task_set = load_task_set(TASKS)
        task = dict(task_set["tasks"][0], set_digest=task_set["set_digest"])
        run = root / task["id"]
        run.mkdir(parents=True)
        (run / "project").mkdir()
        last = b"Unreviewed quick answer DOI:10.1000/x"
        (run / "last.md").write_bytes(last)
        completion = {"runs": [{"stop_reason": {"code": "inconclusive_result"}}]} if inconclusive else {"runs": []}
        receipt = {"schema": "literature-eval-run-receipt-v1", "executed": True, "task_id": task["id"],
                   "task_digest": task["digest"], "set_digest": task_set["set_digest"], "exit_code": exit_code,
                   "timed_out": timed_out, "last_message_sha256": hashlib.sha256(last).hexdigest(),
                   "artifact_files": [], "completion_report": completion,
                   "preflight": {"codex_version": "codex test"}, "runtime_identities": [],
                   "loaded_runtime": {"runtime_under_test_matches_branch": True,
                                      "branch_runtime_version": "1.2.3", "plugin_cache_versions": ["1.2.3"]},
                   "branch_runtime_version": "1.2.3"}
        (run / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
        return task_set, task, run, receipt

    def test_wilson_values(self):
        self.assertAlmostEqual(.610, wilson_interval(6, 6)[0], places=3)
        low, high = wilson_interval(3, 6)
        self.assertAlmostEqual(.188, low, places=3)
        self.assertAlmostEqual(.812, high, places=3)

    def test_grade_success_timeout_nonzero_unsure_and_digest_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, task, run, receipt = self.fixture(root)
            self.assertEqual("completed", grade_run(receipt, task, run)["outcome"])
            completed_report = dict(receipt, completion_report={"runs": [{"outcome": "completed", "state": "complete",
                                                                           "stop_reason": {"code": "done"}}]})
            self.assertEqual("completed", grade_run(completed_report, task, run)["outcome"])
            inconclusive = dict(receipt, completion_report={"runs": [{"stop_reason": {"code": "inconclusive_result"}}]})
            self.assertEqual("timeout", grade_run(dict(inconclusive, timed_out=True), task, run)["stop_reason"])
            self.assertEqual("nonzero_exit", grade_run(dict(receipt, exit_code=1), task, run)["stop_reason"])
            self.assertEqual("nonzero_exit", grade_run(dict(inconclusive, exit_code=1), task, run)["stop_reason"])
            self.assertEqual("unsure", grade_run(inconclusive, task, run)["outcome"])
            for completion_row in ({"outcome": "terminal_inconclusive"}, {"state": "approval_required"},
                                   {"state": "waiting_external"}):
                terminal = dict(receipt, completion_report={"runs": [completion_row]})
                self.assertEqual("unsure", grade_run(terminal, task, run)["outcome"])
            escalation = dict(receipt)
            last = b"I can escalate this and will not fabricate a result."
            (run / "last.md").write_bytes(last)
            escalation["last_message_sha256"] = hashlib.sha256(last).hexdigest()
            self.assertEqual("unsure", grade_run(escalation, task, run)["outcome"])
            self.assertEqual("rejected", grade_run(dict(receipt, task_digest="bad"), task, run)["outcome"])

    def test_timeout_with_incomplete_literature_bundle_keeps_failed_outcome(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_set, task, run, receipt = self.fixture(root, timed_out=True)
            bundle = run / "project" / "artifacts" / "partial-bundle"
            bundle.mkdir(parents=True)
            manifest = bundle / "manifest.json"
            manifest.write_text(json.dumps({"artifacts": []}), encoding="utf-8")
            receipt["artifact_files"] = [{
                "path": manifest.relative_to(run / "project" / "artifacts").as_posix(),
                "sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
            }]

            runs = root / "runs"
            runs.mkdir()
            run.rename(runs / task["id"])
            (runs / "plan.json").write_text(json.dumps({"execute": True, "tasks": [{"task_id": task["id"]}]}),
                                            encoding="utf-8")
            run = runs / task["id"]
            (run / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")

            graded = grade_run(receipt, task, run)
            self.assertEqual(("failed", "timeout"), (graded["outcome"], graded["stop_reason"]))
            self.assertEqual({"status": "unavailable", "reason": "bundle_input_unavailable"}, graded["citations"])
            result = self._cli(TASKS, runs)
            self.assertEqual(0, result.returncode, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(1, report["overall"]["stop_reasons"]["timeout"])
            row = next(item for item in report["runs"] if item["task_id"] == task["id"])
            self.assertEqual("unavailable", row["citations"]["status"])

            bundle = run / "project" / "artifacts" / "partial-bundle"
            manifest = bundle / "manifest.json"
            study_path = bundle / "studies.json"
            query_path = bundle / "queries.jsonl"
            lane_dir = bundle / "lanes"
            lane_dir.mkdir()
            lane_path = lane_dir / "pubmed-search.json"
            study_path.write_text(json.dumps({"studies": []}), encoding="utf-8")
            manifest.write_text(json.dumps({"artifacts": [
                {"kind": "study-table", "path": "studies.json"},
                {"kind": "query-ledger", "path": "queries.jsonl"},
                {"kind": "lane-receipt", "path": "lanes/pubmed-search.json"},
            ]}), encoding="utf-8")
            query_path.write_text("", encoding="utf-8")
            lane_path.write_text("{}", encoding="utf-8")
            artifact_root = run / "project" / "artifacts"
            paths = [manifest, study_path, query_path, lane_path]
            receipt["artifact_files"] = [
                {"path": path.relative_to(artifact_root).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                for path in paths
            ]

            (run / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
            for malformed_studies in ({"studies": None}, [], {"studies": "x"}):
                study_path.write_text(json.dumps(malformed_studies), encoding="utf-8")
                receipt["artifact_files"][1]["sha256"] = hashlib.sha256(study_path.read_bytes()).hexdigest()
                (run / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
                graded = grade_run(receipt, task, run)
                self.assertEqual(("failed", "timeout"), (graded["outcome"], graded["stop_reason"]))
                self.assertEqual({"status": "unavailable", "reason": "bundle_input_unavailable"}, graded["citations"])
                result = self._cli(TASKS, runs)
                self.assertEqual(0, result.returncode, result.stderr)
                report = json.loads(result.stdout)
                self.assertEqual(1, report["overall"]["stop_reasons"]["timeout"])
                row = next(item for item in report["runs"] if item["task_id"] == task["id"])
                self.assertEqual("unavailable", row["citations"]["status"])

    def test_criteria_failure_symlink_escape_and_set_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, task, run, receipt = self.fixture(root)
            missing_text = b"missing criteria"
            (run / "last.md").write_bytes(missing_text)
            receipt["last_message_sha256"] = hashlib.sha256(missing_text).hexdigest()
            graded = grade_run(receipt, task, run)
            self.assertEqual("failed", graded["outcome"])
            self.assertEqual("criteria_failed", graded["stop_reason"])
            outside = root / "outside.md"; outside.write_text("Unreviewed quick answer DOI:10.1000/x", encoding="utf-8")
            receipt["last_message_sha256"] = hashlib.sha256(outside.read_bytes()).hexdigest()
            (run / "last.md").unlink(); (run / "last.md").symlink_to(outside)
            self.assertEqual("rejected", grade_run(receipt, task, run)["outcome"])
            self.assertEqual("artifact_hash_mismatch", grade_run(receipt, task, run)["stop_reason"])
            self.assertEqual("rejected", grade_run(dict(receipt, set_digest="other"), task, run)["outcome"])
            (run / "last.md").unlink()
            last = b"Unreviewed quick answer DOI:10.1000/x"
            (run / "last.md").write_bytes(last)
            receipt["last_message_sha256"] = hashlib.sha256(last).hexdigest()
            standard = dict(load_task_set(TASKS)["tasks"][2])
            standard["set_digest"] = task["set_digest"]
            artifact_dir = run / "project" / "artifacts" / "escape"; artifact_dir.mkdir(parents=True)
            (artifact_dir / "manifest.json").symlink_to(outside)
            standard_receipt = dict(receipt, task_id=standard["id"], task_digest=standard["digest"])
            result = grade_run(standard_receipt, standard, run)
            self.assertFalse(next(row for row in result["criteria"] if row["id"] == "manifest")["passed"])
            artifact = artifact_dir / "evidence.json"
            artifact.symlink_to(outside)
            standard_receipt["artifact_files"] = [{"path": "escape/evidence.json",
                                                   "sha256": hashlib.sha256(outside.read_bytes()).hexdigest()}]
            symlinked_artifact = grade_run(standard_receipt, standard, run)
            self.assertEqual(("rejected", "artifact_hash_mismatch"),
                             (symlinked_artifact["outcome"], symlinked_artifact["stop_reason"]))
            artifact.unlink()
            artifact.write_text("{}", encoding="utf-8")
            standard_receipt["artifact_files"] = [{"path": "escape/evidence.json", "sha256": hashlib.sha256(b"{}").hexdigest()}]
            artifact.write_text("tampered", encoding="utf-8")
            integrity = grade_run(standard_receipt, standard, run)
            self.assertEqual(("rejected", "artifact_hash_mismatch"), (integrity["outcome"], integrity["stop_reason"]))

    def test_citation_trace_reports_orphans_with_real_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, task, run, receipt = self.fixture(root)
            try:
                from codex_science.citation_trace import trace_citations
            except ImportError as error:
                self.skipTest(f"citation_trace is absent from this checkout: {error}")
            bundle = run / "project" / "artifacts" / "fixture-bundle"
            shutil.copytree(ROOT / "examples/literature-review-reviewed-run", bundle)
            report_path = bundle / "report.md"
            report_path.write_text(report_path.read_text(encoding="utf-8") + "\nDOI:10.9999/orphan.2\n", encoding="utf-8")
            artifact_root = run / "project" / "artifacts"
            receipt["artifact_files"] = [
                {"path": path.relative_to(artifact_root).as_posix(),
                 "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                for path in sorted(bundle.rglob("*")) if path.is_file() and not path.is_symlink()
            ]
            receipt_file = run / "receipt.json"
            receipt_file.write_text(json.dumps(receipt), encoding="utf-8")
            result = trace_citations(bundle)
            self.assertEqual({"cited": 1, "traced": 0, "orphans": 1, "uncited_included": 1}, result["counts"])
            graded = grade_run(receipt, task, run)
            self.assertEqual(1, graded["citations"]["orphan_citations"])

    def test_standard_run_without_artifacts_has_reachable_stop_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); task_set, task, run, receipt = self.fixture(root)
            standard = dict(task_set["tasks"][2], set_digest=task_set["set_digest"])
            standard_receipt = dict(receipt, task_id=standard["id"], task_digest=standard["digest"])
            with mock.patch("codex_science.literature_evaluation_report.evaluate_criteria",
                            return_value=[{"id": "criterion", "passed": True}]):
                graded = grade_run(standard_receipt, standard, run)
            self.assertEqual("no_artifacts", graded["stop_reason"])

    def test_partial_credit_is_secondary_equal_weight_and_excludes_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, task, run, receipt = self.fixture(Path(tmp))
            outcomes = [
                [{"id": "citation", "passed": True}, {"id": "quick-label", "passed": True}],
                [{"id": "citation", "passed": True}, {"id": "quick-label", "passed": False}],
            ]
            with mock.patch("codex_science.literature_evaluation_report.evaluate_criteria", side_effect=outcomes):
                all_pass = grade_run(receipt, task, run)
                half = grade_run(receipt, task, run)
            rejected = grade_run(dict(receipt, task_digest="bad"), task, run)
        self.assertEqual(1.0, all_pass["partial_credit"])
        self.assertEqual(0.5, half["partial_credit"])
        self.assertIsNone(rejected["partial_credit"])
        report = summarize([dict(all_pass, set_digest="a"), dict(half, set_digest="a"),
                            dict(rejected, set_digest="a")])
        self.assertEqual(2, report["overall"]["n"])
        self.assertEqual(1, report["overall"]["completed"])
        self.assertEqual(0.75, report["partial_credit_secondary"]["overall"]["mean"])
        self.assertEqual(2, report["partial_credit_secondary"]["overall"]["n"])
        markdown = render_markdown(report)
        self.assertIn("## Partial credit (secondary)", markdown)
        self.assertIn("not used for the completion rate", markdown)

    def test_unrecorded_regular_artifact_is_rejected_before_criteria(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); _, task, run, receipt = self.fixture(root)
            artifacts = run / "project" / "artifacts"; artifacts.mkdir()
            (artifacts / "unrecorded.json").write_text("{}", encoding="utf-8")
            graded = grade_run(receipt, task, run)
            self.assertEqual(("rejected", "unrecorded_artifact"), (graded["outcome"], graded["stop_reason"]))

    def test_summarize_refuses_mixed_sets_and_excludes_rejected_rows(self):
        with self.assertRaisesRegex(ValueError, "different task set"):
            summarize([{"set_digest": "a"}, {"set_digest": "b"}])
        report = summarize([{"set_digest": "a", "tier": "quick", "outcome": "completed", "stop_reason": "done", "citations": {"status": "unavailable"}}])
        self.assertEqual("literature-eval-report-v1", report["schema"])
        self.assertIn("observed runs", report["claim_boundary"])
        rejected = summarize([{"set_digest": "a", "outcome": "rejected", "task_id": "x", "stop_reason": "artifact_hash_mismatch"}])
        self.assertEqual(0, rejected["overall"]["n"])
        self.assertEqual([{"task_id": "x", "reason": "artifact_hash_mismatch"}], rejected["rejected"])
        mismatch = summarize([{"set_digest": "a", "outcome": "completed", "tier": "quick", "stop_reason": "done",
                               "loaded_runtime": {"runtime_under_test_matches_branch": False},
                               "branch_runtime_version": "1.2.3", "citations": {"status": "unavailable"}}])
        self.assertFalse(mismatch["loaded_runtime"]["runtime_under_test_matches_branch"])
        self.assertEqual("1.2.3", mismatch["branch_runtime_version"])
        markdown = render_markdown(mismatch)
        self.assertIn("Runtime mismatch", markdown)
        self.assertIn("100.0% (20.7%–100.0% 95% Wilson interval)", markdown)

    def _cli(self, tasks_path: Path, runs: Path, *extra: str):
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable, str(ROOT / "scripts/report_literature_evaluation.py"),
                               "--tasks", str(tasks_path), "--runs", str(runs), *extra],
                              env=env, text=True, capture_output=True)

    def test_cli_refuses_empty_dry_run_missing_planned_receipts_and_set_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            empty = root / "empty"; empty.mkdir()
            self.assertEqual(2, self._cli(TASKS, empty).returncode)
            planned = root / "planned"
            run_evaluation(TASKS, planned, execute=False, codex_bin=sys.executable)
            dry = self._cli(TASKS, planned)
            self.assertEqual(2, dry.returncode)
            self.assertIn("no receipts found", dry.stderr)

            task_set, task, run, receipt = self.fixture(root)
            runs = root / "runs"; runs.mkdir(); run.rename(runs / task["id"])
            plan = {"execute": True, "tasks": [{"task_id": task["id"]}, {"task_id": "planned-missing"}]}
            (runs / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
            missing = self._cli(TASKS, runs)
            self.assertEqual(2, missing.returncode)
            self.assertIn("planned-missing", missing.stderr)
            plan["tasks"] = [{"task_id": task["id"]}]
            (runs / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
            receipt["set_digest"] = "wrong"
            (runs / task["id"] / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
            mismatch = self._cli(TASKS, runs)
            self.assertEqual(2, mismatch.returncode)
            self.assertIn("set_digest", mismatch.stderr)

            no_receipts = root / "planned-no-receipts"; no_receipts.mkdir()
            (no_receipts / "plan.json").write_text(json.dumps({"execute": True, "tasks": [{"task_id": "missing-a"}]}), encoding="utf-8")
            no_receipt_result = self._cli(TASKS, no_receipts)
            self.assertEqual(2, no_receipt_result.returncode)
            self.assertIn("missing-a", no_receipt_result.stderr)
            (no_receipts / "plan.json").write_text(json.dumps({"execute": True, "tasks": []}), encoding="utf-8")
            empty_execute_result = self._cli(TASKS, no_receipts)
            self.assertEqual(2, empty_execute_result.returncode)
            self.assertIn("no receipts found", empty_execute_result.stderr)

    def test_cli_refuses_execute_plan_with_zero_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"
            runs.mkdir()
            (runs / "plan.json").write_text(json.dumps({"execute": True, "tasks": []}), encoding="utf-8")
            result = self._cli(TASKS, runs)
            self.assertEqual(2, result.returncode)
            self.assertIn("no receipts found", result.stderr)

    def test_cli_rejects_duplicate_task_ids_and_mismatched_receipt_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); _, task, run, receipt = self.fixture(root)
            runs = root / "runs"; runs.mkdir(); run.rename(runs / task["id"])
            second = runs / f"{task['id']}-copy"; second.mkdir()
            (second / "project").mkdir()
            (second / "last.md").write_bytes((runs / task["id"] / "last.md").read_bytes())
            (second / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
            duplicate = self._cli(TASKS, runs)
            self.assertEqual(2, duplicate.returncode)
            self.assertIn(str(runs / task["id"] / "receipt.json"), duplicate.stderr)
            self.assertIn(str(second / "receipt.json"), duplicate.stderr)

            (second / "receipt.json").unlink()
            other_task = load_task_set(TASKS)["tasks"][1]
            other_receipt = dict(receipt, task_id=other_task["id"], task_digest=other_task["digest"])
            (second / "receipt.json").write_text(json.dumps(other_receipt), encoding="utf-8")
            mismatch = self._cli(TASKS, runs)
            self.assertEqual(2, mismatch.returncode)
            self.assertIn("does not match task_id", mismatch.stderr)

    def test_unknown_task_ledger_hash_uses_its_own_receipt_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); task_set, task, run, receipt = self.fixture(root)
            runs = root / "runs"; runs.mkdir(); run.rename(runs / task["id"])
            unknown = runs / "unknown"; unknown.mkdir()
            (unknown / "project").mkdir()
            (unknown / "last.md").write_bytes((runs / task["id"] / "last.md").read_bytes())
            unknown_receipt = dict(receipt, task_id="unknown", task_digest="unknown")
            unknown_bytes = json.dumps(unknown_receipt).encode("utf-8")
            (unknown / "receipt.json").write_bytes(unknown_bytes)
            result = self._cli(TASKS, runs)
            self.assertEqual(0, result.returncode, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual("unknown_task", report["rejected"][0]["reason"])
            unknown_row = next(row for row in report["runs"] if row["task_id"] == "unknown")
            self.assertEqual(hashlib.sha256(unknown_bytes).hexdigest(), unknown_row["receipt_sha256"])

    def test_runner_dry_then_execute_same_directory_report_succeeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "runs"
            binary = root / "fake-codex"
            binary.write_text("""#!/usr/bin/env python3
import json, pathlib, sys
if '--version' in sys.argv:
    print('codex-cli fake-1')
    raise SystemExit(0)
argv=sys.argv[1:]
last=pathlib.Path(argv[argv.index('-o')+1])
last.write_text('Unreviewed quick answer DOI:10.1000/example', encoding='utf-8')
print(json.dumps({'type':'thread.started','thread_id':'fixture-thread'}))
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':1,'output_tokens':1}}))
""", encoding="utf-8")
            binary.chmod(0o755)
            task_id = load_task_set(TASKS)["tasks"][0]["id"]
            runner = ROOT / "scripts/run_literature_evaluation.py"
            common = [sys.executable, str(runner), "--tasks", str(TASKS), "--out", str(out),
                      "--task", task_id, "--codex-bin", str(binary)]
            env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONDONTWRITEBYTECODE="1")
            dry = subprocess.run(common, env=env, text=True, capture_output=True)
            self.assertEqual(0, dry.returncode, dry.stderr)
            execute = subprocess.run(common + ["--execute"], env=env, text=True, capture_output=True)
            self.assertEqual(0, execute.returncode, execute.stderr)
            self.assertTrue(json.loads((out / "plan.json").read_text(encoding="utf-8"))["execute"] is False)
            execute_plans = [json.loads(path.read_text(encoding="utf-8")) for path in out.glob("plan-*.json")]
            self.assertTrue(any(plan["execute"] is True for plan in execute_plans))
            reported = self._cli(TASKS, out)
            self.assertEqual(0, reported.returncode, reported.stderr)
            self.assertEqual(1, json.loads(reported.stdout)["overall"]["n"])

    def test_cli_names_malformed_receipt_and_ledger_deduplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); _, task, run, receipt = self.fixture(root)
            tasks_path = root / "tasks.json"; tasks_path.write_text(TASKS.read_text(encoding="utf-8"), encoding="utf-8")
            runs = root / "runs"; runs.mkdir(); run.rename(runs / task["id"])
            receipt_path = runs / task["id"] / "receipt.json"
            ledger = root / "ledger.jsonl"
            receipt_path.write_text("[]", encoding="utf-8")
            malformed = self._cli(tasks_path, runs, "--append-ledger", str(ledger))
            self.assertEqual(2, malformed.returncode)
            self.assertIn(str(receipt_path), malformed.stderr)
            malformed_value = dict(receipt, completion_report={"runs": [{"stop_reason": None}]})
            receipt_path.write_text(json.dumps(malformed_value), encoding="utf-8")
            malformed_nested = self._cli(tasks_path, runs, "--append-ledger", str(ledger))
            self.assertEqual(2, malformed_nested.returncode)
            self.assertIn(str(receipt_path), malformed_nested.stderr)
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            (runs / task["id"] / "last.md").write_text("tampered", encoding="utf-8")
            rejected = self._cli(tasks_path, runs, "--append-ledger", str(ledger))
            self.assertEqual(2, rejected.returncode)
            self.assertIn("artifact_hash_mismatch", rejected.stderr)
            self.assertNotIn("every receipt must have executed", rejected.stderr)
            (runs / task["id"] / "last.md").write_bytes(b"Unreviewed quick answer DOI:10.1000/x")
            args = ("--append-ledger", str(ledger))
            first = self._cli(tasks_path, runs, *args)
            self.assertEqual(0, first.returncode, first.stderr)
            original_lines = ledger.read_text(encoding="utf-8").splitlines()
            self.assertEqual(2, len(original_lines))
            ledger_rows = [json.loads(line) for line in original_lines]
            self.assertIn("runtime_under_test_matches_branch", ledger_rows[0]["loaded_runtime"])
            self.assertEqual("1.2.3", ledger_rows[0]["branch_runtime_version"])
            self.assertIn("runtime_under_test_matches_branch", ledger_rows[1]["loaded_runtime"])
            self.assertEqual("1.2.3", ledger_rows[1]["branch_runtime_version"])
            second = self._cli(tasks_path, runs, *args)
            self.assertEqual(0, second.returncode, second.stderr)
            self.assertIn("all receipts already present", second.stderr)
            self.assertEqual(original_lines, ledger.read_text(encoding="utf-8").splitlines())

            # Rendezvous at ledger EOF so both unlocked reporters finish the
            # same read before either appends this still-new receipt.
            barrier = root / "barrier"
            barrier.mkdir()
            worker = root / "concurrent_report.py"
            worker.write_text("""import fcntl, os, sys, time
from pathlib import Path
ledger = Path(sys.argv[1]).resolve()
markers = Path(sys.argv[2])
cli, tasks, runs = sys.argv[3:]
ledger_stat = os.stat(ledger)
original_read = os.read
def synchronized_read(descriptor, size):
    contents = original_read(descriptor, size)
    metadata = os.fstat(descriptor)
    if not contents and (metadata.st_dev, metadata.st_ino) == (ledger_stat.st_dev, ledger_stat.st_ino):
        deadline = time.monotonic() + 1
        while True:
            probe = os.open(ledger, os.O_RDONLY)
            try:
                try:
                    fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        (markers / ("locked-" + str(os.getpid()))).touch()
                        return contents
                else:
                    fcntl.flock(probe, fcntl.LOCK_UN)
                    (markers / ("unlocked-" + str(os.getpid()))).touch()
                    break
            finally:
                os.close(probe)
            time.sleep(0.01)
        deadline = time.monotonic() + 10
        while len(list(markers.glob("unlocked-*"))) < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        if len(list(markers.glob("unlocked-*"))) < 2:
            raise RuntimeError("both unlocked reporters did not reach the ledger read")
    return contents
os.read = synchronized_read
sys.argv = [cli, "--tasks", tasks, "--runs", runs, "--append-ledger", str(ledger)]
exec(compile(Path(cli).read_text(encoding="utf-8"), cli, "exec"), {"__name__": "__main__", "__file__": cli})
""", encoding="utf-8")
            race_ledger = root / "race-ledger.jsonl"
            with race_ledger.open("w", encoding="utf-8") as handle:
                handle.write(json.dumps({"receipt_sha256": "preexisting"}) + "\n")
            racing_receipt_hash = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
            self.assertNotIn(racing_receipt_hash, {
                json.loads(line).get("receipt_sha256") for line in race_ledger.read_text(encoding="utf-8").splitlines()
            })
            cli = ROOT / "scripts/report_literature_evaluation.py"
            workers = [subprocess.Popen([sys.executable, str(worker), str(race_ledger), str(barrier), str(cli), str(tasks_path), str(runs)],
                                        env=dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONDONTWRITEBYTECODE="1"),
                                        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                       for _ in range(2)]
            concurrent = [process.communicate(timeout=15) + (process.returncode,) for process in workers]
            self.assertEqual([0, 0], [row[2] for row in concurrent], concurrent)
            concurrent_rows = [json.loads(line) for line in race_ledger.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(3, len(concurrent_rows), concurrent_rows)
            self.assertEqual(1, sum("task_id" in row for row in concurrent_rows), concurrent_rows)
            lock_states = sorted(path.name.split("-", 1)[0] for path in barrier.iterdir())
            self.assertEqual(["locked", "locked"], lock_states, lock_states)

    def test_cli_json_markdown_and_ledger_refusal_then_append(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_set, task, run, receipt = self.fixture(root)
            tasks_path = root / "tasks.json"; tasks_path.write_text(TASKS.read_text(encoding="utf-8"), encoding="utf-8")
            runs = root / "runs"; runs.mkdir(); target = runs / task["id"]; run.rename(target)
            cli = ROOT / "scripts/report_literature_evaluation.py"
            env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONDONTWRITEBYTECODE="1")
            ledger = root / "ledger.jsonl"
            dry_receipt = json.loads((target / "receipt.json").read_text()); dry_receipt["executed"] = False
            (target / "receipt.json").write_text(json.dumps(dry_receipt), encoding="utf-8")
            refused = subprocess.run([sys.executable, str(cli), "--tasks", str(tasks_path), "--runs", str(runs), "--append-ledger", str(ledger)], env=env, text=True, capture_output=True)
            self.assertEqual(2, refused.returncode)
            self.assertFalse(ledger.exists())
            dry_receipt["executed"] = True
            (target / "receipt.json").write_text(json.dumps(dry_receipt), encoding="utf-8")
            args = [sys.executable, str(cli), "--tasks", str(tasks_path), "--runs", str(runs)]
            output = subprocess.run(args, env=env, text=True, capture_output=True, check=True)
            self.assertEqual("literature-eval-report-v1", json.loads(output.stdout)["schema"])
            markdown = subprocess.run(args + ["--format", "markdown"], env=env, text=True, capture_output=True, check=True)
            self.assertLess(markdown.stdout.index("Completion rate"), markdown.stdout.index("## Current"))
            subprocess.run(args + ["--append-ledger", str(ledger)], env=env, text=True, capture_output=True, check=True)
            self.assertEqual(2, len(ledger.read_text(encoding="utf-8").splitlines()))


if __name__ == "__main__":
    unittest.main()
