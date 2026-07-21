import json
import tempfile
import unittest
from pathlib import Path

from codex_science.connector_contract import QueryRequest
from codex_science.source_operations_v3 import EuropePMCSearchV3, PubMedSearchV3
from codex_science.transport_v3 import (
    PageRequest,
    TransportError,
    TransportResponse,
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
