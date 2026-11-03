"""Synthetic proteomics acceptance, hand calculations and hostile-input refusals."""
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
FIXTURE = ROOT / "examples/workflow-proteomics-differential-abundance"
CLI = ROOT / "scripts/validate_proteomics_pack.py"
CALL_TIMEOUT = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "30"))
CASES = (
    "batch-confounding", "technical-replicates", "technical-label", "undeclared-imputation",
    "imputed-as-observed", "decoy-hit", "contaminant-hit", "peptide-hit", "too-few-hit",
    "zero-variance-hit", "missing-as-zero", "database-version", "no-bh", "filtered-bh",
    "post-normalization", "post-contrast", "causal", "mechanistic", "clinical", "physical",
    "review-kind", "review-result", "computed-kind", "computed-result", "external-alias",
    "unavailable-negative", "unavailable-positive", "unfrozen", "stage-order", "qc-hit",
)


class _Fixture(unittest.TestCase):
    def setUp(self):
        self.api = importlib.import_module("codex_science.proteomics_pack")
        self.pack = json.loads((FIXTURE / "pack.json").read_bytes())

    def folder(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        folder = Path(temporary.name) / "bundle"
        folder.mkdir()
        for path in FIXTURE.glob("*.json"):
            shutil.copyfile(path, folder / path.name)
        return folder

    def write(self, folder, name, value):
        raw = (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode()
        (folder / name).write_bytes(raw)
        return {"path": name, "sha256": hashlib.sha256(raw).hexdigest()}

    def run_pack(self, folder):
        self.write(folder, "pack.json", self.pack)
        return self.api.validate_proteomics_pack(folder / "pack.json")

    def freeze(self):
        self.pack["frozen_spec"] = copy.deepcopy(self.pack["analysis_spec"])
        self.pack["frozen_sha256"] = self.api.specification_hash(self.pack["frozen_spec"])

    def input(self, folder, name, mutate):
        filename = self.pack["inputs"][name]["path"]
        value = json.loads((folder / filename).read_bytes())
        mutate(value)
        self.pack["inputs"][name] = self.write(folder, filename, value)
        if name == "design":
            self.pack["frozen_design_sha256"] = self.pack["inputs"][name]["sha256"]

    def refuse(self, folder, code):
        with self.assertRaisesRegex(ValueError, "^" + code + ":"):
            self.run_pack(folder)


class ProteomicsReferenceTests(_Fixture):
    def test_fixture_expected_and_hand_calculations(self):
        actual = self.api.validate_proteomics_pack(FIXTURE / "pack.json")
        self.assertEqual(json.loads((FIXTURE / "expected.json").read_bytes()), actual)
        self.assertEqual(actual, self.api.validate_proteomics_pack(FIXTURE / "pack.json"))
        rows = {row["protein_id"]: row for row in actual["differential"]}
        self.assertEqual(["CHANGED"], [key for key, row in rows.items() if row["significant"]])
        self.assertEqual("statistical-only", actual["evidence_level"])
        self.assertEqual("unavailable", actual["review"])
        self.assertEqual([0.0] * 8, actual["normalization_offsets"])
        # CHANGED means 10.5/14.5, variances 1/3, SE sqrt(1/6), t sqrt(96), df 6.
        changed = rows["CHANGED"]
        self.assertEqual(4, changed["log2_fold_change"])
        self.assertAlmostEqual(math.sqrt(96), changed["t"])
        self.assertAlmostEqual(6, changed["df"])
        # Integrating the df=6 t density gives this polynomial in u=t/sqrt(6+t^2).
        u = math.sqrt(16 / 17)
        p = 1 - (15 * u - 10 * u**3 + 3 * u**5) / 8
        self.assertAlmostEqual(p, changed["p_value"], places=13)
        self.assertAlmostEqual(4 * p, changed["q_value"], places=13)
        self.assertEqual([4, 4], changed["observed"])
        for name in ("BATCH", "NULL_A", "NULL_B"):
            self.assertEqual(0, rows[name]["log2_fold_change"])
            self.assertEqual(1, rows[name]["p_value"])
            self.assertFalse(rows[name]["significant"])
        self.assertEqual([1, 3], rows["MISSING"]["observed"])
        for name in ("MISSING", "ZERO1", "LOW_PEPTIDE", "DECOY", "CONTAMINANT"):
            self.assertEqual("untestable", rows[name]["status"])
            self.assertIsNone(rows[name]["significant"])
            self.assertIsNone(rows[name]["p_value"])
        first = actual["qc"][0]
        self.assertEqual(1024 + 256 + 512 + 2048 + 7 * 1024 + 1024, first["total_intensity"])
        self.assertAlmostEqual(1 / 13, first["missing_rate"])

    def test_reference_welch_and_bh(self):
        actual = self.api.welch_test([1, 2, 3], [2, 3, 4], minimum=3)
        self.assertAlmostEqual(math.sqrt(1.5), actual["t"])
        self.assertAlmostEqual(4, actual["df"])
        u = math.sqrt(3 / 11)
        self.assertAlmostEqual(1 - (3 * u - u**3) / 2, actual["p_value"], places=13)
        tiny = self.api.welch_test([1e-160, 2e-160, 3e-160], [2e-160, 3e-160, 4e-160])
        self.assertAlmostEqual(actual["t"], tiny["t"])
        self.assertAlmostEqual(actual["p_value"], tiny["p_value"])
        self.assertEqual([0.03, 0.04, 0.04], self.api.benjamini_hochberg([0.01, 0.04, 0.03]))
        self.assertEqual([], self.api.benjamini_hochberg([]))
        self.assertEqual([0, 1], self.api.benjamini_hochberg([0, 1]))
        for groups in (([], [1, 2]), ([1], [1, 2]), ([0, 0], [1, 2]), ([1, 2], [3, 3]),
                       ([float("nan"), 2], [1, 2]), ([True, 2], [1, 2])):
            with self.subTest(groups=groups), self.assertRaisesRegex(ValueError, "^[a-z-]+:"):
                self.api.welch_test(*groups)
        for value in ([True], [-0.1], [1.1], [float("inf")], "bad"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                self.api.benjamini_hochberg(value)
        with self.assertRaisesRegex(ValueError, "^untestable-replicates:"):
            self.api.welch_test([1, 2], [3, 4], minimum=3)

    def test_missing_values_and_declared_imputation(self):
        folder = self.folder()
        self.pack["analysis_spec"]["missing_rule"] = {"method": "constant-log2", "value": 8}
        self.freeze()
        actual = self.run_pack(folder)
        normalized = next(row for row in actual["normalized"] if row["protein_id"] == "MISSING")
        self.assertEqual([True, True, True, False, True, False, False, False], normalized["imputed"])
        self.assertEqual([False, False, False, True, False, True, True, True], normalized["observed"])
        self.assertEqual([8, 8, 8, 9, 8, 10, 9, 10], normalized["log2_intensities"])
        row = next(row for row in actual["differential"] if row["protein_id"] == "MISSING")
        self.assertEqual([1, 3], row["observed"])
        self.assertEqual("untestable", row["status"])
        unchanged = self.api.validate_proteomics_pack(FIXTURE / "pack.json")
        before = next(row for row in unchanged["normalized"] if row["protein_id"] == "MISSING")
        self.assertIsNone(before["log2_intensities"][0])

    def test_median_normalization_with_known_sample_scaling(self):
        folder = self.folder()
        def rescale(table):
            for row in table["proteins"]:
                if row["values"][0] is not None:
                    row["values"][0] *= 4
        self.input(folder, "intensities", rescale)
        actual = self.run_pack(folder)
        self.assertEqual([2.0] + [0.0] * 7, actual["normalization_offsets"])
        baseline = self.api.validate_proteomics_pack(FIXTURE / "pack.json")
        self.assertEqual(baseline["differential"], actual["differential"])

    def test_exploratory_changes_and_qc_failures_remain_visible(self):
        folder = self.folder()
        self.pack["exploratory"] = True
        self.pack["analysis_spec"]["contrast"] = ["B", "A"]
        self.pack["analysis_spec"]["normalization"] = "none"
        self.pack["claims"][0]["status"] = "suggestive"
        actual = self.run_pack(folder)
        self.assertTrue(actual["exploratory"])
        self.assertEqual(-4, actual["differential"][0]["log2_fold_change"])
        self.pack["claims"] = []
        self.pack["analysis_spec"]["qc"]["max_missing_rate"] = 0
        self.freeze()
        actual = self.run_pack(folder)
        self.assertTrue(any(row["failures"] for row in actual["qc"]))
        self.assertTrue(all(row["status"] == "untestable" for row in actual["differential"]))
        self.assertTrue(all("sample-qc" in row["reasons"] for row in actual["differential"]))

    def test_cli_json_success_and_all_seeded_refusals(self):
        result = subprocess.run([sys.executable, str(CLI), str(FIXTURE / "pack.json")],
                                capture_output=True, text=True, timeout=CALL_TIMEOUT)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("proteomics-result-v1", json.loads(result.stdout)["schema"])
        cases = json.loads((FIXTURE / "negative-cases.json").read_bytes())["cases"]
        self.assertEqual(set(CASES), {case["id"] for case in cases})
        for case in cases:
            with self.subTest(case=case["id"]):
                result = subprocess.run([sys.executable, str(CLI), str(FIXTURE / case["path"])],
                                        capture_output=True, text=True, timeout=CALL_TIMEOUT)
                self.assertEqual(2, result.returncode)
                self.assertEqual("", result.stdout)
                self.assertTrue(json.loads(result.stderr)["finding"].startswith(case["finding"] + ":"))
                self.assertNotIn("Traceback", result.stderr)

    def test_snapshot_cache_and_no_writes(self):
        folder = self.folder()
        before = {path.name: path.read_bytes() for path in folder.iterdir()}
        calls = []
        original = self.api._json
        def counted(raw):
            calls.append(raw)
            return original(raw)
        with patch.object(self.api, "_json", side_effect=counted):
            self.api.validate_proteomics_pack(folder / "pack.json")
        self.assertEqual(4, len(calls))
        self.assertEqual(before, {path.name: path.read_bytes() for path in folder.iterdir()})


class ProteomicsSeededTests(_Fixture):
    pass


def _seeded_test(name):
    def test(self):
        cases = json.loads((FIXTURE / "negative-cases.json").read_bytes())["cases"]
        case = next(case for case in cases if case["id"] == name)
        with self.assertRaisesRegex(ValueError, "^" + case["finding"] + ":"):
            self.api.validate_proteomics_pack(FIXTURE / case["path"])
    return test


for _case in CASES:
    setattr(ProteomicsSeededTests, "test_" + _case.replace("-", "_"), _seeded_test(_case))


class ProteomicsHardeningTests(_Fixture):
    def test_posthoc_imputation_cannot_override_frozen_missing_rule(self):
        folder = self.folder()
        self.pack["exploratory"] = True
        self.pack["claims"][0]["status"] = "suggestive"
        self.pack["analysis_spec"]["missing_rule"] = {"method": "constant-log2", "value": 8}
        self.refuse(folder, "undeclared-imputation")

    def test_record_shapes_controls_and_inclusive_thresholds(self):
        folder = self.folder()
        baseline = self.api.validate_proteomics_pack(FIXTURE / "pack.json")
        self.pack["analysis_spec"]["qc"] = {
            "max_missing_rate": max(row["missing_rate"] for row in baseline["qc"]),
            "max_log2_total_deviation": max(row["log2_total_deviation"] for row in baseline["qc"]),
        }
        self.pack["analysis_spec"]["minimum_peptides"] = 3
        self.pack["analysis_spec"]["minimum_observed_per_group"] = 4
        self.freeze()
        self.run_pack(folder)
        self.pack["claims"] = []
        for constant in (0, -1000, 1000):
            self.pack["analysis_spec"]["missing_rule"] = {"method": "constant-log2", "value": constant}
            self.freeze()
            self.run_pack(folder)
        for rule in ({}, {"method": []}, {"method": "zero"}, {"method": "constant-log2", "value": True},
                     {"method": "constant-log2", "value": -1001}, {"method": "constant-log2", "value": 1001}):
            self.pack["analysis_spec"]["missing_rule"] = rule
            with self.assertRaisesRegex(ValueError, "^(invalid-record|missing-rule):"):
                self.run_pack(folder)
        for field, value in (("samples", []), ("samples", 0), ("samples", "bad")):
            self.pack = json.loads((FIXTURE / "pack.json").read_bytes())
            self.input(folder, "design", lambda design: design.update({field: value}))
            self.refuse(folder, "invalid-record")
        shutil.copyfile(FIXTURE / "design.json", folder / "design.json")
        for field, value in (("proteins", []), ("proteins", 0), ("sample_ids", []), ("sample_ids", "bad")):
            self.pack = json.loads((FIXTURE / "pack.json").read_bytes())
            shutil.copyfile(FIXTURE / "intensities.json", folder / "intensities.json")
            self.input(folder, "intensities", lambda table: table.update({field: value}))
            self.refuse(folder, "invalid-record")
        self.pack = json.loads((FIXTURE / "pack.json").read_bytes())
        shutil.copyfile(FIXTURE / "intensities.json", folder / "intensities.json")
        self.pack["analysis_spec"]["qc"]["max_missing_rate"] = "bad"
        self.refuse(folder, "invalid-record")
        self.pack = json.loads((FIXTURE / "pack.json").read_bytes())
        self.pack["extra"] = 1
        self.refuse(folder, "invalid-record")

    def test_json_duplicate_nonfinite_huge_depth_roots_and_text(self):
        bad = (b'{"x":1,"x":2}', b'{"x":{"y":1,"y":2}}', b'{"x":NaN}',
               b'{"x":Infinity}', b'{"x":1e999}', b'{"x":' + b'9' * 5000 + b'}',
               b'[]', b'null', b'false', b'{}garbage', b'\xff',
               b'{"x":' + b'[' * 2000 + b'0' + b']' * 2000 + b'}')
        for raw in bad:
            with self.subTest(raw=raw[:60]), self.assertRaisesRegex(ValueError, "^[a-z-]+:"):
                self.api._json(raw)
        with patch.object(self.api, "MAX_DEPTH", 2):
            self.api._json(b'{"x":[[]]}')
            with self.assertRaisesRegex(ValueError, "^input-limit:"):
                self.api._json(b'{"x":[[[]]]}')
        with patch.object(self.api, "MAX_TEXT", 3):
            self.api._json(b'{"xxx":"abc"}')
            for raw in (b'{"xxxx":1}', b'{"x":"abcd"}'):
                with self.assertRaisesRegex(ValueError, "^input-limit:"):
                    self.api._json(raw)
        with patch.object(self.api, "MAX_ITEMS", 2):
            self.api._json(b'{"x":[0,0]}')
            with self.assertRaisesRegex(ValueError, "^input-limit:"):
                self.api._json(b'{"x":[0,0,0]}')
        for value in (float("nan"), {"x": set()}, {"x": "\ud800"}):
            with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                self.api.specification_hash(value)

    def test_paths_and_hashes(self):
        folder = self.folder()
        for value in (None, [], True, b"pack.json", "a\x00b/pack.json", "", "a" * (self.api.MAX_TEXT + 1)):
            with self.subTest(entry=value), self.assertRaisesRegex(ValueError, "^input-path:"):
                self.api.validate_proteomics_pack(value)
        with self.assertRaisesRegex(ValueError, "^input-file:"):
            self.api.validate_proteomics_pack("a" * self.api.MAX_TEXT)
        for value in ("../design.json", "/design.json", "a\\b.json", "a//b.json", "./design.json",
                      "a/../design.json", "C:design.json", ".", "", [], "a\x00.json"):
            with self.subTest(value=value):
                self.pack["inputs"]["design"]["path"] = value
                with self.assertRaisesRegex(ValueError, "^(input-path|invalid-record):"):
                    self.run_pack(folder)
        self.pack["inputs"]["design"]["path"] = "design.json"
        self.pack["inputs"]["design"]["sha256"] = "0" * 64
        self.refuse(folder, "input-hash")

    def test_integer_fields_and_numeric_edges(self):
        folder = self.folder()
        for key in ("minimum_peptides", "minimum_observed_per_group"):
            for value in (True, 3.0, "3", [], 0):
                with self.subTest(key=key, value=value):
                    previous = self.pack["analysis_spec"][key]
                    self.pack["analysis_spec"][key] = value
                    self.refuse(folder, "invalid-record")
                    self.pack["analysis_spec"][key] = previous
        for field in ("seed", "peptides"):
            for value in (True, 3.0, "3"):
                with self.subTest(field=field, value=value):
                    self.pack = json.loads((FIXTURE / "pack.json").read_bytes())
                    def mutate(table):
                        if field == "seed":
                            table[field] = value
                        else:
                            table["proteins"][0][field] = value
                    self.input(folder, "intensities", mutate)
                    self.refuse(folder, "invalid-record")
        self.pack = json.loads((FIXTURE / "pack.json").read_bytes())
        shutil.copyfile(FIXTURE / "intensities.json", folder / "intensities.json")
        for alpha in (0, 1):
            self.pack["claims"] = []
            self.pack["analysis_spec"]["alpha"] = alpha
            self.freeze()
            self.run_pack(folder)
        for alpha in (True, -0.1, 1.1, "0.05"):
            self.pack["analysis_spec"]["alpha"] = alpha
            self.refuse(folder, "invalid-record")

    def test_limits_before_scaled_work(self):
        for constant, equal, too_small in (("MAX_SAMPLES", 8, 7), ("MAX_PROTEINS", 15, 14),
                                           ("MAX_VALUES", 120, 119), ("MAX_CLAIMS", 1, 0),
                                           ("MAX_RECORDS", 4, 3)):
            with self.subTest(constant=constant):
                with patch.object(self.api, constant, equal):
                    self.api.validate_proteomics_pack(FIXTURE / "pack.json")
                with patch.object(self.api, constant, too_small), self.assertRaisesRegex(ValueError, "^input-limit:"):
                    self.api.validate_proteomics_pack(FIXTURE / "pack.json")
        folder = self.folder()
        self.input(folder, "intensities", lambda table: table.update(proteins=[]))
        self.refuse(folder, "invalid-record")
        # A deterministic actual oversize sample list is refused before duplicate-ID construction.
        self.pack = json.loads((FIXTURE / "pack.json").read_bytes())
        self.input(folder, "design", lambda design: design.update(samples=[design["samples"][0]] * 257))
        self.refuse(folder, "input-limit")

    def test_claim_status_keys_wording_and_all_positive_states(self):
        folder = self.folder()
        for key in ("status", "kind", "protein_id"):
            before = self.pack["claims"][0][key]
            self.pack["claims"][0][key] = []
            self.refuse(folder, "invalid-record")
            self.pack["claims"][0][key] = before
        for status in ("supported", "replicated", "suggestive", "unavailable"):
            for word in self.api.WORDING_FAMILIES:
                with self.subTest(status=status, word=word):
                    self.pack["claims"][0].update(status=status, text=f"The result {word.upper()}s the system.")
                    self.refuse(folder, "claim-boundary")
        self.pack["claims"][0].update(status="unavailable", text="Records are unavailable.", support=[])
        self.run_pack(folder)
        for text in ("supported", "replicated", "suggestive", "significant"):
            self.pack["claims"][0]["text"] = text
            self.refuse(folder, "claim-boundary")
        for status in ("supported", "replicated", "suggestive"):
            for field, value in (("kind", "review-approval"), ("result", "computed-agreement")):
                self.pack = json.loads((FIXTURE / "pack.json").read_bytes())
                self.pack["claims"][0]["status"] = status
                evidence = json.loads((FIXTURE / "association.json").read_bytes())
                evidence[field] = value
                self.pack["claims"][0]["support"] = [self.write(folder, "other.json", evidence)]
                self.refuse(folder, "claim-evidence")

    def test_external_alias_by_path_and_by_hash(self):
        folder = self.folder()
        evidence = json.loads((FIXTURE / "association.json").read_bytes())
        for origin in ("external", "independent", "preregistered"):
            evidence["origin"] = origin
            identity = self.write(folder, "source.json", evidence)
            self.pack["claims"][0]["support"] = [identity]
            self.pack["study_outputs"] = [copy.deepcopy(identity)]
            self.refuse(folder, "dependent-evidence")
            alias = self.write(folder, "copy.json", evidence)
            self.pack["study_outputs"] = [alias]
            self.refuse(folder, "dependent-evidence")
        self.pack["study_outputs"] = []
        self.run_pack(folder)

    def test_nonregular_oversize_symlink_and_open_swap(self):
        folder = self.folder()
        path = folder / "intensities.json"
        raw = path.read_bytes()
        for kind in ("fifo", "directory", "symlink"):
            path.unlink()
            if kind == "fifo":
                os.mkfifo(path)
            elif kind == "directory":
                path.mkdir()
            else:
                path.symlink_to(folder / "design.json")
            self.refuse(folder, "input-file")
            if kind == "directory":
                path.rmdir()
            else:
                path.unlink()
            path.write_bytes(raw)
        with path.open("wb") as handle:
            handle.truncate(self.api.MAX_BYTES + 1)
        self.refuse(folder, "input-file")
        path.write_bytes(raw)
        original = os.open
        swapped = False
        def swap(name, flags, *args, **kwargs):
            nonlocal swapped
            if name == "intensities.json" and not swapped:
                swapped = True
                path.unlink()
                os.mkfifo(path)
            return original(name, flags, *args, **kwargs)
        with patch.object(self.api.os, "open", side_effect=swap):
            self.refuse(folder, "input-file")

    def test_read_bound_growth_and_end_hash_recheck(self):
        folder = self.folder()
        small = folder / "small.json"
        raw = b'{"x":0}'
        small.write_bytes(raw)
        with self.api._Bundle(folder / "pack.json") as bundle:
            with patch.object(self.api, "MAX_BYTES", len(raw)):
                self.assertEqual(raw, bundle.read(Path("small.json"))[0])
            with patch.object(self.api, "MAX_BYTES", len(raw) - 1), self.assertRaisesRegex(ValueError, "^input-file:"):
                bundle.read(Path("small.json"))
        original = os.fdopen
        class Growing:
            def __init__(self, handle):
                self.handle = handle
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.handle.close()
            def fileno(self):
                return self.handle.fileno()
            def read(self, bound):
                value = self.handle.read(bound)
                with small.open("ab") as handle:
                    handle.write(b" ")
                return value
        with self.api._Bundle(folder / "pack.json") as bundle:
            with patch.object(self.api.os, "fdopen", side_effect=lambda *a, **k: Growing(original(*a, **k))):
                with self.assertRaisesRegex(ValueError, "^input-file:"):
                    bundle.read(Path("small.json"))
        recheck = self.api._Bundle.recheck
        def replace(bundle):
            path = folder / "intensities.json"
            replacement = folder / "replacement.json"
            replacement.write_bytes(path.read_bytes())
            os.replace(replacement, path)
            return recheck(bundle)
        with patch.object(self.api._Bundle, "recheck", replace):
            self.refuse(folder, "input-changed")

    def test_root_and_ancestor_swaps_at_exact_open_and_lstat(self):
        for hook in ("open", "lstat"):
            with self.subTest(hook=hook):
                folder = self.folder()
                original = getattr(os, hook)
                swapped = False
                def swap(name, *args, **kwargs):
                    nonlocal swapped
                    if str(name) == folder.name and not swapped:
                        swapped = True
                        if hook == "lstat":
                            result = original(name, *args, **kwargs)
                        other = folder.parent / "original"
                        folder.rename(other)
                        folder.symlink_to(other, target_is_directory=True)
                        if hook == "lstat":
                            return result
                    return original(name, *args, **kwargs)
                with patch.object(self.api.os, hook, side_effect=swap):
                    with self.assertRaisesRegex(ValueError, "^input-(file|root):"):
                        self.api.validate_proteomics_pack(folder / "pack.json")
                self.assertTrue(swapped)
        folder = self.folder()
        recheck = self.api._Bundle.recheck
        def replace(bundle):
            folder.rename(folder.parent / "old")
            shutil.copytree(folder.parent / "old", folder)
            return recheck(bundle)
        with patch.object(self.api._Bundle, "recheck", replace):
            self.refuse(folder, "input-changed")


if __name__ == "__main__":
    unittest.main()
