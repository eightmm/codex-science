import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_science.mcp_server import CONNECTOR_SPECS, TOOLS, CodexScienceMCP, run_stdio
from codex_science.version import MCP_VERSION


LEGACY_TOOLS = {
    "science_search_alphafold", "science_search_arxiv", "science_search_bgee",
    "science_search_biobank_japan", "science_search_biostudies", "science_search_cbioportal",
    "science_search_chebi", "science_search_chembl", "science_search_clinical_trials",
    "science_search_ensembl", "science_search_europepmc", "science_search_finngen",
    "science_search_gtex", "science_search_gwas_catalog", "science_search_hpa",
    "science_search_interpro", "science_search_mgnify", "science_search_mygene",
    "science_search_ncbi_gene", "science_search_ols", "science_search_openalex",
    "science_search_opentargets", "science_search_pdb", "science_search_pride",
    "science_search_proteomexchange", "science_search_pubchem", "science_search_pubmed",
    "science_search_quickgo", "science_search_rnacentral", "science_search_reactome",
    "science_search_rhea", "science_search_skills", "science_search_string",
    "science_search_ukb_topmed", "science_search_uniprot",
    "science_plan_life_science_research",
}


class MCPServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.inventory = Path(self.tempdir.name) / "inventory.json"
        self.inventory.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "source": {"commit": "abc"},
                    "summary": {"total": 1, "active": 1, "inactive": 0},
                    "skills": [
                        {
                            "name": "sympy",
                            "description": "Symbolic mathematics",
                            "status": "active",
                            "reasons": [],
                            "path": "skills/sympy",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        self.server = CodexScienceMCP(self.inventory)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_initialize_and_tool_list(self) -> None:
        initialized = self.server.handle(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        )
        listed = self.server.handle(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        )

        self.assertEqual("2025-06-18", initialized["result"]["protocolVersion"])
        self.assertEqual(MCP_VERSION, initialized["result"]["serverInfo"]["version"])
        names = {tool["name"] for tool in listed["result"]["tools"]}
        self.assertTrue(LEGACY_TOOLS <= names)
        self.assertIn("science_query_source_v2", names)
        self.assertIn("science_list_source_contracts", names)
        for name in (
            "science_search_clinvar_v2", "science_search_dbsnp_v2", "science_search_gnomad",
            "science_search_encode", "science_search_jaspar", "science_search_geo",
            "science_search_arrayexpress", "science_search_metabolights", "science_search_openfda",
        ):
            self.assertIn(name, names)

    def test_connector_registry_preserves_legacy_source_of_truth(self) -> None:
        connector_names = [name for name, _, _ in CONNECTOR_SPECS]
        listed_names = [tool["name"] for tool in TOOLS if tool["name"] in self.server.connectors]

        self.assertEqual(34, len(connector_names))
        self.assertEqual(len(connector_names), len(set(connector_names)))
        self.assertEqual(connector_names, list(self.server.connectors))
        self.assertEqual(connector_names, listed_names)
        self.assertIn("gnomad", self.server.sources)
        self.assertIn("eqtl_catalogue", self.server.sources)

    def test_life_science_planner_is_exposed_as_read_only_tool(self) -> None:
        response = self.server.handle(
            {
                "jsonrpc": "2.0",
                "id": 20,
                "method": "tools/call",
                "params": {
                    "name": "science_plan_life_science_research",
                    "arguments": {"query": "Interpret rs7903146 across cohorts", "limit": 3},
                },
            }
        )
        payload = json.loads(response["result"]["content"][0]["text"])
        self.assertIn("human_genetics", payload["lanes"])
        self.assertIn("record_fields", payload)

    def test_search_skill_tool_returns_only_catalog_matches(self) -> None:
        response = self.server.handle(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "science_search_skills",
                    "arguments": {"query": "symbolic math"},
                },
            }
        )
        payload = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual("sympy", payload[0]["name"])

    def test_source_contracts_are_read_only_and_v2_is_typed(self) -> None:
        contracts = self.server.handle(
            {
                "jsonrpc": "2.0",
                "id": 30,
                "method": "tools/call",
                "params": {"name": "science_list_source_contracts", "arguments": {}},
            }
        )
        payload = json.loads(contracts["result"]["content"][0]["text"])
        keys = {item["source"] for item in payload}
        self.assertIn("pubmed", keys)
        self.assertIn("gnomad", keys)
        self.assertIn("eqtl_catalogue", keys)
        self.assertTrue(all(item["source_contract_version"] == "2" for item in payload))

    def test_unknown_tool_returns_jsonrpc_error(self) -> None:
        response = self.server.handle(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "unknown", "arguments": {}},
            }
        )
        self.assertEqual(-32602, response["error"]["code"])

    def test_malformed_request_shapes_do_not_terminate_server(self) -> None:
        invalid_request = self.server.handle([])  # type: ignore[arg-type]
        invalid_params = self.server.handle(
            {"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": []}
        )
        invalid_method = self.server.handle(
            {"jsonrpc": "2.0", "method": ["notifications/bad"]}
        )
        self.assertEqual(-32600, invalid_request["error"]["code"])
        self.assertEqual(-32602, invalid_params["error"]["code"])
        self.assertEqual(-32600, invalid_method["error"]["code"])

    def test_stdio_survives_invalid_method_and_processes_next_request(self) -> None:
        stdin = io.StringIO(
            '{"jsonrpc":"2.0","method":["bad"]}\n'
            '{"jsonrpc":"2.0","id":10,"method":"ping"}\n'
        )
        stdout = io.StringIO()
        with patch("sys.stdin", stdin), patch("sys.stdout", stdout):
            run_stdio(self.inventory)
        responses = [json.loads(line) for line in stdout.getvalue().splitlines()]
        self.assertEqual(-32600, responses[0]["error"]["code"])
        self.assertEqual({}, responses[1]["result"])

    def test_tool_arguments_are_validated_at_runtime(self) -> None:
        cases = (
            {"query": "x", "unexpected": True},
            {"query": 123},
            {"query": "x", "limit": True},
            {"query": "x", "limit": 11},
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                response = self.server.handle(
                    {
                        "jsonrpc": "2.0",
                        "id": 5,
                        "method": "tools/call",
                        "params": {"name": "science_search_skills", "arguments": arguments},
                    }
                )
                self.assertEqual(-32602, response["error"]["code"])


if __name__ == "__main__":
    unittest.main()
