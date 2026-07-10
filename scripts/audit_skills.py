#!/usr/bin/env python3
"""Audit one or more Agent Skills catalogs and write a deterministic inventory."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from codex_science.catalog import CatalogPolicy, audit_catalog, audit_sources, write_inventory


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "vendor" / "scientific-agent-skills" / "skills"
DEFAULT_SOURCES = ROOT / "catalog" / "sources.json"
DEFAULT_OUTPUT = ROOT / "catalog" / "inventory.json"


def current_commit(catalog: Path) -> str:
    repository = catalog.parent
    result = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", type=Path, help="Multi-source config (default: catalog/sources.json)")
    parser.add_argument("--catalog", type=Path, help="Single-catalog mode (schema 1)")
    parser.add_argument("--commit")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def audit_single(catalog: Path, commit: str | None) -> dict:
    catalog = catalog.resolve()
    if not catalog.is_dir():
        raise SystemExit(f"Catalog directory not found: {catalog}")
    resolved_commit = commit or current_commit(catalog)
    try:
        relative = catalog.relative_to(ROOT).as_posix()
    except ValueError:
        relative = ""
    return audit_catalog(catalog, resolved_commit, CatalogPolicy.default(), path_prefix=relative)


def main() -> None:
    args = parse_args()
    if args.catalog is not None:
        inventory = audit_single(args.catalog, args.commit)
    else:
        sources_path = args.sources or DEFAULT_SOURCES
        if not sources_path.is_file():
            raise SystemExit(f"Sources config not found: {sources_path}")
        config = json.loads(sources_path.read_text(encoding="utf-8"))
        inventory = audit_sources(config["sources"], ROOT, CatalogPolicy.default())
    write_inventory(inventory, args.output)
    summary = inventory["summary"]
    print(f"catalog audit: total={summary['total']} active={summary['active']} inactive={summary['inactive']}")


if __name__ == "__main__":
    main()
