"""Offline synthetic particle-size arithmetic, refusal and hostile-input checks."""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from codex_science import particle_size_distribution_pack as pack

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'examples/workflow-particle-size-distribution'
CALL_TIMEOUT = float(os.environ.get('OMS_TEST_CALL_TIMEOUT', '30'))
CASES = json.loads((EXAMPLE / 'negative-cases.json').read_text())['cases']


class PSDPackTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'parent' / 'bundle'
        self.root.mkdir(parents=True)
        for name in ('pack.json', 'rules.json', 'table.json', 'report.json'):
            shutil.copyfile(EXAMPLE / name, self.root / name)
        self.documents = {name: json.loads((self.root / (name + '.json')).read_text())
                          for name in ('pack', 'rules', 'table', 'report')}

    def save(self):
        entry = self.documents['pack']
        for name in ('rules', 'table', 'report', 'evidence'):
            if name not in self.documents:
                continue
            if name == 'evidence':
                for record in self.documents[name]['records']:
                    source = self.root / record['source']['path']
                    record['source']['sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
            if name == 'report':
                self.documents[name]['rules_sha256'] = entry['rules']['sha256']
            target = self.root / (name + '.json')
            target.write_text(json.dumps(self.documents[name], sort_keys=True) + '\n')
            identity = {'path': target.name, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
            entry[name] = [identity] if name == 'evidence' else identity
        entry['frozen_rules_sha256'] = entry['rules']['sha256']
        (self.root / 'pack.json').write_text(json.dumps(entry, sort_keys=True) + '\n')
        return self.root / 'pack.json'

    def compute(self, edges=None):
        return pack.compute_particle_size_distribution(self.documents['table'], self.documents['rules'], edges)

    def refresh_report(self, edges=None):
        self.documents['report'].update(self.compute(edges))

    def run_case(self, case):
        for change in case['changes']:
            node = self.documents[change['target']]
            for key in change['path'][:-1]:
                node = node[key]
            node[change['path'][-1]] = change['value']
        with self.assertRaisesRegex(ValueError, '^' + case['finding'] + ':'):
            pack.validate_particle_size_distribution_pack(self.save())

    def test_fixture_hand_arithmetic(self):
        result = pack.validate_particle_size_distribution_pack(self.root / 'pack.json')
        expected = json.loads((EXAMPLE / 'expected.json').read_text())['computation']
        pack._same(expected, result['computation'], 'hand-derived fixture')
        a, b = result['computation']['samples']
        self.assertEqual([a['statistics'][key] for key in pack.METRICS[:4]], [2, 4, 6, 1])
        self.assertEqual([b['statistics'][key] for key in pack.METRICS[:3]], [1.5, 3.5, 6])
        self.assertAlmostEqual(b['statistics']['span'], 9 / 7)
        self.assertEqual(a['statistics']['mean_by_number_um'], 4)
        self.assertAlmostEqual(a['statistics']['volume_weighted_mean_um'], 41600 / 8320)
        self.assertAlmostEqual(b['statistics']['volume_weighted_mean_um'], 36800 / 7200)
        self.assertEqual(result['computation']['summary']['n'], 2)
        self.assertEqual(result['review'], 'unavailable')
        self.assertEqual(result['stages'], list(pack.STAGES))

    def test_volume_basis_hand_arithmetic(self):
        self.documents['rules']['basis'] = 'volume'
        self.documents['report']['basis'] = 'volume'
        for row in self.documents['table']['rows']:
            row.update(basis='volume', values=[.2, .6, .2])
        self.refresh_report()
        result = pack.validate_particle_size_distribution_pack(self.save())
        a = result['computation']['samples'][0]['statistics']
        self.assertEqual([a[key] for key in pack.METRICS[:3]], [2, 4, 6])
        self.assertAlmostEqual(a['volume_weighted_mean_um'], 4)
        self.assertAlmostEqual(a['mean_by_number_um'], (.2 / 4 + .6 / 16 + .2 / 36)
                               / (.2 / 8 + .6 / 64 + .2 / 216))

    def test_fraction_sum_tolerance(self):
        self.documents['rules']['basis'] = 'volume'
        for row in self.documents['table']['rows']:
            row.update(basis='volume', values=[.25, .5, .25])
        self.documents['table']['rows'][0]['values'][0] += 5e-10
        self.assertEqual(self.compute()['summary']['summarized'], 2)
        self.documents['table']['rows'][0]['values'][0] += 1e-9
        with self.assertRaisesRegex(ValueError, '^fraction-sum:'):
            self.compute()

    def test_count_and_tail_edges(self):
        row = self.documents['table']['rows'][0]
        row.update(values=[2, 6, 2], total_count=10)
        result = self.compute()
        self.assertEqual(result['measurements'][0]['reasons'], ['count-rule'])
        self.assertEqual(result['samples'][0]['statistics'], 'unavailable')
        row.update(values=[3, 6, 2], total_count=11)
        self.assertEqual(self.compute()['measurements'][0]['classification'], 'reliable')
        row.update(values=[20, 60, 20], total_count=100)
        row['above_range_fraction'] = .05
        self.assertEqual(self.compute()['measurements'][0]['reasons'], ['tail-rule'])
        row['above_range_fraction'] = .049
        self.assertEqual(self.compute()['measurements'][0]['classification'], 'reliable')
        row.update(below_range_fraction=.03, above_range_fraction=.03)
        self.assertEqual(self.compute()['measurements'][0]['classification'], 'unreliable')
        row.update(below_range_fraction=0, above_range_fraction=0)
        self.documents['rules']['tail_fraction_max'] = 0
        self.assertEqual(self.compute()['summary']['unreliable_measurements'], 4)
        row.update(values=[0, 0, 0], total_count=0)
        self.assertEqual(self.compute()['measurements'][0]['statistics'], 'unavailable')

    def test_small_tail_mass_affects_cumulative_percentiles(self):
        for row in self.documents['table']['rows']:
            row.update(below_range_fraction=.02, above_range_fraction=.02)
        statistics = self.compute()['measurements'][0]['statistics']
        self.assertAlmostEqual(statistics['D10_um'], 1 + 2 * (.1 - .02) / (.96 * .2))
        self.assertEqual(statistics['D50_um'], 4)
        self.assertAlmostEqual(statistics['D90_um'], 5 + 2 * (.9 - .788) / .192)

    def test_cumulative_bin_boundaries_and_zero_bins(self):
        for row in self.documents['table']['rows']:
            row.update(values=[10, 80, 10])
        statistics = self.compute()['measurements'][0]['statistics']
        self.assertEqual([statistics[key] for key in pack.METRICS[:3]], [3, 4, 5])
        for row in self.documents['table']['rows']:
            row.update(values=[0, 100, 0])
        statistics = self.compute()['measurements'][0]['statistics']
        self.assertEqual([statistics[key] for key in pack.METRICS[:3]], [3.2, 4, 4.8])

    def test_agreement_bounds_equal_zero_and_disagreement(self):
        for key in ('d50_relative_range_max', 'span_relative_range_max'):
            self.documents['rules'][key] = 0
        self.assertEqual(self.compute()['samples'][0]['classification'], 'summarized')
        self.documents['table']['rows'][1]['values'] = [30, 50, 20]
        result = self.compute()
        self.assertEqual(result['samples'][0]['classification'], 'unavailable')
        self.assertEqual(result['samples'][0]['included_measurement_ids'], [])
        ranges = result['samples'][0]['relative_ranges']
        self.documents['rules'].update(d50_relative_range_max=ranges['d50'], span_relative_range_max=ranges['span'])
        self.assertEqual(self.compute()['samples'][0]['classification'], 'summarized')
        for key in ('d50_relative_range_max', 'span_relative_range_max'):
            saved = self.documents['rules'][key]
            self.documents['rules'][key] = saved * .99
            self.assertEqual(self.compute()['samples'][0]['classification'], 'unavailable')
            self.documents['rules'][key] = saved

    def test_unavailable_and_fewer_than_two_replicates(self):
        row = self.documents['table']['rows'][0]
        row.update(availability='unavailable', values=None, total_count=None,
                   below_range_fraction=None, above_range_fraction=None)
        result = self.compute()
        self.assertEqual(result['samples'][0]['statistics'], 'unavailable')
        self.assertEqual(result['measurements'][0]['classification'], 'unavailable')
        self.refresh_report()
        self.assertEqual(pack.validate_particle_size_distribution_pack(self.save())['computation']['summary']['unavailable'], 1)
        row['total_count'] = 0
        with self.assertRaisesRegex(ValueError, '^unavailable-as-zero:'):
            self.compute()

    def test_post_hoc_merge_exploratory_and_invalid_merges(self):
        report = self.documents['report']
        report.update(exploratory=True, bin_edges_um=[1, 5, 7])
        self.refresh_report(report['bin_edges_um'])
        result = pack.validate_particle_size_distribution_pack(self.save())
        self.assertTrue(result['exploratory'])
        self.assertAlmostEqual(result['computation']['samples'][0]['statistics']['D50_um'], 3.5)
        for edges in ([1, 4, 7], [1, 5], [0, 3, 7], [3, 5, 7]):
            with self.subTest(edges=edges), self.assertRaisesRegex(ValueError, '^bin-merge:'):
                self.compute(edges)

    def test_integer_fields_and_numeric_types(self):
        rules = self.documents['rules']
        row = self.documents['table']['rows'][0]
        summary = self.documents['report']['summary']
        fields = [(rules, 'minimum_total_count'), (rules, 'minimum_replicates'), (row, 'total_count'),
                  *[(summary, key) for key in summary]]
        for record, key in fields:
            original = record[key]
            for value in (True, float(original), str(original), []):
                record[key] = value
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, '^invalid-record:'):
                    pack.validate_particle_size_distribution_pack(self.save())
            record[key] = original
        for value in (True, 20.0, '20', -1, float('nan'), float('inf')):
            row['values'][0] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, '^invalid-record:'):
                self.compute()
        row['values'][0] = 20
        for key in ('d50_relative_range_max', 'span_relative_range_max', 'tail_fraction_max'):
            original = rules[key]
            for value in (True, [], -1, float('nan'), float('inf')):
                rules[key] = value
                with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                    self.compute()
            rules[key] = original
        row['total_count'] = 99
        with self.assertRaisesRegex(ValueError, '^count-total:'):
            self.compute()

    def test_edge_resolution_degenerate_and_tail_invalid(self):
        pack._edges([0, pack.MIN_EDGE, pack.MAX_EDGE])
        for edges in ([], [1], [1, 1], [3, 1], [0, pack.MIN_EDGE / 2], [1, pack.MAX_EDGE * 2], [False, 1], ['1', 2]):
            with self.subTest(edges=edges), self.assertRaisesRegex(ValueError, '^(invalid-record|bin-edges):'):
                pack._edges(edges)
        row = self.documents['table']['rows'][0]
        row.update(below_range_fraction=.6, above_range_fraction=.6)
        with self.assertRaisesRegex(ValueError, '^tail-fraction:'):
            self.compute()
        with self.assertRaisesRegex(ValueError, '^degenerate-distribution:'):
            pack._quantities([1, 2], [0], 0, 0, 'count')
        with self.assertRaisesRegex(ValueError, '^percentile-range:'):
            pack._quantities([1, 2], [1], 0, .95, 'count')

    def test_identity_missing_duplicate_and_types(self):
        row = self.documents['table']['rows'][0]
        for field in ('sample_id', 'measurement_id', 'basis', 'availability'):
            original = row[field]
            row[field] = []
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                self.compute()
            row[field] = original
        row['measurement_id'] = 'a2'
        with self.assertRaisesRegex(ValueError, '^duplicate-measurement:'):
            self.compute()
        row['measurement_id'] = 'a1'
        row['sample_id'] = 'absent'
        with self.assertRaisesRegex(ValueError, '^sample-identity:'):
            self.compute()
        self.documents['table']['rows'].pop(0)
        with self.assertRaisesRegex(ValueError, '^missing-measurement:'):
            self.compute()

    def test_dimension_limits_before_work(self):
        for constant, limit in (('MAX_ROWS', 3), ('MAX_SAMPLES', 1), ('MAX_BINS', 2)):
            with patch.object(pack, constant, limit), self.assertRaisesRegex(ValueError, '^input-limit:'):
                self.compute()
        with patch.object(pack, 'MAX_RECORDS', 0), self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack._claims(self.documents['report']['claims'], {})
        with patch.object(pack, 'MAX_BINS', 3), patch.object(pack, 'MAX_ROWS', 4), patch.object(pack, 'MAX_SAMPLES', 2):
            self.assertEqual(self.compute()['summary']['n'], 2)
        with self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack._edges(list(range(pack.MAX_BINS + 2)))
        for value in ([], 0, None, {}, 'rows'):
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack._list(value, 'rows', 2)
        self.assertEqual(pack._list([1, 2], 'rows', 2), [1, 2])
        self.documents['table']['rows'] = []
        with self.assertRaisesRegex(ValueError, '^invalid-record:'):
            self.compute()

    def test_count_numeric_maximum_and_rule_upper_edges(self):
        row = self.documents['table']['rows'][0]
        row.update(values=[pack.MAX_COUNT, 0, 0], total_count=pack.MAX_COUNT)
        self.assertEqual(self.compute()['measurements'][0]['classification'], 'reliable')
        row.update(values=[pack.MAX_COUNT + 1, 0, 0], total_count=pack.MAX_COUNT + 1)
        with self.assertRaisesRegex(ValueError, '^invalid-record:'):
            self.compute()
        row.update(values=[20, 60, 20], total_count=100)
        rules = self.documents['rules']
        rules.update(d50_relative_range_max=10, span_relative_range_max=10, tail_fraction_max=.1)
        self.assertEqual(self.compute()['summary']['summarized'], 2)
        for key, value in (('d50_relative_range_max', 10.01), ('span_relative_range_max', 10.01),
                           ('tail_fraction_max', .1001), ('minimum_total_count', 0), ('minimum_replicates', 1)):
            saved = rules[key]
            rules[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, '^invalid-record:'):
                self.compute()
            rules[key] = saved
        for value in (pack.MAX_NUMBER, -pack.MAX_NUMBER):
            pack._number(value, 'generic bound', -pack.MAX_NUMBER)
        with self.assertRaisesRegex(ValueError, '^invalid-record:'):
            pack._number(2 * pack.MAX_NUMBER, 'generic excess')

    def test_read_only_concurrent_calls(self):
        from concurrent.futures import ThreadPoolExecutor
        before = {path.name: path.read_bytes() for path in self.root.iterdir()}
        with ThreadPoolExecutor(max_workers=2) as pool:
            calls = [pool.submit(pack.validate_particle_size_distribution_pack, self.root / 'pack.json')
                     for _ in range(2)]
            results = [call.result(timeout=CALL_TIMEOUT) for call in calls]
        self.assertEqual(results[0], results[1])
        self.assertEqual({path.name: path.read_bytes() for path in self.root.iterdir()}, before)

    def test_freeze_before_read_and_hashes(self):
        self.documents['pack']['frozen_before_table_read'] = False
        self.save()
        real_load = pack._Bundle.load
        def load(store, name, *args, **kwargs):
            self.assertNotEqual(name, 'table.json')
            return real_load(store, name, *args, **kwargs)
        with patch.object(pack._Bundle, 'load', load), self.assertRaisesRegex(ValueError, '^rule-freeze:'):
            pack.validate_particle_size_distribution_pack(self.root / 'pack.json')
        self.documents['pack']['frozen_before_table_read'] = True
        self.save()
        with (self.root / 'table.json').open('ab') as stream:
            stream.write(b' ')
        with self.assertRaisesRegex(ValueError, '^input-hash:'):
            pack.validate_particle_size_distribution_pack(self.root / 'pack.json')

    def test_strict_json(self):
        malformed = (b'{"x":1,"x":2}', b'{"x":{"a":1,"a":2}}', b'{"x":NaN}', b'{"x":Infinity}',
                     b'{"x":1e200}', b'{"x":' + b'9' * 5000 + b'}', b'[]', b'null', b'{', b'\xff',
                     b'{"x":' + b'[' * 1200 + b'0' + b']' * 1200 + b'}')
        for raw in malformed:
            with self.subTest(raw=raw[:30]), self.assertRaisesRegex(ValueError, '^(invalid-json|input-limit):'):
                pack._json(raw)
        with patch.object(pack, 'MAX_DEPTH', 1), self.assertRaisesRegex(ValueError, '^invalid-json:'):
            pack._json(b'{"x":{"y":[1]}}')
        with patch.object(pack, 'MAX_STRING', 3), self.assertRaisesRegex(ValueError, '^invalid-record:'):
            pack._json(b'{"x":"long"}')
        with patch.object(pack.re, 'findall', side_effect=AssertionError('match-list allocation')):
            self.assertEqual(pack._json(b'{"x":[1,2]}')[0], {'x': [1, 2]})

    def test_preparse_and_cumulative_json_budget(self):
        raw = b'{"x":[1,2]}'
        self.assertEqual(pack._json(raw, 4)[1], 4)
        for allowance in (0, 3):
            with patch.object(pack.json, 'loads', side_effect=AssertionError('parsed before budget')):
                with self.assertRaisesRegex(ValueError, '^input-limit:'):
                    pack._json(raw, allowance)
        for name in ('first.json', 'second.json'):
            (self.root / name).write_bytes(b'{"x":1}')
        with patch.object(pack, 'MAX_NODES', 3):
            store = pack._Bundle(self.root)
            try:
                store.load('first.json')
                with self.assertRaisesRegex(ValueError, '^input-limit:'):
                    store.load('second.json')
            finally:
                store.close()

    def test_bytes_budget_hardlink_and_parse_once(self):
        (self.root / 'tiny.json').write_bytes(b'{"x":1}')
        os.link(self.root / 'tiny.json', self.root / 'alias.json')
        size = (self.root / 'tiny.json').stat().st_size
        with patch.object(pack, 'MAX_BYTES', size), patch.object(pack, 'MAX_TOTAL_BYTES', size):
            store = pack._Bundle(self.root)
            try:
                with patch.object(pack, '_json', wraps=pack._json) as parse:
                    self.assertEqual(store.load('tiny.json'), store.load('alias.json'))
                    self.assertEqual(parse.call_count, 1)
                self.assertEqual(store.total_bytes, size)
                store.finish()
                (self.root / 'extra').write_bytes(b'x')
                with self.assertRaisesRegex(ValueError, '^input-limit:'):
                    store.load('extra', parse=False)
            finally:
                store.close()
        for constant in ('MAX_BYTES', 'MAX_TOTAL_BYTES'):
            with patch.object(pack, constant, size - 1):
                store = pack._Bundle(self.root)
                try:
                    with self.assertRaisesRegex(ValueError, '^(input-file|input-limit):'):
                        store.load('tiny.json')
                finally:
                    store.close()

    def test_paths_special_files_and_missing(self):
        for value in ('../table.json', '/table.json', 'a\\b', 'a/./b', 'a//b', '.', ''):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, '^(input-path|invalid-record):'):
                pack._relative(value)
        target = self.root / 'special'
        for kind in ('directory', 'fifo', 'symlink', 'missing'):
            if kind == 'directory':
                target.mkdir()
            elif kind == 'fifo':
                os.mkfifo(target)
            elif kind == 'symlink':
                target.symlink_to('table.json')
            store = pack._Bundle(self.root)
            try:
                with self.assertRaisesRegex(ValueError, '^input-file:'):
                    store.load('special')
            finally:
                store.close()
                if kind == 'directory':
                    target.rmdir()
                elif kind != 'missing':
                    target.unlink()
        (self.root / 'link').symlink_to(self.root, target_is_directory=True)
        store = pack._Bundle(self.root)
        try:
            with self.assertRaisesRegex(ValueError, '^input-file:'):
                store.load('link/table.json')
        finally:
            store.close()

    def test_file_replacement_and_growth(self):
        target = self.root / 'table.json'
        real_open, real_fstat = os.open, os.fstat
        replaced = False
        def replace(name, flags, *args, **kwargs):
            nonlocal replaced
            if name == target.name and not replaced:
                replaced = True
                raw = target.read_bytes()
                target.rename(self.root / 'old-table')
                target.write_bytes(raw)
            return real_open(name, flags, *args, **kwargs)
        with patch.object(pack.os, 'open', side_effect=replace), self.assertRaisesRegex(ValueError, '^input-file:'):
            pack.validate_particle_size_distribution_pack(self.root / 'pack.json')
        seen = 0
        def grow(descriptor):
            nonlocal seen
            if os.readlink(f'/proc/self/fd/{descriptor}') == str(target):
                seen += 1
                if seen == 2:
                    with target.open('ab') as stream:
                        stream.write(b' ')
            return real_fstat(descriptor)
        with patch.object(pack.os, 'fstat', side_effect=grow), self.assertRaisesRegex(ValueError, '^input-file:'):
            pack.validate_particle_size_distribution_pack(self.root / 'pack.json')

    def test_final_hash_and_root_recheck(self):
        real_finish = pack._Bundle.finish
        def change(store):
            with (self.root / 'table.json').open('ab') as stream:
                stream.write(b' ')
            return real_finish(store)
        with patch.object(pack._Bundle, 'finish', change), self.assertRaisesRegex(ValueError, '^input-changed:'):
            pack.validate_particle_size_distribution_pack(self.root / 'pack.json')

    def test_transient_ancestor_and_root_symlink_swaps(self):
        real_open = os.open
        for component in ('parent', 'bundle'):
            target = self.root.parent if component == 'parent' else self.root
            parked = target.with_name(component + '-parked')
            swapped = False
            def swap(name, flags, *args, **kwargs):
                nonlocal swapped
                if name == component and not swapped:
                    swapped = True
                    target.rename(parked)
                    target.symlink_to(parked, target_is_directory=True)
                return real_open(name, flags, *args, **kwargs)
            try:
                with patch.object(pack.os, 'open', side_effect=swap), self.assertRaisesRegex(ValueError, '^input-root:'):
                    pack.validate_particle_size_distribution_pack(self.root / 'pack.json')
            finally:
                if swapped:
                    target.unlink()
                    parked.rename(target)

    def test_parent_swap_preserving_bundle_inode(self):
        real_finish = pack._Bundle.finish
        parent = self.root.parent
        parked = parent.with_name('old-parent')
        def swap(store):
            parent.rename(parked)
            parent.mkdir()
            (parked / self.root.name).rename(self.root)
            return real_finish(store)
        with patch.object(pack._Bundle, 'finish', swap), self.assertRaisesRegex(ValueError, '^input-root:'):
            pack.validate_particle_size_distribution_pack(self.root / 'pack.json')

    def evidence(self, kind='computed', result='numerical-agreement', origin='internal'):
        identity = self.documents['pack']['table']
        self.documents['evidence'] = {'schema': 'psd-evidence-v1', 'fixture': 'synthetic fixture',
                                     'records': [{'id': 'E1', 'kind': kind, 'result': result, 'origin': origin,
                                                  'source': copy.deepcopy(identity)}]}
        self.documents['report']['claims'] = [{'id': 'C1', 'kind': 'descriptive', 'status': 'supported',
                                               'text': 'Synthetic fixture arithmetic matches the supplied table.',
                                               'evidence': ['E1']}]

    def test_claim_kind_and_result_not_labels(self):
        for kind, result in (('review-approval', 'observed'), ('observed', 'review-approval'),
                             ('computed', 'observed'), ('observed', 'numerical-agreement')):
            self.evidence(kind, result)
            with self.subTest(kind=kind, result=result), self.assertRaisesRegex(ValueError, '^non-evidence-support:'):
                pack.validate_particle_size_distribution_pack(self.save())

    def test_unavailable_mixed_evidence_all_statuses(self):
        for status in sorted(pack.STATUSES - {'unavailable'}):
            self.evidence('unavailable', 'unavailable')
            self.documents['evidence']['records'].append({**self.documents['evidence']['records'][0],
                                                          'id': 'E2', 'kind': 'observed', 'result': 'observed'})
            self.documents['report']['claims'][0].update(status=status, evidence=['E1', 'E2'])
            with self.subTest(status=status), self.assertRaisesRegex(ValueError, '^unavailable-evidence:'):
                pack.validate_particle_size_distribution_pack(self.save())

    def test_claim_empty_unavailable_replication_and_types(self):
        claim = self.documents['report']['claims'][0]
        claim['status'] = 'supported'
        with self.assertRaisesRegex(ValueError, '^missing-evidence:'):
            pack.validate_particle_size_distribution_pack(self.save())
        claim.update(status='unavailable', text='Supported synthetic result')
        with self.assertRaisesRegex(ValueError, '^unavailable-positive:'):
            pack.validate_particle_size_distribution_pack(self.save())
        self.evidence('observed', 'observed')
        self.documents['report']['claims'][0]['status'] = 'replicated'
        with self.assertRaisesRegex(ValueError, '^claim-replication:'):
            pack.validate_particle_size_distribution_pack(self.save())
        for field in ('status', 'kind', 'id'):
            self.documents['report']['claims'][0][field] = []
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.validate_particle_size_distribution_pack(self.save())
            self.evidence('observed', 'observed')

    def test_wording_families_and_refusal_order(self):
        words = ('causes', 'mechanism', 'therapeutic', 'clinical', 'efficacy', 'effective', 'treatment', 'cures',
                 'prevents', 'recommended', 'prescribe', 'binding', 'affinity', 'inhibition', 'activation',
                 'regulation', 'drives', 'induction', 'quality', 'stability', 'stable', 'performance', 'approved', 'certified', 'compliance', 'compliant', 'truth', 'physical validity')
        for word in words:
            self.evidence()
            self.documents['report']['claims'][0].update(kind='descriptive', text='Synthetic ' + word)
            with self.subTest(word=word), self.assertRaisesRegex(ValueError, '^claim-overreach:'):
                pack.validate_particle_size_distribution_pack(self.save())
        self.documents['report']['headline'] = 'Synthetic quality'
        self.documents['table']['rows'][0]['total_count'] = -1
        with self.assertRaisesRegex(ValueError, '^claim-overreach:'):
            pack.validate_particle_size_distribution_pack(self.save())

    def test_external_alias_path_hash_and_hardlink(self):
        for origin in ('external', 'independent', 'preregistered'):
            self.evidence('observed', 'observed', origin)
            with self.subTest(origin=origin), self.assertRaisesRegex(ValueError, '^external-alias:'):
                pack.validate_particle_size_distribution_pack(self.save())
        alias = self.root / 'aliased-source'
        os.link(self.root / 'table.json', alias)
        self.documents['evidence']['records'][0]['source']['path'] = alias.name
        with self.assertRaisesRegex(ValueError, '^external-alias:'):
            pack.validate_particle_size_distribution_pack(self.save())

    def test_near_zero_comparison_has_no_absolute_tolerance(self):
        with self.assertRaisesRegex(ValueError, '^reported-number:'):
            pack._same(2e-20, 1e-20, 'small distinct number')
        pack._same(1e-20 * (1 + 1e-10), 1e-20, 'small relative tie')

    def test_cli_success_refusal_arguments_and_help(self):
        command = [sys.executable, str(ROOT / 'scripts/validate_particle_size_distribution_pack.py')]
        for arguments in ([], ['--unknown'], [str(self.root / 'pack.json'), 'extra'], ['--output', 'x']):
            result = subprocess.run(command + arguments, capture_output=True, text=True, timeout=CALL_TIMEOUT)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, '')
            refusal = json.loads(result.stderr)
            self.assertEqual(refusal['status'], 'refused')
            self.assertTrue(refusal['finding'].startswith('invalid-arguments:'))
        help_result = subprocess.run(command + ['--help'], capture_output=True, text=True, timeout=CALL_TIMEOUT)
        self.assertEqual(help_result.returncode, 0)
        self.assertIn('usage:', help_result.stdout)
        self.assertEqual(help_result.stderr, '')
        success = subprocess.run(command + [str(self.root / 'pack.json')], capture_output=True, text=True, timeout=CALL_TIMEOUT)
        self.assertEqual(success.returncode, 0, success.stderr)
        self.assertEqual(json.loads(success.stdout)['schema'], 'psd-result-v1')
        self.documents['table']['rows'][0]['total_count'] = True
        refused = subprocess.run(command + [str(self.save())], capture_output=True, text=True, timeout=CALL_TIMEOUT)
        self.assertEqual(refused.returncode, 2)
        self.assertTrue(json.loads(refused.stderr)['finding'].startswith('invalid-record:'))



def _seeded_test(case):
    def test(self):
        self.run_case(case)
    return test


for _case in CASES:
    setattr(PSDPackTests, 'test_seed_' + _case['id'].replace('-', '_'), _seeded_test(_case))


if __name__ == '__main__':
    unittest.main()
