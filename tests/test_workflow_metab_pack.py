"""Offline synthetic LC-MS QC acceptance, hand calculations and hostile-input refusals."""
from collections import Counter
import copy
import hashlib
import importlib
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

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/workflow-metabolomics-feature-qc"
CLI = ROOT / "scripts/validate_metabolomics_feature_qc_pack.py"
CALL_TIMEOUT = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "30"))
CASES = (
    "zero-imputation", "blank-retained", "study-rsd", "study-drift", "post-rules", "unnamed-drop",
    "unavailable-absent", "batch-confounding", "identity", "biomarker", "pathway", "mechanism", "clinical",
    "causal", "physical", "unfrozen", "stage-order", "dropped-sample", "computed-kind", "computed-result",
    "review-kind", "review-result", "external-alias", "empty-evidence", "unavailable-positive",
    "unavailable-negative", "replication",
)


class _Fixture(unittest.TestCase):
    def setUp(self):
        self.api = importlib.import_module("codex_science.metabolomics_feature_qc_pack")
        self.pack = self.read("pack.json")
        self.rules = self.read("rules.json")
        self.sheet = self.read("sheet.json")
        self.table = self.read("table.json")
        self.report = self.read("report.json")

    def read(self, name):
        return json.loads((FIXTURE / name).read_bytes())

    def folder(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        folder = Path(temporary.name) / "parent" / "bundle"
        folder.mkdir(parents=True)
        for name in ("pack.json", "rules.json", "sheet.json", "table.json", "report.json", "evidence.json"):
            shutil.copyfile(FIXTURE / name, folder / name)
        return folder

    def write(self, folder, name, value):
        raw = (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode()
        (folder / name).write_bytes(raw)
        return {"path": name, "sha256": hashlib.sha256(raw).hexdigest()}

    def run_pack(self, folder):
        self.write(folder, "pack.json", self.pack)
        return self.api.validate_metabolomics_feature_qc_pack(folder / "pack.json")

    def reference(self):
        return self.api.compute_feature_qc(self.table, self.sheet, self.rules)

    def sync(self, folder):
        result = self.reference()
        self.pack["rules"] = self.write(folder, "applied.json", self.rules)
        self.pack["sheet"] = self.write(folder, "sheet.json", self.sheet)
        self.pack["frozen_sheet_sha256"] = self.pack["sheet"]["sha256"]
        self.pack["table"] = self.write(folder, "table.json", self.table)
        self.report["rules_sha256"] = self.pack["rules"]["sha256"]
        self.report["features"] = [{k: row[k] for k in ("id", "status", "retained", "reasons")} for row in result["features"]]
        self.report["samples"] = [{k: row[k] for k in ("id", "flags")} for row in result["samples"]]
        self.report["batch_confounded"] = result["batch_confounded"]
        self.pack["report"] = self.write(folder, "report.json", self.report)
        # The evidence source follows the changed bytes, without claiming independence.
        evidence = self.read("evidence.json")
        evidence["records"][0]["source"] = self.pack["table"]
        self.pack["evidence"] = [self.write(folder, "evidence.json", evidence)]
        return result


class MetabReferenceTests(_Fixture):
    def test_fixture_expected_and_hand_calculations(self):
        result = self.api.validate_metabolomics_feature_qc_pack(FIXTURE / "pack.json")
        self.assertEqual(self.read("expected.json"), result)
        self.assertEqual(result, self.api.validate_metabolomics_feature_qc_pack(FIXTURE / "pack.json"))
        self.assertEqual("unavailable", result["review"])
        self.assertEqual("offline-arithmetic-only", result["status"])
        calculation = result["computation"]
        rows = {row["id"]: row for row in calculation["features"]}
        good = rows["GOOD"]
        self.assertEqual(1, calculation["retained_feature_count"])
        self.assertEqual(["GOOD"], [row["id"] for row in rows.values() if row["retained"]])
        self.assertAlmostEqual(1 / 20, good["blank_ratio"])
        self.assertAlmostEqual(10 / 20, good["qc_rsd_before"])
        self.assertEqual(0, good["qc_rsd_after"])
        self.assertAlmostEqual(1, good["dilution"]["r_squared"])
        self.assertAlmostEqual(10, good["dilution"]["slope"])
        self.assertEqual([20, 1, 10, 10, 20, 20, 20, 20, 20, 1, 30, 22], good["corrected"])
        self.assertAlmostEqual(1.25, rows["BLANK"]["blank_ratio"])
        self.assertEqual(0.5, rows["MISSING"]["study_missingness"])
        self.assertAlmostEqual(1 / 3, rows["MISSING"]["qc_missingness"])
        self.assertIsNone(rows["MISSING"]["corrected"][0])
        self.assertEqual("unavailable", rows["UNMEASURED"]["status"])
        self.assertIsNone(rows["UNMEASURED"]["dilution"])
        samples = {row["id"]: row for row in calculation["samples"]}
        self.assertAlmostEqual(abs(math.log(23) - math.log(21)), samples["S12"]["qc_log_distance"])
        self.assertEqual(["qc-distance-outlier"], samples["S12"]["flags"])
        self.assertEqual(12, len(samples))
        self.assertEqual(dict(sorted(Counter(reason for row in rows.values() for reason in row["reasons"]).items())),
                         calculation["reason_counts"])

    def test_reference_math_and_degenerate_inputs(self):
        self.assertAlmostEqual(.5, self.api.relative_standard_deviation([10, 20, 30]))
        self.assertEqual(0, self.api.relative_standard_deviation([20, 20, 20]))
        self.assertAlmostEqual(.5, self.api.relative_standard_deviation([1e-160, 2e-160, 3e-160]))
        line = self.api.dilution_linearity([1, 2, 3], [10, 20, 30])
        self.assertAlmostEqual(1, line["r_squared"])
        self.assertAlmostEqual(10, line["slope"])
        self.assertLess(self.api.dilution_linearity([1, 2, 3], [30, 20, 10])["slope"], 0)
        for values in ([], [1], [1, 2], [0, 0, 0]):
            with self.subTest(qc=values), self.assertRaisesRegex(ValueError, "^degenerate-qc:"):
                self.api.relative_standard_deviation(values)
        for xs, ys in (([], []), ([1, 2], [10, 20]), ([1, 1, 1], [1, 2, 3]),
                       ([1, 2, 3], [1, 1, 1]), ([1, 2, 3], [0, 0, 0])):
            with self.subTest(xs=xs, ys=ys), self.assertRaisesRegex(ValueError, "^[a-z-]+:"):
                self.api.dilution_linearity(xs, ys)
        for value in (True, -1, float('nan'), float('inf'), "3", []):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                self.api.relative_standard_deviation([1, 2, value])
        for minimum in (True, 3.0, "3", 0, 2):
            with self.subTest(minimum=minimum), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                self.api.dilution_linearity([1, 2, 3], [1, 2, 3], minimum)

    def test_exploratory_rules_normalization_and_confounding_flags(self):
        folder = self.folder()
        self.report["exploratory"] = True
        self.rules["normalization"] = "median"
        expected = self.sync(folder)
        result = self.run_pack(folder)
        self.assertEqual(expected, result["computation"])
        self.assertTrue(result["exploratory"])
        self.assertTrue(all(value > 0 for value in expected["normalization_factors"]))
        self.rules["normalization"] = "none"
        self.rules["drift"]["method"] = "none"
        expected = self.sync(folder)
        result = self.run_pack(folder)
        self.assertEqual(expected, result["computation"])
        self.assertEqual(0, expected["retained_feature_count"])
        self.assertTrue(all(row["qc_log_distance"] is None for row in expected["samples"]))
        for row in self.sheet["samples"]:
            if row["group"] == "B":
                row["batch"] = "B2"
        self.table["features"][-1]["unavailable_batches"].append("B2")
        self.sync(folder)
        self.assertTrue(self.run_pack(folder)["computation"]["batch_confounded"])

    def test_inclusive_feature_thresholds_and_empty_signals(self):
        self.rules["blank_ratio_max"] = .05
        self.rules["qc_rsd_max"] = 0
        self.rules["dilution_r2_min"] = 1
        self.rules["dilution_slope_min"] = 10
        self.assertTrue(self.reference()["features"][0]["retained"])
        self.rules["study_missing_max"] = .5
        self.rules["qc_missing_max"] = 1 / 3
        missing = self.reference()["features"][2]
        self.assertNotIn("study-missingness", missing["reasons"])
        self.assertNotIn("qc-missingness", missing["reasons"])
        self.rules["blank_ratio_max"] = 0
        self.assertIn("blank-ratio", self.reference()["features"][0]["reasons"])
        for row in self.table["features"]:
            row["values"] = [None] * len(self.table["sample_ids"])
        result = self.reference()
        self.assertEqual(0, result["retained_feature_count"])
        self.assertTrue(all(row["median_intensity"] is None for row in result["samples"]))
        self.rules["normalization"] = "median"
        with self.assertRaisesRegex(ValueError, "^normalization-unavailable:"):
            self.reference()

    def test_cli_success_argument_errors_and_seeded_refusals(self):
        def invoke(*args):
            return subprocess.run([sys.executable, str(CLI), *map(str, args)], capture_output=True,
                                  text=True, timeout=CALL_TIMEOUT)
        result = invoke(FIXTURE / "pack.json")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(self.read("expected.json"), json.loads(result.stdout))
        for args in ((), ("--unknown",), (FIXTURE / "pack.json", "extra"), ("--output", "fake.json")):
            with self.subTest(args=args):
                result = invoke(*args)
                self.assertEqual(2, result.returncode)
                self.assertEqual("", result.stdout)
                self.assertTrue(json.loads(result.stderr)["finding"].startswith("invalid-arguments:"))
                self.assertNotIn("Traceback", result.stderr)
        help_result = invoke("--help")
        self.assertEqual(0, help_result.returncode)
        self.assertIn("usage:", help_result.stdout)
        self.assertEqual("", help_result.stderr)
        cases = self.read("negative-cases.json")["cases"]
        self.assertEqual(set(CASES), {case["id"] for case in cases})
        for case in cases:
            with self.subTest(case=case["id"]):
                result = invoke(FIXTURE / case["path"])
                self.assertEqual(2, result.returncode)
                self.assertEqual("", result.stdout)
                self.assertTrue(json.loads(result.stderr)["finding"].startswith(case["finding"] + ":"))
                self.assertNotIn("Traceback", result.stderr)


class MetabSeededTests(_Fixture):
    pass


def _seeded_test(name):
    def test(self):
        case = next(row for row in self.read("negative-cases.json")["cases"] if row["id"] == name)
        with self.assertRaisesRegex(ValueError, "^" + case["finding"] + ":"):
            self.api.validate_metabolomics_feature_qc_pack(FIXTURE / case["path"])
    return test


for _case in CASES:
    setattr(MetabSeededTests, "test_" + _case.replace("-", "_"), _seeded_test(_case))


class MetabHardeningTests(_Fixture):
    def test_json_refusals_preparse_allowance_and_no_findall(self):
        invalid = (b'', b'{', b'[]', b'{"a":0,"a":1}', b'{"a":{"b":1,"b":2}}',
                   b'{"a":NaN}', b'{"a":Infinity}', b'{"a":1e999}', b'{"a":' + b'9' * 102 + b'}',
                   b'{"a":"\xff"}', b'{"a":"\\ud800"}', b'{"a":' + b'[' * 1100 + b'0' + b']' * 1100 + b'}')
        for raw in invalid:
            with self.subTest(raw=raw[:50]), self.assertRaisesRegex(ValueError, "^[a-z-]+:"):
                self.api._json(raw, self.api.MAX_TOTAL_NODES)
        raw = b'{"a":[0,1]}'
        for limit in (0, 3):
            with self.subTest(limit=limit), patch.object(self.api.json, "loads", side_effect=AssertionError("parsed too early")):
                with self.assertRaisesRegex(ValueError, "^input-limit:"):
                    self.api._json(raw, limit)
        with patch.object(self.api.re, "findall", side_effect=AssertionError("allocated matches")):
            self.assertEqual({"a": [0, 1]}, self.api._json(raw, 4)[0])
        with patch.object(self.api, "MAX_DEPTH", 0), self.assertRaisesRegex(ValueError, "^invalid-json:"):
            self.api._json(raw, 4)
        with patch.object(self.api, "MAX_ITEMS", 1), self.assertRaisesRegex(ValueError, "^input-limit:"):
            self.api._json(raw, 4)
        with patch.object(self.api, "MAX_STRING", 1), self.assertRaisesRegex(ValueError, "^input-limit:"):
            self.api._json(b'{"a":"xx"}', 3)
        self.assertEqual({"a": "x"}, self.api._json(b'{"a":"x"}', 3)[0])

    def test_budget_limits_and_hardlink_cache(self):
        folder = self.folder()
        raw = b'{"a":[0,1]}'
        (folder / "a.json").write_bytes(raw)
        (folder / "b.json").write_bytes(raw)
        os.link(folder / "a.json", folder / "alias.json")
        for limit in (0, len(raw) - 1, len(raw), 2 * len(raw)):
            with self.subTest(limit=limit), patch.object(self.api, "MAX_TOTAL_BYTES", limit):
                with self.api._Bundle(folder) as store:
                    if limit < len(raw):
                        with self.assertRaisesRegex(ValueError, "^input-limit:"):
                            store.load("a.json")
                    else:
                        with patch.object(self.api, "_json", wraps=self.api._json) as parsed:
                            store.load("a.json")
                            store.load("alias.json")
                            self.assertEqual(1, parsed.call_count)
                            self.assertEqual(len(raw), store.total_bytes)
                        if limit == 2 * len(raw):
                            store.load("b.json")
                        else:
                            with self.assertRaisesRegex(ValueError, "^input-limit:"):
                                store.load("b.json")
                        store.finish()
        for limit in (0, 3, 4, 8):
            with self.subTest(nodes=limit), patch.object(self.api, "MAX_TOTAL_NODES", limit):
                with self.api._Bundle(folder) as store:
                    if limit < 4:
                        with self.assertRaisesRegex(ValueError, "^input-limit:"):
                            store.load("a.json")
                    else:
                        store.load("a.json")
                        if limit == 8:
                            store.load("b.json")
                        else:
                            with self.assertRaisesRegex(ValueError, "^input-limit:"):
                                store.load("b.json")
        with patch.object(self.api, "MAX_ARTIFACTS", 1), self.api._Bundle(folder) as store:
            store.load("a.json")
            with self.assertRaisesRegex(ValueError, "^input-limit:"):
                store.load("alias.json")
        with patch.object(self.api, "MAX_BYTES", len(raw)), self.api._Bundle(folder) as store:
            store.load("a.json")
        with patch.object(self.api, "MAX_BYTES", len(raw) - 1), self.api._Bundle(folder) as store:
            with self.assertRaisesRegex(ValueError, "^input-file:"):
                store.load("a.json")

    def test_dimension_limits_and_integer_fields(self):
        for constant, limit in (("MAX_SAMPLES", 11), ("MAX_FEATURES", 4), ("MAX_CELLS", 59)):
            with self.subTest(constant=constant), patch.object(self.api, constant, limit):
                with self.assertRaisesRegex(ValueError, "^input-limit:"):
                    self.reference()
        with patch.object(self.api, "MAX_SAMPLES", 12), patch.object(self.api, "MAX_FEATURES", 5), patch.object(self.api, "MAX_CELLS", 60):
            self.assertEqual(1, self.reference()["retained_feature_count"])
        table = copy.deepcopy(self.table)
        table["features"] = [copy.deepcopy(self.table["features"][0]) for _ in range(self.api.MAX_FEATURES + 1)]
        with self.assertRaisesRegex(ValueError, "^input-limit:"):
            self.api.compute_feature_qc(table, self.sheet, self.rules)
        for field in ("minimum_qc", "minimum_dilution", "minimum_distance_features", "window", "injection_order"):
            for bad in (True, 3.0, "3", [], 0):
                with self.subTest(field=field, bad=bad):
                    rules, sheet = copy.deepcopy(self.rules), copy.deepcopy(self.sheet)
                    if field == "window":
                        rules["drift"][field] = bad
                    elif field == "injection_order":
                        sheet["samples"][0][field] = bad
                    else:
                        rules[field] = bad
                    with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                        self.api.compute_feature_qc(self.table, sheet, rules)
        for window in (2, self.api.MAX_WINDOW + 2):
            self.rules["drift"]["window"] = window
            with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                self.reference()
        self.rules["drift"]["window"] = self.api.MAX_WINDOW
        self.reference()
        for value in ([], 0, "x" * (self.api.MAX_STRING + 1)):
            with self.subTest(text=value), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                self.api._text(value, "text")

    def test_local_limits_empty_zero_equal_and_malformed(self):
        for limit in (0, 1):
            for values in ([], ["x"], ["x", "y"]):
                with self.subTest(limit=limit, values=values):
                    if len(values) > limit:
                        with self.assertRaisesRegex(ValueError, "^input-limit:"):
                            self.api._list(values, "items", limit, True)
                    else:
                        self.assertEqual(values, self.api._list(values, "items", limit, True))
        for values in (None, {}, 0, True, "x"):
            with self.subTest(values=values), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                self.api._list(values, "items", 1, True)
        with patch.object(self.api, "MAX_RECORDS", 0):
            self.api._claims([], {})
            with self.assertRaisesRegex(ValueError, "^input-limit:"):
                self.api._claims([{}], {})
        with patch.object(self.api, "MAX_NUMBER", 1):
            self.assertEqual(1, self.api._number(1, "value"))
            self.assertEqual(0, self.api._number(0, "value"))
            for value in (2, True, [], "1"):
                with self.subTest(value=value), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                    self.api._number(value, "value")
        for field in ("study_missing_max", "qc_missing_max", "dilution_r2_min"):
            for value in (0, 1):
                rules = copy.deepcopy(self.rules)
                rules[field] = value
                self.api._rules(rules)
            for value in (-1, 1.1, True, [], "0"):
                rules = copy.deepcopy(self.rules)
                rules[field] = value
                with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                    self.api._rules(rules)
        rules = copy.deepcopy(self.rules)
        rules["drift"]["anchors"] = "study"
        with self.assertRaisesRegex(ValueError, "^study-drift-anchors:"):
            self.api._rules(rules)
        self.rules["sample_outlier_distance"] = 0
        good = self.reference()
        qc = next(row for row in good["samples"] if row["id"] == "S01")
        self.assertEqual([], qc["flags"])
        distance = next(row for row in good["samples"] if row["id"] == "S12")["qc_log_distance"]
        self.rules["sample_outlier_distance"] = distance
        self.assertEqual([], next(row for row in self.reference()["samples"] if row["id"] == "S12")["flags"])

    def test_table_identity_controls_and_types(self):
        mutations = (
            lambda t, s: t['sample_ids'].__setitem__(0, 'unknown'),
            lambda t, s: s['samples'][1].update(injection_order=1),
            lambda t, s: t['features'][1].update(id='GOOD'),
            lambda t, s: t['features'][0].update(mz=49),
            lambda t, s: t['features'][0].update(retention_time=61),
            lambda t, s: t['features'][0]['values'].__setitem__(0, -1),
            lambda t, s: t['features'][0]['values'].__setitem__(0, True),
            lambda t, s: t['features'][0]['values'].pop(),
            lambda t, s: t['features'][0]['imputed'].__setitem__(0, 1),
            lambda t, s: t['features'][4]['values'].__setitem__(0, 0),
        )
        for mutate in mutations:
            table, sheet = copy.deepcopy(self.table), copy.deepcopy(self.sheet)
            mutate(table, sheet)
            with self.subTest(mutate=mutate), self.assertRaisesRegex(ValueError, "^[a-z-]+:"):
                self.api.compute_feature_qc(table, sheet, self.rules)
        for kind in ('pooled-qc', 'blank', 'dilution-series'):
            sheet = copy.deepcopy(self.sheet)
            for row in sheet['samples']:
                if row['sample_type'] == kind:
                    row.update(sample_type='study', group='A', dilution=None)
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "^missing-controls:"):
                self.api.compute_feature_qc(self.table, sheet, self.rules)

    def test_paths_special_files_and_open_flags(self):
        folder = self.folder()
        for name in ("../outside", "./rules.json", "nested//x", "a\\b", "C:bad", str(folder / 'rules.json'), "", "."):
            with self.subTest(name=name), self.api._Bundle(folder) as store:
                with self.assertRaisesRegex(ValueError, "^[a-z-]+:"):
                    store.load(name)
        (folder / 'link.json').symlink_to('rules.json')
        (folder / 'linked-dir').symlink_to(folder, target_is_directory=True)
        os.mkfifo(folder / 'pipe.json')
        (folder / 'directory.json').mkdir()
        with (folder / 'huge.json').open('wb') as handle:
            handle.truncate(self.api.MAX_BYTES + 1)
        for name in ('link.json', 'linked-dir/rules.json', 'pipe.json', 'directory.json', 'huge.json', 'absent.json'):
            with self.subTest(name=name), self.api._Bundle(folder) as store:
                with self.assertRaisesRegex(ValueError, '^input-file:'):
                    store.load(name)
        calls = []
        original = os.open
        def inspected(path, flags, *args, **kwargs):
            calls.append((path, flags, kwargs.get('dir_fd')))
            return original(path, flags, *args, **kwargs)
        with patch.object(self.api.os, 'open', side_effect=inspected):
            self.api.validate_metabolomics_feature_qc_pack(folder / 'pack.json')
        for name, flags, directory in calls:
            self.assertTrue(flags & os.O_NONBLOCK)
            self.assertTrue(flags & os.O_NOFOLLOW)
            if name == 'rules.json':
                self.assertIsNotNone(directory)

    def test_file_replacement_growth_and_hash_changes(self):
        folder = self.folder()
        with self.api._Bundle(folder) as store:
            store.load('rules.json')
            raw = (folder / 'rules.json').read_bytes()
            (folder / 'replacement.json').write_bytes(raw)
            os.replace(folder / 'replacement.json', folder / 'rules.json')
            with self.assertRaisesRegex(ValueError, '^input-changed:'):
                store.finish()
        original = os.fdopen
        def growing(descriptor, *args, **kwargs):
            handle = original(descriptor, *args, **kwargs)
            read = handle.read
            def read_and_grow(*a):
                value = read(*a)
                with (folder / 'rules.json').open('ab') as writer:
                    writer.write(b' ')
                return value
            handle.read = read_and_grow
            return handle
        with self.api._Bundle(folder) as store, patch.object(self.api.os, 'fdopen', side_effect=growing):
            with self.assertRaisesRegex(ValueError, '^input-file:'):
                store.load('rules.json')
        with self.api._Bundle(folder) as store:
            with self.assertRaisesRegex(ValueError, '^input-hash:'):
                store.load('rules.json', '0' * 64)

    def test_root_swap_at_open_and_transient_ancestor_symlink(self):
        for ancestor in (False, True):
            with self.subTest(ancestor=ancestor):
                folder = self.folder()
                target = folder.parent if ancestor else folder
                moved = target.with_name(target.name + '-saved')
                original = os.open
                changed = False
                def swapped(name, flags, *args, **kwargs):
                    nonlocal changed
                    if not changed and name == target.name:
                        changed = True
                        target.rename(moved)
                        target.symlink_to(moved, target_is_directory=True)
                        try:
                            return original(name, flags, *args, **kwargs)
                        finally:
                            target.unlink()
                            moved.rename(target)
                    return original(name, flags, *args, **kwargs)
                with patch.object(self.api.os, 'open', side_effect=swapped):
                    with self.assertRaisesRegex(ValueError, '^input-root:'):
                        self.api.validate_metabolomics_feature_qc_pack(folder / 'pack.json')
                self.assertTrue(changed)

    def test_ancestor_replacement_with_same_bundle_inode(self):
        folder = self.folder()
        original_inode = folder.stat().st_ino
        with self.api._Bundle(folder) as store:
            store.load('rules.json')
            parent = folder.parent
            moved = parent.with_name('old-parent')
            parent.rename(moved)
            parent.mkdir()
            (moved / folder.name).rename(folder)
            self.assertEqual(original_inode, folder.stat().st_ino)
            with self.assertRaisesRegex(ValueError, '^input-root:'):
                store.finish()

    def test_lstat_swap_and_descriptor_device_refusal(self):
        folder = self.folder()
        original = os.lstat
        changed = False
        def swapped(name, *args, **kwargs):
            nonlocal changed
            before = original(name, *args, **kwargs)
            if name == folder.name and not changed:
                changed = True
                saved = folder.with_name('saved')
                folder.rename(saved)
                folder.mkdir()
            return before
        with patch.object(self.api.os, 'lstat', side_effect=swapped):
            with self.assertRaisesRegex(ValueError, '^input-root:'):
                self.api.validate_metabolomics_feature_qc_pack(folder / 'pack.json')
        folder = self.folder()
        original_open = os.open
        def device(name, flags, *args, **kwargs):
            if name == 'rules.json':
                return original_open(os.devnull, flags)
            return original_open(name, flags, *args, **kwargs)
        with self.api._Bundle(folder) as store, patch.object(self.api.os, 'open', side_effect=device):
            with self.assertRaisesRegex(ValueError, '^input-file:'):
                store.load('rules.json')

    def test_claim_gate_wording_status_types_and_mixed_unavailable(self):
        evidence = {'E1': {'kind': 'observed', 'result': 'observed'},
                    'E2': {'kind': 'observed', 'result': 'unavailable'}}
        base = dict(id='C1', kind='descriptive', status='supported', text='Feature counts recorded.', evidence=['E1'])
        for status in self.api.STATUSES - {'unavailable'}:
            claim = dict(base, status=status, evidence=['E1', 'E2'])
            with self.subTest(status=status), self.assertRaisesRegex(ValueError, '^unavailable-evidence:'):
                self.api._claims([claim], evidence)
        for text in ('causal', 'mechanism', 'therapeutic', 'clinical', 'efficacy', 'effective', 'treatment', 'cure',
                     'prevention', 'recommend', 'prescription', 'binding', 'affinity', 'inhibition', 'activation',
                     'regulation', 'drive', 'drives', 'driving', 'induction', 'biomarker', 'pathway', 'identified',
                     'compound identity', 'physical validity', 'truth'):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, '^claim-overreach:'):
                self.api._claims([dict(base, text=text.upper())], evidence)
        for key in ('id', 'kind', 'status', 'text'):
            for value in ([], {}, 1, True, None):
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, '^invalid-record:'):
                    self.api._claims([dict(base, **{key: value})], evidence)
        for status in self.api.POSITIVE:
            for key in ('kind', 'result'):
                records = {'E1': {'kind': 'observed', 'result': 'observed'}}
                records['E1'][key] = 'review-approval'
                with self.subTest(status=status, key=key), self.assertRaisesRegex(ValueError, '^non-evidence-support:'):
                    self.api._claims([dict(base, status=status)], records)
        for text in ('Supported', 'replicated', 'suggestive', 'significant'):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, '^unavailable-positive:'):
                self.api._claims([dict(base, status='unavailable', text=text, evidence=[])], evidence)
        self.api._claims([dict(base, status='unavailable', evidence=['E1', 'E2'])], evidence)
        with self.assertRaisesRegex(ValueError, '^missing-evidence:'):
            self.api._claims([dict(base, evidence=['unknown'])], evidence)

    def test_external_alias_by_hash_and_read_only_concurrent_runs(self):
        folder = self.folder()
        evidence = self.read('evidence.json')
        shutil.copyfile(folder / 'table.json', folder / 'independent.json')
        evidence['records'][0].update(origin='external')
        evidence['records'][0]['source']['path'] = 'independent.json'
        self.pack['evidence'] = [self.write(folder, 'evidence.json', evidence)]
        with self.assertRaisesRegex(ValueError, '^external-alias:'):
            self.run_pack(folder)
        from concurrent.futures import ThreadPoolExecutor
        before = {p.name: p.read_bytes() for p in FIXTURE.iterdir() if p.is_file()}
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(self.api.validate_metabolomics_feature_qc_pack, [FIXTURE / 'pack.json'] * 2))
        self.assertEqual(results[0], results[1])
        self.assertEqual(before, {p.name: p.read_bytes() for p in FIXTURE.iterdir() if p.is_file()})


if __name__ == '__main__':
    unittest.main()
