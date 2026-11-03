"""Synthetic WB arithmetic, seeded refusals and hostile-file regression checks."""
import copy
from concurrent.futures import ThreadPoolExecutor
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

from codex_science import western_blot_densitometry_pack as pack

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'examples/workflow-western-blot-densitometry'
CALL_TIMEOUT = float(os.environ.get('OMS_TEST_CALL_TIMEOUT', '30'))
CASES = json.loads((EXAMPLE / 'negative-cases.json').read_text())['cases']


class WBPackTests(unittest.TestCase):
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

    def refresh_report(self):
        report = self.documents['report']
        report['computation'] = pack.compute_densitometry(self.documents['table'], report['applied_rules'])

    def run_case(self, case):
        node = self.documents[case['target']]
        for key in case['path'][:-1]:
            node = node[key]
        if case['remove']:
            del node[case['path'][-1]]
        else:
            node[case['path'][-1]] = case['value']
        with self.assertRaisesRegex(ValueError, '^' + case['finding'] + ':'):
            pack.validate_western_blot_densitometry_pack(self.save())

    def test_fixture_hand_arithmetic(self):
        result = pack.validate_western_blot_densitometry_pack(self.root / 'pack.json')
        self.assertEqual(result['computation'], json.loads((EXAMPLE / 'expected.json').read_text())['computation'])
        control, contrast = result['computation']['groups']
        self.assertEqual((control['n'], contrast['n']), (3, 3))
        self.assertAlmostEqual(control['mean'], 4/3)
        self.assertAlmostEqual(control['standard_error'], 1/3)
        self.assertEqual(contrast['mean'], 4)
        self.assertAlmostEqual(contrast['standard_error'], math.sqrt(4/3))
        self.assertEqual(contrast['fold_change'], 3)
        self.assertAlmostEqual(contrast['interval']['degrees_of_freedom'], 3.92)
        self.assertAlmostEqual(contrast['interval']['lower'], 1.0301983496841778)
        self.assertAlmostEqual(contrast['interval']['upper'], 8.736181729236007)
        self.assertEqual(result['computation']['biological_units'][0]['n_lanes'], 2)
        self.assertEqual(result['computation']['lanes'][-1]['classification'], 'unreliable')
        self.assertEqual(result['review'], 'unavailable')
        self.assertEqual(result['stages'], list(pack.STAGES))
        before = {path.name: path.read_bytes() for path in self.root.iterdir()}
        with ThreadPoolExecutor(max_workers=2) as executor:
            calls = [executor.submit(pack.validate_western_blot_densitometry_pack, self.root / 'pack.json')
                     for _ in range(2)]
            self.assertTrue(all(call.result(timeout=CALL_TIMEOUT) == result for call in calls))
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.root.iterdir()})

    def test_welch_known_quantiles_and_degenerate_inputs(self):
        # For t with two degrees of freedom, CDF inversion is algebraic.
        self.assertAlmostEqual(pack._t_quantile(2, .95), math.sqrt(2*.95**2 / (1-.95**2)), places=10)
        self.assertAlmostEqual(pack._t_quantile(4, .95), 2.7764451051977987, places=10)
        for values, code in (([], 'invalid-record'), ([1, 2], 'insufficient-biological-units'),
                             ([1, 1, 1], 'degenerate-variance'), ([0.1, 0.3 - 0.2, 0.1], 'degenerate-variance'), ([0, 1, 2], 'invalid-record'),
                             ([True, 1, 2], 'invalid-record'), ([1, float('nan'), 2], 'invalid-record')):
            with self.subTest(values=values), self.assertRaisesRegex(ValueError, '^' + code + ':'):
                pack.welch_fold_interval(values, [1, 2, 3])
        for constant in ('MAX_ITERATIONS', 'QUANTILE_STEPS'):
            with patch.object(pack, constant, 0), self.assertRaisesRegex(ValueError, '^welch-convergence:'):
                pack.welch_fold_interval([1, 2, 3], [2, 3, 4])
        for level in (.5, .999):
            self.assertGreater(pack.welch_fold_interval([1, 2, 3], [2, 3, 4], level)['upper'], 0)
        for level in (0, 1, True, '0.95'):
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.welch_fold_interval([1, 2, 3], [2, 3, 4], level)

    def test_roundoff_control_spread_is_zero_cv(self):
        rows, rules = self.documents['table']['rows'], self.documents['report']['applied_rules']
        for row in rows:
            row['loading_control_intensity'] = 100
        rules['maximum_loading_control_cv'] = 0
        self.assertEqual(pack.compute_densitometry(self.documents['table'], rules)['loading_control_cv'], 0)
        self.assertEqual(pack._moments([0.1] * 6)[1], 0.0)

    def test_unreliable_excluded_and_small_groups_unavailable(self):
        for row in self.documents['table']['rows']:
            if row['lane_id'] == 'b3':
                row['target_intensity'] = 5
        self.refresh_report()
        result = pack.validate_western_blot_densitometry_pack(self.save())
        contrast = result['computation']['groups'][1]
        self.assertEqual(contrast['n'], 2)
        self.assertEqual(contrast['interval'], 'unavailable')
        self.assertEqual(contrast['mean'], 3)
        for row in self.documents['table']['rows']:
            if row['lane_id'].startswith('b'):
                for key in row:
                    if key != 'lane_id':
                        row[key] = None
        self.refresh_report()
        group = pack.validate_western_blot_densitometry_pack(self.save())['computation']['groups'][1]
        self.assertEqual(group['n'], 0)
        self.assertEqual(group['mean'], 'unavailable')
        self.assertEqual(group['fold_change'], 'unavailable')

    def test_range_saturation_cv_and_exploratory_edges(self):
        rows, rules = self.documents['table']['rows'], self.documents['report']['applied_rules']
        for value, reliable in ((10, True), (1500, True), (0, False), (2000, False)):
            rows[2]['target_intensity'] = value + 10 if value != 2000 else value
            result = pack.compute_densitometry(self.documents['table'], rules)
            self.assertEqual(result['lanes'][2]['classification'] == 'reliable', reliable)
        rows[2]['target_intensity'] = 210
        rows[2]['loading_control_intensity'] = 120
        measured = pack.compute_densitometry(self.documents['table'], rules)['loading_control_cv']
        rules['maximum_loading_control_cv'] = measured
        self.documents['report']['exploratory'] = True
        self.refresh_report()
        self.assertTrue(pack.validate_western_blot_densitometry_pack(self.save())['exploratory'])
        rules['maximum_loading_control_cv'] = measured * (1 - 1e-9)
        with self.assertRaisesRegex(ValueError, '^loading-control-cv:'):
            pack.compute_densitometry(self.documents['table'], rules)
        rows[2]['loading_control_intensity'] = 110
        rules['maximum_loading_control_cv'] = 0
        self.assertEqual(pack.compute_densitometry(self.documents['table'], rules)['loading_control_cv'], 0)
        rules['maximum_loading_control_cv'] = 1
        pack.compute_densitometry(self.documents['table'], rules)
        for value in (-1, True, '0.2', float('inf')):
            rules['maximum_loading_control_cv'] = value
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.compute_densitometry(self.documents['table'], rules)

    def test_integer_fields_identity_series_and_reference(self):
        rules = self.documents['report']['applied_rules']
        for value in (True, 3.0, '3', [], 0):
            rules['minimum_biological_units'] = value
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.compute_densitometry(self.documents['table'], rules)
        rules['minimum_biological_units'] = 3
        rules['lanes'][1]['biological_unit'] = 'invented-unit'
        with self.assertRaisesRegex(ValueError, '^technical-replicates:'):
            pack.compute_densitometry(self.documents['table'], rules)
        rules['lanes'][1]['biological_unit'] = 'A1'
        rules['antibodies'][0]['dilution_series'][1]['intensity'] = 101
        with self.assertRaisesRegex(ValueError, '^dilution-series:'):
            pack.compute_densitometry(self.documents['table'], rules)
        rules['antibodies'][0]['dilution_series'][1]['intensity'] = 100
        rules['lanes'][2].update(target_band='loading', loading_control_band='target')
        with self.assertRaisesRegex(ValueError, '^band-identity:'):
            pack.compute_densitometry(self.documents['table'], rules)
        rules['lanes'][2].update(target_band='target', loading_control_band='loading')
        self.documents['table']['rows'][0]['target_intensity'] = 2000
        with self.assertRaisesRegex(ValueError, '^reference-lane:'):
            pack.compute_densitometry(self.documents['table'], rules)

    def test_all_dimension_limits_equal_excess_empty_and_types(self):
        rules = self.documents['rules']
        for constant, count in (('MAX_GROUPS', 2), ('MAX_BLOTS', 2), ('MAX_ANTIBODIES', 2),
                                ('MAX_DILUTIONS', 3), ('MAX_UNITS', 6), ('MAX_ROWS', 8)):
            with self.subTest(constant=constant):
                with patch.object(pack, constant, count):
                    pack.compute_densitometry(self.documents['table'], rules)
                for bound in (0, count - 1):
                    code = 'invalid-record' if constant == 'MAX_UNITS' and bound == 0 else 'input-limit'
                    with patch.object(pack, constant, bound), self.assertRaisesRegex(ValueError, '^' + code + ':'):
                        pack.compute_densitometry(self.documents['table'], rules)
        for key in ('groups', 'lanes', 'antibodies'):
            original = rules[key]
            for value in ([], 0, {}, None, 'rows'):
                rules[key] = value
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, '^invalid-record:'):
                    pack.compute_densitometry(self.documents['table'], rules)
            rules[key] = original
        original = rules['antibodies'][0]['dilution_series']
        for value in ([], 0, {}, None):
            rules['antibodies'][0]['dilution_series'] = value
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.compute_densitometry(self.documents['table'], rules)
        rules['antibodies'][0]['dilution_series'] = original
        for key in ('minimum', 'maximum', 'saturation_ceiling'):
            original = rules['antibodies'][0][key]
            rules['antibodies'][0][key] = True
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.compute_densitometry(self.documents['table'], rules)
            rules['antibodies'][0][key] = original
        del rules['reference_lanes']['blot-2']
        with self.assertRaisesRegex(ValueError, '^reference-lane:'):
            pack.compute_densitometry(self.documents['table'], rules)

    def test_report_counts_types_freeze_order_hash_and_partial_missing(self):
        unit = self.documents['report']['computation']['biological_units'][0]
        for value in (True, 2.0, '2', [], -1):
            unit['n_lanes'] = value
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.validate_western_blot_densitometry_pack(self.save())
        unit['n_lanes'] = 2
        for field in ('n',):
            group = self.documents['report']['computation']['groups'][0]
            for value in (True, 3.0, '3', [], -1):
                group[field] = value
                with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                    pack.validate_western_blot_densitometry_pack(self.save())
            group[field] = 3
        self.documents['table']['rows'][2]['target_intensity'] = None
        with self.assertRaisesRegex(ValueError, '^invalid-record:'):
            pack.compute_densitometry(self.documents['table'], self.documents['rules'])
        self.documents['pack']['frozen_before_intensities_read'] = False
        real = pack._Bundle.load
        def guard(store, name, *args, **kwargs):
            self.assertNotEqual(name, 'table.json', 'intensities opened before freeze')
            return real(store, name, *args, **kwargs)
        with patch.object(pack._Bundle, 'load', guard), self.assertRaisesRegex(ValueError, '^rule-freeze:'):
            pack.validate_western_blot_densitometry_pack(self.save())
        self.documents['pack']['frozen_before_intensities_read'] = True
        entry = self.save()
        with (self.root / 'rules.json').open('ab') as stream:
            stream.write(b' ')
        with self.assertRaisesRegex(ValueError, '^input-hash:'):
            pack.validate_western_blot_densitometry_pack(entry)

    def test_root_replaced_between_lstat_and_open(self):
        real_lstat = os.lstat
        parked = self.root.with_name('parked-bundle')
        swapped = False
        def swap(name, *args, **kwargs):
            nonlocal swapped
            info = real_lstat(name, *args, **kwargs)
            if name == self.root.name and kwargs.get('dir_fd') is not None and not swapped:
                swapped = True
                self.root.rename(parked)
                self.root.mkdir()
            return info
        with patch.object(pack.os, 'lstat', side_effect=swap), self.assertRaisesRegex(ValueError, '^input-root:'):
            pack.validate_western_blot_densitometry_pack(self.root / 'pack.json')

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
            pack.compute_densitometry(self.documents['table'], self.documents['rules'])
        with patch.object(pack, 'MAX_UNITS', 5), self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack.compute_densitometry(self.documents['table'], self.documents['rules'])
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
                target.rename(self.root / 'old-counts')
                target.write_bytes(raw)
            return real_open(name, flags, *args, **kwargs)
        with patch.object(pack.os, 'open', side_effect=replace), self.assertRaisesRegex(ValueError, '^input-file:'):
            pack.validate_western_blot_densitometry_pack(self.root / 'pack.json')
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
            pack.validate_western_blot_densitometry_pack(self.root / 'pack.json')

    def test_final_hash_and_root_recheck(self):
        real_finish = pack._Bundle.finish
        def change(store):
            with (self.root / 'table.json').open('ab') as stream:
                stream.write(b' ')
            return real_finish(store)
        with patch.object(pack._Bundle, 'finish', change), self.assertRaisesRegex(ValueError, '^input-changed:'):
            pack.validate_western_blot_densitometry_pack(self.root / 'pack.json')

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
                    pack.validate_western_blot_densitometry_pack(self.root / 'pack.json')
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
            pack.validate_western_blot_densitometry_pack(self.root / 'pack.json')

    def evidence(self, kind='computed', result='numerical-agreement', origin='internal'):
        identity = self.documents['pack']['table']
        self.documents['evidence'] = {'schema': 'wb-evidence-v1', 'fixture': 'synthetic fixture',
                                     'records': [{'id': 'E1', 'kind': kind, 'result': result, 'origin': origin,
                                                  'source': copy.deepcopy(identity)}]}
        self.documents['report']['claims'] = [{'id': 'C1', 'kind': 'descriptive', 'status': 'supported',
                                               'text': 'Synthetic fixture arithmetic matches the supplied table.',
                                               'evidence': ['E1']}]

    def test_claim_kind_and_result_not_labels(self):
        for kind, result in (('review-approval', 'observed'), ('observed', 'review-approval'),
                             ('computed', 'observed'), ('observed', 'numerical-agreement'),
                             ('observed', 'arithmetic-only'), ('wb-result-v1', 'observed')):
            self.evidence(kind, result)
            with self.subTest(kind=kind, result=result), self.assertRaisesRegex(ValueError, '^non-evidence-support:'):
                pack.validate_western_blot_densitometry_pack(self.save())

    def test_unavailable_mixed_evidence_all_statuses(self):
        for status in sorted(pack.STATUSES - {'unavailable'}):
            self.evidence('unavailable', 'unavailable')
            self.documents['evidence']['records'].append({**self.documents['evidence']['records'][0],
                                                          'id': 'E2', 'kind': 'observed', 'result': 'observed'})
            self.documents['report']['claims'][0].update(status=status, evidence=['E1', 'E2'])
            with self.subTest(status=status), self.assertRaisesRegex(ValueError, '^unavailable-evidence:'):
                pack.validate_western_blot_densitometry_pack(self.save())

    def test_claim_empty_unavailable_replication_and_types(self):
        claim = self.documents['report']['claims'][0]
        claim['status'] = 'supported'
        with self.assertRaisesRegex(ValueError, '^missing-evidence:'):
            pack.validate_western_blot_densitometry_pack(self.save())
        claim.update(status='unavailable', text='Supported synthetic result')
        with self.assertRaisesRegex(ValueError, '^unavailable-positive:'):
            pack.validate_western_blot_densitometry_pack(self.save())
        self.evidence('observed', 'observed')
        self.documents['report']['claims'][0]['status'] = 'replicated'
        with self.assertRaisesRegex(ValueError, '^claim-replication:'):
            pack.validate_western_blot_densitometry_pack(self.save())
        for field in ('status', 'kind', 'id'):
            self.documents['report']['claims'][0][field] = []
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.validate_western_blot_densitometry_pack(self.save())
            self.evidence('observed', 'observed')

    def test_wording_families_and_refusal_order(self):
        words = ('causes', 'mechanism', 'therapeutic', 'clinical', 'efficacy', 'effective', 'treatment', 'cures',
                 'prevents', 'recommended', 'prescribe', 'binding', 'affinity', 'inhibition', 'activation',
                 'regulation', 'drives', 'induction', 'protein abundance', 'expression', 'truth', 'physical validity')
        for word in words:
            self.evidence()
            self.documents['report']['claims'][0].update(kind='descriptive', text='Synthetic ' + word)
            with self.subTest(word=word), self.assertRaisesRegex(ValueError, '^claim-overreach:'):
                pack.validate_western_blot_densitometry_pack(self.save())
        self.documents['report']['headline'] = 'Synthetic clinical relevance'
        self.documents['table']['rows'][0]['target_intensity'] = -1
        with self.assertRaisesRegex(ValueError, '^claim-overreach:'):
            pack.validate_western_blot_densitometry_pack(self.save())

    def test_external_alias_path_hash_and_hardlink(self):
        for origin in ('external', 'independent', 'preregistered'):
            self.evidence('observed', 'observed', origin)
            with self.subTest(origin=origin), self.assertRaisesRegex(ValueError, '^external-alias:'):
                pack.validate_western_blot_densitometry_pack(self.save())
        alias = self.root / 'aliased-source'
        os.link(self.root / 'table.json', alias)
        self.documents['evidence']['records'][0]['source']['path'] = alias.name
        with self.assertRaisesRegex(ValueError, '^external-alias:'):
            pack.validate_western_blot_densitometry_pack(self.save())

    def test_near_zero_comparison_has_no_absolute_tolerance(self):
        with self.assertRaisesRegex(ValueError, '^reported-number:'):
            pack._same(2e-20, 1e-20, 'small distinct number')
        pack._same(1e-20 * (1 + 1e-10), 1e-20, 'small relative tie')

    def test_cli_success_refusal_arguments_and_help(self):
        command = [sys.executable, str(ROOT / 'scripts/validate_western_blot_densitometry_pack.py')]
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
        self.assertEqual(json.loads(success.stdout)['schema'], 'wb-result-v1')
        self.documents['table']['rows'][0]['target_intensity'] = True
        refused = subprocess.run(command + [str(self.save())], capture_output=True, text=True, timeout=CALL_TIMEOUT)
        self.assertEqual(refused.returncode, 2)
        self.assertTrue(json.loads(refused.stderr)['finding'].startswith('invalid-record:'))


def _seeded_test(case):
    def test(self):
        self.run_case(case)
    return test


for _case in CASES:
    setattr(WBPackTests, 'test_seed_' + _case['id'].replace('-', '_'), _seeded_test(_case))


if __name__ == '__main__':
    unittest.main()
