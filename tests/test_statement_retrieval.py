from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codex_science.statement_retrieval import retrieve_statement_sources

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/literature-review-reviewed-run"
CLI = ROOT / "scripts/retrieve_statement_sources.py"


class StatementRetrievalTests(unittest.TestCase):
    def update_artifact_digests(self, run: Path) -> None:
        manifest_path = run / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for artifact in manifest["artifacts"]:
            artifact["sha256"] = hashlib.sha256((run / artifact["path"]).read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    def make_run(self, temp: Path, report: str) -> Path:
        run = temp / "run"
        shutil.copytree(EXAMPLE, run)
        (run / "report.md").write_text(report, encoding="utf-8")
        self.update_artifact_digests(run)
        return run

    def add_support_excerpt(self, run: Path, text: str, url: str) -> None:
        source = run / "source.txt"
        source.write_text(text, encoding="utf-8")
        studies_path = run / "studies.json"
        studies = json.loads(studies_path.read_text(encoding="utf-8"))
        study = studies["studies"][0]
        study["url"] = url
        study["persistent_ids"] = ["doi:10.9999/other-study.1"]
        study["support_excerpts"] = [{
            "claim_id": "claim-method-effect", "text": text,
            "source_artifact": "source.txt",
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        }]
        studies_path.write_text(json.dumps(studies), encoding="utf-8")
        self.update_artifact_digests(run)

    def test_deterministic_ranking_ties_and_cited_rank(self):
        with tempfile.TemporaryDirectory() as temp:
            report = "Intervention improved the prespecified outcome in a controlled study DOI:10.0000/example.primary.1."
            run = self.make_run(Path(temp), report)
            first = retrieve_statement_sources(run, top_k=4)
            second = retrieve_statement_sources(run, top_k=4)
            self.assertEqual(first, second)
            candidates = first["statements"][0]["candidates"]
            self.assertEqual(2, first["statements"][0]["cited_source_rank"])
            self.assertIn("intervention", candidates[0]["matched_terms"])

    def test_ledger_returned_ids_do_not_fan_out_or_rank_as_cited_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            cited_id = "pmid:12345678"
            run = self.make_run(Path(temp), f"Intervention prespecified outcome improved {cited_id}.")
            ledger = run / "queries.jsonl"
            record = json.loads(ledger.read_text(encoding="utf-8"))
            record["query"] = "intervention prespecified outcome improved"
            record["returned_record_ids"] = [cited_id, *(f"pmid:{12345000 + i}" for i in range(12))]
            record["url"] = 42
            ledger.write_text(json.dumps(record) + "\n", encoding="utf-8")
            self.update_artifact_digests(run)

            statement = retrieve_statement_sources(run, top_k=3)["statements"][0]
            query_candidates = [item for item in statement["candidates"] if item["source"].startswith("queries.jsonl#")]
            self.assertEqual(1, len(query_candidates))
            self.assertIsNone(query_candidates[0]["identifier"])
            self.assertIsNone(query_candidates[0]["url"])
            self.assertTrue(any(item["source"].startswith("studies.json#") for item in statement["candidates"]))
            self.assertIsNone(statement["cited_source_rank"])

    def test_pmcid_study_candidate_has_pubmed_central_url(self):
        with tempfile.TemporaryDirectory() as temp:
            run = self.make_run(Path(temp), "A PMC study record.")
            studies_path = run / "studies.json"
            studies = json.loads(studies_path.read_text(encoding="utf-8"))
            studies["studies"][0]["persistent_id"] = "pmcid:PMC1234567"
            studies_path.write_text(json.dumps(studies), encoding="utf-8")
            self.update_artifact_digests(run)

            candidates = retrieve_statement_sources(run)["statements"][0]["candidates"]
            source = next(item for item in candidates if item["identifier"] == "pmcid:PMC1234567")
            self.assertEqual("https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/", source["url"])

    def test_support_excerpt_candidate_uses_study_url_only_for_primary_id(self):
        with tempfile.TemporaryDirectory() as temp:
            excerpt = "Intervention improved prespecified outcome in the controlled study participants."
            run = self.make_run(Path(temp), excerpt)
            self.add_support_excerpt(run, excerpt, "https://example.org/primary-study")

            candidates = retrieve_statement_sources(run)["statements"][0]["candidates"]
            study_candidates = [item for item in candidates if item["source"] == "studies.json#study-example-1"]
            excerpt_candidates = [item for item in candidates if "/support_excerpts/0" in item["source"]]
            primary_study = next(item for item in study_candidates if item["identifier"] == "doi:10.0000/example.primary.1")
            secondary_study = next(item for item in study_candidates if item["identifier"] == "doi:10.9999/other-study.1")
            self.assertEqual(2, len(excerpt_candidates))
            primary = next(item for item in excerpt_candidates if item["identifier"] == "doi:10.0000/example.primary.1")
            secondary = next(item for item in excerpt_candidates if item["identifier"] == "doi:10.9999/other-study.1")
            self.assertEqual("https://example.org/primary-study", primary["url"])
            self.assertNotEqual("https://example.org/primary-study", secondary["url"])
            self.assertEqual("https://example.org/primary-study", primary_study["url"])
            self.assertNotEqual("https://example.org/primary-study", secondary_study["url"])

    def test_no_candidates_and_no_cited_rank(self):
        with tempfile.TemporaryDirectory() as temp:
            run = self.make_run(Path(temp), "Unrelated nebula quasar terminology.")
            statement = retrieve_statement_sources(run)["statements"][0]
            self.assertEqual([], statement["candidates"])
            self.assertIsNone(statement["cited_source_rank"])

    def test_equal_scores_use_source_path_tie_break(self):
        with tempfile.TemporaryDirectory() as temp:
            phrase = "repeatable shared query terms"
            run = self.make_run(Path(temp), phrase)
            query_path = run / "queries.jsonl"
            base = {"accessed_at": "2026-07-19T00:00:00Z", "query": phrase,
                    "response_sha256": "2" * 64, "source": "PubMed", "status": "complete"}
            with query_path.open("a", encoding="utf-8") as handle:
                for index in (2, 3):
                    handle.write(json.dumps(dict(base, query_id=f"q-tie-{index}")) + "\n")
            self.update_artifact_digests(run)
            ranked = retrieve_statement_sources(run)["statements"][0]["candidates"]
            self.assertEqual(ranked[0]["score"], ranked[1]["score"])
            self.assertEqual(["queries.jsonl#1", "queries.jsonl#2"],
                             [ranked[0]["source"], ranked[1]["source"]])

    def test_malformed_study_record_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            run = self.make_run(Path(temp), "A claim.")
            studies = json.loads((run / "studies.json").read_text())
            studies["studies"] = ["bad-record"]
            (run / "studies.json").write_text(json.dumps(studies))
            manifest = json.loads((run / "manifest.json").read_text())
            for artifact in manifest["artifacts"]:
                artifact["sha256"] = hashlib.sha256((run / artifact["path"]).read_bytes()).hexdigest()
            (run / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaises((ValueError, TypeError)):
                retrieve_statement_sources(run)

    def test_path_escape_refused_by_api_and_cli_errors_are_nonzero(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run = self.make_run(root, "A claim.")
            outside = root / "outside.md"
            outside.write_text("secret")
            with self.assertRaises(ValueError):
                retrieve_statement_sources(run, ["../outside.md"])
            env = dict(os.environ)
            env.pop("PYTHONPATH", None)
            result = subprocess.run([sys.executable, str(CLI), str(run), "--report", "../outside.md"],
                                    cwd=root, env=env, text=True, capture_output=True)
            self.assertEqual(2, result.returncode)
            self.assertIn("invalid input", result.stderr)

    def test_module_imports_no_network_library(self):
        tree = ast.parse((ROOT / "src/codex_science/statement_retrieval.py").read_text())
        imported = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import)
                    for alias in node.names}
        imported.update(node.module.split(".")[0] for node in ast.walk(tree)
                        if isinstance(node, ast.ImportFrom) and node.module)
        self.assertTrue(imported.isdisjoint({"requests", "urllib", "httpx", "aiohttp", "socket"}))


if __name__ == "__main__":
    unittest.main()
