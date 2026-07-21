#!/usr/bin/env python3
"""Validate Connector Contracts v2/v3, source registries, pagination, and replay."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.connector_contract import QueryRequest, classify_drift, execute_connector, replay_snapshot  # noqa: E402
from codex_science.connector_sources import SOURCE_BY_KEY, SOURCE_BY_TOOL, SOURCE_SPECS  # noqa: E402
from codex_science.connectors import PubMedConnector  # noqa: E402
from codex_science.mcp_server import CONNECTOR_SPECS  # noqa: E402
from codex_science.source_operations_v3 import PubMedSearchV3, SOURCE_OPERATIONS_V3  # noqa: E402
from codex_science.transport_v3 import PageRequest, TransportResponse, execute_paginated, replay_snapshot_directory  # noqa: E402
from codex_science.typed_connectors import ClinVarConnector, GnomADConnector, VersionedSnapshotConnector  # noqa: E402


class FixtureTransport:
    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self.payloads = list(payloads)
        self.requests: list[PageRequest] = []

    def send(self, request: PageRequest) -> TransportResponse:
        self.requests.append(request)
        payload = self.payloads.pop(0)
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        return TransportResponse(
            status_code=200,
            url=request.url,
            headers={
                "content-type": "application/json",
                "etag": f'"fixture-{len(self.requests)}"',
                "last-modified": "Sun, 19 Jul 2026 00:00:00 GMT",
                "x-ratelimit-limit": "10",
                "x-ratelimit-remaining": "9",
            },
            body=body,
            media_type="application/json",
            retrieved_at="2026-07-19T00:00:00Z",
            attempts=1,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root.resolve()

    keys = [spec.key for spec in SOURCE_SPECS]
    tools = [spec.tool_name for spec in SOURCE_SPECS]
    if len(keys) != len(set(keys)) or len(tools) != len(set(tools)):
        raise SystemExit("connector source keys and tool names must be unique")
    if len(CONNECTOR_SPECS) != 34:
        raise SystemExit("legacy connector registry must preserve 34 entries")
    if set(keys) != set(SOURCE_BY_KEY) or set(tools) != set(SOURCE_BY_TOOL):
        raise SystemExit("connector source registry indexes are stale")
    if set(SOURCE_OPERATIONS_V3) != {"pubmed", "europepmc", "chembl", "pdb"}:
        raise SystemExit("connector v3 operation registry is stale")

    def pubmed_payload(_url: str) -> dict:
        return {
            "release": "fixture-2026-07",
            "esearchresult": {"idlist": ["12345"]},
        }

    request = QueryRequest("pubmed", "search", {"query": "protein folding"})
    result = execute_connector(
        PubMedConnector(fetch_json=pubmed_payload),
        request,
        include_snapshot=True,
        retrieved_at="2026-07-19T00:00:00Z",
    )
    snapshot = result.snapshot()
    replayed = replay_snapshot(snapshot)
    if replayed.records != result.records:
        raise SystemExit("connector v2 snapshot replay changed normalized records")
    if classify_drift(snapshot, snapshot)["drift_types"] != ["none"]:
        raise SystemExit("identical connector v2 snapshots must not drift")

    v3_request = QueryRequest(
        "pubmed",
        "search",
        {"query": "protein folding"},
        page_size=2,
        max_pages=3,
        source_contract_version="3",
    )
    fixture = FixtureTransport(
        [
            {"esearchresult": {"count": "3", "retstart": "0", "idlist": ["1", "2"]}},
            {"esearchresult": {"count": "3", "retstart": "2", "idlist": ["3"]}},
        ]
    )
    with tempfile.TemporaryDirectory() as tempdir:
        snapshot_dir = Path(tempdir)
        v3_result = execute_paginated(
            PubMedSearchV3(), v3_request, transport=fixture, snapshot_dir=snapshot_dir
        )
        if v3_result.receipt.status != "complete" or len(v3_result.records) != 3:
            raise SystemExit("connector v3 true pagination failed")
        if v3_result.receipt.pages[0].etag != '"fixture-1"':
            raise SystemExit("connector v3 did not preserve ETag")
        replayed_pages = replay_snapshot_directory(snapshot_dir, v3_request.query_id)
        if len(replayed_pages) != 2:
            raise SystemExit("connector v3 raw snapshot replay failed")

    clinvar = ClinVarConnector(fetch_json=lambda _url: {"esearchresult": {"idlist": ["42"]}})
    if clinvar.search("BRCA1", limit=1)[0]["id"] != "42":
        raise SystemExit("ClinVar fixture normalization failed")
    gnomad = GnomADConnector(
        post_json=lambda _url, _body: {
            "data": {
                "variant": {
                    "variant_id": "1-100-A-G",
                    "exome": {"af": 0.1},
                    "genome": {"af": 0.2},
                }
            }
        }
    )
    if gnomad.search("1-100-A-G", limit=1)[0]["assembly"] != "GRCh38":
        raise SystemExit("gnomAD fixture normalization failed")
    release = VersionedSnapshotConnector(
        "eqtl-catalogue-releases.json", root=root / "connectors"
    ).search("current", limit=1)
    if not release:
        raise SystemExit("versioned eQTL release snapshot is unavailable")

    print(
        f"connector contracts: valid ({len(SOURCE_SPECS)} sources, "
        "34 legacy tools, 4 v3 true-pagination operations)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
