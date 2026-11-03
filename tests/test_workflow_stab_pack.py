"""Offline synthetic stability fixtures, hand arithmetic, refusal and race controls."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from codex_science import stability_shelf_life_pack as stab


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "workflow-stability-shelf-life"
CLI = ROOT / "scripts" / "validate_stability_shelf_life_pack.py"
CALL_TIMEOUT = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "30"))
CASES = json.loads((FIXTURE / "negative-cases.json").read_bytes())["cases"]


def _read(path):
    return json.loads(path.read_bytes())


def _write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")


def _identity(path):
    return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


class FixtureTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.parent = Path(self.temporary.name) / "parent"
        self.directory = self.parent / "bundle"
        shutil.copytree(FIXTURE, self.directory)

    def edit(self, target, path, value):
        file = self.directory / (target + ".json")
        record = _read(file)
        owner = record
        for key in path[:-1]:
            owner = owner[key]
        owner[path[-1]] = value
        _write(file, record)

    def refresh(self, recompute=False):
        protocol = _read(self.directory / "protocol.json")
        report = _read(self.directory / "report.json")
        report["protocol_sha256"] = _identity(self.directory / "protocol.json")["sha256"]
        if recompute:
            result = stab.compute_stability(_read(self.directory / "data.json"), protocol, report["specification_limit"])
            report["selected_model"] = result["selected_model"]
            report["evaluation_time"] = result["maximum_time"]
            report["summary"] = {key: result[key] for key in ("n", "df", "earliest_crossing")}
        _write(self.directory / "report.json", report)
        evidence = _read(self.directory / "evidence.json")
        for record in evidence["records"]:
            source = self.directory / record["source"]["path"]
            record["source"]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        _write(self.directory / "evidence.json", evidence)
        pack = _read(self.directory / "pack.json")
        for key in ("protocol", "data", "report"):
            pack[key] = _identity(self.directory / (key + ".json"))
        pack["evidence"] = [_identity(self.directory / "evidence.json")]
        pack["frozen_protocol_sha256"] = pack["protocol"]["sha256"]
        _write(self.directory / "pack.json", pack)

    def validate(self):
        return stab.validate_stability_shelf_life_pack(self.directory / "pack.json")

    def refusal(self, code, operation=None):
        with self.assertRaisesRegex(ValueError, "^" + code + ":"):
            (operation or self.validate)()

    def command(self, *args):
        return subprocess.run([sys.executable, str(CLI), *map(str, args)], text=True,
                              capture_output=True, timeout=CALL_TIMEOUT)


class SeededDefectTests(FixtureTest):
    def check_case(self, case):
        for change in case["changes"]:
            self.edit(change["target"], change["path"], change["value"])
        self.refresh()
        self.refusal(case["code"])
        process = self.command(self.directory / "pack.json")
        self.assertEqual(process.returncode, 2, process.stderr)
        self.assertEqual(process.stdout, "")
        error = json.loads(process.stderr)
        self.assertEqual(error["status"], "refused")
        self.assertTrue(error["error"].startswith(case["code"] + ":"), error)
        self.assertNotIn("Traceback", process.stderr)


def _seeded(case):
    def test(self):
        self.check_case(case)
    return test


for _case in CASES:
    setattr(SeededDefectTests, "test_" + _case["id"].replace("-", "_"), _seeded(_case))


class ReferenceTests(FixtureTest):
    def test_fixture_and_hand_arithmetic(self):
        result = self.validate()
        self.assertEqual(result["status"], "arithmetic-only")
        self.assertEqual(result["review"], "unavailable")
        self.assertEqual(result["stages"], list(stab.STAGES))
        computation = result["computation"]
        def compare(actual, expected):
            if type(expected) is dict:
                self.assertEqual(set(actual), set(expected))
                for key in expected:
                    compare(actual[key], expected[key])
            elif type(expected) is float:
                self.assertTrue(math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-12))
            else:
                self.assertEqual(actual, expected)
        compare(computation, _read(FIXTURE / "expected.json")["computation"])
        self.assertEqual(computation["n"], 12)
        for batch, slope in zip(("batch-a", "batch-b", "batch-c"), (-1, -1, -2)):
            fit = computation["per_batch"][batch]
            self.assertEqual(fit["n"], 4)
            self.assertEqual(fit["df"], 2)
            self.assertAlmostEqual(fit["x_mean"], 1.5)
            self.assertAlmostEqual(fit["sxx"], 5)
            self.assertAlmostEqual(fit["slope"], slope)
            self.assertAlmostEqual(fit["intercept"], 10)
            self.assertAlmostEqual(fit["sse"], .04)
            self.assertAlmostEqual(fit["mse"], .02)
        test = computation["poolability"]["slope"]
        self.assertAlmostEqual(test["f"], 250/3)
        self.assertEqual((test["df1"], test["df2"]), (2, 6))
        self.assertAlmostEqual(test["p"], (6 / (6 + 2*(250/3)))**3)
        self.assertEqual(computation["poolability"]["intercept"], "not-tested-after-slope-rejection")
        t95 = math.sqrt(162/19)  # Closed form for df=2 at CDF=.95.
        self.assertAlmostEqual(computation["t_quantiles"]["2"], t95)
        time = computation["earliest_crossing"]
        self.assertAlmostEqual(10 - 2*time - t95*math.sqrt(.02*(.25+(time-1.5)**2/5)), 4)
        self.assertAlmostEqual(time, 2.83893068942765)
        process = self.command(self.directory / "pack.json")
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout), result)
        self.assertEqual(process.stderr, "")

    def test_pooling_and_intercept_rejection(self):
        data = _read(self.directory / "data.json")
        protocol = _read(self.directory / "protocol.json")
        for row in data["rows"]:
            if row["batch"] == "batch-c":
                row["result"] += row["time"]
        pooled = stab.compute_stability(data, protocol)
        self.assertEqual(pooled["selected_model"], "pooled")
        self.assertEqual(pooled["df"], {"pooled": 10})
        self.assertAlmostEqual(pooled["selected_fits"]["pooled"]["sse"], .12)
        self.assertEqual(pooled["poolability"]["slope"]["p"], 1)
        self.assertEqual(pooled["poolability"]["intercept"]["p"], 1)
        self.assertAlmostEqual(pooled["t_quantiles"]["10"], 1.81246112281073)
        _write(self.directory / "data.json", data)
        self.refresh(recompute=True)
        self.assertEqual(self.validate()["computation"]["selected_model"], "pooled")
        for row in data["rows"]:
            if row["batch"] == "batch-c":
                row["result"] += 2
        separate = stab.compute_stability(data, protocol)
        self.assertEqual(separate["selected_model"], "individual")
        self.assertLess(separate["poolability"]["intercept"]["p"], protocol["alpha"])
        _write(self.directory / "data.json", data)
        self.refresh(recompute=True)
        self.assertEqual(self.validate()["computation"]["selected_model"], "individual")

    def test_crossing_edges_and_upper_direction(self):
        data = _read(self.directory / "data.json")
        protocol = _read(self.directory / "protocol.json")
        protocol["specification_limit"] = -100
        self.assertEqual(stab.compute_stability(data, protocol)["earliest_crossing"], "not-reached-within-observed-range")
        protocol["specification_limit"] = 100
        self.assertEqual(stab.compute_stability(data, protocol)["earliest_crossing"], 0)
        protocol["direction"] = "upper"
        protocol["specification_limit"] = -4
        for row in data["rows"]:
            row["result"] = -row["result"]
        self.assertAlmostEqual(stab.compute_stability(data, protocol)["earliest_crossing"], 2.83893068942765)
        protocol["specification_limit"] = -100
        self.assertEqual(stab.compute_stability(data, protocol)["earliest_crossing"], 0)
        protocol["specification_limit"] = 100
        self.assertEqual(stab.compute_stability(data, protocol)["earliest_crossing"], "not-reached-within-observed-range")
        # Exact horizon crossing, with explicit signs even for subnormal margins.
        fit = dict(n=4, df=2, intercept=10, slope=-1, mse=.02, x_mean=1.5, sxx=5)
        protocol["direction"] = "lower"
        horizon = 6
        q = stab.t_quantile(.95, 2)
        limit = 10-horizon-q*math.sqrt(.02*(.25+(horizon-1.5)**2/5))
        self.assertEqual(stab._crossing(fit, protocol, limit, {2:q}), horizon)
        with patch.object(stab, "t_quantile", return_value=0):
            fit.update(intercept=2e-300, slope=-1e-300)
            self.assertAlmostEqual(stab._crossing(fit, protocol, 0, {2:0}), 2)

    def test_exploratory_change_requires_honest_recomputation(self):
        self.edit("report", ["specification_limit"], 3)
        self.edit("report", ["exploratory"], True)
        self.refresh(recompute=True)
        result = self.validate()
        self.assertTrue(result["exploratory"])
        self.assertGreater(result["computation"]["earliest_crossing"], 3)

    def test_censored_and_degenerate_data_are_retained(self):
        self.edit("data", ["rows", 0, "censored"], True)
        self.edit("data", ["rows", 0, "result"], None)
        self.edit("data", ["rows", 0, "quantification_limit"], 1)
        self.refresh()
        before = (self.directory / "data.json").read_bytes()
        self.refusal("censored-fit-unavailable")
        self.assertEqual((self.directory / "data.json").read_bytes(), before)
        data = _read(FIXTURE / "data.json")
        protocol = _read(FIXTURE / "protocol.json")
        for row in data["rows"]:
            row["result"] = 10-row["time"]
        self.refusal("degenerate-regression", lambda: stab.compute_stability(data, protocol))
        self.refusal("degenerate-regression", lambda: stab._fit([dict(time=0,result=y) for y in (1,2,3)]))
        self.refusal("degenerate-regression", lambda: stab._fit([]))
        with patch.object(stab, "BETA_ITERATIONS", 0):
            self.refusal("numeric-convergence", lambda: stab.t_quantile(.95, 2))
        with patch.object(stab, "SOLVER_ITERATIONS", 0):
            self.refusal("numeric-convergence", lambda: stab.t_quantile(.95, 2))

    def test_probability_and_numeric_edges(self):
        self.assertAlmostEqual(stab.t_quantile(.95, 1), 1/math.tan(math.pi*.05))
        self.assertAlmostEqual(stab.t_quantile(.95, 100), 1.66023432606575)
        for probability in (0, .5, 1, True, None, "0.95", float("nan")):
            self.refusal("invalid-record", lambda: stab.t_quantile(probability, 2))
        for df in (0, 2.0, True, "2", [], stab.MAX_ROWS+1):
            self.refusal("invalid-record", lambda: stab.t_quantile(.95, df))
        self.assertEqual(stab._beta(0, 1, 1), 0)
        self.assertEqual(stab._beta(1, 1, 1), 1)


class AdmissionTests(FixtureTest):
    def test_pack_contract_metadata_and_frozen_questions(self):
        skill = ROOT / "authored-skills" / "workflow-stability-shelf-life"
        lines = (skill / "SKILL.md").read_text().splitlines()
        description = next(line for line in lines if line.startswith("description:"))
        for word in ("workflow", "analysis", "statistics", "pipeline", "regression"):
            self.assertNotIn(word, description.lower())
        for section in ("## Decision contract", "## Reference usage", "## Workflow", "## Outputs", "## Boundaries"):
            self.assertIn(section, lines)
        for document in [*(skill.rglob("*.md")), *(FIXTURE.rglob("*.md"))]:
            if document.name != "SKILL.md":
                self.assertNotRegex(document.read_text(), r"\[[^\]]*\]\(")
        quality = _read(skill / "quality.json")
        self.assertEqual(quality["test_files"], ["tests/test_workflow_stab_pack.py"])
        self.assertEqual(set(quality["seeded_failures"]), {case["id"] for case in CASES})
        self.assertEqual(quality["declared_maturity"], "L4")
        for envelope, schema in (("expected.json", "expected-fixture"), ("negative-cases.json", "negative-fixtures")):
            value = _read(FIXTURE / envelope)
            self.assertEqual(value["fixture"], "synthetic fixture")
            self.assertEqual(value["schema"], "stability-shelf-life-" + schema + "-v1")
        plan = _read(skill / "references" / "plan.json")
        self.assertEqual([step["id"] for step in plan["plan"]], list(stab.STAGES))
        for step in plan["plan"]:
            self.assertEqual(set(step), {"id", "description", "status"})
            self.assertEqual(step["status"], "pending")
        tasks = _read(ROOT / "benchmarks" / "workflow-stability-shelf-life" / "tasks.json")
        self.assertEqual(tasks["fixture"], "synthetic fixture")
        for task in tasks["tasks"]:
            self.assertTrue(task["acceptance_criteria"])
            self.assertFalse(task["budget"]["network"])
            self.assertFalse(task["budget"]["gpu"])
            self.assertTrue((ROOT / task["input"]).is_file())

    def test_reads_once_then_rehashes_and_aggregate_json_budget(self):
        original_fdopen = os.fdopen
        reads = []
        def opened(descriptor, *args, **kwargs):
            handle = original_fdopen(descriptor, *args, **kwargs)
            read = handle.read
            def tracked(limit):
                info = os.fstat(handle.fileno())
                reads.append((info.st_dev, info.st_ino, limit))
                self.assertLessEqual(limit, stab.MAX_BYTES+1)
                return read(limit)
            handle.read = tracked
            return handle
        with patch.object(stab.os, "fdopen", opened):
            self.validate()
        self.assertEqual(len(reads), 10)
        counts = {}
        for dev, ino, _ in reads:
            counts[dev,ino] = counts.get((dev,ino), 0)+1
        self.assertEqual(set(counts.values()), {2})
        total_nodes = 0
        original_json = stab._json
        def parsed(raw, allowance):
            nonlocal total_nodes
            answer = original_json(raw, allowance)
            total_nodes += answer[1]
            return answer
        with patch.object(stab, "_json", parsed):
            self.validate()
        with patch.object(stab, "MAX_JSON_VALUES", total_nodes):
            self.validate()
        with patch.object(stab, "MAX_JSON_VALUES", total_nodes-1):
            self.refusal("input-limit")
        # Distinct artifacts share the aggregate allowance; no per-file reset.
        with patch.object(stab, "MAX_JSON_VALUES", total_nodes//2):
            self.refusal("input-limit")

    def test_cli_argument_errors_and_help(self):
        for args in ((), ("a", "b"), ("--unknown",), ("--output", "a")):
            process = self.command(*args)
            self.assertEqual(process.returncode, 2)
            self.assertEqual(process.stdout, "")
            self.assertTrue(json.loads(process.stderr)["error"].startswith("invalid-arguments:"))
        process = self.command("--help")
        self.assertEqual(process.returncode, 0)
        self.assertIn("usage:", process.stdout)
        self.assertEqual(process.stderr, "")
        process = self.command(self.directory / "missing.json")
        self.assertEqual(process.returncode, 2)
        self.assertTrue(json.loads(process.stderr)["error"].startswith("input-file:"))

    def test_json_refusals_and_preparse_budget(self):
        raw_inputs = (b'{}{}', b'[]', b'{"x":1,"x":2}', b'{"x":{"a":1,"a":2}}',
                      b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e400}',
                      b'{"x":'+b'9'*200+b'}', b'\xff', b'{"x":'+b'['*1100+b'0'+b']'*1100+b'}')
        for raw in raw_inputs:
            (self.directory / "pack.json").write_bytes(raw)
            self.refusal("invalid-json")
        with patch.object(stab.re, "findall", side_effect=AssertionError("allocating match list")):
            self.assertEqual(stab._json(b'{"x":[1,2]}', 10)[0], {"x":[1,2]})
        for raw in (b'{"x":[]}', b'{"x":{}}', b'{"x":[1,2]}'):
            with patch.object(stab.json, "loads", side_effect=AssertionError("parsed before budget")):
                self.refusal("input-limit", lambda: stab._json(raw, 1))
        with patch.object(stab, "MAX_DEPTH", 0):
            self.refusal("invalid-json", lambda: stab._json(b'{"x":{}}', 10))
        with patch.object(stab, "MAX_TEXT", 2):
            self.refusal("input-limit", lambda: stab._json(b'{"x":"abc"}', 10))
        with patch.object(stab, "MAX_ITEMS", 1):
            self.refusal("input-limit", lambda: stab._json(b'{"a":1,"b":2}', 10))
        for allowance in (0,):
            self.refusal("input-limit", lambda: stab._json(b'{}', allowance))
        self.assertEqual(stab._json(b'{}', 1), ({}, 1))
        self.assertEqual(stab._json(b'{"x":[1,2]}', 5)[1], 4)

    def test_protocol_report_and_collection_edges(self):
        protocol = _read(FIXTURE / "protocol.json")
        data = _read(FIXTURE / "data.json")
        for field, values in (("alpha", (0, 1, True, [], "0.25")),
                              ("extrapolation_multiple", (0, 10.001, True, [], "2")),
                              ("confidence_level", (0, 1, True, [], "0.95"))):
            for value in values:
                changed = dict(protocol)
                changed[field] = value
                self.refusal("confidence-level" if field == "confidence_level" and type(value) is int else "invalid-record",
                             lambda: stab.compute_stability(data, changed))
        for multiple in (1, stab.MAX_EXTRAPOLATION):
            changed = dict(protocol, extrapolation_multiple=multiple)
            self.assertEqual(stab.compute_stability(data, changed)["maximum_time"], 3*multiple)
        for field in ("batches", "time_points"):
            for value in ([], 0, None, "fixture"):
                changed = dict(protocol)
                changed[field] = value
                self.refusal("invalid-record", lambda: stab.compute_stability(data, changed))
        changed = dict(protocol, time_points=[0, 1, 1, 3])
        self.refusal("time-order", lambda: stab.compute_stability(data, changed))
        changed = dict(protocol, time_points=[.1, 1, 2, 3])
        self.refusal("missing-baseline", lambda: stab.compute_stability(data, changed))
        changed = dict(protocol, time_points=[0, 1, 2, 1e6])
        for row in data["rows"]:
            if row["time"] == 3:
                row["time"] = stab.MAX_TIME
        self.assertEqual(stab.compute_stability(data, changed)["observed_duration"], stab.MAX_TIME)
        changed["time_points"][-1] += 1
        self.refusal("invalid-record", lambda: stab.compute_stability(data, changed))
        original = _read(self.directory / "report.json")
        for value in ([], True, -1, "6", None):
            self.edit("report", ["evaluation_time"], value)
            self.refresh()
            self.refusal("invalid-record")
        self.edit("report", ["evaluation_time"], 0)
        self.refresh()
        self.refusal("reported-number")
        _write(self.directory / "report.json", original)
        self.refresh()
        self.validate()
        self.assertEqual(stab._names([], "evidence", 0, True), [])
        self.assertEqual(stab._names(["a"], "evidence", 1), ["a"])
        for value in (0, None, "a"):
            self.refusal("invalid-record", lambda: stab._names(value, "evidence", 1))
        self.refusal("input-limit", lambda: stab._names(["a", "b"], "evidence", 1))
        with patch.object(stab, "MAX_TEXT", 3):
            self.assertEqual(stab._text("abc", "fixture"), "abc")
            for value in ("", "abcd", 0, []):
                self.refusal("invalid-record", lambda: stab._text(value, "fixture"))
        with patch.object(stab, "MAX_DEPTH", 1):
            stab._json(b'{"x":1}', 4)
            self.refusal("invalid-json", lambda: stab._json(b'{"x":{"y":1}}', 5))
        with patch.object(stab, "MAX_ITEMS", 1):
            stab._json(b'{"x":1}', 3)
        # At the significance threshold equality permits pooling.
        protocol = _read(FIXTURE / "protocol.json")
        data = _read(FIXTURE / "data.json")
        test = dict(f=1, df1=2, df2=6, p=protocol["alpha"])
        with patch.object(stab, "_f_test", return_value=test):
            self.assertEqual(stab.compute_stability(data, protocol)["selected_model"], "pooled")

    def test_integer_types_and_unhashable_fields(self):
        for target, path in (("protocol", ["minimum_batches"]), ("protocol", ["minimum_time_points"]),
                             ("report", ["summary", "n"]), ("report", ["summary", "df", "batch-a"])):
            original = _read(self.directory / (target+".json"))
            for value in (True, 4.0, "4", []):
                _write(self.directory / (target+".json"), original)
                self.edit(target, path, value)
                self.refresh()
                self.refusal("invalid-record")
            _write(self.directory / (target+".json"), original)
            self.refresh()
        for path in (["claims",0,"status"], ["claims",0,"kind"], ["claims",0,"evidence",0]):
            original = _read(self.directory / "report.json")
            self.edit("report", path, [])
            self.refresh()
            self.refusal("invalid-record")
            _write(self.directory / "report.json", original)
            self.refresh()
        self.assertEqual(self.validate()["status"], "arithmetic-only")

    def test_dimension_limits_before_computation(self):
        protocol = _read(FIXTURE / "protocol.json")
        data = _read(FIXTURE / "data.json")
        for constant, edge in (("MAX_ROWS", 12), ("MAX_BATCHES", 3), ("MAX_TIME_POINTS", 4)):
            with patch.object(stab, constant, edge):
                self.validate()
            with patch.object(stab, constant, edge-1):
                self.refusal("input-limit" if constant == "MAX_ROWS" else "invalid-record")
            with patch.object(stab, constant, 0):
                self.refusal("input-limit" if constant == "MAX_ROWS" else "invalid-record")
        with patch.object(stab, "MAX_ROWS", 12), patch.object(stab, "_fit", side_effect=AssertionError("fit before count")):
            data["rows"].append(copy.deepcopy(data["rows"][0]))
            self.refusal("input-limit", lambda: stab.compute_stability(data, protocol))
        for rows in ([], None, 0):
            data["rows"] = rows
            self.refusal("invalid-record", lambda: stab.compute_stability(data, protocol))
        with patch.object(stab, "MAX_RECORDS", 0):
            self.refusal("input-limit")
        with patch.object(stab, "MAX_ARTIFACTS", 0):
            self.refusal("input-limit")
        with patch.object(stab, "MAX_JSON_VALUES", 0):
            self.refusal("input-limit")

    def test_aggregate_budgets_and_hardlink_cache(self):
        artifacts = [self.directory/name for name in ("pack.json","protocol.json","data.json","report.json","evidence.json")]
        total = sum(path.stat().st_size for path in artifacts)
        with patch.object(stab, "MAX_TOTAL_BYTES", total):
            self.validate()
        for maximum in (0, total-1):
            with patch.object(stab, "MAX_TOTAL_BYTES", maximum):
                self.refusal("input-limit")
        largest = max(path.stat().st_size for path in artifacts)
        with patch.object(stab, "MAX_BYTES", largest):
            self.validate()
        for maximum in (0, largest-1):
            with patch.object(stab, "MAX_BYTES", maximum):
                self.refusal("input-file")
        with patch.object(stab, "MAX_ARTIFACTS", len(artifacts)):
            self.validate()
        with patch.object(stab, "MAX_ARTIFACTS", len(artifacts)-1):
            self.refusal("input-limit")
        store = stab._Bundle(self.directory)
        self.addCleanup(store.close)
        os.link(self.directory / "data.json", self.directory / "alias.json")
        original_json = stab._json
        with patch.object(stab, "_json", wraps=original_json) as parsed:
            first = store.load("data.json")
            second = store.load("alias.json")
            self.assertIs(first, second)
            self.assertEqual(parsed.call_count, 1)
        self.assertEqual(store.total_bytes, (self.directory / "data.json").stat().st_size)
        count = store.nodes
        store.finish()
        with patch.object(stab, "MAX_JSON_VALUES", count):
            another = stab._Bundle(self.directory)
            try:
                another.load("data.json")
            finally:
                another.close()
        with patch.object(stab, "MAX_JSON_VALUES", count-1):
            another = stab._Bundle(self.directory)
            try:
                self.refusal("input-limit", lambda: another.load("data.json"))
            finally:
                another.close()

    def test_nonregular_and_unsafe_paths(self):
        pack_path = self.directory / "pack.json"
        original = _read(pack_path)
        for value in ("../outside.json", "/absolute.json", "a\\b", "./data.json", "a//b", "C:bad", "", 0, []):
            pack = copy.deepcopy(original)
            pack["data"]["path"] = value
            _write(pack_path, pack)
            self.refusal("invalid-record" if value in ("",0,[]) else "input-path")
        _write(pack_path, original)
        data_path = self.directory / "data.json"
        data_path.unlink()
        os.mkfifo(data_path)
        self.refusal("input-file")
        process = self.command(pack_path)
        self.assertEqual(process.returncode, 2)
        self.assertTrue(json.loads(process.stderr)["error"].startswith("input-file:"))
        data_path.unlink()
        data_path.mkdir()
        self.refusal("input-file")
        data_path.rmdir()
        data_path.symlink_to(FIXTURE / "data.json")
        self.refusal("input-file")
        data_path.unlink()
        shutil.copyfile(FIXTURE / "data.json", data_path)
        (self.directory / "linked").symlink_to(FIXTURE, target_is_directory=True)
        original["data"]["path"] = "linked/data.json"
        _write(pack_path, original)
        self.refusal("input-file")

    def test_hash_replacement_growth_and_descriptor_checks(self):
        self.edit("data", ["rows",0,"result"], 11)
        self.refusal("input-hash")
        self.refresh(recompute=True)
        original_read = stab._Bundle._read
        changed = False
        def read_then_replace(store, name):
            nonlocal changed
            answer = original_read(store, name)
            if name == "data.json" and not changed:
                changed = True
                path = self.directory / name
                raw = path.read_bytes()
                path.rename(self.directory / "retained-data.json")
                path.write_bytes(raw)
            return answer
        with patch.object(stab._Bundle, "_read", read_then_replace):
            self.refusal("input-changed")
        original_open = os.open
        changed = False
        def replace_before_open(name, flags, *args, **kwargs):
            nonlocal changed
            if name == "data.json" and not changed:
                changed = True
                target = self.directory / name
                raw = target.read_bytes()
                target.rename(self.directory / "before-open-data.json")
                target.write_bytes(raw)
            return original_open(name, flags, *args, **kwargs)
        with patch.object(stab.os, "open", replace_before_open):
            self.refusal("input-file")
        original_fdopen = os.fdopen
        def growing(descriptor, *args, **kwargs):
            handle = original_fdopen(descriptor, *args, **kwargs)
            read = handle.read
            def grow(limit):
                answer = read(limit)
                if os.fstat(handle.fileno()).st_size == (self.directory / "data.json").stat().st_size:
                    with (self.directory / "data.json").open("ab") as output:
                        output.write(b" ")
                return answer
            handle.read = grow
            return handle
        with patch.object(stab.os, "fdopen", growing):
            self.refusal("input-file")

    def test_transient_ancestor_and_root_symlink_swaps(self):
        original_open = os.open
        for target in (self.parent, self.directory):
            moved = target.with_name(target.name + "-moved")
            swapped = False
            def swap(name, flags, *args, **kwargs):
                nonlocal swapped
                if name == target.name and not swapped and "dir_fd" in kwargs:
                    swapped = True
                    target.rename(moved)
                    target.symlink_to(moved, target_is_directory=True)
                    try:
                        return original_open(name, flags, *args, **kwargs)
                    finally:
                        target.unlink()
                        moved.rename(target)
                return original_open(name, flags, *args, **kwargs)
            with patch.object(stab.os, "open", swap):
                self.refusal("input-root")
            self.assertTrue(swapped)
        original_lstat = os.lstat
        target = self.directory
        moved = self.parent / "moved"
        swapped = False
        def swap_at_lstat(name, *args, **kwargs):
            nonlocal swapped
            if name == target.name and not swapped and "dir_fd" in kwargs:
                swapped = True
                target.rename(moved)
                target.symlink_to(moved, target_is_directory=True)
            return original_lstat(name, *args, **kwargs)
        try:
            with patch.object(stab.os, "lstat", swap_at_lstat):
                self.refusal("input-root")
        finally:
            if swapped:
                target.unlink()
                moved.rename(target)

    def test_parent_identity_change_with_same_bundle_inode(self):
        original_read = stab._Bundle._read
        swapped = False
        moved = self.parent.with_name("parent-moved")
        original_inode = self.directory.stat().st_ino
        def replace_parent(store, name):
            nonlocal swapped
            answer = original_read(store, name)
            if name == "data.json" and not swapped:
                swapped = True
                self.parent.rename(moved)
                self.parent.mkdir()
                (moved / "bundle").rename(self.directory)
                self.assertEqual(self.directory.stat().st_ino, original_inode)
            return answer
        with patch.object(stab._Bundle, "_read", replace_parent):
            self.refusal("input-root")
        self.assertTrue(swapped)

    def test_claim_wording_and_unavailable_semantics(self):
        evidence = {"observed":dict(kind="observed",result="observed"), "missing":dict(kind="unavailable",result="unavailable")}
        claim = dict(id="fixture",kind="descriptive",status="suggestive",text="A synthetic signal is present.",evidence=["observed"])
        stab._claims([claim], evidence)
        for wording in ("causes", "mechanism", "therapeutic", "clinical", "efficacy", "effective", "treat", "cure", "prevent",
                        "recommend", "prescribe", "binding", "affinity", "inhibition", "activation", "regulation", "drives", "induced",
                        "shelf life", "expiry", "physical validity", "product safety", "product quality", "truth"):
            changed = dict(claim,text="Synthetic fixture " + wording)
            self.refusal("claim-overreach", lambda: stab._claims([changed], evidence))
        for status in stab.STATUSES - {"unavailable"}:
            for ids in (["missing"], ["observed","missing"]):
                changed = dict(claim,status=status,evidence=ids)
                self.refusal("unavailable-evidence", lambda: stab._claims([changed], evidence))
        for status in stab.STATUSES - {"unavailable"}:
            self.refusal("missing-evidence", lambda: stab._claims([dict(claim,status=status,evidence=[])], evidence))
        stab._claims([dict(claim,status="unavailable",text="Evidence unavailable.",evidence=[])], evidence)
        self.refusal("claim-replication", lambda: stab._claims([dict(claim,status="replicated")], evidence))
        for field in ("kind", "result"):
            for value in ("review-approval", "computed", "numerical agreement"):
                record = dict(kind="observed",result="observed")
                record[field] = value
                for status in stab.POSITIVE:
                    self.refusal("non-evidence-support", lambda: stab._claims([dict(claim,status=status)], {"observed":record}))

    def test_external_labels_and_hash_aliases(self):
        original = _read(self.directory / "evidence.json")
        shutil.copyfile(self.directory / "data.json", self.directory / "separate.json")
        for origin in ("external", "independent", "preregistered"):
            record = copy.deepcopy(original)
            record["records"][0]["origin"] = origin
            record["records"][0]["source"] = _identity(self.directory / "separate.json")
            _write(self.directory / "evidence.json", record)
            self.refresh()
            self.refusal("external-alias")

    def test_repeated_concurrent_and_interrupted_calls_write_nothing(self):
        before = {path.name:path.read_bytes() for path in self.directory.iterdir() if path.is_file()}
        first = self.validate()
        self.assertEqual(first, self.validate())
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.validate(), range(2)))
        self.assertEqual(results, [first, first])
        original = stab._Bundle._read
        def interrupt(store, name):
            raw = original(store, name)
            if name == "data.json":
                raise KeyboardInterrupt
            return raw
        with patch.object(stab._Bundle, "_read", interrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.validate()
        self.assertEqual(before, {path.name:path.read_bytes() for path in self.directory.iterdir() if path.is_file()})
        self.assertEqual(first, self.validate())


if __name__ == "__main__":
    unittest.main()
