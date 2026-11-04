"""Offline synthetic fixtures, hand calculations, seeded refusals and input races."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

try:
    from codex_science import gene_set_overrepresentation_pack as gso
except ImportError:
    gso = None

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "workflow-gene-set-overrepresentation"
CLI = ROOT / "scripts" / "validate_gene_set_overrepresentation_pack.py"
CALL_TIMEOUT = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "30"))
CASE_NAMES = (
    "whole-genome", "universe-subset", "outside-universe", "namespace", "identifier-form",
    "duplicate-list", "post-selection", "set-size-tested", "set-size-nonsignificant",
    "raw-correction", "raw-significant", "independent-overlap", "direction-ignored",
    "empty-enriched", "selection-changed", "collection-version", "rule-freeze",
    "claim-activated", "claim-regulated", "claim-driving", "claim-causal",
    "claim-pathway-mechanism", "claim-therapeutic", "claim-clinical-action", "claim-efficacy",
    "claim-physical-validity", "review-kind", "review-result", "computed-kind", "computed-result",
    "external-alias", "empty-evidence", "unavailable-positive", "missing-evidence",
    "unavailable-mixed", "replicated",
)


def _read(path):
    return json.loads(path.read_bytes())


def _write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")


def _identity(path):
    return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


class _Fixture(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(gso, "new enrichment public entry point is required")
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name) / "fixture"
        shutil.copytree(FIXTURE, self.directory)

    def _load(self, name):
        return _read(self.directory / (name + ".json"))

    def _save(self, name, value):
        _write(self.directory / (name + ".json"), value)

    def _refresh(self):
        rules = self._load("rules")
        for name in ("upstream", "genes", "collection"):
            rules[name] = _identity(self.directory / (name + ".json"))
        self._save("rules", rules)
        report = self._load("report")
        report["rules_sha256"] = _identity(self.directory / "rules.json")["sha256"]
        self._save("report", report)
        evidence = self._load("evidence")
        for record in evidence["records"]:
            source = record["source"]["path"]
            record["source"]["sha256"] = hashlib.sha256((self.directory / source).read_bytes()).hexdigest()
        self._save("evidence", evidence)
        pack = self._load("pack")
        for name in ("rules", "report"):
            pack[name] = _identity(self.directory / (name + ".json"))
        pack["evidence"] = [_identity(self.directory / "evidence.json")]
        pack["frozen_rules_sha256"] = pack["rules"]["sha256"]
        self._save("pack", pack)

    def _case(self, case):
        for change in case["changes"]:
            document = self._load(change["target"])
            owner = document
            for key in change["path"][:-1]:
                owner = owner[key]
            owner[change["path"][-1]] = copy.deepcopy(change["value"])
            self._save(change["target"], document)
        self._refresh()
        if case["id"] == "rule-freeze":
            pack = self._load("pack")
            pack["frozen_rules_sha256"] = "0" * 64
            self._save("pack", pack)

    def _validate(self):
        return gso.validate_gene_set_overrepresentation_pack(self.directory / "pack.json")

    def _compute(self):
        return gso.reference_computation(*(self._load(name) for name in ("rules", "upstream", "genes", "collection")))

    def _recompute(self):
        report = dict(schema="gso-report-v1", fixture="synthetic fixture",
                      rules_sha256="0" * 64, **self._compute())
        self._save("report", report)
        self._refresh()

    def _cli(self, *args):
        return subprocess.run([sys.executable, str(CLI), *map(str, args)],
                              text=True, capture_output=True, timeout=CALL_TIMEOUT)


class EnrichmentMathTests(_Fixture):
    def test_fixture_hand_calculations_bh_and_no_writes(self):
        before = {p.name: p.read_bytes() for p in self.directory.iterdir()}
        result = self._validate()
        self.assertEqual(self._load("expected"), result)
        rows = result["computation"]["rows"]
        self.assertEqual(30, result["computation"]["universe_size"])
        self.assertEqual({"combined": 6}, result["computation"]["list_sizes"])
        # C(30,6)=593775; planted k=5 tail=C(5,5)*C(25,1)=25.
        self.assertEqual(25 / 593775, rows[0]["p_value"])
        self.assertEqual(1 / 593775, rows[1]["p_value"])
        # k>=3 for K=5: 10*2300+5*300+1*25=24525.
        self.assertEqual(24525 / 593775, rows[2]["p_value"])
        self.assertEqual(rows[0]["p_value"] * 2, rows[0]["q_value"])
        self.assertEqual(rows[1]["p_value"] * 4, rows[1]["q_value"])
        self.assertLess(rows[2]["p_value"], .05)
        self.assertGreater(rows[2]["q_value"], .05)
        self.assertEqual("non-significant", rows[2]["status"])
        self.assertEqual(1, rows[3]["p_value"])
        self.assertEqual("untested", rows[4]["status"])
        self.assertIsNone(rows[4]["q_value"])
        self.assertEqual([["combined:planted", "combined:redundant"]], result["computation"]["findings"])
        self.assertEqual(5 / 6, result["computation"]["jaccard"][0]["jaccard"])
        self.assertEqual("statistical-overrepresentation-only", result["status"])
        self.assertEqual("unavailable", result["review"])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.directory.iterdir()})

    def test_math_edges_invalid_integers_and_degeneracy(self):
        self.assertEqual(.5, gso.hypergeometric_upper_tail(4, 2, 2, 1) - 1 / 3)
        self.assertEqual(1, gso.hypergeometric_upper_tail(4, 2, 2, 0))
        self.assertEqual(1 / 6, gso.hypergeometric_upper_tail(4, 2, 2, 2))
        self.assertEqual([], gso.benjamini_hochberg([]))
        self.assertEqual([0, 1], gso.benjamini_hochberg([0, 1]))
        self.assertEqual([.03, .03, .03], gso.benjamini_hochberg([.01, .02, .03]))
        for arguments in ((0, 1, 1, 0), (4, 0, 1, 0), (4, 2, 0, 0), (4, 2, 4, 2), (4, 2, 2, 3), (4, 4, 2, 0)):
            with self.subTest(arguments=arguments), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                gso.hypergeometric_upper_tail(*arguments)
        for index in range(4):
            for bad in (True, 2.0, "2", [], float("nan"), float("inf")):
                arguments = [4, 2, 2, 1]
                arguments[index] = bad
                with self.subTest(index=index, bad=bad), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                    gso.hypergeometric_upper_tail(*arguments)
        for values in ([True], [-1], [float("nan")], [2], "bad"):
            with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                gso.benjamini_hochberg(values)

    def test_directional_exploratory_and_threshold_edges(self):
        rules = self._load("rules")
        rules.update(directional=True, selected_before_sets=False, exploratory=True)
        self._save("rules", rules)
        genes = self._load("genes")
        genes["lists"] = [{"direction": "up", "genes": genes["universe"][:4]},
                          {"direction": "down", "genes": genes["universe"][4:6]}]
        self._save("genes", genes)
        self._recompute()
        result = self._validate()["computation"]
        self.assertEqual(10, len(result["rows"]))
        self.assertTrue(result["exploratory"])
        rules.update(directional=False, min_set_size=5, max_set_size=6, alpha=0, overlap_limit=1)
        self._save("rules", rules)
        genes["lists"] = [{"direction": "combined", "genes": genes["universe"][:6]}]
        self._save("genes", genes)
        result = self._compute()
        self.assertEqual([True, True, True, False, False], [r["tested"] for r in result["rows"]])
        self.assertEqual([], result["findings"])
        rules.update(alpha=1, overlap_limit=1)
        self._save("rules", rules)
        self.assertTrue(all(len(f) == 1 for f in self._compute()["findings"]))
        rules.update(alpha=.05, overlap_limit=5 / 6, min_set_size=3, max_set_size=10)
        self._save("rules", rules)
        self.assertEqual(2, len(self._compute()["findings"]))
        rules["overlap_limit"] = 0
        self._save("rules", rules)
        self.assertEqual(1, len(self._compute()["findings"]))
        rules.update(min_set_size=31, max_set_size=31)
        self._save("rules", rules)
        self.assertTrue(all(r["status"] == "untested" for r in self._compute()["rows"]))

    def test_cli_and_repeated_concurrent_validation(self):
        success = self._cli(self.directory / "pack.json")
        self.assertEqual(0, success.returncode, success.stdout + success.stderr)
        self.assertEqual(self._load("expected"), json.loads(success.stdout))
        for arguments in ([], ["--output", "elsewhere"], [self.directory / "absent.json"]):
            refused = self._cli(*arguments)
            self.assertEqual(2, refused.returncode)
            self.assertEqual("refused", json.loads(refused.stdout)["status"])
            self.assertNotIn("Traceback", refused.stderr)
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self._validate(), range(2)))
        self.assertEqual(results[0], results[1])


class EnrichmentDefectTests(_Fixture):
    pass


def _seeded_test(name):
    def test(self):
        cases = self._load("negative-cases")["cases"]
        case = next(case for case in cases if case["id"] == name)
        self._case(case)
        with self.assertRaisesRegex(ValueError, "^" + case["code"] + ":"):
            self._validate()
        refused = self._cli(self.directory / "pack.json")
        self.assertEqual(2, refused.returncode)
        self.assertTrue(json.loads(refused.stdout)["error"].startswith(case["code"] + ":"), refused.stdout)
        self.assertNotIn("Traceback", refused.stderr)
    return test


for _name in CASE_NAMES:
    setattr(EnrichmentDefectTests, "test_negative_" + _name.replace("-", "_"), _seeded_test(_name))


class EnrichmentSafetyTests(_Fixture):
    def test_json_duplicates_roots_depth_numbers_and_types(self):
        invalid = (b'{"x":1,"x":2}', b'{"x":{"a":1,"a":2}}', b'[]', b'null',
                   b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e999}', b'{"x":' + b'9' * 5000 + b'}',
                   b'{"x":', b'\xff', b'{"x":' + b'[' * 2000 + b'0' + b']' * 2000 + b'}')
        for raw in invalid:
            with self.subTest(raw=raw[:50]), self.assertRaisesRegex(ValueError, "^invalid-json:"):
                gso._json(raw, gso.MAX_TOTAL_NODES)
        with patch.object(gso, "MAX_DEPTH", 1), self.assertRaisesRegex(ValueError, "^invalid-json:"):
            gso._json(b'{"x":{"y":1}}', 100)
        with patch.object(gso, "MAX_TEXT", 2), self.assertRaisesRegex(ValueError, "^invalid-record:"):
            gso._json(b'{"x":"abc"}', 100)
        with patch.object(gso, "MAX_ITEMS", 1), self.assertRaisesRegex(ValueError, "^input-limit:"):
            gso._json(b'{"x":[1,2]}', 100)
        for field in ("min_set_size", "max_set_size"):
            for value in (True, 3.0, "3", [], 0, -1):
                rules = self._load("rules")
                rules[field] = value
                with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                    gso._rules(rules)
        for field in ("alpha", "overlap_limit"):
            for value in (True, [], -1, 1.1):
                rules = self._load("rules")
                rules[field] = value
                with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                    gso._rules(rules)
        for field in ("size", "overlap"):
            for value in (True, 3.0, "3", []):
                report = self._load("report")
                report["rows"][0][field] = value
                with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                    gso._report(report, self._compute(), report["rules_sha256"])
        for field in ("universe_size", "list_sizes"):
            for value in (True, 6.0, "6", []):
                report = self._load("report")
                if field == "list_sizes":
                    report[field]["combined"] = value
                else:
                    report[field] = value
                with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                    gso._report(report, self._compute(), report["rules_sha256"])

    def test_budgets_before_work_and_equal_edges(self):
        files = ("pack", "rules", "upstream", "genes", "collection", "report", "evidence")
        raw = [(self.directory / (name + ".json")).read_bytes() for name in files]
        size = sum(map(len, raw))
        nodes = sum(gso._json(value, gso.MAX_TOTAL_NODES)[1] for value in raw)
        for constant, limit in (("MAX_TOTAL_BYTES", size), ("MAX_TOTAL_NODES", nodes), ("MAX_RECORDS", 7)):
            with patch.object(gso, constant, limit):
                self._validate()
            for bound in (0, limit - 1):
                with patch.object(gso, constant, bound), self.assertRaisesRegex(ValueError, "^input-limit:"):
                    self._validate()
        for constant, equal in (("MAX_GENES", 30), ("MAX_SETS", 5), ("MAX_LISTS", 1),
                                ("MAX_MEMBERSHIPS", 20), ("MAX_TESTS", 5), ("MAX_PAIRS", 1),
                                ("MAX_TAIL_TERMS", 9)):
            with self.subTest(constant=constant), patch.object(gso, constant, equal):
                self._compute()
            for bound in (0, equal - 1):
                with patch.object(gso, constant, bound), self.assertRaisesRegex(ValueError, "^(input-limit|invalid-record):"):
                    self._compute()
        with patch.object(gso, "MAX_CLAIMS", 1):
            self._validate()
        with patch.object(gso, "MAX_CLAIMS", 0), self.assertRaisesRegex(ValueError, "^input-limit:"):
            self._validate()
        for count in (0, 2001):
            upstream = self._load("upstream")
            upstream["rows"] = [{"gene": f"G{i}", "direction": "none", "selected": False} for i in range(count)]
            with self.assertRaisesRegex(ValueError, "^(input-limit|invalid-record):"):
                gso.reference_computation(self._load("rules"), upstream, self._load("genes"), self._load("collection"))

    def test_hardlinks_read_parse_once_and_aggregate_preflight(self):
        first = self.directory / "small.json"
        first.write_bytes(b'{"x":1}')
        alias = self.directory / "alias.json"
        os.link(first, alias)
        calls = []
        original_fdopen = os.fdopen
        def opened(fd, *args, **kwargs):
            handle = original_fdopen(fd, *args, **kwargs)
            original_read = handle.read
            def read(size):
                calls.append(size)
                return original_read(size)
            handle.read = read
            return handle
        bundle = gso._Bundle(self.directory)
        try:
            with patch.object(gso.os, "fdopen", opened), patch.object(gso, "_json", wraps=gso._json) as parsed:
                with patch.object(gso, "MAX_TOTAL_BYTES", 7), patch.object(gso, "MAX_TOTAL_NODES", 2):
                    self.assertIs(bundle.load("small.json"), bundle.load("alias.json"))
                    bundle.finish()
                self.assertEqual(1, parsed.call_count)
            self.assertEqual([8, 8], calls)
        finally:
            bundle.close()
        bundle = gso._Bundle(self.directory)
        try:
            with patch.object(gso.os, "fdopen", opened), patch.object(gso, "MAX_TOTAL_BYTES", 6):
                calls.clear()
                with self.assertRaisesRegex(ValueError, "^input-limit:"):
                    bundle.load("small.json")
                self.assertEqual([], calls)
        finally:
            bundle.close()

    def test_paths_hashes_nonregular_oversized_and_growth(self):
        for value in ("../x", "x/../y", "/x", "x\\y", "a//b", "./x", "x/", "C:x", [], None):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "^(input-path|invalid-record):"):
                gso._relative(value)
        for value in (None, [], True, b"pack.json", "a\x00b"):
            with self.assertRaisesRegex(ValueError, "^(input-path|invalid-record):"):
                gso.validate_gene_set_overrepresentation_pack(value)
        path = self.directory / "odd.json"
        os.mkfifo(path)
        bundle = gso._Bundle(self.directory)
        try:
            with self.assertRaisesRegex(ValueError, "^input-file:"):
                bundle.load(path.name)
            path.unlink()
            path.mkdir()
            with self.assertRaisesRegex(ValueError, "^input-file:"):
                bundle.load(path.name)
            path.rmdir()
            path.symlink_to("pack.json")
            with self.assertRaisesRegex(ValueError, "^input-file:"):
                bundle.load(path.name)
            path.unlink()
            with path.open("wb") as handle:
                handle.truncate(gso.MAX_BYTES + 1)
            with self.assertRaisesRegex(ValueError, "^input-file:"):
                bundle.load(path.name)
            path.write_bytes(b'{"x":1}')
            with patch.object(gso, "MAX_BYTES", 7):
                bundle.load(path.name)
            with self.assertRaisesRegex(ValueError, "^input-hash:"):
                bundle.load(path.name, "0" * 64)
            path.write_bytes(b'{"x":2}')
            with self.assertRaisesRegex(ValueError, "^input-changed:"):
                bundle.finish()
        finally:
            bundle.close()

    def test_growing_file_descriptor_swap_and_linked_component(self):
        original_fdopen = os.fdopen
        path = self.directory / "small.json"
        path.write_bytes(b'{"x":1}')
        fired = []
        def opened(fd, *args, **kwargs):
            handle = original_fdopen(fd, *args, **kwargs)
            original_read = handle.read
            def read(size):
                raw = original_read(size)
                if not fired:
                    fired.append(True)
                    with path.open("ab") as output:
                        output.write(b" ")
                return raw
            handle.read = read
            return handle
        bundle = gso._Bundle(self.directory)
        try:
            with patch.object(gso.os, "fdopen", opened), self.assertRaisesRegex(ValueError, "^input-file:"):
                bundle.load(path.name)
            original_open = os.open
            fired.clear()
            def swapped(name, flags, *args, **kwargs):
                if name == path.name and not fired:
                    fired.append(True)
                    path.unlink()
                    path.write_bytes(b'{"y":2}')
                return original_open(name, flags, *args, **kwargs)
            with patch.object(gso.os, "open", swapped), self.assertRaisesRegex(ValueError, "^input-file:"):
                bundle.load(path.name)
            (self.directory / "linked").symlink_to(".", target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "^input-file:"):
                bundle.load("linked/pack.json")
        finally:
            bundle.close()

    def test_empty_shapes_malformed_fields_and_namespace_route(self):
        for name, key in (("upstream", "rows"), ("genes", "lists"), ("genes", "universe"), ("collection", "sets")):
            values = {n: self._load(n) for n in ("rules", "upstream", "genes", "collection")}
            values[name][key] = []
            with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                gso.reference_computation(*(values[n] for n in ("rules", "upstream", "genes", "collection")))
        for malformed in (None, [], {}, {"id": []}):
            with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                gso._fields(malformed, "id genes", "set")
        gso._claims([], {})
        for value in ([], {}, 1, "yes"):
            rules = self._load("rules")
            rules["directional"] = value
            with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                gso._rules(rules)
        rules = self._load("rules")
        rules["namespace"] = "ensembl_gene_id"
        self.assertEqual({"ENSG001", "ENSMUSG002.1"}, gso._identifiers(["ENSG001", "ENSMUSG002.1"], rules, "genes"))
        with self.assertRaisesRegex(ValueError, "^identifier-namespace:"):
            gso._identifiers(["G01"], rules, "genes")
        for constant, count in (("MAX_ITEMS", 1), ("MAX_DEPTH", 1), ("MAX_TEXT", 1)):
            with patch.object(gso, constant, count):
                gso._json(b'{"x":1}', 2)
        with self.assertRaisesRegex(ValueError, "^input-limit:"):
            gso._json(b'{"x":1}', 1)
        self.assertEqual(({}, 1), gso._json(b'{}', 1))

    def test_root_and_ancestor_swaps_at_open_and_lstat(self):
        original_open = os.open
        original_lstat = os.lstat
        for target in (self.directory, self.directory.parent):
            saved = target.with_name(target.name + "-saved")
            fired = []
            def opened(path, flags, *args, **kwargs):
                if path == target.name and not fired:
                    fired.append(True)
                    target.rename(saved)
                    target.symlink_to(saved, target_is_directory=True)
                return original_open(path, flags, *args, **kwargs)
            try:
                with patch.object(gso.os, "open", opened), self.assertRaisesRegex(ValueError, "^input-root:"):
                    self._validate()
            finally:
                if fired:
                    target.unlink()
                    saved.rename(target)
            self.assertTrue(fired)
        saved = self.directory.with_name("saved")
        fired = []
        def inspected(path, *args, **kwargs):
            info = original_lstat(path, *args, **kwargs)
            if path == self.directory.name and not fired:
                fired.append(True)
                self.directory.rename(saved)
                self.directory.mkdir()
            return info
        try:
            with patch.object(gso.os, "lstat", inspected), self.assertRaisesRegex(ValueError, "^input-root:"):
                self._validate()
        finally:
            if fired:
                self.directory.rmdir()
                saved.rename(self.directory)
        bundle = gso._Bundle(self.directory)
        try:
            bundle.load("pack.json")
            self.directory.rename(saved)
            self.directory.mkdir()
            with self.assertRaisesRegex(ValueError, "^input-root:"):
                bundle.finish()
        finally:
            bundle.close()
            self.directory.rmdir()
            saved.rename(self.directory)

    def test_arithmetic_status_and_result_schema_cannot_support_positive_claims(self):
        for field in ("kind", "result"):
            for label in ("arithmetic-only", "gso-result-v1"):
                evidence = self._load("evidence")
                record = evidence["records"][0]
                record.update(kind="observed", result="observed")
                record[field] = label
                self._save("evidence", evidence)
                pack = self._load("pack")
                pack["claims"][0].update(status="unsupported", evidence=[record["id"]])
                self._save("pack", pack)
                self._refresh()
                self._validate()
                pack = self._load("pack")
                for status in gso.POSITIVE:
                    with self.subTest(field=field, label=label, status=status):
                        pack["claims"][0]["status"] = status
                        self._save("pack", pack)
                        with self.assertRaisesRegex(ValueError, "^non-evidence:"):
                            self._validate()

    def test_claim_status_evidence_and_wording_families(self):
        record = {"id": "observed", "kind": "observed", "result": "frozen-inputs"}
        claim = {"id": "C", "kind": "descriptive", "status": "supported", "text": "Synthetic over-representation.", "evidence": ["observed"]}
        for status in ("supported", "replicated", "suggestive"):
            for field in ("kind", "result"):
                for label in ("review-approval", "computed-agreement"):
                    with self.assertRaisesRegex(ValueError, "^non-evidence:"):
                        gso._claims([dict(claim, status=status)], {"observed": dict(record, **{field: label})})
        for status in gso.STATUSES - {"unavailable"}:
            for field in ("kind", "result"):
                with self.assertRaisesRegex(ValueError, "^evidence-unavailable:"):
                    gso._claims([dict(claim, status=status)], {"observed": dict(record, **{field: "unavailable"})})
        for field in ("id", "kind", "status"):
            with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                gso._claims([dict(claim, **{field: []})], {"observed": record})
        words = "causality mechanism therapy clinical efficacy effective treatment cure prevention recommendation prescription binding affinity inhibition activation regulation drives induction".split()
        for word in words:
            with self.subTest(word=word), self.assertRaisesRegex(ValueError, "^claim-overreach:"):
                gso._claims([dict(claim, text=word.upper())], {"observed": record})


if __name__ == "__main__":
    unittest.main()
