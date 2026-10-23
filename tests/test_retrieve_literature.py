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
from codex_science.literature_retrieval import _status, retrieve_literature
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
            (root / "queries.jsonl").write_text('{"query_id": "ok"}\nnot-json\n')
            transport = FakeTransport([europe_payload()])
            with self.assertRaisesRegex(ValueError, "invalid query ledger JSON"):
                retrieve_literature(root, "europepmc", "corrupt", transport=transport)
            self.assertEqual(0, transport.calls)

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


if __name__ == "__main__":
    unittest.main()
