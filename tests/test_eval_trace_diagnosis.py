from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.eval_trace_diagnosis import diagnose_events, diagnose_task_dir  # noqa: E402

CLI = ROOT / "scripts" / "diagnose_eval_trace.py"
CACHE = "$HOME/.codex/plugins/cache/codex-science/codex-science/1.2.3"


def cmd(item_id, command, exit_code=0, output="", t=None, wrapped=True, event="item.completed"):
    item = {"id": item_id, "type": "command_execution", "command": command, "exit_code": exit_code,
            "aggregated_output": output}
    body = {"type": event, "item": item}
    return json.dumps({"t": t, "event": body} if wrapped else body)


def change(item_id, path, t=1.0):
    body = {"type": "item.completed", "item": {"id": item_id, "type": "file_change",
                                               "changes": [{"path": path, "kind": "update"}]}}
    return json.dumps({"t": t, "event": body})


TURN_DONE = json.dumps({"t": 99, "event": {"type": "turn.completed"}})


class DiagnoseTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def run_events(self, lines):
        path = self.tmp / "events.jsonl"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return diagnose_events(path)

    def test_failed_tool_use_split_and_benign_miss(self):
        result = self.run_events([
            cmd("a", f"python {CACHE}/scripts/build.py --x", 1, "boom", t=1),
            cmd("b", "rg needle docs", 1, "", t=2),
            cmd("c", "rg needle docs", 2, "stderr text", t=3),
            cmd("d", "false", 2, t=4),
            cmd("e", "true", 0, t=5)])
        failed = result["failed_tool_use"]
        self.assertEqual(failed["count"], 4)
        self.assertEqual(failed["plugin_script"]["count"], 1)
        self.assertEqual(failed["benign_search_miss"]["count"], 1)
        self.assertEqual(failed["other"]["count"], 2)  # rg exit 2 is not benign
        self.assertEqual(failed["benign_search_miss"]["examples"][0]["item_id"], "b")

    def test_started_and_completed_count_once(self):
        result = self.run_events([cmd("a", "false", None, event="item.started"), cmd("a", "false", 1)])
        self.assertEqual(result["command_count"], 1)
        self.assertEqual(result["failed_tool_use"]["count"], 1)

    def test_truncation_of_examples_and_commands(self):
        lines = [cmd(f"i{n}", "x" * 500 + str(n), 1) for n in range(8)]
        result = self.run_events(lines)
        section = result["failed_tool_use"]["other"]
        self.assertEqual(section["count"], 8)
        self.assertEqual(len(section["examples"]), 5)
        self.assertEqual(len(section["examples"][0]["command"]), 200)

    def test_repeated_exploration_threshold(self):
        lines = [cmd(f"r{n}", "ls   -la", t=n) for n in range(3)]
        lines += [cmd(f"s{n}", "pwd") for n in range(2)]
        lines += [cmd(f"f{n}", "sed -n '1,40p' src/a.py") for n in range(3)]
        lines += [cmd("g0", "cat notes.md"), cmd("g1", "head -n 5 notes.md")]
        result = self.run_events(lines)["repeated_exploration"]
        commands = {row["command"]: row["count"] for row in result["commands"]["examples"]}
        self.assertEqual(commands, {"ls -la": 3, "sed -n '1,40p' src/a.py": 3})
        self.assertEqual(result["file_reads"]["examples"], [{"path": "src/a.py", "count": 3}])

    def test_plugin_source_reads_exclude_help_and_markdown(self):
        result = self.run_events([
            cmd("a", f"sed -n '1,80p' {CACHE}/scripts/build.py"),
            cmd("b", f"cat {CACHE}/src/codex_science/mod.py"),
            cmd("c", f"python {CACHE}/scripts/build.py --help"),
            cmd("d", f"cat {CACHE}/skills/x/SKILL.md"),
            cmd("e", f"bash -lc 'cat {CACHE}/references/a.md'"),
            cmd("f", "cat src/local.py")])
        self.assertEqual([r["item_id"] for r in result["plugin_source_reads"]["examples"]], ["a", "b"])

    def test_manifest_hand_edits(self):
        result = self.run_events([
            cmd("a", "sed -i 's/x/y/' run/manifest.json"),
            cmd("b", "echo {} > run/manifest.json"),
            cmd("c", "python -c \"open('run/manifest.json','w').write('{}')\""),
            cmd("d", "cat run/manifest.json"),
            cmd("e", "cat run/manifest.json > copy.txt"),
            cmd("f", f"python {CACHE}/scripts/package_run.py run/manifest.json > out.txt"),
            change("g", "run/manifest.json"),
            change("h", "run/other.json")])
        edits = result["manifest_hand_edits"]
        self.assertEqual(sorted(r["item_id"] for r in edits["examples"]), ["a", "b", "c", "g"])
        self.assertEqual(edits["count"], 4)

    def test_bare_and_wrapped_lines_and_malformed_tolerated(self):
        bad_event_type = json.dumps({"type": []})
        bad_item_type = json.dumps({"type": "item.completed", "item": {"type": {}}})
        huge_timestamp = json.dumps({"t": 10 ** 400, "event": json.loads(cmd("huge", "false", 1))["event"]})
        lines = [cmd("a", "false", 1, wrapped=False), "not json", "[1,2]", "",
                 bad_event_type, bad_item_type, huge_timestamp, cmd("b", "false", 1, t=2)]
        result = self.run_events(lines)
        self.assertEqual(result["failed_tool_use"]["count"], 3)
        self.assertEqual(result["malformed_lines"], 6)

    def test_oversized_line_is_malformed_not_fatal(self):
        path = self.tmp / "events.jsonl"
        path.write_bytes(b"x" * ((1 << 20) + 10) + b"\n" + cmd("a", "false", 1).encode() + b"\n")
        result = diagnose_events(path)
        self.assertEqual((result["malformed_lines"], result["failed_tool_use"]["count"]), (1, 1))

    def test_phase_seconds_sorted_by_first_use(self):
        result = self.run_events([
            cmd("a", f"python {CACHE}/scripts/zeta.py", t=5), cmd("b", f"python {CACHE}/scripts/alpha.py", t=9),
            cmd("c", f"python {CACHE}/scripts/zeta.py", t=20), cmd("d", "ls", t=1)])
        self.assertEqual(result["phase_seconds"], [
            {"script": "zeta.py", "first_t": 5.0, "last_t": 20.0},
            {"script": "alpha.py", "first_t": 9.0, "last_t": 9.0}])

    def task_dir(self, receipt, last, artifacts=(), manifest=None):
        task = Path(tempfile.mkdtemp(dir=self.tmp))
        (task / "project" / "artifacts").mkdir(parents=True)
        (task / "events.jsonl").write_text("\n".join([cmd("a", "ls", t=1), TURN_DONE]) + "\n")
        if receipt is not None:
            (task / "receipt.json").write_text(json.dumps(receipt))
        if last is not None:
            (task / "last.md").write_text(last if isinstance(last, str) else json.dumps(last))
        for name in artifacts:
            (task / "project" / name).write_text("x")
        if manifest is not None:
            (task / "project" / "artifacts" / "manifest.json").write_text(json.dumps(manifest))
        return task

    def test_lost_artifacts(self):
        last = {"status": "completed", "deliverables": ["report.md", "gone.md", "../escape.md"]}
        task = self.task_dir({}, last, artifacts=["report.md"],
                             manifest={"artifacts": [{"path": "present.json"}, {"path": "absent.json"}]})
        (task / "project" / "artifacts" / "present.json").write_text("{}")
        lost = diagnose_task_dir(task)["lost_artifacts"]
        self.assertTrue(lost["checked"])
        self.assertEqual({(r["path"], r["reason"]) for r in lost["examples"]},
                         {("gone.md", "missing"), ("../escape.md", "outside_project"), ("absent.json", "missing")})

    def test_lost_artifacts_negative_and_unparseable_last(self):
        task = self.task_dir({}, "not json at all", artifacts=["report.md"])
        self.assertEqual(diagnose_task_dir(task)["lost_artifacts"]["count"], 0)
        self.assertFalse(self.run_events([TURN_DONE])["lost_artifacts"]["checked"])

    def test_premature_closure_reasons(self):
        complete = {"completion_report": {"runs": [{"run_id": "r1", "outcome": "completed"}]}}
        ok = diagnose_task_dir(self.task_dir(complete, {"status": "completed", "deliverables": []}))
        self.assertFalse(ok["premature_closure"]["value"])
        bad_report = {"completion_report": {"runs": [{"run_id": "r1", "outcome": "active"}]}}
        bad = diagnose_task_dir(self.task_dir(bad_report, {"status": "partial", "deliverables": []}))
        reasons = bad["premature_closure"]["reasons"]
        self.assertTrue(bad["premature_closure"]["value"])
        self.assertEqual(len(reasons), 2)
        self.assertIn("outcome active", reasons[0])
        self.assertIn("'partial'", reasons[1])
        absent = {"completion_report": {"status": "no_artifacts"}}
        empty = diagnose_task_dir(self.task_dir(absent, None))
        self.assertEqual(empty["premature_closure"]["reasons"], [])
        self.assertTrue(empty["premature_closure"]["no_artifacts"])
        self.assertFalse(empty["premature_closure"]["value"])
        unavailable = diagnose_task_dir(self.task_dir({"completion_report": {"status": "unavailable"}}, None))
        self.assertEqual(unavailable["premature_closure"]["reasons"], ["completion_report status unavailable"])

    def test_no_artifacts_quick_answer_plain_text_is_not_premature(self):
        task = self.task_dir({"completion_report": {"status": "no_artifacts"}}, "The answer is 42.")
        closure = diagnose_task_dir(task)["premature_closure"]
        self.assertEqual((closure["value"], closure["no_artifacts"]), (False, True))
        for status, flagged in (("blocked", True), ("failed", True), ("partial", True), ("quick_answer", False)):
            task = self.task_dir({"completion_report": {"status": "no_artifacts"}},
                                 {"status": status, "deliverables": []})
            self.assertEqual(diagnose_task_dir(task)["premature_closure"]["value"], flagged, status)

    def test_no_closure_flag_without_completed_turn(self):
        failed = json.dumps({"t": 2, "event": {"type": "turn.failed"}})
        result = self.run_events([cmd("a", "ls"), failed])
        self.assertEqual(result["premature_closure"], {"value": False, "turn_completed": False, "no_artifacts": False,
                                                       "reasons": [], "reason_count": 0})

    def test_trace_content_is_not_executed(self):
        marker = self.tmp / "pwned"
        result = self.run_events([cmd("a", f"touch {marker}", 1)])
        self.assertEqual(result["failed_tool_use"]["count"], 1)
        self.assertFalse(marker.exists())

    def test_cli_help_events_and_output(self):
        helped = subprocess.run([sys.executable, str(CLI), "--help"], capture_output=True, text=True, check=True)
        for text in ("--events", "--output", "benign_search_miss", "pattern matches"):
            self.assertIn(text, helped.stdout)
        events = self.tmp / "e.jsonl"
        events.write_text(cmd("a", "false", 1) + "\n")
        done = subprocess.run([sys.executable, str(CLI), "--events", str(events)],
                              capture_output=True, text=True, check=True)
        payload = json.loads(done.stdout)
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["failed_tool_use"]["count"], 1)
        self.assertIn("evidence_boundary", payload)
        out = self.tmp / "out.json"
        subprocess.run([sys.executable, str(CLI), "--events", str(events), "--output", str(out)], check=True)
        self.assertEqual(json.loads(out.read_text()), payload)

    def test_cli_input_errors(self):
        both = subprocess.run([sys.executable, str(CLI)], capture_output=True, text=True)
        self.assertEqual(both.returncode, 2)
        missing = subprocess.run([sys.executable, str(CLI), "--events", str(self.tmp / "none")],
                                 capture_output=True, text=True)
        self.assertEqual(missing.returncode, 2)
        self.assertIn("diagnose_eval_trace", missing.stderr)

    def test_cli_task_dir(self):
        task = self.task_dir({"completion_report": {"runs": []}}, {"status": "completed", "deliverables": []})
        done = subprocess.run([sys.executable, str(CLI), str(task)], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(done.stdout)["premature_closure"]["reasons"], [])
        self.assertTrue(json.loads(done.stdout)["premature_closure"]["no_artifacts"])

    def test_benign_search_miss_in_wrapped_script_with_nonempty_output(self):
        wrapped = '/bin/bash -lc "pwd; rg --files -g \'AGENTS.md\' -g \'*.md\' ."'
        result = self.run_events([
            cmd("a", wrapped, 1, "/work/project\n"),
            cmd("b", "/bin/bash -lc 'cd x && grep -n foo y.txt 2>&1'", 1, "x"),
            cmd("c", wrapped, 2, "/work/project\nrg: bad glob"),
            cmd("d", "/bin/bash -lc 'rg foo . | head -n 3; false'", 1, ""),
            cmd("e", "/bin/bash -lc 'rg foo .\nls nowhere'", 1, "")])
        failed = result["failed_tool_use"]
        self.assertEqual(sorted(r["item_id"] for r in failed["benign_search_miss"]["examples"]), ["a", "b"])
        self.assertEqual(sorted(r["item_id"] for r in failed["other"]["examples"]), ["c", "d", "e"])

    def test_plugin_source_reads_ignore_heredoc_writes_and_executions(self):
        runtime = f"{CACHE}/scripts/python_runtime.sh"
        write = (f"cat > artifacts/r/finalize_evidence.py <<'PY'\nimport subprocess\n"
                 f"subprocess.run(['{runtime}', 'x'])\nPY\npython artifacts/r/finalize_evidence.py")
        result = self.run_events([
            cmd("a", write), cmd("b", f"{runtime} {CACHE}/scripts/build.py --out x"),
            cmd("c", f"bash {runtime} --version"),
            cmd("d", f"cat {runtime}"),
            cmd("e", f"/bin/bash -lc \"nl -ba {CACHE}/src/codex_science/mod.py | sed -n '1,20p'\""),
            cmd("f", f"rg -n pattern {CACHE}/scripts"),
            cmd("g", f"rg -n pattern {CACHE}/scripts/build.py {CACHE}/src")])
        reads = [r["item_id"] for r in result["plugin_source_reads"]["examples"]]
        self.assertEqual(reads, ["d", "e", "g"])

    def test_plugin_paths_are_normalized_in_every_example(self):
        script = f"{CACHE}/scripts/package_run.py"
        result = self.run_events([
            cmd("a", f"python {script} refresh --run r1 " + "x" * 300, 1, "boom", t=2),
            cmd("b", f"cat {script}", t=3)])
        example = result["failed_tool_use"]["plugin_script"]["examples"][0]
        self.assertTrue(example["command"].startswith("python <plugin>/scripts/package_run.py refresh"))
        self.assertEqual(example["script"], "package_run.py")
        self.assertNotIn("codex-science/codex-science", json.dumps(result))
        self.assertNotIn(".codex", json.dumps(result))
        self.assertEqual(result["plugin_source_reads"]["examples"][0]["path"], "<plugin>/scripts/package_run.py")
        self.assertEqual(result["phase_seconds"][0]["script"], "package_run.py")

    def test_repeated_commands_group_across_plugin_versions(self):
        other = CACHE.replace("1.2.3", "9.9.9")
        result = self.run_events([cmd("a", f"python {CACHE}/scripts/x.py"), cmd("b", f"python {other}/scripts/x.py"),
                                  cmd("c", f"python {CACHE}/scripts/x.py")])
        self.assertEqual(result["repeated_exploration"]["commands"]["examples"],
                         [{"command": "python <plugin>/scripts/x.py", "count": 3}])


if __name__ == "__main__":
    unittest.main()
