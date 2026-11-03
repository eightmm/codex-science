"""Synthetic qPCR arithmetic, named refusals, untrusted input and read-only checks."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import copy
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

from codex_science import qpcr_relative_quantification_pack as qpcr


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/workflow-qpcr-relative-quantification"
CLI = ROOT / "scripts/validate_qpcr_relative_quantification_pack.py"
CALL_TIMEOUT = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "30"))
CASES = json.loads((FIXTURE / "negative-cases.json").read_bytes())["cases"]


def _read(path):
    return json.loads(path.read_bytes())


def _write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")


def _identity(path):
    return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _track_reads(reads):
    original = os.fdopen

    def opened(descriptor, *args, **kwargs):
        handle = original(descriptor, *args, **kwargs)
        read = handle.read

        def tracked(*args, **kwargs):
            reads.append(os.fstat(handle.fileno()).st_size)
            return read(*args, **kwargs)

        handle.read = tracked
        return handle

    return patch.object(qpcr.os, "fdopen", opened)


class _Fixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name) / "fixture"
        shutil.copytree(FIXTURE, self.directory)

    def _edit(self, target, path, value, remove=False):
        filename = self.directory / (target + ".json")
        document = _read(filename)
        owner = document
        for key in path[:-1]:
            owner = owner[key]
        if remove:
            del owner[path[-1]]
        else:
            owner[path[-1]] = value
        _write(filename, document)

    def _refresh(self, recompute=False):
        protocol = self.directory / "protocol.json"
        table = self.directory / "table.json"
        report = _read(self.directory / "report.json")
        report["protocol_sha256"] = _identity(protocol)["sha256"]
        if recompute:
            report["summary"] = qpcr.reference_computation(_read(protocol), _read(table))
        _write(self.directory / "report.json", report)
        evidence = _read(self.directory / "evidence.json")
        for row in evidence["records"]:
            row["source"]["sha256"] = hashlib.sha256((self.directory / row["source"]["path"]).read_bytes()).hexdigest()
        _write(self.directory / "evidence.json", evidence)
        pack = _read(self.directory / "pack.json")
        for field in ("protocol", "table", "report"):
            pack[field] = _identity(self.directory / (field + ".json"))
        pack["evidence"] = [_identity(self.directory / "evidence.json")]
        pack["frozen_protocol_sha256"] = pack["protocol"]["sha256"]
        _write(self.directory / "pack.json", pack)

    def _validate(self):
        return qpcr.validate_qpcr_relative_quantification_pack(self.directory / "pack.json")

    def _cli(self, *args):
        return subprocess.run([sys.executable, str(CLI), *map(str, args)], capture_output=True,
                              text=True, timeout=CALL_TIMEOUT)

    def _apply_case(self, case):
        self.directory = self.directory / case["base"]
        for change in case["changes"]:
            self._edit(change["target"], change["path"], change["value"], change.get("remove", False))
        self._refresh()


class QpcrSeededRefusalTests(_Fixture):
    pass


def _seeded(case):
    def test(self):
        self._apply_case(case)
        with self.assertRaisesRegex(ValueError, "^" + case["code"] + ":"):
            self._validate()
        result = self._cli(self.directory / "pack.json")
        self.assertEqual(2, result.returncode, result.stderr)
        self.assertEqual("", result.stdout)
        refusal = json.loads(result.stderr)
        self.assertEqual("refused", refusal["status"])
        self.assertTrue(refusal["error"].startswith(case["code"] + ":"), refusal)
    return test


for _case in CASES:
    setattr(QpcrSeededRefusalTests, "test_" + _case["id"].replace("-", "_"), _seeded(_case))


class QpcrArithmeticTests(_Fixture):
    def test_hand_derived_efficiency_corrected_quantities_and_welch_interval(self):
        result = self._validate()
        self.assertEqual(_read(self.directory / "expected.json"), result)
        summary = result["computation"][0]
        expected = 1 - math.log2(1.9)
        self.assertAlmostEqual(expected, summary["log2_fold_change"], places=12)
        self.assertAlmostEqual(2 / 1.9, summary["fold_change"], places=12)
        self.assertNotAlmostEqual(2, summary["fold_change"], places=2)
        self.assertEqual({"calibrator": 3, "contrast": 3}, summary["n"])
        self.assertEqual({"calibrator": 0, "contrast": 0}, summary["censored_n"])
        for sample, value in zip(summary["samples"], [0.5, 1, 2, 1 / 1.9, 2 / 1.9, 4 / 1.9]):
            self.assertAlmostEqual(value, sample["relative_quantity"], places=12)
        interval = summary["interval"]
        self.assertAlmostEqual(4, interval["df"], places=12)
        # For df=4, integrating the t density gives tail = 1 - 1.5*s + .5*s**3,
        # where s = t / sqrt(4+t*t). This independently checks the beta reference.
        critical = (interval["upper"] - expected) / math.sqrt(2 / 3)
        s = critical / math.sqrt(4 + critical * critical)
        self.assertAlmostEqual(0.05, 1 - 1.5 * s + 0.5 * s ** 3, places=12)
        self.assertAlmostEqual(2.7764451051977987, critical, places=10)
        self.assertAlmostEqual(expected - critical * math.sqrt(2 / 3), interval["lower"], places=12)
        self.assertEqual("unavailable", result["review"])
        self.assertEqual("arithmetic-only", result["status"])

    def test_small_n_interval_is_unavailable(self):
        self.directory /= "small-n"
        result = self._validate()
        self.assertEqual(_read(self.directory / "expected.json"), result)
        self.assertEqual({"calibrator": 2, "contrast": 2}, result["computation"][0]["n"])
        self.assertEqual("unavailable", result["computation"][0]["interval"])

    def test_censored_undetermined_and_detection_equality_never_become_zero(self):
        for value in ("undetermined", 35):
            with self.subTest(cq=value):
                self._edit("table", ["rows", 0, "cq"], value)
                # Keep the second technical well equal when testing cutoff censoring.
                self._edit("table", ["rows", 1, "cq"], value)
                self._refresh(recompute=True)
                summary = self._validate()["computation"][0]
                self.assertEqual(2, summary["n"]["calibrator"])
                self.assertEqual(1, summary["censored_n"]["calibrator"])
                self.assertTrue(summary["samples"][0]["censored"])
                self.assertEqual("unavailable", summary["samples"][0]["relative_quantity"])
                self.assertEqual("unavailable", summary["interval"])

    def test_no_detected_condition_and_zero_biological_variance_refuse(self):
        protocol, table = _read(self.directory / "protocol.json"), _read(self.directory / "table.json")
        censored = copy.deepcopy(table)
        for row in censored["rows"][:12]:
            row["cq"] = "undetermined"
        with self.assertRaisesRegex(ValueError, "^insufficient-biological-n:"):
            qpcr.reference_computation(protocol, censored)
        for row in table["rows"][:12]:
            row["cq"] = 20
        with self.assertRaisesRegex(ValueError, "^degenerate-variance:"):
            qpcr.reference_computation(protocol, table)

    def test_threshold_edges_zero_equal_and_just_over(self):
        protocol, table = _read(self.directory / "protocol.json"), _read(self.directory / "table.json")
        protocol["max_technical_spread"] = 0.2
        qpcr.reference_computation(protocol, table)
        protocol["max_technical_spread"] = 0
        with self.assertRaisesRegex(ValueError, "^technical-spread:"):
            qpcr.reference_computation(protocol, table)
        for offset in range(0, 24, 2):
            table["rows"][offset + 1]["cq"] = table["rows"][offset]["cq"]
        qpcr.reference_computation(protocol, table)
        for cq, succeeds in [(36, True), (35, False), (0, False)]:
            table["rows"][-1]["cq"] = cq
            if succeeds:
                qpcr.reference_computation(protocol, table)
            else:
                with self.assertRaisesRegex(ValueError, "^ntc-amplification:"):
                    qpcr.reference_computation(protocol, table)
        table["rows"][-1]["cq"] = "undetermined"
        protocol["max_technical_spread"] = 0.5
        # Use the actual regression-derived boundaries, including equality.
        actual = []
        for assay in protocol["assays"]:
            series = assay["dilution_series"]
            slope = (series[2]["cq"] - series[0]["cq"]) / 2
            actual.append(math.expm1(-math.log(10) / slope))
        protocol["efficiency_range"] = [min(actual), max(actual)]
        qpcr.reference_computation(protocol, table)

    def test_dilution_zero_variance_duplicate_and_malformed(self):
        protocol, table = _read(self.directory / "protocol.json"), _read(self.directory / "table.json")
        for change, code in [("constant", "degenerate-series"), ("duplicate", "dilution-series"),
                             ("empty", "dilution-series"), ("malformed", "invalid-record")]:
            broken = copy.deepcopy(protocol)
            points = broken["assays"][0]["dilution_series"]
            if change == "constant":
                for point in points:
                    point["cq"] = 20
            elif change == "duplicate":
                points[1]["log10_input"] = points[0]["log10_input"]
            else:
                broken["assays"][0]["dilution_series"] = [] if change == "empty" else {}
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "^" + code + ":"):
                qpcr.reference_computation(broken, table)

    def test_unique_wells_complete_grid_and_independent_biological_units(self):
        for target, path, value, code in [
            ("table", ["rows", 1, "well_id"], "calibrator-1-T-1", "well-identity"),
            ("protocol", ["samples", 1, "biological_id"], "calibrator-1", "biological-identity"),
            ("protocol", ["samples", 0, "wells", 0, "gene"], "unknown", "well-identity"),
            ("protocol", ["ntc_wells"], [], "invalid-record"),
        ]:
            with self.subTest(path=path):
                original = (self.directory / (target + ".json")).read_bytes()
                self._edit(target, path, value)
                self._refresh()
                with self.assertRaisesRegex(ValueError, "^" + code + ":"):
                    self._validate()
                (self.directory / (target + ".json")).write_bytes(original)
        self._refresh()

    def test_subnormal_variance_has_finite_welch_interval(self):
        protocol, table = _read(self.directory / "protocol.json"), _read(self.directory / "table.json")
        for index, sample in enumerate(protocol["samples"]):
            target = (index % 3 + (index // 3)) * 1e-160
            names = {well["well_id"]: well["gene"] for well in sample["wells"]}
            for row in table["rows"]:
                if row["well_id"] in names:
                    row["cq"] = target if names[row["well_id"]] == "T" else 0
        summary = qpcr.reference_computation(protocol, table)[0]
        self.assertTrue(math.isfinite(summary["interval"]["df"]))
        self.assertAlmostEqual(4, summary["interval"]["df"], places=2)
        self.assertGreater(summary["interval"]["upper"], summary["interval"]["lower"])
        for index, sample in enumerate(protocol["samples"]):
            target = (index % 3 + (index // 3)) * math.sqrt(math.ulp(0.0))
            names = {well["well_id"]: well["gene"] for well in sample["wells"]}
            for row in table["rows"]:
                if row["well_id"] in names:
                    row["cq"] = target if names[row["well_id"]] == "T" else 0
        with self.assertRaisesRegex(ValueError, "^degenerate-variance:"):
            qpcr.reference_computation(protocol, table)

    def test_condition_labels_with_spaces(self):
        protocol = _read(self.directory / "protocol.json")
        protocol["conditions"] = ["calibrator cells", "contrast cells"]
        for sample in protocol["samples"]:
            sample["condition"] += " cells"
        _write(self.directory / "protocol.json", protocol)
        self._refresh(recompute=True)
        self.assertEqual({"calibrator cells": 3, "contrast cells": 3}, self._validate()["computation"][0]["n"])


class QpcrClaimTests(_Fixture):
    def test_all_wording_families_in_headline_and_unavailable_claim(self):
        for word in [prefix + "ing" for prefix in qpcr.WORDING_FAMILIES] + ["drive", "drives", "biomarker", "target validity", "physical validity"]:
            for destination in [["headline"], ["claims", 0, "text"]]:
                with self.subTest(word=word, destination=destination):
                    self._edit("report", destination, "The fixture demonstrates " + word.upper() + ".")
                    self._refresh()
                    with self.assertRaisesRegex(ValueError, "^claim-overreach:"):
                        self._validate()
                    self._edit("report", destination, "Biological interpretation remains unavailable.")

    def test_positive_statuses_check_kind_and_result_and_refusal_order(self):
        for status in sorted(qpcr.POSITIVE):
            for field in ("kind", "result"):
                for label in ("computed", "review-approved", "arithmetic-only", "numerical-agreement"):
                    with self.subTest(status=status, field=field, label=label):
                        self._edit("report", ["claims", 0, "status"], status)
                        self._edit("report", ["claims", 0, "text"], "Synthetic fixture values agree.")
                        self._edit("evidence", ["records", 0, "kind"], "observed")
                        self._edit("evidence", ["records", 0, "result"], "measured")
                        self._edit("evidence", ["records", 0, field], label)
                        # A later malformed summary must not mask the evidence finding.
                        self._edit("report", ["summary"], [])
                        self._refresh()
                        with self.assertRaisesRegex(ValueError, "^non-evidence-support:"):
                            self._validate()

    def test_unavailable_sources_require_unavailable_for_every_other_status(self):
        for status in sorted(qpcr.STATUSES - {"unavailable"}):
            for key in ("kind", "result"):
                self._edit("report", ["claims", 0, "status"], status)
                self._edit("report", ["claims", 0, "text"], "Synthetic fixture observations.")
                self._edit("evidence", ["records", 0, "kind"], "observed")
                self._edit("evidence", ["records", 0, "result"], "measured")
                self._edit("evidence", ["records", 0, key], "unavailable")
                self._refresh()
                with self.subTest(status=status, key=key), self.assertRaisesRegex(ValueError, "^unavailable-evidence:"):
                    self._validate()
        evidence = _read(self.directory / "evidence.json")
        other = copy.deepcopy(evidence["records"][0])
        other.update(id="observed", kind="observed", result="measured")
        evidence["records"].append(other)
        _write(self.directory / "evidence.json", evidence)
        self._edit("report", ["claims", 0, "evidence"], ["calculation", "observed"])
        self._edit("report", ["claims", 0, "status"], "unsupported")
        self._refresh()
        with self.assertRaisesRegex(ValueError, "^unavailable-evidence:"):
            self._validate()
        self._edit("report", ["claims", 0, "status"], "unavailable")
        self._refresh()
        self._validate()

    def test_empty_evidence_unavailable_assertions_and_unhashable_fields(self):
        self._edit("report", ["claims", 0, "evidence"], [])
        self._refresh()
        self._validate()
        for text in ("supported", "replicated", "suggestive", "SIGNIFICANT"):
            self._edit("report", ["claims", 0, "text"], text)
            self._refresh()
            with self.assertRaisesRegex(ValueError, "^unavailable-positive:"):
                self._validate()
        self._edit("report", ["claims", 0, "text"], "Interpretation remains unavailable.")
        for field in ("id", "kind", "status"):
            original = _read(self.directory / "report.json")["claims"][0][field]
            self._edit("report", ["claims", 0, field], [])
            self._refresh()
            with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                self._validate()
            self._edit("report", ["claims", 0, field], original)

    def test_noninternal_origins_refuse_path_and_hash_aliases(self):
        shutil.copyfile(self.directory / "table.json", self.directory / "copied.json")
        for origin in ("external", "independent", "preregistered"):
            for name in ("table.json", "copied.json"):
                self._edit("evidence", ["records", 0, "origin"], origin)
                self._edit("evidence", ["records", 0, "source"], _identity(self.directory / name))
                self._refresh()
                with self.subTest(origin=origin, name=name), self.assertRaisesRegex(ValueError, "^external-alias:"):
                    self._validate()


class QpcrInputTests(_Fixture):
    def test_cli_success_argument_errors_and_help(self):
        result = self._cli(self.directory / "pack.json")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", result.stderr)
        self.assertEqual(self._validate(), json.loads(result.stdout))
        for args in [[], ["--unknown"], [self.directory / "pack.json", "extra"],
                     [self.directory / "pack.json", "--output", "out.json"]]:
            with self.subTest(args=args):
                result = self._cli(*args)
                self.assertEqual(2, result.returncode)
                self.assertEqual("", result.stdout)
                self.assertTrue(json.loads(result.stderr)["error"].startswith("invalid-arguments:"))
        result = self._cli("--help")
        self.assertEqual(0, result.returncode)
        self.assertEqual("", result.stderr)
        self.assertIn("bundle", result.stdout)
        result = self._cli(self.directory / "absent.json")
        self.assertEqual(2, result.returncode)
        self.assertEqual("", result.stdout)
        self.assertTrue(json.loads(result.stderr)["error"].startswith("input-file:"))

    def test_strict_json_duplicate_nested_nonfinite_deep_huge_and_bad_roots(self):
        bad = [b'', b'[]', b'null', b'{', b'{"x":1,"x":2}', b'{"x":{"y":1,"y":2}}',
               b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e999}', b'{"x":' + b'9' * 102 + b'}',
               b'{"x":' + b'[' * 1200 + b'0' + b']' * 1200 + b'}', b'{"x":"\xff"}']
        for raw in bad:
            with self.subTest(raw_length=len(raw)):
                (self.directory / "pack.json").write_bytes(raw)
                with self.assertRaisesRegex(ValueError, "^invalid-json:"):
                    self._validate()
                result = self._cli(self.directory / "pack.json")
                self.assertEqual(2, result.returncode)
                self.assertTrue(json.loads(result.stderr)["error"].startswith("invalid-json:"))

    def test_real_integer_fields_and_finite_numeric_types(self):
        locations = [(name, ["schema_version"]) for name in ("pack", "protocol", "table", "report", "evidence")]
        locations += [("protocol", ["minimum_interval_n"]), ("protocol", ["samples", 0, "technical_replicates"]),
                      ("protocol", ["samples", 0, "wells", 0, "technical_replicate"]),
                      ("report", ["summary", 0, "n", "calibrator"]),
                      ("report", ["summary", 0, "censored_n", "calibrator"])]
        baseline = {name: (self.directory / (name + ".json")).read_bytes() for name in ("pack", "protocol", "table", "report", "evidence")}
        for target, path in locations:
            for value in (True, 1.0, "1", []):
                for name, raw in baseline.items():
                    (self.directory / (name + ".json")).write_bytes(raw)
                self._edit(target, path, value)
                self._refresh()
                with self.subTest(target=target, path=path, value=value), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                    self._validate()
        protocol, table = _read(FIXTURE / "protocol.json"), _read(FIXTURE / "table.json")
        for value in (True, None, [], {}, "20", float("nan"), float("inf")):
            table["rows"][0]["cq"] = value
            with self.subTest(cq=value), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                qpcr.reference_computation(protocol, table)

    def test_nonregular_symlink_device_directory_fifo_and_oversized(self):
        path = self.directory / "table.json"
        saved = path.read_bytes()
        for kind in ("fifo", "directory", "symlink", "oversized"):
            path.unlink()
            if kind == "fifo":
                os.mkfifo(path)
            elif kind == "directory":
                path.mkdir()
            elif kind == "symlink":
                path.symlink_to("protocol.json")
            else:
                with path.open("wb") as handle:
                    handle.truncate(qpcr.MAX_BYTES + 1)
            with self.subTest(kind=kind):
                result = self._cli(self.directory / "pack.json")
                self.assertEqual(2, result.returncode)
                self.assertTrue(json.loads(result.stderr)["error"].startswith("input-file:"))
            if kind == "directory":
                path.rmdir()
            else:
                path.unlink()
            path.write_bytes(saved)
        with patch.object(qpcr.os, "lstat", return_value=os.stat(os.devnull)):
            with self.assertRaisesRegex(ValueError, "^input-root:"):
                self._validate()

    def test_canonical_paths_and_symlinked_component(self):
        original = _read(self.directory / "pack.json")
        for value in ("../table.json", "/table.json", "a\\table.json", "./table.json", "a//table.json", "C:table.json", ".", [], ""):
            pack = copy.deepcopy(original)
            pack["table"]["path"] = value
            _write(self.directory / "pack.json", pack)
            with self.subTest(path=value), self.assertRaisesRegex(ValueError, "^(?:input-path|invalid-record):"):
                self._validate()
        (self.directory / "linked").symlink_to(self.directory, target_is_directory=True)
        pack = copy.deepcopy(original)
        pack["table"]["path"] = "linked/table.json"
        _write(self.directory / "pack.json", pack)
        with self.assertRaisesRegex(ValueError, "^input-file:"):
            self._validate()

    def test_hashes_invalid_or_null_and_protocol_checked_before_table(self):
        original = _read(self.directory / "pack.json")
        for value in (None, [], 0, "", "0" * 63, "0" * 64, "A" * 64, "g" * 64):
            pack = copy.deepcopy(original)
            pack["table"]["sha256"] = value
            _write(self.directory / "pack.json", pack)
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "^input-hash:"):
                self._validate()
        pack = copy.deepcopy(original)
        pack["frozen_before_cq_read"] = False
        pack["table"]["path"] = "missing.json"
        _write(self.directory / "pack.json", pack)
        with self.assertRaisesRegex(ValueError, "^protocol-freeze:"):
            self._validate()

    def test_unique_reads_parse_cache_and_final_rechecks(self):
        reads = []
        parsed = []
        original = qpcr._json
        def counted(raw, allowance):
            parsed.append(raw)
            return original(raw, allowance)
        with _track_reads(reads), patch.object(qpcr, "_json", counted):
            result = self._validate()
        self.assertEqual(5, len(parsed))
        self.assertEqual(10, len(reads))
        self.assertEqual(5, len(result["inputs"]))

    def test_raw_and_json_aggregate_budgets_before_read_and_parse(self):
        total = sum((self.directory / (name + ".json")).stat().st_size for name in ("pack", "protocol", "table", "report", "evidence"))
        with patch.object(qpcr, "MAX_TOTAL_BYTES", total):
            self._validate()
        for limit in (0, total - 1):
            reads = []
            with patch.object(qpcr, "MAX_TOTAL_BYTES", limit), _track_reads(reads):
                with self.assertRaisesRegex(ValueError, "^input-limit:"):
                    self._validate()
            self.assertLessEqual(sum(reads), limit)
        root = qpcr._Bundle(self.directory)
        try:
            self._validate()
            for name in ("pack", "protocol", "table", "report", "evidence"):
                root.load(name + ".json")
            allowance = root.total_nodes
        finally:
            root.close()
        with patch.object(qpcr, "MAX_TOTAL_NODES", allowance), patch.object(qpcr.re, "findall", side_effect=AssertionError("match-list allocation")):
            self._validate()
        for limit in (0, allowance - 1):
            with patch.object(qpcr, "MAX_TOTAL_NODES", limit):
                with self.assertRaisesRegex(ValueError, "^input-limit:"):
                    self._validate()

    def test_hardlinks_share_reads_parsing_and_budgets(self):
        source = self.directory / "source.json"
        source.write_bytes(b'{"fixture":"synthetic fixture"}')
        alias = self.directory / "alias.json"
        os.link(source, alias)
        reads = []
        with patch.object(qpcr, "MAX_TOTAL_BYTES", source.stat().st_size), _track_reads(reads):
            store = qpcr._Bundle(self.directory)
            try:
                first = store.load(source.name)
                nodes = store.total_nodes
                self.assertIs(first, store.load(alias.name))
                self.assertEqual(nodes, store.total_nodes)
                self.assertEqual(1, len(reads))
                store.finish()
                self.assertEqual(2, len(reads))
                alias.unlink()
                alias.write_bytes(source.read_bytes())
                with self.assertRaisesRegex(ValueError, "^input-changed:"):
                    store.finish()
            finally:
                store.close()

    def test_dimension_limits_equal_zero_empty_malformed_and_oversize(self):
        protocol, table = _read(self.directory / "protocol.json"), _read(self.directory / "table.json")
        limits = [("MAX_SAMPLES", 6), ("MAX_GENES", 2), ("MAX_WELLS", 26),
                  ("MAX_DILUTIONS", 3), ("MAX_TECHNICAL_REPLICATES", 2)]
        for name, count in limits:
            with self.subTest(name=name), patch.object(qpcr, name, count):
                qpcr.reference_computation(protocol, table)
            with patch.object(qpcr, name, count - 1):
                with self.assertRaisesRegex(ValueError, "^(?:input-limit|invalid-record):"):
                    qpcr.reference_computation(protocol, table)
            with patch.object(qpcr, name, 0):
                with self.assertRaisesRegex(ValueError, "^(?:input-limit|invalid-record):"):
                    qpcr.reference_computation(protocol, table)
        for key in ("samples", "targets", "assays", "ntc_wells"):
            for value in ([], {}, None):
                invalid = copy.deepcopy(protocol)
                invalid[key] = value
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                    qpcr.reference_computation(invalid, table)
        table["rows"] = [{}] * (qpcr.MAX_WELLS + 1)
        with self.assertRaisesRegex(ValueError, "^input-limit:"):
            qpcr.reference_computation(protocol, table)
        with patch.object(qpcr, "MAX_ARTIFACTS", 5), patch.object(qpcr, "MAX_RECORDS", 1):
            self._validate()
        for name in ("MAX_ARTIFACTS", "MAX_RECORDS"):
            with patch.object(qpcr, name, 0):
                with self.assertRaisesRegex(ValueError, "^input-limit:"):
                    self._validate()

    def test_file_text_container_nesting_and_numeric_limit_edges(self):
        store = qpcr._Bundle(self.directory)
        try:
            file = self.directory / "edge.bin"
            file.write_bytes(b"")
            with patch.object(qpcr, "MAX_BYTES", 0), patch.object(qpcr, "MAX_TOTAL_BYTES", 0):
                store.load(file.name, parse=False)
            file = self.directory / "nonempty.bin"
            file.write_bytes(b"x")
            with patch.object(qpcr, "MAX_BYTES", 1):
                store.load(file.name, parse=False)
            with patch.object(qpcr, "MAX_BYTES", 0):
                with self.assertRaisesRegex(ValueError, "^input-file:"):
                    store.load("pack.json", parse=False)
        finally:
            store.close()
        for limit, value, succeeds in [(3, "abc", True), (2, "abc", False), (0, "x", False)]:
            with patch.object(qpcr, "MAX_TEXT", limit):
                if succeeds:
                    qpcr._json(json.dumps({"x": value}).encode(), 100)
                else:
                    with self.assertRaisesRegex(ValueError, "^input-limit:"):
                        qpcr._json(json.dumps({"x": value}).encode(), 100)
        with patch.object(qpcr, "MAX_ITEMS", 1):
            qpcr._json(b'{"x":[0]}', 100)
            with self.assertRaisesRegex(ValueError, "^input-limit:"):
                qpcr._json(b'{"x":[0,1]}', 100)
        with patch.object(qpcr, "MAX_DEPTH", 2):
            qpcr._json(b'{"x":[0]}', 100)
            with self.assertRaisesRegex(ValueError, "^invalid-json:"):
                qpcr._json(b'{"x":[[0]]}', 100)
        with patch.object(qpcr, "MAX_ITEMS", 0), patch.object(qpcr, "MAX_DEPTH", 0):
            qpcr._json(b'{}', 1)
            with self.assertRaisesRegex(ValueError, "^input-limit:"):
                qpcr._json(b'{"x":0}', 100)
        with patch.object(qpcr, "MAX_DEPTH", 0):
            with self.assertRaisesRegex(ValueError, "^invalid-json:"):
                qpcr._json(b'{"x":0}', 100)
        with patch.object(qpcr, "MAX_NUMBER", 2):
            qpcr._json(b'{"x":2}', 100)
            with self.assertRaisesRegex(ValueError, "^invalid-json:"):
                qpcr._json(b'{"x":3}', 100)
        qpcr._json(b'{"x":1e100}', 100)
        with self.assertRaisesRegex(ValueError, "^invalid-json:"):
            qpcr._json(b'{"x":1.01e100}', 100)

    def test_root_swap_after_lstat_before_open(self):
        parked = self.directory.parent / "parked"
        original = os.open
        def swapped(path, flags, *args, **kwargs):
            if path == self.directory.name and kwargs.get("dir_fd") is not None:
                self.directory.rename(parked)
                self.directory.symlink_to(parked, target_is_directory=True)
            return original(path, flags, *args, **kwargs)
        with patch.object(qpcr.os, "open", swapped):
            with self.assertRaisesRegex(ValueError, "^input-root:"):
                self._validate()

    def test_transient_ancestor_swap_cannot_redirect_reads(self):
        holder = self.directory.parent / "holder"
        nested = holder / "nested"
        shutil.copytree(FIXTURE, nested)
        parked = self.directory.parent / "parked-holder"
        outside = self.directory.parent / "outside"
        shutil.copytree(FIXTURE, outside / "nested")
        original = os.lstat
        attacked = []
        def swapped(path, *args, **kwargs):
            if path == holder.name and kwargs.get("dir_fd") is not None:
                if holder.is_symlink():
                    holder.unlink()
                    parked.rename(holder)
                info = original(path, *args, **kwargs)
                holder.rename(parked)
                holder.symlink_to(outside, target_is_directory=True)
                attacked.append(path)
                return info
            return original(path, *args, **kwargs)
        with patch.object(qpcr.os, "lstat", swapped):
            with self.assertRaisesRegex(ValueError, "^input-root:"):
                qpcr.validate_qpcr_relative_quantification_pack(nested / "pack.json")
        self.assertTrue(attacked)

    def test_parent_replaced_while_bundle_inode_is_preserved(self):
        holder = self.directory.parent / "holder"
        nested = holder / "nested"
        shutil.copytree(FIXTURE, nested)
        parked = self.directory.parent / "original-holder"
        original = qpcr._Bundle.finish
        def replaced(store):
            holder.rename(parked)
            holder.mkdir()
            (parked / "nested").rename(nested)
            return original(store)
        with patch.object(qpcr._Bundle, "finish", replaced):
            with self.assertRaisesRegex(ValueError, "^input-root:"):
                qpcr.validate_qpcr_relative_quantification_pack(nested / "pack.json")

    def test_input_replacement_growth_and_final_hash_change(self):
        original = qpcr._Bundle.finish
        def replaced(store):
            file = self.directory / "table.json"
            raw = file.read_bytes()
            file.unlink()
            file.write_bytes(raw)
            return original(store)
        with patch.object(qpcr._Bundle, "finish", replaced):
            with self.assertRaisesRegex(ValueError, "^input-changed:"):
                self._validate()
        self._refresh()
        original_fdopen = os.fdopen
        def grown(descriptor, *args, **kwargs):
            handle = original_fdopen(descriptor, *args, **kwargs)
            read = handle.read
            def grow(*args, **kwargs):
                raw = read(*args, **kwargs)
                with (self.directory / "pack.json").open("ab") as writer:
                    writer.write(b" ")
                return raw
            handle.read = grow
            return handle
        with patch.object(qpcr.os, "fdopen", grown):
            with self.assertRaisesRegex(ValueError, "^input-file:"):
                self._validate()

    def test_concurrent_calls_and_interruption_write_nothing(self):
        before = {p.relative_to(self.directory): p.read_bytes() for p in self.directory.rglob("*") if p.is_file()}
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self._validate(), range(2)))
        self.assertEqual(results[0], results[1])
        original = qpcr._Bundle.artifact
        def interrupted(store, descriptor, parse=True):
            if descriptor["path"] == "table.json":
                raise KeyboardInterrupt
            return original(store, descriptor, parse)
        with patch.object(qpcr._Bundle, "artifact", interrupted):
            with self.assertRaises(KeyboardInterrupt):
                self._validate()
        after = {p.relative_to(self.directory): p.read_bytes() for p in self.directory.rglob("*") if p.is_file()}
        self.assertEqual(before, after)


class QpcrMetadataTests(unittest.TestCase):
    def test_metadata_schema_inventory_seed_coverage_and_plan(self):
        skill = ROOT / "authored-skills/workflow-qpcr-relative-quantification"
        quality = _read(skill / "quality.json")
        self.assertEqual(["tests/test_workflow_qpcr_pack.py"], quality["test_files"])
        self.assertEqual({case["id"] for case in CASES}, set(quality["seeded_failures"]))
        for case in CASES:
            self.assertTrue(hasattr(QpcrSeededRefusalTests, "test_" + case["id"].replace("-", "_")))
        self.assertEqual(list(qpcr.STAGES), [step["id"] for step in _read(skill / "references/plan.json")["plan"]])
        self.assertEqual(7, len(quality["output_schemas"]))
        for path in [*skill.rglob("*.md"), *FIXTURE.rglob("*.md")]:
            if path.name != "SKILL.md":
                self.assertNotRegex(path.read_text(), r"\]\(")
        description = re.search(r'^description: (.*)$', (skill / "SKILL.md").read_text(), re.M).group(1)
        self.assertNotRegex(description.lower(), r"\b(?:workflow|analysis|statistics|pipeline)\b")
        for path in quality["acceptance_fixtures"]:
            self.assertTrue((ROOT / path).is_file(), path)


if __name__ == "__main__":
    unittest.main()
