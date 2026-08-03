"""Release identity and cachebuster validation."""
from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Iterable

from codex_science.version import (
    BOOTSTRAP_AFFECTING_FILES,
    BOOTSTRAP_AFFECTING_PREFIXES,
    CACHE_NEUTRAL_FILES,
    CACHE_NEUTRAL_PREFIXES,
    MCP_VERSION,
    PACKAGE_VERSION,
    PLUGIN_VERSION,
    RELEASE_SCHEMA_VERSION,
    RUNTIME_AFFECTING_PREFIXES,
    RUNTIME_VERSION,
)

RELEASE_VERSION_RE = re.compile(
    r"^(?P<package>\d+\.\d+\.\d+)\+codex\.(?P<cache>\d{14})$"
)
# Kept as a compatibility alias for callers that used the old single-identity
# name. Both the stable bootstrap and live runtime use the same syntax.
PLUGIN_RE = RELEASE_VERSION_RE


def load_release_manifest(root: Path) -> dict:
    path = root / "release" / "manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") not in {1, 2}:
        raise ValueError("unsupported release manifest schema")
    return payload


def manifest_runtime_version(manifest: dict) -> str:
    """Return the runtime identity, including the schema-1 compatibility rule."""

    schema = manifest.get("schema_version")
    if schema == 1:
        value = manifest.get("plugin_version")
    elif schema == 2:
        value = manifest.get("runtime_version")
    else:
        raise ValueError("unsupported release manifest schema")
    if not isinstance(value, str) or not value:
        raise ValueError("release manifest runtime version is missing")
    return value


def validate_release(root: Path) -> list[str]:
    errors: list[str] = []
    plugin = json.loads((root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    manifest = load_release_manifest(root)
    observed_plugin = str(plugin.get("version", ""))
    observed_package = str(pyproject.get("project", {}).get("version", ""))
    try:
        observed_runtime = manifest_runtime_version(manifest)
    except ValueError:
        observed_runtime = ""
    for key, observed, expected in (
        ("plugin_version", observed_plugin, PLUGIN_VERSION),
        ("package_version", observed_package, PACKAGE_VERSION),
        ("runtime_version", observed_runtime, RUNTIME_VERSION),
    ):
        if observed != expected:
            errors.append(f"{key} mismatch: expected {expected}, got {observed}")
    for key, expected in (
        ("package_version", PACKAGE_VERSION),
        ("plugin_version", PLUGIN_VERSION),
        ("runtime_version", RUNTIME_VERSION),
        ("mcp_version", MCP_VERSION),
    ):
        if str(manifest.get(key, "")) != expected:
            errors.append(f"release manifest {key} mismatch")
    if manifest.get("schema_version") != RELEASE_SCHEMA_VERSION:
        errors.append("release manifest schema is stale")
    if RELEASE_VERSION_RE.fullmatch(PLUGIN_VERSION) is None:
        errors.append("plugin version must match <semver>+codex.<14 digits>")
    runtime_match = RELEASE_VERSION_RE.fullmatch(RUNTIME_VERSION)
    if runtime_match is None:
        errors.append("runtime version must match <semver>+codex.<14 digits>")
    elif runtime_match.group("package") != PACKAGE_VERSION:
        errors.append("runtime version must embed the package version")
    if manifest.get("runtime_affecting_prefixes") != list(RUNTIME_AFFECTING_PREFIXES):
        errors.append("release manifest runtime-affecting prefixes are stale")
    if manifest.get("cache_neutral_files") != list(CACHE_NEUTRAL_FILES):
        errors.append("release manifest cache-neutral files are stale")
    if manifest.get("cache_neutral_prefixes") != list(CACHE_NEUTRAL_PREFIXES):
        errors.append("release manifest cache-neutral prefixes are stale")
    if manifest.get("bootstrap_affecting_files") != list(BOOTSTRAP_AFFECTING_FILES):
        errors.append("release manifest bootstrap-affecting files are stale")
    if manifest.get("bootstrap_affecting_prefixes") != list(BOOTSTRAP_AFFECTING_PREFIXES):
        errors.append("release manifest bootstrap-affecting prefixes are stale")
    return errors


def classify_release_path(
    path: str,
    *,
    runtime_prefixes: Iterable[str] = RUNTIME_AFFECTING_PREFIXES,
    neutral_files: Iterable[str] = CACHE_NEUTRAL_FILES,
    neutral_prefixes: Iterable[str] = CACHE_NEUTRAL_PREFIXES,
) -> str:
    if any(path.startswith(prefix) for prefix in runtime_prefixes):
        return "runtime"
    if path in neutral_files or any(path.startswith(prefix) for prefix in neutral_prefixes):
        return "neutral"
    return "unknown"


def runtime_change_requires_bump(
    changed_paths: Iterable[str],
    previous_runtime_version: str,
    current_runtime_version: str,
    *,
    prefixes: Iterable[str] = RUNTIME_AFFECTING_PREFIXES,
) -> bool:
    runtime_prefixes = tuple(prefixes)
    changed = any(
        any(path.startswith(prefix) for prefix in runtime_prefixes)
        for path in changed_paths
    )
    return changed and not release_version_advances(
        previous_runtime_version, current_runtime_version
    )


def release_version_advances(previous: str, current: str) -> bool:
    previous_match = RELEASE_VERSION_RE.fullmatch(previous)
    current_match = RELEASE_VERSION_RE.fullmatch(current)
    if previous_match is None or current_match is None:
        return False
    previous_package = tuple(int(value) for value in previous_match.group("package").split("."))
    current_package = tuple(int(value) for value in current_match.group("package").split("."))
    if current_package != previous_package:
        return current_package > previous_package
    return int(current_match.group("cache")) > int(previous_match.group("cache"))


def plugin_version_advances(previous: str, current: str) -> bool:
    """Compatibility name for the shared monotonic release-version ordering."""

    return release_version_advances(previous, current)
