import hashlib
import json
import tempfile
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.message import Message
from pathlib import Path
from unittest.mock import MagicMock, call, patch

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
    TransportPolicy,
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
        if len(response) == 3 and isinstance(response[0], int):
            status_code, body, headers = response
        else:
            payload, headers = response
            status_code = 200
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        return TransportResponse(
            status_code,
            request.url,
            headers,
            body,
            "application/json",
            "2026-07-20T00:00:00Z",
            1,
        )


class TransportV3Tests(unittest.TestCase):
    def _retry_opener(self, value, status=503):
        headers = Message()
        if value is not None:
            headers["retry-after"] = value
        error = urllib.error.HTTPError("https://example.org/search", status, "Unavailable", headers, None)
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.headers = {"Content-Type": "application/json"}
        response.geturl.return_value = "https://example.org/search"
        response.read.return_value = b"{}"
        opener = MagicMock()
        opener.open.return_value = response
        opener.open.side_effect = [error, response]
        return opener, error

    def _send_retry(self, opener, policy=None):
        with patch("codex_science.transport_v3.urllib.request.build_opener", return_value=opener), \
                patch("codex_science.transport_v3.time.sleep") as sleep:
            result = UrllibTransport(policy).send(PageRequest("GET", "https://example.org/search", {}))
        self.assertEqual(2, result.attempts)
        self.assertEqual(2, opener.open.call_count)
        self.assertEqual(b"{}", result.body)
        return sleep

    def test_retry_after_delta_seconds(self):
        for status in (429, 500, 503, 599):
            with self.subTest(status=status):
                opener, _ = self._retry_opener("2", status)
                self._send_retry(opener).assert_called_once_with(2)

    def test_retry_after_cap(self):
        for value in ("10", "999", "9" * 400):
            with self.subTest(value=value):
                opener, _ = self._retry_opener(value)
                self._send_retry(opener).assert_called_once_with(10)

    def test_retry_after_http_date(self):
        now = datetime(2026, 10, 29, tzinfo=timezone.utc).timestamp()
        for value, expected in (("Thu, 29 Oct 2026 00:00:02 GMT", 2),
                                ("Thursday, 29-Oct-26 00:00:02 GMT", 2),
                                ("Thu Oct 29 00:00:02 2026", 2),
                                ("Thu, 29 Oct 2026 00:00:00 GMT", 0.5),
                                ("Thu, 29 Oct 2026 00:01:00 GMT", 10)):
            with self.subTest(value=value), patch("codex_science.transport_v3.time.time", return_value=now):
                opener, _ = self._retry_opener(value)
                self._send_retry(opener).assert_called_once_with(expected)

    def test_retry_after_invalid_or_past_falls_back_to_backoff(self):
        now = datetime(2026, 10, 29, tzinfo=timezone.utc).timestamp()
        policy = TransportPolicy(max_retry_after_seconds=10)
        for value in (None, "", " ", "-1", "+2", "1.5", "NaN", "inf", "invalid", "٢",
                      "Thu, 29 Oct 2026 00:00:99 GMT", "Wed, 28 Oct 2026 23:59:59 GMT"):
            with self.subTest(value=value), patch("codex_science.transport_v3.time.time", return_value=now):
                opener, _ = self._retry_opener(value)
                self._send_retry(opener, policy).assert_called_once_with(0.5)

    def test_retry_after_backoff_floor_and_cap(self):
        for value, backoff, expected in (("0", 3, 3), ("1", 3, 3), ("2", 20, 20),
                                         ("999", 20, 20), ("2", 10, 10)):
            with self.subTest(value=value, backoff=backoff):
                opener, _ = self._retry_opener(value)
                policy = TransportPolicy(backoff_seconds=(0, backoff, backoff), max_retry_after_seconds=10)
                self._send_retry(opener, policy).assert_called_once_with(expected)

    def test_retry_after_policy_limit_validation(self):
        self.assertEqual(10, TransportPolicy().max_retry_after_seconds)
        for value in (True, False, -1, float("nan"), float("inf"), "invalid", None, []):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "max_retry_after_seconds"):
                UrllibTransport(TransportPolicy(max_retry_after_seconds=value))

    def test_retry_after_zero_and_configured_caps(self):
        for cap, expected in ((0, 0.5), (0.25, 0.5), (0.5, 0.5), (1.25, 1.25), (2, 2)):
            with self.subTest(cap=cap):
                opener, _ = self._retry_opener("2")
                self._send_retry(opener, TransportPolicy(max_retry_after_seconds=cap)).assert_called_once_with(expected)

    def test_retry_after_final_attempt_does_not_sleep(self):
        for attempts, expected in ((1, []), (3, [call(2), call(2)])):
            with self.subTest(attempts=attempts):
                opener, error = self._retry_opener("2")
                opener.open.side_effect = error
                policy = TransportPolicy(max_attempts=attempts)
                with patch("codex_science.transport_v3.urllib.request.build_opener", return_value=opener), \
                        patch("codex_science.transport_v3.time.sleep") as sleep:
                    with self.assertRaises(TransportError) as caught:
                        UrllibTransport(policy).send(PageRequest("GET", "https://example.org/search", {}))
                self.assertEqual(503, caught.exception.status_code)
                self.assertTrue(caught.exception.retryable)
                self.assertEqual(attempts, opener.open.call_count)
                self.assertEqual(expected, sleep.call_args_list)

    def test_retry_after_applies_only_to_the_next_attempt(self):
        opener, error = self._retry_opener("2")
        opener.open.side_effect = [error, urllib.error.URLError("offline"), opener.open.return_value]
        with patch("codex_science.transport_v3.urllib.request.build_opener", return_value=opener), \
                patch("codex_science.transport_v3.time.sleep") as sleep:
            result = UrllibTransport().send(PageRequest("GET", "https://example.org/search", {}))
        self.assertEqual(3, result.attempts)
        self.assertEqual(3, opener.open.call_count)
        self.assertEqual([call(2), call(1.5)], sleep.call_args_list)

    def test_retry_after_does_not_retry_other_http_errors(self):
        opener, _ = self._retry_opener("2", status=404)
        policy = TransportPolicy(max_retry_after_seconds=10)
        with patch("codex_science.transport_v3.urllib.request.build_opener", return_value=opener), \
                patch("codex_science.transport_v3.time.sleep") as sleep:
            with self.assertRaises(TransportError) as caught:
                UrllibTransport(policy).send(PageRequest("GET", "https://example.org/search", {}))
        self.assertEqual(404, caught.exception.status_code)
        self.assertFalse(caught.exception.retryable)
        self.assertEqual(1, opener.open.call_count)
        sleep.assert_not_called()

    def test_pdb_204_empty_body_is_negative_with_receipt(self) -> None:
        request = QueryRequest("pdb", "search", {"query": "no results"}, source_contract_version="3")
        result = execute_paginated(PDBSearchV3(), request, transport=FakeTransport([(204, b"", {})]))

        self.assertEqual("negative", result.receipt.status)
        self.assertEqual(1, result.receipt.fetched_pages)
        page = result.receipt.pages[0]
        self.assertEqual(204, page.status_code)
        self.assertEqual(0, page.normalized_record_count)
        self.assertEqual(0, page.response_bytes)
        self.assertEqual(hashlib.sha256(b"").hexdigest(), page.response_sha256)

    def test_pdb_204_nonempty_body_remains_schema_drift(self) -> None:
        request = QueryRequest("pdb", "search", {"query": "fixture"}, source_contract_version="3")
        with self.assertRaisesRegex(ValueError, "schema-drift: source returned invalid JSON"):
            execute_paginated(PDBSearchV3(), request, transport=FakeTransport([(204, b"not empty", {})]))

    def test_pubmed_204_empty_body_remains_schema_drift(self) -> None:
        request = QueryRequest("pubmed", "search", {"query": "fixture"}, source_contract_version="3")
        with self.assertRaisesRegex(ValueError, "schema-drift: source returned invalid JSON"):
            execute_paginated(PubMedSearchV3(), request, transport=FakeTransport([(204, b"", {})]))

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

    def test_pdb_empty_204_snapshot_replays_as_negative(self) -> None:
        request = QueryRequest("pdb", "search", {"query": "no results"}, source_contract_version="3")
        with tempfile.TemporaryDirectory() as tempdir:
            result = execute_paginated(
                PDBSearchV3(), request, transport=FakeTransport([(204, b"", {})]),
                snapshot_dir=Path(tempdir),
            )
            replayed = replay_snapshot_directory(Path(tempdir), request.query_id)

        self.assertEqual("negative", result.receipt.status)
        self.assertEqual(0, result.receipt.records_returned)
        self.assertEqual(1, len(replayed))
        self.assertEqual(204, replayed[0]["metadata"]["response"]["status_code"])
        self.assertIsNone(replayed[0]["payload"])

    def test_pdb_empty_204_on_later_page_remains_schema_drift(self) -> None:
        request = QueryRequest(
            "pdb", "search", {"query": "fixture"}, max_pages=2, source_contract_version="3"
        )
        first_page = {"result_set": [{"identifier": "1"}], "total_count": 2}
        with self.assertRaisesRegex(ValueError, "schema-drift: source returned invalid JSON"):
            execute_paginated(
                PDBSearchV3(), request,
                transport=FakeTransport([(first_page, {}), (204, b"", {})]),
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

    def test_europepmc_normalize_keeps_only_valid_pmcid(self) -> None:
        base = {"id": "25203112", "source": "MED", "title": "T", "doi": "10.1/x", "firstPublicationDate": "2014-09-01"}
        records = EuropePMCSearchV3().normalize({"resultList": {"result": [
            {**base, "pmcid": "pmc4159349"},
            {**base, "id": "2", "pmcid": "4159349"},
            {**base, "id": "3"},
        ]}})
        self.assertEqual("PMC4159349", records[0]["pmcid"])
        self.assertNotIn("pmcid", records[1])
        self.assertNotIn("pmcid", records[2])
        self.assertEqual(
            {"id": "3", "title": "T", "source": "MED", "doi": "10.1/x", "publication_date": "2014-09-01",
             "url": "https://europepmc.org/article/MED/3"},
            records[2],
        )

    def test_europepmc_terminal_page_without_cursor_is_complete(self) -> None:
        request = QueryRequest(
            "europepmc", "search", {"query": "DOI:10.1038/nm.3444"},
            page_size=20, source_contract_version="3",
        )
        transport = FakeTransport([
            ({"hitCount": 1, "resultList": {"result": [{"id": "1", "source": "MED"}]}}, {}),
        ])

        result = execute_paginated(EuropePMCSearchV3(), request, transport=transport)

        self.assertEqual("complete", result.receipt.status)
        self.assertEqual(["1"], [record["id"] for record in result.records])
        self.assertEqual(1, len(result.receipt.pages))
        self.assertEqual(1, len(transport.requests))

    def test_europepmc_missing_cursor_with_unaccounted_hits_is_schema_drift(self) -> None:
        request = QueryRequest(
            "europepmc", "search", {"query": "broad query"},
            page_size=2, source_contract_version="3",
        )
        payload = {
            "hitCount": 3,
            "resultList": {"result": [{"id": "1", "source": "MED"}, {"id": "2", "source": "MED"}]},
        }

        short_request = QueryRequest(
            "europepmc", "search", {"query": "narrow query"},
            page_size=20, source_contract_version="3",
        )
        short_payload = {"hitCount": 2, "resultList": {"result": [{"id": "1", "source": "MED"}]}}
        for paged_request, page in ((request, payload), (short_request, short_payload)):
            with self.subTest(hit_count=page["hitCount"]), self.assertRaisesRegex(
                ValueError, r"^schema-drift: europepmc pagination missing nextCursorMark$"
            ):
                execute_paginated(EuropePMCSearchV3(), paged_request, transport=FakeTransport([(page, {})]))

    def test_v3_pagination_missing_keys_have_schema_drift_labels(self) -> None:
        operation = PubMedSearchV3()
        request = QueryRequest("pubmed", "search", {"query": "fixture"}, source_contract_version="3")
        first_request = operation.first_request(request)
        pubmed_cases = (
            ({}, "missing esearchresult"),
            (None, "invalid response object while reading esearchresult"),
            ({"esearchresult": None}, "invalid esearchresult: expected object"),
            ({"esearchresult": {"count": "0"}}, "missing idlist"),
            ({"esearchresult": {"count": "0", "idlist": "1"}}, "invalid idlist: expected list"),
            ({"esearchresult": {"ERROR": "Empty term"}}, "invalid response: NCBI ESearch error: Empty term"),
            ({"ERROR": "backend failure"}, "invalid response: NCBI ESearch error: backend failure"),
            ({"error": "backend failure"}, "invalid response: NCBI ESearch error: backend failure"),
        )
        for payload, detail in pubmed_cases:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError) as caught:
                    operation.next_request(request, first_request, payload, 0)
                self.assertEqual(f"schema-drift: pubmed pagination {detail}", str(caught.exception))

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

    def test_pubmed_search_v3_raises_on_ncbi_error_payload(self) -> None:
        request = QueryRequest("pubmed", "search", {"query": "x"}, source_contract_version="3")
        with self.assertRaisesRegex(ValueError, "NCBI ESearch error"):
            execute_paginated(PubMedSearchV3(), request, transport=FakeTransport([({"esearchresult": {"ERROR": "Empty term"}}, {})]))

    def test_pubmed_search_v3_raises_on_missing_esearchresult(self) -> None:
        request = QueryRequest("pubmed", "search", {"query": "x"}, source_contract_version="3")
        with self.assertRaisesRegex(ValueError, "missing esearchresult"):
            execute_paginated(PubMedSearchV3(), request, transport=FakeTransport([({"count": "0"}, {})]))

    def test_pubmed_search_v3_zero_hit_returns_empty(self) -> None:
        request = QueryRequest("pubmed", "search", {"query": "no results"}, source_contract_version="3")
        result = execute_paginated(PubMedSearchV3(), request, transport=FakeTransport([({"esearchresult": {"count": "0", "retstart": "0", "idlist": []}}, {})]))
        self.assertEqual("negative", result.receipt.status)
        self.assertEqual(0, len(result.records))

    def test_pubmed_search_v3_ignores_errorlist_with_ids(self) -> None:
        request = QueryRequest("pubmed", "search", {"query": "x"}, source_contract_version="3")
        result = execute_paginated(PubMedSearchV3(), request, transport=FakeTransport([({"esearchresult": {"count": "3", "retstart": "0", "idlist": ["1", "2", "3"], "errorlist": {"phrasesnotfound": ["unknown"]}}}, {})]))
        self.assertEqual(["1", "2", "3"], [record["id"] for record in result.records])


if __name__ == "__main__":
    unittest.main()
