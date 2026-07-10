#!/usr/bin/env python3
"""Audit an Agent Skills catalog and write a deterministic inventory."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from codex_science.catalog import CatalogPolicy, audit_catalog, write_inventory


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "vendor" / "scientific-agent-skills" / "skills"
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
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--commit")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    catalog = args.catalog.resolve()
    if not catalog.is_dir():
        raise SystemExit(f"Catalog directory not found: {catalog}")
    commit = args.commit or current_commit(catalog)
    try:
        relative = catalog.relative_to(ROOT).as_posix()
    except ValueError:
        relative = ""
    inventory = audit_catalog(catalog, commit, CatalogPolicy.default(), path_prefix=relative)
    write_inventory(inventory, args.output)
    summary = inventory["summary"]
    print(f"catalog audit: total={summary['total']} active={summary['active']} inactive={summary['inactive']}")


if __name__ == "__main__":
    main()
