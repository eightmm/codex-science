#!/usr/bin/env python3
"""Read a protein variant JSON file (or stdin with -); emit JSON only."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from codex_science.protein_variants import analyze_protein_variants


def _reject_constant(value):
    raise ValueError(f'nonstandard JSON constant: {value}')


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON key: {key}')
        result[key] = value
    return result


def _load(stream):
    return json.load(stream, parse_constant=_reject_constant, object_pairs_hook=_unique_object)


def main():
    try:
        if len(sys.argv) != 2:
            raise ValueError('usage: analyze_protein_variants.py INPUT.json|-')
        if sys.argv[1] == '-':
            record = _load(sys.stdin)
        else:
            with open(sys.argv[1], encoding='utf-8') as stream:
                record = _load(stream)
        result = analyze_protein_variants(record)
        output = json.dumps(result, indent=2, allow_nan=False)
    except (ValueError, TypeError, KeyError, OSError, OverflowError) as exc:
        print(json.dumps({'status': 'invalid', 'error': str(exc)}, allow_nan=False))
        return 2
    print(output)
    return 0


if __name__ == '__main__':
    sys.exit(main())
