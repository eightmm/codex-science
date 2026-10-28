import hashlib
import json
import io
import os
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from codex_science.evidence import _validate_query_records
from codex_science.connector_contract import QueryRequest
from codex_science.literature_retrieval import _ledger_ids, _plain_abstract, _pubmed_records, _status, retrieve_literature
from codex_science.transport_v3 import PageRequest, TransportError, TransportResponse
from scripts.retrieve_literature import main


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
        self.requests = []

    def send(self, request: PageRequest) -> TransportResponse:
        self.calls += 1
        self.requests.append(request)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, tuple):
            body, media_type = item
        else:
            body, media_type = json.dumps(item, separators=(",", ":")).encode(), "application/json"
        return TransportResponse(200, request.url, {}, body, media_type, "2026-07-20T00:00:00Z", 1)


def europe_payload(rows=None, hit_count=None):
    if hit_count is None:
        hit_count = len(rows or [])
    return {"hitCount": hit_count, "nextCursorMark": "*", "resultList": {"result": rows or []}}


def pubmed_esummary(ids):
    return {"result": {
        "uids": [str(identifier) for identifier in ids],
        **{str(identifier): {"uid": str(identifier), "title": f"Title {identifier}", "pubdate": "2024"}
           for identifier in ids},
    }}


class RetrieveLiteratureTests(unittest.TestCase):
    def test_inconsistent_search_pages_never_publish_complete_query_rows(self):
        for source, payload in (
            ("pubmed", {"esearchresult": {"count": "1", "idlist": []}}),
            ("europepmc", europe_payload([], 1)),
            ("europepmc", europe_payload([{"id": "1"}], 2)),
        ):
            with self.subTest(source=source, payload=payload), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                with self.assertRaisesRegex(ValueError, "schema-drift"):
                    retrieve_literature(root, source, "inconsistent", transport=FakeTransport([payload]))
                self.assertFalse((root / "queries.jsonl").exists())
                self.assertEqual([], list(root.iterdir()))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            payload = europe_payload([{"id": "1"}], 2)
            payload["nextCursorMark"] = "next"
            summary = retrieve_literature(root, "europepmc", "capped", page_size=1, max_pages=1,
                                          transport=FakeTransport([payload]))
            row = json.loads((root / "queries.jsonl").read_text())
            self.assertEqual("partial", summary["status"])
            self.assertEqual("partial", row["status"])
            self.assertEqual(2, row["hit_count"])
            self.assertEqual(1, row["records_returned"])

    def test_plain_abstract_strips_markup_without_deleting_comparisons(self):
        cases = {
            '<p>p < 0.05 and fold change > 2</p>': 'p < 0.05 and fold change > 2\n',
            '<i><h4 class="x">A &amp; B</h4></i>': 'A & B\n',
            '<0.001': '<0.001\n',
            'a<b>c': 'a c\n',
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(expected.encode(), _plain_abstract(raw))

    def test_ledger_snapshot_abstracts_and_compact_result(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            transport = FakeTransport([europe_payload([{"id": "PMC123", "title": "A title", "firstPublicationDate": "2024-01-01", "abstractText": "<p>A &amp; B</p>"}])])
            summary = retrieve_literature(root, "europepmc", "gene", abstracts=True, transport=transport)
            ledger = [json.loads(line) for line in (root / "queries.jsonl").read_text().splitlines()]
            _validate_query_records(ledger)
            row = ledger[0]
            result_path = root / row["result_path"]
            result = result_path.read_bytes()
            self.assertEqual(row["response_sha256"], __import__("hashlib").sha256(result).hexdigest())
            self.assertEqual("complete", row["status"])
            self.assertEqual(1, row["hit_count"])
            self.assertEqual("A & B\n", (root / "sources/PMC123.abstract.txt").read_text())
            self.assertTrue(summary["records"][0]["abstract_written"])
            self.assertTrue((root / "raw/queries" / row["query_id"] / "page-0000.body").exists())

    def test_status_mapping(self):
        self.assertEqual("complete", _status({"status": "complete"}))
        self.assertEqual("complete", _status({"status": "negative"}))
        self.assertEqual("partial", _status({"status": "bounded-by-user"}))
        self.assertEqual("partial", _status({"status": "partial-rate-limit"}))
        self.assertEqual("failed", _status({"status": "source-unavailable"}))

    def test_duplicate_query_refuses_before_transport_or_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            transport = FakeTransport([europe_payload()])
            retrieve_literature(root, "europepmc", "duplicate", transport=transport)
            before = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))
            with self.assertRaisesRegex(FileExistsError, "q-"):
                retrieve_literature(root, "europepmc", "duplicate", transport=transport)
            self.assertEqual(1, transport.calls)
            self.assertEqual(before, sorted(p.relative_to(root).as_posix() for p in root.rglob("*")))

    def test_existing_europepmc_query_adds_abstracts_offline_from_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            transport = FakeTransport([europe_payload([{"id": "PMC123", "title": "A", "abstractText": "<p>new &amp; saved</p>"}])])
            original = retrieve_literature(root, "europepmc", "recover", transport=transport)
            self.assertFalse(original["records"][0]["abstract_written"])
            ledger = root / "queries.jsonl"
            ledger.write_text("\n" + ledger.read_text() + "\n")
            second = retrieve_literature(root, "europepmc", "recover", abstracts=True, transport=transport)
            self.assertEqual(1, transport.calls)
            self.assertTrue(second["abstracts_from_saved_snapshot"])
            self.assertTrue(second["records"][0]["abstract_written"])
            self.assertEqual("new & saved\n", (root / "sources/PMC123.abstract.txt").read_text())
            self.assertEqual(1, sum(bool(line.strip()) for line in (root / "queries.jsonl").read_text().splitlines()))

    def test_recovery_requires_valid_ledger_result_digest(self):
        for digest in (None, "missing", "z" * 64):
            with self.subTest(digest=digest), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                retrieve_literature(root, "europepmc", "digest", transport=FakeTransport([
                    europe_payload([{"id": "PMC123", "abstractText": "saved"}])]))
                ledger_path = root / "queries.jsonl"
                row = json.loads(ledger_path.read_text())
                if digest == "missing":
                    row.pop("response_sha256")
                else:
                    row["response_sha256"] = digest
                ledger_path.write_text(json.dumps(row) + "\n")
                with self.assertRaisesRegex(ValueError, row["query_id"]):
                    retrieve_literature(root, "europepmc", "digest", abstracts=True)
                self.assertFalse(list((root / "sources").glob("*.abstract.txt")) if (root / "sources").exists() else [])

    def _snapshot_with_bad_second_page(self, root, name, bad_body):
        retrieve_literature(root, "europepmc", name, transport=FakeTransport([
            europe_payload([{"id": "PMC123", "abstractText": "saved"}])]))
        ledger_path = root / "queries.jsonl"
        row = json.loads(ledger_path.read_text())
        result_path = root / row["result_path"]
        result = json.loads(result_path.read_text())
        first = result["receipt"]["pages"][0]
        second_name = first["snapshot_body_path"].replace("page-", "page-extra-")
        second_bytes = bad_body.encode()
        (root / "raw/queries" / second_name).write_bytes(second_bytes)
        result["receipt"]["pages"].append(
            {**first, "snapshot_body_path": second_name, "response_sha256": hashlib.sha256(second_bytes).hexdigest()})
        result_bytes = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
        result_path.write_bytes(result_bytes)
        row["response_sha256"] = hashlib.sha256(result_bytes).hexdigest()
        ledger_path.write_text(json.dumps(row) + "\n")
        return row["query_id"]

    def test_recovery_validates_snapshot_structure_and_result_path_before_writes(self):
        bad_pages = {
            "result-null": '{"resultList":{"result":null}}',
            "result-has-null": '{"resultList":{"result":[null]}}',
            "resultlist-not-object": '{"resultList":[]}',
            "page-not-object": '[]',
        }
        for mutation, bad_body in bad_pages.items():
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self._snapshot_with_bad_second_page(root, "nested", bad_body)
                with self.assertRaisesRegex(ValueError, "saved page body"):
                    retrieve_literature(root, "europepmc", "nested", abstracts=True)
                self.assertFalse(list((root / "sources").glob("*.abstract.txt")) if (root / "sources").exists() else [])
        for mutation in ("records-null", "receipt-null", "other-result-path"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                retrieve_literature(root, "europepmc", "shape", transport=FakeTransport([
                    europe_payload([{"id": "PMC123", "abstractText": "saved"}])]))
                ledger_path = root / "queries.jsonl"
                row = json.loads(ledger_path.read_text())
                if mutation == "other-result-path":
                    row["result_path"] = "raw/queries/q-other/result.json"
                else:
                    result_path = root / row["result_path"]
                    result = json.loads(result_path.read_text())
                    if mutation == "records-null":
                        result["records"] = None
                    else:
                        result["receipt"] = None
                    result_bytes = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
                    result_path.write_bytes(result_bytes)
                    row["response_sha256"] = __import__("hashlib").sha256(result_bytes).hexdigest()
                ledger_path.write_text(json.dumps(row) + "\n")
                with self.assertRaisesRegex(ValueError, row["query_id"]):
                    retrieve_literature(root, "europepmc", "shape", abstracts=True)
                self.assertFalse(list((root / "sources").glob("*.abstract.txt")) if (root / "sources").exists() else [])

    def test_snapshot_abstract_recovery_refuses_modified_page_body(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            transport = FakeTransport([europe_payload([{"id": "PMC123", "abstractText": "saved"}])])
            retrieve_literature(root, "europepmc", "tampered", transport=transport)
            body = next((root / "raw/queries").glob("*/page-*.body"))
            body.write_text('{"resultList":{"result":[{"id":"PMC123","abstractText":"changed"}]}}')
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                retrieve_literature(root, "europepmc", "tampered", abstracts=True, transport=transport)
            self.assertEqual(1, transport.calls)
            self.assertFalse((root / "sources/PMC123.abstract.txt").exists())

    def test_transport_failure_leaves_no_run_artifacts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(RuntimeError, "transport failed"):
                retrieve_literature(root, "europepmc", "offline", transport=FakeTransport([TransportError("offline")]))
            self.assertEqual([], list(root.iterdir()))

    def test_differing_abstract_is_kept_and_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "sources").mkdir()
            target = root / "sources/PMC123.abstract.txt"
            target.write_text("older text\n")
            summary = retrieve_literature(root, "europepmc", "abstract", abstracts=True,
                transport=FakeTransport([europe_payload([{"id": "PMC123", "abstractText": "new text"}])]))
            self.assertEqual("older text\n", target.read_text())
            self.assertTrue(summary["records"][0]["abstract_written"])
            self.assertTrue(summary["records"][0]["abstract_kept_existing"])
            self.assertEqual(["PMC123.abstract.txt"], summary["abstracts_kept_existing"])
            self.assertEqual(1, len((root / "queries.jsonl").read_text().splitlines()))

    def test_pubmed_abstract_differing_from_europepmc_keeps_existing_and_ledgers_query(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            retrieve_literature(root, "europepmc", "first", abstracts=True, transport=FakeTransport([
                europe_payload([{"id": "111", "abstractText": "Europe PMC words"}])]))
            kept = root / "sources/111.abstract.txt"
            before = kept.read_bytes()
            def article(pmid, text):
                return (f"<PubmedArticle><MedlineCitation><PMID>{pmid}</PMID><Article><Abstract>"
                        f"<AbstractText>{text}</AbstractText></Abstract></Article></MedlineCitation></PubmedArticle>")
            efetch = ("<PubmedArticleSet>" + article(111, "PubMed words") + article(222, "New words")
                      + "</PubmedArticleSet>").encode()
            esearch = {"esearchresult": {"count": "2", "retstart": "0", "idlist": ["111", "222"]}}
            transport = FakeTransport([esearch, pubmed_esummary([111, 222]), (efetch, "application/xml")])
            summary = retrieve_literature(root, "pubmed", "second", abstracts=True, transport=transport)
            self.assertEqual(before, kept.read_bytes())
            self.assertEqual("New words\n", (root / "sources/222.abstract.txt").read_text())
            by_id = {row["id"]: row for row in summary["records"]}
            self.assertTrue(by_id["111"]["abstract_kept_existing"])
            self.assertTrue(by_id["111"]["abstract_written"])
            self.assertFalse(by_id["222"]["abstract_kept_existing"])
            self.assertEqual(["111.abstract.txt"], summary["abstracts_kept_existing"])
            rows = [json.loads(line) for line in (root / "queries.jsonl").read_text().splitlines()]
            self.assertEqual(["EuropePMC", "PubMed"], [row["source"] for row in rows])
            body = next((root / "raw/queries").glob("*/page-0002.body")).read_text()
            self.assertIn("PubMed words", body)

    def test_symlinked_sources_directory_is_refused_without_touching_target(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "run"
            outside = Path(temp) / "outside"
            root.mkdir()
            outside.mkdir()
            protected = outside / "PMC123.abstract.txt"
            protected.write_text("protected\n")
            (root / "sources").symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlinked run target"):
                retrieve_literature(root, "europepmc", "symlink", abstracts=True,
                    transport=FakeTransport([europe_payload([{"id": "PMC123", "abstractText": "replacement"}])]))
            self.assertEqual("protected\n", protected.read_text())

    def test_fsync_failure_keeps_snapshot_referenced_by_written_row(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch("codex_science.literature_retrieval.os.fsync", side_effect=OSError("simulated fsync failure")):
                with self.assertRaisesRegex(OSError, "simulated fsync failure"):
                    retrieve_literature(root, "europepmc", "fsync", transport=FakeTransport([europe_payload()]))
            row = json.loads((root / "queries.jsonl").read_text())
            self.assertTrue((root / row["result_path"]).is_file())

    def test_append_separates_existing_ledger_without_final_newline(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            prior = {"query_id": "q-existing", "source": "EuropePMC", "query": "prior",
                     "accessed_at": "2026-07-20T00:00:00Z", "status": "complete", "response_sha256": None}
            (root / "queries.jsonl").write_text(json.dumps(prior))
            retrieve_literature(root, "europepmc", "append", transport=FakeTransport([europe_payload()]))
            lines = (root / "queries.jsonl").read_text().splitlines()
            self.assertEqual(2, len(lines))
            self.assertTrue(all(isinstance(json.loads(line), dict) for line in lines))
            self.assertEqual("q-existing", json.loads(lines[0])["query_id"])

    def test_corrupt_ledger_refuses_before_transport(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "queries.jsonl").write_text('{"query_id": "ok"}\n\nnot-json\n')
            transport = FakeTransport([europe_payload()])
            with self.assertRaisesRegex(ValueError, "invalid query ledger JSON"):
                retrieve_literature(root, "europepmc", "corrupt", transport=transport)
            self.assertEqual(0, transport.calls)

    def test_duplicate_query_via_cli_reports_recovery_error_without_traceback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            retrieve_literature(root, "europepmc", "cli-recovery", transport=FakeTransport([
                europe_payload([{"id": "PMC123", "abstractText": "saved"}])]))
            ledger_path = root / "queries.jsonl"
            row = json.loads(ledger_path.read_text())
            row["response_sha256"] = None
            ledger_path.write_text(json.dumps(row) + "\n")
            stderr = io.StringIO()
            with patch("sys.stderr", stderr):
                status = main(["--run-dir", str(root), "europepmc", "cli-recovery", "--abstracts"])
            self.assertEqual(1, status)
            self.assertTrue(stderr.getvalue().startswith("error:"))
            self.assertNotIn("Traceback", stderr.getvalue())
            self.assertFalse(list((root / "sources").glob("*.abstract.txt")) if (root / "sources").exists() else [])

    def test_cli_recovery_reports_nested_structure_and_ledger_errors(self):
        for mutation in ("result-null", "ledger-array", "ledger-deep"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self._snapshot_with_bad_second_page(root, "cli-nested", '{"resultList":{"result":null}}')
                ledger_path = root / "queries.jsonl"
                if mutation == "ledger-array":
                    ledger_path.write_text("[1]\n" + ledger_path.read_text())
                elif mutation == "ledger-deep":
                    ledger_path.write_text("[" * 100000 + "\n" + ledger_path.read_text())
                before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
                stderr = io.StringIO()
                with patch("sys.stderr", stderr):
                    status = main(["--run-dir", str(root), "europepmc", "cli-nested", "--abstracts"])
                self.assertEqual(1, status)
                self.assertTrue(stderr.getvalue().startswith("error:"))
                self.assertNotIn("Traceback", stderr.getvalue())
                self.assertEqual(before, {path: path.read_bytes() for path in root.rglob("*") if path.is_file()})

    def _two_pages(self, first_text, second_text, hit_count=2):
        first = europe_payload([{"id": "PMC123", "abstractText": first_text}], hit_count)
        second = europe_payload([{"id": "PMC123", "abstractText": second_text}], hit_count)
        first["nextCursorMark"] = "next"
        return [first, second]

    def test_first_retrieval_duplicate_ids_conflict_before_any_write(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(ValueError, "conflicting abstracts for PMC123.abstract.txt"):
                retrieve_literature(root, "europepmc", "dup", page_size=1, max_pages=2, abstracts=True,
                                    transport=FakeTransport(self._two_pages("one", "two")))
            self.assertFalse(list((root / "sources").glob("*.abstract.txt")) if (root / "sources").exists() else [])
            self.assertFalse((root / "queries.jsonl").exists())

    def test_identical_duplicate_ids_write_one_abstract(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            retrieve_literature(root, "europepmc", "same", page_size=1, max_pages=2, abstracts=True,
                                transport=FakeTransport(self._two_pages("one", "one")))
            self.assertEqual("one\n", (root / "sources/PMC123.abstract.txt").read_text())

    def test_recovery_conflicting_duplicate_ids_write_nothing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            retrieve_literature(root, "europepmc", "dupr", page_size=1, max_pages=2,
                                transport=FakeTransport(self._two_pages("one", "two")))
            with self.assertRaisesRegex(ValueError, "conflicting abstracts"):
                retrieve_literature(root, "europepmc", "dupr", page_size=1, max_pages=2, abstracts=True)
            self.assertFalse(list((root / "sources").glob("*.abstract.txt")) if (root / "sources").exists() else [])

    def test_ledger_ids_rejects_deeply_nested_line(self):
        with tempfile.TemporaryDirectory() as temp:
            ledger = Path(temp) / "queries.jsonl"
            ledger.write_text("[" * 100000 + "\n")
            with self.assertRaisesRegex(ValueError, "invalid query ledger JSON"):
                _ledger_ids(ledger)

    def test_pubmed_doi_fallback_rejects_non_doi_elocationid(self):
        records = _pubmed_records({"result": {"uids": ["1", "2", "3", "4"],
            "1": {"elocationid": "pii: S123456789"},
            "2": {"elocationid": "doi: 10.1000/xyz"},
            "3": {"articleids": [{"idtype": "doi", "value": "10.1000/article"}],
                  "elocationid": "pii: S123456789"},
            "4": {"articleids": [{"idtype": "doi", "value": "not-a-doi"}]},
        }})
        self.assertEqual("", records["1"]["doi"])
        self.assertEqual("10.1000/xyz", records["2"]["doi"])
        self.assertEqual("10.1000/article", records["3"]["doi"])
        self.assertEqual("", records["4"]["doi"])

    def test_pubmed_hit_count_comes_from_esearch_body(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            body = {"esearchresult": {"count": "19", "retstart": "0", "idlist": ["123"]}}
            esummary = {"result": {"uids": ["123"], "123": {
                "uid": "123", "title": "PubMed title", "pubdate": "2024 Jan 2",
                "fulljournalname": "Journal", "elocationid": "doi: 10.1000/example",
            }}}
            transport = FakeTransport([body, esummary])
            summary = retrieve_literature(root, "pubmed", "topic", transport=transport)
            self.assertEqual(19, summary["hit_count"])
            self.assertEqual("PubMed title", summary["records"][0]["title"])
            self.assertEqual("2024", summary["records"][0]["year"])
            self.assertEqual("Journal", summary["records"][0]["journal"])
            ledger_row = json.loads((root / "queries.jsonl").read_text())
            result_path = root / ledger_row["result_path"]
            result_bytes = result_path.read_bytes()
            self.assertEqual(ledger_row["response_sha256"], hashlib.sha256(result_bytes).hexdigest())
            result = json.loads(result_bytes)
            self.assertEqual("123", result["records"][0]["id"])
            self.assertEqual("PubMed title", result["records"][0]["title"])
            self.assertEqual("10.1000/example", summary["records"][0]["doi"])
            self.assertEqual("Journal", result["records"][0]["journal"])
            self.assertEqual(2, len(result["receipt"]["pages"]))
            for page in result["receipt"]["pages"]:
                body_path = root / "raw/queries" / page["snapshot_body_path"]
                self.assertEqual(page["response_sha256"], hashlib.sha256(body_path.read_bytes()).hexdigest())

    def test_pubmed_abstracts_are_saved_and_legacy_duplicate_still_refuses(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            esearch = {"esearchresult": {"count": "1", "retstart": "0", "idlist": ["123"]}}
            esummary = {"result": {"uids": ["123"], "123": {"uid": "123", "title": "T", "pubdate": "2022"}}}
            efetch = (b'<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123</PMID>'
                      b'<Article><Abstract><AbstractText Label="BACKGROUND">Abstract words; A &lt; B</AbstractText>'
                      b'</Abstract></Article></MedlineCitation></PubmedArticle></PubmedArticleSet>',
                      "application/xml")
            transport = FakeTransport([esearch, esummary, efetch])
            summary = retrieve_literature(root, "pubmed", "abstract topic", abstracts=True, transport=transport)
            self.assertTrue(summary["abstracts_supported"])
            self.assertTrue(summary["records"][0]["abstract_written"])
            self.assertEqual("BACKGROUND: Abstract words; A < B\n", (root / "sources/123.abstract.txt").read_text())
            ledger_row = json.loads((root / "queries.jsonl").read_text())
            result_path = root / ledger_row["result_path"]
            result_bytes = result_path.read_bytes()
            self.assertEqual(ledger_row["response_sha256"], hashlib.sha256(result_bytes).hexdigest())
            result = json.loads(result_bytes)
            self.assertEqual(3, len(result["receipt"]["pages"]))
            calls_before_retry = transport.calls
            with self.assertRaisesRegex(FileExistsError, "query already exists"):
                retrieve_literature(root, "pubmed", "abstract topic", abstracts=True, transport=transport)
            self.assertEqual(calls_before_retry, transport.calls)

    def test_pubmed_esummary_batches_up_to_two_hundred_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ids = [str(index) for index in range(1, 202)]
            responses = [
                {"esearchresult": {"count": "201", "retstart": "0", "idlist": ids[:100]}},
                {"esearchresult": {"count": "201", "retstart": "100", "idlist": ids[100:200]}},
                {"esearchresult": {"count": "201", "retstart": "200", "idlist": ids[200:]}},
                pubmed_esummary(ids[:200]),
                pubmed_esummary(ids[200:]),
            ]
            transport = FakeTransport(responses)
            summary = retrieve_literature(
                root, "pubmed", "batch", page_size=100, max_pages=3, transport=transport,
            )
            self.assertEqual(201, len(summary["records"]))
            self.assertEqual(5, transport.calls)
            metadata_requests = transport.requests[3:]
            self.assertEqual([200, 1], [
                len(urllib.parse.parse_qs(urllib.parse.urlsplit(item.url).query)["id"][0].split(","))
                for item in metadata_requests
            ])
            result = json.loads((root / json.loads((root / "queries.jsonl").read_text())["result_path"]).read_text())
            self.assertEqual(5, len(result["receipt"]["pages"]))

    def test_pubmed_empty_search_skips_metadata_and_malformed_esummary_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            empty_transport = FakeTransport([
                {"esearchresult": {"count": "0", "retstart": "0", "idlist": []}},
            ])
            empty = retrieve_literature(root, "pubmed", "no records", abstracts=True, transport=empty_transport)
            self.assertEqual([], empty["records"])
            self.assertEqual(1, empty_transport.calls)
            self.assertTrue(empty["abstracts_supported"])

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(ValueError, "missing result"):
                retrieve_literature(root, "pubmed", "bad metadata", transport=FakeTransport([
                    {"esearchresult": {"count": "1", "retstart": "0", "idlist": ["123"]}},
                    {"invalid": True},
                ]))
            self.assertEqual([], list(root.iterdir()))

    def test_pubmed_saved_result_persists_fetched_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            summary = retrieve_literature(root, "pubmed", "legacy", transport=FakeTransport([
                {"esearchresult": {"count": "1", "retstart": "0", "idlist": ["123"]}},
                {"result": {"uids": ["123"], "123": {"uid": "123", "title": "T", "pubdate": "2020"}}},
            ]))
            result_path = root / "raw/queries" / summary["query_id"] / "result.json"
            saved = json.loads(result_path.read_text())
            self.assertEqual("123", saved["records"][0]["id"])
            self.assertEqual("T", saved["records"][0]["title"])

    def test_legacy_pubmed_result_without_metadata_loads_into_candidate_pool(self):
        from codex_science.screening_pool import build_candidate_pool

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result_dir = root / "raw/queries/legacy"
            result_dir.mkdir(parents=True)
            (result_dir / "result.json").write_text(json.dumps({
                "records": [{"id": "123", "title": "", "url": "https://pubmed.ncbi.nlm.nih.gov/123/"}],
            }))
            row = {
                "query_id": "legacy", "source": "PubMed", "query": "old query",
                "result_path": "raw/queries/legacy/result.json",
            }
            (root / "queries.jsonl").write_text(json.dumps(row) + "\n")
            pool = build_candidate_pool(root)
            self.assertEqual(1, pool["returned_records"])
            self.assertEqual(["pubmed:123"], [item["record_id"] for item in pool["records"]])

    def test_duplicate_query_via_cli_is_clean_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            request = QueryRequest("europepmc", "search", {"query": "duplicate"}, 25, 1, None, "3")
            (root / "queries.jsonl").write_text(json.dumps({"query_id": request.query_id}) + "\n")
            before = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
            stderr = io.StringIO()
            with patch("sys.stderr", stderr):
                self.assertEqual(1, main(["--run-dir", str(root), "europepmc", "duplicate"]))
            self.assertTrue(stderr.getvalue().startswith("error: query already exists"))
            self.assertIn("changing --page-size, --max-pages, or --evidence-cutoff yields a new query id", stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())
            self.assertEqual(before, sorted(path.relative_to(root).as_posix() for path in root.rglob("*")))

    def test_cli_main_prints_compact_summary(self):
        with patch("codex_science.literature_retrieval.retrieve_literature", return_value={
            "query_id": "q-one", "status": "complete", "hit_count": 2,
            "records_returned": 1, "records": [{"id": "123", "year": "2024", "title": "Title", "abstract_written": False}], "abstracts_supported": True,
        }), patch("scripts.retrieve_literature.retrieve_literature", return_value={
            "query_id": "q-one", "status": "complete", "hit_count": 2,
            "records_returned": 1, "records": [{"id": "123", "year": "2024", "title": "Title", "abstract_written": False}], "abstracts_supported": True,
        }), patch("builtins.print") as output:
            self.assertEqual(0, main(["--run-dir", ".", "europepmc", "test"]))
            self.assertEqual(2, output.call_count)
            self.assertNotIn("records", json.loads(output.call_args_list[0].args[0]))
            self.assertTrue(output.call_args_list[1].args[0].endswith("abstract=not-requested"))
            output.reset_mock()
            self.assertEqual(0, main(["--run-dir", ".", "europepmc", "test", "--abstracts"]))
            self.assertTrue(output.call_args_list[1].args[0].endswith("abstract=no"))
        kept_row = {"id": "123", "year": "2024", "title": "Title", "abstract_written": True,
                    "abstract_kept_existing": True}
        with patch("scripts.retrieve_literature.retrieve_literature", return_value={
            "query_id": "q-one", "records": [kept_row], "abstracts_kept_existing": ["123.abstract.txt"],
        }), patch("builtins.print") as output:
            self.assertEqual(0, main(["--run-dir", ".", "pubmed", "test", "--abstracts"]))
            self.assertTrue(output.call_args_list[1].args[0].endswith("abstract=kept-existing"))


if __name__ == "__main__":
    unittest.main()
