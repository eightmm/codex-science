"""Synthetic flow fixtures: arithmetic, seeded refusals and untrusted-input boundaries."""
import copy
from concurrent.futures import ThreadPoolExecutor
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

from codex_science import flow_cytometry_qc_pack as flow

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "workflow-flow-cytometry-qc"
CLI = ROOT / "scripts" / "validate_flow_cytometry_qc_pack.py"
CALL_TIMEOUT = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "30"))
CASES = json.loads((FIXTURE / "negative-cases.json").read_bytes())["cases"]


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")


def identity(path):
    return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


class FixtureCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name) / "bundle"
        shutil.copytree(FIXTURE, self.directory)

    def edit(self, target, keys, value):
        path = self.directory / (target + ".json")
        document = read(path)
        owner = document
        for key in keys[:-1]:
            owner = owner[key]
        owner[keys[-1]] = value
        write(path, document)

    def refresh(self, recompute=False):
        rules = read(self.directory / "rules.json")
        rules["compensation"]["source"] = identity(self.directory / "compensation-source.json")
        write(self.directory / "rules.json", rules)
        report = read(self.directory / "report.json")
        if recompute:
            report.update(flow.reference_computation(rules, read(self.directory / "events.json")))
        report["rules_sha256"] = identity(self.directory / "rules.json")["sha256"]
        report["events_sha256"] = identity(self.directory / "events.json")["sha256"]
        write(self.directory / "report.json", report)
        pack = read(self.directory / "pack.json")
        for field in ("rules", "events", "report"):
            pack[field] = identity(self.directory / (field + ".json"))
        pack["frozen_rules_sha256"] = pack["rules"]["sha256"]
        for record in pack["evidence"]:
            record["source"]["sha256"] = hashlib.sha256((self.directory / record["source"]["path"]).read_bytes()).hexdigest()
        write(self.directory / "pack.json", pack)

    def validate(self):
        return flow.validate_flow_cytometry_qc_pack(self.directory / "pack.json")

    def cli(self, *args):
        return subprocess.run([sys.executable, str(CLI), *map(str, args)],
                              capture_output=True, text=True, timeout=CALL_TIMEOUT)

    def seed(self, case):
        for change in case["changes"]:
            self.edit(change["target"], change["path"], change["value"])
        self.refresh()


class FlowMathTests(FixtureCase):
    def test_hand_counts_compensation_and_percentages(self):
        result = self.validate()
        expected = read(self.directory / "expected.json")
        self.assertEqual(result["status"], "arithmetic-only")
        self.assertEqual(result["review"], "unavailable")
        for sample in result["computation"]["samples"]:
            self.assertEqual([gate["count"] for gate in sample["gates"]], expected["counts"][sample["id"]])
            for gate, percentage in zip(sample["gates"], expected["percentages"][sample["id"]]):
                if percentage == "unavailable":
                    self.assertEqual(gate["percentage"], percentage)
                else:
                    self.assertAlmostEqual(gate["percentage"], percentage)
        self.assertEqual([control["percentage"] for control in result["computation"]["controls"]], [0, 0])
        for actual, expected in zip(flow._solve([[1, 0.5], [0.2, 1]], [11, 4]), [10, 2]):
            self.assertAlmostEqual(actual, expected)
        # Pivoting is required for this invertible system.
        self.assertEqual(flow._solve([[0, 1], [1, 1]], [2, 5]), [3, 2])

    def test_exploratory_and_unavailable_preserved(self):
        self.edit("rules", ["outcomes_seen"], True)
        self.edit("rules", ["exploratory"], True)
        self.edit("events", ["samples", 1, "status"], "unavailable")
        self.edit("events", ["samples", 1, "events"], [])
        self.refresh(recompute=True)
        result = self.validate()["computation"]
        self.assertTrue(result["exploratory"])
        absent = result["samples"][1]
        self.assertEqual(absent["stability"], "unavailable")
        self.assertTrue(all(gate["count"] == gate["percentage"] == "unavailable" for gate in absent["gates"]))

    def test_gate_thresholds_and_minimum_edges(self):
        self.edit("rules", ["populations", 0, "bounds", 0, "low"], 6)
        self.refresh(recompute=True)
        self.assertEqual(self.validate()["computation"]["samples"][0]["gates"][3]["count"], 2)
        self.edit("rules", ["min_gate_events"], 3)
        self.refresh(recompute=True)
        self.assertEqual(self.validate()["computation"]["samples"][0]["gates"][3]["percentage"], "unavailable")
        self.edit("rules", ["min_gate_events"], 2)
        self.edit("rules", ["min_percentage_events"], 4)
        with self.assertRaisesRegex(ValueError, "insufficient-control:"):
            self.refresh(recompute=True)

    def test_fmo_bound_equal_zero_and_failure(self):
        self.edit("rules", ["controls", 0, "max_positive_percentage"], 0)
        self.refresh(recompute=True)
        self.validate()
        self.edit("events", ["samples", 2, "events", 0, "values", "FITC"], 7)
        with self.assertRaisesRegex(ValueError, "fmo-positive-rate:"):
            self.refresh(recompute=True)

    def test_stability_equal_bound_and_zero(self):
        self.edit("events", ["samples", 0, "events", 1, "time"], 1.0)
        self.edit("rules", ["time", "max_rate_variation"], 1)
        self.refresh(recompute=True)
        self.assertEqual(self.validate()["computation"]["samples"][0]["stability"]["variation"], 1)
        self.edit("rules", ["time", "max_rate_variation"], 0)
        with self.assertRaisesRegex(ValueError, "flow-unstable:"):
            self.refresh(recompute=True)

    def test_near_zero_distinct_values_do_not_tie(self):
        with self.assertRaisesRegex(ValueError, "report-mismatch:"):
            flow._compare(2e-100, 1e-100, "percentage")
        flow._compare(1e-100 * (1 + 1e-10), 1e-100, "percentage")
        with self.assertRaisesRegex(ValueError, "compensation-singular:"):
            flow._solve([[1, 1], [1, 1]], [1, 1])
        with self.assertRaisesRegex(ValueError, "compensation-singular:"):
            flow._solve([[1, 0.9096585139012329], [1.0993136267271566, 1]], [1, 1])
        self.assertEqual([1.0, 2.0], flow._solve([[1, 0], [0, 1]], [1, 2]))


class FlowSeededTests(FixtureCase):
    pass


def seeded_test(case):
    def test(self):
        self.seed(case)
        with self.assertRaisesRegex(ValueError, "^" + case["finding"] + ":"):
            self.validate()
        result = self.cli(self.directory / "pack.json")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        refusal = json.loads(result.stderr)
        self.assertTrue(refusal["finding"].startswith(case["finding"] + ":"), refusal)
    return test


for case in CASES:
    setattr(FlowSeededTests, "test_" + case["id"].replace("-", "_"), seeded_test(case))


class FlowClaimTests(FixtureCase):
    def test_all_wording_families_and_status_types(self):
        pack_path = self.directory / "pack.json"
        pack = read(pack_path)
        for word in ("causes", "mechanism", "therapy", "clinical", "efficacy", "effective", "treatment",
                     "cure", "prevention", "recommend", "prescribe", "binding", "affinity", "inhibition",
                     "activation", "regulates", "drives", "induced", "diagnostic", "disease", "cell identity", "functional state"):
            for status in ("supported", "suggestive", "replicated", "unavailable"):
                with self.subTest(word=word, status=status):
                    modified = copy.deepcopy(pack)
                    modified["claims"][0].update(text="The fixture " + word, status=status)
                    write(pack_path, modified)
                    with self.assertRaisesRegex(ValueError, "claim-overreach:"):
                        self.validate()
        for field in ("id", "kind", "status", "text"):
            modified = copy.deepcopy(pack)
            modified["claims"][0][field] = []
            write(pack_path, modified)
            with self.assertRaisesRegex(ValueError, "invalid-record:"):
                self.validate()

    def test_non_evidence_each_label_and_positive_status(self):
        for status in flow.POSITIVE:
            for field in ("kind", "result"):
                for label in ("review-approval", "computed", "numerical-agreement"):
                    with self.subTest(status=status, field=field, label=label):
                        self.edit("pack", ["claims", 0, "status"], status)
                        self.edit("pack", ["evidence", 0, field], label)
                        with self.assertRaisesRegex(ValueError, "non-evidence-support:"):
                            self.validate()

    def test_arithmetic_status_and_result_schema_cannot_support_positive_claims(self):
        pack_path = self.directory / "pack.json"
        pack = read(pack_path)
        for field in ("kind", "result"):
            for label in ("arithmetic-only", "flow-cytometry-qc-result-v1"):
                pack["evidence"][0].update(kind="observed", result="observed")
                pack["evidence"][0][field] = label
                pack["claims"][0]["status"] = "unsupported"
                write(pack_path, pack)
                self.validate()
                for status in flow.POSITIVE:
                    with self.subTest(field=field, label=label, status=status):
                        pack["claims"][0]["status"] = status
                        write(pack_path, pack)
                        with self.assertRaisesRegex(ValueError, "^non-evidence-support:"):
                            self.validate()

    def test_unavailable_mixed_evidence_and_empty_claim(self):
        pack = read(self.directory / "pack.json")
        pack["evidence"][0].update(kind="observed", result="observed")
        other = copy.deepcopy(pack["evidence"][0])
        other.update(id="absent", result="unavailable")
        pack["evidence"].append(other)
        pack["claims"][0]["evidence"].append("absent")
        for status in flow.STATUSES - {"unavailable"}:
            pack["claims"][0]["status"] = status
            write(self.directory / "pack.json", pack)
            with self.assertRaisesRegex(ValueError, "unavailable-evidence:"):
                self.validate()
        pack["claims"][0].update(status="unavailable", evidence=[], text="No record is available.")
        write(self.directory / "pack.json", pack)
        self.validate()

    def test_external_alias_hash_and_replication(self):
        shutil.copyfile(self.directory / "report.json", self.directory / "alias.json")
        self.edit("pack", ["evidence", 0, "source"], identity(self.directory / "alias.json"))
        for origin in ("external", "independent", "preregistered"):
            self.edit("pack", ["evidence", 0, "origin"], origin)
            with self.assertRaisesRegex(ValueError, "external-alias:"):
                self.validate()
        self.edit("pack", ["evidence", 0, "origin"], "internal")
        self.edit("pack", ["evidence", 0, "kind"], "observed")
        self.edit("pack", ["evidence", 0, "result"], "observed")
        self.edit("pack", ["claims", 0, "status"], "replicated")
        with self.assertRaisesRegex(ValueError, "claim-replication:"):
            self.validate()


class FlowIOTests(FixtureCase):
    def test_cli_success_argument_refusals_help_and_no_writes(self):
        before = {path.name: path.read_bytes() for path in self.directory.iterdir()}
        for args in ((), ("--unknown",), (self.directory / "pack.json", "extra"), ("--output", "out")):
            result = self.cli(*args)
            self.assertEqual(result.returncode, 2)
            self.assertTrue(json.loads(result.stderr)["finding"].startswith("invalid-arguments:"))
            self.assertEqual(result.stdout, "")
        result = self.cli("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("usage:", result.stdout)
        self.assertEqual(result.stderr, "")
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.validate(), range(2)))
        self.assertEqual(results[0], results[1])
        result = self.cli(self.directory / "pack.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "arithmetic-only")
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.directory.iterdir()})

    def test_strict_json_and_preparse_budget(self):
        bad = (b'{"x":1,"x":2}', b'{"x":{"y":1,"y":2}}', b'{"x":NaN}', b'{"x":Infinity}',
               b'[]', b'{"x":1e999}', b'{"x":' + b'9' * 102 + b'}', b'not json', b'\xff',
               b'{"x":' + b'[' * 1200 + b'0' + b']' * 1200 + b'}')
        for raw in bad:
            with self.subTest(raw=raw[:50]), self.assertRaisesRegex(ValueError, "^[a-z-]+:"):
                flow._json(raw)
        raw = b'{"x":[1,2]}'
        _, allowance = flow._json(raw)
        with patch.object(flow, "MAX_JSON_VALUES", allowance):
            flow._json(raw)
        for limit in (0, allowance - 1):
            with patch.object(flow, "MAX_JSON_VALUES", limit), patch.object(flow.json, "loads", side_effect=AssertionError("too late")):
                with self.assertRaisesRegex(ValueError, "input-limit:"):
                    flow._json(raw)
        with patch.object(flow.re, "findall", side_effect=AssertionError("match list allocated")):
            self.validate()
        with patch.object(flow, "MAX_DEPTH", 1):
            with self.assertRaisesRegex(ValueError, "invalid-json:"):
                flow._json(b'{"x":[[0]]}')

    def test_byte_value_artifact_budgets_and_hardlink_cache(self):
        paths = [self.directory / name for name in ("pack.json", "rules.json", "events.json", "report.json", "compensation-source.json")]
        total = sum(path.stat().st_size for path in paths)
        with patch.object(flow, "MAX_TOTAL_BYTES", total):
            self.validate()
        for limit in (0, total - 1):
            with patch.object(flow, "MAX_TOTAL_BYTES", limit), self.assertRaisesRegex(ValueError, "input-limit:"):
                self.validate()
        with patch.object(flow, "MAX_ARTIFACTS", 5):
            self.validate()
        with patch.object(flow, "MAX_ARTIFACTS", 4), self.assertRaisesRegex(ValueError, "input-limit:"):
            self.validate()
        values = sum(flow._json(path.read_bytes())[1] for path in paths[:-1])
        with patch.object(flow, "MAX_JSON_VALUES", values):
            self.validate()
        with patch.object(flow, "MAX_JSON_VALUES", values - 1), self.assertRaisesRegex(ValueError, "input-limit:"):
            self.validate()
        alias = self.directory / "alias.json"
        os.link(paths[-1], alias)
        with patch.object(flow, "MAX_TOTAL_BYTES", paths[-1].stat().st_size):
            store = flow._Bundle(self.directory)
            try:
                original = store.load(paths[-1].name)
                with patch.object(flow, "_json", side_effect=AssertionError("alias reparsed")):
                    self.assertIs(store.load(alias.name), original)
                self.assertEqual(store.total_bytes, paths[-1].stat().st_size)
                store.finish()
            finally:
                store.close()

    def test_special_files_paths_hashes_size_and_growth(self):
        for bad in ("../rules.json", "a/../rules.json", "a\\rules.json", "/rules.json", "./rules.json", "a//b", "a:b", "a\x00b"):
            with self.subTest(path=bad), self.assertRaisesRegex(ValueError, "input-path:|invalid-record:"):
                flow._relative(bad)
        for mode in ("fifo", "directory", "symlink", "oversize"):
            target = self.directory / "unsafe"
            if mode == "fifo":
                os.mkfifo(target)
            elif mode == "directory":
                target.mkdir()
            elif mode == "symlink":
                target.symlink_to("events.json")
            else:
                target.write_bytes(b"x" * 10)
            store = flow._Bundle(self.directory)
            try:
                with patch.object(flow, "MAX_BYTES", 9), self.assertRaisesRegex(ValueError, "input-file:"):
                    store.load("unsafe")
            finally:
                store.close()
                target.rmdir() if mode == "directory" else target.unlink()
        self.edit("pack", ["events", "sha256"], "0" * 64)
        with self.assertRaisesRegex(ValueError, "input-hash:"):
            self.validate()
        for digest in (None, [], "", "G" * 64):
            self.edit("pack", ["events", "sha256"], digest)
            with self.assertRaisesRegex(ValueError, "input-hash:|invalid-record:"):
                self.validate()
        store = flow._Bundle(self.directory)
        try:
            path = self.directory / "tiny"
            path.write_bytes(b"{}")
            with patch.object(flow, "MAX_BYTES", 2):
                store.load("tiny")
            original_fdopen = os.fdopen
            def growing(fd, *args, **kwargs):
                handle = original_fdopen(fd, *args, **kwargs)
                path.write_bytes(b"{} ")
                return handle
            store.snapshots.clear()
            store.cache.clear()
            with patch.object(flow.os, "fdopen", growing), self.assertRaisesRegex(ValueError, "input-file:"):
                store.load("tiny")
        finally:
            store.close()

    def test_read_once_then_final_recheck_detects_replacement(self):
        original = flow._Bundle._read
        reads = []
        def track(store, name):
            reads.append(name)
            return original(store, name)
        with patch.object(flow._Bundle, "_read", track):
            self.validate()
        self.assertEqual(len(reads), 10)
        self.assertTrue(all(reads.count(name) == 2 for name in set(reads)))
        original_finish = flow._Bundle.finish
        def replaced(store):
            path = self.directory / "events.json"
            replacement = path.with_suffix(".new")
            replacement.write_bytes(path.read_bytes())
            replacement.replace(path)
            return original_finish(store)
        with patch.object(flow._Bundle, "finish", replaced), self.assertRaisesRegex(ValueError, "input-changed:"):
            self.validate()

    def test_transient_ancestor_and_root_swaps_at_open(self):
        original = os.open
        for name in (self.directory.name, self.directory.parent.name):
            fired = []
            def swapped(path, flags, *args, **kwargs):
                if path == name and kwargs.get("dir_fd") is not None and not fired:
                    fired.append(True)
                    target = self.directory if name == self.directory.name else self.directory.parent
                    moved = target.with_name(target.name + "-moved")
                    target.rename(moved)
                    target.symlink_to(moved, target_is_directory=True)
                    try:
                        return original(path, flags, *args, **kwargs)
                    finally:
                        target.unlink()
                        moved.rename(target)
                return original(path, flags, *args, **kwargs)
            with patch.object(flow.os, "open", swapped), self.assertRaisesRegex(ValueError, "input-root:"):
                self.validate()
            self.assertEqual(fired, [True])

    def test_parent_replaced_but_bundle_inode_preserved(self):
        store = flow._Bundle(self.directory)
        parent = self.directory.parent
        moved = parent.with_name(parent.name + "-original")
        try:
            parent.rename(moved)
            parent.mkdir()
            (moved / self.directory.name).rename(self.directory)
            with self.assertRaisesRegex(ValueError, "input-root:"):
                store.finish()
        finally:
            self.directory.rename(moved / self.directory.name)
            parent.rmdir()
            moved.rename(parent)
            store.close()

    def test_root_replaced_at_final_recheck_and_lstat_race(self):
        original = flow._Bundle.finish
        def replaced(store):
            moved = self.directory.with_name("moved")
            self.directory.rename(moved)
            self.directory.mkdir()
            try:
                return original(store)
            finally:
                self.directory.rmdir()
                moved.rename(self.directory)
        with patch.object(flow._Bundle, "finish", replaced), self.assertRaisesRegex(ValueError, "input-root:"):
            self.validate()
        original_lstat = os.lstat
        moved = self.directory.with_name("moved")
        fired = []
        def swapped(name, *args, **kwargs):
            before = original_lstat(name, *args, **kwargs)
            if name == self.directory.name and kwargs.get("dir_fd") is not None and not fired:
                fired.append(True)
                self.directory.rename(moved)
                self.directory.mkdir()
            return before
        try:
            with patch.object(flow.os, "lstat", swapped), self.assertRaisesRegex(ValueError, "input-root:"):
                self.validate()
        finally:
            if moved.exists():
                self.directory.rmdir()
                moved.rename(self.directory)
        self.assertEqual(fired, [True])

    def test_empty_source_zero_budget_and_exact_file_size(self):
        (self.directory / "empty").write_bytes(b"")
        store = flow._Bundle(self.directory)
        try:
            with patch.object(flow, "MAX_TOTAL_BYTES", 0), patch.object(flow, "MAX_BYTES", 0):
                self.assertEqual(store.load("empty", parse=False), hashlib.sha256(b"").hexdigest())
                store.finish()
        finally:
            store.close()
        for raw, limit in ((b"{}", 2), (b"{} ", 2), (b"{}", 0)):
            (self.directory / "tiny").write_bytes(raw)
            store = flow._Bundle(self.directory)
            try:
                with patch.object(flow, "MAX_BYTES", limit):
                    if len(raw) <= limit:
                        store.load("tiny")
                    else:
                        with self.assertRaisesRegex(ValueError, "input-file:"):
                            store.load("tiny")
            finally:
                store.close()

    def test_freeze_refused_before_events_are_read(self):
        self.edit("rules", ["hashed_before_events"], False)
        self.refresh()
        original = flow._Bundle._read
        def track(store, name):
            self.assertNotEqual(name, "events.json")
            return original(store, name)
        with patch.object(flow._Bundle, "_read", track), self.assertRaisesRegex(ValueError, "rule-freeze:"):
            self.validate()


class FlowContractTests(FixtureCase):
    def test_declared_integers_and_malformed_keys(self):
        mutations = [("rules", ["min_gate_events"]), ("rules", ["min_percentage_events"]),
                     ("events", ["samples", 0, "compensation_applied"]), ("report", ["samples", 0, "gates", 0, "count"]),
                     ("report", ["samples", 0, "gates", 0, "parent_count"]), ("report", ["samples", 0, "stability", "bin_counts", 0])]
        for target, keys in mutations:
            original = (self.directory / (target + ".json")).read_bytes()
            for value in (True, 2.0, "2", None, []):
                with self.subTest(target=target, keys=keys, value=value):
                    self.edit(target, keys, value)
                    self.refresh()
                    with self.assertRaisesRegex(ValueError, "invalid-record:"):
                        self.validate()
                    (self.directory / (target + ".json")).write_bytes(original)
                    self.refresh()

    def test_limits_equal_zero_empty_malformed_and_oversize(self):
        for limit in (0, 2):
            with patch.object(flow, "MAX_SAMPLES", limit), self.assertRaisesRegex(ValueError, "input-limit:"):
                self.validate()
        with patch.object(flow, "MAX_SAMPLES", 3):
            self.validate()
        for constant, value in (("MAX_CHANNELS", 4), ("MAX_ROWS", 11), ("MAX_GATES", 1), ("MAX_BINS", 2),
                                ("MAX_RECORDS", 0), ("MAX_STRING", 10), ("MAX_ITEMS", 3)):
            with self.subTest(constant=constant), patch.object(flow, constant, value), self.assertRaisesRegex(ValueError, "input-limit:|invalid-record:|input-path:"):
                self.validate()
        for target, keys in (("rules", ["panel"]), ("rules", ["controls"]), ("rules", ["populations"]),
                             ("rules", ["time", "bin_edges"]), ("rules", ["compensation", "matrix"]), ("events", ["samples"])):
            original = (self.directory / (target + ".json")).read_bytes()
            for value in ([], {}, None):
                self.edit(target, keys, value)
                self.refresh()
                with self.assertRaisesRegex(ValueError, "invalid-record:"):
                    self.validate()
                (self.directory / (target + ".json")).write_bytes(original)
                self.refresh()
        self.edit("events", ["samples"], [read(self.directory / "events.json")["samples"][0]] * (flow.MAX_SAMPLES + 1))
        self.refresh()
        with self.assertRaisesRegex(ValueError, "input-limit:"):
            self.validate()

    def test_event_integrity_and_numerical_degeneracy(self):
        rules = read(self.directory / "rules.json")
        original = read(self.directory / "events.json")
        for keys, value, code in ((["samples", 0, "events", 1, "id"], "sample-a-0", "duplicate-event"),
                                  (["samples", 0, "events", 1, "time"], 0, "time-not-monotonic"),
                                  (["samples", 0, "events", 0, "values", "FSC-H"], 0, "degenerate-singlet"),
                                  (["samples", 0, "events", 0, "values", "FITC"], -1, "invalid-record"),
                                  (["samples", 0, "events", 0, "time"], 3, "time-outside-bins"),
                                  (["samples", 0, "events"], [], "empty-events")):
            write(self.directory / "events.json", original)
            self.edit("events", keys, value)
            with self.assertRaisesRegex(ValueError, code + ":"):
                flow.reference_computation(rules, read(self.directory / "events.json"))
        with self.assertRaisesRegex(ValueError, "invalid-record:"):
            flow.reference_computation({}, original)

    def test_frozen_control_cannot_be_relabelled_as_sample(self):
        self.edit("events", ["samples", 2, "role"], "sample")
        self.refresh()
        with self.assertRaisesRegex(ValueError, "missing-control:"):
            self.validate()

    def test_each_dimension_accepts_equality_and_refuses_zero(self):
        equal = {"MAX_ROWS": 12, "MAX_SAMPLES": 3, "MAX_CHANNELS": 5,
                 "MAX_GATES": 2, "MAX_BINS": 3, "MAX_RECORDS": 1,
                 "MAX_ITEMS": 17, "MAX_STRING": 64, "MAX_DEPTH": 6,
                 "MAX_NUMBER": 100, "MAX_ARTIFACTS": 5}
        for constant, limit in equal.items():
            with self.subTest(constant=constant, edge="equal"), patch.object(flow, constant, limit):
                self.validate()
            with self.subTest(constant=constant, edge="zero"), patch.object(flow, constant, 0):
                with self.assertRaisesRegex(ValueError, "^[a-z-]+:"):
                    self.validate()
        flow._list([], "empty allowed", 0, empty=True)
        with self.assertRaisesRegex(ValueError, "invalid-record:"):
            flow._list([], "empty forbidden", 0)
        for invalid in (None, {}, "list", 0):
            with self.assertRaisesRegex(ValueError, "invalid-record:"):
                flow._list(invalid, "malformed list", 0)
        for invalid in (None, {}, [], True, "0"):
            with self.assertRaisesRegex(ValueError, "invalid-record:"):
                flow._number(invalid, "malformed number")
        for invalid in (None, {}, [], 0, ""):
            with self.assertRaisesRegex(ValueError, "invalid-record:"):
                flow._text(invalid, "malformed text")

    def test_metadata_matches_real_fixtures_and_plan(self):
        skill = ROOT / "authored-skills" / "workflow-flow-cytometry-qc"
        quality = read(skill / "quality.json")
        self.assertEqual(quality["test_files"], ["tests/test_workflow_flow_pack.py"])
        self.assertEqual(set(quality["seeded_failures"]), {case["id"] for case in CASES})
        self.assertEqual([step["id"] for step in read(skill / "references" / "plan.json")["plan"]], list(flow.STAGES))
        for path in quality["acceptance_fixtures"]:
            self.assertTrue((ROOT / path).is_file())
        description = (skill / "SKILL.md").read_text().split("description:", 1)[1].split("\n", 1)[0].lower()
        for word in ("workflow", "analysis", "statistics", "pipeline"):
            self.assertNotIn(word, description)
        self.assertIn(flow.WORDING_FAMILIES, (skill / "references" / "stages.md").read_text())
        self.assertTrue(any(flow.WORDING_FAMILIES in limit for limit in quality["limitations"]))


if __name__ == "__main__":
    unittest.main()
