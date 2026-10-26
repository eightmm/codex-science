import hashlib
import json
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from codex_science.evidence import _validate_query_records
from codex_science.connector_contract import QueryRequest
from codex_science.literature_retrieval import _ledger_ids, _plain_abstract, _status, retrieve_literature
from codex_science.transport_v3 import PageRequest, TransportError, TransportResponse
from scripts.retrieve_literature import main


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def send(self, request: PageRequest) -> TransportResponse:
        self.calls += 1
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        body = json.dumps(item, separators=(",", ":")).encode()
        return TransportResponse(200, request.url, {}, body, "application/json", "2026-07-20T00:00:00Z", 1)


def europe_payload(rows=None, hit_count=1):
    return {"hitCount": hit_count, "nextCursorMark": "*", "resultList": {"result": rows or []}}


class RetrieveLiteratureTests(unittest.TestCase):
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

    def test_differing_abstract_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "sources").mkdir()
            target = root / "sources/PMC123.abstract.txt"
            target.write_text("older text\n")
            with self.assertRaisesRegex(FileExistsError, "differing abstract"):
                retrieve_literature(root, "europepmc", "abstract", abstracts=True,
                    transport=FakeTransport([europe_payload([{"id": "PMC123", "abstractText": "new text"}])]))
            self.assertEqual("older text\n", target.read_text())
            self.assertFalse((root / "queries.jsonl").exists())

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

    def test_pubmed_hit_count_comes_from_esearch_body(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            body = {"esearchresult": {"count": "19", "retstart": "0", "idlist": ["123"]}}
            summary = retrieve_literature(root, "pubmed", "topic", transport=FakeTransport([body]))
            self.assertEqual(19, summary["hit_count"])
            result = json.loads(next((root / "raw/queries").glob("*/result.json")).read_text())
            self.assertEqual("123", result["records"][0]["id"])
            self.assertEqual("", result["records"][0]["title"])

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


if __name__ == "__main__":
    unittest.main()
