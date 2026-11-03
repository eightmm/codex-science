#!/usr/bin/env python3
"""Read-only offline validation of one synthetic qPCR pack JSON bundle."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from codex_science.qpcr_relative_quantification_pack import validate_qpcr_relative_quantification_pack


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError("invalid-arguments: " + message)


def main():
    parser = _Parser(description=__doc__)
    parser.add_argument("bundle", help="qpcr-pack-v1 JSON with relative path and SHA-256 identities")
    try:
        args = parser.parse_args()
        print(json.dumps(validate_qpcr_relative_quantification_pack(args.bundle), sort_keys=True, allow_nan=False))
        return 0
    except (ValueError, OSError) as error:
        print(json.dumps({"status": "refused", "error": str(error)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
