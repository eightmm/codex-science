import copy
import json
import tempfile
import unittest
from pathlib import Path

from codex_science.connector_contract import QueryRequest, classify_drift, execute_connector, replay_snapshot
from codex_science.connector_sources import SOURCE_BY_KEY
from codex_science.connectors import PubMedConnector
from codex_science.mcp_server import CodexScienceMCP
from codex_science.release import runtime_change_requires_bump, validate_release
from codex_science.typed_connectors import ClinVarConnector, GnomADConnector
from codex_science.version import MCP_VERSION, PACKAGE_VERSION, PLUGIN_VERSION


class ReleaseAndConnectorV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]

    def test_release_identities_are_synchronized(self) -> None:
        self.assertEqual([], validate_release(self.root))
        self.assertTrue(PLUGIN_VERSION.startswith(PACKAGE_VERSION + "+codex."))
        self.assertEqual(PACKAGE_VERSION, MCP_VERSION)
        self.assertTrue(runtime_change_requires_bump(["src/codex_science/review.py"], "1.0.0+codex.a", "1.0.0+codex.a"))
        self.assertFalse(runtime_change_requires_bump(["docs/README.md"], "a", "a"))

    def test_query_request_receipt_replay_and_drift_are_deterministic(self) -> None:
        def fetch_json(_url: str) -> dict:
            return {"release": "2026-07", "nextCursor": "cursor-2", "esearchresult": {"idlist": ["123", "456"]}}

        request = QueryRequest("pubmed", "search", {"query": "protein folding"}, page_size=2, max_pages=2)
        result = execute_connector(PubMedConnector(fetch_json=fetch_json), request, include_snapshot=True, retrieved_at="2026-07-19T00:00:00Z")
        self.assertEqual("q-" + request.request_sha256[:24], result.receipt.query_id)
        self.assertEqual("2026-07", result.receipt.source_release)
        self.assertEqual("partial-next-cursor", result.receipt.completeness)
        snapshot = result.snapshot()
        replayed = replay_snapshot(snapshot)
        self.assertEqual(result.receipt.normalized_records_sha256, replayed.receipt.normalized_records_sha256)
        self.assertEqual(result.records, replayed.records)

        changed = copy.deepcopy(snapshot)
        changed["records"][0]["title"] = "changed"
        changed["receipt"]["normalized_records_sha256"] = __import__("hashlib").sha256(
            json.dumps(changed["records"], sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        report = classify_drift(snapshot, changed)
        self.assertIn("semantic-drift", report["drift_types"])

    def test_typed_source_registry_and_parsers_are_available(self) -> None:
        for key in ("clinvar", "dbsnp", "gnomad", "encode", "jaspar", "geo", "arrayexpress", "metabolights", "bindingdb", "openfda", "emdb", "complex_portal", "intact", "eqtl_catalogue"):
            self.assertIn(key, SOURCE_BY_KEY)
        clinvar = ClinVarConnector(fetch_json=lambda _url: {"esearchresult": {"idlist": ["42"]}})
        self.assertEqual("42", clinvar.search("BRCA1", limit=1)[0]["id"])
        gnomad = GnomADConnector(post_json=lambda _url, _body: {"data": {"variant": {"variant_id": "1-100-A-G", "exome": {"af": 0.1}, "genome": {"af": 0.2}}}})
        self.assertEqual("GRCh38", gnomad.search("1-100-A-G", limit=1)[0]["assembly"])

    def test_mcp_exposes_v2_and_preserves_legacy_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            inventory = Path(tempdir) / "inventory.json"
            inventory.write_text(json.dumps({"schema_version": 1, "source": {"commit": "abc"}, "summary": {"total": 0, "active": 0, "inactive": 0}, "skills": []}))
            server = CodexScienceMCP(inventory)
            response = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
            names = {item["name"] for item in response["result"]["tools"]}
            self.assertIn("science_query_source_v2", names)
            self.assertIn("science_list_source_contracts", names)
            self.assertIn("science_search_pubmed", names)
            initialized = server.handle({"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {}})
            self.assertEqual(MCP_VERSION, initialized["result"]["serverInfo"]["version"])


if __name__ == "__main__":
    unittest.main()
