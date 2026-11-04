"""Offline synthetic dissolution acceptance, refusal and hostile-file regression checks."""
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

from codex_science import dissolution_profile_f2_pack as pack

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'examples/workflow-dissolution-profile-f2'
CALL_TIMEOUT = float(os.environ.get('OMS_TEST_CALL_TIMEOUT', '30'))
CASES = json.loads((EXAMPLE / 'negative-cases.json').read_text())['cases']


class DissolutionPackTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'parent' / 'bundle'
        self.root.mkdir(parents=True)
        for name in ('pack.json', 'rules.json', 'profiles.json', 'report.json'):
            shutil.copyfile(EXAMPLE / name, self.root / name)
        self.documents = {name: json.loads((self.root / (name + '.json')).read_text())
                          for name in ('pack', 'rules', 'profiles', 'report')}

    def save(self):
        entry = self.documents['pack']
        for name in ('rules', 'profiles', 'report', 'evidence'):
            if name not in self.documents:
                continue
            if name == 'evidence':
                for record in self.documents[name]['records']:
                    record['source']['sha256'] = hashlib.sha256((self.root / record['source']['path']).read_bytes()).hexdigest()
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
        self.documents['report']['computation'] = pack.compute_dissolution(
            self.documents['profiles'], self.documents['rules'], self.documents['report']['selected_time_points'])

    def run_case(self, case):
        node = self.documents[case['target']]
        for key in case['path'][:-1]:
            node = node[key]
        node[case['path'][-1]] = copy.deepcopy(case['value'])
        if case['target'] == 'rules' and case['path'] == ['selected_time_points']:
            self.documents['report']['selected_time_points'] = case['value']
        with self.assertRaisesRegex(ValueError, '^' + case['finding'] + ':'):
            pack.validate_dissolution_profile_f2_pack(self.save())

    def test_fixture_hand_arithmetic_and_bounds(self):
        result = pack.validate_dissolution_profile_f2_pack(self.root / 'pack.json')
        expected = json.loads((EXAMPLE / 'expected.json').read_text())['computation']
        pack._same(result['computation'], expected, 'expected fixture')
        values = result['computation']
        # Reference means sum to 210; four differences of 2 sum to 8 and have MSE 4.
        self.assertTrue(math.isclose(values['f1'], 80 / 21, rel_tol=1e-12, abs_tol=0))
        self.assertTrue(math.isclose(values['f2'], 50 * math.log10(100 / math.sqrt(5)), rel_tol=1e-12, abs_tol=0))
        self.assertTrue(math.isclose(values['cv_controls'][0]['cv'], 5 * math.sqrt(12 / 11), rel_tol=1e-12, abs_tol=0))
        self.assertEqual(values['unit_counts'], {'reference': 12, 'test': 12})
        self.assertEqual(values['f2_status'], 'computed')
        self.assertEqual(result['stages'], list(pack.STAGES))
        self.assertEqual(result['review'], 'unavailable')

    def test_statuses_small_units_points_and_cv(self):
        rules, profiles = self.documents['rules'], self.documents['profiles']
        for count in (1, 11, 12):
            current = copy.deepcopy(profiles)
            for product in current['products']:
                product['units'] = product['units'][:count]
            changed = copy.deepcopy(rules)
            changed['units_per_product'] = {p: count for p in rules['product_ids']}
            result = pack.compute_dissolution(current, changed)
            self.assertEqual(result['f2_status'], 'computed' if count == 12 else 'unavailable')
            if count < 12:
                self.assertEqual(result['f2'], 'unavailable')
        for selected in ([], [5], [5, 10], [5, 10, 15]):
            result = pack.compute_dissolution(profiles, rules, selected)
            self.assertEqual(result['f2_status'], 'computed' if len(selected) == 3 else 'unavailable')
        profiles['products'][0]['units'][0]['percentages'][2] = 90
        result = pack.compute_dissolution(profiles, rules)
        self.assertEqual(result['f2_status'], 'variability-too-high')
        self.assertIsInstance(result['f2'], float)
        self.assertEqual(result['threshold_result'], 'unavailable')
        self.assertGreater(result['summary']['failed_cv_controls'], 0)
        self.refresh_report()
        self.assertEqual(pack.validate_dissolution_profile_f2_pack(self.save())['status'], 'arithmetic-only')
        self.documents['report']['headline'] = 'Synthetic similarity'
        with self.assertRaisesRegex(ValueError, '^similarity-wording:'):
            pack.validate_dissolution_profile_f2_pack(self.save())

    def test_cv_equal_limits_and_threshold_edge(self):
        rules, profiles = self.documents['rules'], self.documents['profiles']
        for product in profiles['products']:
            for i, unit in enumerate(product['units']):
                sign = -1 if i % 2 == 0 else 1
                unit['percentages'] = [0] + [25 + sign * 25 * limit / 100 * math.sqrt(11 / 12)
                                             for limit in (20, 10, 10, 10, 10)]
        result = pack.compute_dissolution(profiles, rules, [5, 10, 15])
        self.assertTrue(all(row['passed'] for row in result['cv_controls']))
        self.assertEqual(result['f1'], 0)
        self.assertTrue(math.isclose(result['f2'], 100, rel_tol=1e-12, abs_tol=0))
        for difference in (math.sqrt(99), 20):
            for product in profiles['products']:
                for unit in product['units']:
                    unit['percentages'] = [0] + [25 + (difference if product['product_id'] == 'test' else 0)] * 5
            result = pack.compute_dissolution(profiles, rules, [5, 10, 15])
            self.assertEqual(result['threshold_result'], 'at-or-above-50' if difference < 10 else 'below-50')
        for product in profiles['products']:
            for unit in product['units']:
                unit['percentages'][1] = 0
        with self.assertRaisesRegex(ValueError, '^degenerate-numerics:'):
            pack.compute_dissolution(profiles, rules)

    def test_exploratory_selection_and_late_union(self):
        self.documents['report'].update(exploratory=True, selected_time_points=[5, 10, 15])
        self.refresh_report()
        self.assertTrue(pack.validate_dissolution_profile_f2_pack(self.save())['exploratory'])
        profiles = self.documents['profiles']
        for unit in profiles['products'][1]['units']:
            unit['percentages'][2] = 86
        with self.assertRaisesRegex(ValueError, '^multiple-late-points:'):
            pack.compute_dissolution(profiles, self.documents['rules'])

    def test_unit_permutation_and_relative_scale(self):
        profiles, rules = self.documents['profiles'], self.documents['rules']
        expected = pack.compute_dissolution(profiles, rules)
        profiles['products'][1]['units'].reverse()
        actual = pack.compute_dissolution(profiles, rules)
        pack._same(actual, expected, 'unit permutation')
        for product in profiles['products']:
            for unit in product['units']:
                unit['percentages'] = [value * 1e-20 for value in unit['percentages']]
        scaled = pack.compute_dissolution(profiles, rules)
        self.assertTrue(math.isclose(scaled['f1'], expected['f1'], rel_tol=1e-12, abs_tol=0))
        self.assertEqual(scaled['f2_status'], 'computed')
        for actual, original in zip(scaled['cv_controls'], expected['cv_controls']):
            self.assertTrue(math.isclose(actual['cv'], original['cv'], rel_tol=1e-12, abs_tol=0))

    def test_numeric_types_integer_fields_and_identity(self):
        rules, profiles = self.documents['rules'], self.documents['profiles']
        for row, key in ((rules, 'minimum_time_points'), (rules, 'maximum_late_points'),
                         (rules['units_per_product'], 'reference')):
            original = row[key]
            for value in (True, float(original), str(original), [], 0):
                row[key] = value
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, '^invalid-record:'):
                    pack.compute_dissolution(profiles, rules)
            row[key] = original
        for value in (-1, 101, True, float('nan'), float('inf'), '20', None):
            profiles['products'][0]['units'][0]['percentages'][1] = value
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.compute_dissolution(profiles, rules)
        profiles['products'][0]['units'][0]['percentages'][1] = 20
        profiles['products'][0]['units'][1]['unit_id'] = profiles['products'][0]['units'][0]['unit_id']
        with self.assertRaisesRegex(ValueError, '^duplicate-unit:'):
            pack.compute_dissolution(profiles, rules)

    def test_dimension_limits_before_work(self):
        for constant, value in (('MAX_PRODUCTS', 1), ('MAX_UNITS', 11), ('MAX_TIME_POINTS', 5)):
            with patch.object(pack, constant, value), self.assertRaisesRegex(ValueError, '^(input-limit|invalid-record):'):
                pack.compute_dissolution(self.documents['profiles'], self.documents['rules'])
        changed = copy.deepcopy(self.documents['rules'])
        changed['units_per_product'] = {'reference': 1, 'test': 1}
        with patch.object(pack, 'MAX_UNITS', 11), self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack.compute_dissolution(self.documents['profiles'], changed)
        for constant in ('MAX_PRODUCTS', 'MAX_UNITS', 'MAX_TIME_POINTS', 'MAX_RECORDS'):
            bound = getattr(pack, constant)
            with patch.object(pack, constant, 2):
                self.assertEqual(pack._list([0, 0], 'equal edge', getattr(pack, constant)), [0, 0])
                for values in ([0, 0, 0],):
                    with self.assertRaisesRegex(ValueError, '^input-limit:'):
                        pack._list(values, 'excess edge', getattr(pack, constant))
            self.assertGreater(bound, 0)
        with patch.object(pack, 'MAX_RECORDS', 0), self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack._claims(self.documents['report']['claims'], {})
        raw = json.dumps({'x': [0] * (pack.MAX_ROWS + 1)}).encode()
        with self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack._json(raw)
        with patch.object(pack, 'MAX_ROWS', 2), self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack._pairs([('a', 1), ('b', 2), ('c', 3)])
        self.assertEqual(pack._list([1, 2], 'edge', 2), [1, 2])
        self.assertEqual(pack._list([], 'edge', 0, True), [])
        for value in ([], 0, None, {}, 'rows'):
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack._list(value, 'rows', 2)
        for value in (0, 100):
            self.documents['profiles']['products'][0]['units'][0]['percentages'][0] = value
            pack.compute_dissolution(self.documents['profiles'], self.documents['rules'])

    def test_report_numeric_times_and_integer_counts(self):
        pack._same({'selected_points': [1.5]}, {'selected_points': [1.5]}, 'means')
        computation = self.documents['report']['computation']
        computation['selected_time_points'] = [float(t) * (1 + 1e-10) for t in computation['selected_time_points']]
        for control in computation['cv_controls']:
            control['time_point'] = float(control['time_point'])
            control['limit'] = float(control['limit'])
        self.assertEqual(pack.validate_dissolution_profile_f2_pack(self.save())['status'], 'arithmetic-only')
        fields = [(computation['unit_counts'], 'reference'), (computation['unit_counts'], 'test')]
        fields.extend((computation['summary'], field) for field in computation['summary'])
        for record, field in fields:
            original = record[field]
            for value in (True, float(original), str(original), []):
                record[field] = value
                with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, '^invalid-record:'):
                    pack.validate_dissolution_profile_f2_pack(self.save())
            record[field] = original

    def test_strict_json(self):
        malformed = (b'{"x":1,"x":2}', b'{"x":{"a":1,"a":2}}', b'{"x":NaN}', b'{"x":Infinity}',
                     b'{"x":1e200}', b'{"x":1e999}', b'{"x":' + b'9' * 5000 + b'}', b'[]', b'null', b'{', b'\xff',
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
        for value in ('../profiles.json', '/profiles.json', 'a\\b', 'a/./b', 'a//b', '.', ''):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, '^(input-path|invalid-record):'):
                pack._relative(value)
        target = self.root / 'special'
        for kind in ('directory', 'fifo', 'symlink', 'missing'):
            if kind == 'directory':
                target.mkdir()
            elif kind == 'fifo':
                os.mkfifo(target)
            elif kind == 'symlink':
                target.symlink_to('profiles.json')
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
                store.load('link/profiles.json')
        finally:
            store.close()

    def test_file_replacement_and_growth(self):
        target = self.root / 'profiles.json'
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
            pack.validate_dissolution_profile_f2_pack(self.root / 'pack.json')
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
            pack.validate_dissolution_profile_f2_pack(self.root / 'pack.json')

    def test_final_hash_and_root_recheck(self):
        real_finish = pack._Bundle.finish
        def change(store):
            with (self.root / 'profiles.json').open('ab') as stream:
                stream.write(b' ')
            return real_finish(store)
        with patch.object(pack._Bundle, 'finish', change), self.assertRaisesRegex(ValueError, '^input-changed:'):
            pack.validate_dissolution_profile_f2_pack(self.root / 'pack.json')

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
                    pack.validate_dissolution_profile_f2_pack(self.root / 'pack.json')
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
            pack.validate_dissolution_profile_f2_pack(self.root / 'pack.json')

    def evidence(self, kind='computed', result='numerical-agreement', origin='internal'):
        identity = self.documents['pack']['profiles']
        self.documents['evidence'] = {'schema': 'dissolution-evidence-v1', 'fixture': 'synthetic fixture',
                                     'records': [{'id': 'E1', 'kind': kind, 'result': result, 'origin': origin,
                                                  'source': copy.deepcopy(identity)}]}
        self.documents['report']['claims'] = [{'id': 'C1', 'kind': 'descriptive', 'status': 'supported',
                                               'text': 'Synthetic fixture arithmetic matches the supplied table.',
                                               'evidence': ['E1']}]

    def test_claim_kind_and_result_not_labels(self):
        for kind, result in (('review-approval', 'observed'), ('observed', 'review-approval'),
                             ('computed', 'observed'), ('observed', 'numerical-agreement'),
                             ('observed', 'arithmetic-only'), ('diss-result-v1', 'observed')):
            self.evidence(kind, result)
            with self.subTest(kind=kind, result=result), self.assertRaisesRegex(ValueError, '^non-evidence-support:'):
                pack.validate_dissolution_profile_f2_pack(self.save())

    def test_unavailable_mixed_evidence_all_statuses(self):
        for status in sorted(pack.STATUSES - {'unavailable'}):
            self.evidence('unavailable', 'unavailable')
            self.documents['evidence']['records'].append({**self.documents['evidence']['records'][0],
                                                          'id': 'E2', 'kind': 'observed', 'result': 'observed'})
            self.documents['report']['claims'][0].update(status=status, evidence=['E1', 'E2'])
            with self.subTest(status=status), self.assertRaisesRegex(ValueError, '^unavailable-evidence:'):
                pack.validate_dissolution_profile_f2_pack(self.save())

    def test_claim_empty_unavailable_replication_and_types(self):
        claim = self.documents['report']['claims'][0]
        claim['status'] = 'supported'
        with self.assertRaisesRegex(ValueError, '^missing-evidence:'):
            pack.validate_dissolution_profile_f2_pack(self.save())
        claim.update(status='unavailable', text='Supported synthetic result')
        with self.assertRaisesRegex(ValueError, '^unavailable-positive:'):
            pack.validate_dissolution_profile_f2_pack(self.save())
        self.evidence('observed', 'observed')
        self.documents['report']['claims'][0]['status'] = 'replicated'
        with self.assertRaisesRegex(ValueError, '^claim-replication:'):
            pack.validate_dissolution_profile_f2_pack(self.save())
        for field in ('status', 'kind', 'id'):
            self.documents['report']['claims'][0][field] = []
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.validate_dissolution_profile_f2_pack(self.save())
            self.evidence('observed', 'observed')

    def test_wording_families_and_refusal_order(self):
        words = ('causes', 'mechanism', 'therapeutic', 'clinical', 'efficacy', 'effective', 'treatment', 'cures',
                 'prevents', 'recommended', 'prescribe', 'binding', 'affinity', 'inhibition', 'activation',
                 'regulation', 'drives', 'induction', 'bioequivalence', 'interchangeability', 'product quality', 'truth', 'physical validity')
        for word in words:
            self.evidence()
            self.documents['report']['claims'][0].update(kind='descriptive', text='Synthetic ' + word)
            with self.subTest(word=word), self.assertRaisesRegex(ValueError, '^claim-overreach:'):
                pack.validate_dissolution_profile_f2_pack(self.save())
        self.documents['report']['headline'] = 'Synthetic clinical relevance'
        self.documents['profiles']['products'][0]['units'][0]['percentages'][1] = -1
        with self.assertRaisesRegex(ValueError, '^claim-overreach:'):
            pack.validate_dissolution_profile_f2_pack(self.save())

    def test_external_alias_path_hash_and_hardlink(self):
        for origin in ('external', 'independent', 'preregistered'):
            self.evidence('observed', 'observed', origin)
            with self.subTest(origin=origin), self.assertRaisesRegex(ValueError, '^external-alias:'):
                pack.validate_dissolution_profile_f2_pack(self.save())
        alias = self.root / 'aliased-source'
        os.link(self.root / 'profiles.json', alias)
        self.documents['evidence']['records'][0]['source']['path'] = alias.name
        with self.assertRaisesRegex(ValueError, '^external-alias:'):
            pack.validate_dissolution_profile_f2_pack(self.save())

    def test_near_zero_comparison_has_no_absolute_tolerance(self):
        with self.assertRaisesRegex(ValueError, '^reported-number:'):
            pack._same(2e-20, 1e-20, 'small distinct number')
        pack._same(1e-20 * (1 + 1e-10), 1e-20, 'small relative tie')
        pack._same(1e-20 * (1 + 5e-9), 1e-20, 'documented relative tolerance')

    def test_selection_refuses_two_times_mapping_to_one_frozen_time(self):
        with self.assertRaisesRegex(ValueError, '^time-points:'):
            pack._selection([4.99999999999625, 5.00000000000375, 10], [0, 5, 10, 15])

    def test_decision_edges_use_tight_tolerance(self):
        self.assertTrue(pack._edge(85 * (1 + 1e-13), 85))
        self.assertFalse(pack._edge(85.00000001, 85))
        self.assertFalse(pack._edge(49.99999998, 50))

    def test_frozen_limit_cannot_drift_within_report_tolerance(self):
        self.documents['rules']['first_cv_limit'] = 20 * (1 + 5e-9)
        with self.assertRaisesRegex(ValueError, '^frozen-threshold:'):
            pack.compute_dissolution(self.documents['profiles'], self.documents['rules'])

    def test_frozen_echo_in_report_cannot_drift(self):
        pack._same(20 * (1 + 5e-9), 20, 'reported_value')
        with self.assertRaisesRegex(ValueError, '^reported-number:'):
            pack._same(20 * (1 + 5e-9), 20, 'limit')

    def test_cli_success_refusal_arguments_and_help(self):
        command = [sys.executable, str(ROOT / 'scripts/validate_dissolution_profile_f2_pack.py')]
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
        self.assertEqual(json.loads(success.stdout)['schema'], 'dissolution-result-v1')
        self.documents['profiles']['products'][0]['units'][0]['percentages'][1] = True
        refused = subprocess.run(command + [str(self.save())], capture_output=True, text=True, timeout=CALL_TIMEOUT)
        self.assertEqual(refused.returncode, 2)
        self.assertTrue(json.loads(refused.stderr)['finding'].startswith('invalid-record:'))


def _seeded_test(case):
    def test(self):
        self.run_case(case)
    return test


for _case in CASES:
    setattr(DissolutionPackTests, 'test_seed_' + _case['id'].replace('-', '_'), _seeded_test(_case))


if __name__ == '__main__':
    unittest.main()
