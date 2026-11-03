#!/usr/bin/env python3
"""Analyze supplied free-energy network records; never launch simulations."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from codex_science.md_campaign import analyze_md_campaign


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def _invalid(value):
    raise ValueError('nonfinite JSON constant: ' + value)


def main():
    try:
        if len(sys.argv) != 2:
            raise ValueError('usage: analyze_md_campaign.py INPUT.json')
        record = json.loads(Path(sys.argv[1]).read_text(), object_pairs_hook=_unique, parse_constant=_invalid)
        result = analyze_md_campaign(record)
        print(json.dumps(result, allow_nan=False, sort_keys=True))
        return 0
    except (ValueError, KeyError, TypeError, OSError, OverflowError) as error:
        print(json.dumps({'status': 'invalid', 'error': str(error)}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
