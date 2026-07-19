#!/usr/bin/env python3
"""Validate Connector Contract v2, source registry, and offline replay semantics."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.connector_contract import QueryRequest, classify_drift, execute_connector, replay_snapshot  # noqa: E402
from codex_science.connector_sources import SOURCE_BY_KEY, SOURCE_BY_TOOL, SOURCE_SPECS  # noqa: E402
from codex_science.connectors import PubMedConnector  # noqa: E402
from codex_science.mcp_server import CONNECTOR_SPECS  # noqa: E402
from codex_science.typed_connectors import ClinVarConnector, GnomADConnector, VersionedSnapshotConnector  # noqa: E402


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
        raise SystemExit("connector snapshot replay changed normalized records")
    if classify_drift(snapshot, snapshot)["drift_types"] != ["none"]:
        raise SystemExit("identical connector snapshots must not drift")

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

    print(f"connector contracts: valid ({len(SOURCE_SPECS)} sources, 34 legacy tools)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
