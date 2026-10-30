import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_science.mcp_server import CONNECTOR_SPECS, TOOLS, CodexScienceMCP, run_stdio
from codex_science.version import MCP_VERSION
from codex_science.connectors import OpenTargetsConnector


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

    def test_platform_v2_mcp_example_matches_input_schema_and_executes(self) -> None:
        document = (Path(__file__).resolve().parents[1] / "docs/PLATFORM_CONTRACTS.md").read_text(
            encoding="utf-8"
        )
        section = document.split("## Connector Contract v2\n", 1)[1].split("\n### ", 1)[0]
        examples = re.findall(r"```json\n(.*?)\n```", section, re.S)
        self.assertEqual(1, len(examples))
        arguments = json.loads(examples[0])
        listed = self.server.handle({"id": 1, "method": "tools/list"})
        schema = next(tool["inputSchema"] for tool in listed["result"]["tools"]
                      if tool["name"] == "science_query_source_v2")
        self.assertIsInstance(arguments, dict)
        self.assertLessEqual(set(schema["required"]), set(arguments))
        self.assertFalse(schema["additionalProperties"])
        self.assertLessEqual(set(arguments), set(schema["properties"]))
        types = {"string": str, "object": dict, "integer": int, "boolean": bool, "null": type(None)}
        for name, value in arguments.items():
            field = schema["properties"][name]
            kinds = field["type"] if isinstance(field["type"], list) else [field["type"]]
            with self.subTest(argument=name):
                self.assertIn(type(value), [types[kind] for kind in kinds])
                if "enum" in field:
                    self.assertIn(value, field["enum"])
                if "minimum" in field:
                    self.assertGreaterEqual(value, field["minimum"])
                if "maximum" in field:
                    self.assertLessEqual(value, field["maximum"])
        with patch.object(self.server.sources[arguments["source"]], "search", return_value=[]) as search:
            response = self.server.handle({"id": 2, "method": "tools/call", "params": {
                "name": "science_query_source_v2", "arguments": arguments,
            }})
        self.assertNotIn("error", response)
        self.assertNotIn("isError", response["result"])
        self.assertEqual([], json.loads(response["result"]["content"][0]["text"])["records"])
        search.assert_called_once()

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

    def test_v2_opentargets_rejects_graphql_errors_and_invalid_envelopes(self) -> None:
        for payload in ({"errors": [{"message": "backend unavailable"}]}, {}, {"data": None},
                        {"data": {"search": {"hits": []}}, "errors": [{"message": "backend unavailable"}]}):
            self.server.sources["opentargets"] = OpenTargetsConnector(post_json=lambda *_: payload)
            response = self.server.handle({"jsonrpc": "2.0", "id": 31, "method": "tools/call", "params": {
                "name": "science_query_source_v2", "arguments": {
                    "source": "opentargets", "operation": "search", "parameters": {"query": "TP53"}}}})
            with self.subTest(payload=payload):
                self.assertIn("error", response)
                self.assertIn("upstream error", response["error"]["message"])

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

    def test_non_string_tool_names_return_jsonrpc_errors(self) -> None:
        for name in (["x"], {}, [], None, 0, True):
            with self.subTest(name=name):
                response = self.server.handle({
                    "jsonrpc": "2.0", "id": 40, "method": "tools/call",
                    "params": {"name": name, "arguments": {}},
                })
                self.assertEqual(40, response["id"])
                self.assertEqual(-32602, response["error"]["code"])

    def test_source_argument_types_match_schema_before_dispatch(self) -> None:
        for version, source, executor in (
            ("v2", "eqtl_catalogue", "execute_connector"),
            ("v3", "europepmc", "execute_paginated"),
        ):
            arguments = {"source": source, "parameters": {"query": "release"}}
            if version == "v2":
                arguments["include_snapshot"] = True
            cases = [("parameters", value) for value in (
                [["query", "release"]], [], "", "query", None, False, 0,
            )]
            cases.extend((field, value) for field in ("page_size", "max_pages")
                         for value in (True, False, 1.9, 1.0, "1", "", None, [], {}, 0, -1, 101))
            with patch(f"codex_science.mcp_server.{executor}") as execute:
                execute.return_value.to_dict.return_value = {"records": []}
                for field, value in cases:
                    with self.subTest(version=version, field=field, value=value):
                        execute.reset_mock()
                        response = self.server.handle({
                            "jsonrpc": "2.0", "id": 41, "method": "tools/call",
                            "params": {"name": f"science_query_source_{version}",
                                       "arguments": {**arguments, field: value}},
                        })
                        self.assertEqual(-32602, response.get("error", {}).get("code"))
                        execute.assert_not_called()
                for optional in ({}, {"parameters": {}}, {"page_size": 1, "max_pages": 1},
                                 {"page_size": 100, "max_pages": 100}):
                    with self.subTest(version=version, valid=optional):
                        execute.reset_mock()
                        response = self.server.handle({
                            "jsonrpc": "2.0", "id": 42, "method": "tools/call",
                            "params": {"name": f"science_query_source_{version}",
                                       "arguments": {**arguments, **optional}},
                        })
                        self.assertNotIn("error", response)
                        self.assertNotIn("isError", response["result"])
                        execute.assert_called_once()
                        request = execute.call_args.args[1]
                        self.assertEqual(optional.get("parameters", arguments["parameters"]), request.parameters)
                        self.assertEqual(optional.get("page_size", 5), request.page_size)
                        self.assertEqual(optional.get("max_pages", 1), request.max_pages)
                        if version == "v2":
                            self.assertTrue(execute.call_args.kwargs["include_snapshot"])

    def test_stdio_survives_deep_json_in_real_process(self) -> None:
        nested = "[" * 10000 + "0" + "]" * 10000
        request = ('{"jsonrpc":"2.0","id":43,"method":"tools/call",'
                   '"params":{"name":"science_query_source_v2",'
                   '"arguments":{"source":"eqtl_catalogue","parameters":{"query":'
                   + nested + '}}}}\n')
        completed = subprocess.run(
            [sys.executable, "scripts/science_mcp.py", "--inventory", str(self.inventory)],
            cwd=Path(__file__).resolve().parents[1],
            input=request + '{"jsonrpc":"2.0","id":44,"method":"ping"}\n',
            text=True, capture_output=True,
            timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "60")),
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        responses = [json.loads(line) for line in completed.stdout.splitlines()]
        self.assertEqual(2, len(responses))
        self.assertEqual(-32700, responses[0]["error"]["code"])
        self.assertEqual({"jsonrpc": "2.0", "id": 44, "result": {}}, responses[1])

    def test_stdio_bounds_frames_and_recovers_in_real_process(self) -> None:
        limit = 96
        ping = '{"id":44,"method":"ping"}'
        exact = ping + " " * (limit - len(ping) - 1) + "\n"
        wide_prefix = '{"id":49,"method":"ping","extra":"'
        wide = wide_prefix + "é" * (limit - len(wide_prefix) - 3) + '"}\n'
        oversized = ping + " " * (limit - len(ping)) + "\n"
        frames = ("\n\u00a0\n0\n{\n" + exact + oversized + " " * (2 * 65536 + 17) + "\n"
                  + '{"method":"notifications/initialized"}\n'
                  + '{"id":45,"method":"ping","extra":"' + "é" * limit + '"}\n'
                  + ping + "\n" + wide + " " * (limit * 4))
        launcher = (
            "import runpy, sys; import codex_science.mcp_server as server; "
            f"server.DEFAULT_MAX_JSON_BYTES = {limit}; "
            "sys.argv = ['scripts/science_mcp.py', '--inventory', sys.argv[1]]; "
            "runpy.run_path('scripts/science_mcp.py', run_name='__main__')"
        )
        completed = subprocess.run(
            [sys.executable, "-c", launcher, str(self.inventory)],
            cwd=Path(__file__).resolve().parents[1], input=frames,
            encoding="utf-8", capture_output=True,
            env=dict(os.environ, LC_ALL="C.UTF-8", LANG="C.UTF-8",
                     PYTHONUTF8="0", PYTHONCOERCECLOCALE="0",
                     PYTHONIOENCODING="utf-8:strict"),
            timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "60")),
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        responses = [json.loads(line) for line in completed.stdout.splitlines()]
        self.assertEqual(9, len(responses))
        self.assertEqual(-32600, responses[0]["error"]["code"])
        self.assertEqual(-32700, responses[1]["error"]["code"])
        for index in (2, 6):
            self.assertEqual({"jsonrpc": "2.0", "id": 44, "result": {}}, responses[index])
        self.assertEqual({"jsonrpc": "2.0", "id": 49, "result": {}}, responses[7])
        for index in (3, 4, 5, 8):
            self.assertIsNone(responses[index]["id"])
            self.assertEqual(-32600, responses[index]["error"]["code"])
            self.assertIn(f"frame limit of {limit} characters", responses[index]["error"]["message"])

        class BoundedInput(io.StringIO):
            def readline(stream, size=-1):
                self.assertGreater(size, 0)
                self.assertLessEqual(size, max(limit + 1, 65536))
                return super().readline(size)

            def __iter__(stream):
                self.fail("stdio must read bounded frames")

        stdout = io.StringIO()
        with patch("sys.stdin", BoundedInput(frames)), patch("sys.stdout", stdout), \
                patch("codex_science.mcp_server.DEFAULT_MAX_JSON_BYTES", limit, create=True):
            run_stdio(self.inventory)
        self.assertEqual(completed.stdout, stdout.getvalue())
        for raw in ("", ping):
            stdout = io.StringIO()
            with patch("sys.stdin", BoundedInput(raw)), patch("sys.stdout", stdout), \
                    patch("codex_science.mcp_server.DEFAULT_MAX_JSON_BYTES", limit, create=True):
                run_stdio(self.inventory)
            self.assertEqual("" if not raw else json.dumps(
                {"jsonrpc": "2.0", "id": 44, "result": {}}, separators=(",", ":")) + "\n",
                stdout.getvalue())

        raw_frames = (b'{"id":47,"method":"ping","extra":"\xff"}\r\n'
                      b'{"method":"notifications/initialized","extra":"\xff"}\r\n'
                      b'{"id":48,"method":"ping"}')
        reference = """\
import json, sys
from pathlib import Path
from codex_science.mcp_server import CodexScienceMCP
server = CodexScienceMCP(Path(sys.argv[1]))
for line in sys.stdin:
    if not line.strip():
        continue
    try:
        response = server.handle(json.loads(line))
    except (json.JSONDecodeError, TypeError, ValueError, RecursionError) as error:
        response = server._error(None, -32700, str(error))
    if response is not None:
        print(json.dumps(response, separators=(",", ":")), flush=True)
"""
        locale = os.environ.get("LC_ALL", "C.UTF-8")
        if locale not in ("C", "C.UTF-8"):
            locale = "C.UTF-8"
        for setting in (None, "utf-8:strict", "utf-8:surrogateescape", "latin-1:strict",
                        "utf-8:replace", "utf-8:ignore", "utf-16:strict", "utf-32:strict"):
            env = dict(os.environ, LC_ALL=locale, LANG=locale,
                       PYTHONUTF8="0", PYTHONCOERCECLOCALE="0")
            env.pop("PYTHONIOENCODING", None)
            if setting is not None:
                env["PYTHONIOENCODING"] = setting
            with self.subTest(stdin_encoding=setting):
                configuration = subprocess.run(
                    [sys.executable, "-c", "import json,sys; print(json.dumps([sys.stdin.encoding,sys.stdin.errors,sys.stdout.encoding]))"],
                    capture_output=True, env=env,
                    timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "60")))
                self.assertEqual(0, configuration.returncode, configuration.stderr)
                encoding, errors, output_encoding = json.loads(configuration.stdout)
                payload = (raw_frames.decode("latin-1").encode(encoding)
                           if setting in ("utf-16:strict", "utf-32:strict") else raw_frames)
                try:
                    payload.decode(encoding, errors)
                except UnicodeError:
                    expected_exit, expected_responses = 1, []
                else:
                    expected_exit, expected_responses = 0, [
                        {"jsonrpc": "2.0", "id": 47, "result": {}},
                        {"jsonrpc": "2.0", "id": 48, "result": {}},
                    ]
                native = subprocess.run(
                    [sys.executable, "-c", reference, str(self.inventory)],
                    input=payload, capture_output=True, env=env,
                    timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "60")))
                self.assertEqual(expected_exit, native.returncode, native.stderr)
                self.assertEqual(expected_responses, [json.loads(line) for line in native.stdout.decode(output_encoding).splitlines()])
                completed = subprocess.run(
                    [sys.executable, "-c", launcher, str(self.inventory)],
                    cwd=Path(__file__).resolve().parents[1], input=payload,
                    capture_output=True, env=env,
                    timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "60")))
                self.assertEqual(native.returncode, completed.returncode, completed.stderr)
                self.assertEqual(native.stdout, completed.stdout)
        stdout = io.StringIO()
        with patch("sys.stdin", BoundedInput(raw_frames.decode("utf-8", "surrogateescape"))), \
                patch("sys.stdout", stdout), \
                patch("codex_science.mcp_server.DEFAULT_MAX_JSON_BYTES", limit):
            run_stdio(self.inventory)
        self.assertEqual([47, 48], [json.loads(line)["id"] for line in stdout.getvalue().splitlines()])

    def test_stdio_survives_handler_recursion(self) -> None:
        stdin = io.StringIO(
            '{"jsonrpc":"2.0","id":45,"method":"tools/call",'
            '"params":{"name":"science_search_skills","arguments":{"query":"math"}}}\n'
            '{"jsonrpc":"2.0","id":46,"method":"ping"}\n'
        )
        stdout = io.StringIO()
        with patch("sys.stdin", stdin), patch("sys.stdout", stdout), patch.object(
            CodexScienceMCP, "_text_payload", side_effect=RecursionError("nested result")
        ):
            run_stdio(self.inventory)
        responses = [json.loads(line) for line in stdout.getvalue().splitlines()]
        self.assertEqual(2, len(responses))
        self.assertEqual(-32700, responses[0]["error"]["code"])
        self.assertEqual({"jsonrpc": "2.0", "id": 46, "result": {}}, responses[1])

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
        self.assertIsNone(invalid_method)

    def test_stdio_survives_invalid_method_and_processes_next_request(self) -> None:
        stdin = io.StringIO(
            '{"jsonrpc":"2.0","method":["bad"]}\n'
            '{"jsonrpc":"2.0","id":10,"method":"ping"}\n'
        )
        stdout = io.StringIO()
        with patch("sys.stdin", stdin), patch("sys.stdout", stdout):
            run_stdio(self.inventory)
        responses = [json.loads(line) for line in stdout.getvalue().splitlines()]
        self.assertEqual(1, len(responses))
        self.assertEqual({}, responses[0]["result"])

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

    def test_unexpected_arguments_name_the_accepted_set(self) -> None:
        cases = (
            (
                "science_search_skills",
                {"query": "x", "page_size": 5},
                "Unexpected arguments: page_size; accepted: query, limit (1-10)",
            ),
            (
                "science_query_source_v3",
                {"source": "europepmc", "bogus": 1},
                "Unexpected arguments: bogus; accepted: evidence_cutoff, max_pages, operation, page_size, "
                "parameters, source",
            ),
        )
        for name, arguments, expected in cases:
            with self.subTest(tool=name):
                response = self.server.handle(
                    {
                        "jsonrpc": "2.0",
                        "id": 6,
                        "method": "tools/call",
                        "params": {"name": name, "arguments": arguments},
                    }
                )
                self.assertEqual(-32602, response["error"]["code"])
                self.assertEqual(expected, response["error"]["message"])


if __name__ == "__main__":
    unittest.main()
