import json
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from codex_science.connector_contract import QueryRequest, classify_drift, execute_connector, sha256_json
from codex_science.connectors import PubMedConnector
from codex_science.source_operations_v3 import (
    ChEMBLMoleculeSearchV3,
    EuropePMCSearchV3,
    PDBSearchV3,
    PubMedSearchV3,
)
from codex_science.transport_v3 import (
    PageRequest,
    SafeRedirectHandler,
    TransportError,
    TransportResponse,
    UrllibTransport,
    execute_paginated,
    replay_snapshot_directory,
)


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def send(self, request: PageRequest) -> TransportResponse:
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        payload, headers = response
        return TransportResponse(
            200,
            request.url,
            headers,
            json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            "application/json",
            "2026-07-20T00:00:00Z",
            1,
        )


class TransportV3Tests(unittest.TestCase):
    def test_pubmed_page_fixtures_replay_stably(self) -> None:
        fixture_dir = Path(__file__).parent / "fixtures" / "pubmed_v3"
        pages = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(fixture_dir.glob("page-*.json"))]
        self.assertEqual(2, len(pages))
        request = QueryRequest(
            "pubmed", "search", {"query": "fixture query"},
            page_size=2, max_pages=3, source_contract_version="3",
        )

        results = []
        replayed = None
        for run_index in range(2):
            transport = FakeTransport([(payload, {}) for payload in pages])
            with tempfile.TemporaryDirectory() as tempdir:
                result = execute_paginated(
                    PubMedSearchV3(), request, transport=transport, snapshot_dir=Path(tempdir)
                )
                if run_index == 0:
                    replayed = replay_snapshot_directory(Path(tempdir), request.query_id)
                results.append(result)
        first, second = results
        self.assertEqual("complete", first.receipt.completeness)
        self.assertEqual(2, first.receipt.fetched_pages)
        self.assertEqual(["101", "102", "103"], [record["id"] for record in first.records])
        self.assertEqual(2, len(replayed))
        self.assertEqual(pages, [page["payload"] for page in replayed])
        self.assertEqual(first.receipt.normalized_records_sha256, second.receipt.normalized_records_sha256)
        self.assertEqual(
            [page.response_sha256 for page in first.receipt.pages],
            [page.response_sha256 for page in second.receipt.pages],
        )

    def test_v2_classifier_reports_rehashed_normalized_record_change(self) -> None:
        fixture_dir = Path(__file__).parent / "fixtures" / "pubmed_v3"
        first_page = json.loads((fixture_dir / "page-0000.json").read_text(encoding="utf-8"))
        legacy_request = QueryRequest("pubmed", "search", {"query": "fixture query"})
        baseline = execute_connector(
            PubMedConnector(fetch_json=lambda _url: first_page),
            legacy_request,
            include_snapshot=True,
            retrieved_at="2026-07-20T00:00:00Z",
        ).snapshot()
        # This mutates a v2 normalized snapshot; source-side v3 drift is tested separately.
        drifted = json.loads(json.dumps(baseline))
        drifted["records"][0].pop("title")
        drifted["receipt"]["normalized_records_sha256"] = sha256_json(drifted["records"])
        self.assertIn("semantic-drift", classify_drift(baseline, drifted)["drift_types"])

    def test_pubmed_renamed_idlist_field_raises_named_normalization_error(self) -> None:
        fixture_dir = Path(__file__).parent / "fixtures" / "pubmed_v3"
        payload = json.loads((fixture_dir / "drift-idlist.json").read_text(encoding="utf-8"))
        request = QueryRequest(
            "pubmed", "search", {"query": "fixture query"},
            page_size=2, max_pages=3, source_contract_version="3",
        )

        with self.assertRaisesRegex(ValueError, "normalization-failed.*idlist"):
            execute_paginated(PubMedSearchV3(), request, transport=FakeTransport([(payload, {})]))

    def test_pubmed_present_empty_idlist_remains_negative(self) -> None:
        fixture_dir = Path(__file__).parent / "fixtures" / "pubmed_v3"
        payload = json.loads((fixture_dir / "empty-result.json").read_text(encoding="utf-8"))
        request = QueryRequest("pubmed", "search", {"query": "no results"}, source_contract_version="3")

        result = execute_paginated(PubMedSearchV3(), request, transport=FakeTransport([(payload, {})]))
        self.assertEqual("negative", result.receipt.status)
        self.assertEqual("negative", result.receipt.missingness)

    def test_europepmc_empty_page_without_cursor_remains_negative(self) -> None:
        request = QueryRequest(
            "europepmc", "search", {"query": "no results"}, source_contract_version="3"
        )
        result = execute_paginated(
            EuropePMCSearchV3(),
            request,
            transport=FakeTransport([({"hitCount": 0, "resultList": {"result": []}}, {})]),
        )
        self.assertEqual("negative", result.receipt.status)
        self.assertEqual("negative", result.receipt.missingness)

    def test_v3_pagination_missing_keys_have_schema_drift_labels(self) -> None:
        cases = (
            (
                PubMedSearchV3(),
                QueryRequest("pubmed", "search", {"query": "fixture"}, source_contract_version="3"),
                {"esearchresult": {"idlist": []}},
                "count",
            ),
            (
                EuropePMCSearchV3(),
                QueryRequest("europepmc", "search", {"query": "fixture"}, source_contract_version="3"),
                {"resultList": {"result": [{"id": "PMC1", "source": "MED"}]}},
                "nextCursorMark",
            ),
            (
                ChEMBLMoleculeSearchV3(),
                QueryRequest("chembl", "search", {"query": "fixture"}, source_contract_version="3"),
                {"molecules": [], "page_meta": {}},
                "next",
            ),
            (
                PDBSearchV3(),
                QueryRequest("pdb", "search", {"query": "fixture"}, source_contract_version="3"),
                {"result_set": []},
                "total_count",
            ),
        )
        for operation, request, payload, missing_key in cases:
            with self.subTest(source=operation.source, key=missing_key):
                message = rf"^schema-drift: {operation.source} pagination missing {missing_key}$"
                with self.assertRaisesRegex(ValueError, message):
                    execute_paginated(operation, request, transport=FakeTransport([(payload, {})]))

    def test_missing_record_identifiers_are_skipped_and_pdb_ids_are_stringified(self) -> None:
        europepmc = EuropePMCSearchV3().normalize({
            "resultList": {"result": [{"title": "no id"}, {"id": "PMC1", "source": "MED"}]}
        })
        chembl = ChEMBLMoleculeSearchV3().normalize({
            "molecules": [{"pref_name": "no id"}, {"molecule_chembl_id": "CHEMBL1"}]
        })
        pdb = PDBSearchV3().normalize({"result_set": [{}, {"identifier": 1234}]})

        self.assertEqual(["PMC1"], [record["id"] for record in europepmc])
        self.assertEqual(["CHEMBL1"], [record["id"] for record in chembl])
        self.assertEqual(["1234"], [record["id"] for record in pdb])

    def test_redirect_handler_enforces_scheme_downgrade_and_sensitive_origin_policy(self) -> None:
        handler = SafeRedirectHandler()

        def redirect(url: str, headers: dict[str, str] | None = None):
            request = urllib.request.Request("https://example.org/start", headers=headers or {})
            return handler.redirect_request(request, None, 302, "Found", {}, url)

        self.assertIsNotNone(redirect("https://example.org/next"))
        self.assertIsNotNone(redirect("https://example.org:443/next"))
        self.assertIsNone(redirect("http://example.org/next"))
        self.assertIsNone(redirect("file:///tmp/data"))
        self.assertIsNone(redirect("ftp://example.org/data"))
        self.assertIsNone(redirect("https://other.example/next", {"X-API-Key": "secret-value"}))
        self.assertIsNone(redirect("https://example.org:444/next", {"Authorization": "secret-value"}))
        self.assertIsNotNone(redirect("https://other.example/next"))

    def test_send_maps_refused_redirect_to_non_retryable_redacted_transport_error(self) -> None:
        request = PageRequest(
            "GET", "https://example.org/start?token=query-secret",
            {"X-API-Key": "header-secret"},
        )
        handler = SafeRedirectHandler()

        class RefusingOpener:
            def open(self, req, timeout):
                redirected = handler.redirect_request(
                    req, None, 302, "Found", {}, "https://other.example/next"
                )
                if redirected is None:
                    raise urllib.error.HTTPError(
                        "https://other.example/next", 302, "Found", {}, None
                    )
                raise AssertionError("cross-origin redirect was allowed")

        with patch("codex_science.transport_v3.urllib.request.build_opener", return_value=RefusingOpener()):
            with self.assertRaises(TransportError) as caught:
                UrllibTransport().send(request)

        self.assertFalse(caught.exception.retryable)
        self.assertNotIn("header-secret", str(caught.exception))
        self.assertNotIn("query-secret", str(caught.exception))

    def test_pubmed_fetches_all_pages_and_replays_raw_bodies(self) -> None:
        request = QueryRequest(
            "pubmed", "search", {"query": "protein folding"},
            page_size=2, max_pages=3, source_contract_version="3",
        )
        transport = FakeTransport(
            [
                ({"esearchresult": {"count": "3", "retstart": "0", "idlist": ["1", "2"]}}, {"etag": '"one"', "last-modified": "date"}),
                ({"esearchresult": {"count": "3", "retstart": "2", "idlist": ["3"]}}, {"etag": '"two"'}),
            ]
        )
        with tempfile.TemporaryDirectory() as tempdir:
            snapshot_dir = Path(tempdir)
            result = execute_paginated(PubMedSearchV3(), request, transport=transport, snapshot_dir=snapshot_dir)
            self.assertEqual("complete", result.receipt.status)
            self.assertEqual(["1", "2", "3"], [item["id"] for item in result.records])
            self.assertEqual('"one"', result.receipt.pages[0].etag)
            self.assertEqual(2, len(replay_snapshot_directory(snapshot_dir, request.query_id)))

    def test_user_page_bound_is_not_source_completion(self) -> None:
        request = QueryRequest(
            "europepmc", "search", {"query": "BRCA1"},
            page_size=1, max_pages=1, source_contract_version="3",
        )
        transport = FakeTransport(
            [({"nextCursorMark": "cursor-2", "resultList": {"result": [{"id": "1", "source": "MED"}]}}, {})]
        )
        result = execute_paginated(EuropePMCSearchV3(), request, transport=transport)
        self.assertEqual("bounded-by-user", result.receipt.status)
        self.assertEqual("partial", result.receipt.missingness)

    def test_error_statuses_remain_distinct(self) -> None:
        request = QueryRequest(
            "pubmed", "search", {"query": "x"}, source_contract_version="3"
        )
        result = execute_paginated(
            PubMedSearchV3(), request,
            transport=FakeTransport([TransportError("rate", status_code=429, retryable=True)]),
        )
        self.assertEqual("partial-rate-limit", result.receipt.status)
        self.assertEqual("partial", result.receipt.missingness)
        self.assertEqual(0, result.receipt.fetched_pages)


if __name__ == "__main__":
    unittest.main()
