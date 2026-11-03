#!/usr/bin/env python3
"""Prepare Vina jobs, explicitly submit an approved job, or parse supplied output."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from codex_science.docking_adapter import parse_vina_output, prepare_cpu_docking, submit_cpu_docking


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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--work-dir', type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--parse-output', action='store_true')
    mode.add_argument('--execute', action='store_true')
    parser.add_argument('--approval', type=Path)
    parser.add_argument('--state-dir', type=Path)
    args = parser.parse_args()
    try:
        if args.parse_output:
            result = parse_vina_output(args.input.read_text())
        else:
            record = json.loads(args.input.read_text(), object_pairs_hook=_unique, parse_constant=_invalid)
            if args.execute and isinstance(record, dict) and record.get('schema') == 'cpu-docking-preparation-v1':
                result = record
            else:
                result = prepare_cpu_docking(record, args.work_dir or args.input.resolve().parent)
            if args.execute:
                if args.approval is None or args.state_dir is None:
                    raise ValueError('--execute requires --approval FILE and --state-dir DIR')
                approval = json.loads(args.approval.read_text(), object_pairs_hook=_unique, parse_constant=_invalid)
                result = submit_cpu_docking(result, args.state_dir, approval)
        print(json.dumps(result, allow_nan=False, sort_keys=True))
        return 0
    except (ValueError, KeyError, TypeError, OSError, OverflowError) as error:
        print(json.dumps({'status': 'invalid', 'error': str(error)}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
