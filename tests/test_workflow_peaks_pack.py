"""Synthetic fixture arithmetic, seeded refusals and hostile-input admission."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from codex_science import peak_replicate_qc_pack as peaks

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'examples' / 'workflow-peak-replicate-qc'
CLI = ROOT / 'scripts' / 'validate_peak_replicate_qc_pack.py'
CALL_TIMEOUT = float(os.environ.get('OMS_TEST_CALL_TIMEOUT', '30'))


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False) + '\n')


def identity(path):
    return {'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


class PeakPackTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name) / 'fixture'
        shutil.copytree(FIXTURE, self.directory)

    def validate(self):
        return peaks.validate_peak_replicate_qc_pack(self.directory / 'pack.json')

    def edit(self, target, path, value):
        file = self.directory / (target + '.json')
        document = read(file)
        owner = document
        for key in path[:-1]:
            owner = owner[key]
        owner[path[-1]] = value
        write(file, document)

    def refresh(self):
        rules = read(self.directory / 'rules.json')
        rules['blacklist'] = identity(self.directory / 'blacklist.json')
        write(self.directory / 'rules.json', rules)
        report = read(self.directory / 'report.json')
        report['rules_sha256'] = identity(self.directory / 'rules.json')['sha256']
        write(self.directory / 'report.json', report)
        evidence = read(self.directory / 'evidence.json')
        for record in evidence['records']:
            record['source'] = identity(self.directory / record['source']['path'])
        write(self.directory / 'evidence.json', evidence)
        pack = read(self.directory / 'pack.json')
        for key in ('rules', 'peaks', 'report', 'evidence'):
            pack[key] = identity(self.directory / (key + '.json'))
        pack['frozen_rules_sha256'] = pack['rules']['sha256']
        write(self.directory / 'pack.json', pack)

    def cli(self, *args):
        return subprocess.run([sys.executable, str(CLI), *map(str, args)],
                              text=True, capture_output=True, timeout=CALL_TIMEOUT)

    def test_arithmetic_and_result_schema_labels_cannot_support_positive_claims(self):
        evidence = read(self.directory / 'evidence.json')
        record = evidence['records'][0]
        source = self.directory / record['source']['path']
        source_record = read(source)
        source_record.update(kind='observed', result='observed')
        write(source, source_record)
        self.edit('report', ['claims', 0, 'status'], 'supported')
        record.update(kind='observed', result='observed')
        write(self.directory / 'evidence.json', evidence)
        self.refresh()
        self.assertEqual('arithmetic-only', self.validate()['status'])
        for field in ('kind', 'result'):
            for label in ('arithmetic-only', 'peak-qc-result-v1'):
                record.update(kind='observed', result='observed')
                record[field] = label
                write(self.directory / 'evidence.json', evidence)
                self.refresh()
                with self.subTest(field=field, label=label), self.assertRaisesRegex(ValueError, '^non-evidence-support:'):
                    self.validate()

    def test_hand_calculations_expected_and_read_only(self):
        before = {p.name: p.read_bytes() for p in self.directory.iterdir() if p.is_file()}
        result = self.validate()
        self.assertEqual(read(self.directory / 'expected.json'), result)
        computation = result['computation']
        self.assertEqual(3, computation['n_replicates'])
        self.assertEqual(2, computation['n_eligible'])
        self.assertEqual([0.5, 0.4, 0.1], [r['frip'] for r in computation['replicates']])
        self.assertEqual([1, 1, 0], [r['blacklist_peak_count'] for r in computation['replicates']])
        pair = computation['pairs'][0]
        # A covers 20 bases, B covers 20; shared lengths are 5 + 10 = 15.
        self.assertEqual(15, pair['intersection_bp'])
        self.assertEqual(25, pair['union_bp'])
        self.assertEqual(3 / 5, pair['jaccard'])
        self.assertEqual(1, pair['reciprocal_overlap_fraction'])
        self.assertEqual([['A', 'B'], ['A', 'B']], [p['replicates'] for p in computation['consensus']])
        self.assertEqual([(15, 20), (40, 50)], [(p['start'], p['end']) for p in computation['consensus']])
        self.assertEqual('unavailable', result['review'])
        self.assertEqual('arithmetic-only', result['status'])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.directory.iterdir() if p.is_file()})

    def test_empty_zero_equal_and_malformed_inputs(self):
        rules = read(self.directory / 'rules.json')
        table = read(self.directory / 'peaks.json')
        empty = copy.deepcopy(table)
        for row in empty['replicates']:
            row['peaks'] = []
            row['reads_in_peaks'] = 0
        computed = peaks.compute_peak_qc(empty, rules, read(self.directory / 'blacklist.json'))
        self.assertEqual([], computed['consensus'])
        self.assertTrue(all(p['jaccard'] == 'unavailable' for p in computed['pairs']))
        zero = copy.deepcopy(table)
        zero['replicates'][0]['total_reads'] = 0
        with self.assertRaisesRegex(ValueError, '^library-counts:'):
            peaks.compute_peak_qc(zero, rules, read(self.directory / 'blacklist.json'))
        equal = copy.deepcopy(rules)
        equal['minimum_reads'] = 100
        equal['minimum_frip'] = 0.4
        equal['minimum_replicate_overlap'] = 1
        computed = peaks.compute_peak_qc(table, equal, read(self.directory / 'blacklist.json'))
        self.assertEqual(2, computed['n_eligible'])
        for value in (True, 2.0, '2', [], None):
            with self.subTest(value=value):
                malformed = copy.deepcopy(rules)
                malformed['minimum_support'] = value
                with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                    peaks.compute_peak_qc(table, malformed, read(self.directory / 'blacklist.json'))

    def test_cli_success_refusals_and_help(self):
        good = self.cli(self.directory / 'pack.json')
        self.assertEqual(0, good.returncode, good.stderr)
        self.assertEqual('arithmetic-only', json.loads(good.stdout)['status'])
        self.assertEqual('', good.stderr)
        for args in ((), ('--bad',), ('a', 'b'), (self.directory / 'missing.json',)):
            with self.subTest(args=args):
                result = self.cli(*args)
                self.assertEqual(2, result.returncode)
                self.assertEqual('', result.stdout)
                self.assertEqual('refused', json.loads(result.stderr)['status'])
                self.assertNotIn('Traceback', result.stderr)
        help_result = self.cli('--help')
        self.assertEqual(0, help_result.returncode)
        self.assertIn('usage:', help_result.stdout)
        self.assertEqual('', help_result.stderr)

    def test_overlap_qc_blacklist_sweep_and_exploration(self):
        rules = read(self.directory / 'rules.json')
        table = read(self.directory / 'peaks.json')
        blacklist = read(self.directory / 'blacklist.json')
        rules['minimum_replicate_overlap'] = 1
        rules['reciprocal_interval_fraction'] = 1
        computed = peaks.compute_peak_qc(table, rules, blacklist)
        self.assertEqual(0, computed['n_eligible'])
        self.assertEqual([], computed['consensus'])
        self.assertTrue(all('low-overlap' in row['flags'] for row in computed['replicates']))
        # One long peak overlaps two disjoint peaks, including exact half-open edges.
        first = [{'chrom': 'chrA', 'start': 0, 'end': 20}]
        second = [{'chrom': 'chrA', 'start': 0, 'end': 5}, {'chrom': 'chrA', 'start': 10, 'end': 20}]
        pair = peaks._pair(first, second, 0.5)
        self.assertEqual(15, pair['intersection_bp'])
        self.assertEqual([1, 0.5], pair['directional_fractions'])
        self.assertEqual(0.75, pair['jaccard'])
        self.assertEqual(first, peaks._clean(first, [{'chrom': 'chrA', 'start': 20, 'end': 25}]))
        self.edit('report', ['minimum_replicate_overlap'], 0)
        self.edit('report', ['exploratory'], True)
        self.refresh()
        self.assertTrue(self.validate()['exploratory'])

    def test_unavailable_is_not_empty_and_controls_can_be_optional(self):
        table = read(self.directory / 'peaks.json')
        rules = read(self.directory / 'rules.json')
        missing = table['replicates'][2]
        missing['status'] = 'unavailable'
        for field in ('total_reads', 'reads_in_peaks', 'input_control', 'peaks'):
            missing[field] = 'unavailable'
        computed = peaks.compute_peak_qc(table, rules, read(self.directory / 'blacklist.json'))
        self.assertEqual(2, computed['n_available'])
        self.assertEqual('unavailable', computed['replicates'][2]['n_peaks'])
        self.assertEqual(2, computed['n_consensus'])
        rules['input_control_required'] = False
        table['replicates'][0]['input_control'] = 'unavailable'
        peaks.compute_peak_qc(table, rules, read(self.directory / 'blacklist.json'))
        missing['status'] = 'available'
        missing['peaks'] = []
        with self.assertRaisesRegex(ValueError, '^invalid-record:'):
            peaks.compute_peak_qc(table, rules, read(self.directory / 'blacklist.json'))

    def test_numeric_types_and_malformed_key_fields(self):
        cases = [('pack', ['schema_version']), ('rules', ['schema_version']), ('rules', ['minimum_reads']),
                 ('rules', ['minimum_support']), ('rules', ['chromosomes', 'chrA']),
                 ('peaks', ['schema_version']), ('blacklist', ['schema_version']),
                 ('report', ['schema_version']), ('evidence', ['schema_version']), ('source', ['schema_version']),
                 ('peaks', ['replicates', 0, 'total_reads']), ('peaks', ['replicates', 0, 'reads_in_peaks']),
                 ('peaks', ['replicates', 0, 'input_control', 'total_reads']),
                 ('peaks', ['replicates', 0, 'peaks', 0, 'start']), ('peaks', ['replicates', 0, 'peaks', 0, 'end']),
                 ('report', ['computation', 'n_replicates']), ('report', ['computation', 'consensus', 0, 'n_support'])]
        for target, path in cases:
            for value in (True, 2.0, '2'):
                with self.subTest(target=target, path=path, value=value):
                    original = (self.directory / (target + '.json')).read_bytes()
                    self.edit(target, path, value)
                    self.refresh()
                    with self.assertRaises(ValueError):
                        self.validate()
                    (self.directory / (target + '.json')).write_bytes(original)
                    self.refresh()
        for path in (['claims', 0, 'status'], ['claims', 0, 'id'], ['claims', 0, 'kind'], ['claims', 0, 'evidence', 0]):
            with self.subTest(path=path):
                original = (self.directory / 'report.json').read_bytes()
                self.edit('report', path, [])
                self.refresh()
                with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                    self.validate()
                (self.directory / 'report.json').write_bytes(original)
                self.refresh()

    def test_json_duplicate_nonfinite_root_depth_huge_and_bounds(self):
        cases = [b'{"x":1,"x":2}', b'{"x":{"x":1,"x":2}}', b'{"x":NaN}',
                 b'{"x":Infinity}', b'[]', b'{"x":1e999}', b'{"x":' + b'9' * 500 + b'}',
                 b'{', b'\xff', b'{"x":' + b'[' * 2000 + b'0' + b']' * 2000 + b'}']
        for raw in cases:
            with self.subTest(raw=raw[:40]):
                (self.directory / 'pack.json').write_bytes(raw)
                with self.assertRaisesRegex(ValueError, '^invalid-json:'):
                    self.validate()
        with patch.object(peaks, 'MAX_DEPTH', 1):
            with self.assertRaisesRegex(ValueError, '^invalid-json:'):
                peaks._json(b'{"x":{"y":[1]}}', 100)
        for constant, equal, lower, raw in [('MAX_STRING', 4, 3, b'{"x":"abcd"}'),
                                            ('MAX_ITEMS', 2, 1, b'{"x":[1,2]}')]:
            with self.subTest(constant=constant):
                with patch.object(peaks, constant, equal):
                    peaks._json(raw, 100)
                with patch.object(peaks, constant, lower):
                    with self.assertRaisesRegex(ValueError, '^input-limit:'):
                        peaks._json(raw, 100)
        with patch.object(peaks.re, 'findall', side_effect=AssertionError('must not allocate matches')):
            peaks._json(b'{"x":[1,2]}', 4)
        with self.assertRaisesRegex(ValueError, '^input-limit:'):
            peaks._json(b'{"x":[1,2]}', 3)

    def test_aggregate_and_dimension_budgets_equal_zero_and_oversize(self):
        result = self.validate()
        names = [entry['path'] for entry in result['inputs']]
        size = sum((self.directory / name).stat().st_size for name in names)
        values = sum(1 + raw.count(b',') + sum(1 for _ in peaks.re.finditer(rb'[\[{](?=\s*[^\s\]}])', raw))
                     for raw in [(self.directory / name).read_bytes() for name in names])
        for constant, bound in [('MAX_TOTAL_BYTES', size), ('MAX_BYTES', max((self.directory / name).stat().st_size for name in names)),
                                ('MAX_TOTAL_VALUES', values), ('MAX_ARTIFACTS', len(names)),
                                ('MAX_REPLICATES', 3), ('MAX_CHROMOSOMES', 2), ('MAX_PEAKS', 9), ('MAX_RECORDS', 1)]:
            with self.subTest(constant=constant):
                with patch.object(peaks, constant, bound):
                    self.validate()
                for lower in (0, bound - 1):
                    with patch.object(peaks, constant, lower):
                        with self.assertRaisesRegex(ValueError, '^(input-limit|input-file):'):
                            self.validate()
        rules = read(self.directory / 'rules.json')
        rules['replicates'] = ['R' + str(i) for i in range(peaks.MAX_REPLICATES + 1)]
        with self.assertRaisesRegex(ValueError, '^input-limit:'):
            peaks.compute_peak_qc(read(self.directory / 'peaks.json'), rules, read(self.directory / 'blacklist.json'))

    def test_unsafe_artifact_paths_file_types_and_limits(self):
        for path in ('../rules.json', '/rules.json', 'nested/../rules.json', 'x\\rules.json', './rules.json', 'x//rules.json'):
            with self.subTest(path=path):
                self.edit('pack', ['rules', 'path'], path)
                with self.assertRaisesRegex(ValueError, '^input-path:'):
                    self.validate()
        self.refresh()
        file = self.directory / 'rules.json'
        original = file.read_bytes()
        for kind in ('symlink', 'fifo', 'directory', 'oversize'):
            with self.subTest(kind=kind):
                file.unlink()
                if kind == 'symlink':
                    file.symlink_to('peaks.json')
                elif kind == 'fifo':
                    os.mkfifo(file)
                elif kind == 'directory':
                    file.mkdir()
                else:
                    with file.open('wb') as handle:
                        handle.truncate(peaks.MAX_BYTES + 1)
                with self.assertRaisesRegex(ValueError, '^input-file:'):
                    self.validate()
                if kind == 'directory':
                    file.rmdir()
                else:
                    file.unlink()
                file.write_bytes(original)
        file.unlink()
        nested = self.directory / 'nested'
        nested.symlink_to(self.directory, target_is_directory=True)
        self.edit('pack', ['rules', 'path'], 'nested/rules.json')
        with self.assertRaisesRegex(ValueError, '^input-file:'):
            self.validate()

    def test_pinned_root_ancestor_swaps_and_recheck_chain(self):
        original_open = os.open
        original_lstat = os.lstat
        parent = self.directory.parent
        for swapped in (self.directory, parent):
            with self.subTest(swapped=swapped.name):
                moved = swapped.with_name(swapped.name + '-moved')
                fired = False
                def opened(path, flags, *args, **kwargs):
                    nonlocal fired
                    if path == swapped.name and 'dir_fd' in kwargs and not fired:
                        fired = True
                        swapped.rename(moved)
                        swapped.symlink_to(moved, target_is_directory=True)
                    return original_open(path, flags, *args, **kwargs)
                try:
                    with patch.object(peaks.os, 'open', opened):
                        with self.assertRaises(ValueError):
                            self.validate()
                    self.assertTrue(fired)
                finally:
                    if fired:
                        swapped.unlink()
                        moved.rename(swapped)
        # Replace the parent while retaining exactly the original bundle inode.
        original_compute = peaks.compute_peak_qc
        moved = parent.with_name(parent.name + '-old')
        def compute(*args, **kwargs):
            value = original_compute(*args, **kwargs)
            parent.rename(moved)
            parent.mkdir()
            (moved / self.directory.name).rename(self.directory)
            return value
        try:
            with patch.object(peaks, 'compute_peak_qc', compute):
                with self.assertRaisesRegex(ValueError, '^input-root:'):
                    self.validate()
        finally:
            if moved.exists():
                self.directory.rename(moved / self.directory.name)
                parent.rmdir()
                moved.rename(parent)
        # Swap at lstat: the previously pinned descriptor must disagree at recheck.
        moved = self.directory.with_name('saved-fixture')
        fired = False
        def inspected(path, *args, **kwargs):
            nonlocal fired
            result = original_lstat(path, *args, **kwargs)
            if path == self.directory.name and 'dir_fd' in kwargs and not fired:
                fired = True
                self.directory.rename(moved)
                self.directory.mkdir()
            return result
        try:
            with patch.object(peaks.os, 'lstat', inspected):
                with self.assertRaisesRegex(ValueError, '^input-root:'):
                    self.validate()
        finally:
            if fired:
                self.directory.rmdir()
                moved.rename(self.directory)

    def test_replacement_growing_file_hash_and_hardlink_cache(self):
        original_compute = peaks.compute_peak_qc
        def compute(*args, **kwargs):
            result = original_compute(*args, **kwargs)
            file = self.directory / 'peaks.json'
            content = file.read_bytes()
            file.unlink()
            file.write_bytes(content)
            return result
        with patch.object(peaks, 'compute_peak_qc', compute):
            with self.assertRaisesRegex(ValueError, '^input-changed:'):
                self.validate()
        self.edit('pack', ['rules', 'sha256'], '0' * 64)
        with self.assertRaisesRegex(ValueError, '^input-hash:'):
            self.validate()
        self.refresh()
        file = self.directory / 'source.json'
        os.link(file, self.directory / 'alias.json')
        store = peaks._Bundle(self.directory / 'pack.json')
        try:
            first = store.artifact(identity(file))
            count, size = store.values_read, store.bytes_read
            self.assertIs(first, store.artifact(identity(self.directory / 'alias.json')))
            self.assertEqual((count, size), (store.values_read, store.bytes_read))
            self.assertEqual(1, len(store.artifacts))
            store.recheck()
        finally:
            store.close()
        original_fdopen = os.fdopen
        fired = False
        def opened(descriptor, *args, **kwargs):
            nonlocal fired
            handle = original_fdopen(descriptor, *args, **kwargs)
            original_read = handle.read
            def growing(*args, **kwargs):
                nonlocal fired
                raw = original_read(*args, **kwargs)
                if not fired:
                    fired = True
                    with (self.directory / 'pack.json').open('ab') as writer:
                        writer.write(b' ')
                return raw
            handle.read = growing
            return handle
        with patch.object(peaks.os, 'fdopen', opened):
            with self.assertRaisesRegex(ValueError, '^input-changed:'):
                self.validate()

    def test_claim_wording_statuses_unavailable_mixed_and_aliases(self):
        report_original = (self.directory / 'report.json').read_bytes()
        for word in ('causation', 'mechanism', 'therapy', 'clinical', 'efficacy', 'effective', 'treatment', 'cure',
                     'prevention', 'recommended', 'prescribed', 'binding', 'affinity', 'inhibition', 'activation',
                     'regulation', 'drives', 'induced', 'enhancer', 'promoter'):
            with self.subTest(word=word):
                self.edit('report', ['claims', 0, 'text'], 'Synthetic fixture ' + word + '.')
                self.refresh()
                with self.assertRaisesRegex(ValueError, '^claim-overreach:'):
                    self.validate()
        (self.directory / 'report.json').write_bytes(report_original)
        self.refresh()
        for status in peaks.STATUSES - {'unavailable'}:
            with self.subTest(status=status):
                self.edit('report', ['claims', 0, 'status'], status)
                self.edit('evidence', ['records', 0, 'result'], 'unavailable')
                self.refresh()
                with self.assertRaisesRegex(ValueError, '^unavailable-evidence:'):
                    self.validate()
        self.edit('report', ['claims', 0, 'status'], 'unavailable')
        self.refresh()
        self.validate()
        self.edit('report', ['claims', 0, 'evidence'], [])
        self.refresh()
        self.validate()

    def test_concurrent_calls_and_single_admission_read(self):
        from collections import Counter
        from concurrent.futures import ThreadPoolExecutor
        before = {p.name: p.read_bytes() for p in self.directory.iterdir() if p.is_file()}
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self.cli(self.directory / 'pack.json'), range(2)))
        for result in results:
            self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(results[0].stdout, results[1].stdout)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.directory.iterdir() if p.is_file()})
        reads = Counter()
        original_fdopen = os.fdopen
        def opened(descriptor, *args, **kwargs):
            handle = original_fdopen(descriptor, *args, **kwargs)
            info = os.fstat(handle.fileno())
            key = info.st_dev, info.st_ino
            original_read = handle.read
            def counted(*args, **kwargs):
                reads[key] += 1
                return original_read(*args, **kwargs)
            handle.read = counted
            return handle
        with patch.object(peaks.os, 'fdopen', opened):
            result = self.validate()
        self.assertEqual(len(result['inputs']), len(reads))
        self.assertEqual({2}, set(reads.values()))

    def test_file_open_swap_and_source_alias_by_hash(self):
        original_open = os.open
        fired = False
        def opened(path, flags, *args, **kwargs):
            nonlocal fired
            if path == 'rules.json' and 'dir_fd' in kwargs and not fired:
                fired = True
                file = self.directory / 'rules.json'
                content = file.read_bytes()
                file.unlink()
                file.write_bytes(content)
            return original_open(path, flags, *args, **kwargs)
        with patch.object(peaks.os, 'open', opened):
            with self.assertRaisesRegex(ValueError, '^input-file:'):
                self.validate()
        self.assertTrue(fired)
        self.refresh()
        copied = self.directory / 'copied.json'
        copied.write_bytes((self.directory / 'report.json').read_bytes())
        evidence = read(self.directory / 'evidence.json')
        evidence['records'][0]['origin'] = 'external'
        evidence['records'][0]['source'] = identity(copied)
        write(self.directory / 'evidence.json', evidence)
        self.refresh()
        with self.assertRaisesRegex(ValueError, '^external-alias:'):
            self.validate()

    def test_control_failures_and_scalar_edges(self):
        table = read(self.directory / 'peaks.json')
        rules = read(self.directory / 'rules.json')
        blacklist = read(self.directory / 'blacklist.json')
        rules['minimum_frip'] = 0
        rules['minimum_replicate_overlap'] = 0
        rules['reciprocal_interval_fraction'] = 0
        table['replicates'][0]['peaks'][0]['score'] = 0
        self.assertEqual(2, peaks.compute_peak_qc(table, rules, blacklist)['n_eligible'])
        touching = peaks._pair([{'chrom': 'chrA', 'start': 0, 'end': 5}],
                               [{'chrom': 'chrA', 'start': 5, 'end': 10}], 0)
        self.assertEqual(0, touching['reciprocal_overlap_fraction'])
        self.assertEqual(0, touching['jaccard'])
        for key in ('minimum_frip', 'minimum_replicate_overlap', 'reciprocal_interval_fraction'):
            for value in (-0.01, 1.01, True, [], '1'):
                with self.subTest(key=key, value=value):
                    bad = copy.deepcopy(rules)
                    bad[key] = value
                    with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                        peaks.compute_peak_qc(table, bad, blacklist)
        for value in (-1, float('inf'), float('nan'), True, '1'):
            with self.subTest(score=value):
                bad = copy.deepcopy(table)
                bad['replicates'][0]['peaks'][0]['score'] = value
                with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                    peaks.compute_peak_qc(bad, rules, blacklist)
        bad = copy.deepcopy(table)
        bad['replicates'][0]['reads_in_peaks'] = 101
        with self.assertRaisesRegex(ValueError, '^library-counts:'):
            peaks.compute_peak_qc(bad, rules, blacklist)
        bad = copy.deepcopy(table)
        bad['replicates'][0]['peaks'] = []
        with self.assertRaisesRegex(ValueError, '^library-counts:'):
            peaks.compute_peak_qc(bad, rules, blacklist)
        for control in ([], {'id': 'synthetic', 'genome_build': 'synthetic-v1', 'total_reads': 0}):
            bad = copy.deepcopy(table)
            bad['replicates'][0]['input_control'] = control
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                peaks.compute_peak_qc(bad, rules, blacklist)
        bad = copy.deepcopy(rules)
        bad['peak_merge_rule'] = 'unknown'
        with self.assertRaisesRegex(ValueError, '^merge-rule:'):
            peaks.compute_peak_qc(table, bad, blacklist)
        bad = copy.deepcopy(rules)
        bad['replicates'] = ['A']
        with self.assertRaisesRegex(ValueError, '^insufficient-replicates:'):
            peaks.compute_peak_qc(table, bad, blacklist)
        for replicates in ([], table['replicates'][:1], [table['replicates'][0]] * 3):
            bad = copy.deepcopy(table)
            bad['replicates'] = replicates
            with self.assertRaises(ValueError):
                peaks.compute_peak_qc(bad, rules, blacklist)
        for constant, good, bad in [('MAX_INTEGER', 200, 199), ('MAX_NUMBER', 200, 199)]:
            with self.subTest(constant=constant):
                with patch.object(peaks, constant, good):
                    peaks.compute_peak_qc(table, rules, blacklist)
                with patch.object(peaks, constant, bad):
                    with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                        peaks.compute_peak_qc(table, rules, blacklist)

    def test_mixed_unavailable_citations_and_all_positive_statuses(self):
        evidence = read(self.directory / 'evidence.json')
        unavailable = copy.deepcopy(evidence['records'][0])
        unavailable['id'] = 'E-missing'
        unavailable['result'] = 'unavailable'
        evidence['records'].append(unavailable)
        write(self.directory / 'evidence.json', evidence)
        self.edit('report', ['claims', 0, 'evidence'], ['E-computed', 'E-missing'])
        self.refresh()
        with self.assertRaisesRegex(ValueError, '^unavailable-evidence:'):
            self.validate()
        self.edit('report', ['claims', 0, 'status'], 'unavailable')
        self.refresh()
        self.validate()
        self.edit('report', ['claims', 0, 'evidence'], ['E-computed'])
        for status in peaks.POSITIVE:
            with self.subTest(status=status):
                self.edit('report', ['claims', 0, 'status'], status)
                self.refresh()
                with self.assertRaisesRegex(ValueError, '^non-evidence-support:'):
                    self.validate()


def _negative_case(case):
    def test(self):
        for change in case['changes']:
            self.edit(change['target'], change['path'], change['value'])
        self.refresh()
        with self.assertRaisesRegex(ValueError, '^' + case['code'] + ':'):
            self.validate()
    return test


# Separate names let a mutation exercise exactly one seeded refusal.
for _case in read(FIXTURE / 'negative-cases.json')['cases']:
    setattr(PeakPackTests, 'test_refuses_' + _case['id'].replace('-', '_'), _negative_case(_case))
