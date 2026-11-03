"""Offline synthetic fixture acceptance, hand derivations and refusal controls."""
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

from codex_science import survival_pack as survival


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "workflow-survival-time-to-event"
CLI = ROOT / "scripts" / "validate_survival_pack.py"
CALL_TIMEOUT = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "30"))
CASES = json.loads((FIXTURE / "negative-cases.json").read_bytes())["cases"]


def _read(path):
    return json.loads(path.read_bytes())


def _write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")


def _identity(path):
    return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _track_reads(reads):
    original_fdopen = os.fdopen

    def opened(descriptor, *args, **kwargs):
        handle = original_fdopen(descriptor, *args, **kwargs)
        original_read = handle.read

        def read(*args, **kwargs):
            reads.append(os.fstat(handle.fileno()).st_size)
            return original_read(*args, **kwargs)

        handle.read = read
        return handle

    return patch.object(survival.os, "fdopen", opened)


class _FixtureTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name) / "fixture"
        shutil.copytree(FIXTURE, self.directory)

    def _refresh(self):
        protocol = self.directory / "protocol.json"
        report = _read(self.directory / "report.json")
        report["protocol_sha256"] = _identity(protocol)["sha256"]
        _write(self.directory / "report.json", report)
        evidence = _read(self.directory / "evidence.json")
        for record in evidence["records"]:
            record["source"]["sha256"] = hashlib.sha256(
                (self.directory / record["source"]["path"]).read_bytes()).hexdigest()
        _write(self.directory / "evidence.json", evidence)
        pack = _read(self.directory / "pack.json")
        for field in ("protocol", "cohort", "report"):
            pack[field] = _identity(self.directory / (field + ".json"))
        pack["evidence"] = [_identity(self.directory / "evidence.json")]
        pack["frozen_protocol_sha256"] = pack["protocol"]["sha256"]
        _write(self.directory / "pack.json", pack)

    def _edit(self, target, path, value):
        file = self.directory / (target + ".json")
        document = _read(file)
        owner = document
        for key in path[:-1]:
            owner = owner[key]
        owner[path[-1]] = value
        _write(file, document)

    def _case(self, case):
        for change in case["changes"]:
            self._edit(change["target"], change["path"], change["value"])
        self._refresh()

    def _validate(self):
        return survival.validate_survival_pack(self.directory / "pack.json")

    def _cli(self, *args):
        return subprocess.run([sys.executable, str(CLI), *map(str, args)],
                              text=True, capture_output=True, timeout=CALL_TIMEOUT)


class SurvivalMathTests(_FixtureTest):
    def test_planted_difference_expected_and_read_only(self):
        before = {p.relative_to(self.directory): p.read_bytes() for p in self.directory.rglob("*") if p.is_file()}
        result = self._validate()
        self.assertEqual(_read(self.directory / "expected.json"), result)
        self.assertLess(result["computation"]["log_rank"]["p_value"], 0.001)
        self.assertEqual("unavailable", result["computation"]["groups"]["B"]["median"])
        self.assertEqual("statistical-evidence-only", result["status"])
        self.assertEqual("unavailable", result["review"])
        self.assertEqual(list(survival.STAGES), result["stages"])
        after = {p.relative_to(self.directory): p.read_bytes() for p in self.directory.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_tiny_hand_derived_km_log_rank_and_ties(self):
        result = survival.validate_survival_pack(FIXTURE / "tiny" / "pack.json")
        self.assertEqual(_read(FIXTURE / "tiny" / "expected.json"), result)
        math_result = result["computation"]
        a = math_result["groups"]["A"]
        b = math_result["groups"]["B"]
        self.assertEqual([0.5, 0.5], [p["survival"] for p in a["curve"]])
        self.assertEqual([0.5, 0.0], [p["survival"] for p in b["curve"]])
        self.assertAlmostEqual(1 / 8, a["curve"][0]["greenwood_variance"])
        self.assertAlmostEqual(1 / 8, b["curve"][0]["greenwood_variance"])
        self.assertEqual([0, 0], b["curve"][-1]["log_log_interval"])
        self.assertEqual(1, a["median"])
        self.assertEqual(2, b["median"])
        log_rank = math_result["log_rank"]
        # t=1: E_A=1/2,V=1/4; t=2: E_A=1/3,V=2/9 (A censor retained).
        # t=3: only B at risk. O_A=1, E_A=5/6, V=17/36; chi-square=1/17.
        self.assertAlmostEqual(5 / 6, log_rank["expected"]["A"])
        self.assertAlmostEqual(17 / 36, log_rank["variance"])
        self.assertAlmostEqual(1 / 17, log_rank["chi_square"])
        self.assertAlmostEqual(math.erfc(1 / math.sqrt(34)), log_rank["p_value"])
        self.assertAlmostEqual(13 / 10, math_result["hazard_ratio"]["value"])
        # z_0.975=1.959963984540054; log-log SE=sqrt(1/2)/abs(log(1/2)).
        center = math.log(-math.log(0.5))
        width = 1.959963984540054 * math.sqrt(0.5) / abs(math.log(0.5))
        expected_ci = [math.exp(-math.exp(center + width)), math.exp(-math.exp(center - width))]
        for actual, expected in zip(a["curve"][0]["log_log_interval"], expected_ci):
            self.assertAlmostEqual(actual, expected)

    def test_censor_only_time_before_first_event(self):
        cohort = _read(FIXTURE / "tiny" / "cohort.json")
        cohort["rows"][1]["time"] = 0.5
        result = survival.compute_survival(cohort, _read(FIXTURE / "tiny" / "protocol.json"))
        point = result["groups"]["A"]["curve"][0]
        self.assertEqual(1, point["survival"])
        self.assertEqual([1, 1], point["log_log_interval"])
        self.assertEqual(0, point["greenwood_variance"])

    def test_zero_observed_events_ratio_unavailable(self):
        cohort = _read(FIXTURE / "tiny" / "cohort.json")
        cohort["rows"][0].update(event=0, censored=True)
        protocol = _read(FIXTURE / "tiny" / "protocol.json")
        protocol["maximum_censoring_imbalance"] = 1
        result = survival.compute_survival(cohort, protocol)
        self.assertEqual("unavailable", result["hazard_ratio"]["value"])
        self.assertEqual("unavailable", result["groups"]["A"]["median"])

    def test_degenerate_zero_variance_refused(self):
        cohort = _read(FIXTURE / "tiny" / "cohort.json")
        for row in cohort["rows"]:
            row.update(time=1, event=1, censored=False)
        with self.assertRaisesRegex(ValueError, "^degenerate-log-rank:"):
            survival.compute_survival(cohort, _read(FIXTURE / "tiny" / "protocol.json"))

    def test_exploratory_reversed_groups(self):
        report = _read(self.directory / "report.json")
        report.update(groups=["B", "A"], exploratory=True)
        report["hazard_ratio"]["value"] = 1 / report["hazard_ratio"]["value"]
        report["headline"] = "Exploratory hazard ratio in a synthetic fixture."
        _write(self.directory / "report.json", report)
        self._refresh()
        self.assertTrue(self._validate()["exploratory"])
        self._edit("report", ["test"], "weighted-log-rank")
        self._refresh()
        with self.assertRaisesRegex(ValueError, "^unsupported-test:"):
            self._validate()


class SurvivalDefectTests(_FixtureTest):
    def test_all_seeded_refusals_through_cli(self):
        for case in CASES:
            with self.subTest(case=case["name"]):
                for filename in ("pack", "protocol", "cohort", "report", "evidence"):
                    shutil.copyfile(FIXTURE / (filename + ".json"), self.directory / (filename + ".json"))
                self._case(case)
                result = self._cli(self.directory / "pack.json")
                self.assertEqual(2, result.returncode, result.stderr)
                self.assertEqual("", result.stderr)
                self.assertTrue(json.loads(result.stdout)["error"].startswith(case["code"] + ":"))

    def test_claim_wording_families_and_status_types(self):
        original = _read(self.directory / "report.json")
        words = ("causal", "mechanistic", "therapy", "clinical", "efficacy", "effective", "treatment",
                 "cure", "prevention", "recommendation", "prescription", "binding", "affinity", "inhibition",
                 "activation", "regulation", "drive", "drives", "driving", "induction", "physical validity")
        for word in words:
            with self.subTest(word=word):
                report = copy.deepcopy(original)
                report["claims"][0]["text"] = "Synthetic fixture " + word
                _write(self.directory / "report.json", report)
                self._refresh()
                with self.assertRaisesRegex(ValueError, "^claim-overreach:"):
                    self._validate()
        for field in ("status", "kind", "id"):
            for value in ([], {}, None, 1, True):
                with self.subTest(field=field, value=value):
                    report = copy.deepcopy(original)
                    report["claims"][0][field] = value
                    _write(self.directory / "report.json", report)
                    self._refresh()
                    with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                        self._validate()

    def test_all_positive_statuses_and_record_labels(self):
        report = _read(self.directory / "report.json")
        evidence = _read(self.directory / "evidence.json")
        for status in ("supported", "replicated", "suggestive"):
            for field in ("kind", "result"):
                for label in ("review-approval", "computed-agreement"):
                    with self.subTest(status=status, field=field, label=label):
                        report["claims"][0]["status"] = status
                        _write(self.directory / "report.json", report)
                        altered = copy.deepcopy(evidence)
                        altered["records"][0][field] = label
                        _write(self.directory / "evidence.json", altered)
                        self._refresh()
                        with self.assertRaisesRegex(ValueError, "^non-evidence-support:"):
                            self._validate()

    def test_external_alias_by_hash_and_each_origin(self):
        shutil.copyfile(self.directory / "cohort.json", self.directory / "renamed.json")
        for origin in ("external", "independent", "preregistered"):
            self._edit("evidence", ["records", 0, "origin"], origin)
            self._edit("evidence", ["records", 0, "source", "path"], "renamed.json")
            self._refresh()
            with self.assertRaisesRegex(ValueError, "^external-alias:"):
                self._validate()
        (self.directory / "external.txt").write_text("Separate synthetic fixture reference.\n")
        self._edit("evidence", ["records", 0, "source", "path"], "external.txt")
        self._refresh()
        self.assertEqual("statistical-evidence-only", self._validate()["status"])

    def test_unavailable_evidence_requires_unavailable_claim(self):
        original = _read(self.directory / "evidence.json")
        for field in ("kind", "result"):
            evidence = copy.deepcopy(original)
            missing = copy.deepcopy(evidence["records"][0])
            missing.update(id="E2", **{field: "unavailable"})
            evidence["records"].append(missing)
            _write(self.directory / "evidence.json", evidence)
            for status in sorted(survival.STATUSES):
                with self.subTest(field=field, status=status):
                    self._edit("report", ["claims", 0, "status"], status)
                    self._edit("report", ["claims", 0, "evidence"], ["E1", "E2"])
                    self._refresh()
                    if status == "unavailable":
                        self.assertEqual(status, self._validate()["claims"][0]["status"])
                    else:
                        with self.assertRaisesRegex(ValueError, "^unavailable-evidence:"):
                            self._validate()

    def test_replication_requires_two_distinct_declared_sources(self):
        self._edit("report", ["claims", 0, "status"], "replicated")
        self._refresh()
        with self.assertRaisesRegex(ValueError, "^claim-replication:"):
            self._validate()
        first = _read(self.directory / "evidence.json")["records"][0]
        separate = self.directory / "separate.txt"
        separate.write_text("Separate synthetic fixture observations.\n")
        second = dict(first, id="E2", source=_identity(separate))
        evidence = _read(self.directory / "evidence.json")
        evidence["records"].append(second)
        _write(self.directory / "evidence.json", evidence)
        self._edit("report", ["claims", 0, "evidence"], ["E1", "E2"])
        self._refresh()
        with self.assertRaisesRegex(ValueError, "^claim-replication:"):
            self._validate()
        for origin in ("external", "independent", "preregistered"):
            with self.subTest(origin=origin):
                self._edit("evidence", ["records", 1, "origin"], origin)
                self._refresh()
                self.assertEqual("replicated", self._validate()["claims"][0]["status"])
        self._edit("report", ["claims", 0, "evidence"], ["E2"])
        self._refresh()
        with self.assertRaisesRegex(ValueError, "^claim-replication:"):
            self._validate()
        self._edit("report", ["claims", 0, "evidence"], ["E1", "E2"])
        for alias in ("cohort.json", "renamed.json"):
            shutil.copyfile(self.directory / "cohort.json", self.directory / "renamed.json")
            self._edit("evidence", ["records", 1, "source", "path"], alias)
            self._refresh()
            with self.assertRaisesRegex(ValueError, "^external-alias:"):
                self._validate()


def _seeded_test(case):
    def test(self):
        self._case(case)
        with self.assertRaisesRegex(ValueError, "^" + case["code"] + ":"):
            self._validate()
    test.__doc__ = "Refuse synthetic fixture: " + case["name"]
    return test


for _case_record in CASES:
    setattr(SurvivalDefectTests, "test_" + _case_record["name"].replace("-", "_"), _seeded_test(_case_record))


class SurvivalIOTests(_FixtureTest):
    def test_each_input_is_read_once_and_rechecked_once(self):
        from collections import Counter
        reads = Counter()
        original = survival._Bundle._read
        def tracked(store, name):
            reads[name] += 1
            return original(store, name)
        with patch.object(survival._Bundle, "_read", tracked):
            result = self._validate()
        self.assertEqual({item["path"] for item in result["inputs"]}, set(reads))
        self.assertEqual({2}, set(reads.values()))

    def test_cli_success_errors_and_no_output_option(self):
        result = self._cli(self.directory / "pack.json")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(self._validate(), json.loads(result.stdout))
        for args in ((), ("missing.json",), (str(self.directory / "pack.json"), "--output", "result.json")):
            with self.subTest(args=args):
                result = self._cli(*args)
                self.assertEqual(2, result.returncode)
                self.assertEqual("refused", json.loads(result.stdout)["status"])
                self.assertNotIn("Traceback", result.stderr)
        help_result = self._cli("--help")
        self.assertEqual(0, help_result.returncode)
        self.assertIn("bundle", help_result.stdout)
        self.assertNotIn("--output", help_result.stdout)

    def test_nonregular_symlink_and_oversized_inputs(self):
        file = self.directory / "cohort.json"
        data = file.read_bytes()
        file.unlink()
        os.mkfifo(file)
        result = self._cli(self.directory / "pack.json")
        self.assertEqual(2, result.returncode)
        self.assertTrue(json.loads(result.stdout)["error"].startswith("input-file:"))
        file.unlink()
        file.mkdir()
        with self.assertRaisesRegex(ValueError, "^input-file:"):
            self._validate()
        file.rmdir()
        file.symlink_to(self.directory / "tiny" / "cohort.json")
        with self.assertRaisesRegex(ValueError, "^input-file:"):
            self._validate()
        file.unlink()
        file.write_bytes(data)
        with patch.object(survival, "MAX_BYTES", len(data) - 1):
            with self.assertRaisesRegex(ValueError, "^input-file:"):
                self._validate()
        with file.open("wb") as handle:
            handle.truncate(survival.MAX_BYTES + 1)
        with self.assertRaisesRegex(ValueError, "^input-file:"):
            self._validate()

    def test_canonical_paths_and_symlink_component(self):
        pack = _read(self.directory / "pack.json")
        for name in ("../cohort.json", "./cohort.json", "cohort.json/", "a//b", "a\\b", str(self.directory / "cohort.json"), "C:cohort.json", "."):
            with self.subTest(path=name):
                changed = copy.deepcopy(pack)
                changed["cohort"]["path"] = name
                _write(self.directory / "pack.json", changed)
                with self.assertRaisesRegex(ValueError, "^input-path:"):
                    self._validate()
        (self.directory / "alias").symlink_to(self.directory / "tiny", target_is_directory=True)
        pack["cohort"]["path"] = "alias/cohort.json"
        _write(self.directory / "pack.json", pack)
        with self.assertRaisesRegex(ValueError, "^input-file:"):
            self._validate()

    def test_strict_json_and_huge_numbers(self):
        file = self.directory / "pack.json"
        samples = (b'{"x":1,"x":2}', b'{"x":{"a":1,"a":2}}', b'{"x":NaN}', b'{"x":Infinity}',
                   b'{"x":1e400}', b'{"x":' + b'9' * 5000 + b'}', b'[]', b'{', b'\xff',
                   b'{"x":' + b'[' * 2000 + b'0' + b']' * 2000 + b'}')
        for raw in samples:
            with self.subTest(raw=raw[:60]):
                file.write_bytes(raw)
                with self.assertRaisesRegex(ValueError, "^invalid-json:"):
                    self._validate()
        file.write_text('{"x":"' + 'x' * (survival.MAX_STRING + 1) + '"}')
        with self.assertRaisesRegex(ValueError, "^invalid-record:"):
            self._validate()
        file.write_text('{"x":' + '[' * (survival.MAX_DEPTH + 1) + '0' + ']' * (survival.MAX_DEPTH + 1) + '}')
        with self.assertRaisesRegex(ValueError, "^invalid-json:"):
            self._validate()

    def test_artifact_replaced_at_final_recheck(self):
        finish = survival._Bundle.finish
        def replaced(store):
            path = self.directory / "cohort.json"
            replacement = self.directory / "replacement.json"
            replacement.write_bytes(path.read_bytes())
            replacement.replace(path)
            return finish(store)
        with patch.object(survival._Bundle, "finish", replaced):
            with self.assertRaisesRegex(ValueError, "^input-changed:"):
                self._validate()

    def test_root_swap_at_exact_open(self):
        original = os.open
        parked = self.directory.parent / "parked"
        def swapped(path, flags, *args, **kwargs):
            if path == self.directory.name and kwargs.get("dir_fd") is not None:
                self.directory.rename(parked)
                self.directory.symlink_to(parked, target_is_directory=True)
            return original(path, flags, *args, **kwargs)
        with patch.object(survival.os, "open", swapped):
            with self.assertRaisesRegex(ValueError, "^input-root:"):
                self._validate()

    def test_ancestor_swap_after_lstat_before_open(self):
        holder = self.directory.parent / "holder"
        holder.mkdir()
        nested = holder / "nested"
        shutil.copytree(FIXTURE, nested)
        parked = self.directory.parent / "parked-holder"
        original = os.open
        def swapped(path, flags, *args, **kwargs):
            if path == holder.name and kwargs.get("dir_fd") is not None:
                holder.rename(parked)
                holder.symlink_to(parked, target_is_directory=True)
            return original(path, flags, *args, **kwargs)
        with patch.object(survival.os, "open", swapped):
            with self.assertRaisesRegex(ValueError, "^input-root:"):
                survival.validate_survival_pack(nested / "pack.json")

    def test_ancestor_restored_only_during_lstat_cannot_escape(self):
        holder = self.directory.parent / "holder"
        nested = holder / "nested"
        shutil.copytree(FIXTURE, nested)
        outside = self.directory.parent / "outside"
        shutil.copytree(FIXTURE, outside / "nested")
        report_path = outside / "nested" / "report.json"
        report = _read(report_path)
        report["claims"][0]["text"] = "Observations from outside the selected bundle."
        _write(report_path, report)
        pack_path = outside / "nested" / "pack.json"
        pack = _read(pack_path)
        pack["report"] = _identity(report_path)
        _write(pack_path, pack)
        parked = self.directory.parent / "parked-holder"
        original_open, original_lstat = os.open, os.lstat
        attacked = []

        def inspected(path, *args, **kwargs):
            if Path(path) == holder or (path == holder.name and kwargs.get("dir_fd") is not None):
                if holder.is_symlink():
                    holder.unlink()
                    parked.rename(holder)
                info = original_lstat(path, *args, **kwargs)
                holder.rename(parked)
                holder.symlink_to(outside, target_is_directory=True)
                return info
            return original_lstat(path, *args, **kwargs)

        def opened(path, flags, *args, **kwargs):
            if Path(path) == nested or (path == holder.name and kwargs.get("dir_fd") is not None):
                attacked.append(path)
            return original_open(path, flags, *args, **kwargs)

        with patch.object(survival.os, "lstat", inspected), patch.object(survival.os, "open", opened):
            with self.assertRaisesRegex(ValueError, "^input-root:"):
                survival.validate_survival_pack(nested / "pack.json")
        self.assertTrue(attacked)

    def test_referenced_source_digest_cannot_be_null_or_malformed(self):
        (self.directory / "separate.txt").write_text("Separate synthetic fixture observations.\n")
        for name in ("cohort.json", "separate.txt"):
            for digest in (None, 0, [], {}, "", "0" * 63, "0" * 64, "0" * 65, "A" * 64, "g" * 64):
                with self.subTest(name=name, digest=digest):
                    evidence = _read(self.directory / "evidence.json")
                    evidence["records"][0]["source"] = {"path": name, "sha256": digest}
                    _write(self.directory / "evidence.json", evidence)
                    pack = _read(self.directory / "pack.json")
                    pack["evidence"] = [_identity(self.directory / "evidence.json")]
                    _write(self.directory / "pack.json", pack)
                    code = "input-hash" if digest is None else "(?:input-hash|invalid-record)"
                    with self.assertRaisesRegex(ValueError, "^" + code + ":"):
                        self._validate()

    def test_aggregate_budget_checked_before_read_and_at_equality(self):
        total = sum((self.directory / (name + ".json")).stat().st_size
                    for name in ("pack", "protocol", "report", "cohort", "evidence"))
        reads = []
        with patch.object(survival, "MAX_TOTAL_BYTES", total, create=True):
            self.assertEqual(_read(self.directory / "expected.json"), self._validate())
        for limit in (0, total - 1):
            with self.subTest(limit=limit), patch.object(survival, "MAX_TOTAL_BYTES", limit, create=True):
                reads.clear()
                with _track_reads(reads):
                    with self.assertRaisesRegex(ValueError, "^input-limit:"):
                        self._validate()
                self.assertLessEqual(sum(reads), limit)

    def test_hardlink_aliases_share_reads_and_aggregate_budget(self):
        file = self.directory / "source.bin"
        file.write_bytes(b"Synthetic fixture source.")
        alias = self.directory / "alias.bin"
        os.link(file, alias)
        later_alias = self.directory / "later.bin"
        os.link(file, later_alias)
        distinct = self.directory / "distinct.bin"
        distinct.write_bytes(file.read_bytes())
        size = file.stat().st_size
        reads = []
        with patch.object(survival, "MAX_TOTAL_BYTES", size, create=True), _track_reads(reads):
            store = survival._Bundle(self.directory)
            try:
                expected = hashlib.sha256(b"Synthetic fixture source.").hexdigest()
                self.assertEqual(expected, store.artifact(_identity(file), parse=False))
                self.assertEqual(expected, store.artifact(_identity(alias), parse=False))
                self.assertEqual(1, len(reads))
                store.finish()
                self.assertEqual(2, len(reads))
                with self.assertRaisesRegex(ValueError, "^input-limit:"):
                    store.artifact(_identity(distinct), parse=False)
                self.assertEqual(2, len(reads))
                distinct.replace(alias)
                with self.assertRaisesRegex(ValueError, "^input-changed:"):
                    store.finish()
                file.write_bytes(b"Changed synthetic fixture source.")
                with self.assertRaisesRegex(ValueError, "^input-changed:"):
                    store.artifact(_identity(later_alias), parse=False)
            finally:
                store.close()

    def test_zero_budget_allows_empty_source_but_not_nonempty_source(self):
        empty = self.directory / "empty.bin"
        empty.write_bytes(b"")
        malformed = self.directory / "malformed.json"
        malformed.write_bytes(b"{")
        with patch.object(survival, "MAX_TOTAL_BYTES", 0, create=True):
            store = survival._Bundle(self.directory)
            try:
                self.assertEqual(hashlib.sha256(b"").hexdigest(),
                                 store.artifact(_identity(empty), parse=False))
                with self.assertRaisesRegex(ValueError, "^input-limit:"):
                    store.artifact(_identity(malformed))
            finally:
                store.close()
        with patch.object(survival, "MAX_TOTAL_BYTES", 1, create=True):
            store = survival._Bundle(self.directory)
            try:
                with self.assertRaisesRegex(ValueError, "^invalid-json:"):
                    store.artifact(_identity(malformed))
            finally:
                store.close()

    def test_root_replaced_at_final_recheck(self):
        finish = survival._Bundle.finish
        parked = self.directory.parent / "parked"
        def replaced(store):
            self.directory.rename(parked)
            self.directory.mkdir()
            return finish(store)
        with patch.object(survival._Bundle, "finish", replaced):
            with self.assertRaisesRegex(ValueError, "^input-root:"):
                self._validate()

    def test_initial_file_swap_and_growth(self):
        original_open = os.open
        file = self.directory / "cohort.json"
        def swapped(path, flags, *args, **kwargs):
            if path == "cohort.json":
                file.unlink()
                os.mkfifo(file)
            return original_open(path, flags, *args, **kwargs)
        with patch.object(survival.os, "open", swapped):
            with self.assertRaisesRegex(ValueError, "^input-file:"):
                self._validate()
        file.unlink()
        shutil.copyfile(FIXTURE / "cohort.json", file)
        original_fstat = os.fstat
        def growing(fd):
            info = original_fstat(fd)
            if info.st_ino == os.lstat(file).st_ino:
                with file.open("ab") as handle:
                    handle.write(b" ")
            return info
        with patch.object(survival.os, "fstat", growing):
            with self.assertRaisesRegex(ValueError, "^input-file:"):
                self._validate()

    def test_hash_binding_and_protocol_before_cohort(self):
        self._edit("pack", ["protocol", "sha256"], "0" * 64)
        with self.assertRaisesRegex(ValueError, "^input-hash:"):
            self._validate()
        self._refresh()
        self._edit("pack", ["frozen_before_table_read"], False)
        original = survival._Bundle.load
        loaded = []
        def tracked(store, name, *args, **kwargs):
            loaded.append(name)
            return original(store, name, *args, **kwargs)
        with patch.object(survival._Bundle, "load", tracked):
            with self.assertRaisesRegex(ValueError, "^protocol-freeze:"):
                self._validate()
        self.assertNotIn("cohort.json", loaded)

    def test_two_calls_and_concurrent_readers_leave_no_files(self):
        from concurrent.futures import ThreadPoolExecutor
        before = sorted(p.relative_to(self.directory) for p in self.directory.rglob("*"))
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self._validate) for _ in range(2)]
            values = [future.result(timeout=CALL_TIMEOUT) for future in futures]
        self.assertEqual(values[0], values[1])
        self.assertEqual(before, sorted(p.relative_to(self.directory) for p in self.directory.rglob("*")))


class SurvivalContractTests(_FixtureTest):
    def test_unavailable_ratio_report_and_time_limits(self):
        cohort = _read(self.directory / "cohort.json")
        protocol = _read(self.directory / "protocol.json")
        for row in cohort["rows"]:
            if row["group"] == "B":
                row.update(event=0, censored=True)
        protocol["maximum_censoring_imbalance"] = 1
        computed = survival.compute_survival(cohort, protocol)
        self.assertEqual("unavailable", computed["hazard_ratio"]["value"])
        report = _read(self.directory / "report.json")
        report.update(significant=computed["significant"], hazard_ratio=computed["hazard_ratio"],
                      censoring_fractions=computed["censoring_fractions"])
        _write(self.directory / "report.json", report)
        _write(self.directory / "cohort.json", cohort)
        _write(self.directory / "protocol.json", protocol)
        self._refresh()
        self._validate()
        self._edit("report", ["hazard_ratio", "value"], 0)
        self._refresh()
        with self.assertRaisesRegex(ValueError, "^hazard-unavailable:"):
            self._validate()
        for alpha in (1e-12, 0.5):
            survival.compute_survival(cohort, dict(protocol, alpha=alpha))
        for value in (1e12, 1e-100):
            cohort["rows"][0]["time"] = value
            survival.compute_survival(cohort, protocol)
        cohort["rows"][0]["time"] = 1e12 + 1
        with self.assertRaisesRegex(ValueError, "^invalid-record:"):
            survival.compute_survival(cohort, protocol)

    def test_dimension_limits_equal_zero_empty_malformed_and_oversize(self):
        cohort = _read(self.directory / "cohort.json")
        protocol = _read(self.directory / "protocol.json")
        size = len(cohort["rows"])
        with patch.object(survival, "MAX_ROWS", size):
            self.assertTrue(survival.compute_survival(cohort, protocol)["significant"])
        with patch.object(survival, "MAX_ROWS", size - 1):
            with self.assertRaisesRegex(ValueError, "^input-limit:"):
                survival.compute_survival(cohort, protocol)
        for value in ([], None, {}, 0):
            with self.subTest(rows=value):
                changed = copy.deepcopy(cohort)
                changed["rows"] = value
                with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                    survival.compute_survival(changed, protocol)
        changed = copy.deepcopy(cohort)
        changed["rows"] = [cohort["rows"][0]] * (survival.MAX_ROWS + 1)
        with self.assertRaisesRegex(ValueError, "^input-limit:"):
            survival.compute_survival(changed, protocol)
        report = _read(self.directory / "report.json")
        with patch.object(survival, "MAX_RECORDS", len(report["claims"])):
            self._validate()
        with patch.object(survival, "MAX_RECORDS", len(report["claims"]) - 1):
            with self.assertRaisesRegex(ValueError, "^input-limit:"):
                self._validate()
        with patch.object(survival, "MAX_RECORDS", 0):
            with self.assertRaisesRegex(ValueError, "^input-limit:"):
                self._validate()
        with patch.object(survival, "MAX_STRING", 3):
            survival._text("abc", "edge")
            with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                survival._text("abcd", "edge")

    def test_byte_depth_and_empty_collection_edges(self):
        file = self.directory / "limit.json"
        file.write_bytes(b"{}")
        store = survival._Bundle(self.directory)
        try:
            with patch.object(survival, "MAX_BYTES", 2):
                self.assertEqual({}, store.load(file.name))
                store.finish()
            with patch.object(survival, "MAX_BYTES", 1):
                with self.assertRaisesRegex(ValueError, "^input-file:"):
                    store._read(file.name)
        finally:
            store.close()
        with patch.object(survival, "MAX_DEPTH", 2):
            self.assertEqual({"x": [0]}, survival._json(b'{"x":[0]}'))
            with self.assertRaisesRegex(ValueError, "^invalid-json:"):
                survival._json(b'{"x":[[0]]}')
        with patch.object(survival, "MAX_DEPTH", 0):
            self.assertEqual({}, survival._json(b'{}'))
        self._edit("report", ["claims"], [])
        self._refresh()
        self._edit("pack", ["evidence"], [])
        with patch.object(survival, "MAX_RECORDS", 0):
            self.assertEqual([], self._validate()["claims"])

    def test_every_declared_integer_and_numeric_type(self):
        protocol = _read(self.directory / "protocol.json")
        cohort = _read(self.directory / "cohort.json")
        for field in ("minimum_events", "minimum_subjects_per_group"):
            for value in (True, 8.0, "8", [], 0, -1, float("nan"), float("inf")):
                with self.subTest(field=field, value=value):
                    changed = copy.deepcopy(protocol)
                    changed[field] = value
                    with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                        survival.compute_survival(cohort, changed)
        for value in (True, 1.0, "1", [], -1, 2):
            changed = copy.deepcopy(cohort)
            changed["rows"][0]["event"] = value
            with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                survival.compute_survival(changed, protocol)
        for field in ("time", "group_assignment_time"):
            for value in (True, "1", [], float("nan"), float("inf")):
                changed = copy.deepcopy(cohort)
                changed["rows"][0][field] = value
                with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                    survival.compute_survival(changed, protocol)

    def test_frozen_threshold_edges_and_minimum_events(self):
        cohort = _read(self.directory / "cohort.json")
        protocol = _read(self.directory / "protocol.json")
        for threshold in (0.5, 1):
            changed = dict(protocol, maximum_censoring_imbalance=threshold)
            survival.compute_survival(cohort, changed)
        for threshold in (0, math.nextafter(0.5, 0)):
            with self.assertRaisesRegex(ValueError, "^censoring-imbalance:"):
                survival.compute_survival(cohort, dict(protocol, maximum_censoring_imbalance=threshold))
        balanced = _read(FIXTURE / "tiny" / "cohort.json")
        balanced["rows"][-1].update(event=0, censored=True)
        survival.compute_survival(balanced, dict(protocol, minimum_events=2, maximum_censoring_imbalance=0))
        events = sum(row["event"] for row in cohort["rows"])
        survival.compute_survival(cohort, dict(protocol, minimum_events=events))
        with self.assertRaisesRegex(ValueError, "^insufficient-events:"):
            survival.compute_survival(cohort, dict(protocol, minimum_events=events + 1))
        with self.assertRaisesRegex(ValueError, "^insufficient-subjects:"):
            survival.compute_survival(cohort, dict(protocol, minimum_subjects_per_group=17))
        survival.compute_survival(cohort, dict(protocol, minimum_subjects_per_group=16))
        for field in ("alpha", "maximum_censoring_imbalance"):
            for value in (True, "0.05", [], -1, 2):
                with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                    survival.compute_survival(cohort, dict(protocol, **{field: value}))

    def test_structural_field_types_have_labelled_refusals(self):
        originals = {name: _read(self.directory / (name + ".json"))
                     for name in ("pack", "protocol", "cohort", "report", "evidence")}
        mutations = [
            ("pack", ["evidence"], {}), ("pack", ["protocol"], []),
            ("protocol", ["groups"], [[], "B"]), ("protocol", ["groups"], []),
            ("protocol", ["groups"], ["A", "A"]), ("protocol", ["groups"], ["A"]),
            ("cohort", ["rows", 0, "group"], []), ("cohort", ["rows", 0, "subject_id"], {}),
            ("cohort", ["rows", 0, "censored"], 0),
            ("report", ["claims"], {}), ("report", ["claims", 0, "evidence"], [[]]),
            ("report", ["exploratory"], 1), ("report", ["significant"], 1),
            ("report", ["hazard_ratio", "proportional_hazards_claim"], 0),
            ("evidence", ["records"], {}), ("evidence", ["records", 0, "origin"], []),
            ("evidence", ["records", 0, "id"], []), ("evidence", ["records", 0, "result"], []),
        ]
        for target, path, value in mutations:
            with self.subTest(target=target, path=path):
                for name, original in originals.items():
                    _write(self.directory / (name + ".json"), original)
                self._edit(target, path, value)
                if target != "pack" and target != "evidence":
                    self._refresh()
                elif target == "evidence":
                    pack = _read(self.directory / "pack.json")
                    pack["evidence"] = [_identity(self.directory / "evidence.json")]
                    _write(self.directory / "pack.json", pack)
                with self.assertRaisesRegex(ValueError, "^[a-z][a-z-]*:"):
                    self._validate()
        for path in (None, [], "bad\x00path", "bad\ud800path"):
            with self.assertRaisesRegex(ValueError, "^input-path:"):
                survival.validate_survival_pack(path)

    def test_group_labels_with_spaces(self):
        protocol = _read(self.directory / "protocol.json")
        cohort = _read(self.directory / "cohort.json")
        protocol["groups"] = ["group A", "group B"]
        for row in cohort["rows"]:
            row["group"] = "group " + row["group"]
        result = survival.compute_survival(cohort, protocol)
        self.assertEqual({"group A", "group B"}, set(result["groups"]))

    def test_metadata_plan_schemas_and_failure_coverage(self):
        skill = ROOT / "authored-skills" / "workflow-survival-time-to-event"
        quality = _read(skill / "quality.json")
        self.assertEqual("L4", quality["declared_maturity"])
        self.assertEqual({case["name"] for case in CASES}, set(quality["seeded_failures"]))
        self.assertEqual(["tests/test_workflow_survival_pack.py"], quality["test_files"])
        plan = _read(skill / "references" / "plan.json")["plan"]
        self.assertEqual(list(survival.STAGES), [step["id"] for step in plan])
        for step in plan:
            self.assertEqual({"id", "description", "status"}, set(step))
        for text in ((skill / "references" / "stages.md").read_text(), " ".join(quality["limitations"])):
            self.assertIn(survival.WORDING_FAMILIES, text)
        self.assertEqual(6, len(quality["output_schemas"]))


if __name__ == "__main__":
    unittest.main()
