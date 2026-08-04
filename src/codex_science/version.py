"""Single source of truth for Codex Science release identities."""
from __future__ import annotations

PACKAGE_VERSION = "0.5.0"
# Host-loaded hooks, MCP proxy, and bootstrap skills use this version. Automatic
# updates must not change it; a change requires the explicit curl migration so
# Codex can refresh its own cache safely.
PLUGIN_VERSION = "0.5.0+codex.20260803040515"
# Scientific workflows and implementation run from the project-owned immutable
# runtime store. This cachebuster can advance independently of PLUGIN_VERSION.
RUNTIME_VERSION = "0.5.0+codex.20260804051742"
MCP_VERSION = PACKAGE_VERSION
RELEASE_SCHEMA_VERSION = 2
RUNTIME_AFFECTING_PREFIXES = (
    ".agents/plugins/marketplace.json",
    ".codex-plugin/",
    ".gitmodules",
    ".mcp.json",
    ".python-version",
    "assets/",
    "authored-skills/",
    "catalog/",
    "connectors/",
    "docs/",
    "examples/",
    "hooks/",
    "models/",
    "pyproject.toml",
    "release/manifest.json",
    "runtime-skills/",
    "scripts/",
    "skills/",
    "src/",
    "uv.lock",
    "vendor/",
)
CACHE_NEUTRAL_FILES = (
    ".gitignore",
    "AGENTS.md",
    "CLAUDE.md",
    "LICENSE",
    "PROJECT.md",
    "README.md",
    "README.ko.md",
)
CACHE_NEUTRAL_PREFIXES = (
    ".claude/",
    ".github/",
    ".oms/",
    "benchmarks/",
    "tests/",
)
BOOTSTRAP_AFFECTING_FILES = (
    ".agents/plugins/marketplace.json",
    ".mcp.json",
    "scripts/python_runtime.sh",
    "scripts/science_hook_dispatch.py",
    "scripts/science_mcp_proxy.py",
    "scripts/science_runtime_state.py",
    "scripts/science_update_entry.py",
    "scripts/science_update_hook.py",
)
BOOTSTRAP_AFFECTING_PREFIXES = (
    ".codex-plugin/",
    "hooks/",
    "skills/",
)
