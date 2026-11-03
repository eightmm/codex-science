"""Offline synthetic fixtures; no assay, patient or clinical efficacy assertions."""
import copy
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from codex_science import calibration_lod_pack as cal


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/workflow-calibration-lod"
CLI = ROOT / "scripts/validate_calibration_lod_pack.py"
CALL_TIMEOUT = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "60"))
CASES = json.loads((FIXTURE / "negative-cases.json").read_text())["cases"]


class CalibrationPackTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.parent = Path(self.temporary.name) / "parent"
        self.root = self.parent / "bundle"
        shutil.copytree(FIXTURE, self.root)
        self.pack_path = self.root / "pack.json"

    def read(self, name):
        return json.loads((self.root / name).read_text())

    def write(self, name, value):
        raw = (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode()
        (self.root / name).write_bytes(raw)
        return {"path": name, "sha256": hashlib.sha256(raw).hexdigest()}

    def change(self, slot, mutate):
        pack = self.read("pack.json")
        value = self.read(pack["inputs"][slot]["path"])
        mutate(value)
        pack["inputs"][slot] = self.write(f"{slot}.json", value)
        if slot == "protocol":
            pack["frozen_protocol_sha256"] = pack["inputs"][slot]["sha256"]
        self.write("pack.json", pack)

    def computation(self):
        return cal.reference_computation(self.read("protocol.json"), self.read("data.json"))

    def cli(self, *args):
        return subprocess.run([sys.executable, str(CLI), *map(str, args)],
                              capture_output=True, text=True, timeout=CALL_TIMEOUT, cwd=ROOT)

    def test_reference_hand_calculations(self):
        result = cal.validate_calibration_lod_pack(self.pack_path)
        values = result["calculation"]
        initial = values["initial_fit"]
        self.assertAlmostEqual(initial["slope"], 32 / 15)
        self.assertAlmostEqual(initial["intercept"], 1)
        self.assertAlmostEqual(initial["r_squared"], 128 / 155)
        self.assertAlmostEqual(initial["residual_standard_error"], 1.2)
        self.assertAlmostEqual(initial["back_calculated"][8]["percent_deviation"], 56.25)
        self.assertEqual(values["excluded_ids"], ["S3-3"])
        self.assertEqual(values["fit"]["slope"], 2)
        self.assertEqual(values["fit"]["intercept"], 1)
        self.assertEqual(values["fit"]["n"], 11)
        self.assertEqual(values["fit"]["df"], 9)
        self.assertEqual(values["fit"]["r_squared"], 1)
        self.assertEqual(values["fit"]["residual_standard_error"], 0)
        self.assertAlmostEqual(values["limits"]["blank_sd"], 0.4)
        self.assertAlmostEqual(values["limits"]["lod"], 0.66)
        self.assertAlmostEqual(values["limits"]["loq"], 2)
        self.assertEqual(values["unknowns"], [{"id": "U-in", "status": "in-range", "concentration": 2.5},
                                             {"id": "U-out", "status": "out-of-range", "concentration": None}])
        self.assertEqual(values, self.read("expected.json")["calculation"])
        self.assertEqual(result["review"], "unavailable")
        self.assertEqual(result["evidence_level"], "synthetic-arithmetic-only")

    def test_weighted_fits_and_frozen_zero_match_rational_normal_equations(self):
        protocol, data = self.read("protocol.json"), self.read("data.json")
        protocol.update(model="weighted-linear", exclusion_rule="none")
        for weighting, power in (("1/x", 1), ("1/x^2", 2)):
            for intercept in ("free", "zero"):
                with self.subTest(weighting=weighting, intercept=intercept):
                    protocol.update(weighting=weighting, intercept=intercept)
                    pairs = [(Fraction(r["concentration"]), Fraction(r["response"])) for r in data["standards"]]
                    weights = [1 / x ** power for x, _ in pairs]
                    s = sum(weights)
                    sx = sum(w*x for w, (x, _) in zip(weights, pairs))
                    sy = sum(w*y for w, (_, y) in zip(weights, pairs))
                    sxx = sum(w*x*x for w, (x, _) in zip(weights, pairs))
                    sxy = sum(w*x*y for w, (x, y) in zip(weights, pairs))
                    slope = (s*sxy-sx*sy)/(s*sxx-sx*sx) if intercept == "free" else sxy/sxx
                    offset = (sy-slope*sx)/s if intercept == "free" else 0
                    result = cal.reference_computation(protocol, data)["fit"]
                    self.assertAlmostEqual(result["slope"], float(slope))
                    self.assertAlmostEqual(result["intercept"], float(offset))

    def test_blank_mean_rule_and_minimum_blank_edge(self):
        protocol, data = self.read("protocol.json"), self.read("data.json")
        protocol["limit_rule"]["method"] = "blank-mean"
        for row in data["blanks"]:
            row["response"] += 1
        result = cal.reference_computation(protocol, data)
        self.assertAlmostEqual(result["limits"]["lod"], 1.16)
        self.assertAlmostEqual(result["limits"]["loq"], 2.5)
        for blanks in ([], data["blanks"][:2]):
            bad = copy.deepcopy(data)
            bad["blanks"] = blanks
            with self.assertRaisesRegex(ValueError, "^insufficient-blanks:"):
                cal.reference_computation(protocol, bad)

    def test_unknown_edges_and_no_silent_extrapolation(self):
        protocol, data = self.read("protocol.json"), self.read("data.json")
        template = data["unknowns"][0]
        responses = (0, 2.999, 3, 5, 9, 9.001)
        data["unknowns"] = [dict(template, id=f"U{n}", response=y) for n, y in enumerate(responses)]
        rows = cal.reference_computation(protocol, data)["unknowns"]
        self.assertEqual([r["status"] for r in rows],
                         ["out-of-range", "out-of-range", "below-loq", "in-range", "in-range", "out-of-range"])
        for row in (rows[0], rows[1], rows[-1]):
            self.assertIsNone(row["concentration"])
        data["unknowns"] = []
        self.assertEqual(cal.reference_computation(protocol, data)["unknowns"], [])

    def test_failed_controls_retained_without_exclusion_or_unknown_quantification(self):
        protocol, data = self.read("protocol.json"), self.read("data.json")
        protocol["exclusion_rule"] = "none"
        result = cal.reference_computation(protocol, data)
        self.assertEqual(result["acceptance"], "failed")
        self.assertEqual(result["excluded_ids"], [])
        self.assertEqual(result["initial_fit"], result["fit"])
        self.assertTrue(result["fit"]["back_calculated"][8]["failed"])
        self.assertEqual(result["unknowns"][0]["status"], "unavailable")

    def test_minimum_level_replicate_and_exclusion_edges(self):
        protocol, data = self.read("protocol.json"), self.read("data.json")
        data["standards"] = [r for r in data["standards"] if r["concentration"] in (1, 2, 4) and not r["id"].endswith("3")]
        result = cal.reference_computation(protocol, data)
        self.assertEqual(len(result["levels"]), 3)
        self.assertTrue(all(r["n_retained"] == 2 for r in result["levels"]))
        for rows in ([], data["standards"][:4], data["standards"][:-1]):
            bad = copy.deepcopy(data)
            bad["standards"] = rows
            with self.assertRaisesRegex(ValueError, "^(invalid-record|insufficient-standards):"):
                cal.reference_computation(protocol, bad)
        protocol["min_replicates"] = 3
        with self.assertRaisesRegex(ValueError, "^insufficient-standards:"):
            cal.reference_computation(protocol, self.read("data.json"))

    def test_report_counts_are_real_integers(self):
        base = self.read("report.json")
        for mutate in (
            lambda o: o["calculation"]["fit"].update(n=11.0),
            lambda o: o["calculation"]["fit"].update(df=True),
            lambda o: o["calculation"]["initial_fit"].update(n="12"),
            lambda o: o["calculation"]["levels"][0].update(n_initial=3.0),
            lambda o: o["calculation"]["levels"][0].update(n_retained=True),
            lambda o: o["calculation"]["limits"].update(blank_n=3.0),
        ):
            value = copy.deepcopy(base)
            mutate(value)
            with self.assertRaisesRegex(ValueError, "^report-mismatch:"):
                cal._report(value, self.read("protocol.json"), self.computation())

    def test_all_input_integer_fields_are_strict(self):
        for field in ("schema_version", "min_levels", "min_replicates"):
            for value in (True, 3.0, "3", 0, -1):
                with self.subTest(field=field, value=value):
                    protocol = self.read("protocol.json")
                    protocol[field] = value
                    with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                        cal.reference_computation(protocol, self.read("data.json"))
        for value in (True, 3.0, "3", 0):
            protocol = self.read("protocol.json")
            protocol["limit_rule"]["min_blanks"] = value
            with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                cal.reference_computation(protocol, self.read("data.json"))
        for name in ("pack.json", "data.json", "report.json", "evidence.json"):
            obj = self.read(name)
            obj["schema_version"] = 1.0
            self.write(name, obj)
            if name == "pack.json":
                with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                    cal.validate_calibration_lod_pack(self.pack_path)
                obj["schema_version"] = 1
                self.write(name, obj)
            else:
                with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                    cal._record(obj, obj["schema"], " ".join(k for k in obj if k not in {"schema", "schema_version", "fixture"}))

    def test_bad_types_never_leak_type_or_key_errors(self):
        for field in ("status", "kind", "id", "text"):
            pack = self.read("pack.json")
            pack["claims"][0][field] = []
            self.write("pack.json", pack)
            with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                cal.validate_calibration_lod_pack(self.pack_path)
            shutil.copyfile(FIXTURE / "pack.json", self.pack_path)
        for slot, key in (("protocol", "model"), ("protocol", "weighting"), ("protocol", "intercept"),
                          ("data", "standards"), ("report", "calculation")):
            self.change(slot, lambda o, k=key: o.update({k: [] if k != "standards" else False}))
            with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                cal.validate_calibration_lod_pack(self.pack_path)
            shutil.copyfile(FIXTURE / f"{slot}.json", self.root / f"{slot}.json")
            shutil.copyfile(FIXTURE / "pack.json", self.pack_path)

    def test_json_duplicate_nonfinite_huge_deep_and_root_refusals(self):
        invalid = (b'{"a":1,"a":2}', b'{"a":{"b":1,"b":2}}', b'[]', b'true', b'{',
                   b'{"a":NaN}', b'{"a":Infinity}', b'{"a":1e9999}',
                   b'{"a":' + b'9'*102 + b'}', b'\xff',
                   b'{"a":' + b'['*1000 + b'0' + b']'*1000 + b'}')
        for raw in invalid:
            with self.subTest(raw=raw[:35]):
                self.pack_path.write_bytes(raw)
                with self.assertRaisesRegex(ValueError, "^(invalid-json|invalid-record):"):
                    cal.validate_calibration_lod_pack(self.pack_path)

    def test_json_limits_precede_parser_and_do_not_allocate_match_list(self):
        raw = b'{"a":[1,2]}'
        estimate = 1 + raw.count(b",") + sum(1 for _ in re.finditer(rb"[\[{](?=\s*[^\s\]}])", raw))
        with patch.object(cal.re, "findall", side_effect=AssertionError("match list allocated")):
            self.assertEqual(cal._json(raw, estimate)[0], {"a": [1, 2]})
        for budget in (0, estimate-1):
            with patch.object(cal.json, "loads", side_effect=AssertionError("parser called")):
                with self.assertRaisesRegex(ValueError, "^input-limit:"):
                    cal._json(raw, budget)
        with patch.object(cal, "MAX_DEPTH", 1):
            with self.assertRaisesRegex(ValueError, "^invalid-json:"):
                cal._json(raw, estimate)
        with patch.object(cal, "MAX_ITEMS", 1):
            with self.assertRaisesRegex(ValueError, "^input-limit:"):
                cal._json(raw, estimate)
        with patch.object(cal, "MAX_TEXT", 1):
            with self.assertRaisesRegex(ValueError, "^input-limit:"):
                cal._json(b'{"a":"xx"}', 10)

    def test_row_and_claim_budgets_before_per_item_work(self):
        with patch.object(cal, "MAX_ROWS", 12):
            self.computation()
        with patch.object(cal, "MAX_ROWS", 11), patch.object(cal, "_counts", side_effect=AssertionError("work before bound")):
            with self.assertRaisesRegex(ValueError, "^input-limit:"):
                self.computation()
        deterministic = self.read("data.json")
        deterministic["unknowns"] = [dict(deterministic["unknowns"][0], id=f"U{i}") for i in range(cal.MAX_ROWS+1)]
        with self.assertRaisesRegex(ValueError, "^input-limit:"):
            cal.reference_computation(self.read("protocol.json"), deterministic)
        with patch.object(cal, "MAX_CLAIMS", 0):
            with self.assertRaisesRegex(ValueError, "^input-limit:"):
                cal.validate_calibration_lod_pack(self.pack_path)
        with patch.object(cal, "MAX_SUPPORT", 0):
            with self.assertRaisesRegex(ValueError, "^input-limit:"):
                cal.validate_calibration_lod_pack(self.pack_path)
        for field in ("unknowns", "blanks"):
            value = self.read("data.json")
            value[field] = False
            with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                cal.reference_computation(self.read("protocol.json"), value)

    def test_small_limit_equality_zero_and_malformed_edges(self):
        with patch.object(cal, "MAX_CLAIMS", 1), patch.object(cal, "MAX_SUPPORT", 1):
            cal.validate_calibration_lod_pack(self.pack_path)
        raw = b'{"a":[1,2]}'
        with patch.object(cal, "MAX_ITEMS", 2), patch.object(cal, "MAX_DEPTH", 2):
            cal._json(raw, 10)
        with patch.object(cal, "MAX_ITEMS", 0):
            self.assertEqual(cal._json(b'{}', 1)[0], {})
            with self.assertRaisesRegex(ValueError, "^input-limit:"):
                cal._json(b'{"a":1}', 10)
        with patch.object(cal, "MAX_DEPTH", 0):
            cal._json(b'{}', 1)
            with self.assertRaisesRegex(ValueError, "^invalid-json:"):
                cal._json(b'{"a":1}', 10)
        with patch.object(cal, "MAX_TEXT", 1):
            cal._json(b'{"a":"b"}', 10)
        with patch.object(cal, "MAX_NUMBER", 4):
            for value in (-4, 0, 4):
                self.assertEqual(cal._number(value, "edge"), value)
            for value in (-5, 5, True, "4", float("nan"), float("inf")):
                with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                    cal._number(value, "edge")
        with patch.object(cal, "MAX_NUMBER", 0):
            self.assertEqual(cal._number(0, "zero"), 0)
            with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                cal._number(1, "zero")

    def test_hardlink_aliases_share_parse_and_aggregate_budgets(self):
        os.link(self.root / "evidence.json", self.root / "alias.json")
        pack = self.read("pack.json")
        pack["study_outputs"].append(dict(pack["study_outputs"][0], path="alias.json"))
        self.write("pack.json", pack)
        names = ("pack.json", "protocol.json", "data.json", "report.json", "evidence.json")
        raw_values = [(self.root / n).read_bytes() for n in names]
        byte_count = sum(map(len, raw_values))
        value_count = sum(cal._json(raw, cal.MAX_JSON_VALUES)[1] for raw in raw_values)
        with patch.object(cal, "_json", wraps=cal._json) as parse:
            with patch.object(cal, "MAX_TOTAL_BYTES", byte_count), patch.object(cal, "MAX_JSON_VALUES", value_count), patch.object(cal, "MAX_ARTIFACTS", 6):
                cal.validate_calibration_lod_pack(self.pack_path)
            self.assertEqual(parse.call_count, 5)
        for name, value in (("MAX_TOTAL_BYTES", byte_count-1), ("MAX_TOTAL_BYTES", 0),
                            ("MAX_JSON_VALUES", value_count-1), ("MAX_JSON_VALUES", 0),
                            ("MAX_ARTIFACTS", 5), ("MAX_ARTIFACTS", 0)):
            with self.subTest(limit=name, value=value), patch.object(cal, name, value):
                with self.assertRaisesRegex(ValueError, "^input-limit:"):
                    cal.validate_calibration_lod_pack(self.pack_path)

    def test_regular_file_size_path_hash_and_link_refusals(self):
        for bad in ("../protocol.json", "/protocol.json", "./protocol.json", "x//y", "x\\y", "C:/fixture.json"):
            pack = self.read("pack.json")
            pack["inputs"]["protocol"]["path"] = bad
            self.write("pack.json", pack)
            with self.assertRaisesRegex(ValueError, "^input-path:"):
                cal.validate_calibration_lod_pack(self.pack_path)
            shutil.copyfile(FIXTURE / "pack.json", self.pack_path)
        pack = self.read("pack.json")
        pack["inputs"]["protocol"]["sha256"] = "0"*64
        self.write("pack.json", pack)
        with self.assertRaisesRegex(ValueError, "^input-hash:"):
            cal.validate_calibration_lod_pack(self.pack_path)
        for kind in ("fifo", "directory", "symlink", "oversize"):
            path = self.root / kind
            if kind == "fifo":
                os.mkfifo(path)
            elif kind == "directory":
                path.mkdir()
            elif kind == "symlink":
                path.symlink_to("protocol.json")
            else:
                with path.open("wb") as handle:
                    handle.truncate(cal.MAX_BYTES+1)
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "^input-file:"):
                cal.validate_calibration_lod_pack(path)
        shutil.copyfile(FIXTURE / "pack.json", self.pack_path)
        maximum = max((self.root / n).stat().st_size for n in ("pack.json", "protocol.json", "data.json", "report.json", "evidence.json"))
        with patch.object(cal, "MAX_BYTES", maximum):
            cal.validate_calibration_lod_pack(self.pack_path)
        with patch.object(cal, "MAX_BYTES", maximum-1):
            with self.assertRaisesRegex(ValueError, "^input-file:"):
                cal.validate_calibration_lod_pack(self.pack_path)

    def test_artifact_symlink_component_refused(self):
        (self.root / "linked").symlink_to(self.root, target_is_directory=True)
        pack = self.read("pack.json")
        pack["inputs"]["protocol"]["path"] = "linked/protocol.json"
        self.write("pack.json", pack)
        with self.assertRaisesRegex(ValueError, "^input-file:"):
            cal.validate_calibration_lod_pack(self.pack_path)

    def test_growing_file_refused(self):
        original = os.fstat
        touched = False
        def fstat(descriptor):
            nonlocal touched
            info = original(descriptor)
            if not touched and info.st_ino == self.pack_path.stat().st_ino:
                touched = True
                with self.pack_path.open("ab") as handle:
                    handle.write(b" ")
            return info
        with patch.object(cal.os, "fstat", side_effect=fstat):
            with self.assertRaisesRegex(ValueError, "^input-changed:"):
                cal.validate_calibration_lod_pack(self.pack_path)

    def test_input_replacement_at_final_hash_check_refused(self):
        original = cal._Bundle.recheck
        def recheck(bundle):
            self.write("data.json", self.read("data.json"))
            return original(bundle)
        with patch.object(cal._Bundle, "recheck", recheck):
            with self.assertRaisesRegex(ValueError, "^input-changed:"):
                cal.validate_calibration_lod_pack(self.pack_path)

    def test_root_swap_at_open_refused(self):
        original = os.open
        swapped = False
        def opening(name, flags, **kwargs):
            nonlocal swapped
            if not swapped and name == "bundle" and flags & os.O_DIRECTORY:
                swapped = True
                old = self.parent / "old"
                self.root.rename(old)
                self.root.symlink_to(old, target_is_directory=True)
            return original(name, flags, **kwargs)
        with patch.object(cal.os, "open", side_effect=opening):
            with self.assertRaisesRegex(ValueError, "^input-file:"):
                cal.validate_calibration_lod_pack(self.pack_path)
        self.assertTrue(swapped)

    def test_transient_ancestor_swap_at_lstat_refused(self):
        original = os.lstat
        swapped = False
        def lstat(name, **kwargs):
            nonlocal swapped
            info = original(name, **kwargs)
            if not swapped and name == "parent":
                swapped = True
                old = self.parent.with_name("old-parent")
                self.parent.rename(old)
                self.parent.symlink_to(old, target_is_directory=True)
            return info
        with patch.object(cal.os, "lstat", side_effect=lstat):
            with self.assertRaisesRegex(ValueError, "^input-file:"):
                cal.validate_calibration_lod_pack(self.pack_path)
        self.assertTrue(swapped)

    def test_changed_parent_with_same_bundle_inode_refused(self):
        original = cal._claims
        def claims(*args):
            result = original(*args)
            old = self.parent.with_name("old-parent")
            self.parent.rename(old)
            self.parent.mkdir()
            (old / "bundle").rename(self.root)
            return result
        with patch.object(cal, "_claims", side_effect=claims):
            with self.assertRaisesRegex(ValueError, "^input-changed:.*ancestor chain"):
                cal.validate_calibration_lod_pack(self.pack_path)

    def test_claim_families_and_absence_are_not_positive_evidence(self):
        words = ("causes", "mechanism", "therapy", "clinical", "efficacy", "effective", "treatment", "cure", "prevent", "recommend", "prescribe", "binding", "affinity", "inhibition", "activation", "regulatory", "drive", "drives", "induced")
        base = self.read("pack.json")
        for word in words:
            pack = copy.deepcopy(base)
            pack["claims"][0]["text"] = word.upper()
            self.write("pack.json", pack)
            with self.subTest(word=word), self.assertRaisesRegex(ValueError, "^claim-boundary:"):
                cal.validate_calibration_lod_pack(self.pack_path)
        for status in cal.STATUSES - {"unavailable"}:
            pack = copy.deepcopy(base)
            pack["claims"][0].update(status=status, text="Observed fixture response.")
            missing = self.write("missing.json", dict(self.read("evidence.json"), kind="unavailable", result="missing"))
            pack["claims"][0]["support"].append(dict(missing, origin="study"))
            self.write("pack.json", pack)
            with self.subTest(status=status), self.assertRaisesRegex(ValueError, "^unavailable-evidence:"):
                cal.validate_calibration_lod_pack(self.pack_path)

    def test_threshold_equality_and_loq_at_standard_edges(self):
        protocol, data = self.read("protocol.json"), self.read("data.json")
        protocol["exclusion_rule"] = "none"
        protocol["acceptance"].update(percent_deviation=56.25, lowest_percent_deviation=60)
        self.assertFalse(cal.reference_computation(protocol, data)["initial_fit"]["back_calculated"][8]["failed"])
        protocol["acceptance"]["percent_deviation"] = 56.249
        self.assertTrue(cal.reference_computation(protocol, data)["initial_fit"]["back_calculated"][8]["failed"])
        for sd in (0.2, 0.8):
            protocol, data = self.read("protocol.json"), self.read("data.json")
            data["blanks"] = [dict(row, response=y) for row, y in zip(data["blanks"], (-sd, 0, sd))]
            result = cal.reference_computation(protocol, data)
            self.assertAlmostEqual(result["limits"]["loq"], sd*5)
        for sd in (0.1, 0.9):
            data["blanks"] = [dict(row, response=y) for row, y in zip(data["blanks"], (-sd, 0, sd))]
            with self.assertRaisesRegex(ValueError, "^loq-range:"):
                cal.reference_computation(protocol, data)

    def test_protocol_rule_type_and_range_refusals(self):
        for field, value, code in (("model", "log", "model-choice"), ("intercept", "auto", "intercept-choice"),
                                   ("exclusion_rule", "best-r-squared", "exclusion-rule")):
            protocol = self.read("protocol.json")
            protocol[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "^" + code + ":"):
                cal.reference_computation(protocol, self.read("data.json"))
        for value in (0, -1, False, "1"):
            data = self.read("data.json")
            data["standards"][0]["concentration"] = value
            with self.assertRaisesRegex(ValueError, "^(nonpositive-concentration|invalid-record):"):
                cal.reference_computation(self.read("protocol.json"), data)
        for field, value, code in (("method", "unknown", "limit-rule"), ("method", [], "invalid-record"),
                                   ("lod_k", 0, "limit-rule"), ("lod_k", 10, "limit-rule"),
                                   ("loq_k", 3.3, "limit-rule"), ("min_blanks", [], "invalid-record")):
            protocol = self.read("protocol.json")
            protocol["limit_rule"][field] = value
            with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, "^" + code + ":"):
                cal.reference_computation(protocol, self.read("data.json"))
        for value in (0, 15, -1, False):
            protocol = self.read("protocol.json")
            protocol["acceptance"]["lowest_percent_deviation"] = value
            with self.assertRaisesRegex(ValueError, "^(acceptance-rule|invalid-record):"):
                cal.reference_computation(protocol, self.read("data.json"))
        for endpoint in (0, 1, 5):
            protocol = self.read("protocol.json")
            protocol["validity"]["max"] = endpoint
            with self.assertRaisesRegex(ValueError, "^validity-range:"):
                cal.reference_computation(protocol, self.read("data.json"))
        for path in (None, [], 1):
            with self.assertRaisesRegex(ValueError, "^input-path:"):
                cal.validate_calibration_lod_pack(path)

    def test_exploratory_weights_require_separate_frozen_bundle(self):
        self.change("report", lambda o: o.update(weighting="1/x", exploratory=True))
        with self.assertRaisesRegex(ValueError, "^exploratory-rerun:"):
            cal.validate_calibration_lod_pack(self.pack_path)

    def test_nonpositive_slope_and_weight_underflow_refused(self):
        protocol, data = self.read("protocol.json"), self.read("data.json")
        for row in data["standards"]:
            row["response"] = -row["concentration"]
        with self.assertRaisesRegex(ValueError, "^degenerate-fit:"):
            cal.reference_computation(protocol, data)
        protocol.update(model="weighted-linear", weighting="1/x^2")
        rows = [{"id": "A", "concentration": 1e-200, "response": 1},
                {"id": "B", "concentration": 1e100, "response": 2}]
        with self.assertRaisesRegex(ValueError, "^degenerate-fit:"):
            cal._fit(rows, protocol)

    def test_concurrent_calls_match_without_writes(self):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(cal.validate_calibration_lod_pack, [self.pack_path]*2))
        self.assertEqual(results[0], results[1])

    def test_cli_success_refusal_arguments_and_help(self):
        result = self.cli(self.pack_path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["review"], "unavailable")
        for args, code in (([], "invalid-arguments"), ([self.pack_path, "extra"], "invalid-arguments"),
                           (["--unknown"], "invalid-arguments"), ([self.pack_path, "--output", "out.json"], "invalid-arguments"),
                           ([self.root / "absent.json"], "input-file"),
                           ([self.root / CASES[0]["path"]], CASES[0]["finding"])):
            result = self.cli(*args)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(result.stdout, "")
            value = json.loads(result.stderr)
            self.assertEqual(value["status"], "refused")
            self.assertTrue(value["finding"].startswith(code + ":"), result.stderr)
            self.assertNotIn("Traceback", result.stderr)
        result = self.cli("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("usage:", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_validator_writes_nothing_and_repeated_calls_match(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir() if p.is_file()}
        first = cal.validate_calibration_lod_pack(self.pack_path)
        self.assertEqual(first, cal.validate_calibration_lod_pack(self.pack_path))
        after = {p.name: p.read_bytes() for p in self.root.iterdir() if p.is_file()}
        self.assertEqual(before, after)


def _negative_test(case):
    def test(self):
        with self.assertRaisesRegex(ValueError, "^" + re.escape(case["finding"]) + ":"):
            cal.validate_calibration_lod_pack(self.root / case["path"])
    return test


for _case in CASES:
    setattr(CalibrationPackTests, "test_seeded_" + _case["id"].replace("-", "_"), _negative_test(_case))


if __name__ == "__main__":
    unittest.main()
