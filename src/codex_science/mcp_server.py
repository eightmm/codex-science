"""Read-only MCP server for audited skills and replayable public-source queries."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from codex_science.catalog import load_inventory, search_inventory
from codex_science.connector_contract import QueryRequest, execute_connector
from codex_science.connector_sources import SOURCE_BY_KEY, SOURCE_BY_TOOL, SOURCE_SPECS
from codex_science.life_science import plan_life_science_research
from codex_science.version import MCP_VERSION

PROTOCOL_VERSION = "2025-06-18"


def _legacy_tool(name: str, description: str) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1, "maxLength": 500},
                "limit": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": True},
    }


def _v2_tool() -> dict[str, Any]:
    return {
        "name": "science_query_source_v2",
        "description": "Execute a bounded typed public-source query and return normalized records plus a canonical replay receipt.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "enum": sorted(SOURCE_BY_KEY)},
                "operation": {"type": "string", "default": "search"},
                "parameters": {"type": "object", "additionalProperties": True},
                "page_size": {"type": "integer", "minimum": 1, "maximum": 100, "default": 5},
                "max_pages": {"type": "integer", "minimum": 1, "maximum": 100, "default": 1},
                "evidence_cutoff": {"type": ["string", "null"]},
                "include_snapshot": {"type": "boolean", "default": False},
            },
            "required": ["source", "parameters"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": True},
    }


def _contracts_tool() -> dict[str, Any]:
    return {
        "name": "science_list_source_contracts",
        "description": "List public-source operations, query semantics, and maturity states.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    }


TOOLS = (
    _legacy_tool("science_search_skills", "Search the audited local scientific skill catalog."),
    *(_legacy_tool(spec.tool_name, spec.description) for spec in SOURCE_SPECS),
    _legacy_tool("science_plan_life_science_research", "Plan bounded normalization, evidence lanes, provenance, and synthesis."),
    _v2_tool(),
    _contracts_tool(),
)
TOOL_NAMES = frozenset(tool["name"] for tool in TOOLS)


class CodexScienceMCP:
    def __init__(self, inventory_path: Path) -> None:
        self.inventory_path = inventory_path
        self.connectors = {spec.key: spec.factory() for spec in SOURCE_SPECS}

    @staticmethod
    def _result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    @staticmethod
    def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}

    @staticmethod
    def _text_payload(payload: Any) -> dict[str, Any]:
        return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}

    def handle(self, request: Any) -> dict[str, Any] | None:
        if not isinstance(request, dict):
            return self._error(None, -32600, "Invalid Request")
        request_id = request.get("id")
        method = request.get("method")
        if not isinstance(method, str):
            return self._error(request_id, -32600, "Invalid Request")
        if request_id is None and method.startswith("notifications/"):
            return None
        if method == "initialize":
            return self._result(request_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "codex-science", "version": MCP_VERSION},
                "instructions": "Read-only scientific catalog and public-source queries. Prefer science_query_source_v2 for material evidence and replay receipts.",
            })
        if method == "ping":
            return self._result(request_id, {})
        if method == "tools/list":
            return self._result(request_id, {"tools": list(TOOLS)})
        if method == "tools/call":
            return self._call_tool(request_id, request.get("params", {}))
        return self._error(request_id, -32601, f"Unknown method: {method}")

    def _call_tool(self, request_id: Any, params: Any) -> dict[str, Any]:
        if not isinstance(params, dict):
            return self._error(request_id, -32602, "Invalid tool parameters")
        name, arguments = params.get("name"), params.get("arguments", {})
        if name not in TOOL_NAMES or not isinstance(arguments, dict):
            return self._error(request_id, -32602, f"Unknown or invalid tool: {name}")
        try:
            if name == "science_list_source_contracts":
                if arguments:
                    raise ValueError("science_list_source_contracts takes no arguments")
                payload = [spec.public_contract() for spec in SOURCE_SPECS]
            elif name == "science_query_source_v2":
                extra = set(arguments) - {"source", "operation", "parameters", "page_size", "max_pages", "evidence_cutoff", "include_snapshot"}
                if extra:
                    raise ValueError(f"Unexpected arguments: {', '.join(sorted(extra))}")
                source = arguments.get("source")
                if source not in SOURCE_BY_KEY:
                    raise ValueError(f"Unknown source: {source}")
                include_snapshot = arguments.get("include_snapshot", False)
                if not isinstance(include_snapshot, bool):
                    raise TypeError("include_snapshot must be boolean")
                request_payload = dict(arguments)
                request_payload.pop("include_snapshot", None)
                request = QueryRequest.from_payload(request_payload)
                payload = execute_connector(self.connectors[str(source)], request, include_snapshot=include_snapshot).to_dict(include_snapshot=include_snapshot)
            else:
                extra = set(arguments) - {"query", "limit"}
                if extra:
                    raise ValueError(f"Unexpected arguments: {', '.join(sorted(extra))}")
                query, limit = arguments.get("query", ""), arguments.get("limit", 5)
                if not isinstance(query, str):
                    raise TypeError("Query must be a string")
                if not query.strip() or len(query) > 500:
                    raise ValueError("Query must contain 1 to 500 characters")
                if isinstance(limit, bool) or not isinstance(limit, int):
                    raise TypeError("Limit must be an integer")
                if not 1 <= limit <= 10:
                    raise ValueError("Limit must be between 1 and 10")
                if name == "science_search_skills":
                    payload = search_inventory(load_inventory(self.inventory_path), query, limit=limit)
                elif name == "science_plan_life_science_research":
                    payload = plan_life_science_research(query)
                else:
                    spec = SOURCE_BY_TOOL[str(name)]
                    payload = self.connectors[spec.key].search(query, limit=limit)
        except (KeyError, TypeError, ValueError) as exc:
            return self._error(request_id, -32602, str(exc))
        except Exception as exc:
            return self._result(request_id, {"content": [{"type": "text", "text": f"Connector error: {exc}"}], "isError": True})
        return self._result(request_id, self._text_payload(payload))


def run_stdio(inventory_path: Path) -> None:
    server = CodexScienceMCP(inventory_path)
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            response = server.handle(request)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            response = CodexScienceMCP._error(None, -32700, str(exc))
        if response is not None:
            sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
            sys.stdout.flush()
