import json
import tempfile
import unittest
from pathlib import Path

from codex_science.mcp_server import CodexScienceMCP


class MCPV3Tests(unittest.TestCase):
    def test_tool_and_source_contract_advertise_true_pagination(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            inventory = Path(tempdir) / "inventory.json"
            inventory.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "source": {"commit": "fixture"},
                        "summary": {"total": 0, "active": 0, "inactive": 0},
                        "skills": [],
                    }
                ),
                encoding="utf-8",
            )
            server = CodexScienceMCP(inventory)
            listed = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
            names = {item["name"] for item in listed["result"]["tools"]}
            self.assertIn("science_query_source_v3", names)

            contracts = server.handle(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "science_list_source_contracts", "arguments": {}},
                }
            )
            payload = json.loads(contracts["result"]["content"][0]["text"])
            by_source = {item["source"]: item for item in payload}
            for source in ("pubmed", "europepmc", "chembl", "pdb"):
                self.assertEqual(["search"], by_source[source]["v3_operations"])
            self.assertEqual([], by_source["gnomad"]["v3_operations"])


if __name__ == "__main__":
    unittest.main()
