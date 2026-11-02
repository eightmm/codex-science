from __future__ import annotations

import itertools
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science import eval_trace_diagnosis  # noqa: E402
from codex_science.eval_trace_diagnosis import (  # noqa: E402
    _strip_heredocs, collect_items, diagnose_events, diagnose_task_dir)

CLI = ROOT / "scripts" / "diagnose_eval_trace.py"
CACHE = "$HOME/.codex/plugins/cache/codex-science/codex-science/1.2.3"


def cmd(item_id, command, exit_code=0, output="", t=None, wrapped=True, event="item.completed", status=None):
    item = {"id": item_id, "type": "command_execution", "command": command, "exit_code": exit_code,
            "aggregated_output": output}
    if status is not None:
        item["status"] = status
    body = {"type": event, "item": item}
    return json.dumps({"t": t, "event": body} if wrapped else body)


def change(item_id, path, t=1.0):
    body = {"type": "item.completed", "item": {"id": item_id, "type": "file_change",
                                               "changes": [{"path": path, "kind": "update"}]}}
    return json.dumps({"t": t, "event": body})


def wrap(script):
    """A command as Codex records it: `/bin/bash -lc "<script>"`."""
    for char in '\\"$`':
        script = script.replace(char, "\\" + char)
    return f'/bin/bash -lc "{script}"'


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

    def test_explicit_failed_status_is_counted_without_an_exit_code(self):
        for command, category, output in (("sleep 60", "other", "Command timed out"),
                                          ("false", "other", ""), ("rg needle .", "other", "Command timed out"),
                                          (f"python {CACHE}/scripts/build.py", "plugin_script", "Command timed out")):
            for exit_code in (None, 0, "missing"):
                for wrapped in (False, True):
                    with self.subTest(command=command, exit_code=exit_code, wrapped=wrapped):
                        completed = json.loads(cmd("a", command, None if exit_code == "missing" else exit_code,
                                                   output, wrapped=wrapped, status="failed"))
                        item = completed["event"]["item"] if wrapped else completed["item"]
                        if exit_code == "missing":
                            del item["exit_code"]
                        result = self.run_events([
                            cmd("a", command, None, event="item.started", status="in_progress"),
                            json.dumps(completed)])
                        failed = result["failed_tool_use"]
                        self.assertEqual(result["command_count"], 1)
                        self.assertEqual(failed["count"], 1)
                        self.assertEqual(failed[category]["count"], 1)
                        self.assertEqual(failed[category]["examples"][0]["exit_code"], item.get("exit_code"))
                        self.assertEqual(set(failed), {"count", "plugin_script", "benign_search_miss", "other"})
        for status in (None, "", "completed", "in_progress", [], False, 0):
            with self.subTest(status=status):
                result = self.run_events([cmd("a", "rg needle .", None, status=status)])
                self.assertEqual(result["failed_tool_use"]["count"], 0)
                self.assertEqual(result["malformed_lines"], int(isinstance(status, (list, bool, int))))
        result = self.run_events([cmd("a", "", None, status="failed")])
        self.assertEqual(result["command_count"], 0)

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

    def test_manifest_writes_past_the_word_split_cap_are_detected(self):
        filler = "x = 1\n" * (eval_trace_diagnosis._MAX_SCAN_CHARS // 6)
        writes = ["open('run/manifest.json', 'w').write('{}')", "Path('run/manifest.json').write_text('{}')",
                  "sed -i 's/a/b/' run/manifest.json", "echo {} | tee run/manifest.json", "echo {} > run/manifest.json"]
        lines = [cmd(f"w{n}", wrap(f"python3 - <<'PY'\n{filler}PY\n{write}" if n > 1
                                    else f"python3 - <<'PY'\n{filler}{write}\nPY"))
                 for n, write in enumerate(writes)]
        lines.append(cmd("r", wrap(f"python3 - <<'PY'\n{filler}print(open('run/manifest.json').read())\nPY")))
        result = self.run_events(lines)
        self.assertGreater(len(json.loads(lines[0])["event"]["item"]["command"]), eval_trace_diagnosis._MAX_SCAN_CHARS)
        self.assertEqual(sorted(r["item_id"] for r in result["manifest_hand_edits"]["examples"]),
                         ["w0", "w1", "w2", "w3", "w4"])

    def test_manifest_write_matching_equals_one_search_per_pattern(self):
        patterns = [re.compile(p) for p in (
            r"\bsed\b[^|;&\n]*\s-[A-Za-z]*i[^|;&\n]*manifest\.json",
            r">>?\s*['\"]?[^\s'\"<>|;&]*manifest\.json",
            r"\btee\b[^|;&\n]*manifest\.json",
            r"open\([^)\n]*manifest\.json[^)\n]*['\"][wax]\+?b?['\"]",
            r"manifest\.json['\"]?\s*\)\s*\.write_(?:text|bytes)\(")]
        atoms = ["sed", "tee", " ", "\n", "-i", "-n", ";", "|", ")", "open(", "manifest.json", "'w'", ">",
                 ".write_text("]
        for size in range(1, 5):
            for parts in itertools.product(atoms, repeat=size):
                text = "".join(parts)
                self.assertEqual(eval_trace_diagnosis._writes_manifest(text),
                                 any(p.search(text) for p in patterns), repr(text))

    def test_bare_and_wrapped_lines_and_malformed_tolerated(self):
        bad_event_type = json.dumps({"type": []})
        bad_item_type = json.dumps({"type": "item.completed", "item": {"type": {}}})
        huge_timestamp = json.dumps({"t": 10 ** 400, "event": json.loads(cmd("huge", "false", 1))["event"]})
        huge_integer = '{"t":' + "9" * 5000 + ',"event":{"type":"turn.completed"}}'
        lines = [cmd("a", "false", 1, wrapped=False), "not json", "[1,2]", "",
                 bad_event_type, bad_item_type, huge_timestamp, huge_integer, cmd("b", "false", 1, t=2)]
        result = self.run_events(lines)
        self.assertEqual(result["failed_tool_use"]["count"], 3)
        self.assertEqual(result["malformed_lines"], 7)

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
        malformed_number = '{"status":"completed","deliverables":[' + "9" * 5000 + ']}'
        task = self.task_dir({}, malformed_number, artifacts=["report.md"])
        self.assertEqual(diagnose_task_dir(task)["lost_artifacts"]["count"], 0)
        self.assertFalse(self.run_events([TURN_DONE])["lost_artifacts"]["checked"])

    def test_lost_artifacts_follow_symlink_targets_within_project(self):
        names = ["report.md", "escaped.md", "present.md", "loop.md", "via-dir/report.md"]
        task = self.task_dir({}, {"status": "completed", "deliverables": names}, artifacts=["actual.md"],
                             manifest={"artifacts": [{"path": "broken.md"}]})
        project = task / "project"
        (project / "report.md").symlink_to("deleted.md")
        (task / "outside.md").write_text("outside")
        (project / "escaped.md").symlink_to("../outside.md")
        (project / "present.md").symlink_to("actual.md")
        (project / "loop.md").symlink_to("loop.md")
        (project / "via-dir").symlink_to("..", target_is_directory=True)
        (project / "artifacts/broken.md").symlink_to("deleted.md")
        lost = diagnose_task_dir(task)["lost_artifacts"]
        self.assertTrue(lost["checked"])
        self.assertEqual(5, lost["count"])
        self.assertEqual({("report.md", "missing"), ("escaped.md", "outside_project"),
                          ("loop.md", "missing"), ("via-dir/report.md", "outside_project"),
                          ("broken.md", "missing")},
                         {(row["path"], row["reason"]) for row in lost["examples"]})
        empty = self.task_dir({}, {"deliverables": ["", 0, None]})
        self.assertEqual([{"path": "", "source": "completion_record", "reason": "outside_project"}],
                         diagnose_task_dir(empty)["lost_artifacts"]["examples"])
        for length in (255, 256):
            name = "x" * length
            task = self.task_dir({}, {"deliverables": [name]}, artifacts=[name] if length == 255 else [])
            with self.subTest(component_bytes=length):
                lost = diagnose_task_dir(task)["lost_artifacts"]
                self.assertEqual(int(length > 255), lost["count"])
                if length > 255:
                    self.assertEqual("missing", lost["examples"][0]["reason"])
                result = subprocess.run([sys.executable, str(CLI), str(task)], capture_output=True, text=True)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual(lost, json.loads(result.stdout)["lost_artifacts"])
        for escaped, present in ((True, False), (True, True), (False, True)):
            with self.subTest(symlink_escape=escaped, target_present=present):
                task = self.task_dir({}, {"deliverables": ["link/../report.md"]}, artifacts=["report.md"])
                project = task / "project"
                destination = task / "outside" if escaped else project / "inside"
                (destination / "nested").mkdir(parents=True)
                (project / "link").symlink_to("../outside/nested" if escaped else "inside/nested",
                                             target_is_directory=True)
                if present:
                    (destination / "report.md").write_text("actual target")
                    self.assertEqual("actual target", (project / "link/../report.md").read_text())
                else:
                    self.assertFalse((project / "link/../report.md").exists())
                lost = diagnose_task_dir(task)["lost_artifacts"]
                expected = [{"path": "link/../report.md", "source": "completion_record",
                             "reason": "outside_project"}] if escaped else []
                self.assertEqual({"checked": True, "count": int(escaped), "examples": expected}, lost)
        task = self.task_dir({}, {"deliverables": ["absent/../report.md"]}, artifacts=["report.md"])
        self.assertEqual([{"path": "absent/../report.md", "source": "completion_record", "reason": "missing"}],
                         diagnose_task_dir(task)["lost_artifacts"]["examples"])
        task = self.task_dir({}, {"status": "completed", "deliverables": ["\ud800"]})
        lost = diagnose_task_dir(task)["lost_artifacts"]
        self.assertEqual({"checked": True, "count": 1, "examples": [
            {"path": "\ud800", "source": "completion_record", "reason": "missing"}]}, lost)
        result = subprocess.run([sys.executable, str(CLI), str(task)], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(lost, json.loads(result.stdout)["lost_artifacts"])

    def test_premature_closure_requires_named_run_in_completion_report(self):
        complete = {"completion_report": {"runs": [{"run_id": "actual", "outcome": "completed"}]}}
        for run_id, flagged in (("missing", True), ("actual", False), (None, False), ("", True), (0, True), ([], True)):
            with self.subTest(run_id=run_id):
                record = {"status": "completed", "run_id": run_id, "deliverables": []}
                closure = diagnose_task_dir(self.task_dir(complete, record))["premature_closure"]
                self.assertEqual(flagged, closure["value"])
                self.assertEqual(int(flagged), closure["reason_count"])
                if flagged:
                    self.assertIn("absent from completion_report", closure["reasons"][0])
        for report in ({"status": "no_artifacts"}, {"runs": []}):
            closure = diagnose_task_dir(self.task_dir({"completion_report": report},
                                       {"status": "completed", "run_id": "missing"}))["premature_closure"]
            self.assertEqual((False, True, []), (closure["value"], closure["no_artifacts"], closure["reasons"]))

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
            cmd("g", f"rg -n pattern {CACHE}/scripts/build.py {CACHE}/src"),
            cmd("h", wrap(f"cat > f.py <<'PY'\nprint(open('{CACHE}/scripts/build.py').read())\nPY\npython f.py"), 1),
            cmd("i", wrap(f"cat > f.sh <<'SH'\ncat {runtime}\nSH\nsh f.sh"))])
        reads = [r["item_id"] for r in result["plugin_source_reads"]["examples"]]
        self.assertEqual(reads, ["d", "e", "g"])
        self.assertEqual([r["item_id"] for r in result["failed_tool_use"]["other"]["examples"]], ["h"])

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

    def cli(self, *args):
        return subprocess.run([sys.executable, str(CLI), *map(str, args)], capture_output=True, text=True, timeout=60)

    def test_cli_refuses_output_that_resolves_to_an_input(self):
        events = self.tmp / "ev.jsonl"
        events.write_text(cmd("a", "false", 1) + "\n")
        before = events.read_bytes()
        link = self.tmp / "link.json"
        link.symlink_to(events)
        hard = self.tmp / "hard.json"
        os.link(events, hard)
        for target in (events, link, hard):
            done = self.cli("--events", events, "--output", target)
            self.assertEqual(done.returncode, 2, target)
            self.assertIn("diagnose_eval_trace:", done.stderr)
            self.assertEqual(events.read_bytes(), before)
        task = self.task_dir({"completion_report": {"runs": []}}, {"status": "completed"}, manifest={"artifacts": []})
        for name in ("events.jsonl", "receipt.json", "last.md", "project/artifacts/manifest.json"):
            kept = (task / name).read_bytes()
            done = self.cli(task, "--output", task / name)
            self.assertEqual(done.returncode, 2, name)
            self.assertEqual((task / name).read_bytes(), kept)

    def test_cli_output_write_errors_are_labelled(self):
        events = self.tmp / "ev.jsonl"
        events.write_text(cmd("a", "false", 1) + "\n")
        done = self.cli("--events", events, "--output", self.tmp / "nodir" / "x.json")
        self.assertEqual(done.returncode, 2)
        self.assertIn("diagnose_eval_trace:", done.stderr)
        self.assertNotIn("Traceback", done.stderr)
        done = self.cli("--events", events, "--output", self.tmp)  # a directory cannot be replaced
        self.assertEqual(done.returncode, 2)
        self.assertNotIn("Traceback", done.stderr)
        # the temporary file is created next to the output, here in the parent of self.tmp
        self.assertEqual([p.name for p in self.tmp.parent.iterdir() if p.name.startswith(f".{self.tmp.name}.")], [])

    def test_events_must_be_a_regular_file_within_the_byte_cap(self):
        fifo = self.tmp / "fifo"
        os.mkfifo(fifo)
        for target in (fifo, self.tmp):
            with self.assertRaises(OSError):
                diagnose_events(target)
        done = self.cli("--events", fifo)
        self.assertEqual(done.returncode, 2)
        events = self.tmp / "ev.jsonl"
        events.write_bytes((cmd("a", "false", 1) + "\n").encode())
        size = events.stat().st_size
        original = eval_trace_diagnosis._MAX_FILE_BYTES
        self.addCleanup(setattr, eval_trace_diagnosis, "_MAX_FILE_BYTES", original)
        eval_trace_diagnosis._MAX_FILE_BYTES = size
        self.assertEqual(diagnose_events(events)["command_count"], 1)  # equal to the cap is allowed
        eval_trace_diagnosis._MAX_FILE_BYTES = size - 1
        with self.assertRaises(OSError):
            diagnose_events(events)
        events.write_bytes(b"")
        eval_trace_diagnosis._MAX_FILE_BYTES = 0
        self.assertEqual(diagnose_events(events)["command_count"], 0)

    def test_long_commands_are_scanned_in_bounded_time(self):
        size = 200_000
        commands = ["a" * size, "$" * size, "sed " * (size // 4), "open(" * (size // 5), "> " * (size // 2),
                    "/" * size, "x/plugins/cache/" * (size // 16), "a=" * (size // 2),
                    "sed " * (size // 4) + "manifest.json", "sed manifest.json" + " -i" * (size // 3),
                    "tee " * (size // 4) + "manifest.json", "open(" + "manifest.json" * (size // 13),
                    "cat <<A\n" * (size // 8), "<<'" * (size // 3), 'bash -c "' * (size // 9),
                    wrap("x <<'P'\n" * (size // 8))]
        start = time.monotonic()
        result = self.run_events([cmd(f"i{n}", text, 1) for n, text in enumerate(commands)])
        self.assertLess(time.monotonic() - start, 30)
        self.assertEqual(result["command_count"], len(commands))
        shared = "echo " + "x" * 9000
        result = self.run_events([cmd(f"r{n}", shared + tail, 0) for n, tail in enumerate("ABC")])
        self.assertEqual(result["repeated_exploration"]["commands"]["count"], 0)
        result = self.run_events([cmd(f"r{n}", shared + "A", 0) for n in range(3)])
        self.assertEqual(result["repeated_exploration"]["commands"]["count"], 1)

    def test_heredoc_lookalikes_do_not_hide_later_lines(self):
        for first in ('grep x <<< "$v"', 'echo "a << b"', "echo 'a << b'", "echo $((1 << 2))", "echo $(( x << y ))",
                      "cat <<EOF # unterminated"):
            text = f"{first}\npython scripts/b.py"
            self.assertEqual(_strip_heredocs(text), text, first)
            result = self.run_events([cmd("a", text, 1)])
            self.assertEqual(result["failed_tool_use"]["plugin_script"]["examples"][0]["script"], "b.py", first)
        self.assertEqual(_strip_heredocs("cat <<EOF\nscripts/x.py\nEOF\nls"), "cat <<EOF\nls")
        self.assertEqual(_strip_heredocs("x=$(cat <<'E'\nbody\nE\n)\nls"), "x=$(cat <<'E'\n)\nls")
        self.assertEqual(_strip_heredocs(""), "")
        quoted = 'echo "cat <<EOF\nscripts/x.py\nEOF"\nls'  # a quoted argument, not shell code
        self.assertEqual(_strip_heredocs(quoted), quoted)
        for first in ('grep x <<< "$v"', 'echo "a << b"', "echo 'a << b'", "echo $((1 << 2))",
                      "cat <<EOF # unterminated"):
            text = wrap(f"{first}\npython scripts/b.py")
            self.assertEqual(_strip_heredocs(text), text, first)
        self.assertEqual(_strip_heredocs(wrap("cat <<EOF\nscripts/x.py\nEOF\nls")), wrap("cat <<EOF\nls"))

    def test_heredocs_inside_a_shell_c_argument_are_dropped(self):
        # the terminator is usually glued to the closing quote; the quote stays
        self.assertEqual(_strip_heredocs(wrap("python3 - <<'PY'\nopen('scripts/x.py')\nPY")), wrap("python3 - <<'PY'"))
        self.assertEqual(_strip_heredocs("sh -c 'cat <<E\nscripts/x.py\nE'"), "sh -c 'cat <<E'")
        joined = "/bin/bash -lc 'python3 - <<'\"'\"'PY'\"'\"'\nscripts/x.py\nPY\nls'"  # '...'"'"'...' quoting
        self.assertEqual(_strip_heredocs(joined), "/bin/bash -lc 'python3 - <<'\"'\"'PY'\"'\"'\nls'")
        spanning = "/bin/bash -lc \"cat <<'EOF'\nscripts/x.py\"'\nEOF\nls'"  # the body crosses a quote change
        self.assertEqual(shlex.split(_strip_heredocs(spanning)), ["/bin/bash", "-lc", "cat <<'EOF'\nls"])
        text = wrap("python3 - <<'PY'\nimport x\nopen('/p/scripts/foo.py').read()\nPY\ncat /a/b.txt")
        self.assertEqual(_strip_heredocs(text), wrap("python3 - <<'PY'\ncat /a/b.txt"))
        result = self.run_events([cmd(f"c{n}", text, 1) for n in range(3)])
        self.assertEqual(result["failed_tool_use"]["other"]["count"], 3)
        self.assertEqual(result["repeated_exploration"]["file_reads"]["examples"], [{"path": "/a/b.txt", "count": 3}])

    def test_word_split_cap_keeps_a_cut_wrapped_word(self):
        cap = eval_trace_diagnosis._MAX_SCAN_CHARS
        head, tail = "/bin/bash -lc \"cd x; rg foo . -g '", "'\""
        for extra in (0, 1, 2):  # equal to the cap, then cut inside the outer and the inner quote
            text = head + "a" * (cap - len(head) - len(tail) + extra) + tail
            self.assertEqual(len(text), cap + extra)
            failed = self.run_events([cmd("a", text, 1)])["failed_tool_use"]
            self.assertEqual(failed["benign_search_miss"]["count"], 1, extra)
        failed = self.run_events([cmd("a", '/bin/bash -lc "rg foo .', 1)])["failed_tool_use"]  # malformed, not cut
        self.assertEqual(failed["other"]["count"], 1)

    def test_output_is_dropped_and_ids_and_phases_are_bounded(self):
        parsed = collect_items([cmd("a", "ls", output="x" * 1000).encode()])
        self.assertNotIn("output", parsed["items"][0])
        result = self.run_events([cmd("i" * 500, "false", 1), change("c" * 500, "p/manifest.json")])
        self.assertEqual(len(result["failed_tool_use"]["other"]["examples"][0]["item_id"]), 200)
        self.assertEqual(len(result["manifest_hand_edits"]["examples"][0]["item_id"]), 200)
        result = self.run_events([cmd(f"i{n}", f"python scripts/s{n}.py", t=n) for n in range(12)])
        self.assertEqual([row["script"] for row in result["phase_seconds"]], [f"s{n}.py" for n in range(5)])

    def test_item_identity_is_typed_and_idless_pairs_merge_only_when_adjacent(self):
        def count(*events):
            return len(collect_items([json.dumps(e) for e in events])["items"])

        def item(event, item_id=None, kind="command_execution", command="false"):
            body = {"type": kind, "command": command, "exit_code": 1}
            if item_id is not None:
                body["id"] = item_id
            return {"type": event, "item": body}

        started, done = "item.started", "item.completed"
        self.assertEqual(count(item(done, 1), item(done, "1")), 2)
        self.assertEqual(count(item(done, "a"), item(done, "a", kind="file_change")), 2)
        self.assertEqual(count(item(started, "a"), item(done, "a")), 1)
        self.assertEqual(count(item(started), item(done)), 1)
        self.assertEqual(count(item(started), item(done, command="true")), 2)
        self.assertEqual(count(item(started), {"type": "turn.started"}, item(done)), 2)
        self.assertEqual(count(item(started), item(started), item(done)), 2)
        self.assertEqual(count(item(done), item(done)), 2)
        result = self.run_events([cmd(None, "false", None, event="item.started"), cmd(None, "false", 1)])
        self.assertEqual((result["command_count"], result["failed_tool_use"]["count"]), (1, 1))


if __name__ == "__main__":
    unittest.main()
