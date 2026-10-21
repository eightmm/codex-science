import json
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from codex_science.connector_contract import QueryRequest
from codex_science.source_operations_v3 import EuropePMCSearchV3, PubMedSearchV3
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
