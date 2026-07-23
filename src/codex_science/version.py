"""Single source of truth for Codex Science release identities."""
from __future__ import annotations

PACKAGE_VERSION = "0.5.0"
PLUGIN_VERSION = "0.5.0+codex.20260723035417"
MCP_VERSION = PACKAGE_VERSION
RELEASE_SCHEMA_VERSION = 1
RUNTIME_AFFECTING_PREFIXES = (
    ".codex-plugin/", ".mcp.json", "authored-skills/", "catalog/", "connectors/",
    "hooks/", "models/", "scripts/", "skills/", "src/",
)
