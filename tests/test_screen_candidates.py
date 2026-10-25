from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codex_science.source_operations_v3 import PubMedSearchV3

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/screen_candidates.py"


class ScreenCandidatesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.records = [
            {"id": "10001", "source": "MED", "doi": "10.1000/ABC", "title": "Alpha", "publication_date": "2024-01-02"},
            {"id": "PMC9001", "source": "PMC", "pmid": "10001", "title": "Alpha copy", "publication_date": "2024"},
            {"id": "10002", "source": "MED", "doi": "10.1000/other", "title": "Beta"},
        ]
        for query_id, rows in (("q1", self.records[:2]), ("q2", self.records[1:])):
            result = self.root / "raw/queries" / query_id / "result.json"
            result.parent.mkdir(parents=True, exist_ok=True)
            result.write_text(json.dumps({"records": rows}), encoding="utf-8")
        (self.root / "queries.jsonl").write_text("".join(json.dumps({"query_id": q, "source": "EuropePMC", "result_path": f"raw/queries/{q}/result.json"}) + "\n" for q in ("q1", "q2")), encoding="utf-8")
        (self.root / "sources").mkdir()
        (self.root / "sources/10001.abstract.txt").write_text("abstract alpha\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, *args, cwd=None):
        return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True, check=False, cwd=cwd)

    def pool(self):
        result = self.run_cli("pool", "--run-dir", self.root)
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads((self.root / "candidates.json").read_text(encoding="utf-8"))

    def test_pool_merges_identifier_chains_and_is_deterministic(self):
        pubmed_records = PubMedSearchV3().normalize({"esearchresult": {"idlist": ["10001"]}})
        result_path = self.root / "raw/queries/q3/result.json"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps({"records": pubmed_records}), encoding="utf-8")
        with (self.root / "queries.jsonl").open("a", encoding="utf-8") as ledger:
            ledger.write(json.dumps({"query_id": "q3", "source": "PubMed", "result_path": "raw/queries/q3/result.json"}) + "\n")
        pool = self.pool()
        self.assertEqual((5, 2), (pool["returned_records"], pool["unique_records"]))
        merged = next(row for row in pool["records"] if "pmid:10001" in row["identifiers"])
        self.assertIn("doi:10.1000/abc", merged["identifiers"])
        self.assertIn("pmcid:PMC9001", merged["identifiers"])
        self.assertEqual(["q1", "q2", "q3"], merged["query_ids"])
        self.assertEqual("sources/10001.abstract.txt", merged["abstract_artifact"])
        first = (self.root / "candidates.json").read_bytes()
        self.pool()
        self.assertEqual(first, (self.root / "candidates.json").read_bytes())

    def add_result(self, query_id, payload, *, source="EuropePMC", name="result.json"):
        result_path = self.root / "raw/queries" / query_id / name
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8")
        with (self.root / "queries.jsonl").open("a", encoding="utf-8") as ledger:
            ledger.write(json.dumps({"query_id": query_id, "source": source, "result_path": f"raw/queries/{query_id}/{name}"}) + "\n")

    def test_native_europepmc_response_merges_by_identifier(self):
        self.add_result("q3", {"hitCount": 2, "resultList": {"result": [
            {"id": "10001", "source": "MED", "pmid": "10001", "doi": "10.1000/abc", "title": "Alpha native", "firstPublicationDate": "2024-01-02"},
            {"id": "PPR1", "source": "PPR", "doi": "10.1000/OTHER", "title": "Beta preprint"},
        ]}}, name="response.json")
        pool = self.pool()
        self.assertEqual((6, 2, []), (pool["returned_records"], pool["unique_records"], pool["skipped_results"]))
        alpha = next(row for row in pool["records"] if "pmid:10001" in row["identifiers"])
        beta = next(row for row in pool["records"] if "doi:10.1000/other" in row["identifiers"])
        self.assertEqual(["q1", "q2", "q3"], alpha["query_ids"])
        self.assertEqual(["q2", "q3"], beta["query_ids"])

    def test_med_record_with_pmcid_merges_with_pmc_record(self):
        rows = [
            {"id": "20001", "source": "MED", "pmcid": "PMC7001", "title": "Gamma"},
            {"id": "PMC7001", "source": "PMC", "title": "Gamma copy"},
        ]
        for query_id, row in (("q4", rows[0]), ("q5", rows[1])):
            path = self.root / "raw/queries" / query_id / "result.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"records": [row]}), encoding="utf-8")
        with (self.root / "queries.jsonl").open("a", encoding="utf-8") as ledger:
            for query_id in ("q4", "q5"):
                ledger.write(json.dumps({"query_id": query_id, "source": "EuropePMC", "result_path": f"raw/queries/{query_id}/result.json"}) + "\n")
        merged = [row for row in self.pool()["records"] if "pmcid:PMC7001" in row["identifiers"]]
        self.assertEqual(1, len(merged))
        self.assertIn("pmid:20001", merged[0]["identifiers"])

    def test_unusable_results_are_skipped_and_reported(self):
        self.add_result("q5", {"unexpected": []})
        self.add_result("q4", "{not json")
        self.add_result("q6", {"resultList": {"result": ["not-an-object"]}})
        with (self.root / "queries.jsonl").open("a", encoding="utf-8") as ledger:
            ledger.write(json.dumps({"query_id": "q7", "source": "PubMed", "result_path": "raw/missing.json"}) + "\n")
        result = self.run_cli("pool", "--run-dir", self.root)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(4, json.loads(result.stdout)["counts"]["skipped_results"])
        pool = json.loads((self.root / "candidates.json").read_text(encoding="utf-8"))
        self.assertEqual((4, 2), (pool["returned_records"], pool["unique_records"]))
        self.assertEqual([
            ("q4", "raw/queries/q4/result.json", "invalid, oversized, or non-object JSON"),
            ("q5", "raw/queries/q5/result.json", "unrecognized result shape"),
            ("q6", "raw/queries/q6/result.json", "unrecognized result shape"),
            ("q7", "raw/missing.json", "missing or not a regular file"),
        ], [(row["query_id"], row["result_path"], row["reason"]) for row in pool["skipped_results"]])

    def test_apply_defaults_missing_abstract_and_hashes(self):
        pool = self.pool()
        decisions = {"schema": "screening-decisions-v1", "reviewer": "R", "stage": "abstract", "groups": [{"decision": "include", "criterion": "eligible", "rationale": "checked", "record_ids": [pool["records"][0]["record_id"]]}]}
        (self.root / "decisions.json").write_text(json.dumps(decisions), encoding="utf-8")
        result = self.run_cli("apply", "--run-dir", self.root, "--decisions", "decisions.json")
        self.assertEqual(0, result.returncode, result.stderr)
        table = json.loads((self.root / "screening.json").read_text(encoding="utf-8"))
        self.assertEqual(hashlib.sha256((self.root / "candidates.json").read_bytes()).hexdigest(), table["candidates_sha256"])
        self.assertIn("awaiting-full-text", table["counts"])
        self.assertEqual(1, table["counts"]["awaiting-full-text"])

    def test_cwd_relative_path_containing_run_directory_resolves(self):
        pool = self.pool()
        decisions = {"schema": "screening-decisions-v1", "reviewer": "R", "stage": "abstract", "groups": [
            {"decision": "include", "criterion": "eligible", "rationale": "checked", "record_ids": [pool["records"][0]["record_id"]]},
        ]}
        decisions_path = self.root / "screening-decisions.json"
        decisions_path.write_text(json.dumps(decisions), encoding="utf-8")
        result = self.run_cli("apply", "--run-dir", self.root, "--decisions", self.root.name + "/screening-decisions.json", cwd=self.root.parent)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue((self.root / "screening.json").is_file())

    def test_missing_top_level_fields_are_reported_together(self):
        self.pool()
        (self.root / "decisions.json").write_text("{}", encoding="utf-8")
        result = self.run_cli("apply", "--run-dir", self.root, "--decisions", "decisions.json")
        self.assertNotEqual(0, result.returncode)
        for field in ("schema", "reviewer", "stage", "groups"):
            self.assertIn(field, result.stderr)

    def test_apply_help_example_parses_and_applies(self):
        pool = self.pool()
        help_result = self.run_cli("apply", "--help")
        self.assertEqual(0, help_result.returncode, help_result.stderr)
        match = re.search(r"```json\n(.*?)\n```", help_result.stdout, re.DOTALL)
        self.assertIsNotNone(match, help_result.stdout)
        decisions = json.loads(match.group(1))
        with_abstract = [row["record_id"] for row in pool["records"] if row["abstract_artifact"]]
        without_abstract = [row["record_id"] for row in pool["records"] if not row["abstract_artifact"]]
        self.assertTrue(with_abstract)
        self.assertTrue(without_abstract)
        decisions["groups"][0]["record_ids"] = with_abstract
        decisions["groups"][1]["record_ids"] = without_abstract
        (self.root / "fulltext").mkdir()
        (self.root / "fulltext/article.txt").write_text("full text evidence", encoding="utf-8")
        (self.root / "decisions.json").write_text(json.dumps(decisions), encoding="utf-8")
        result = self.run_cli("apply", "--run-dir", self.root, "--decisions", "decisions.json")
        self.assertEqual(0, result.returncode, result.stderr)

    def test_refusals_do_not_write_screening(self):
        pool = self.pool()
        record = pool["records"][0]["record_id"]
        cases = [
            [{"decision": "include", "criterion": "x", "rationale": "x", "record_ids": ["unknown"]}],
            [{"decision": "include", "criterion": "x", "rationale": "x", "record_ids": [record, record]}],
            [{"decision": "include", "criterion": "x", "rationale": "x", "record_ids": []}],
            [],
            [{"decision": "exclude", "criterion": "x", "rationale": "title only", "record_ids": [pool["records"][1]["record_id"]]}],
        ]
        for groups in cases:
            (self.root / "screening.json").unlink(missing_ok=True)
            (self.root / "decisions.json").write_text(json.dumps({"schema": "screening-decisions-v1", "reviewer": "R", "stage": "abstract", "groups": groups}), encoding="utf-8")
            result = self.run_cli("apply", "--run-dir", self.root, "--decisions", "decisions.json")
            self.assertNotEqual(0, result.returncode)
            self.assertIn("error:", result.stderr)
            self.assertFalse((self.root / "screening.json").exists())

    def test_full_text_path_allows_exclusion_and_is_hashed(self):
        pool = self.pool()
        candidate = next(row for row in pool["records"] if row["abstract_artifact"] is None)
        fulltext = self.root / "fulltext/article.txt"
        fulltext.parent.mkdir()
        fulltext.write_text("full text evidence", encoding="utf-8")
        decisions = {"schema": "screening-decisions-v1", "reviewer": "R", "stage": "full text", "groups": [
            {"decision": "include", "criterion": "eligible", "rationale": "Checked fulltext/article.txt", "record_ids": [row["record_id"] for row in pool["records"] if row["abstract_artifact"]]},
            {"decision": "exclude", "criterion": "ineligible population", "rationale": "Checked fulltext/article.txt", "record_ids": [candidate["record_id"]]},
        ]}
        (self.root / "decisions.json").write_text(json.dumps(decisions), encoding="utf-8")
        result = self.run_cli("apply", "--run-dir", self.root, "--decisions", "decisions.json")
        self.assertEqual(0, result.returncode, result.stderr)
        rows = json.loads((self.root / "screening.json").read_text(encoding="utf-8"))["records"]
        abstract_candidate = next(row for row in pool["records"] if row["abstract_artifact"])
        cited_row = next(row for row in rows if row["record_id"] == abstract_candidate["record_id"])
        self.assertEqual("fulltext/article.txt", cited_row["evidence_artifact"])
        first_hash = hashlib.sha256(fulltext.read_bytes()).hexdigest()
        self.assertEqual(first_hash, cited_row["evidence_sha256"])
        fulltext.write_text("updated full text evidence", encoding="utf-8")
        result = self.run_cli("apply", "--run-dir", self.root, "--decisions", "decisions.json")
        self.assertEqual(0, result.returncode, result.stderr)
        rows = json.loads((self.root / "screening.json").read_text(encoding="utf-8"))["records"]
        cited_row = next(row for row in rows if row["record_id"] == abstract_candidate["record_id"])
        self.assertEqual(hashlib.sha256(fulltext.read_bytes()).hexdigest(), cited_row["evidence_sha256"])
        self.assertNotEqual(first_hash, cited_row["evidence_sha256"])

    def test_rejects_symlinked_result(self):
        outside = self.root / "outside.json"
        outside.write_text('{"records":[]}', encoding="utf-8")
        result_path = self.root / "raw/queries/q1/result.json"
        result_path.unlink()
        result_path.symlink_to(outside)
        result = self.run_cli("pool", "--run-dir", self.root)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("error:", result.stderr)
        self.assertFalse((self.root / "candidates.json").exists())

    def test_rejects_result_path_outside_run(self):
        with (self.root / "queries.jsonl").open("a", encoding="utf-8") as ledger:
            ledger.write(json.dumps({"query_id": "q9", "source": "EuropePMC", "result_path": "../outside.json"}) + "\n")
        result = self.run_cli("pool", "--run-dir", self.root)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("error:", result.stderr)
        self.assertFalse((self.root / "candidates.json").exists())


if __name__ == "__main__":
    unittest.main()
