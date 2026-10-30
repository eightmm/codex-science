from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/plan_matched_baseline.py"
TASKS = ROOT / "benchmarks/literature-review/tasks.json"


class MatchedBaselineTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("matched_baseline", SCRIPT)
        self.planner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.planner)

    def invoke(self, out, *extra):
        arguments = ["--tasks", str(TASKS), "--out", str(out), "--model", "fixed-model-v1", *extra]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                return self.planner.main(arguments)
            except SystemExit as error:
                return error.code

    def read_plan(self, out):
        return json.loads((out / "plan.json").read_text())

    def test_default_grid_budget_shared_inputs_and_interleaving(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary) / "plan"
            self.assertEqual(0, self.invoke(out))
            plan = self.read_plan(out)
            schedule = plan["schedule"]
            self.assertEqual(54, len(schedule))
            self.assertEqual(54, len({r["run_id"] for r in schedule}))
            self.assertEqual(set(range(1, 55)), {r["position"] for r in schedule})
            self.assertEqual(97200, plan["budget"]["worst_case_wall_seconds"])
            self.assertEqual(194400, plan["budget"]["worst_case_with_reruns_seconds"])
            self.assertEqual({1800}, {r["timeout_seconds"] for r in schedule})
            self.assertEqual({"fixed-model-v1"}, {r["model"] for r in schedule})
            tasks = json.loads(TASKS.read_text())
            expected = {(t["id"], t["digest"]) for t in tasks["tasks"]}
            for condition in ("A", "B", "C"):
                selected = [r for r in schedule if r["condition"] == condition]
                self.assertEqual(18, len(selected))
                self.assertEqual(expected, {(r["task_id"], r["task_digest"]) for r in selected})
                for repetition in (1, 2, 3):
                    self.assertEqual(6, sum(r["repetition"] == repetition for r in selected))
            for index in range(0, 54, 3):
                block = schedule[index:index + 3]
                self.assertEqual({"A", "B", "C"}, {r["condition"] for r in block})
                self.assertEqual(1, len({(r["task_id"], r["repetition"]) for r in block}))
            summary = (out / "summary.md").read_bytes()
            self.assertEqual(hashlib.sha256(summary).hexdigest(), plan["summary_sha256"])
            self.assertIn("3 x 6 x 3 = 54", summary.decode())
            self.assertIn("27 hours", summary.decode())
            self.assertIn("GPT-Rosalind", summary.decode())
            self.assertFalse(plan["execute"])
            self.assertFalse(plan["execution_authorized"])

    def test_fixed_seed_determinism_and_changed_seed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, seed in (("one", "0"), ("two", "0"), ("three", "1")):
                self.assertEqual(0, self.invoke(root / name, "--seed", seed))
            grids = [[row["run_id"] for row in self.read_plan(root / name)["schedule"]]
                     for name in ("one", "two", "three")]
            self.assertEqual(grids[0], grids[1])
            self.assertNotEqual(grids[0], grids[2])

    def test_unverified_identifiers_and_plain_commands_are_blocked(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary) / "plan"
            self.assertEqual(0, self.invoke(out))
            plan = self.read_plan(out)
            condition = plan["conditions"][1]
            self.assertEqual(4, len(condition["plugins"]))
            self.assertTrue(all(p["selector"] is None and p["status"] == "unverified_placeholder"
                                for p in condition["plugins"]))
            self.assertIn("unverified_plugin_identifiers", condition["command_blockers"])
            evidence = plan["local_evidence"]
            self.assertEqual("unresolved_user_decision", evidence["plain_isolation"]["status"])
            self.assertEqual("unverified", evidence["life_science_plugins"]["status"])
            self.assertTrue(evidence["plain_isolation"]["sources"])
            self.assertTrue(evidence["life_science_plugins"]["sources"])
            for row in plan["schedule"]:
                if row["condition"] in ("A", "B"):
                    self.assertIsNone(row["codex_argv"])
                    self.assertIsNone(row["runner_plan_only_argv"])
                    self.assertTrue(row["command_blockers"])

    def test_explicit_plugin_flags_partial_complete_and_invalid(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            flags = []
            for name in self.planner.LIFE_SCIENCE:
                flags.extend(["--life-science-plugin", f"{name}={name}@operator-marketplace"])
            self.assertEqual(0, self.invoke(root / "partial", *flags[:2]))
            self.assertIn("unverified_plugin_identifiers",
                          self.read_plan(root / "partial")["conditions"][1]["command_blockers"])
            self.assertEqual(0, self.invoke(root / "complete", *flags))
            condition = self.read_plan(root / "complete")["conditions"][1]
            self.assertNotIn("unverified_plugin_identifiers", condition["command_blockers"])
            self.assertTrue(condition["command_blockers"])
            self.assertTrue(all(p["status"] == "user_supplied_unverified_provenance" for p in condition["plugins"]))
            invalid = ["", "0", "pubmed", "other=pubmed@market", "pubmed=", "pubmed=pubmed",
                       "pubmed=codex-science@market", "pubmed=a@bad/market"]
            for index, value in enumerate(invalid):
                out = root / f"invalid-{index}"
                self.assertEqual(2, self.invoke(out, "--life-science-plugin", value))
                self.assertFalse(out.exists())
            for index, duplicate in enumerate((flags[:2], ["--life-science-plugin", "pubmed=alphafold@operator-marketplace"])):
                self.assertEqual(2, self.invoke(root / f"duplicate-{index}", *flags[:2], *duplicate))

    def test_runner_scaffolding_and_pinned_argv_reuse(self):
        from codex_science.literature_evaluation_runner import _argv, load_task_set

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "shared-home"
            (root / "target").mkdir()
            (root / "alias").symlink_to(root / "target", target_is_directory=True)
            (root / "tasks.json").symlink_to(TASKS)
            task_by_id = {t["id"]: t for t in load_task_set(TASKS)["tasks"]}
            cases = [(root / "absolute-plan", root / "absolute-plan"),
                     (Path("relative-plan"), root / "relative-plan"),
                     (Path("alias/linked-plan"), root / "alias/linked-plan")]
            with contextlib.chdir(root):
                for out, intended_out in cases:
                    with self.subTest(out=out):
                        self.assertEqual(0, self.invoke(out, "--timeout-seconds", "1", "--plugin",
                                                      "codex-science@branch", "--codex-home", "shared-home",
                                                      "--tasks", "tasks.json"))
                        plan = self.read_plan(out)
                        self.assertEqual(str(root / "tasks.json"), plan["tasks_path"])
                        self.assertFalse(home.exists())
                        self.assertEqual({1}, {r["timeout_seconds"] for r in plan["schedule"]})
                        for row in plan["schedule"]:
                            intended_run = intended_out / "runs" / row["run_id"]
                            path = intended_run / row["task_id"]
                            self.assertEqual(str(intended_run), row["runner_out"])
                            self.assertEqual(str(path), row["receipt_directory"])
                            self.assertEqual({"CODEX_HOME": str(home)}, row["environment"])
                            report = row["report_argv"]
                            self.assertEqual(str(ROOT / "scripts/report_literature_evaluation.py"), report[1])
                            self.assertEqual(str(intended_run), report[report.index("--runs") + 1])
                            self.assertEqual(str(root / "tasks.json"), report[report.index("--tasks") + 1])
                            if row["condition"] != "C":
                                continue
                            runner = row["runner_plan_only_argv"]
                            self.assertNotIn("--execute", runner)
                            self.assertEqual(str(ROOT / "scripts/run_literature_evaluation.py"), runner[1])
                            self.assertEqual(str(intended_run), runner[runner.index("--out") + 1])
                            self.assertEqual(str(root / "tasks.json"), runner[runner.index("--tasks") + 1])
                            self.assertEqual("1", runner[runner.index("--timeout-seconds") + 1])
                            self.assertEqual("codex-science@branch", runner[runner.index("--plugin") + 1])
                            self.assertEqual(str(home), runner[runner.index("--codex-home") + 1])
                            argv = row["codex_argv"]
                            project = Path(argv[argv.index("-C") + 1])
                            last = Path(argv[argv.index("-o") + 1])
                            self.assertTrue(project.is_absolute())
                            self.assertTrue(last.is_absolute())
                            self.assertEqual(path / "project", project)
                            self.assertEqual(path / "last.md", last)
                            expected = _argv("codex", task_by_id[row["task_id"]], project, last,
                                             plugin="codex-science@branch")
                            expected[2:2] = ["--model", "fixed-model-v1"]
                            self.assertEqual(expected, argv)

    def test_limits_empty_zero_equal_and_malformed_refuse_before_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            invalid = [("--repetitions", ""), ("--repetitions", "0"), ("--repetitions", "2"),
                       ("--repetitions", "3.5"), ("--timeout-seconds", ""), ("--timeout-seconds", "0"),
                       ("--timeout-seconds", "1801"), ("--timeout-seconds", "bad"),
                       ("--seed", ""), ("--seed", "bad"), ("--model", ""), ("--model", "a b"),
                       ("--model", "GPT-Rosalind"), ("--plugin", ""), ("--plugin", "0"),
                       ("--plugin", "other@market"), ("--plugin", "codex-science@bad/market"),
                       ("--execute",)]
            for index, options in enumerate(invalid):
                with self.subTest(options=options):
                    out = root / f"invalid-{index}"
                    self.assertEqual(2, self.invoke(out, *options))
                    self.assertFalse(out.exists())
            self.assertEqual(0, self.invoke(root / "edge", "--repetitions", "3", "--timeout-seconds", "1800", "--seed", "-1"))
            self.assertEqual(0, self.invoke(root / "four", "--repetitions", "4"))
            self.assertEqual(72, self.read_plan(root / "four")["budget"]["run_count"])
            broken = root / "tasks.json"
            for data in ("", "{}", "not-json"):
                broken.write_text(data)
                self.assertEqual(2, self.invoke(root / "bad-tasks", "--tasks", str(broken)))
                self.assertFalse((root / "bad-tasks").exists())

    def test_no_process_network_or_frozen_changes(self):
        frozen = [ROOT / "scripts/run_literature_evaluation.py", ROOT / "scripts/report_literature_evaluation.py"]
        frozen.extend((ROOT / "src/codex_science").rglob("*.py"))
        frozen.extend((ROOT / "benchmarks/literature-review").rglob("*"))
        before = {p: p.read_bytes() for p in frozen if p.is_file()}
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary) / "plan"
            with patch("subprocess.Popen", side_effect=AssertionError("process launch forbidden")), \
                    patch("socket.socket", side_effect=AssertionError("network forbidden")):
                self.assertEqual(0, self.invoke(out))
            plan = self.read_plan(out)
            recorded = [item["path"] for item in plan["frozen_files"]]
            required = {"src/codex_science/literature_v2.py", "src/codex_science/rigor.py",
                        "src/codex_science/completion_report.py", "src/codex_science/rubric_tree.py",
                        "src/codex_science/citation_trace.py", "src/codex_science/checkpoints.py",
                        "src/codex_science/runtime_identity.py", "src/codex_science/cli_io.py"}
            self.assertTrue(required.issubset(recorded), required - set(recorded))
            self.assertEqual(sorted(set(recorded)), recorded)
            self.assertEqual(recorded, plan["grader"]["sources"])
            for item in plan["frozen_files"]:
                self.assertEqual(hashlib.sha256(before[ROOT / item["path"]]).hexdigest(), item["sha256"])
            canonical = json.dumps(plan["frozen_files"], sort_keys=True, separators=(",", ":")).encode()
            self.assertEqual(hashlib.sha256(canonical).hexdigest(), plan["grader"]["sha256"])
            self.assertIn(f"Scoring closure: {len(recorded)} files", (out / "summary.md").read_text())
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_scoring_closure_digest_tracks_dependency_and_data_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = root / "fixture"
            sources = [ROOT / "scripts/run_literature_evaluation.py", ROOT / "scripts/report_literature_evaluation.py"]
            sources.extend((ROOT / "src/codex_science").rglob("*.py"))
            sources.extend((ROOT / "benchmarks/literature-review").rglob("*"))
            for source in sources:
                if source.is_file():
                    target = fixture / source.relative_to(ROOT)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(source.read_bytes())
            tasks = fixture / "benchmarks/literature-review/tasks.json"
            changed = fixture / "src/codex_science/literature_v2.py"
            original = changed.read_bytes()
            real_import = __import__

            def forbid_scoring_imports(name, *args, **kwargs):
                if name == "codex_science" or name.startswith("codex_science."):
                    raise AssertionError("scoring dependency import forbidden")
                return real_import(name, *args, **kwargs)

            with patch.object(self.planner, "ROOT", fixture), \
                    patch("builtins.__import__", side_effect=forbid_scoring_imports), \
                    patch("subprocess.Popen", side_effect=AssertionError("process launch forbidden")), \
                    patch("socket.socket", side_effect=AssertionError("network forbidden")):
                self.assertEqual(0, self.invoke(root / "before", "--tasks", str(tasks)))
                changed.write_bytes(original + b"\n")
                self.assertEqual(0, self.invoke(root / "after", "--tasks", str(tasks)))
                before = self.read_plan(root / "before")
                after = self.read_plan(root / "after")
                self.assertNotEqual(before["grader"]["sha256"], after["grader"]["sha256"])
                first = {item["path"]: item["sha256"] for item in before["frozen_files"]}
                second = {item["path"]: item["sha256"] for item in after["frozen_files"]}
                self.assertEqual({"src/codex_science/literature_v2.py"},
                                 {name for name in first if first[name] != second[name]})
                nested = fixture / "benchmarks/literature-review/nested/rubric.json"
                nested.parent.mkdir()
                nested.write_text("{}")
                self.assertEqual(0, self.invoke(root / "data", "--tasks", str(tasks)))
                data_plan = self.read_plan(root / "data")
                self.assertIn("benchmarks/literature-review/nested/rubric.json", data_plan["grader"]["sources"])
                self.assertNotEqual(after["grader"]["sha256"], data_plan["grader"]["sha256"])
                missing = ["scripts/run_literature_evaluation.py", "scripts/report_literature_evaluation.py",
                           "src/codex_science/citation_trace.py", "src/codex_science/literature_evaluation_report.py",
                           "src/codex_science/literature_v2.py"]
                for index, name in enumerate(missing):
                    path = fixture / name
                    content = path.read_bytes()
                    path.unlink()
                    out = root / f"missing-{index}"
                    try:
                        self.assertEqual(2, self.invoke(out, "--tasks", str(tasks)))
                        self.assertFalse(out.exists())
                    finally:
                        path.write_bytes(content)
                changed.write_text("not valid Python :::")
                self.assertEqual(2, self.invoke(root / "malformed", "--tasks", str(tasks)))
                self.assertFalse((root / "malformed").exists())

    def test_scoring_inventory_import_forms_cycles_and_empty_sources(self):
        sources = {
            "scripts/run_literature_evaluation.py": b"import codex_science.helpers\nfrom codex_science import zero\n",
            "scripts/report_literature_evaluation.py": b"",
            "src/codex_science/citation_trace.py": b"from . import helpers\n",
            "src/codex_science/literature_evaluation_report.py": b"from .helpers import *\n",
            "src/codex_science/__init__.py": b"",
            "src/codex_science/helpers/__init__.py": b"from .child import score\n",
            "src/codex_science/helpers/child.py": (b"from .. import zero\nfrom codex_science import helpers\n"
                                                   b"score = 0\nraise AssertionError('source executed')\n"),
            "src/codex_science/zero.py": b"",
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, content in sources.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            benchmark = root / "benchmarks/literature-review"
            benchmark.mkdir(parents=True)
            rows = self.planner.scoring_inventory(root)
            self.assertEqual(sorted(sources), [row["path"] for row in rows])
            for row in rows:
                self.assertEqual(hashlib.sha256(sources[row["path"]]).hexdigest(), row["sha256"])
            (root / "src/codex_science/citation_trace.py").write_text("from .. import zero\n")
            with self.assertRaisesRegex(ValueError, "invalid relative scoring import"):
                self.planner.scoring_inventory(root)
            (root / "src/codex_science/citation_trace.py").write_bytes(sources["src/codex_science/citation_trace.py"])
            benchmark.rmdir()
            with self.assertRaisesRegex(ValueError, "missing scoring data directory"):
                self.planner.scoring_inventory(root)

    def test_existing_symlink_concurrent_and_interrupted_outputs_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            out = root / "plan"
            self.assertEqual(0, self.invoke(out))
            before = {p.name: p.read_bytes() for p in out.iterdir()}
            self.assertEqual(2, self.invoke(out))
            self.assertEqual(before, {p.name: p.read_bytes() for p in out.iterdir()})
            link = root / "link"
            link.symlink_to(out, target_is_directory=True)
            self.assertEqual(2, self.invoke(link))
            self.assertEqual(2, self.invoke(root / "missing-parent" / "plan"))
            partial = root / "partial"
            original = Path.open

            def fail_json(path, *args, **kwargs):
                if path == partial / "plan.json":
                    raise OSError("interrupted before second write")
                return original(path, *args, **kwargs)

            with patch.object(Path, "open", fail_json):
                self.assertEqual(2, self.invoke(partial))
            self.assertTrue((partial / "summary.md").exists())
            self.assertFalse((partial / "plan.json").exists())
            self.assertEqual(2, self.invoke(partial))
            arguments = [sys.executable, str(SCRIPT), "--tasks", str(TASKS), "--out", str(root / "race"),
                         "--model", "fixed-model-v1"]
            first = subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            second = subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            timeout = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120"))
            try:
                first.communicate(timeout=timeout)
                second.communicate(timeout=timeout)
            finally:
                for process in (first, second):
                    if process.poll() is None:
                        process.kill()
                    process.communicate()
            self.assertEqual([0, 2], sorted([first.returncode, second.returncode]))
            self.assertEqual(54, self.read_plan(root / "race")["budget"]["run_count"])

    def test_policy_metrics_and_grader_bias_are_preregistered(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary) / "plan"
            self.assertEqual(0, self.invoke(out))
            plan = self.read_plan(out)
            self.assertIn("provider_policy_block counts as failure", plan["rules"]["policy_blocks"])
            self.assertIn("at most one linked rerun", plan["rules"]["infrastructure_rerun"])
            self.assertIn("all scheduled slots", plan["rules"]["attrition"])
            self.assertIn("can favor C", plan["grader"]["limitation"])
            self.assertEqual(6, len(plan["grader"]["metrics"]))
            self.assertIn("never zero", plan["grader"]["limitation"])


if __name__ == "__main__":
    unittest.main()
