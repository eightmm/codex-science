"""Synthetic fixture arithmetic, individual seeded refusals and hostile input checks."""
from __future__ import annotations

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
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from codex_science import pk_nca_pack as nca

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "workflow-pk-nca-profile"
CLI = ROOT / "scripts" / "validate_pk_nca_pack.py"
CALL_TIMEOUT = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "30"))
CASES = json.loads((FIXTURE / "negative-cases.json").read_bytes())["cases"]


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")


def identity(path):
    return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


class NcaTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name) / "fixture"
        shutil.copytree(FIXTURE, self.directory)

    def edit(self, target, path, value):
        file = self.directory / (target + ".json")
        document = read(file)
        owner = document
        for name in path[:-1]:
            owner = owner[name]
        owner[path[-1]] = value
        write(file, document)

    def refresh(self, freeze=True):
        report = read(self.directory / "report.json")
        report["rules_sha256"] = identity(self.directory / "rules.json")["sha256"]
        write(self.directory / "report.json", report)
        evidence = read(self.directory / "evidence.json")
        for record in evidence["records"]:
            record["source"]["sha256"] = hashlib.sha256((self.directory / record["source"]["path"]).read_bytes()).hexdigest()
        write(self.directory / "evidence.json", evidence)
        pack = read(self.directory / "pack.json")
        for field in ("rules", "profiles", "report", "evidence"):
            pack[field] = identity(self.directory / (field + ".json"))
        if freeze:
            pack["frozen_rules"] = pack["rules"]
        write(self.directory / "pack.json", pack)

    def validate(self):
        return nca.validate_pk_nca_pack(self.directory / "pack.json")

    def recompute(self):
        report = read(self.directory / "report.json")
        report["computation"] = nca.compute_nca(read(self.directory / "profiles.json"), read(self.directory / "rules.json"))
        write(self.directory / "report.json", report)
        self.refresh()

    def cli(self, *args):
        return subprocess.run([sys.executable, str(CLI), *map(str, args)], text=True,
                              capture_output=True, timeout=CALL_TIMEOUT)

    def test_fixture_hand_calculations_and_read_only_concurrency(self):
        before = {p.name: p.read_bytes() for p in self.directory.iterdir()}
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.validate(), range(2)))
        self.assertEqual(results[0], results[1])
        result = results[0]
        self.assertEqual(read(self.directory / "expected.json"), result)
        clean, censored, bad = result["computation"]["subjects"]
        self.assertEqual((16, 0), (clean["cmax"], clean["tmax"]))
        self.assertAlmostEqual(15 / math.log(2), clean["auc_0_tlast"])
        self.assertAlmostEqual(math.log(2), clean["lambda_z"])
        self.assertAlmostEqual(1, clean["half_life"])
        self.assertAlmostEqual(16 / math.log(2), clean["auc_0_inf"])
        self.assertAlmostEqual(1 / 16, clean["extrapolated_fraction"])
        self.assertAlmostEqual(1, clean["adjusted_r_squared"])
        self.assertEqual(clean["auc_0_inf"], censored["auc_0_inf"])
        self.assertEqual("unreliable", bad["auc_0_inf"])
        self.assertIn("terminal-fit", bad["reasons"])
        self.assertEqual(2, result["computation"]["group"]["n"])
        self.assertEqual("unavailable", result["review"])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.directory.iterdir()})

    def test_cli_success_and_refusal_are_json(self):
        good = self.cli(self.directory / "pack.json")
        self.assertEqual(0, good.returncode, good.stderr)
        self.assertEqual("arithmetic-only", json.loads(good.stdout)["status"])
        for args in [[], [self.directory / "missing.json"], [self.directory / "pack.json", "--output", "x"]]:
            with self.subTest(args=args):
                bad = self.cli(*args)
                self.assertEqual(2, bad.returncode)
                self.assertEqual("refused", json.loads(bad.stdout)["status"])
                self.assertNotIn("Traceback", bad.stderr)

    def test_censored_interior_substitution_and_linear_up(self):
        profiles = read(self.directory / "profiles.json")
        rules = read(self.directory / "rules.json")
        profiles["subjects"] = [profiles["subjects"][0]]
        profiles["subjects"][0]["points"][1].update(concentration=None, censored=True)
        with self.assertRaisesRegex(ValueError, "^censored-gap:"):
            nca.compute_nca(profiles, rules)
        rules.update(below_limit_rule="substitute", substitution=0)
        result = nca.compute_nca(profiles, rules)["subjects"][0]
        self.assertAlmostEqual(8 + 2 + 3 / math.log(2), result["auc_0_tlast"])
        self.assertEqual("observed", result["cmax_source"])
        self.assertIsNone(profiles["subjects"][0]["points"][1]["concentration"])
        for bad in (-1, 0.3, True, "0"):
            rules["substitution"] = bad
            with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                nca.compute_nca(profiles, rules)

    def test_terminal_and_fraction_threshold_edges(self):
        profiles = read(self.directory / "profiles.json")
        rules = read(self.directory / "rules.json")
        profiles["subjects"] = [profiles["subjects"][0]]
        result = nca.compute_nca(profiles, rules)
        rules["maximum_extrapolated_fraction"] = result["subjects"][0]["extrapolated_fraction"]
        rules["minimum_adjusted_r_squared"] = result["subjects"][0]["adjusted_r_squared"]
        self.assertEqual("reliable", nca.compute_nca(profiles, rules)["subjects"][0]["status"])
        rules["maximum_extrapolated_fraction"] = 0
        self.assertEqual(0, nca.compute_nca(profiles, rules)["group"]["n"])
        rules["maximum_extrapolated_fraction"] = 1
        rules["minimum_terminal_points"] = 4
        self.assertIn("terminal-points", nca.compute_nca(profiles, rules)["subjects"][0]["reasons"])
        rules["minimum_terminal_points"] = 3
        for values, reason in [([4, 4, 4], "terminal-degenerate"), ([1, 2, 4], "terminal-nondecreasing")]:
            for point, value in zip(profiles["subjects"][0]["points"][2:], values):
                point["concentration"] = value
            self.assertIn(reason, nca.compute_nca(profiles, rules)["subjects"][0]["reasons"])

    def test_missing_dose_field_and_all_integer_types(self):
        rules = read(self.directory / "rules.json")
        absent = copy.deepcopy(rules)
        del absent["nominal_dose"]
        with self.assertRaisesRegex(ValueError, "^dose-units:"):
            nca._rules(absent)
        for value in (True, 3.0, "3", 0, None):
            changed = dict(rules, minimum_terminal_points=value)
            with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                nca._rules(changed)
        for path in (["computation", "group", "n"], ["computation", "subjects", 0, "terminal_points"]):
            for value in (True, 2.0, "2"):
                self.edit("report", path, value)
                self.refresh()
                with self.assertRaisesRegex(ValueError, "^reported-value:"):
                    self.validate()
                shutil.copyfile(FIXTURE / "report.json", self.directory / "report.json")

    def test_exploratory_rules_keep_original_hash(self):
        shutil.copyfile(self.directory / "rules.json", self.directory / "original.json")
        pack = read(self.directory / "pack.json")
        pack["frozen_rules"] = identity(self.directory / "original.json")
        write(self.directory / "pack.json", pack)
        self.edit("rules", ["minimum_adjusted_r_squared"], 0.9)
        self.edit("report", ["exploratory"], True)
        self.refresh(False)
        self.assertTrue(self.validate()["exploratory"])

    def test_claim_wording_families_all_statuses(self):
        words = ["causal", "mechanism", "therapeutic", "clinical", "efficacy", "effective", "treatment",
                 "cure", "prevention", "recommendation", "prescription", "binding", "affinity", "inhibition",
                 "activation", "regulation", "drives", "induction", "bioavailability", "safe dose",
                 "human exposure", "exposure response", "physical validity", "truth"]
        for word in words:
            for status in ("unsupported", "supported", "unavailable"):
                claim = dict(id="c", kind="descriptive", status=status, text=word.upper(), evidence=["r"])
                with self.subTest(word=word, status=status):
                    with self.assertRaisesRegex(ValueError, "^claim-boundary:"):
                        nca._claims([claim], {"r": dict(kind="observed", result="observed")})
        for value in ([], {}, None, 1):
            claim = dict(id="c", kind="descriptive", status=value, text="Fixture record.", evidence=[])
            with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                nca._claims([claim], {})

    def test_unavailable_mixed_kind_or_result_and_no_evidence(self):
        for field in ("kind", "result"):
            for status in nca.STATUSES - {"unavailable"}:
                record = dict(kind="observed", result="observed")
                record[field] = "unavailable"
                claim = dict(id="c", kind="descriptive", status=status, text="Fixture record.", evidence=["a", "b"])
                with self.assertRaisesRegex(ValueError, "^unavailable-evidence:"):
                    nca._claims([claim], {"a": record, "b": dict(kind="observed", result="observed")})
        nca._claims([dict(id="c", kind="descriptive", status="unavailable", text="No record supplied.", evidence=[])], {})

    def test_dimension_limits_before_computation(self):
        rules = read(self.directory / "rules.json")
        profiles = read(self.directory / "profiles.json")
        for constant, limit in [("MAX_SUBJECTS", 2), ("MAX_POINTS", 4), ("MAX_ROWS", 14), ("MAX_RECORDS", 0)]:
            with self.subTest(constant=constant):
                with patch.object(nca, constant, limit):
                    with self.assertRaisesRegex(ValueError, "^input-limit:"):
                        self.validate()
        with patch.object(nca, "MAX_SUBJECTS", 3), patch.object(nca, "MAX_POINTS", 7), patch.object(nca, "MAX_ROWS", 17):
            self.validate()
        profiles["subjects"] = profiles["subjects"] * (nca.MAX_SUBJECTS // 3 + 1)
        with self.assertRaisesRegex(ValueError, "^input-limit:"):
            nca.compute_nca(profiles, rules)
        for value in ([], None, 0, "malformed"):
            with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                nca._list(value, "dimension", 1)
        self.assertEqual([0], nca._list([0], "dimension", 1))
        self.assertEqual([], nca._list([], "dimension", 0, True))
        with self.assertRaisesRegex(ValueError, "^input-limit:"):
            nca._list([0], "dimension", 0, True)

    def test_json_hostile_inputs_and_budget_edges(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":{"b":1,"b":2}}', b'{"a":NaN}', b'{"a":Infinity}',
                    b'{"a":1e999}', b'{"a":' + b'9' * 200 + b'}', b'[]', b'{', b'\xff',
                    b'{"a":' + b'[' * 2000 + b'0' + b']' * 2000 + b'}'):
            with self.subTest(raw=raw[:30]):
                with self.assertRaisesRegex(ValueError, "^invalid-json:"):
                    nca._json(raw, nca.MAX_JSON_VALUES)
        with patch.object(nca.re, "findall", side_effect=AssertionError("unbounded match list")):
            with self.assertRaisesRegex(ValueError, "^input-limit:"):
                nca._json(b'{"x":[[],[],[],[]]}', 1)
        for value, expected in [(b'{}', 1), (b'{"a":1}', 2)]:
            self.assertEqual(expected, nca._json(value, expected)[1])
            with self.assertRaisesRegex(ValueError, "^input-limit:"):
                nca._json(value, expected - 1)
        with patch.object(nca, "MAX_JSON_VALUES", 1):
            with self.assertRaisesRegex(ValueError, "^input-limit:"):
                self.validate()
        with patch.object(nca, "MAX_DEPTH", 0):
            with self.assertRaisesRegex(ValueError, "^invalid-json:"):
                nca._json(b'{"a":{}}', 10)
        with patch.object(nca, "MAX_STRING", 2):
            with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                nca._json(b'{"a":"long"}', 10)

    def test_file_path_and_hash_refusals(self):
        pack = self.directory / "pack.json"
        original = read(pack)
        for name in ("../rules.json", "/rules.json", "./rules.json", "a//b", "a\\b", "a/../b"):
            altered = copy.deepcopy(original)
            altered["rules"]["path"] = name
            write(pack, altered)
            with self.assertRaisesRegex(ValueError, "^input-path:"):
                self.validate()
        write(pack, original)
        self.edit("rules", ["route"], "changed fixture route")
        with self.assertRaisesRegex(ValueError, "^input-hash:"):
            self.validate()

    def test_fifo_directory_symlink_oversize_and_aggregate(self):
        file = self.directory / "rules.json"
        saved = file.read_bytes()
        for kind in ("fifo", "directory", "symlink", "oversize"):
            file.unlink()
            if kind == "fifo":
                os.mkfifo(file)
            elif kind == "directory":
                file.mkdir()
            elif kind == "symlink":
                file.symlink_to(self.directory / "profiles.json")
            else:
                with file.open("wb") as handle:
                    handle.truncate(nca.MAX_BYTES + 1)
            with self.assertRaisesRegex(ValueError, "^input-file:"):
                self.validate()
            if kind == "directory":
                file.rmdir()
                file.write_bytes(saved)
            else:
                file.unlink()
                file.write_bytes(saved)
        total = sum((self.directory / name).stat().st_size for name in ("pack.json", "rules.json", "profiles.json", "report.json", "evidence.json"))
        with patch.object(nca, "MAX_TOTAL_BYTES", total):
            self.validate()
        with patch.object(nca, "MAX_TOTAL_BYTES", total - 1):
            with self.assertRaisesRegex(ValueError, "^input-limit:"):
                self.validate()
        with patch.object(nca, "MAX_ARTIFACTS", 5):
            self.validate()
        with patch.object(nca, "MAX_ARTIFACTS", 4):
            with self.assertRaisesRegex(ValueError, "^input-limit:"):
                self.validate()
        largest = max((self.directory / name).stat().st_size for name in ("pack.json", "rules.json", "profiles.json", "report.json", "evidence.json"))
        with patch.object(nca, "MAX_BYTES", largest):
            self.validate()
        with patch.object(nca, "MAX_BYTES", largest - 1):
            with self.assertRaisesRegex(ValueError, "^input-file:"):
                self.validate()
        with patch.object(nca, "MAX_BYTES", 0):
            with self.assertRaisesRegex(ValueError, "^input-file:"):
                self.validate()

    def test_inode_cache_read_parse_once_and_hardlinks(self):
        os.link(self.directory / "rules.json", self.directory / "alias.json")
        reader = nca._Bundle(self.directory)
        self.addCleanup(reader.close)
        original = nca._json
        with patch.object(nca, "_json", wraps=original) as parser:
            a = reader.load("rules.json")
            b = reader.load("alias.json")
            self.assertIs(a, b)
            self.assertEqual(1, parser.call_count)
        self.assertEqual((self.directory / "rules.json").stat().st_size, reader.total_bytes)
        reader.finish()

    def test_input_replacement_at_finish_and_growth(self):
        original = nca._Bundle.finish
        def changed(reader):
            self.edit("rules", ["route"], "another fixture route")
            original(reader)
        with patch.object(nca._Bundle, "finish", changed):
            with self.assertRaisesRegex(ValueError, "^input-changed:"):
                self.validate()
        self.refresh()
        fdopen = nca.os.fdopen
        def growing(descriptor, *args, **kwargs):
            handle = fdopen(descriptor, *args, **kwargs)
            bounded_read = handle.read
            def read_more(limit):
                data = bounded_read(limit)
                with (self.directory / "pack.json").open("ab") as writer:
                    writer.write(b" ")
                return data
            handle.read = read_more
            return handle
        with patch.object(nca.os, "fdopen", growing):
            with self.assertRaisesRegex(ValueError, "^input-file:"):
                self.validate()

    def test_transient_ancestor_and_root_swap(self):
        original_open = nca.os.open
        for name in (self.directory.name, self.directory.parent.name):
            swapped = False
            target = self.directory if name == self.directory.name else self.directory.parent
            backup = target.with_name(target.name + "-moved")
            def swapping(path, flags, *args, **kwargs):
                nonlocal swapped
                if path == name and kwargs.get("dir_fd") is not None and not swapped:
                    swapped = True
                    target.rename(backup)
                    target.symlink_to(backup, target_is_directory=True)
                    try:
                        return original_open(path, flags, *args, **kwargs)
                    finally:
                        target.unlink()
                        backup.rename(target)
                return original_open(path, flags, *args, **kwargs)
            with self.subTest(component=name), patch.object(nca.os, "open", swapping):
                with self.assertRaisesRegex(ValueError, "^input-root:"):
                    self.validate()
            self.assertTrue(swapped)

    def test_root_replaced_by_real_directory_and_symlinked_artifact_component(self):
        original = nca._Bundle.finish
        moved = self.directory.with_name("old-fixture")
        def replace(reader):
            self.directory.rename(moved)
            self.directory.mkdir()
            try:
                original(reader)
            finally:
                self.directory.rmdir()
                moved.rename(self.directory)
        with patch.object(nca._Bundle, "finish", replace):
            with self.assertRaisesRegex(ValueError, "^input-root:"):
                self.validate()
        (self.directory / "linked").symlink_to(self.directory, target_is_directory=True)
        self.edit("pack", ["rules", "path"], "linked/rules.json")
        with self.assertRaisesRegex(ValueError, "^input-file:"):
            self.validate()

    def test_empty_zero_malformed_profiles_and_rules(self):
        profiles = read(self.directory / "profiles.json")
        rules = read(self.directory / "rules.json")
        for values in ([], None, 0, "bad"):
            changed = dict(profiles, subjects=values)
            with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                nca.compute_nca(changed, rules)
        for value in ([], [0, 0], [False], ["0"]):
            with self.assertRaisesRegex(ValueError, "^(invalid-record|sampling-schedule):"):
                nca.compute_nca(profiles, dict(rules, sampling_schedule=value))
        for field in ("maximum_extrapolated_fraction", "minimum_adjusted_r_squared"):
            for value in (-1, 1.1, True, "0", None):
                with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                    nca.compute_nca(profiles, dict(rules, **{field: value}))
        for concentration in (-1, True, "1", math.nan, math.inf):
            bad = copy.deepcopy(profiles)
            bad["subjects"][0]["points"][0]["concentration"] = concentration
            with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                nca.compute_nca(bad, rules)


    def test_zero_origin_and_cmax_ties(self):
        profiles = read(self.directory / "profiles.json")
        rules = read(self.directory / "rules.json")
        profiles["subjects"][0]["points"].pop(0)
        with self.assertRaisesRegex(ValueError, "^time-origin:"):
            nca.compute_nca(profiles, rules)
        profiles = read(self.directory / "profiles.json")
        profiles["subjects"][0]["points"][1]["concentration"] = 16
        self.assertEqual(0, nca.compute_nca(profiles, rules)["subjects"][0]["tmax"])
        for value in ([], None, "", "bad\x00path"):
            with self.assertRaisesRegex(ValueError, "^input-path:"):
                nca.validate_pk_nca_pack(value)

    def test_aggregate_json_allowance_and_limit_edges(self):
        files = ["pack.json", "rules.json", "profiles.json", "report.json", "evidence.json"]
        count = sum(nca._json((self.directory / name).read_bytes(), nca.MAX_JSON_VALUES)[1] for name in files)
        with patch.object(nca, "MAX_JSON_VALUES", count):
            self.validate()
        with patch.object(nca, "MAX_JSON_VALUES", count - 1):
            with self.assertRaisesRegex(ValueError, "^input-limit:"):
                self.validate()
        for constant in ("MAX_SUBJECTS", "MAX_POINTS", "MAX_ROWS", "MAX_ARTIFACTS", "MAX_JSON_VALUES", "MAX_TOTAL_BYTES"):
            with self.subTest(constant=constant), patch.object(nca, constant, 0):
                with self.assertRaisesRegex(ValueError, "^input-limit:"):
                    self.validate()
        with patch.object(nca, "MAX_ITEMS", 1):
            with self.assertRaisesRegex(ValueError, "^input-limit:"):
                nca._json(b'{"a":1,"b":2}', 10)
        with patch.object(nca, "MAX_STRING", 1):
            self.assertEqual("a", nca._text("a", "text"))
            with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                nca._text("aa", "text")
        self.assertEqual(0, nca._json(b'{}', 1)[0].get("absent", 0))

    def test_read_once_per_inode_plus_final_hash_recheck(self):
        original_fdopen = nca.os.fdopen
        reads = []
        def tracking(descriptor, *args, **kwargs):
            handle = original_fdopen(descriptor, *args, **kwargs)
            original_read = handle.read
            def bounded_read(limit):
                info = os.fstat(handle.fileno())
                reads.append((info.st_dev, info.st_ino))
                self.assertLessEqual(limit, nca.MAX_BYTES + 1)
                return original_read(limit)
            handle.read = bounded_read
            return handle
        with patch.object(nca.os, "fdopen", tracking):
            self.validate()
        self.assertEqual(5, len(set(reads)))
        self.assertTrue(all(reads.count(item) == 2 for item in set(reads)))

    def test_root_swap_during_lstat_is_refused(self):
        original_lstat = nca.os.lstat
        moved = self.directory.with_name("moved-root")
        swapped = False
        def swapping(path, *args, **kwargs):
            nonlocal swapped
            info = original_lstat(path, *args, **kwargs)
            if path == self.directory.name and kwargs.get("dir_fd") is not None and not swapped:
                swapped = True
                self.directory.rename(moved)
                self.directory.mkdir()
            return info
        try:
            with patch.object(nca.os, "lstat", swapping):
                with self.assertRaisesRegex(ValueError, "^input-root:"):
                    self.validate()
        finally:
            if swapped:
                self.directory.rmdir()
                moved.rename(self.directory)
        self.assertTrue(swapped)

    def test_boundary_and_unavailable_precede_later_output_checks(self):
        self.edit("report", ["claims", 0, "text"], "Clinical relevance is established.")
        self.edit("report", ["computation", "group", "n"], 999)
        self.refresh()
        with self.assertRaisesRegex(ValueError, "^claim-boundary:"):
            self.validate()
        self.edit("report", ["claims", 0, "text"], "Missing fixture record.")
        self.edit("evidence", ["records", 0, "result"], "unavailable")
        self.refresh()
        with self.assertRaisesRegex(ValueError, "^unavailable-evidence:"):
            self.validate()

    def test_numerically_extreme_positive_decrease_and_close_values(self):
        profiles = read(self.directory / "profiles.json")
        rules = read(self.directory / "rules.json")
        rules["lloq"] = 0
        profiles["subjects"] = [profiles["subjects"][0]]
        profiles["subjects"][0]["points"][1]["concentration"] = 1e-310
        result = nca.compute_nca(profiles, rules)
        self.assertTrue(math.isfinite(result["subjects"][0]["auc_0_tlast"]))
        profiles["subjects"][0]["points"][1]["concentration"] = math.nextafter(16, 0)
        result = nca.compute_nca(profiles, rules)
        self.assertTrue(math.isfinite(result["subjects"][0]["auc_0_tlast"]))


def _negative_test(case):
    def test(self):
        if case["name"] == "changed-rules":
            shutil.copyfile(self.directory / "rules.json", self.directory / "original.json")
            pack = read(self.directory / "pack.json")
            pack["frozen_rules"] = identity(self.directory / "original.json")
            write(self.directory / "pack.json", pack)
        for change in case["changes"]:
            self.edit(change["target"], change["path"], change["value"])
        self.refresh(case["name"] != "changed-rules")
        with self.assertRaisesRegex(ValueError, "^" + case["code"] + ":"):
            self.validate()
        result = self.cli(self.directory / "pack.json")
        self.assertEqual(2, result.returncode)
        self.assertTrue(json.loads(result.stdout)["error"].startswith(case["code"] + ":"))
        self.assertNotIn("Traceback", result.stderr)
    return test


for _case in CASES:
    setattr(NcaTests, "test_seed_" + _case["name"].replace("-", "_"), _negative_test(_case))


if __name__ == "__main__":
    unittest.main()
