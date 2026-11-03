"""Acceptance and refusal tests use synthetic fixtures, never live data."""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from codex_science.bulk_expression_pack import (
    STAGES, benjamini_hochberg, hypergeometric_tail, specification_hash,
    validate_bulk_expression_pack, welch_test,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/workflow-bulk-expression-analysis"
CLI = ROOT / "scripts/validate_bulk_expression_pack.py"
CALL_TIMEOUT = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "30"))


class BulkExpressionTests(unittest.TestCase):
    def setUp(self):
        self.pack = json.loads((FIXTURE / "pack.json").read_text())

    def _run(self, record, counts=None, gene_sets=None):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            record = copy.deepcopy(record)
            for key, filename, content in (("expression", "counts.json", counts), ("gene_sets", "gene-sets.json", gene_sets)):
                raw = ((FIXTURE / filename).read_bytes() if content is None
                       else (json.dumps(content, sort_keys=True) + "\n").encode())
                (folder / filename).write_bytes(raw)
                record["inputs"][key] = {"path": filename, "sha256": hashlib.sha256(raw).hexdigest()}
            path = folder / "pack.json"
            path.write_text(json.dumps(record))
            return validate_bulk_expression_pack(path)

    def _freeze(self):
        self.pack["frozen_spec"] = copy.deepcopy(self.pack["analysis_spec"])
        self.pack["frozen_sha256"] = specification_hash(self.pack["frozen_spec"])

    def _negative(self, name):
        cases = json.loads((FIXTURE / "negative-cases.json").read_text())["cases"]
        case = next(item for item in cases if item["id"] == name)
        with self.assertRaisesRegex(ValueError, "^" + case["finding"] + ":"):
            validate_bulk_expression_pack(FIXTURE / case["path"])

    def test_planted_fixture(self):
        result = validate_bulk_expression_pack(FIXTURE / "pack.json")
        self.assertEqual(result, validate_bulk_expression_pack(FIXTURE / "pack.json"))
        self.assertEqual(list(STAGES), result["stages"])
        self.assertEqual("statistical-only", result["evidence_level"])
        self.assertEqual("unavailable", result["review"])
        self.assertEqual({"G01", "G02"}, {r["gene_id"] for r in result["differential"] if r["significant"]})
        self.assertTrue(result["enrichment"][0]["significant"])
        self.assertFalse(result["enrichment"][1]["significant"])
        expected = json.loads((FIXTURE / "expected.json").read_text())
        self.assertEqual(expected["selected_genes"], sorted(r["gene_id"] for r in result["differential"] if r["significant"]))
        self.assertAlmostEqual(expected["planted_set_p_value"], result["enrichment"][0]["p_value"])

    def test_batch_confounding(self):
        self._negative("batch-confounding")

    def test_post_result_contrast(self):
        self._negative("post-result-contrast")

    def test_post_result_threshold(self):
        self._negative("post-result-threshold")

    def test_no_correction(self):
        self._negative("no-correction")

    def test_filtered_correction(self):
        self._negative("filtered-correction")

    def test_missing_background(self):
        self._negative("missing-background")

    def test_incomplete_background(self):
        self._negative("incomplete-background")

    def test_namespace_mismatch(self):
        self._negative("namespace-mismatch")

    def test_annotation_mismatch(self):
        self._negative("annotation-mismatch")

    def test_insufficient_replicates(self):
        self._negative("insufficient-replicates")

    def test_outlier_missing_reason(self):
        self._negative("outlier-missing-reason")

    def test_outlier_missing_threshold(self):
        self._negative("outlier-missing-threshold")

    def test_causal_pathway(self):
        self._negative("causal-pathway")

    def test_exploratory_revision_and_equal_replicates(self):
        self.pack["analysis_spec"]["contrast"].reverse()
        self.pack["analysis_spec"]["minimum_replicates"] = 4
        self.pack["exploratory"] = True
        result = self._run(self.pack)
        self.assertTrue(result["exploratory"])
        self.assertLess(result["differential"][0]["log2_fold_change"], 0)

    def test_statistics_known_values_and_degenerate_edges(self):
        self.assertEqual([], benjamini_hochberg([]))
        for values, expected in (([0, 1], [0, 1]), ([0.01, 0.04, 0.03], [0.03, 0.04, 0.04]), ([1], [1])):
            with self.subTest(values=values):
                for actual, want in zip(benjamini_hochberg(values), expected):
                    self.assertAlmostEqual(want, actual)
        for bad in (-0.1, 1.1, True, "0", math.nan, math.inf):
            with self.subTest(p=bad), self.assertRaisesRegex(ValueError, "invalid-record"):
                benjamini_hochberg([bad])
        self.assertEqual(1, hypergeometric_tail(0, 0, 0, 0))
        self.assertEqual(1, hypergeometric_tail(20, 2, 0, 0))
        self.assertEqual(1, hypergeometric_tail(20, 20, 20, 20))
        self.assertAlmostEqual(1 / 190, hypergeometric_tail(20, 2, 2, 2))
        for values in ((-1, 0, 0, 0), (1, 2, 0, 0), (1, 1, 2, 0), (1, 1, 1, 2), ("1", 0, 0, 0)):
            with self.subTest(values=values), self.assertRaisesRegex(ValueError, "invalid-record"):
                hypergeometric_tail(*values)
        known = welch_test([1, 2, 3], [2, 3, 4])
        self.assertAlmostEqual(4, known["df"])
        self.assertAlmostEqual(0.2878641347266908, known["p_value"], places=12)
        self.assertAlmostEqual(0.5, welch_test([0, 2], [2, 2])["p_value"], places=12)
        for first, second, p_value in (([0, 0], [0, 0], 1), ([0, 0], [1, 1], 1), ([0, 1], [0, 1], 1)):
            self.assertEqual(p_value, welch_test(first, second)["p_value"])
        for first in ([], [1], [True, 2], [math.nan, 1], ["0", 1]):
            with self.subTest(first=first), self.assertRaisesRegex(ValueError, "invalid-record"):
                welch_test(first, [1, 2])

    def test_zero_variance_genes_are_untestable_in_full_bh_family(self):
        counts = json.loads((FIXTURE / "counts.json").read_text())
        for row in counts["genes"]:
            row["counts"] = [1000] * 8
        counts["genes"][0]["counts"] = [100] * 4 + [200] * 4
        counts["genes"][1]["counts"] = [200] * 4 + [100] * 4
        counts["genes"][2]["counts"] = [0] * 8
        for alpha in (0, 0.05, 1):
            with self.subTest(alpha=alpha):
                self.pack["analysis_spec"]["alpha"] = alpha
                self._freeze()
                result = self._run(self.pack, counts=counts)
                self.assertEqual(20, len(result["differential"]))
                for row in result["differential"]:
                    self.assertIsNone(row["t"])
                    self.assertIsNone(row["df"])
                    self.assertEqual(1, row["p_value"])
                    self.assertEqual(1, row["q_value"])
                    self.assertFalse(row["significant"])
                    self.assertTrue(any(row["gene_id"] in reason and "zero within-group variance" in reason
                                        for reason in result["limitations"]))
                self.assertGreater(result["differential"][0]["log2_fold_change"], 0)
                self.assertTrue(all(not row["overlap"] for row in result["enrichment"]))
        mixed = json.loads((FIXTURE / "counts.json").read_text())
        mixed["genes"][2]["counts"] = [0] * 8
        self.pack["analysis_spec"]["alpha"] = 0.05
        self._freeze()
        result = self._run(self.pack, counts=mixed)
        expected = benjamini_hochberg([row["p_value"] for row in result["differential"]])
        self.assertEqual(expected, [row["q_value"] for row in result["differential"]])
        self.assertEqual(1, result["differential"][2]["p_value"])
        self.assertFalse(result["differential"][2]["significant"])

    def test_background_refuses_untested_genes(self):
        genes = self.pack["analysis_spec"]["enrichment_background"][:]
        for background, code in ((genes + ["UNTESTED"], "enrichment-background"),
                                 (genes[:-1], "enrichment-background"), ([], "enrichment-background"),
                                 (0, "enrichment-background"), ("G01", "enrichment-background"),
                                 (genes + [genes[0]], "invalid-record")):
            with self.subTest(background=background), self.assertRaisesRegex(ValueError, "^" + code + ":"):
                self.pack["analysis_spec"]["enrichment_background"] = background
                self._freeze()
                self._run(self.pack)
        self.pack["analysis_spec"]["enrichment_background"] = list(reversed(genes))
        self._freeze()
        self.assertEqual(20, len(self._run(self.pack)["differential"]))

    def test_claim_wording_refuses_therapeutic_and_mechanistic_assertions(self):
        texts = (
            "Drug X is an effective treatment for patients with this disease.",
            "Knockdown of gene A induces the inflammatory pathway and determines the phenotype.",
            "Gene A has therapeutic value.", "Drug X shows efficacy.",
            "Gene A regulates the pathway.", "Gene A activates the pathway.",
            "Gene A represses the pathway.", "Gene A is responsible for the phenotype.",
            "Gene A is a biomarker of outcome.", "Gene A predicts survival.",
            "Gene A establishes prognosis.", "Gene A induced inflammation.",
            "Gene A determined the phenotype.", "Gene A regulated the pathway.",
            "Gene A activated the pathway.", "Gene A repressed the pathway.",
            "Drug X is EFFECTIVE.", "Gene A is a biomarker-of-outcome.",
        )
        for kind in ("descriptive", "associational"):
            for text in texts:
                with self.subTest(kind=kind, text=text), self.assertRaisesRegex(ValueError, "^claim-boundary:"):
                    self.pack["claims"][0].update(kind=kind, text=text, status="supported")
                    self._run(self.pack)
        for text in ("Treated samples have higher expression in this synthetic fixture.",
                     "Gene A expression is associated with the declared condition."):
            self.pack["claims"][0]["text"] = text
            self.assertEqual(text, self._run(self.pack)["claims"][0]["text"])

    def test_duplicate_json_keys_are_refused_in_each_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            for filename, key in (("pack.json", None), ("counts.json", "expression"),
                                  ("gene-sets.json", "gene_sets")):
                for nested in (False, True):
                    with self.subTest(filename=filename, nested=nested):
                        record = copy.deepcopy(self.pack)
                        for field, name in (("expression", "counts.json"), ("gene_sets", "gene-sets.json")):
                            (folder / name).write_bytes((FIXTURE / name).read_bytes())
                        original = (json.dumps(record) if key is None else (folder / filename).read_text())
                        if nested:
                            value = '"condition": "control"' if key is None else '"id": "G01"'
                            if key == "gene_sets":
                                value = '"id": "planted-fixture-set"'
                            self.assertIn(value, original)
                            raw = original.replace(value, value + ", " + value, 1).encode()
                        else:
                            raw = ('{"fixture": false, ' + original.lstrip()[1:]).encode()
                        if key is not None:
                            (folder / filename).write_bytes(raw)
                            record["inputs"][key]["sha256"] = hashlib.sha256(raw).hexdigest()
                            raw = json.dumps(record).encode()
                        path = folder / "pack.json"
                        path.write_bytes(raw)
                        with self.assertRaisesRegex(ValueError, "^invalid-record:.*duplicate JSON key"):
                            validate_bulk_expression_pack(path)

    def test_readme_explains_refusal_and_usage_share_exit_two(self):
        readme = (FIXTURE / "README.md").read_text()
        self.assertRegex(readme, r"(?is)exit(?:s)? 2.*argparse.*usage")

    def test_threshold_edges_and_shapes(self):
        for alpha in (0, 1):
            self.pack["analysis_spec"]["alpha"] = alpha
            self.pack["analysis_spec"]["enrichment_alpha"] = alpha
            self._freeze()
            result = self._run(self.pack)
            self.assertEqual(alpha == 1, result["differential"][0]["significant"])
        for alpha in (-1, 1.01, None, "0.05", True):
            with self.subTest(alpha=alpha), self.assertRaisesRegex(ValueError, "invalid-record"):
                self.pack["analysis_spec"]["alpha"] = alpha
                self._freeze()
                self._run(self.pack)
        for field, value in (("contrast", []), ("contrast", ["control"]), ("minimum_replicates", 0),
                             ("minimum_replicates", 1), ("minimum_replicates", 2.5), ("qc", None),
                             ("correction_genes", []), ("enrichment_background", [])):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.setUp()
                self.pack["analysis_spec"][field] = value
                self._freeze()
                self._run(self.pack)

    def test_qc_limits_and_outlier_retention(self):
        result = self._run(self.pack)
        libraries = [row["library_size"] for row in result["qc"]]
        detected = min(row["detected_genes"] for row in result["qc"])
        deviation = max(row["log_library_deviation"] for row in result["qc"])
        qc = self.pack["analysis_spec"]["qc"]
        qc.update(min_library_size=min(libraries), min_detected_genes=detected, max_log_library_deviation=deviation)
        self._freeze()
        self._run(self.pack)
        for field, value in (("min_library_size", max(libraries) + 1), ("min_detected_genes", detected + 1),
                             ("max_log_library_deviation", 0)):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "qc-failed"):
                prior = qc[field]
                qc[field] = value
                self._freeze()
                try:
                    self._run(self.pack)
                finally:
                    qc[field] = prior
        self.setUp()
        counts = json.loads((FIXTURE / "counts.json").read_text())
        for row in counts["genes"]:
            row["counts"][0] *= 100
        with self.assertRaisesRegex(ValueError, "qc-failed"):
            self._run(self.pack, counts=counts)
        self.pack["removed_samples"] = [{"sample_id": "S1", "reason": "Synthetic library-size outlier exceeds frozen bound.", "threshold": 2}]
        result = self._run(self.pack, counts=counts)
        self.assertTrue(result["qc"][0]["excluded"])
        self.assertEqual(self.pack["removed_samples"][0], result["qc"][0]["removal"])

    def test_identity_freeze_order_and_pretest_refusal(self):
        cases = (("frozen_sha256", "0" * 64, "freeze-hash"), ("freeze_before_testing", False, "freeze-order"),
                 ("stages", list(reversed(STAGES)), "stage-order"), ("fixture", False, "invalid-record"),
                 ("design", None, "invalid-record"), ("removed_samples", "S1", "invalid-record"))
        for field, value, code in cases:
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, code):
                self.setUp()
                self.pack[field] = value
                with patch("codex_science.bulk_expression_pack.welch_test", side_effect=AssertionError("test ran before validation")):
                    self._run(self.pack)
        self.setUp()
        self.pack["design"]["samples"][0]["covariates"] = {"age": 1}
        with self.assertRaisesRegex(ValueError, "unsupported-covariates"):
            self._run(self.pack)
        for path in ("../counts.json", "/counts.json", "missing.json"):
            with self.subTest(path=path), tempfile.TemporaryDirectory() as temporary:
                self.setUp()
                self.pack["inputs"]["expression"]["path"] = path
                local = Path(temporary) / "pack.json"
                local.write_text(json.dumps(self.pack))
                with self.assertRaisesRegex(ValueError, "input-identity|unavailable"):
                    validate_bulk_expression_pack(local)

    def test_malformed_inputs_and_evidence_boundaries(self):
        for count in (None, -1, True, "1", 1.5):
            counts = json.loads((FIXTURE / "counts.json").read_text())
            counts["genes"][0]["counts"][0] = count
            with self.subTest(count=count), self.assertRaisesRegex(ValueError, "invalid-record"):
                self._run(self.pack, counts=counts)
        counts = json.loads((FIXTURE / "counts.json").read_text())
        for row in counts["genes"]:
            row["counts"][0] = 0
        with self.assertRaisesRegex(ValueError, "qc-failed"):
            self._run(self.pack, counts=counts)
        for text in ("Numerical agreement establishes physical validity.", "The result establishes clinical efficacy."):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "claim-boundary"):
                self.pack["claims"][0]["text"] = text
                self._run(self.pack)
        self.setUp()
        self.pack["claims"][0].update(evidence_basis="unavailable", status="unsupported")
        with self.assertRaisesRegex(ValueError, "unavailable-evidence"):
            self._run(self.pack)
        self.pack["claims"][0]["status"] = "unavailable"
        self.assertEqual("unavailable", self._run(self.pack)["claims"][0]["status"])
        for field, value in (("kind", []), ("evidence_basis", {}), ("status", "passed"), ("id", "")):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.setUp()
                self.pack["claims"][0][field] = value
                self._run(self.pack)
        self.setUp()
        self.pack["claims"][0]["text"] = "Review approval establishes truth."
        with self.assertRaisesRegex(ValueError, "claim-boundary"):
            self._run(self.pack)

    def test_fifo_swapped_in_after_lstat_is_refused_without_blocking(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("mkfifo is unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            regular = folder / "regular.json"
            regular.write_bytes(b"{}")
            fifo = folder / "pipe.json"
            os.mkfifo(fifo)
            with patch.object(Path, "lstat", return_value=os.lstat(regular)):
                with self.assertRaisesRegex(ValueError, "^invalid-record:"):
                    validate_bulk_expression_pack(fifo)

    def test_input_byte_bound_hash_and_json_shapes(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            paths = [folder / "missing.json", folder]
            if hasattr(os, "mkfifo"):
                fifo = folder / "pipe.json"
                os.mkfifo(fifo)
                paths.append(fifo)
            for path in paths:
                with self.subTest(path=path), self.assertRaisesRegex(ValueError, "^invalid-record:"):
                    with patch("os.open", side_effect=AssertionError("non-file input was opened")):
                        validate_bulk_expression_pack(path)
        size = len((FIXTURE / "counts.json").read_bytes())
        with patch("codex_science.bulk_expression_pack.DEFAULT_MAX_JSON_BYTES", size):
            self._run(self.pack)
        for limit in (0, size - 1):
            with self.subTest(limit=limit), patch("codex_science.bulk_expression_pack.DEFAULT_MAX_JSON_BYTES", limit):
                with self.assertRaisesRegex(ValueError, "invalid-record"):
                    self._run(self.pack)
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            path = folder / "pack.json"
            source = folder / "counts.json"
            for raw in (b"", b"{", b"[]", b"\xff"):
                with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, "invalid-record"):
                    source.write_bytes(raw)
                    self.pack["inputs"]["expression"] = {"path": source.name, "sha256": hashlib.sha256(raw).hexdigest()}
                    path.write_text(json.dumps(self.pack))
                    validate_bulk_expression_pack(path)
            source.write_bytes((FIXTURE / "counts.json").read_bytes())
            self.pack["inputs"]["expression"]["sha256"] = "0" * 64
            path.write_text(json.dumps(self.pack))
            with self.assertRaisesRegex(ValueError, "input-identity"):
                validate_bulk_expression_pack(path)

    def test_cli_output_errors_and_preservation(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "result.json"
            command = [sys.executable, str(CLI), str(FIXTURE / "pack.json"), "--output", str(destination)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=CALL_TIMEOUT)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(json.loads(result.stdout), json.loads(destination.read_text()))
            original = destination.read_bytes()
            result = subprocess.run(command, capture_output=True, text=True, timeout=CALL_TIMEOUT)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(original, destination.read_bytes())
            command[2] = str(FIXTURE / "negative-causal-pathway.json")
            result = subprocess.run(command, capture_output=True, text=True, timeout=CALL_TIMEOUT)
            self.assertEqual(2, result.returncode)
            self.assertIn("claim-boundary", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(original, destination.read_bytes())
            malformed = Path(temporary) / "bad.json"
            for raw in ("", "{", "[]", "null"):
                malformed.write_text(raw)
                result = subprocess.run([sys.executable, str(CLI), str(malformed)], capture_output=True, text=True, timeout=CALL_TIMEOUT)
                self.assertEqual(2, result.returncode)
                self.assertNotIn("Traceback", result.stderr)
            for target in (FIXTURE / "pack.json", FIXTURE / "new-result.json"):
                result = subprocess.run([sys.executable, str(CLI), str(FIXTURE / "pack.json"), "--output", str(target)],
                                        capture_output=True, text=True, timeout=CALL_TIMEOUT)
                self.assertEqual(2, result.returncode)
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse((FIXTURE / "new-result.json").exists())
            help_result = subprocess.run([sys.executable, str(CLI), "--help"], capture_output=True, text=True, timeout=CALL_TIMEOUT)
            self.assertEqual(0, help_result.returncode)
            self.assertIn("--output", help_result.stdout)
            missing = subprocess.run([sys.executable, str(CLI)], capture_output=True, text=True, timeout=CALL_TIMEOUT)
            self.assertEqual(2, missing.returncode)
            self.assertNotIn("Traceback", missing.stderr)


if __name__ == "__main__":
    unittest.main()
