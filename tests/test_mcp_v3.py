import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from codex_science.mcp_server import CodexScienceMCP
from test_transport_v3 import FakeTransport


class MCPV3Tests(unittest.TestCase):
    def test_query_v3_refuses_non_string_cutoffs_before_dispatch(self):
        server = CodexScienceMCP(Path("unused-inventory.json"))
        invalid = (2026, 2026.0, 0, -1, True, False, [], [2026], {}, {"year": 2026})
        with patch("codex_science.mcp_server.execute_paginated") as execute:
            execute.return_value.to_dict.return_value = {"records": []}
            for source in ("pubmed", "europepmc", "chembl", "pdb"):
                for cutoff in invalid:
                    with self.subTest(source=source, cutoff=cutoff):
                        execute.reset_mock()
                        reply = server.handle({
                            "jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
                                "name": "science_query_source_v3", "arguments": {
                                    "source": source, "parameters": {"query": "x"}, "evidence_cutoff": cutoff}}})
                        self.assertEqual(-32602, reply["error"]["code"])
                        self.assertIn("invalid evidence_cutoff:", reply["error"]["message"])
                        self.assertIn("string or null", reply["error"]["message"])
                        execute.assert_not_called()
                for extra in ({}, {"evidence_cutoff": None}, {"evidence_cutoff": "2026"},
                              {"evidence_cutoff": "2026-01-01"}):
                    with self.subTest(source=source, extra=extra):
                        execute.reset_mock()
                        reply = server.handle({
                            "jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
                                "name": "science_query_source_v3", "arguments": {
                                    "source": source, "parameters": {"query": "x"}, **extra}}})
                        self.assertNotIn("error", reply)
                        execute.assert_called_once()
                        self.assertEqual(extra.get("evidence_cutoff"), execute.call_args.args[1].evidence_cutoff)
        with patch("codex_science.mcp_server.execute_connector") as execute:
            execute.return_value.to_dict.return_value = {"records": []}
            for cutoff in (*invalid, None, "2026"):
                with self.subTest(version="v2", cutoff=cutoff):
                    execute.reset_mock()
                    reply = server.handle({
                        "jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
                            "name": "science_query_source_v2", "arguments": {
                                "source": "eqtl_catalogue", "parameters": {"query": "x"}, "evidence_cutoff": cutoff}}})
                    self.assertNotIn("error", reply)
                    execute.assert_called_once()
                    self.assertEqual(None if cutoff is None else str(cutoff), execute.call_args.args[1].evidence_cutoff)

    def test_query_v3_uses_canonical_cutoff_dates(self):
        fake = FakeTransport([({"esearchresult": {"count": "1", "idlist": ["1"]}}, {})])
        with patch("codex_science.transport_v3.UrllibTransport", return_value=fake):
            reply = CodexScienceMCP(Path("unused-inventory.json")).handle({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
                    "name": "science_query_source_v3", "arguments": {
                        "source": "pubmed", "parameters": {"query": "x", "maxdate": "2026/1/1", "mindate": "2025-1-1"},
                        "evidence_cutoff": "2026-01-01"}}})
        receipt = json.loads(reply["result"]["content"][0]["text"])["receipt"]
        self.assertEqual("complete", receipt["status"])
        params = parse_qs(urlsplit(fake.requests[0].url).query)
        self.assertEqual(["2026/01/01"], params["maxdate"])
        self.assertEqual(["2025/01/01"], params["mindate"])

    def test_query_v3_labels_invalid_cutoffs(self):
        for source in ("pubmed", "europepmc", "chembl", "pdb"):
            for cutoff in ("", "2026/02/30", "２０２６-01-01", "2026/01-01", "2026-01/01"):
                fake = FakeTransport([])
                with self.subTest(source=source, cutoff=cutoff), patch(
                    "codex_science.transport_v3.UrllibTransport", return_value=fake
                ):
                    reply = CodexScienceMCP(Path("unused-inventory.json")).handle({
                        "jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
                            "name": "science_query_source_v3", "arguments": {
                                "source": source, "parameters": {"query": "x", "maxdate": "2026/01/01"},
                                "evidence_cutoff": cutoff}}})
                    self.assertEqual(-32602, reply["error"]["code"])
                    self.assertTrue(reply["error"]["message"].startswith("invalid evidence_cutoff:"))
                    self.assertEqual([], fake.requests)

    def test_query_v3_reports_unenforced_cutoffs(self):
        for source, payload in (
            ("pdb", {"total_count": 1, "result_set": [{"identifier": "1ABC"}]}),
            ("chembl", {"molecules": [{"molecule_chembl_id": "CHEMBL1"}], "page_meta": {"next": None}}),
        ):
            fake = FakeTransport([(payload, {})])
            with self.subTest(source=source), patch("codex_science.transport_v3.UrllibTransport", return_value=fake):
                reply = CodexScienceMCP(Path("unused-inventory.json")).handle({
                    "jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
                        "name": "science_query_source_v3", "arguments": {
                            "source": source, "parameters": {"query": "x"}, "evidence_cutoff": "2026-01-01"}}})
            receipt = json.loads(reply["result"]["content"][0]["text"])["receipt"]
            self.assertEqual("bounded-by-user", receipt["status"])
            self.assertEqual("bounded-by-user", receipt["completeness"])
            self.assertEqual([f"evidence cutoff was not enforced by source: {source}"], receipt["warnings"])

    def test_query_v3_labels_cutoff_conflicts_and_page_overlap(self):
        for arguments, responses, label in (
            ({"source": "pubmed", "parameters": {"query": "x", "maxdate": "2027/01/01"},
              "evidence_cutoff": "2026-01-01"}, [], "evidence-cutoff-conflict"),
            ({"source": "pdb", "parameters": {"query": "x"}, "page_size": 1, "max_pages": 2},
             [({"total_count": 2, "result_set": [{"identifier": "1ABC"}]}, {})] * 2,
             "schema-drift: pagination has overlapping record identities"),
        ):
            fake = FakeTransport(responses)
            with self.subTest(label=label), patch("codex_science.transport_v3.UrllibTransport", return_value=fake):
                reply = CodexScienceMCP(Path("unused-inventory.json")).handle({
                    "jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
                        "name": "science_query_source_v3", "arguments": arguments}})
            self.assertEqual(-32602, reply["error"]["code"])
            self.assertIn(label, reply["error"]["message"])

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
