#!/usr/bin/env python3
"""Validate the Codex Science model registry against the audited skill inventory."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.models import registry_sha256, validate_registry  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=ROOT / "models" / "registry.json")
    parser.add_argument("--inventory", type=Path, default=ROOT / "catalog" / "inventory.json")
    args = parser.parse_args()
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    models = validate_registry(registry)
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
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
    raise SystemExit(main())
