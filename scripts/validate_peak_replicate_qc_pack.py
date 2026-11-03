#!/usr/bin/env python3
"""Validate one offline synthetic peak QC bundle; print JSON and write nothing."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from codex_science.peak_replicate_qc_pack import validate_peak_replicate_qc_pack  # noqa: E402


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError('invalid-arguments: ' + message)


def main():
    parser = _Parser(description=__doc__)
    parser.add_argument('bundle', help='peak-qc-pack-v1 JSON with hash-bound synthetic fixture inputs')
    try:
        args = parser.parse_args()
        print(json.dumps(validate_peak_replicate_qc_pack(args.bundle), sort_keys=True, allow_nan=False))
        return 0
    except ValueError as error:
        print(json.dumps({'status': 'refused', 'error': str(error)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
