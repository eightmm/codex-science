"""Release identity and cachebuster validation."""
from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Iterable

from codex_science.version import MCP_VERSION, PACKAGE_VERSION, PLUGIN_VERSION, RUNTIME_AFFECTING_PREFIXES

PLUGIN_RE = re.compile(r"^(?P<package>\d+\.\d+\.\d+)\+codex\.(?P<cache>[0-9A-Za-z.-]+)$")


def load_release_manifest(root: Path) -> dict:
    path = root / "release" / "manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported release manifest schema")
    return payload


def validate_release(root: Path) -> list[str]:
    errors: list[str] = []
    plugin = json.loads((root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    manifest = load_release_manifest(root)
    observed = {
        "plugin_version": str(plugin.get("version", "")),
        "package_version": str(pyproject.get("project", {}).get("version", "")),
        "mcp_version": MCP_VERSION,
    }
    expected = {
        "plugin_version": PLUGIN_VERSION,
        "package_version": PACKAGE_VERSION,
        "mcp_version": MCP_VERSION,
    }
    for key, value in expected.items():
        if observed[key] != value:
            errors.append(f"{key} mismatch: expected {value}, got {observed[key]}")
        if str(manifest.get(key, "")) != value:
            errors.append(f"release manifest {key} mismatch")
    match = PLUGIN_RE.fullmatch(PLUGIN_VERSION)
    if match is None or match.group("package") != PACKAGE_VERSION:
        errors.append("plugin cachebuster must embed the package version")
    if manifest.get("runtime_affecting_prefixes") != list(RUNTIME_AFFECTING_PREFIXES):
        errors.append("release manifest runtime-affecting prefixes are stale")
    return errors


def runtime_change_requires_bump(
    changed_paths: Iterable[str], previous_plugin_version: str, current_plugin_version: str
) -> bool:
    changed = any(
        path == ".mcp.json" or any(path.startswith(prefix) for prefix in RUNTIME_AFFECTING_PREFIXES)
        for path in changed_paths
    )
    return changed and previous_plugin_version == current_plugin_version
