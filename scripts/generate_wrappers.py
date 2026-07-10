#!/usr/bin/env python3
"""Generate or verify Codex-compatible wrappers for every catalog skill."""

from __future__ import annotations

import argparse
from pathlib import Path

from codex_science.catalog import load_inventory
from codex_science.wrappers import check_sources, check_wrappers, generate_wrappers


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, default=ROOT / "catalog" / "inventory.json")
    parser.add_argument("--output", type=Path, default=ROOT / "catalog" / "codex-skills")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    inventory = load_inventory(args.inventory)
    errors = check_sources(inventory, ROOT)
    if args.check:
        errors.extend(check_wrappers(inventory, args.output))
        if errors:
            raise SystemExit("\n".join(errors))
        print(f"wrapper check: ok ({len(inventory['skills'])} skills)")
        return
    if errors:
        raise SystemExit("\n".join(errors))
    summary = generate_wrappers(inventory, args.output)
    print(
        "wrapper generation: "
        f"total={summary['generated']} active={summary['active']} inactive={summary['inactive']}"
    )


if __name__ == "__main__":
    main()
