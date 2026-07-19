#!/usr/bin/env python3
from __future__ import annotations
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.release import validate_release  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    errors = validate_release(args.root.resolve())
    if errors:
        raise SystemExit("\n".join(errors))
    print("release contract: valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
