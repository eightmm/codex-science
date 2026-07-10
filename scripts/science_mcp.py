#!/usr/bin/env python3
"""Run the Codex Science MCP server over stdio."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.mcp_server import run_stdio  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, default=ROOT / "catalog" / "inventory.json")
    args = parser.parse_args()
    run_stdio(args.inventory)


if __name__ == "__main__":
    main()
