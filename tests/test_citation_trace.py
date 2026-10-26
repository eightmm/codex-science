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
from codex_science.literature_v2 import normalize_identifier

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
                "https://dx.doi.org/10.5678/Other_ID>` |10.1234/abc| "
                "|[paper](https://doi.org/10.1234/abc)|")
        ids = [item["identifier"] for item in extract_identifiers(text)]
        self.assertEqual(ids, ["doi:10.1234/abc", "doi:10.1016/s0146-6736(20)30183-5", "doi:10.5678/other_id"])

    def test_arxiv_subject_class_and_numeric_boundaries(self) -> None:
        text = ("arXiv:math.GT/0309136 arXiv:cond-mat.stat-mech/0101001 "
                "arXiv:physics.bio-ph/0412001 arXiv:hep-th/9901001 arXiv:q-bio.PE/0601001 "
                "arXiv:math.GT/03091367 arXiv:2401.123456 PMID:1234567890")
        ids = [item["identifier"] for item in extract_identifiers(text)]
        self.assertEqual(ids, ["arxiv:math/0309136", "arxiv:cond-mat/0101001",
                               "arxiv:physics/0412001", "arxiv:hep-th/9901001",
                               "arxiv:q-bio/0601001"])
        for identifier in ids:
            self.assertEqual(identifier, normalize_identifier(identifier))

    def test_arxiv_dotted_identifiers_round_trip_through_shared_normalizer(self) -> None:
        for raw in ("math.GT/0309136", "cond-mat.stat-mech/0101001", "physics.bio-ph/0412001",
                    "hep-th/9901001", "q-bio.PE/0601001"):
            with self.subTest(identifier=raw):
                traced = [item["identifier"] for item in extract_identifiers("arXiv:" + raw)]
                normalized = normalize_identifier("arxiv:" + raw)
                self.assertEqual([normalized], traced)
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

    def test_pmid_in_identifiers_is_citation_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / "run"
            shutil.copytree(EXAMPLE, run)
            study_path = run / "studies.json"
            study = json.loads(study_path.read_text(encoding="utf-8"))
            study["studies"][0]["identifiers"] = ["pmid:12345678"]
            study["studies"][0].pop("pmid", None)
            study["studies"][0]["persistent_id"] = "doi:10.0000/example.primary.1"
            study_path.write_text(json.dumps(study), encoding="utf-8")
            (run / "report.md").write_text("Cites PMID:12345678.\n", encoding="utf-8")
            result = trace_citations(run)
            self.assertEqual(["pmid:12345678"], [item["identifier"] for item in result["traced"]])
            self.assertEqual([], result["orphans"])

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

    def test_cli_output_written_on_success_and_require_failure_but_not_on_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / "run"
            shutil.copytree(EXAMPLE, run)
            env = dict(os.environ)
            env.pop("PYTHONPATH", None)
            out = Path(temp) / "citation-trace.json"
            def invoke(target: Path, *extra: str) -> subprocess.CompletedProcess[str]:
                return subprocess.run([sys.executable, str(CLI), "--run-dir", str(run), "--output", str(target), *extra], cwd=temp, env=env, text=True, capture_output=True)
            ok = invoke(out)
            self.assertEqual(ok.returncode, 0)
            self.assertEqual(json.loads(out.read_text()), json.loads(ok.stdout))
            report = run / "report.md"
            report.write_text(report.read_text() + "\nDOI:10.9999/orphan.1\n", encoding="utf-8")
            failed = invoke(out, "--require-traced")
            self.assertEqual(failed.returncode, 1)
            self.assertEqual(json.loads(out.read_text())["require_traced_failure"], "orphan_citations")
            self.assertEqual(list(Path(temp).glob(".*.tmp")), [])
            out.write_text("keep")
            fresh = Path(temp) / "fresh.json"
            for target in (out, fresh):
                bad = invoke(target, "--report", "../outside.md")
                self.assertEqual(bad.returncode, 2)
                self.assertEqual(json.loads(bad.stdout)["schema"], "citation-trace-error-v1")
                self.assertEqual(bad.stderr.strip(), f"note: {target} was not written because the run is invalid")
            self.assertEqual(out.read_text(), "keep")
            self.assertFalse(fresh.exists())

    def test_cli_unwritable_output_is_error_exit_two_without_success_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            env = dict(os.environ)
            env.pop("PYTHONPATH", None)
            target = Path(temp) / "no-such-dir" / "out.json"
            result = subprocess.run([sys.executable, str(CLI), "--run-dir", str(EXAMPLE), "--output", str(target)], cwd=temp,
                                    env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 2, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual((payload["schema"], payload["error"]["code"]), ("citation-trace-error-v1", "output_write_failed"))
            self.assertIn(str(target), payload["error"]["message"])

    def test_documented_gate_sequence_leaves_a_clean_registered_bundle(self) -> None:
        from codex_science.artifacts import validate_bundle
        from codex_science.review import review_manifest
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        scripts = ROOT / "scripts"
        def run_cli(temp: str, name: str, *args: str) -> None:
            done = subprocess.run([sys.executable, str(scripts / name), *args], cwd=temp, env=env, text=True, capture_output=True)
            self.assertEqual(done.returncode, 0, f"{name} {args}: {done.stdout}{done.stderr}")
        for variant in ("edited-report", "existing-review-evidence"):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temp:
                run = Path(temp) / "run"
                shutil.copytree(EXAMPLE, run)
                first_refresh = ["package_run.py", "refresh", "--run-dir", str(run)]
                if variant == "edited-report":
                    run_cli(temp, *first_refresh, "--invalidate-review")
                    (run / "report.md").write_text((run / "report.md").read_text(encoding="utf-8") + "\nEdited after refresh.\n", encoding="utf-8")
                else:
                    first_refresh.append("--invalidate-review")
                kinds = ["--kind", "citation-trace.json=citation-trace", "--kind", "claim-sufficiency.json=claim-sufficiency"]
                run_cli(temp, *first_refresh)
                run_cli(temp, "check_claim_sufficiency.py", "--run-dir", str(run), "--tier", "standard", "--output", str(run / "claim-sufficiency.json"))
                run_cli(temp, "trace_citations.py", "--run-dir", str(run), "--require-traced", "--output", str(run / "citation-trace.json"))
                run_cli(temp, "package_run.py", "refresh", "--run-dir", str(run), *kinds)
                run_cli(temp, "validate_artifact.py", str(run / "manifest.json"), "--review-output", str(run / "deterministic-review.json"))
                manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
                kinds_seen = {item["path"]: item["kind"] for item in manifest["artifacts"]}
                self.assertEqual((kinds_seen["citation-trace.json"], kinds_seen["claim-sufficiency.json"]), ("citation-trace", "claim-sufficiency"))
                review = review_manifest(manifest, run, sidecars=validate_bundle(manifest, run))
                self.assertFalse([f for f in review["findings"] if f["code"] in {"error-object-artifact", "uninspectable-generated-artifact"}])

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
