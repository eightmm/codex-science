import json
import tempfile
import unittest
from pathlib import Path

from codex_science.mcp_server import CodexScienceMCP


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
        initialized = self.server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        listed = self.server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})

        self.assertEqual("2025-06-18", initialized["result"]["protocolVersion"])
        names = {tool["name"] for tool in listed["result"]["tools"]}
        self.assertEqual(
            {"science_search_skills", "science_search_pubmed", "science_search_arxiv", "science_search_uniprot"},
            names,
        )

    def test_search_skill_tool_returns_only_catalog_matches(self) -> None:
        response = self.server.handle(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "science_search_skills", "arguments": {"query": "symbolic math"}},
            }
        )

        text = response["result"]["content"][0]["text"]
        payload = json.loads(text)
        self.assertEqual("sympy", payload[0]["name"])

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


if __name__ == "__main__":
    unittest.main()
