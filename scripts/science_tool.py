#!/usr/bin/env python3
"""Call a codex-science MCP tool from the command line.

Use this when the MCP server is not running. The tools are the same as the
codex-science MCP tools and are served by the same server code, so accepted
inputs and output match exactly. All tools are read-only; connector tools
(science_search_*, science_query_source_v2/_v3) contact public sources over
the network. Prints the tool's JSON result to stdout.

Exit codes: 0 success, 1 tool-reported failure (message on stderr),
2 invalid usage or arguments.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.mcp_server import TOOLS, CodexScienceMCP  # noqa: E402


def _json_safe(text: str) -> str:
    """Escape to ASCII when the JSON text holds lone surrogates, as the MCP stdio server does."""
    return text if _utf8_ok(text) else json.dumps(json.loads(text))


def _plain_safe(text: str) -> str:
    return text.encode("ascii", "backslashreplace").decode("ascii") if not _utf8_ok(text) else text


def _utf8_ok(text: str) -> bool:
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _fail(message: str, code: int = 2) -> None:
    print(_plain_safe(f"error: {message}"), file=sys.stderr)
    raise SystemExit(code)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("tool", nargs="?", metavar="TOOL_NAME", help="MCP tool name, for example science_search_skills (see --list)")
    parser.add_argument("--list", action="store_true", help="print each tool name and description, one per line, then exit")
    parser.add_argument("--json", dest="json_args", metavar="ARGS_JSON", help="the tool's arguments as a JSON object; exclusive with --query/--limit")
    parser.add_argument("--query", metavar="TEXT", help="shorthand for {\"query\": TEXT}; passed through unchanged; exclusive with --json")
    parser.add_argument("--limit", type=int, metavar="N", help="shorthand for {\"limit\": N}; only with --query")
    args = parser.parse_args()

    if args.list:
        for tool in TOOLS:
            print(_plain_safe(f"{tool['name']}\t{tool['description']}"))
        return
    if not args.tool:
        parser.error("TOOL_NAME is required (or use --list)")
    if args.json_args is not None and (args.query is not None or args.limit is not None):
        parser.error("--json cannot be combined with --query/--limit")
    if args.limit is not None and args.query is None:
        parser.error("--limit requires --query")
    if args.json_args is not None:
        try:
            arguments = json.loads(args.json_args)
        except (ValueError, RecursionError) as exc:
            _fail(f"--json is not valid JSON: {exc}")
        if not isinstance(arguments, dict):
            _fail("--json must be a JSON object")
    else:
        arguments = {}
        if args.query is not None:
            arguments["query"] = args.query
        if args.limit is not None:
            arguments["limit"] = args.limit

    server = CodexScienceMCP(ROOT / "catalog" / "inventory.json")
    response = server.handle(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": args.tool, "arguments": arguments}}
    )
    if response is None:
        _fail("server returned no response")
    if "error" in response:
        _fail(str(response["error"].get("message", "unknown error")))
    result = response["result"]
    text = result["content"][0]["text"]
    if result.get("isError"):
        print(_plain_safe(text), file=sys.stderr)
        raise SystemExit(1)
    print(_json_safe(text))


def _run() -> None:
    try:
        try:
            main()
        finally:
            sys.stdout.flush()
    except BrokenPipeError:
        # The reader closed early: point stdout at devnull so the interpreter's
        # exit-time flush cannot raise again.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        raise SystemExit(1)


if __name__ == "__main__":
    _run()
