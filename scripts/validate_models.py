#!/usr/bin/env python3
"""Validate the Codex Science model registry against the audited skill inventory."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.catalog import load_inventory  # noqa: E402
from codex_science.models import load_registry, registry_sha256, validate_registry  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=ROOT / "models" / "registry.json")
    parser.add_argument("--inventory", type=Path, default=ROOT / "catalog" / "inventory.json")
    args = parser.parse_args()
    registry = load_registry(args.registry)
    models = validate_registry(registry)
    inventory = load_inventory(args.inventory)
    active_skills = {
        str(record["name"])
        for record in inventory["skills"]
        if record.get("status") == "active"
    }
    missing = sorted({str(model["skill"]) for model in models.values()} - active_skills)
    if missing:
        raise SystemExit(f"model registry references inactive or missing skills: {', '.join(missing)}")
    print(
        f"model registry: valid ({len(models)} models, sha256={registry_sha256(registry)})"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
