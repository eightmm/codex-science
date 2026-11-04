"""Offline synthetic CFU acceptance, refusal and hostile-file regression checks."""
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

from codex_science import cfu_plate_count_pack as pack

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'examples/workflow-cfu-plate-counts'
CALL_TIMEOUT = float(os.environ.get('OMS_TEST_CALL_TIMEOUT', '30'))
CASES = json.loads((EXAMPLE / 'negative-cases.json').read_text())['cases']


class CFUPackTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'parent' / 'bundle'
        self.root.mkdir(parents=True)
        for name in ('pack.json', 'rules.json', 'counts.json', 'report.json'):
            shutil.copyfile(EXAMPLE / name, self.root / name)
        self.documents = {name: json.loads((self.root / (name + '.json')).read_text())
                          for name in ('pack', 'rules', 'counts', 'report')}

    def save(self):
        entry = self.documents['pack']
        for name in ('rules', 'counts', 'report', 'evidence'):
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
            if name == 'evidence':
                entry[name] = [identity]
            else:
                entry[name] = identity
        entry['frozen_rules_sha256'] = entry['rules']['sha256']
        (self.root / 'pack.json').write_text(json.dumps(entry, sort_keys=True) + '\n')
        return self.root / 'pack.json'

    def refresh_report(self, ranges=None):
        self.documents['report'].update(pack.compute_cfu(self.documents['counts'], self.documents['rules'], ranges))

    def run_case(self, case):
        node = self.documents[case['target']]
        for key in case['path'][:-1]:
            node = node[key]
        if case['remove']:
            del node[case['path'][-1]]
        else:
            node[case['path'][-1]] = case['value']
        with self.assertRaisesRegex(ValueError, '^' + case['finding'] + ':'):
            pack.validate_cfu_plate_count_pack(self.save())

    def test_fixture_hand_arithmetic_and_bounds(self):
        result = pack.validate_cfu_plate_count_pack(self.root / 'pack.json')
        expected = json.loads((EXAMPLE / 'expected.json').read_text())['computation']
        self.assertEqual(result['computation'], expected)
        rows = result['computation']['samples']
        self.assertEqual(rows[0]['included_plate_ids'], ['p02', 'p03', 'p04', 'p05'])
        self.assertEqual(rows[0]['total_colonies'], 660)
        self.assertAlmostEqual(rows[0]['volume_equivalent_ml'], .0022)
        self.assertAlmostEqual(rows[0]['cfu_per_ml'], 300000)
        self.assertAlmostEqual(rows[0]['log10_cfu_per_ml'], math.log10(300000))
        self.assertAlmostEqual(rows[1]['lod_upper_cfu_per_ml'], -math.log(.05) / .0011)
        self.assertEqual(rows[2]['lower_bound_cfu_per_ml'], 3000000)
        self.assertEqual(rows[3]['cfu_per_ml'], 'unavailable')
        self.assertEqual(result['computation']['summary']['n'], 4)
        self.assertEqual(result['review'], 'unavailable')
        self.assertEqual(result['stages'], list(pack.STAGES))

    def test_exact_poisson_small_counts(self):
        for count, lower, upper in ((0, 0, 3.6888794541139363),
                                     (1, .025317807984289876, 5.571643390938898)):
            interval = pack.poisson_interval(count, 1)
            self.assertAlmostEqual(interval['lower'], lower, places=11)
            self.assertAlmostEqual(interval['upper'], upper, places=11)
        # The count-one limits solve finite Poisson tail equations independently.
        one = pack.poisson_interval(1, 1)
        self.assertAlmostEqual(math.exp(-one['lower']), .975, places=12)
        self.assertAlmostEqual(math.exp(-one['upper']) * (1 + one['upper']), .025, places=12)
        high = pack.poisson_interval(pack.MAX_COLONIES, 1)
        self.assertLess(high['lower'], pack.MAX_COLONIES)
        self.assertGreater(high['upper'], pack.MAX_COLONIES)

    def test_numeric_invalid_types_and_edges(self):
        for count in (True, 1.0, '1', -1, pack.MAX_COLONIES + 1, [], None):
            with self.subTest(count=count), self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.poisson_interval(count, 1)
        for exposure in (0, -1, True, float('nan'), float('inf'), '1'):
            with self.subTest(exposure=exposure), self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.poisson_interval(1, exposure)
        for level in (.5, .999):
            self.assertGreater(pack.poisson_interval(0, 1, level)['upper'], 0)
        for level in (0, .499, 1, True):
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.poisson_interval(1, 1, level)

    def test_convergence_limits_and_pooled_budget(self):
        for constant in ('MAX_ITERATIONS', 'QUANTILE_STEPS'):
            with patch.object(pack, constant, 0), self.assertRaisesRegex(ValueError, '^poisson-convergence:'):
                pack.poisson_interval(1, 1)
        self.documents['counts']['rows'][3]['count'] = 300
        self.documents['counts']['rows'][4]['count'] = 300
        with patch.object(pack, 'MAX_COLONIES', 1000), self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack.compute_cfu(self.documents['counts'], self.documents['rules'])

    def test_flagged_counts_and_report_integer_types(self):
        for flag in ('spreader', 'uncountable', 'unavailable'):
            self.documents['counts']['rows'][11].update(flag=flag, count=0)
            with self.subTest(flag=flag), self.assertRaisesRegex(ValueError, '^flagged-as-zero:'):
                pack.compute_cfu(self.documents['counts'], self.documents['rules'])
            self.documents['counts']['rows'][11]['count'] = None
            self.assertEqual(pack.compute_cfu(self.documents['counts'], self.documents['rules'])['samples'][3]['classification'],
                             'unavailable')
        for value in (True, 4.0, '4', []):
            self.documents['report']['summary']['n'] = value
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.validate_cfu_plate_count_pack(self.save())
        del self.documents['report']['interval_method']
        with self.assertRaisesRegex(ValueError, '^poisson-interval:'):
            pack.validate_cfu_plate_count_pack(self.save())

    def test_integer_fields_and_count_edges(self):
        fields = [(self.documents['rules'], 'minimum_countable_plates'),
                  (self.documents['rules']['plates'][0], 'minimum'),
                  (self.documents['rules']['plates'][0], 'maximum'),
                  (self.documents['counts']['rows'][0], 'count')]
        for row, key in fields:
            original = row[key]
            for value in (True, float(original), str(original), [], -1):
                row[key] = value
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, '^invalid-record:'):
                    pack.compute_cfu(self.documents['counts'], self.documents['rules'])
            row[key] = original
        for value in (30, 300):
            self.documents['counts']['rows'][1]['count'] = value
            self.documents['counts']['rows'][2]['count'] = value
            result = pack.compute_cfu(self.documents['counts'], self.documents['rules'])
            self.assertIn('p02', result['samples'][0]['included_plate_ids'])

    def test_duplicate_ratio_equal_and_minimum_equal(self):
        self.documents['counts']['rows'][2]['count'] = 150
        self.documents['rules']['minimum_countable_plates'] = 4
        self.refresh_report()
        self.assertEqual(pack.validate_cfu_plate_count_pack(self.save())['status'], 'arithmetic-only')
        self.documents['rules']['minimum_countable_plates'] = 5
        with self.assertRaisesRegex(ValueError, '^insufficient-countable:'):
            pack.compute_cfu(self.documents['counts'], self.documents['rules'])

    def test_exploratory_range_change(self):
        report = self.documents['report']
        report['exploratory'] = True
        report['countable_ranges']['p01']['maximum'] = 1100
        self.refresh_report(report['countable_ranges'])
        self.assertTrue(pack.validate_cfu_plate_count_pack(self.save())['exploratory'])

    def test_geometric_dilutions_and_identity(self):
        self.documents['rules']['plates'][0]['dilution_factor'] = .2
        self.documents['counts']['rows'][0]['dilution_factor'] = .2
        with self.assertRaisesRegex(ValueError, '^dilution-series:'):
            pack.compute_cfu(self.documents['counts'], self.documents['rules'])

    def test_duplicate_plate_identity(self):
        self.documents['counts']['rows'][2]['plate_id'] = 'p02'
        with self.assertRaisesRegex(ValueError, '^duplicate-plate:'):
            pack.compute_cfu(self.documents['counts'], self.documents['rules'])

    def test_no_countable_bracket(self):
        for index in (1, 2, 3, 4):
            self.documents['counts']['rows'][index]['count'] = 1
        with self.assertRaisesRegex(ValueError, '^no-countable-bracket:'):
            pack.compute_cfu(self.documents['counts'], self.documents['rules'])

    def test_empty_no_quantified_and_flagged_data(self):
        for row in self.documents['counts']['rows']:
            row['flag'], row['count'] = 'unavailable', None
        result = pack.compute_cfu(self.documents['counts'], self.documents['rules'])
        self.assertEqual(result['summary']['unavailable'], 4)
        self.assertEqual(result['summary']['mean_log10_cfu_per_ml'], 'unavailable')
        self.documents['counts']['rows'] = []
        with self.assertRaisesRegex(ValueError, '^invalid-record:'):
            pack.compute_cfu(self.documents['counts'], self.documents['rules'])

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

    def test_collection_limits_before_work(self):
        with patch.object(pack, 'MAX_ROWS', 2), self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack.compute_cfu(self.documents['counts'], self.documents['rules'])
        with patch.object(pack, 'MAX_SAMPLES', 3), self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack.compute_cfu(self.documents['counts'], self.documents['rules'])
        with patch.object(pack, 'MAX_RECORDS', 0), self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack._claims([self.documents['report']['claims'][0]], {})
        raw = json.dumps({'x': [0] * (pack.MAX_ROWS + 1)}).encode()
        with self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack._json(raw)
        self.assertEqual(pack._list([1, 2], 'edge', 2), [1, 2])
        for value in ([], 0, None, {}, 'rows'):
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack._list(value, 'rows', 2)

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
        for value in ('../counts.json', '/counts.json', 'a\\b', 'a/./b', 'a//b', '.', ''):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, '^(input-path|invalid-record):'):
                pack._relative(value)
        target = self.root / 'special'
        for kind in ('directory', 'fifo', 'symlink', 'missing'):
            if kind == 'directory':
                target.mkdir()
            elif kind == 'fifo':
                os.mkfifo(target)
            elif kind == 'symlink':
                target.symlink_to('counts.json')
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
                store.load('link/counts.json')
        finally:
            store.close()

    def test_file_replacement_and_growth(self):
        target = self.root / 'counts.json'
        real_open, real_fstat = os.open, os.fstat
        replaced = False
        def replace(name, flags, *args, **kwargs):
            nonlocal replaced
            if name == target.name and not replaced:
                replaced = True
                raw = target.read_bytes()
                target.rename(self.root / 'old-counts')
                target.write_bytes(raw)
            return real_open(name, flags, *args, **kwargs)
        with patch.object(pack.os, 'open', side_effect=replace), self.assertRaisesRegex(ValueError, '^input-file:'):
            pack.validate_cfu_plate_count_pack(self.root / 'pack.json')
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
            pack.validate_cfu_plate_count_pack(self.root / 'pack.json')

    def test_final_hash_and_root_recheck(self):
        real_finish = pack._Bundle.finish
        def change(store):
            with (self.root / 'counts.json').open('ab') as stream:
                stream.write(b' ')
            return real_finish(store)
        with patch.object(pack._Bundle, 'finish', change), self.assertRaisesRegex(ValueError, '^input-changed:'):
            pack.validate_cfu_plate_count_pack(self.root / 'pack.json')

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
                    pack.validate_cfu_plate_count_pack(self.root / 'pack.json')
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
            pack.validate_cfu_plate_count_pack(self.root / 'pack.json')

    def evidence(self, kind='computed', result='numerical-agreement', origin='internal'):
        identity = self.documents['pack']['counts']
        self.documents['evidence'] = {'schema': 'cfu-evidence-v1', 'fixture': 'synthetic fixture',
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
                pack.validate_cfu_plate_count_pack(self.save())

    def test_arithmetic_and_result_schema_are_non_evidence(self):
        for field in ('kind', 'result'):
            for value in ('arithmetic-only', 'cfu-result-v1'):
                with self.subTest(field=field, value=value):
                    self.evidence(**{'kind': 'observed', 'result': 'observed', field: value})
                    with self.assertRaisesRegex(ValueError, '^non-evidence-support:'):
                        pack.validate_cfu_plate_count_pack(self.save())

    def test_unavailable_mixed_evidence_all_statuses(self):
        for status in sorted(pack.STATUSES - {'unavailable'}):
            self.evidence('unavailable', 'unavailable')
            self.documents['evidence']['records'].append({**self.documents['evidence']['records'][0],
                                                          'id': 'E2', 'kind': 'observed', 'result': 'observed'})
            self.documents['report']['claims'][0].update(status=status, evidence=['E1', 'E2'])
            with self.subTest(status=status), self.assertRaisesRegex(ValueError, '^unavailable-evidence:'):
                pack.validate_cfu_plate_count_pack(self.save())

    def test_claim_empty_unavailable_replication_and_types(self):
        claim = self.documents['report']['claims'][0]
        claim['status'] = 'supported'
        with self.assertRaisesRegex(ValueError, '^missing-evidence:'):
            pack.validate_cfu_plate_count_pack(self.save())
        claim.update(status='unavailable', text='Supported synthetic result')
        with self.assertRaisesRegex(ValueError, '^unavailable-positive:'):
            pack.validate_cfu_plate_count_pack(self.save())
        self.evidence('observed', 'observed')
        self.documents['report']['claims'][0]['status'] = 'replicated'
        with self.assertRaisesRegex(ValueError, '^claim-replication:'):
            pack.validate_cfu_plate_count_pack(self.save())
        for field in ('status', 'kind', 'id'):
            self.documents['report']['claims'][0][field] = []
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.validate_cfu_plate_count_pack(self.save())
            self.evidence('observed', 'observed')

    def test_wording_families_and_refusal_order(self):
        words = ('causes', 'mechanism', 'therapeutic', 'clinical', 'efficacy', 'effective', 'treatment', 'cures',
                 'prevents', 'recommended', 'prescribe', 'binding', 'affinity', 'inhibition', 'activation',
                 'regulation', 'drives', 'induction', 'sterile', 'safe', 'potency', 'truth', 'physical validity')
        for word in words:
            self.evidence()
            self.documents['report']['claims'][0].update(kind='descriptive', text='Synthetic ' + word)
            with self.subTest(word=word), self.assertRaisesRegex(ValueError, '^claim-overreach:'):
                pack.validate_cfu_plate_count_pack(self.save())
        self.documents['report']['headline'] = 'Synthetic safety'
        self.documents['counts']['rows'][0]['count'] = -1
        with self.assertRaisesRegex(ValueError, '^claim-overreach:'):
            pack.validate_cfu_plate_count_pack(self.save())

    def test_external_alias_path_hash_and_hardlink(self):
        for origin in ('external', 'independent', 'preregistered'):
            self.evidence('observed', 'observed', origin)
            with self.subTest(origin=origin), self.assertRaisesRegex(ValueError, '^external-alias:'):
                pack.validate_cfu_plate_count_pack(self.save())
        alias = self.root / 'aliased-source'
        os.link(self.root / 'counts.json', alias)
        self.documents['evidence']['records'][0]['source']['path'] = alias.name
        with self.assertRaisesRegex(ValueError, '^external-alias:'):
            pack.validate_cfu_plate_count_pack(self.save())

    def test_near_zero_comparison_has_no_absolute_tolerance(self):
        with self.assertRaisesRegex(ValueError, '^reported-number:'):
            pack._same(2e-20, 1e-20, 'small distinct number')
        pack._same(1e-20 * (1 + 1e-10), 1e-20, 'small relative tie')

    def test_cli_success_refusal_arguments_and_help(self):
        command = [sys.executable, str(ROOT / 'scripts/validate_cfu_plate_count_pack.py')]
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
        self.assertEqual(json.loads(success.stdout)['schema'], 'cfu-result-v1')
        self.documents['counts']['rows'][0]['count'] = True
        refused = subprocess.run(command + [str(self.save())], capture_output=True, text=True, timeout=CALL_TIMEOUT)
        self.assertEqual(refused.returncode, 2)
        self.assertTrue(json.loads(refused.stderr)['finding'].startswith('invalid-record:'))


def _seeded_test(case):
    def test(self):
        self.run_case(case)
    return test


for _case in CASES:
    setattr(CFUPackTests, 'test_seed_' + _case['id'].replace('-', '_'), _seeded_test(_case))


if __name__ == '__main__':
    unittest.main()
