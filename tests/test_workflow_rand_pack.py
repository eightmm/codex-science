"""Synthetic allocation controls, seeded refusals, bounded input and CLI contracts."""
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
from unittest.mock import patch

from codex_science import randomization_audit_pack as audit

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "workflow-randomization-audit"
CLI = ROOT / "scripts" / "validate_randomization_audit_pack.py"
CALL_TIMEOUT = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "30"))
CASES = json.loads((FIXTURE / "negative-cases.json").read_bytes())["cases"]


def _read(path):
    return json.loads(path.read_bytes())


def _write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")


def _identity(path):
    return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


class _Fixture(unittest.TestCase):
    fixture = "."

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.parent = Path(self.temporary.name) / "ancestor"
        self.directory = self.parent / "bundle"
        self.directory.mkdir(parents=True)
        for source in (FIXTURE / self.fixture).glob("*.json"):
            shutil.copyfile(source, self.directory / source.name)

    def document(self, name):
        return _read(self.directory / (name + ".json"))

    def edit(self, name, path, value):
        file = self.directory / (name + ".json")
        document = _read(file)
        owner = document
        for key in path[:-1]:
            owner = owner[key]
        owner[path[-1]] = value
        _write(file, document)

    def refresh(self):
        protocol = self.document("protocol")
        protocol["units"] = _identity(self.directory / "units.json")
        _write(self.directory / "protocol.json", protocol)
        report = self.document("report")
        report["protocol_sha256"] = _identity(self.directory / "protocol.json")["sha256"]
        _write(self.directory / "report.json", report)
        evidence = self.document("evidence")
        for record in evidence["records"]:
            record["source"]["sha256"] = hashlib.sha256(
                (self.directory / record["source"]["path"]).read_bytes()).hexdigest()
        _write(self.directory / "evidence.json", evidence)
        pack = self.document("pack")
        for name in ("protocol", "allocation", "report"):
            pack[name] = _identity(self.directory / (name + ".json"))
        pack["frozen_protocol_sha256"] = pack["protocol"]["sha256"]
        pack["evidence"] = [_identity(self.directory / "evidence.json")]
        _write(self.directory / "pack.json", pack)

    def validate(self):
        return audit.validate_randomization_audit_pack(self.directory / "pack.json")

    def cli(self, *args):
        return subprocess.run([sys.executable, str(CLI), *map(str, args)],
                              capture_output=True, text=True, timeout=CALL_TIMEOUT)

    def refuse(self, code):
        with self.assertRaisesRegex(ValueError, "^" + code + ":"):
            self.validate()


class RandomizationMathTests(_Fixture):
    def test_three_fixtures_hand_checked_and_read_only(self):
        rosters = {
            ".": "AAABBABB",
            "blocked": "AABB BABA".replace(" ", ""),
            "stratified": "AABBBABAABBAABBA",
        }
        for folder, roster in rosters.items():
            with self.subTest(fixture=folder):
                directory = FIXTURE / folder
                before = {p.name: p.read_bytes() for p in directory.glob("*.json")}
                result = audit.validate_randomization_audit_pack(directory / "pack.json")
                self.assertEqual(_read(directory / "expected.json"), result)
                protocol = _read(directory / "protocol.json")
                table = _read(directory / "units.json")
                computed = audit.reference_computation(protocol, table)
                self.assertEqual(roster, "".join(computed["generated_allocation"][row["unit_id"]]
                                                for row in table["rows"]))
                self.assertEqual({"A": len(roster)//2, "B": len(roster)//2}, result["computation"]["counts"])
                for metric in result["computation"]["balance"]:
                    expected = -0.25 if metric["metric"] == "risk_difference" else -math.sqrt(
                        7/40 if folder == "stratified" and metric["scope"] == "overall" else 3/20)
                    self.assertAlmostEqual(expected, metric["value"], places=14)
                    self.assertTrue(metric["flag"])
                self.assertFalse(result["computation"]["balanced"])
                self.assertTrue(result["reproduced"])
                self.assertEqual("arithmetic-only", result["status"])
                self.assertEqual("unavailable", result["review"])
                self.assertEqual(before, {p.name: p.read_bytes() for p in directory.glob("*.json")})

    def test_disclosed_mismatch_is_not_reported_reproduced(self):
        self.edit("allocation", ["rows", 0, "arm"], "B")
        self.edit("allocation", ["rows", 3, "arm"], "A")
        self.edit("report", ["reproduced"], False)
        protocol, table = self.document("protocol"), self.document("units")
        rows, groups = audit._units(table, protocol)
        recorded = {row["unit_id"]: row["arm"] for row in self.document("allocation")["rows"]}
        metrics = audit._metrics(protocol, rows, groups, recorded)
        for key, value in metrics.items():
            self.edit("report", [key], value)
        self.refresh()
        result = self.validate()
        self.assertFalse(result["reproduced"])
        self.assertEqual("allocation-not-reproduced", result["finding"])

    def test_partial_blocks_unequal_ratios_and_row_order(self):
        protocol, table = self.document("protocol"), self.document("units")
        protocol.update(method="permuted-block", block_size=6, allocation_ratio=[2, 1])
        table["rows"].extend(copy.deepcopy(table["rows"][:3]))
        for index, row in enumerate(table["rows"]):
            row["unit_id"] = f"T{index:02}"
        result = audit.reference_computation(protocol, table)
        roster = list(result["generated_allocation"].values())
        self.assertEqual(4, roster[:6].count("A"))
        self.assertEqual(2, roster[:6].count("B"))
        self.assertLessEqual(roster[6:].count("A"), 4)
        self.assertLessEqual(roster[6:].count("B"), 2)
        self.assertEqual(result, audit.reference_computation(protocol, {**table, "rows": list(reversed(table["rows"]))}))
        rows, groups = audit._units(table, protocol)
        allocation = {"schema": "randomization-audit-allocation-v1", "schema_version": 1,
                      "fixture": "synthetic fixture", "attempts": 1, "after_balance_seen": False,
                      "rows": [{"unit_id": k, "arm": v, "recorded_at": "2030-01-02T00:00:00Z"}
                               for k, v in result["generated_allocation"].items()]}
        self.assertEqual(result["generated_allocation"], audit._allocation(allocation, protocol, rows, groups))
        for row in allocation["rows"][6:]:
            row["arm"] = "A"
        with self.assertRaisesRegex(ValueError, "^block-size:"):
            audit._allocation(allocation, protocol, rows, groups)

    def test_threshold_equality_zero_and_near_zero_relative_comparison(self):
        protocol, table = self.document("protocol"), self.document("units")
        result = audit.reference_computation(protocol, table)
        for metric in result["balance"]:
            protocol["thresholds"][metric["metric"]] = abs(metric["value"])
        self.assertTrue(audit.reference_computation(protocol, table)["balanced"])
        protocol["thresholds"] = {"smd": 0, "risk_difference": 0}
        self.assertTrue(all(m["flag"] for m in audit.reference_computation(protocol, table)["balance"]))
        self.edit("report", ["balance", 0, "value"], 0)
        self.refresh()
        self.refuse("covariate-imbalance")
        audit._same(1e-100, 1e-100, "comparison")
        with self.assertRaisesRegex(ValueError, "^comparison:"):
            audit._same(1e-100, 2e-100, "comparison")

    def test_degenerate_empty_and_below_minimum_units(self):
        protocol, table = self.document("protocol"), self.document("units")
        for row in table["rows"]:
            row["covariates"]["baseline"] = 1
        with self.assertRaisesRegex(ValueError, "^degenerate-covariate:"):
            audit.reference_computation(protocol, table)
        with self.assertRaisesRegex(ValueError, "^invalid-record:"):
            audit.reference_computation(protocol, {**table, "rows": []})
        protocol["minimum_per_arm"] = 5
        with self.assertRaisesRegex(ValueError, "^insufficient-units:"):
            audit.reference_computation(protocol, self.document("units"))

    def test_exploratory_attempts_preserved_and_time_equality_refused(self):
        self.edit("allocation", ["attempts"], 2)
        self.edit("allocation", ["after_balance_seen"], True)
        self.edit("report", ["exploratory"], True)
        self.refresh()
        self.assertTrue(self.validate()["exploratory"])
        self.edit("allocation", ["rows", 0, "recorded_at"], "2030-01-03T00:00:00Z")
        self.refresh()
        self.refuse("allocation-after-outcomes")


class RandomizationDefectTests(_Fixture):
    pass


def _defect_test(case):
    def test(self):
        for change in case["changes"]:
            self.edit(change["target"], change["path"], change["value"])
        self.refresh()
        self.refuse(case["finding"])
        completed = self.cli(self.directory / "pack.json")
        self.assertEqual(2, completed.returncode)
        self.assertEqual("", completed.stdout)
        self.assertTrue(json.loads(completed.stderr)["finding"].startswith(case["finding"] + ":"))
        self.assertNotIn("Traceback", completed.stderr)
    def method(self):
        for file in self.directory.iterdir():
            file.unlink()
        for source in (FIXTURE / case["fixture"]).glob("*.json"):
            shutil.copyfile(source, self.directory / source.name)
        test(self)
    return method


for _case in CASES:
    setattr(RandomizationDefectTests, "test_" + _case["id"].replace("-", "_"), _defect_test(_case))


class RandomizationInputTests(_Fixture):
    def test_freeze_after_outcomes_and_any_unavailable_result_refused(self):
        self.edit("pack", ["frozen_at"], "2030-01-04T00:00:00Z")
        self.edit("pack", ["allocation_read_at"], "2030-01-05T00:00:00Z")
        self.refuse("rule-freeze")
        self.edit("pack", ["frozen_at"], "2030-01-01T00:00:00Z")
        self.edit("evidence", ["records", 1, "kind"], "observation")
        self.edit("evidence", ["records", 1, "result"], "UNAVAILABLE")
        self.edit("report", ["claims", 0, "status"], "withdrawn")
        self.edit("report", ["claims", 0, "support"], ["E2", "E3"])
        self.refresh()
        self.refuse("unavailable-evidence")

    def test_cli_arguments_success_help_and_refusals(self):
        for args in ((), ("a", "b"), ("--unknown",), (self.directory / "pack.json", "--output", "x")):
            with self.subTest(args=args):
                result = self.cli(*args)
                self.assertEqual(2, result.returncode)
                self.assertEqual("", result.stdout)
                self.assertTrue(json.loads(result.stderr)["finding"].startswith("invalid-arguments:"))
        result = self.cli("--help")
        self.assertEqual(0, result.returncode)
        self.assertIn("usage:", result.stdout)
        self.assertEqual("", result.stderr)
        result = self.cli(self.directory / "pack.json")
        self.assertEqual(0, result.returncode)
        self.assertEqual("", result.stderr)
        self.assertEqual("arithmetic-only", json.loads(result.stdout)["status"])

    def test_json_duplicate_nonfinite_root_types_huge_depth(self):
        invalid = [b'{"a":1,"a":2}', b'{"a":{"x":1,"x":2}}', b'{"a":NaN}',
                   b'{"a":Infinity}', b'{"a":1e999}', b'{"a":' + b'9'*200 + b'}',
                   b'[]', b'null', b'false', b'{', b'\xff', b'{"a":' + b'['*2000 + b'0' + b']'*2000 + b'}']
        for raw in invalid:
            with self.subTest(raw=raw[:40]):
                with self.assertRaisesRegex(ValueError, "^invalid-json:"):
                    audit._json(raw, audit.MAX_JSON_VALUES)
        with patch.object(audit.re, "findall", side_effect=AssertionError("match lists forbidden")):
            self.validate()

    def test_every_declared_integer_rejects_bool_float_string(self):
        fields = [(name, ["schema_version"]) for name in ("pack", "protocol", "units", "allocation", "report", "evidence")]
        fields += [("protocol", ["seed"]), ("protocol", ["minimum_per_arm"]),
                   ("protocol", ["allocation_ratio", 0]), ("allocation", ["attempts"]),
                   ("units", ["rows", 0, "covariates", "marker"]), ("report", ["counts", "A"])]
        originals = {p.name: p.read_bytes() for p in self.directory.glob("*.json")}
        for name, path in fields:
            for value in (True, 1.0, "1"):
                with self.subTest(record=name, field=path, value=value):
                    for filename, raw in originals.items():
                        (self.directory / filename).write_bytes(raw)
                    self.edit(name, path, value)
                    self.refresh()
                    self.refuse("invalid-record")
        protocol = self.document("protocol")
        for value in (True, 4.0, "4"):
            with self.subTest(block_size=value):
                protocol.update(method="permuted-block", block_size=value)
                with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                    audit.reference_computation(protocol, self.document("units"))

    def test_unhashable_labels_missing_blinding_and_null_covariate(self):
        edits = [("allocation", ["rows", 0, "arm"], []),
                 ("report", ["claims", 0, "status"], []),
                 ("report", ["claims", 0, "support"], [[]]),
                 ("evidence", ["records", 0, "origin"], {})]
        originals = {p.name: p.read_bytes() for p in self.directory.glob("*.json")}
        for name, path, value in edits:
            with self.subTest(field=path):
                for filename, raw in originals.items():
                    (self.directory / filename).write_bytes(raw)
                self.edit(name, path, value)
                self.refresh()
                self.refuse("invalid-record")
        protocol = self.document("protocol")
        del protocol["blinding"]
        with self.assertRaisesRegex(ValueError, "^blinding-missing:"):
            audit.reference_computation(protocol, self.document("units"))
        self.edit("units", ["rows", 0, "covariates", "baseline"], None)
        self.refresh()
        self.refuse("unit-unavailable")

    def test_claim_wording_families_and_unavailable_order(self):
        words = ["causality", "mechanism", "therapy", "clinical", "efficacy", "effective", "treatment", "cure",
                 "prevention", "recommendation", "prescription", "binding", "affinity", "inhibition", "activation",
                 "regulation", "drive", "drives", "driving", "induction"]
        for word in words:
            with self.subTest(word=word):
                self.edit("report", ["claims", 0, "text"], word.upper())
                self.refresh()
                self.refuse("claim-overreach")
        self.edit("report", ["claims", 0, "text"], "The roster was recorded.")
        self.edit("report", ["claims", 0, "support"], ["E2", "E3"])
        for status in sorted(audit.STATUSES - {"unavailable"}):
            self.edit("report", ["claims", 0, "status"], status)
            self.refresh()
            self.refuse("unavailable-evidence")

    def test_arithmetic_status_and_result_schema_cannot_support_positive_claims(self):
        report = self.document("report")
        report["claims"][0].update(status="supported", support=["E3"], text="The synthetic roster was recorded.")
        _write(self.directory / "report.json", report)
        evidence = self.document("evidence")
        self.refresh()
        self.validate()
        for field in ("kind", "result"):
            for label in ("arithmetic-only", "randomization-audit-result-v1"):
                with self.subTest(field=field, label=label):
                    changed = copy.deepcopy(evidence)
                    changed["records"][2][field] = label
                    _write(self.directory / "evidence.json", changed)
                    self.refresh()
                    self.refuse("non-evidence")

    def test_regular_file_path_hash_and_growth_controls(self):
        pack = self.document("pack")
        for name in ("/absolute", "../escape", "a\\b", "./units.json", "a//b", "a/../b"):
            self.edit("pack", ["allocation", "path"], name)
            self.refuse("input-path")
        _write(self.directory / "pack.json", pack)
        self.edit("pack", ["allocation", "sha256"], "0"*64)
        self.refuse("input-hash")
        _write(self.directory / "pack.json", pack)
        unit = self.directory / "units.json"
        saved = unit.read_bytes()
        unit.unlink()
        for kind in ("fifo", "directory", "symlink"):
            with self.subTest(kind=kind):
                if kind == "fifo":
                    os.mkfifo(unit)
                elif kind == "directory":
                    unit.mkdir()
                else:
                    unit.symlink_to(self.directory / "protocol.json")
                self.refuse("input-file")
                unit.rmdir() if kind == "directory" else unit.unlink()
        unit.write_bytes(saved)
        opened = os.fdopen
        wanted = unit.stat().st_ino
        def grow(descriptor, *args, **kwargs):
            handle = opened(descriptor, *args, **kwargs)
            if os.fstat(descriptor).st_ino == wanted:
                read = handle.read
                def changed(size):
                    raw = read(size)
                    with unit.open("ab") as writer:
                        writer.write(b" ")
                    return raw
                handle.read = changed
            return handle
        with patch.object(audit.os, "fdopen", side_effect=grow):
            self.refuse("input-file")

    def test_artifact_and_root_symlink_components_refused(self):
        child = self.directory / "link"
        child.symlink_to(self.directory, target_is_directory=True)
        self.edit("pack", ["allocation", "path"], "link/allocation.json")
        self.refuse("input-file")
        with self.assertRaisesRegex(ValueError, "^input-root:"):
            audit.validate_randomization_audit_pack(child / "pack.json")

    def test_final_input_replacement_is_refused(self):
        original = audit._generate
        def swapped(*args):
            result = original(*args)
            unit = self.directory / "units.json"
            replacement = self.directory / "replacement.json"
            replacement.write_bytes(unit.read_bytes())
            os.replace(replacement, unit)
            return result
        with patch.object(audit, "_generate", side_effect=swapped):
            self.refuse("input-changed")

    def test_transient_root_and_ancestor_swaps_at_open(self):
        opened = os.open
        for target in (self.directory, self.parent):
            fired = False
            backup = target.with_name(target.name + "-saved")
            def swapped(name, flags, *args, **kwargs):
                nonlocal fired
                if not fired and name == target.name and "dir_fd" in kwargs:
                    fired = True
                    target.rename(backup)
                    target.symlink_to(backup, target_is_directory=True)
                    try:
                        return opened(name, flags, *args, **kwargs)
                    finally:
                        target.unlink()
                        backup.rename(target)
                return opened(name, flags, *args, **kwargs)
            with self.subTest(target=target.name), patch.object(audit.os, "open", side_effect=swapped):
                self.refuse("input-root")
            self.assertTrue(fired)

    def test_parent_swap_preserving_bundle_inode_is_refused(self):
        original = audit._generate
        before = self.directory.stat().st_ino
        def moved(*args):
            result = original(*args)
            backup = self.parent.with_name("old-parent")
            self.parent.rename(backup)
            self.parent.mkdir()
            (backup / "bundle").rename(self.directory)
            return result
        with patch.object(audit, "_generate", side_effect=moved):
            self.refuse("input-root")
        self.assertEqual(before, self.directory.stat().st_ino)

    def test_lstat_open_file_swap_and_final_root_swap_refused(self):
        original = os.lstat
        target = self.directory / "units.json"
        fired = False
        def changed(name, *args, **kwargs):
            nonlocal fired
            info = original(name, *args, **kwargs)
            if not fired and name == "units.json":
                fired = True
                replacement = target.with_name("replacement.json")
                replacement.write_bytes(target.read_bytes())
                os.replace(replacement, target)
            return info
        with patch.object(audit.os, "lstat", side_effect=changed):
            self.refuse("input-file")
        self.assertTrue(fired)
        original_check = audit._Bundle._check_root
        called = 0
        def moved(store):
            nonlocal called
            called += 1
            if called == 2:
                self.directory.rename(self.directory.with_name("old-bundle"))
                self.directory.mkdir()
            return original_check(store)
        with patch.object(audit._Bundle, "_check_root", moved):
            self.refuse("input-root")

    def test_inode_cache_parse_once_and_aggregate_byte_limits(self):
        first = self.directory / "one.json"
        first.write_bytes(b'{"x":1}')
        alias = self.directory / "two.json"
        os.link(first, alias)
        store = audit._Bundle(self.directory)
        self.addCleanup(store.close)
        with patch.object(audit, "MAX_TOTAL_BYTES", len(first.read_bytes())), \
                patch.object(audit, "MAX_ARTIFACTS", 1), \
                patch.object(audit, "MAX_JSON_VALUES", 2), \
                patch.object(audit, "_json", wraps=audit._json) as parsed:
            self.assertIs(store.load("one.json"), store.load("two.json"))
            self.assertEqual(1, parsed.call_count)
            store.finish()
            with self.assertRaisesRegex(ValueError, "^input-limit:"):
                store.load("pack.json")
        for limit in (0, len(first.read_bytes()) - 1):
            other = audit._Bundle(self.directory)
            try:
                with patch.object(audit, "MAX_TOTAL_BYTES", limit):
                    with self.assertRaisesRegex(ValueError, "^input-limit:"):
                        other.load("one.json")
            finally:
                other.close()
        for limit, accepted in ((len(first.read_bytes()), True), (0, False)):
            other = audit._Bundle(self.directory)
            try:
                with patch.object(audit, "MAX_BYTES", limit):
                    if accepted:
                        other.load("one.json")
                    else:
                        with self.assertRaisesRegex(ValueError, "^input-file:"):
                            other.load("one.json")
            finally:
                other.close()

    def test_json_count_string_depth_and_number_boundaries(self):
        for raw, limit, accepted in ((b'{"x":1}', 2, True), (b'{"x":1}', 1, False),
                                     (b'{"x":1}', 0, False), (b'{"x":[1,2]}', 4, True)):
            with self.subTest(raw=raw, limit=limit):
                if accepted:
                    audit._json(raw, limit)
                else:
                    with self.assertRaisesRegex(ValueError, "^input-limit:"):
                        audit._json(raw, limit)
        for constant, bound, good, bad in (
                ("MAX_ITEMS", 2, b'{"x":[1,2]}', b'{"x":[1,2,3]}'),
                ("MAX_STRING", 4, b'{"x":"1234"}', b'{"x":"12345"}'),
                ("MAX_DEPTH", 1, b'{"x":0}', b'{"x":[0]}'),
                ("MAX_NUMBER", 1, b'{"x":1}', b'{"x":2}')):
            with self.subTest(constant=constant), patch.object(audit, constant, bound):
                audit._json(good, 100)
                with self.assertRaises(ValueError):
                    audit._json(bad, 100)

    def test_unit_arm_covariate_group_and_metric_limits(self):
        protocol, table = self.document("protocol"), self.document("units")
        for constant, equal in (("MAX_UNITS", 8), ("MAX_ARMS", 2), ("MAX_COVARIATES", 2), ("MAX_METRICS", 2)):
            with self.subTest(constant=constant):
                with patch.object(audit, constant, equal):
                    audit.reference_computation(protocol, table)
                with patch.object(audit, constant, equal - 1):
                    with self.assertRaisesRegex(ValueError, "^input-limit:"):
                        audit.reference_computation(protocol, table)
        oversize = {**table, "rows": table["rows"] * (audit.MAX_UNITS // len(table["rows"]) + 1)}
        with self.assertRaisesRegex(ValueError, "^input-limit:"):
            audit.reference_computation(protocol, oversize)
        protocol = _read(FIXTURE / "stratified/protocol.json")
        table = _read(FIXTURE / "stratified/units.json")
        for constant, equal in (("MAX_STRATA", 1), ("MAX_GROUPS", 2)):
            with self.subTest(constant=constant):
                with patch.object(audit, constant, equal):
                    audit.reference_computation(protocol, table)
                with patch.object(audit, constant, equal - 1):
                    with self.assertRaisesRegex(ValueError, "^input-limit:"):
                        audit.reference_computation(protocol, table)
        with patch.object(audit, "MAX_RECORDS", 3):
            self.validate()
        with patch.object(audit, "MAX_RECORDS", 2):
            self.refuse("input-limit")

    def test_no_cross_product_before_metric_bound(self):
        with patch.object(audit, "MAX_METRICS", 0), \
                patch.object(audit, "combinations", side_effect=AssertionError("unbounded pair work")):
            self.refuse("input-limit")


if __name__ == "__main__":
    unittest.main()
