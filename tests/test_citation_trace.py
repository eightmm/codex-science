from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codex_science.citation_trace import extract_identifiers, trace_citations

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/literature-review-reviewed-run"
CLI = ROOT / "scripts/trace_citations.py"


class CitationTraceTests(unittest.TestCase):
    def test_extracts_and_normalizes_all_supported_ids(self) -> None:
        text = ("DOI:10.1234/ABC.XYZ., PMID: 12345678; https://pubmed.ncbi.nlm.nih.gov/87654321/ "
                "PMCID:PMC12345 arXiv:2401.12345v2 https://arxiv.org/abs/hep-th/9901001.")
        ids = [item["identifier"] for item in extract_identifiers(text)]
        self.assertEqual(ids, ["doi:10.1234/abc.xyz", "pmid:12345678", "pmid:87654321", "pmcid:PMC12345", "arxiv:2401.12345", "arxiv:hep-th/9901001"])

    def test_doi_markup_and_balanced_parentheses(self) -> None:
        text = ("[x](https://doi.org/10.1234/abc), (doi:10.1234/abc), "
                "`doi:10.1234/abc`, **doi:10.1234/abc**, "
                "doi:10.1016/S0146-6736(20)30183-5. "
                "https://dx.doi.org/10.5678/Other_ID>`")
        ids = [item["identifier"] for item in extract_identifiers(text)]
        self.assertEqual(ids, ["doi:10.1234/abc", "doi:10.1016/s0146-6736(20)30183-5", "doi:10.5678/other_id"])

    def test_arxiv_subject_class_and_numeric_boundaries(self) -> None:
        text = "arXiv:math.GT/0309136 arXiv:math.GT/03091367 arXiv:2401.123456 PMID:1234567890"
        ids = [item["identifier"] for item in extract_identifiers(text)]
        self.assertEqual(ids, ["arxiv:math.gt/0309136"])
        bare = extract_identifiers("**10.1126/Science.1232033** and https://example.org/10.1234/not-a-citation")
        self.assertEqual([item["identifier"] for item in bare], ["doi:10.1126/science.1232033"])

    def test_trace_orphan_and_uncited_included(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / "run"
            shutil.copytree(EXAMPLE, run)
            report = run / "report.md"
            report.write_text(report.read_text() + "\nCites DOI:10.0000/example.primary.1 and DOI:10.9999/missing.2.\n", encoding="utf-8")
            result = trace_citations(run)
            self.assertEqual(result["counts"], {"cited": 2, "traced": 1, "orphans": 1, "uncited_included": 0})
            self.assertEqual(result["orphans"][0]["identifier"], "doi:10.9999/missing.2")
            self.assertEqual(result, trace_citations(run))

    def test_study_is_cited_when_any_of_its_ids_is_cited(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / "run"
            shutil.copytree(EXAMPLE, run)
            study_path = run / "studies.json"
            study = json.loads(study_path.read_text(encoding="utf-8"))
            study["studies"][0]["pmid"] = "12345678"
            study_path.write_text(json.dumps(study), encoding="utf-8")
            (run / "report.md").write_text("Cites doi:10.0000/example.primary.1.\n", encoding="utf-8")
            self.assertEqual(trace_citations(run)["uncited_included"], [])

    def test_uncited_included_study_has_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / "run"
            shutil.copytree(EXAMPLE, run)
            result = trace_citations(run)
            self.assertEqual(result["uncited_included"], [{
                "study_id": "study-example-1", "ids": ["doi:10.0000/example.primary.1"]
            }])

    def test_refuses_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / "run"
            shutil.copytree(EXAMPLE, run)
            (run / "report.md").unlink()
            (run / "report.md").symlink_to(EXAMPLE / "report.md")
            with self.assertRaises(ValueError):
                trace_citations(run)

    def test_cli_exit_codes_from_other_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / "run"
            cwd = Path(temp) / "cwd"
            shutil.copytree(EXAMPLE, run)
            cwd.mkdir()
            env = dict(os.environ)
            env.pop("PYTHONPATH", None)
            def invoke(*extra: str) -> subprocess.CompletedProcess[str]:
                return subprocess.run([sys.executable, str(CLI), "--run-dir", str(run), *extra], cwd=cwd, env=env, text=True, capture_output=True)
            self.assertEqual(invoke().returncode, 0)
            report = run / "report.md"
            report.write_text(report.read_text() + "\nDOI:10.9999/orphan.1\n", encoding="utf-8")
            self.assertEqual(invoke("--require-traced").returncode, 1)
            invalid = invoke("--report", "../outside.md")
            self.assertEqual(invalid.returncode, 2)
            self.assertEqual(json.loads(invalid.stdout)["schema"], "citation-trace-error-v1")

    def test_cli_rejects_malformed_manifest_artifact_paths(self) -> None:
        for malformed in (None, 17):
            with self.subTest(path=malformed), tempfile.TemporaryDirectory() as temp:
                run = Path(temp) / "run"
                shutil.copytree(EXAMPLE, run)
                manifest_path = run / "manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if malformed is None:
                    manifest["artifacts"][0].pop("path")
                else:
                    manifest["artifacts"][0]["path"] = malformed
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                env = dict(os.environ)
                env.pop("PYTHONPATH", None)
                result = subprocess.run([sys.executable, str(CLI), "--run-dir", str(run)], cwd=temp,
                                        env=env, text=True, capture_output=True)
                self.assertEqual(result.returncode, 2)
                payload = json.loads(result.stdout)
                self.assertEqual(payload["schema"], "citation-trace-error-v1")
                self.assertIn("path", payload["error"]["message"])

    def test_require_traced_fails_when_no_report_is_examined(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / "run"
            shutil.copytree(EXAMPLE, run)
            manifest_path = run / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"] = [item for item in manifest["artifacts"] if item.get("kind") != "report"]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            env = dict(os.environ)
            env.pop("PYTHONPATH", None)
            result = subprocess.run([sys.executable, str(CLI), "--run-dir", str(run), "--require-traced"], cwd=temp,
                                    env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["require_traced_failure"], "no_report_examined")


if __name__ == "__main__":
    unittest.main()
