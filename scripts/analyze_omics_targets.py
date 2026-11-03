#!/usr/bin/env python3
"""Analyze one workflow JSON file or stdin; emit a JSON result or error."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from codex_science.omics_targets import analyze_omics_targets


def _constant(value):
    raise ValueError(f'nonstandard JSON constant: {value}')


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON key: {key}')
        result[key] = value
    return result


def main():
    try:
        if len(sys.argv) != 2:
            raise ValueError('usage: analyze_omics_targets.py INPUT.json|-')
        if sys.argv[1] == '-':
            record = json.load(sys.stdin, parse_constant=_constant, object_pairs_hook=_unique)
        else:
            with open(sys.argv[1], encoding='utf-8') as stream:
                record = json.load(stream, parse_constant=_constant, object_pairs_hook=_unique)
        json.dumps(record, allow_nan=False)
        result = analyze_omics_targets(record)
        output = json.dumps(result, indent=2, allow_nan=False)
    except (ValueError, TypeError, KeyError, OSError, OverflowError, RecursionError) as exc:
        print(json.dumps({'status': 'invalid', 'error': str(exc)}, allow_nan=False))
        return 2
    print(output)
    return 0


if __name__ == '__main__':
    sys.exit(main())
