"""Offline synthetic fixture acceptance, adversarial inputs and refusal boundaries."""
import copy
import hashlib
import importlib
import json
import math
import os
import re
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/workflow-single-cell-pseudobulk"
CLI = ROOT / "scripts/validate_single_cell_pseudobulk_pack.py"
CALL_TIMEOUT = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "30"))


class SingleCellPseudobulkTests(unittest.TestCase):
    def setUp(self):
        self.api = importlib.import_module("codex_science.single_cell_pseudobulk_pack")
        self.pack = json.loads((FIXTURE / "pack.json").read_bytes())

    def _negative(self, name):
        cases = json.loads((FIXTURE / "negative-cases.json").read_bytes())["cases"]
        case = next(item for item in cases if item["id"] == name)
        with self.assertRaisesRegex(ValueError, "^" + case["finding"] + ":"):
            self.api.validate_single_cell_pseudobulk_pack(FIXTURE / case["path"])

    def _folder(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        folder = Path(temporary.name)
        for path in FIXTURE.glob("*.json"):
            shutil.copyfile(path, folder / path.name)
        return folder

    def _write(self, folder, filename, value):
        raw = (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode()
        (folder / filename).write_bytes(raw)
        return {"path": filename, "sha256": hashlib.sha256(raw).hexdigest()}

    def _run(self, folder=None):
        folder = folder or self._folder()
        self._write(folder, "pack.json", self.pack)
        return self.api.validate_single_cell_pseudobulk_pack(folder / "pack.json")

    def _freeze(self):
        self.pack["frozen_spec"] = copy.deepcopy(self.pack["analysis_spec"])
        self.pack["frozen_sha256"] = self.api.specification_hash(self.pack["frozen_spec"])

    def _input(self, folder, name, mutate):
        filename = self.pack["inputs"][name]["path"]
        value = json.loads((folder / filename).read_bytes())
        mutate(value)
        self.pack["inputs"][name] = self._write(folder, filename, value)
        if name == "design":
            self.pack["frozen_design_sha256"] = self.pack["inputs"][name]["sha256"]

    def test_planted_fixture_and_expected_artifact(self):
        result = self.api.validate_single_cell_pseudobulk_pack(FIXTURE / "pack.json")
        expected = json.loads((FIXTURE / "expected.json").read_bytes())
        self.assertEqual(result, expected)
        self.assertEqual(result, self.api.validate_single_cell_pseudobulk_pack(FIXTURE / "pack.json"))
        self.assertEqual(["EFFECT"], [row["gene_id"] for row in result["differential"] if row["significant"]])
        self.assertEqual("statistical-only", result["evidence_level"])
        self.assertEqual("unavailable", result["review"])
        self.assertEqual(list(self.api.STAGES), result["stages"])
        self.assertEqual(8, len(result["pseudobulk"]))
        self.assertTrue(all(row["donors"] == [4, 4] for row in result["differential"]))
        self.assertEqual(4, len(result["excluded_cells"]))
        self.assertEqual(8, len(result["excluded_units"]))
        self.assertEqual("ZERO", result["excluded_genes"][0]["gene_id"])

    def test_pseudoreplication(self):
        self._negative("pseudoreplication")

    def test_donor_confounding(self):
        self._negative("donor-confounding")

    def test_donor_adjustment(self):
        self._negative("donor-adjustment")

    def test_batch_confounding(self):
        self._negative("batch-confounding")

    def test_insufficient_donors(self):
        self._negative("insufficient-donors")

    def test_missing_marker(self):
        self._negative("missing-marker")

    def test_circular_label(self):
        self._negative("circular-label")

    def test_post_result_qc(self):
        self._negative("post-result-qc")

    def test_post_result_aggregation(self):
        self._negative("post-result-aggregation")

    def test_minimum_cells(self):
        self._negative("minimum-cells")

    def test_no_correction(self):
        self._negative("no-correction")

    def test_filtered_correction(self):
        self._negative("filtered-correction")

    def test_namespace_mismatch(self):
        self._negative("namespace-mismatch")

    def test_annotation_mismatch(self):
        self._negative("annotation-mismatch")

    def test_unit_and_cell_type_counts_are_bounded_before_allocation(self):
        for name in ("MAX_UNITS", "MAX_CELL_TYPES"):
            with self.subTest(name=name), patch.object(self.api, name, 1), self.assertRaisesRegex(
                    ValueError, "^invalid-record: at most"):
                self._run()

    def test_oversized_unit_table_is_refused_before_batch_scans(self):
        folder = self._folder()

        def grow(design):
            template = design["biological_units"][0]
            design["biological_units"] = [
                dict(template, id=f"X{i}", donor_id=f"D{i}", batch=f"B{i}")
                for i in range(self.api.MAX_UNITS + 1)]

        self._input(folder, "design", grow)
        with self.assertRaisesRegex(ValueError, "^invalid-record: at most 1000 units"):
            self._run(folder)

    def test_causal_mechanism(self):
        self._negative("causal-mechanism")
        folder = self._folder()
        for status in ("supported", "replicated", "suggestive"):
            for text in ("Compound A binds target B with high affinity",
                         "Compound A binds target B.", "Compound A has high affinity for target B.",
                         "Compound A shows binding to target B.", "Compound A inhibits target B.",
                         "Compound A shows inhibition of target B.", "Compound A activates target B.",
                         "Compound A has a mechanism involving target B.",
                         "BINDING", "AFFINITY", "INHIBITION", "ACTIVATION", "MECHANISM"):
                self.pack["claims"][0].update(status=status, text=text)
                with self.subTest(status=status, text=text), self.assertRaisesRegex(
                        ValueError, "^claim-boundary: only descriptive or associational statistical wording is allowed"):
                    self._run(folder)
        for text in ("Labels xbinding, xaffinity, xinhibition, xactivation and xmechanism are associated with counts.",
                     "Labels xbind and xaffinit and xinhibit are associated with counts."):
            self.pack["claims"][0].update(status="suggestive", text=text)
            self.assertEqual("statistical-only", self._run(folder)["evidence_level"])
        for text in ("Compound A is an effective cancer drug", "Compound A is effectively cured"):
            self.pack["claims"][0].update(status="supported", text=text)
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "^claim-boundary:"):
                self._run(folder)
        for text in ("The association is supported and statistically significant.", "Gene X is differentially expressed."):
            self.pack["claims"][0].update(status="unavailable", text=text)
            with self.subTest(status="unavailable", text=text), self.assertRaisesRegex(
                    ValueError, "^claim-boundary: unavailable claim cannot assert positive evidence"):
                self._run(folder)
        for text in ("", 0, None):
            self.pack["claims"][0]["text"] = text
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                self._run(folder)
        self.pack["claims"][0]["text"] = "Compound A binds target B with high affinity"
        self._write(folder, "pack.json", self.pack)
        refusal = subprocess.run([sys.executable, str(CLI), str(folder / "pack.json")],
                                 capture_output=True, text=True, timeout=CALL_TIMEOUT)
        self.assertEqual(2, refusal.returncode)
        self.assertIn("claim-boundary:", refusal.stderr)
        self.assertEqual("", refusal.stdout)

    def test_declared_seed_requires_integer(self):
        folder = self._folder()
        for seed in (True, False, 20261103.0, 0.0, 1.5, "20261103", "", None, [], {}):
            self._input(folder, "counts", lambda value: value.update(seed=seed))
            with self.subTest(seed=seed), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                self._run(folder)
        self._write(folder, "pack.json", self.pack)
        refusal = subprocess.run([sys.executable, str(CLI), str(folder / "pack.json")],
                                 capture_output=True, text=True, timeout=CALL_TIMEOUT)
        self.assertEqual(2, refusal.returncode)
        self.assertIn("invalid-record:", refusal.stderr)
        self.assertEqual("", refusal.stdout)
        for seed in (0, -1, 20261103, 10**100, -10**100):
            self._input(folder, "counts", lambda value: value.update(seed=seed))
            with self.subTest(seed=seed):
                self.assertEqual("statistical-only", self._run(folder)["evidence_level"])
        self._input(folder, "counts", lambda value: value.pop("seed"))
        self.assertEqual("statistical-only", self._run(folder)["evidence_level"])

    def test_trajectory(self):
        self._negative("trajectory")

    def test_fate(self):
        self._negative("fate")

    def test_clinical(self):
        self._negative("clinical")

    def test_physical(self):
        self._negative("physical")

    def test_review_approval(self):
        self._negative("review-approval")

    def test_computed_kind(self):
        self._negative("computed-kind")

    def test_computed_result(self):
        self._negative("computed-result")

    def test_unavailable_as_negative(self):
        self._negative("unavailable-as-negative")

    def test_external_alias(self):
        self._negative("external-alias")

    def test_welch_and_bh_known_values(self):
        result = self.api.welch_test([1., 2., 3.], [2., 3., 4.], 3)
        self.assertAlmostEqual(0.2878641347266908, result["p_value"], places=12)
        self.assertAlmostEqual(4, result["df"])
        self.assertAlmostEqual(1, result["log2_fold_change"])
        self.assertEqual([0.03, 0.04, 0.04], self.api.benjamini_hochberg([0.01, 0.04, 0.03]))
        self.assertAlmostEqual(1, self.api.welch_test([1., 2., 3.], [1., 2., 3.])["p_value"])

    def test_welch_degenerate_and_minimum_edges(self):
        for group in ([], [0.], [0., 0.], [1., 1.], [math.nan, 1.], [math.inf, 1.], [True, 1.], ["bad", 1.]):
            with self.subTest(group=group), self.assertRaisesRegex(ValueError, "^[a-z-]+:"):
                self.api.welch_test(group, [1., 2.])
        for minimum in (0, 1, True, "3", 2.5, 4):
            with self.subTest(minimum=minimum), self.assertRaisesRegex(ValueError, "^[a-z-]+:"):
                self.api.welch_test([1., 2., 3.], [2., 3., 4.], minimum)

    def test_threshold_types_and_limits(self):
        original = copy.deepcopy(self.pack)
        for key in ("min_counts", "min_genes", "min_cells", "gene_min_units"):
            for bad in (None, 0, -1, True, "3", 1.5):
                with self.subTest(key=key, bad=bad):
                    self.pack = copy.deepcopy(original)
                    self.pack["analysis_spec"]["qc"][key] = bad
                    self._freeze()
                    with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                        self._run()
        for key in ("alpha", "max_mito_fraction"):
            for bad in (None, -0.01, 1.01, True, "0.5"):
                self.pack = copy.deepcopy(original)
                target = self.pack["analysis_spec"] if key == "alpha" else self.pack["analysis_spec"]["qc"]
                target[key] = bad
                self._freeze()
                with self.subTest(key=key, bad=bad), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                    self._run()
        for minimum in (None, 0, 1, True, "3", 3.5):
            self.pack = copy.deepcopy(original)
            self.pack["analysis_spec"]["minimum_donors"] = minimum
            self._freeze()
            with self.subTest(minimum=minimum), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                self._run()
        self.pack = copy.deepcopy(original)
        self.pack["analysis_spec"].update(minimum_donors=4)
        self.pack["analysis_spec"]["qc"].update(min_counts=1000, min_genes=6, min_cells=3,
                                                     gene_min_units=8, max_mito_fraction=0.01)
        self._freeze()
        self.assertEqual(8, len(self._run()["pseudobulk"]))
        for alpha in (0, 1):
            self.pack["analysis_spec"]["alpha"] = alpha
            self.pack["claims"] = []
            self._freeze()
            self.assertEqual(3 * alpha, sum(row["significant"] for row in self._run()["differential"]))

    def test_qc_beyond_each_retention_edge(self):
        original = copy.deepcopy(self.pack)
        for key, value in (("min_counts", 1001), ("min_genes", 7), ("min_cells", 4), ("max_mito_fraction", 0)):
            self.pack = copy.deepcopy(original)
            self.pack["analysis_spec"]["qc"][key] = value
            self.pack["included_units"] = []
            self._freeze()
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "^insufficient-donors:"):
                self._run()

    def test_unsupported_aggregation_model_and_covariates(self):
        original = copy.deepcopy(self.pack)
        for key, value, code in (("aggregation", "", "aggregation-rule"), ("aggregation", 0, "aggregation-rule"),
                                 ("aggregation", "median", "aggregation-rule"), ("model", "edgeR", "unsupported-model")):
            self.pack = copy.deepcopy(original)
            self.pack["analysis_spec"][key] = value
            with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, "^" + code + ":"):
                self._run()
        self.pack = copy.deepcopy(original)
        folder = self._folder()
        self._input(folder, "design", lambda value: value.update(adjustment=["age"]))
        with self.assertRaisesRegex(ValueError, "^unsupported-model:"):
            self._run(folder)

    def test_gene_qc_empty_family_and_empty_cells(self):
        self.pack["analysis_spec"]["qc"]["gene_min_units"] = 9
        self._freeze()
        with self.assertRaisesRegex(ValueError, "^degenerate-data:"):
            self._run()
        folder = self._folder()
        self._input(folder, "counts", lambda value: value.update(cells=[]))
        with self.assertRaisesRegex(ValueError, "^invalid-record:"):
            self._run(folder)

    def test_exploratory_revisions_and_biological_sample_unit(self):
        self.pack["exploratory"] = True
        self.pack["analysis_spec"]["aggregation"] = "mean-raw-counts"
        result = self._run()
        self.assertTrue(result["exploratory"])
        self.assertAlmostEqual(1000, sum(result["pseudobulk"][0]["counts"]))
        self.pack["analysis_spec"]["replicate_unit"] = "biological_sample"
        self.assertEqual(8, len(self._run()["pseudobulk"]))
        folder = self._folder()
        self._input(folder, "labels", lambda value: value["labels"][0].update(origin="study", genes=["EFFECT"]))
        self.assertTrue(self._run(folder)["exploratory"])

    def test_reference_labels_and_hash_alias(self):
        folder = self._folder()
        evidence = dict(schema="single-cell-pseudobulk-evidence-v1", fixture=True, kind="reference-evidence",
                        result="reference-support", cell_types=["T", "rare"], reference_id="fixture-reference")
        ref = self._write(folder, "atlas.json", evidence)
        self._input(folder, "labels", lambda value: value.update(labels=[dict(cell_type=x, method="reference",
                    origin="external", source=ref, genes=[], reference_id="fixture-reference") for x in ("T", "rare")]))
        self.assertEqual(8, len(self._run(folder)["pseudobulk"]))
        self.pack["study_outputs"].append(ref)
        alias = dict(ref, path="atlas-copy.json")
        shutil.copyfile(folder / "atlas.json", folder / "atlas-copy.json")
        self._input(folder, "labels", lambda value: value["labels"][0].update(source=alias))
        with self.assertRaisesRegex(ValueError, "^label-independence:"):
            self._run(folder)

    def test_external_label_features_and_missing_reference_support(self):
        folder = self._folder()
        self._input(folder, "labels", lambda value: value["labels"][0].update(genes=["EFFECT"]))
        with self.assertRaisesRegex(ValueError, "^circular-label:"):
            self._run(folder)
        self._input(folder, "labels", lambda value: value["labels"][0].update(method="reference", genes=[], reference_id="missing"))
        with self.assertRaisesRegex(ValueError, "^label-evidence:"):
            self._run(folder)

    def test_undeclared_independence_and_preregistration_fields(self):
        for key in ("independent", "preregistered"):
            folder = self._folder()
            self._input(folder, "labels", lambda value: value["labels"][0].update({key: True}))
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                self._run(folder)
        self.pack["preregistered"] = True
        with self.assertRaisesRegex(ValueError, "^invalid-record:"):
            self._run()

    def test_every_positive_status_checks_both_evidence_fields(self):
        folder = self._folder()
        for status in ("supported", "replicated", "suggestive"):
            for field, value in (("kind", "review-approval"), ("kind", "computed-record"),
                                 ("result", "review-approved"), ("result", "numerical-agreement")):
                evidence = json.loads((FIXTURE / "observation.json").read_bytes())
                evidence[field] = value
                ref = self._write(folder, "claim-evidence.json", evidence)
                self.pack["claims"][0].update(status=status, support=[ref])
                with self.subTest(status=status, field=field), self.assertRaisesRegex(ValueError, "^claim-evidence:"):
                    self._run(folder)
        self.pack["claims"][0].update(status="unavailable", support=[])
        self.assertEqual("unavailable", self._run(folder)["review"])
        evidence.update(kind="unavailable", result="unavailable")
        ref = self._write(folder, "claim-evidence.json", evidence)
        self.pack["claims"][0].update(status="unsupported", support=[ref])
        with self.assertRaisesRegex(ValueError, "^unavailable-evidence:"):
            self._run(folder)

    def test_json_duplicate_nonfinite_huge_deep_and_wrong_roots(self):
        samples = [b'', b'[]', b'null', b'true', b'{"a":1,"a":2}', b'{"x":{"a":1,"a":2}}',
                   b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e9999}', b'{"x":' + b'9'*5000 + b'}',
                   b'{"x":' + b'['*2000 + b'0' + b']'*2000 + b'}', b'\xff']
        for raw in samples:
            with self.subTest(raw=raw[:30]), self.assertRaisesRegex(ValueError, "^invalid-json:"):
                self.api._json(raw)
        self.assertEqual({"n": 0}, self.api._json(b'{"n":0}'))
        self.assertEqual({"n": 1e100}, self.api._json(b'{"n":1e100}'))
        self.assertIsInstance(self.api._json(b'{"x":' + b'['*64 + b'0' + b']'*64 + b'}'), dict)
        with self.assertRaisesRegex(ValueError, "^invalid-json:"):
            self.api._json(b'{"x":' + b'['*65 + b'0' + b']'*65 + b'}')
        folder = self._folder()
        (folder / "counts.json").write_bytes(b'{"x":{"a":1,"a":2}}')
        raw = (folder / "counts.json").read_bytes()
        self.pack["inputs"]["counts"]["sha256"] = hashlib.sha256(raw).hexdigest()
        with self.assertRaisesRegex(ValueError, "^invalid-json:"):
            self._run(folder)

    def test_artifact_paths_and_symlink_components(self):
        for value in ("", ".", "../counts.json", "/counts.json", "a/../counts.json", "./counts.json",
                      "a//counts.json", "a\\counts.json", "C:/counts.json", "a\x00b", 0, True, []):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "^[a-z-]+:"):
                self.api._relative(value)
        folder = self._folder()
        (folder / "linked").symlink_to(folder, target_is_directory=True)
        self.pack["inputs"]["counts"]["path"] = "linked/counts.json"
        with self.assertRaisesRegex(ValueError, "^input-file:"):
            self._run(folder)

    def test_nonregular_oversized_and_exact_size_limit(self):
        folder = self._folder()
        target = folder / "probe.json"
        self.assertEqual(64 * 1024 * 1024, self.api.MAX_BYTES)
        with patch.object(self.api, "MAX_BYTES", 64):
            target.write_bytes(b'{}' + b' '*62)
            self.assertEqual(64, len(self.api._read(folder, PurePosixPath("probe.json"))[0]))
            target.write_bytes(b'{}' + b' '*63)
            with self.assertRaisesRegex(ValueError, "^input-file:"):
                self.api._read(folder, PurePosixPath("probe.json"))
            target.write_bytes(b'')
            with self.assertRaisesRegex(ValueError, "^invalid-json:"):
                self.api._Bundle(target)
        target.unlink()
        target.mkdir()
        with self.assertRaisesRegex(ValueError, "^input-file:"):
            self.api._Bundle(target)
        target.rmdir()
        os.mkfifo(target)
        with self.assertRaisesRegex(ValueError, "^input-file:"):
            self.api._Bundle(target)
        target.unlink()
        target.symlink_to(folder / "counts.json")
        with self.assertRaisesRegex(ValueError, "^input-file:"):
            self.api._Bundle(target)

    def test_fifo_swapped_after_lstat_does_not_block(self):
        folder = self._folder()
        real_stat = os.lstat
        swapped = False
        def swap(path, *args, **kwargs):
            nonlocal swapped
            info = real_stat(path, *args, **kwargs)
            if path == "pack.json" and not swapped:
                swapped = True
                (folder / "pack.json").unlink()
                os.mkfifo(folder / "pack.json")
            return info
        with patch.object(self.api.os, "lstat", side_effect=swap):
            with self.assertRaisesRegex(ValueError, "^input-file:"):
                self.api.validate_single_cell_pseudobulk_pack(folder / "pack.json")

    def test_end_recheck_and_single_parse_per_artifact(self):
        folder = self._folder()
        original = self.api._analyze
        def replace(bundle):
            result = original(bundle)
            path = folder / "counts.json"
            raw = path.read_bytes()
            path.unlink()
            path.write_bytes(raw)
            return result
        with patch.object(self.api, "_analyze", side_effect=replace):
            with self.assertRaisesRegex(ValueError, "^input-changed:"):
                self.api.validate_single_cell_pseudobulk_pack(folder / "pack.json")
        with patch.object(self.api, "_json", wraps=self.api._json) as parser:
            result = self.api.validate_single_cell_pseudobulk_pack(FIXTURE / "pack.json")
        self.assertEqual(len(result["input_identities"]), parser.call_count)

    def test_growing_file_and_post_qc_chemistry_confounding(self):
        folder = self._folder()
        real_fstat = os.fstat
        calls = 0
        def growing(descriptor):
            nonlocal calls
            info = real_fstat(descriptor)
            calls += 1
            if calls == 2:
                with (folder / "pack.json").open("ab") as handle:
                    handle.write(b' ')
                return real_fstat(descriptor)
            return info
        with patch.object(self.api.os, "fstat", side_effect=growing):
            with self.assertRaisesRegex(ValueError, "^input-file:"):
                self.api.validate_single_cell_pseudobulk_pack(folder / "pack.json")
        self._input(folder, "design", lambda value: [unit.update(chemistry=unit["condition"]) for unit in value["biological_units"]])
        with self.assertRaisesRegex(ValueError, "^chemistry-confounding:"):
            self._run(folder)
        self.pack = json.loads((FIXTURE / "pack.json").read_bytes())
        folder = self._folder()
        self._input(folder, "design", lambda value: [unit.update(chemistry="exposed" if unit["id"] == "U1"
                    else unit["condition"]) for unit in value["biological_units"]])
        self._input(folder, "counts", lambda value: [cell.update(doublet=True) for cell in value["cells"]
                    if cell["unit_id"] == "U1" and cell["cell_type"] == "T"])
        self.pack["included_units"] = [row for row in self.pack["included_units"] if row["unit_id"] != "U1"]
        with self.assertRaisesRegex(ValueError, "^chemistry-confounding:"):
            self._run(folder)

    def test_missing_hash_freeze_order_stage_order_and_bad_counts(self):
        original = copy.deepcopy(self.pack)
        for key, value, code in (("frozen_sha256", "0"*64, "freeze-hash"),
                                 ("freeze_before_results", False, "freeze-order"),
                                 ("stages", [], "stage-order")):
            self.pack = copy.deepcopy(original)
            self.pack[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "^" + code + ":"):
                self._run()
        self.pack = copy.deepcopy(original)
        self.pack["inputs"]["counts"]["sha256"] = "0"*64
        with self.assertRaisesRegex(ValueError, "^input-hash:"):
            self._run()
        for bad in (True, -1, 1.5, "2", None):
            self.pack = copy.deepcopy(original)
            folder = self._folder()
            self._input(folder, "counts", lambda value: value["cells"][0]["counts"].__setitem__(0, bad))
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                self._run(folder)

    def test_cli_success_refusal_help_and_no_writes(self):
        folder = self._folder()
        before = {p.name: p.read_bytes() for p in folder.iterdir()}
        good = subprocess.run([sys.executable, str(CLI), str(folder / "pack.json")], capture_output=True,
                              text=True, timeout=CALL_TIMEOUT)
        self.assertEqual(0, good.returncode, good.stderr)
        self.assertEqual("statistical-only", json.loads(good.stdout)["evidence_level"])
        bad = subprocess.run([sys.executable, str(CLI), str(folder / "negative-pseudoreplication.json")],
                             capture_output=True, text=True, timeout=CALL_TIMEOUT)
        self.assertEqual(2, bad.returncode)
        self.assertIn("pseudoreplication:", bad.stderr)
        self.assertNotIn("Traceback", bad.stderr)
        malformed = folder / "malformed.json"
        malformed.write_bytes(b'[]')
        bad = subprocess.run([sys.executable, str(CLI), str(malformed)], capture_output=True,
                             text=True, timeout=CALL_TIMEOUT)
        self.assertEqual(2, bad.returncode)
        self.assertNotIn("Traceback", bad.stderr)
        malformed.unlink()
        help_result = subprocess.run([sys.executable, str(CLI), "--help"], capture_output=True,
                                     text=True, timeout=CALL_TIMEOUT)
        self.assertEqual(0, help_result.returncode)
        self.assertIn("write nothing", help_result.stdout)
        self.assertNotIn("--output", help_result.stdout)
        self.assertEqual(before, {p.name: p.read_bytes() for p in folder.iterdir()})


    def test_aggregate_byte_budget_is_checked_before_reading(self):
        folder = self._folder()
        entry = folder / "pack.json"
        original_fdopen = os.fdopen
        def guarded_fdopen(*args, **kwargs):
            handle = original_fdopen(*args, **kwargs)
            handle.read = lambda *args: self.fail("must not read over budget")
            return handle
        with patch.object(os, "fdopen", side_effect=guarded_fdopen), \
                patch.object(self.api, "MAX_TOTAL_BYTES", 0, create=True), self.assertRaisesRegex(ValueError, "^input-limit:"):
            self.api.validate_single_cell_pseudobulk_pack(entry)
        with patch.object(self.api, "MAX_TOTAL_BYTES", entry.stat().st_size, create=True), self.assertRaisesRegex(ValueError, "^input-limit:"):
            self.api.validate_single_cell_pseudobulk_pack(entry)
        with patch.object(self.api, "MAX_TOTAL_BYTES", 256 * 1024 * 1024, create=True):
            self.api.validate_single_cell_pseudobulk_pack(entry)

        entry = folder / "probe.json"
        for raw, allowance, error in ((b'{}', 2, None), (b'{}', 1, "input-limit"), (b'', 0, "invalid-json")):
            entry.write_bytes(raw)
            digest = hashlib.sha256(raw).hexdigest()
            with self.subTest(raw=raw, byte_allowance=allowance), patch.object(self.api, "MAX_TOTAL_BYTES", allowance, create=True):
                def check():
                    bundle = self.api._Bundle(entry)
                    try:
                        return bundle.load({"path": entry.name, "sha256": digest})
                    finally:
                        getattr(bundle, "close", lambda: None)()
                if error:
                    with self.assertRaisesRegex(ValueError, "^" + error + ":"):
                        check()
                else:
                    self.assertEqual({}, check())

    def test_aggregate_json_allowance_precedes_each_parse(self):
        folder = self._folder()
        entry = folder / "pack.json"
        raw = entry.read_bytes()
        first = 1 + raw.count(b",") + len(re.findall(rb"[\[{](?=\s*[^\s\]}])", raw))
        for allowance, expected_calls in ((0, 0), (first - 1, 0), (first, 1)):
            with self.subTest(allowance=allowance), patch.object(self.api, "MAX_TOTAL_NODES", allowance, create=True), \
                    patch.object(self.api.json, "loads", wraps=json.loads) as parse:
                with self.assertRaisesRegex(ValueError, "^input-limit:"):
                    self.api.validate_single_cell_pseudobulk_pack(entry)
                self.assertEqual(expected_calls, parse.call_count)

    def test_hardlinks_share_one_snapshot_and_preserve_path_checks(self):
        folder = self._folder()
        entry = folder / "pack.json"
        raw = b'{"value":[0,1,2]}'
        digest = hashlib.sha256(raw).hexdigest()
        entry = folder / "probe.json"
        entry.write_bytes(raw)
        for index in range(100):
            os.link(entry, folder / f"alias-{index}.json")
        read_sizes = []
        original_read, original_fdopen = os.read, os.fdopen
        def tracked_read(*args, **kwargs):
            result = original_read(*args, **kwargs)
            read_sizes.append(len(result))
            return result
        def tracked_fdopen(*args, **kwargs):
            handle = original_fdopen(*args, **kwargs)
            read = handle.read
            def tracked(size=-1):
                result = read(size)
                read_sizes.append(len(result))
                return result
            handle.read = tracked
            return handle
        with patch.object(os, "read", side_effect=tracked_read), \
                patch.object(os, "fdopen", side_effect=tracked_fdopen), \
                patch.object(self.api, "MAX_TOTAL_BYTES", len(raw), create=True), \
                patch.object(self.api, "MAX_TOTAL_NODES", 5, create=True), \
                patch.object(self.api, "_json", wraps=self.api._json) as parse:
            bundle = self.api._Bundle(entry)
            self.addCleanup(lambda: getattr(bundle, "close", lambda: None)())
            load = lambda name: bundle.load({"path": name, "sha256": digest})
            first = load("probe.json")
            for index in range(100):
                self.assertIs(first, load(f"alias-{index}.json"))
            self.assertEqual(1, parse.call_count)
            self.assertEqual(101, len(bundle.cache))
            finish = bundle.recheck
            finish()
            self.assertEqual(2 * len(raw), sum(read_sizes))
            replacement = folder / "replacement.json"
            replacement.write_bytes(raw)
            replacement.replace(folder / "alias-99.json")
            with self.assertRaisesRegex(ValueError, "^input-changed:"):
                finish()

    def test_json_budget_empty_zero_equal_and_malformed(self):
        folder = self._folder()
        entry = folder / "pack.json"
        entry = folder / "probe.json"
        samples = ((b'{}', 1, None), (b'{"x":[{},{}]}', 4, None),
                   (b'{"x":[{},{}]}', 3, "input-limit"),
                   (b'{}', 0, "input-limit"), (b'', 1, "invalid-json"),
                   (b'{"x":', 2, "invalid-json"))
        for raw, allowance, error in samples:
            entry.write_bytes(raw)
            digest = hashlib.sha256(raw).hexdigest()
            with self.subTest(raw=raw, allowance=allowance), patch.object(self.api, "MAX_TOTAL_NODES", allowance, create=True):
                def check():
                    bundle = self.api._Bundle(entry)
                    try:
                        return bundle.load({"path": entry.name, "sha256": digest})
                    finally:
                        getattr(bundle, "close", lambda: None)()
                if error:
                    with self.assertRaisesRegex(ValueError, "^" + error + ":"):
                        check()
                else:
                    self.assertEqual(json.loads(raw), check())

    def test_bundle_ancestor_and_root_swaps_are_refused(self):
        original_open, original_lstat = os.open, os.lstat
        for ancestor in (False, True):
            for destination in ("directory", "symlink"):
                for point in ("open", "lstat", "between-reads", "final-read"):
                    with self.subTest(ancestor=ancestor, destination=destination, point=point), tempfile.TemporaryDirectory() as temporary:
                        base = Path(temporary)
                        component = base / "component"
                        root = component / "bundle" if ancestor else component
                        outside, saved = base / "outside", base / "saved"
                        shutil.copytree(FIXTURE, root)
                        shutil.copytree(component, outside, copy_function=os.link)
                        swapped = False
                        entry_opens = 0

                        def swap():
                            nonlocal swapped
                            if not swapped:
                                swapped = True
                                component.rename(saved)
                                if destination == "directory":
                                    outside.rename(component)
                                else:
                                    component.symlink_to(outside, target_is_directory=True)

                        def racing_open(path, flags, *args, **kwargs):
                            nonlocal entry_opens
                            if path == "pack.json" and kwargs.get("dir_fd") is not None:
                                entry_opens += 1
                                if point == "final-read" and entry_opens == 2:
                                    swap()
                            if kwargs.get("dir_fd") is not None and (
                                    point == "open" and path == component.name or
                                    point == "between-reads" and path == "design.json"):
                                swap()
                            return original_open(path, flags, *args, **kwargs)

                        def racing_lstat(path, *args, **kwargs):
                            info = original_lstat(path, *args, **kwargs)
                            if point == "lstat" and path == component.name and kwargs.get("dir_fd") is not None:
                                swap()
                            return info

                        with patch.object(os, "open", side_effect=racing_open), \
                                patch.object(os, "lstat", side_effect=racing_lstat):
                            with self.assertRaisesRegex(ValueError, "^(input-file|input-changed):"):
                                self.api.validate_single_cell_pseudobulk_pack(root / "pack.json")
                        self.assertTrue(swapped)


    def test_artifact_ancestor_swap_is_refused(self):
        folder = self._folder()
        entry = folder / "pack.json"
        nested, outside = folder / "nested", folder / "outside"
        nested.mkdir()
        outside.mkdir()
        target = nested / "probe.json"
        raw = b'{"value":0}'
        digest = hashlib.sha256(raw).hexdigest()
        target.write_bytes(raw)
        os.link(target, outside / target.name)
        original_open = os.open
        for racing in (False, True):
            bundle = self.api._Bundle(entry)
            swapped = False
            def swap(path, flags, *args, **kwargs):
                nonlocal swapped
                if racing and path == nested.name and kwargs.get("dir_fd") is not None and not swapped:
                    swapped = True
                    nested.rename(folder / "saved")
                    outside.rename(nested)
                return original_open(path, flags, *args, **kwargs)
            try:
                load = lambda: bundle.load({"path": "nested/probe.json", "sha256": digest})
                with patch.object(os, "open", side_effect=swap):
                    if racing:
                        with self.assertRaisesRegex(ValueError, "^input-changed:"):
                            load()
                        self.assertTrue(swapped)
                    else:
                        self.assertEqual({"value": 0}, load())
            finally:
                getattr(bundle, "close", lambda: None)()


if __name__ == "__main__":
    unittest.main()
