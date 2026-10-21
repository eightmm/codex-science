from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import stat
import sys
import tempfile
import types
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "benchmarks" / "literature-review" / "tasks.json"
FORBIDDEN = {"--ephemeral", "--ignore-user-config", "--dangerously-bypass-approvals-and-sandbox",
             "--approve-for-me", "-a"}


class LiteratureEvaluationTests(unittest.TestCase):
    def _run(self, *args: str, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONDONTWRITEBYTECODE="1")
        env.update(extra_env or {})
        return subprocess.run([sys.executable, str(ROOT / "scripts/run_literature_evaluation.py"), *args],
                              cwd=ROOT, env=env, text=True, capture_output=True, check=False)

    def _codex_home(self, root: Path) -> Path:
        home = root / "codex-home"
        home.mkdir()
        (home / "config.toml").write_text('''
sandbox_mode = "danger-full-access"
approval_policy = "on-request"
approvals_reviewer = "guardian_subagent"

[plugins."codex-science@codex-science"]
enabled = true

[hooks.state]
"codex-science@codex-science:hooks/hooks.json:session_start:0:0" = { enabled = true }
"codex-science@codex-science:hooks/hooks.json:stop:0:0" = { enabled = false }
''', encoding="utf-8")
        manifest = home / "plugins/cache/codex-science/codex-science/0.5.0/.codex-plugin/plugin.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({"name": "codex-science", "version": "0.5.0-test"}), encoding="utf-8")
        return home

    def _fake_codex(self, root: Path) -> Path:
        binary = root / "fake-codex"
        example = repr(str(ROOT / "examples/literature-review-reviewed-run/manifest.json"))
        binary.write_text(f'''#!/usr/bin/env python3
import hashlib, json, os, pathlib, sys, time
if "--version" in sys.argv:
 print("codex-cli fake-1"); raise SystemExit(0)
if os.environ.get("FAKE_INVOCATIONS"):
 pathlib.Path(os.environ["FAKE_INVOCATIONS"]).open("a").write(json.dumps(sys.argv[1:])+"\\n")
if os.environ.get("FAKE_CODEX_HOME_RECORD"):
 pathlib.Path(os.environ["FAKE_CODEX_HOME_RECORD"]).write_text(os.environ.get("CODEX_HOME", "<unset>"))
assert sys.stdin.read() == ""
if os.environ.get("FAKE_SLEEP"): time.sleep(float(os.environ["FAKE_SLEEP"]))
argv=sys.argv[1:]
project=pathlib.Path(argv[argv.index("-C")+1])
last=pathlib.Path(argv[argv.index("-o")+1])
prompt=argv[-1]
if os.environ.get("FAKE_REALISTIC") == "1":
 from codex_science.checkpoints import advance_checkpoint, complete_checkpoint, create_checkpoint, record_review, verify_criterion
 from codex_science.artifacts import write_manifest
 run_dir=project/"artifacts"/"fixture-run"
 tier="full" if "full tier" in prompt else "standard"
 create_checkpoint(run_dir, goal="Fixture research question", deliverable="Reviewed report",
   done_criteria=["Evidence is checked"], steps=[("review", "Review evidence")], next_action="Review evidence",
   session_key=hashlib.sha256(str(project).encode()).hexdigest(), rigor_tier=tier)
 advance_checkpoint(run_dir, completed_step="review", next_step=None, next_action="Verify evidence")
 (run_dir/"evidence.json").write_text('{{"status":"passed"}}\\n')
 verify_criterion(run_dir, "criterion-1", ["evidence.json"])
 (run_dir/"review.json").write_text('{{"status":"passed","reviewer":"fixture-reviewer","independent":true,"findings":[]}}\\n')
 record_review(run_dir, artifact_ref="review.json")
 complete_checkpoint(run_dir)
 manifest=json.loads(pathlib.Path({example}).read_text())
 manifest["run_id"]="fixture-run"
 manifest["question"]="Fixture research question"
 write_manifest(manifest, run_dir/"manifest.json")
else:
 if os.environ.get("FAKE_SAMPLE_ARTIFACT") == "1":
  (project/"artifacts").mkdir(exist_ok=True)
  (project/"artifacts"/"sample.json").write_text('{{"ok":true}}')
if os.environ.get("FAKE_CHECKPOINT") == "active":
 from codex_science.checkpoints import create_checkpoint
 run_dir=project/"artifacts"/"fixture-run"
 create_checkpoint(run_dir, goal="Fixture research question", deliverable="Reviewed report",
   done_criteria=["Evidence is checked"], steps=[("review", "Review evidence")], next_action="Review evidence",
   session_key=hashlib.sha256(str(project).encode()).hexdigest(), rigor_tier="standard")
elif os.environ.get("FAKE_CHECKPOINT") == "partial":
 from codex_science.checkpoints import create_checkpoint, finish_partial, record_attempt
 run_dir=project/"artifacts"/"fixture-run"
 create_checkpoint(run_dir, goal="Fixture research question", deliverable="Reviewed report",
   done_criteria=["Evidence is checked"], steps=[("review", "Review evidence")], next_action="Review evidence",
   session_key=hashlib.sha256(str(project).encode()).hexdigest(), rigor_tier="standard",
   budget_policy="tier-v1")
 record_attempt(run_dir, failure_class="network", approach="route-1", outcome="failed", next_action="try another route")
 record_attempt(run_dir, failure_class="network", approach="route-2", outcome="failed", next_action="finish with partial result")
 (run_dir/"partial-result.json").write_text('{{"schema_version":1,"status":"partial","result_refs":[],"unmet_criteria":["criterion-1"],"unfinished_steps":["review"],"caveats":["incomplete"],"review_status":"not reviewed"}}')
 finish_partial(run_dir, artifact_ref="partial-result.json")
if os.environ.get("FAKE_NO_LAST") != "1":
 last.write_text(os.environ.get("FAKE_LAST_CONTENT", "unreviewed quick answer DOI:10.1000/example"))
if os.environ.get("FAKE_COMMAND"):
 print(json.dumps({{"type":"item.completed","item":{{"type":"command_execution","command":os.environ["FAKE_COMMAND"],"status":"completed","exit_code":int(os.environ.get("FAKE_EXIT", "0"))}}}}))
print(json.dumps({{"type":"thread.started","thread_id":"fake-thread"}}))
if int(os.environ.get("FAKE_EXIT", "0")) == 0:
 print(json.dumps({{"type":"turn.completed","usage":{{"input_tokens":40,"cached_input_tokens":10,"output_tokens":12,"reasoning_tokens":3}}}}))
raise SystemExit(int(os.environ.get("FAKE_EXIT", "0")))
''', encoding="utf-8")
        binary.chmod(0o755)
        return binary

    def test_frozen_task_set_digests_tiers_and_criterion_schemas(self) -> None:
        from codex_science.literature_evaluation_runner import load_task_set, task_digest
        from codex_science.rigor import classify_rigor
        data = load_task_set(TASKS)
        self.assertEqual(6, len(data["tasks"]))
        for task in data["tasks"]:
            self.assertEqual(task_digest(task["spec"]), task["digest"])
            self.assertEqual(task["spec"]["expected_tier"], classify_rigor(task["spec"]["rigor_request"])["tier"])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tampered.json"
            tampered = json.loads(TASKS.read_text(encoding="utf-8"))
            tampered["tasks"][0]["spec"]["question"] += " changed"
            path.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                load_task_set(path)
            unknown = json.loads(TASKS.read_text(encoding="utf-8"))
            unknown["tasks"][0]["spec"]["criteria"][0]["kind"] = "semantic_score"
            unknown["tasks"][0]["digest"] = task_digest(unknown["tasks"][0]["spec"])
            unknown["set_digest"] = hashlib.sha256(json.dumps(
                {"task_digests": [task["digest"] for task in unknown["tasks"]], "canary": unknown["canary"]},
                sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
            path.write_text(json.dumps(unknown), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "criterion kind"):
                load_task_set(path)

    def test_citation_criteria_match_common_identifier_forms(self) -> None:
        data = json.loads(TASKS.read_text(encoding="utf-8"))
        examples = ["**10.1126/science.1232033**",
                    "[10.1126/science.1231143](https://doi.org/10.1126/science.1231143)",
                    "PMID 12345678", "pmid: 12345678", "PMCID PMC1234567",
                    "arXiv 2401.12345", "arXiv:2401.12345"]
        for task in data["tasks"]:
            criterion = next(item for item in task["spec"]["criteria"] if item["id"] == "citation")
            for citation in examples:
                self.assertRegex(citation, re.compile(criterion["arg"], re.IGNORECASE),
                                 f"{task['id']} did not match {citation!r}")

    def test_dry_run_records_preflight_and_executes_no_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = self._fake_codex(root)
            codex_home = self._codex_home(root)
            out = root / "out"
            invocations = root / "exec-invocations.jsonl"
            result = self._run("--tasks", str(TASKS), "--out", str(out), "--codex-bin", str(binary),
                               "--codex-home", str(codex_home),
                               extra_env={"FAKE_INVOCATIONS": str(invocations),
                                          "FAKE_CODEX_HOME_RECORD": str(root / "codex-home-seen")})
            self.assertEqual(0, result.returncode, result.stderr)
            plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
            self.assertEqual(6, len(plan["tasks"]))
            self.assertEqual("codex-cli fake-1", plan["preflight"]["codex_version"])
            self.assertTrue(plan["preflight"]["codex_science_enabled"])
            self.assertEqual("0.5.0-test", plan["preflight"]["installed_plugin_version"])
            self.assertEqual("danger-full-access", plan["preflight"]["configured"]["sandbox_mode"])
            self.assertEqual("workspace-write", plan["preflight"]["argv_overrides"]["sandbox_mode"])
            self.assertIn("installed_runtime_differs_from_branch", plan["preflight"]["warnings"])
            self.assertEqual([True, False], [item["enabled"] for item in plan["preflight"]["codex_science_hooks_state"]])
            self.assertNotIn(str(codex_home), json.dumps(plan))
            self.assertFalse(invocations.exists(), "dry run must not execute any codex task")
            self.assertFalse((root / "codex-home-seen").exists())
            self.assertFalse((out / "quick-doi").exists())
            self.assertEqual(0o600, stat.S_IMODE((out / "plan.json").stat().st_mode))
            for entry in plan["tasks"]:
                argv = entry["argv"]
                self.assertTrue(FORBIDDEN.isdisjoint(argv))
                task_dir = out / entry["task_id"]
                question = next(task["spec"]["question"] for task in json.loads(TASKS.read_text(encoding="utf-8"))["tasks"]
                                if task["id"] == entry["task_id"])
                tier = next(task["spec"]["expected_tier"] for task in json.loads(TASKS.read_text(encoding="utf-8"))["tasks"]
                            if task["id"] == entry["task_id"])
                expected_prompt = (f"$codex-science {question}\n\n"
                                   f"Work autonomously to completion within the {tier} tier.")
                self.assertEqual([str(binary), "exec", "-C", str(task_dir / "project"),
                                  "-s", "workspace-write", "-c", "sandbox_workspace_write.network_access=true",
                                  "-c", 'approval_policy="never"', "-c", 'approvals_reviewer="user"',
                                  "--json", "-o", str(task_dir / "last.md"), expected_prompt], argv)
                self.assertEqual("devnull", entry["stdin"])

    def test_task_filter_existing_target_and_execute_plan_does_not_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = self._fake_codex(root)
            home = self._codex_home(root)
            out = root / "out"
            result = self._run("--tasks", str(TASKS), "--out", str(out), "--task", "quick-doi",
                               "--codex-bin", str(binary), "--codex-home", str(home))
            self.assertEqual(0, result.returncode, result.stderr)
            original_plan = (out / "plan.json").read_bytes()
            self.assertEqual(["quick-doi"], [t["task_id"] for t in json.loads(original_plan)["tasks"]])
            result = self._run("--tasks", str(TASKS), "--out", str(out), "--task", "quick-doi", "--execute",
                               "--codex-bin", str(binary), "--codex-home", str(home))
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(original_plan, (out / "plan.json").read_bytes())
            self.assertEqual(1, len(list(out.glob("plan-*.json"))))
            target = root / "existing"
            (target / "quick-doi").mkdir(parents=True)
            result = self._run("--tasks", str(TASKS), "--out", str(target), "--task", "quick-doi", "--execute",
                               "--codex-bin", str(binary), "--codex-home", str(home))
            self.assertEqual(2, result.returncode)
            self.assertIn("pass a new --out", result.stderr)

    def test_dry_runs_atomically_replace_plan_in_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = self._fake_codex(root)
            home = self._codex_home(root)
            out = root / "out"
            args = ["--tasks", str(TASKS), "--out", str(out), "--codex-bin", str(binary),
                    "--codex-home", str(home)]
            first = self._run(*args, "--task", "quick-doi")
            self.assertEqual(0, first.returncode, first.stderr)
            first_plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
            self.assertEqual(["quick-doi"], [task["task_id"] for task in first_plan["tasks"]])
            second = self._run(*args, "--task", "quick-arxiv")
            self.assertEqual(0, second.returncode, second.stderr)
            second_plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
            self.assertEqual(["quick-arxiv"], [task["task_id"] for task in second_plan["tasks"]])
            self.assertNotEqual(first_plan, second_plan)

    def test_output_schema_opt_in_and_completion_record_cross_check(self) -> None:
        schema = ROOT / "benchmarks/literature-review/completion-record.schema.json"
        valid = json.dumps({"status": "quick_answer", "run_id": None, "deliverables": [],
                            "citations": ["DOI:10.1000/example"], "caveats": [], "summary": "Answer"})
        inconsistent = json.dumps({"status": "completed", "run_id": "missing-run", "deliverables": [],
                                   "citations": [], "caveats": [], "summary": "Answer"})
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary, home = self._fake_codex(root), self._codex_home(root)
            dry = root / "dry"
            result = self._run("--tasks", str(TASKS), "--out", str(dry), "--task", "quick-doi",
                               "--codex-bin", str(binary), "--codex-home", str(home), "--output-schema")
            self.assertEqual(0, result.returncode, result.stderr)
            plan = json.loads((dry / "plan.json").read_text(encoding="utf-8"))
            argv = plan["tasks"][0]["argv"]
            self.assertEqual(str(schema.resolve()), argv[argv.index("--output-schema") + 1])
            self.assertEqual(hashlib.sha256(schema.read_bytes()).hexdigest(), plan["output_schema_sha256"])
            self.assertIn("final message as the JSON completion record", argv[-1])

            for name, body, expected_valid, expected_mismatches, extra in [
                ("valid", valid, True, [], {}),
                ("inconsistent", inconsistent, True,
                 ["completed status requires the named run to be completed in completion_report"],
                 {"FAKE_CHECKPOINT": "active"}),
                ("invalid-json", "not json", False, ["not_checked: completion record invalid"], {}),
                ("partial-consistent", json.dumps({"status": "partial", "run_id": "fixture-run",
                    "deliverables": [], "citations": [], "caveats": [], "summary": "Partial"}), True, [],
                 {"FAKE_CHECKPOINT": "partial"}),
                ("partial-inconsistent", json.dumps({"status": "partial", "run_id": "other-run",
                    "deliverables": [], "citations": [], "caveats": [], "summary": "Partial"}), True,
                 ["partial requires the named run to be terminal_inconclusive with budget_exhausted"],
                 {"FAKE_CHECKPOINT": "partial"}),
                ("quick-with-checkpoint", valid, True, ["quick_answer requires no checkpoint runs"],
                 {"FAKE_CHECKPOINT": "active"}),
                ("completed-active", inconsistent.replace("missing-run", "fixture-run"), True,
                 ["completed status requires the named run to be completed in completion_report"],
                 {"FAKE_CHECKPOINT": "active"}),
                ("completed-consistent", inconsistent.replace("missing-run", "fixture-run"), True, [],
                 {"FAKE_REALISTIC": "1"}),
            ]:
                out = root / name
                result = self._run("--tasks", str(TASKS), "--out", str(out), "--task", "quick-doi",
                                   "--execute", "--output-schema", "--codex-bin", str(binary),
                                   "--codex-home", str(home), extra_env={"FAKE_LAST_CONTENT": body, **extra})
                self.assertEqual(0, result.returncode, result.stderr)
                receipt = json.loads((out / "quick-doi/receipt.json").read_text(encoding="utf-8"))
                self.assertEqual(expected_valid, receipt["completion_record"]["valid"])
                self.assertEqual(expected_mismatches, receipt["completion_record_consistent"])
                self.assertEqual(hashlib.sha256(schema.read_bytes()).hexdigest(), receipt["output_schema_sha256"])
                if name == "invalid-json":
                    self.assertTrue(receipt["completion_record"]["errors"])
            from codex_science.literature_evaluation_runner import _completion_consistency
            valid_record = json.loads(valid)
            valid_record["valid"] = True
            for report_status in ("unavailable", "invalid"):
                with self.subTest(completion_report_status=report_status):
                    self.assertEqual(["completion_report_unavailable"], _completion_consistency(
                        valid_record, {"schema": "completion-report-v1", "status": report_status, "runs": []}))
            from codex_science.literature_evaluation_runner import _completion_consistency
            empty_report = {"schema": "completion-report-v1", "runs": []}
            for claim in ("completed", "partial"):
                record = {**valid_record, "status": claim, "run_id": "missing"}
                self.assertEqual(["claimed_run_missing"], _completion_consistency(record, empty_report))
            for claim in ("inconclusive", "needs_human"):
                record = {**valid_record, "status": claim, "run_id": None}
                self.assertEqual(["not_checked: no run_id"], _completion_consistency(record, empty_report))
                record["run_id"] = "missing"
                self.assertEqual(["claimed_run_missing"], _completion_consistency(record, empty_report))
                record["run_id"] = "done"
                report = {"schema": "completion-report-v1", "runs": [{"run_id": "done", "outcome": "completed"}]}
                self.assertEqual([f"{claim} status names a completed run"], _completion_consistency(record, report))

    def test_fake_completed_failed_timeout_empty_message_and_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = self._fake_codex(root)
            home = self._codex_home(root)
            cases = [("quick-doi", "success", {"FAKE_SAMPLE_ARTIFACT": "1"}, 0, False, True),
                     ("quick-arxiv", "nonzero", {"FAKE_EXIT": "7", "FAKE_SAMPLE_ARTIFACT": "1"}, 7, False, True),
                     ("quick-doi", "timeout", {"FAKE_SLEEP": "2"}, -9, True, False),
                     ("quick-doi", "empty-message", {"FAKE_NO_LAST": "1"}, 0, False, False)]
            for task_id, name, extra, expected_exit, timed_out, has_artifact in cases:
                out = root / name
                home_seen = root / f"{name}-codex-home-seen"
                env = {"PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1",
                       "FAKE_CODEX_HOME_RECORD": str(home_seen), **extra}
                result = subprocess.run([sys.executable, str(ROOT / "scripts/run_literature_evaluation.py"),
                                         "--tasks", str(TASKS), "--out", str(out), "--task", task_id,
                                         "--execute", "--timeout-seconds", "1", "--codex-bin", str(binary),
                                         "--codex-home", str(home)], cwd=ROOT, env=dict(os.environ, **env),
                                        text=True, capture_output=True, check=False)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual(str(home), home_seen.read_text(encoding="utf-8"))
                task_dir = out / task_id
                for path in (task_dir / "receipt.json", task_dir / "events.jsonl",
                             task_dir / "stderr.log", task_dir / "last.md"):
                    self.assertEqual(0o600, stat.S_IMODE(path.stat().st_mode), path)
                receipt = json.loads((task_dir / "receipt.json").read_text(encoding="utf-8"))
                self.assertTrue(receipt["executed"])
                self.assertEqual(timed_out, receipt["timed_out"])
                self.assertEqual(expected_exit, receipt["exit_code"])
                self.assertEqual(has_artifact, bool(receipt["artifact_files"]))
                self.assertEqual(hashlib.sha256((task_dir / "events.jsonl").read_bytes()).hexdigest(),
                                 receipt["events_sha256"])
                self.assertEqual(hashlib.sha256((task_dir / "last.md").read_bytes()).hexdigest(),
                                 receipt["last_message_sha256"])
                self.assertTrue(FORBIDDEN.isdisjoint(receipt["argv"]))
                self.assertEqual(name != "empty-message" and not timed_out,
                                 receipt["last_message_present"])
                if name == "empty-message":
                    self.assertEqual(0, receipt["last_message_size_bytes"])
                self.assertEqual("timeout" if timed_out else "interrupted" if expected_exit else "completed",
                                 receipt["event_metrics"]["terminal_stop_reason"])
                self.assertEqual("0.5.0-test", receipt["preflight"]["installed_plugin_version"])
                completion = receipt["completion_report"]
                self.assertTrue(completion.get("schema") == "completion-report-v1"
                                or completion.get("status") in {"unavailable", "no_artifacts"})

    def test_missing_codex_binary_records_launch_error_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "out"
            home = self._codex_home(root)
            result = self._run("--tasks", str(TASKS), "--out", str(out), "--task", "quick-doi", "--execute",
                               "--codex-bin", str(root / "missing-codex"), "--codex-home", str(home))
            self.assertEqual(0, result.returncode, result.stderr)
            receipt = json.loads((out / "quick-doi/receipt.json").read_text(encoding="utf-8"))
            self.assertEqual("Codex executable not found", receipt["launch_error"])
            self.assertIsNone(receipt["exit_code"])
            self.assertFalse(receipt["last_message_present"])

    def test_non_executable_codex_binary_records_launch_error_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = root / "non-executable-codex"
            binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            binary.chmod(0o644)
            out = root / "out"
            home = self._codex_home(root)
            result = self._run("--tasks", str(TASKS), "--out", str(out), "--task", "quick-doi", "--execute",
                               "--codex-bin", str(binary), "--codex-home", str(home))
            self.assertEqual(0, result.returncode, result.stderr)
            receipt = json.loads((out / "quick-doi/receipt.json").read_text(encoding="utf-8"))
            self.assertTrue(receipt["launch_error"])
            self.assertIsNone(receipt["exit_code"])

    def test_loaded_runtime_comes_only_from_command_event_paths(self) -> None:
        from codex_science.literature_evaluation_runner import _loaded_runtime

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = self._fake_codex(root)
            home = self._codex_home(root)
            out = root / "out"
            command = ("cat ~/.codex/plugins/cache/codex-science/codex-science/"
                       "0.5.0+installed/skills/codex-science/SKILL.md; cat "
                       "~/.codex/plugins/cache/codex-science/codex-science/0.5.1+other/"
                       "skills/literature-review/SKILL.md; echo private-command")
            result = self._run("--tasks", str(TASKS), "--out", str(out), "--task", "quick-doi", "--execute",
                               "--codex-bin", str(binary), "--codex-home", str(home),
                               extra_env={"FAKE_COMMAND": command})
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("warning: installed_runtime_differs_from_branch", result.stderr)
            receipt = json.loads((out / "quick-doi/receipt.json").read_text(encoding="utf-8"))
            loaded = receipt["loaded_runtime"]
            self.assertEqual(["0.5.0+installed", "0.5.1+other"], loaded["plugin_cache_versions"])
            self.assertEqual(["skills/codex-science/SKILL.md", "skills/literature-review/SKILL.md"],
                             loaded["skill_paths"])
            branch_version = json.loads((ROOT / "release/manifest.json").read_text(encoding="utf-8"))["runtime_version"]
            self.assertEqual(branch_version, loaded["branch_runtime_version"])
            self.assertFalse(loaded["runtime_under_test_matches_branch"])
            self.assertNotIn("private-command", json.dumps(loaded))
            self.assertNotIn("cat", json.dumps(loaded))
            matching_events = root / "matching-events.jsonl"
            matching_events.write_text(json.dumps({"event": {
                "type": "item.completed", "item": {"type": "command_execution",
                    "exit_code": 0,
                    "command": ("cat ~/.codex/plugins/cache/codex-science/codex-science/"
                    f"{branch_version}/skills/codex-science/SKILL.md")}},
                "t": 0.0}) + "\n", encoding="utf-8")
            with matching_events.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"event": {"type": "item.completed", "item": {
                    "type": "command_execution", "exit_code": 1,
                    "command": "cat ~/.codex/plugins/cache/codex-science/codex-science/9.9.9/skills/failed/SKILL.md"}},
                    "t": 0.0}) + "\n")
            matching = _loaded_runtime(matching_events, branch_version)
            self.assertEqual([branch_version], matching["plugin_cache_versions"])
            self.assertEqual(["skills/codex-science/SKILL.md"], matching["skill_paths"])
            self.assertTrue(matching["runtime_under_test_matches_branch"])
            unknown = _loaded_runtime(matching_events, "unknown")
            self.assertFalse(unknown["runtime_under_test_matches_branch"])

    def test_process_group_kill_tolerates_disappeared_process(self) -> None:
        from codex_science.literature_evaluation_runner import _kill_process_group

        class ExitedProcess:
            pid = 12345

            @staticmethod
            def poll() -> int:
                return 0

        with patch("codex_science.literature_evaluation_runner.os.killpg",
                   side_effect=ProcessLookupError):
            _kill_process_group(ExitedProcess())  # type: ignore[arg-type]

    def test_symlinked_plan_and_task_directory_are_refused(self) -> None:
        from codex_science.literature_evaluation_runner import _write_plan, run_evaluation
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "out"
            out.mkdir()
            target = root / "victim"
            target.write_text("keep", encoding="utf-8")
            (out / "plan.json").symlink_to(target)
            with self.assertRaisesRegex(ValueError, "symlink"):
                _write_plan(out, {"schema": "test"}, execute=False)
            self.assertEqual("keep", target.read_text(encoding="utf-8"))
            (out / "plan.json").unlink()
            external = root / "external-task"
            external.mkdir()
            (out / "quick-doi").symlink_to(external, target_is_directory=True)
            with self.assertRaisesRegex(FileExistsError, "already exists"):
                run_evaluation(TASKS, out, selected=["quick-doi"], execute=True, codex_bin="unused")
            self.assertEqual([], list(external.iterdir()))

    def test_execute_oversized_line_is_truncated_and_counted(self) -> None:
        from codex_science.literature_evaluation_runner import _execute
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = root / "fake-codex"
            binary.write_text("#!/usr/bin/env python3\nimport sys\nsys.stdout.buffer.write(b'x'*(2*1024*1024)+b'\\n'+b'y'*(1024*1024)+b'\\n'+b'z'*(2*1024*1024))\nsys.stdout.flush()\n",
                              encoding="utf-8")
            binary.chmod(0o755)
            task_dir = root / "task"
            task_dir.mkdir()
            _, timed_out, launch_error, _, _ = _execute([str(binary)], root, task_dir, 5)
            self.assertFalse(timed_out)
            self.assertIsNone(launch_error)
            self.assertIn(b"output truncated", (task_dir / "events.jsonl").read_bytes())
            records = [json.loads(line) for line in (task_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual("x" * (1024 * 1024) + "\n[output truncated: line limit exceeded]", records[0]["event"])
            self.assertTrue(records[0]["line_truncated"])
            self.assertEqual("y" * (1024 * 1024), records[1]["event"])
            self.assertFalse(records[1]["line_truncated"])
            self.assertEqual("z" * (1024 * 1024) + "\n[output truncated: line limit exceeded]", records[2]["event"])
            self.assertTrue(records[2]["line_truncated"])
            from codex_science.literature_evaluation_runner import _count_truncated_lines
            self.assertEqual(2, _count_truncated_lines(task_dir / "events.jsonl"))

    def test_execute_end_marker_survives_full_line_queue(self) -> None:
        from codex_science import literature_evaluation_runner as runner

        class SlowQueue(runner.queue.Queue):
            def get(self, *args, **kwargs):
                item = super().get(*args, **kwargs)
                if item[1] is not None:
                    time.sleep(0.12)
                return item

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = root / "fake-codex"
            binary.write_text("#!/usr/bin/env python3\nfor index in range(17): print('{\"type\":\"item.completed\",\"id\":%d}' % index)\n",
                              encoding="utf-8")
            binary.chmod(0o755)
            task_dir = root / "task"
            task_dir.mkdir()
            deadline = 6
            with patch("codex_science.literature_evaluation_runner.queue.Queue", SlowQueue):
                exit_code, timed_out, _, wall_seconds, _ = runner._execute([str(binary)], root, task_dir, deadline)
            self.assertEqual(0, exit_code)
            self.assertFalse(timed_out)
            self.assertLess(wall_seconds, deadline / 2)

    def test_execute_total_output_cap_kills_child(self) -> None:
        from codex_science.literature_evaluation_runner import _execute
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = root / "fake-codex"
            binary.write_text("#!/usr/bin/env python3\nimport sys,time\nsys.stdout.write('{}\\n{}\\n'); sys.stdout.flush(); time.sleep(2)\n",
                              encoding="utf-8")
            binary.chmod(0o755)
            task_dir = root / "task"
            task_dir.mkdir()
            with patch("codex_science.literature_evaluation_runner._MAX_OUTPUT_BYTES", 3):
                _, timed_out, launch_error, _, _ = _execute([str(binary)], root, task_dir, 5)
            self.assertFalse(timed_out)
            self.assertEqual("output_cap", launch_error)
            records = [json.loads(line) for line in (task_dir / "events.jsonl").read_text().splitlines()]
            self.assertEqual([{}], [record["event"] for record in records])

    def test_execute_stderr_cap_is_reported_after_child_exit(self) -> None:
        from codex_science.literature_evaluation_runner import _execute
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = root / "fake-codex"
            binary.write_text("#!/usr/bin/env python3\nimport sys\nsys.stderr.write('x'*4096); sys.stderr.flush()\n",
                              encoding="utf-8")
            binary.chmod(0o755)
            task_dir = root / "task"
            task_dir.mkdir()
            with patch("codex_science.literature_evaluation_runner._MAX_OUTPUT_BYTES", 1024):
                _, timed_out, launch_error, _, _ = _execute([str(binary)], root, task_dir, 5)
            self.assertFalse(timed_out)
            self.assertEqual("output_cap", launch_error)

    def test_execute_keyboard_interrupt_kills_child_group(self) -> None:
        from codex_science.literature_evaluation_runner import _execute
        import io

        class InterruptQueue:
            def put(self, item, **kwargs):
                pass
            def get(self, timeout):
                raise KeyboardInterrupt()

        class LiveProcess:
            pid = 123
            stdout = io.BytesIO(b"event\n")
            stderr = io.BytesIO()
            returncode = None
            def poll(self): return self.returncode
            def wait(self, timeout):
                self.returncode = -9
                return self.returncode

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = root / "task"
            task_dir.mkdir()
            process = LiveProcess()
            with patch("codex_science.literature_evaluation_runner.subprocess.Popen", return_value=process), \
                 patch("codex_science.literature_evaluation_runner.queue.Queue", return_value=InterruptQueue()), \
                 patch("codex_science.literature_evaluation_runner._kill_process_group") as kill:
                with self.assertRaises(KeyboardInterrupt):
                    _execute(["fake"], root, task_dir, 5)
            kill.assert_called_once_with(process)

    def test_execute_timeout_with_unclosed_stdout_is_bounded(self) -> None:
        from codex_science.literature_evaluation_runner import _execute
        import io
        read_fd, write_fd = os.pipe()

        class PipeProcess:
            pid = 123
            def __init__(self):
                self.stdout = os.fdopen(read_fd, "rb", buffering=0)
                self.stderr = io.BytesIO()
                self.returncode = None
            def poll(self): return self.returncode
            def wait(self, timeout):
                self.returncode = -9
                return self.returncode

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = root / "task"
            task_dir.mkdir()
            process = PipeProcess()
            started = time.monotonic()
            try:
                with patch("codex_science.literature_evaluation_runner.subprocess.Popen", return_value=process), \
                     patch("codex_science.literature_evaluation_runner._kill_process_group"):
                    _, timed_out, _, _, _ = _execute(["fake"], root, task_dir, 0.01)
            finally:
                os.close(write_fd)
            self.assertTrue(timed_out)
            self.assertLess(time.monotonic() - started, 2)

    def test_frozen_criteria_pass_realistic_run_and_fail_broken_checkpoint(self) -> None:
        from codex_science.literature_evaluation_runner import evaluate_criteria
        task = next(task for task in json.loads(TASKS.read_text(encoding="utf-8"))["tasks"]
                    if task["id"] == "full-microbiome")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = self._fake_codex(root)
            home = self._codex_home(root)
            out = root / "out"
            result = self._run("--tasks", str(TASKS), "--out", str(out), "--task", task["id"], "--execute",
                               "--codex-bin", str(binary), "--codex-home", str(home),
                               extra_env={"FAKE_REALISTIC": "1"})
            self.assertEqual(0, result.returncode, result.stderr)
            project = out / task["id"] / "project"
            report = evaluate_criteria(task["spec"]["criteria"], project,
                                       (out / task["id"] / "last.md").read_text(encoding="utf-8"))
            self.assertTrue(all(item["passed"] for item in report), report)
            receipt = json.loads((out / task["id"] / "receipt.json").read_text(encoding="utf-8"))
            self.assertTrue(receipt["runtime_identities"])
            checkpoint = project / "artifacts/fixture-run/checkpoint.json"
            broken = json.loads(checkpoint.read_text(encoding="utf-8"))
            broken["state"] = "active"
            checkpoint.write_text(json.dumps(broken), encoding="utf-8")
            failed = evaluate_criteria(task["spec"]["criteria"], project,
                                       (out / task["id"] / "last.md").read_text(encoding="utf-8"))
            self.assertFalse(next(item["passed"] for item in failed if item["id"] == "complete-checkpoint"))

    def test_completion_report_receives_end_time_and_staleness(self) -> None:
        from codex_science.literature_evaluation_runner import _completion_report
        now = datetime.now(timezone.utc)
        fake = types.ModuleType("codex_science.completion_report")
        calls = {}

        def report(artifacts_root: Path, *, now: datetime, stale_after: timedelta) -> dict[str, object]:
            calls.update(root=artifacts_root, now=now, stale_after=stale_after)
            return {"schema": "completion-report-v1", "runs": []}

        fake.report_completion = report
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp) / "artifacts"
            artifacts.mkdir()
            with patch.dict(sys.modules, {"codex_science.completion_report": fake}):
                self.assertEqual({"schema": "completion-report-v1", "runs": []},
                                 _completion_report(artifacts, now=now))
            self.assertEqual(artifacts, calls["root"])
            self.assertEqual(now, calls["now"])
            self.assertEqual(timedelta(hours=24), calls["stale_after"])
            self.assertEqual({"status": "no_artifacts"},
                             _completion_report(Path(tmp) / "absent", now=now))

    def test_criterion_json_list_wildcard_and_regex_min_count(self) -> None:
        from codex_science.literature_evaluation_runner import evaluate_criteria
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            run = project / "artifacts/run-1"
            run.mkdir(parents=True)
            (run / "manifest.json").write_text(json.dumps({"artifacts": [
                {"kind": "review-receipt"}, {"kind": "evidence-graph"}]}), encoding="utf-8")
            (run / "report.txt").write_text("PMID:1 PMID:2", encoding="utf-8")
            criteria = [
                {"id": "review", "kind": "json_field", "path": "project/artifacts/*/manifest.json",
                 "arg": {"path": "artifacts.*.kind", "contains": "review-receipt"}},
                {"id": "references", "kind": "min_count", "path": "project/artifacts/*/*.txt",
                 "arg": {"regex": r"PMID:\d+", "minimum": 2}},
            ]
            self.assertEqual([True, True], [r["passed"] for r in evaluate_criteria(criteria, project)])

    def test_parse_exec_event_fixtures_and_unknown_types(self) -> None:
        from codex_science.literature_evaluation_runner import parse_exec_events
        completed = [
            '{"type":"thread.started","thread_id":"t-1"}',
            '{"type":"item.completed","item":{"type":"command_execution","status":"failed"}}',
            '{"type":"item.completed","item":{"type":"command_execution","exit_code":23}}',
            '{"type":"item.declined","item":{"type":"command_execution"}}',
            '{"type":"item.completed","item":{"type":"mcp_tool_call","tool":"europepmc","status":"completed"}}',
            '{"type":"item.completed","item":{"type":"future_item","status":"new"}}',
            '{"type":"future.event"}',
            '{"type":"turn.completed","usage":{"input_tokens":200,"output_tokens":70}}',
            '{"type":"turn.completed","usage":{"input_tokens":40,"cached_input_tokens":10,"output_tokens":12,"reasoning_tokens":3}}',
        ]
        metrics = parse_exec_events(completed, exit_code=0, wall_seconds=1.5)
        self.assertEqual("completed", metrics["terminal_stop_reason"])
        self.assertEqual("t-1", metrics["thread_id"])
        self.assertEqual({"declined": 1, "failed": 2}, metrics["item_counts_by_type_and_status"]["command_execution"])
        self.assertEqual({"completed": 1}, metrics["mcp_tool_call_counts_by_tool"]["europepmc"])
        self.assertEqual(10, metrics["usage"]["cached_input_tokens"])
        self.assertEqual(1, metrics["event_counts"]["future.event"])
        empty_final_message = ['{"type":"thread.started","thread_id":"t-empty"}',
                               '{"type":"turn.completed","usage":{"input_tokens":3,"output_tokens":0}}']
        self.assertEqual("completed", parse_exec_events(empty_final_message, exit_code=0)["terminal_stop_reason"])
        failed = parse_exec_events(['{"type":"turn.failed","error":{"message":"x"}}'], exit_code=0)
        self.assertEqual("failed", failed["terminal_stop_reason"])
        self.assertEqual("x", failed["error_message"])
        self.assertEqual("interrupted", parse_exec_events(['{"type":"thread.started"}'], exit_code=2)["terminal_stop_reason"])
        self.assertEqual("timeout", parse_exec_events([], timed_out=True)["terminal_stop_reason"])


if __name__ == "__main__":
    unittest.main()
