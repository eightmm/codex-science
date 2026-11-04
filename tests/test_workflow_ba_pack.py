"""Offline synthetic Bland–Altman arithmetic, seeded refusals and hostile-file checks."""
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

from codex_science import bland_altman_agreement_pack as pack

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'examples/workflow-bland-altman-agreement'
CALL_TIMEOUT = float(os.environ.get('OMS_TEST_CALL_TIMEOUT', '30'))
CASES = json.loads((EXAMPLE / 'negative-cases.json').read_text())['cases']


class BlandAltmanPackTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'parent' / 'bundle'
        self.root.mkdir(parents=True)
        self.load_base('')

    def load_base(self, prefix):
        self.documents = {}
        for name in ('pack', 'rules', 'pairs', 'report'):
            self.documents[name] = json.loads((EXAMPLE / (prefix + name + '.json')).read_text())
        return self.save()

    def save(self):
        entry = self.documents['pack']
        for name in ('rules', 'pairs', 'report', 'evidence'):
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

    def refresh_report(self):
        report = self.documents['report']
        report.update(pack.compute_agreement(self.documents['pairs'], self.documents['rules'],
                                             report['maximum_allowed_difference']))

    def run_case(self, case):
        self.load_base(case['base'])
        node = self.documents[case['target']]
        for key in case['path'][:-1]:
            node = node[int(key)] if type(node) is list else node[key]
        key = int(case['path'][-1]) if type(node) is list else case['path'][-1]
        if case['remove']:
            del node[key]
        else:
            node[key] = case['value']
        with self.assertRaisesRegex(ValueError, '^' + case['finding'] + ':'):
            pack.validate_bland_altman_agreement_pack(self.save())

    def assertRelative(self, actual, expected):
        self.assertTrue(math.isclose(actual, expected, rel_tol=1e-9, abs_tol=0), (actual, expected))

    def test_fixture_hand_arithmetic_and_missingness(self):
        result = pack.validate_bland_altman_agreement_pack(EXAMPLE / 'pack.json')
        s = result['computation']['summary']
        self.assertEqual(s['n'], 6)
        self.assertEqual(s['unavailable'], 1)
        self.assertRelative(s['bias'], 2)
        self.assertRelative(s['sd_difference'], math.sqrt(2))
        self.assertRelative(s['lower_limit'], 2 - 1.96 * math.sqrt(2))
        self.assertRelative(s['upper_limit'], 2 + 1.96 * math.sqrt(2))
        self.assertEqual(s['intervals'], 'unavailable')
        self.assertEqual(s['proportional_bias']['screen'], 'detected')
        self.assertRelative(s['proportional_bias']['slope'], 13 / 175)
        self.assertRelative(s['proportional_bias']['t'], math.sqrt(338 / 3))
        z = math.sqrt(169 / 175)
        self.assertRelative(s['proportional_bias']['p_value'], 1 - 1.5 * z + .5 * z ** 3)
        self.assertRelative(s['normality']['excess_kurtosis'], -19 / 12)
        self.assertEqual(result['computation']['units'][-1]['difference'], 'unavailable')
        self.assertEqual(result['review'], 'unavailable')
        self.assertEqual(result['stages'], list(pack.STAGES))
        pack._same(result['computation'], json.loads((EXAMPLE / 'expected.json').read_text())['computation'], 'expected')

    def test_thirty_pairs_intervals_by_hand(self):
        self.load_base('interval-')
        result = pack.validate_bland_altman_agreement_pack(self.save())['computation']['summary']
        self.assertEqual(result['n'], 30)
        pack._same(result, json.loads((EXAMPLE / 'interval-expected.json').read_text())['computation']['summary'], 'expected')
        sd = math.sqrt(50 / 29)
        critical = 2.045229642132703
        self.assertRelative(result['sd_difference'], sd)
        intervals = result['intervals']
        self.assertEqual(intervals['degrees_of_freedom'], 29)
        self.assertRelative(intervals['bias']['lower'], 2 - critical * sd / math.sqrt(30))
        for key, point in (('lower_limit', 2 - 1.96 * sd), ('upper_limit', 2 + 1.96 * sd)):
            self.assertRelative(intervals[key]['lower'], point - critical * sd * math.sqrt(3 / 30))
            self.assertRelative(intervals[key]['upper'], point + critical * sd * math.sqrt(3 / 30))
        for key in ('bias', 'lower_limit', 'upper_limit'):
            self.load_base('interval-')
            del self.documents['report']['summary']['intervals'][key]
            with self.assertRaisesRegex(ValueError, '^agreement-interval:'):
                pack.validate_bland_altman_agreement_pack(self.save())

    def test_log_scale_and_original_scale_cannot_mix(self):
        self.load_base('log-')
        result = pack.validate_bland_altman_agreement_pack(self.save())['computation']['summary']
        self.assertRelative(result['bias'], .2)
        pack._same(result, json.loads((EXAMPLE / 'log-expected.json').read_text())['computation']['summary'], 'expected')
        self.assertRelative(result['sd_difference'], math.sqrt(2) / 10)
        self.documents['report']['summary']['bias'] = 2
        with self.assertRaisesRegex(ValueError, '^reported-number:'):
            pack.validate_bland_altman_agreement_pack(self.save())
        for bad in (0, -1):
            self.documents['pairs']['rows'][0]['method_a'] = [bad]
            with self.assertRaisesRegex(ValueError, '^difference-scale:'):
                pack.compute_agreement(self.documents['pairs'], self.documents['rules'])

    def test_exact_t_closed_form_and_convergence(self):
        for t in (0, .1, 1, 10):
            self.assertRelative(pack.student_t_pvalue(t, 1), 1 - 2 * math.atan(t) / math.pi)
            self.assertRelative(pack.student_t_pvalue(-t, 2), 1 - t / math.sqrt(t * t + 2))
        self.assertRelative(pack._t_critical(29, .95), 2.045229642132703)
        for constant in ('MAX_ITERATIONS', 'QUANTILE_STEPS'):
            with patch.object(pack, constant, 0), self.assertRaisesRegex(ValueError, '^t-convergence:'):
                pack._t_critical(29, .95)
        for t in (True, '1', [], float('nan'), float('inf')):
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.student_t_pvalue(t, 3)
        for df in (0, True, 3.0, '3', [], pack.MAX_UNITS + 1):
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.student_t_pvalue(1, df)
        self.assertGreater(pack.student_t_pvalue(1, pack.MAX_UNITS), 0)
        with self.assertRaisesRegex(ValueError, '^degenerate-numeric:'):
            pack.student_t_pvalue(1e100, pack.MAX_UNITS)

    def test_replicate_collapse_counts_units(self):
        rules = self.documents['rules']
        rules['replicate_rule'] = 'mean-per-method-before-transform'
        for row in self.documents['pairs']['rows']:
            for key in ('method_a', 'method_b'):
                if row[key] is not None:
                    v = row[key][0]
                    row[key] = [v - .5, v + .5]
        self.refresh_report()
        result = pack.validate_bland_altman_agreement_pack(self.save())['computation']
        self.assertEqual(result['summary']['n'], 6)
        self.assertEqual(result['units'][0]['replicate_count'], 2)
        self.documents['pairs']['rows'][0]['method_a'].append(10)
        with self.assertRaisesRegex(ValueError, '^repeated-measures:'):
            pack.compute_agreement(self.documents['pairs'], rules)
        self.load_base('')
        self.documents['pairs']['rows'][1]['unit_id'] = 'u01'
        with self.assertRaisesRegex(ValueError, '^repeated-measures:'):
            pack.compute_agreement(self.documents['pairs'], self.documents['rules'])

    def test_degenerate_and_minimum_pairs(self):
        original = copy.deepcopy(self.documents['pairs'])
        for mode in ('zero', 'constant', 'constant-means', 'perfect-regression', 'relative'):
            self.documents['pairs'] = copy.deepcopy(original)
            for i, row in enumerate(self.documents['pairs']['rows'][:-1]):
                m = 10 * (i + 1)
                d = (0, 1, 2, 2, 3, 4)[i]
                if mode == 'zero':
                    d = 0
                elif mode == 'constant':
                    d = 2
                elif mode == 'constant-means':
                    m = 10
                elif mode == 'perfect-regression':
                    d = i
                else:
                    d = 2 + i * 1e-14
                row.update(method_a=[m + d / 2], method_b=[m - d / 2])
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, '^degenerate-numeric:'):
                pack.compute_agreement(self.documents['pairs'], self.documents['rules'])
        self.documents['pairs'] = original
        self.documents['rules']['minimum_pairs'] = 6
        self.assertEqual(pack.compute_agreement(original, self.documents['rules'])['summary']['n'], 6)
        self.documents['rules']['minimum_pairs'] = 7
        with self.assertRaisesRegex(ValueError, '^insufficient-pairs:'):
            pack.compute_agreement(original, self.documents['rules'])
        for row in original['rows']:
            row['method_a'] = None
        with self.assertRaisesRegex(ValueError, '^insufficient-pairs:'):
            pack.compute_agreement(original, self.documents['rules'])

    def test_reported_bound_cannot_drift_within_report_tolerance(self):
        self.documents['report']['maximum_allowed_difference'] = 6 * (1 + 5e-9)
        with self.assertRaisesRegex(ValueError, '^post-hoc-bound:'):
            pack.validate_bland_altman_agreement_pack(self.save())

    def test_normality_screen_and_bound_edges(self):
        result = pack.compute_agreement(self.documents['pairs'], self.documents['rules'])['summary']
        self.documents['rules']['normality_max_abs_skewness'] = abs(result['normality']['skewness'])
        self.documents['rules']['normality_max_abs_excess_kurtosis'] = abs(result['normality']['excess_kurtosis'])
        pack.compute_agreement(self.documents['pairs'], self.documents['rules'])
        self.documents['rules']['normality_max_abs_excess_kurtosis'] = 0
        with self.assertRaisesRegex(ValueError, '^normality-screen:'):
            pack.compute_agreement(self.documents['pairs'], self.documents['rules'])
        self.documents['rules']['normality_max_abs_excess_kurtosis'] = 19 / 12
        pack.compute_agreement(self.documents['pairs'], self.documents['rules'])
        self.load_base('')
        edge = result['upper_limit']
        self.assertTrue(pack.compute_agreement(self.documents['pairs'], self.documents['rules'], edge * (1 - 1e-13))['summary']['limits_within_bound'])
        pack._same(1.0 * (1 + 5e-9), 1.0, 'documented relative tolerance')
        self.assertTrue(pack.compute_agreement(self.documents['pairs'], self.documents['rules'], edge)['summary']['limits_within_bound'])
        self.assertFalse(pack.compute_agreement(self.documents['pairs'], self.documents['rules'], edge * (1 - 1e-6))['summary']['limits_within_bound'])
        self.documents['report'].update(exploratory=True, maximum_allowed_difference=7)
        self.refresh_report()
        self.assertTrue(pack.validate_bland_altman_agreement_pack(self.save())['exploratory'])

    def test_integer_numeric_types_missingness_and_units(self):
        fields = [(self.documents['rules'], 'minimum_pairs'), (self.documents['rules'], 'interval_minimum_pairs'),
                  (self.documents['report']['summary'], 'n'), (self.documents['report']['summary'], 'unavailable'),
                  (self.documents['report']['units'][0], 'replicate_count'),
                  (self.documents['report']['summary']['proportional_bias'], 'degrees_of_freedom')]
        for row, key in fields:
            old = row[key]
            for bad in (True, float(old), str(old), []):
                row[key] = bad
                with self.subTest(key=key, bad=bad), self.assertRaisesRegex(ValueError, '^invalid-record:'):
                    pack.validate_bland_altman_agreement_pack(self.save())
            row[key] = old
        for bad in (True, '1', [], float('nan'), float('inf')):
            self.documents['pairs']['rows'][0]['method_a'] = [bad]
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.compute_agreement(self.documents['pairs'], self.documents['rules'])
        self.load_base('interval-')
        self.documents['report']['summary']['intervals']['degrees_of_freedom'] = 29.0
        with self.assertRaisesRegex(ValueError, '^invalid-record:'):
            pack.validate_bland_altman_agreement_pack(self.save())
        self.load_base('')
        self.documents['pairs']['rows'][0]['units'] = 'other-unit'
        with self.assertRaisesRegex(ValueError, '^unit-mismatch:'):
            pack.validate_bland_altman_agreement_pack(self.save())
        self.documents['pairs']['rows'][0]['units'] = 'synthetic-unit'
        self.documents['report']['units'].pop()
        with self.assertRaisesRegex(ValueError, '^unit-identity:'):
            pack.validate_bland_altman_agreement_pack(self.save())

    def test_collection_limits_before_work(self):
        for constant, value in (('MAX_UNITS', 6), ('MAX_REPLICATES', 0)):
            with patch.object(pack, constant, value), self.assertRaisesRegex(ValueError, '^input-limit:'):
                pack.compute_agreement(self.documents['pairs'], self.documents['rules'])
        self.assertEqual(pack._list([1, 2], 'edge', 2), [1, 2])
        for value in ([], 0, None, {}, 'rows'):
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack._list(value, 'rows', 2)
        raw = json.dumps({'x': [0] * (pack.MAX_ROWS + 1)}).encode()
        with self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack._json(raw)
        with patch.object(pack, 'MAX_RECORDS', 0), self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack._claims([self.documents['report']['claims'][0]], {})
        with patch.object(pack, 'MAX_REPLICATES', 1):
            pack.compute_agreement(self.documents['pairs'], self.documents['rules'])
        self.documents['pairs']['rows'][0]['method_a'] = []
        with self.assertRaisesRegex(ValueError, '^invalid-record:'):
            pack.compute_agreement(self.documents['pairs'], self.documents['rules'])

    def test_strict_json(self):
        malformed = (b'{"x":1,"x":2}', b'{"x":{"a":1,"a":2}}', b'{"x":NaN}', b'{"x":Infinity}',
                     b'{"x":1e200}', b'{"x":1e400}', b'{"x":' + b'9' * 5000 + b'}', b'[]', b'null', b'{', b'\xff',
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
        for value in ('../pairs.json', '/pairs.json', 'a\\b', 'a/./b', 'a//b', '.', ''):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, '^(input-path|invalid-record):'):
                pack._relative(value)
        target = self.root / 'special'
        for kind in ('directory', 'fifo', 'symlink', 'missing'):
            if kind == 'directory':
                target.mkdir()
            elif kind == 'fifo':
                os.mkfifo(target)
            elif kind == 'symlink':
                target.symlink_to('pairs.json')
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
                store.load('link/pairs.json')
        finally:
            store.close()

    def test_file_replacement_and_growth(self):
        target = self.root / 'pairs.json'
        real_open, real_fstat = os.open, os.fstat
        replaced = False
        def replace(name, flags, *args, **kwargs):
            nonlocal replaced
            if name == target.name and not replaced:
                replaced = True
                raw = target.read_bytes()
                target.rename(self.root / 'old-pairs')
                target.write_bytes(raw)
            return real_open(name, flags, *args, **kwargs)
        with patch.object(pack.os, 'open', side_effect=replace), self.assertRaisesRegex(ValueError, '^input-file:'):
            pack.validate_bland_altman_agreement_pack(self.root / 'pack.json')
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
            pack.validate_bland_altman_agreement_pack(self.root / 'pack.json')

    def test_final_hash_and_root_recheck(self):
        real_finish = pack._Bundle.finish
        def change(store):
            with (self.root / 'pairs.json').open('ab') as stream:
                stream.write(b' ')
            return real_finish(store)
        with patch.object(pack._Bundle, 'finish', change), self.assertRaisesRegex(ValueError, '^input-changed:'):
            pack.validate_bland_altman_agreement_pack(self.root / 'pack.json')

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
                    pack.validate_bland_altman_agreement_pack(self.root / 'pack.json')
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
            pack.validate_bland_altman_agreement_pack(self.root / 'pack.json')


    def test_lstat_directory_identity_swap(self):
        real_lstat = os.lstat
        for component in ('parent', 'bundle'):
            target = self.root.parent if component == 'parent' else self.root
            parked = target.with_name(component + '-saved')
            swapped = False
            def swap(name, *args, **kwargs):
                nonlocal swapped
                info = real_lstat(name, *args, **kwargs)
                if name == component and not swapped:
                    swapped = True
                    target.rename(parked)
                    target.mkdir()
                return info
            try:
                with patch.object(pack.os, 'lstat', side_effect=swap), self.assertRaisesRegex(ValueError, '^input-root:'):
                    pack.validate_bland_altman_agreement_pack(self.root / 'pack.json')
            finally:
                if swapped:
                    target.rmdir()
                    parked.rename(target)

    def test_freeze_precedes_opening_values_and_hash_identity(self):
        self.documents['pack']['frozen_before_values_read'] = False
        path = self.save()
        real_load = pack._Bundle.load
        def guarded(store, name, *args, **kwargs):
            if name == 'pairs.json':
                raise AssertionError('values read before rule freeze')
            return real_load(store, name, *args, **kwargs)
        with patch.object(pack._Bundle, 'load', guarded), self.assertRaisesRegex(ValueError, '^rule-freeze:'):
            pack.validate_bland_altman_agreement_pack(path)
        self.documents['pack']['frozen_before_values_read'] = True
        path = self.save()
        root = json.loads(path.read_text())
        root['pairs']['sha256'] = '0' * 64
        path.write_text(json.dumps(root))
        with self.assertRaisesRegex(ValueError, '^input-hash:'):
            pack.validate_bland_altman_agreement_pack(path)

    def test_limits_equal_zero_empty_and_malformed(self):
        rules = self.documents['rules']
        for key in ('unit_ids',):
            old = rules[key]
            for bad in ([], 0, {}, None):
                rules[key] = bad
                with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                    pack.compute_agreement(self.documents['pairs'], rules)
            rules[key] = old
        for key, good in (('minimum_pairs', 3), ('interval_minimum_pairs', 30), ('loa_multiplier', 1.96),
                          ('interval_level', .5), ('proportional_bias_alpha', .001),
                          ('normality_max_abs_skewness', 1), ('normality_max_abs_excess_kurtosis', 2),
                          ('maximum_allowed_difference', 1e-100)):
            old = rules[key]
            rules[key] = good
            pack.compute_agreement(self.documents['pairs'], rules)
            for bad in ([], True, 'value', -1):
                rules[key] = bad
                with self.subTest(key=key, bad=bad), self.assertRaisesRegex(ValueError, '^invalid-record:'):
                    pack.compute_agreement(self.documents['pairs'], rules)
            rules[key] = old
        with patch.object(pack, 'MAX_UNITS', 7):
            pack.compute_agreement(self.documents['pairs'], rules)
        for constant in ('MAX_UNITS', 'MAX_ROWS', 'MAX_STRING'):
            with patch.object(pack, constant, 0), self.assertRaisesRegex(ValueError, '^(input-limit|invalid-record):'):
                pack.compute_agreement(self.documents['pairs'], rules) if constant == 'MAX_UNITS' else pack._json(b'{"x":1}')
        with patch.object(pack, 'MAX_ROWS', 1):
            self.assertEqual(pack._json(b'{"x":1}')[0], {'x': 1})
        with patch.object(pack, 'MAX_STRING', 1):
            self.assertEqual(pack._json(b'{"x":"a"}')[0], {'x': 'a'})
        with patch.object(pack, 'MAX_DEPTH', 0):
            self.assertEqual(pack._json(b'{}')[0], {})
            with self.assertRaisesRegex(ValueError, '^invalid-json:'):
                pack._json(b'{"x":1}')
        self.assertEqual(pack._number(pack.MAX_NUMBER, 'edge'), pack.MAX_NUMBER)
        with self.assertRaisesRegex(ValueError, '^invalid-record:'):
            pack._number(pack.MAX_NUMBER * 2, 'overflow')

    def test_no_detection_and_unit_order_without_extra_pairs(self):
        ds = (0, 3, 3, 3, 3, 0)
        for i, row in enumerate(self.documents['pairs']['rows'][:-1]):
            m, d = 10 * (i + 1), ds[i]
            row.update(method_a=[m + d / 2], method_b=[m - d / 2])
        result = pack.compute_agreement(self.documents['pairs'], self.documents['rules'])['summary']
        self.assertEqual(result['proportional_bias']['screen'], 'not-detected')
        self.assertRelative(result['proportional_bias']['p_value'], 1)
        self.documents['pairs']['rows'].reverse()
        self.refresh_report()
        self.assertEqual(pack.validate_bland_altman_agreement_pack(self.save())['computation']['units'][0]['status'],
                         'unavailable')

    def evidence(self, kind='computed', result='numerical-agreement', origin='internal'):
        identity = self.documents['pack']['pairs']
        self.documents['evidence'] = {'schema': 'ba-evidence-v1', 'fixture': 'synthetic fixture',
                                     'records': [{'id': 'E1', 'kind': kind, 'result': result, 'origin': origin,
                                                  'source': copy.deepcopy(identity)}]}
        self.documents['report']['claims'] = [{'id': 'C1', 'kind': 'descriptive', 'status': 'supported',
                                               'text': 'Synthetic fixture arithmetic matches the supplied table.',
                                               'evidence': ['E1']}]

    def test_claim_kind_and_result_not_labels(self):
        for kind, result in (('review-approval', 'observed'), ('observed', 'review-approval'),
                             ('computed', 'observed'), ('observed', 'numerical-agreement'),
                             ('observed', 'arithmetic-only'), ('ba-result-v1', 'observed')):
            self.evidence(kind, result)
            with self.subTest(kind=kind, result=result), self.assertRaisesRegex(ValueError, '^non-evidence-support:'):
                pack.validate_bland_altman_agreement_pack(self.save())

    def test_unavailable_mixed_evidence_all_statuses(self):
        for status in sorted(pack.STATUSES - {'unavailable'}):
            self.evidence('unavailable', 'unavailable')
            self.documents['evidence']['records'].append({**self.documents['evidence']['records'][0],
                                                          'id': 'E2', 'kind': 'observed', 'result': 'observed'})
            self.documents['report']['claims'][0].update(status=status, evidence=['E1', 'E2'])
            with self.subTest(status=status), self.assertRaisesRegex(ValueError, '^unavailable-evidence:'):
                pack.validate_bland_altman_agreement_pack(self.save())

    def test_claim_empty_unavailable_replication_and_types(self):
        claim = self.documents['report']['claims'][0]
        claim['status'] = 'supported'
        with self.assertRaisesRegex(ValueError, '^missing-evidence:'):
            pack.validate_bland_altman_agreement_pack(self.save())
        claim.update(status='unavailable', text='Supported synthetic result')
        with self.assertRaisesRegex(ValueError, '^unavailable-positive:'):
            pack.validate_bland_altman_agreement_pack(self.save())
        self.evidence('observed', 'observed')
        self.documents['report']['claims'][0]['status'] = 'replicated'
        with self.assertRaisesRegex(ValueError, '^claim-replication:'):
            pack.validate_bland_altman_agreement_pack(self.save())
        for field in ('status', 'kind', 'id'):
            self.documents['report']['claims'][0][field] = []
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.validate_bland_altman_agreement_pack(self.save())
            self.evidence('observed', 'observed')

    def test_wording_families_and_refusal_order(self):
        words = ('causes', 'mechanism', 'therapeutic', 'clinical', 'efficacy', 'effective', 'treatment', 'cures',
                 'prevents', 'recommended', 'prescribe', 'binding', 'affinity', 'inhibition', 'activation',
                 'regulation', 'drives', 'induction', 'interchangeability', 'equivalence', 'method validity', 'truth', 'physical validity')
        for word in words:
            self.evidence()
            self.documents['report']['claims'][0].update(kind='descriptive', text='Synthetic ' + word)
            with self.subTest(word=word), self.assertRaisesRegex(ValueError, '^claim-overreach:'):
                pack.validate_bland_altman_agreement_pack(self.save())
        self.documents['report']['headline'] = 'Synthetic interchangeability'
        self.documents['pairs']['rows'][0]['method_a'] = -1
        with self.assertRaisesRegex(ValueError, '^claim-overreach:'):
            pack.validate_bland_altman_agreement_pack(self.save())

    def test_external_alias_path_hash_and_hardlink(self):
        for origin in ('external', 'independent', 'preregistered'):
            self.evidence('observed', 'observed', origin)
            with self.subTest(origin=origin), self.assertRaisesRegex(ValueError, '^external-alias:'):
                pack.validate_bland_altman_agreement_pack(self.save())
        alias = self.root / 'aliased-source'
        os.link(self.root / 'pairs.json', alias)
        self.documents['evidence']['records'][0]['source']['path'] = alias.name
        with self.assertRaisesRegex(ValueError, '^external-alias:'):
            pack.validate_bland_altman_agreement_pack(self.save())

    def test_near_zero_comparison_has_no_absolute_tolerance(self):
        with self.assertRaisesRegex(ValueError, '^reported-number:'):
            pack._same(2e-20, 1e-20, 'small distinct number')
        pack._same(1e-20 * (1 + 1e-10), 1e-20, 'small relative tie')
        for row in self.documents['pairs']['rows']:
            for method in ('method_a', 'method_b'):
                if row[method] is not None:
                    row[method] = [v * 1e-100 for v in row[method]]
        result = pack.compute_agreement(self.documents['pairs'], self.documents['rules'])['summary']
        self.assertRelative(result['bias'], 2e-100)
        self.assertRelative(result['sd_difference'], math.sqrt(2) * 1e-100)
        self.assertRelative(result['proportional_bias']['slope'], 13 / 175)


    def test_cli_success_refusal_arguments_and_help(self):
        command = [sys.executable, str(ROOT / 'scripts/validate_bland_altman_agreement_pack.py')]
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
        self.assertEqual(json.loads(success.stdout)['schema'], 'ba-result-v1')
        self.documents['pairs']['rows'][0]['method_a'] = True
        refused = subprocess.run(command + [str(self.save())], capture_output=True, text=True, timeout=CALL_TIMEOUT)
        self.assertEqual(refused.returncode, 2)
        self.assertTrue(json.loads(refused.stderr)['finding'].startswith('invalid-record:'))


def _seeded_test(case):
    def test(self):
        self.run_case(case)
    return test


for _case in CASES:
    setattr(BlandAltmanPackTests, 'test_seed_' + _case['id'].replace('-', '_'), _seeded_test(_case))


if __name__ == '__main__':
    unittest.main()
