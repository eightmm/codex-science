"""Offline synthetic cell-count acceptance, refusal and hostile-file regression checks."""
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

from codex_science import cell_count_viability_pack as pack

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'examples/workflow-cell-count-viability'
CALL_TIMEOUT = float(os.environ.get('OMS_TEST_CALL_TIMEOUT', '30'))
CASES = json.loads((EXAMPLE / 'negative-cases.json').read_text())['cases']


class CellPackTests(unittest.TestCase):
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

    def run_case(self, case):
        node = self.documents[case['target']]
        for key in case['path'][:-1]:
            node = node[key]
        if case['remove']:
            del node[case['path'][-1]]
        else:
            node[case['path'][-1]] = case['value']
        with self.assertRaisesRegex(ValueError, '^' + case['finding'] + ':'):
            pack.validate_cell_count_viability_pack(self.save())

    def refresh_report(self, squares=None):
        self.documents['report'].update(pack.compute_cell_count_viability(
            self.documents['counts'], self.documents['rules'], squares))

    def test_fixture_hand_arithmetic(self):
        result = pack.validate_cell_count_viability_pack(self.root / 'pack.json')
        expected = json.loads((EXAMPLE / 'expected.json').read_text())['computation']
        pack._same(result['computation'], expected, 'expected synthetic fixture')
        a, b = result['computation']['samples']
        self.assertEqual((a['recorded_live'], a['recorded_dead'], a['usable_total']), (32, 8, 40))
        self.assertTrue(math.isclose(a['cells_per_ml'], 10 * 2 * 2 * 10000, rel_tol=1e-12, abs_tol=0))
        self.assertTrue(math.isclose(a['viability'], 32 / 40, rel_tol=1e-12, abs_tol=0))
        se = a['count_uncertainty']
        self.assertTrue(math.isclose(se['standard_error_per_ml'], math.sqrt(40) / 4 * 40000,
                                     rel_tol=1e-12, abs_tol=0))
        self.assertEqual((b['recorded_live'], b['recorded_dead']), (4, 0))
        self.assertEqual(b['cells_per_ml'], 'unavailable')
        self.assertEqual(b['viability_interval'], 'unavailable')
        self.assertEqual(result['computation']['summary'], {'n': 2, 'quantified': 1, 'unavailable': 1})
        self.assertEqual(result['review'], 'unavailable')
        self.assertEqual(result['stages'], list(pack.STAGES))

    def test_exact_binomial_independent_tail_equations(self):
        for live, total in ((1, 2), (2, 4), (32, 40)):
            interval = pack.binomial_interval(live, total)
            lower, upper = interval['lower'], interval['upper']
            lower_tail = math.fsum(math.comb(total, k) * lower ** k * (1 - lower) ** (total - k)
                                   for k in range(live, total + 1))
            upper_tail = math.fsum(math.comb(total, k) * upper ** k * (1 - upper) ** (total - k)
                                   for k in range(live + 1))
            self.assertTrue(math.isclose(lower_tail, .025, rel_tol=1e-10, abs_tol=0))
            self.assertTrue(math.isclose(upper_tail, .025, rel_tol=1e-10, abs_tol=0))
        zero = pack.binomial_interval(0, 4)
        full = pack.binomial_interval(4, 4)
        self.assertTrue(math.isclose(zero['upper'], 1 - .025 ** .25, rel_tol=1e-12, abs_tol=0))
        self.assertTrue(math.isclose(full['lower'], .025 ** .25, rel_tol=1e-12, abs_tol=0))
        self.assertEqual((zero['lower'], full['upper']), (0, 1))
        high = pack.binomial_interval(pack.MAX_CELLS // 2, pack.MAX_CELLS)
        self.assertLess(high['lower'], .5)
        self.assertGreater(high['upper'], .5)

    def test_interval_types_limits_and_convergence(self):
        for value in (True, 2.0, '2', [], None, -1, pack.MAX_CELLS + 1):
            for field in ('live', 'total'):
                args = {'live': 1, 'total': 2}
                args[field] = value
                with self.subTest(value=value, field=field), self.assertRaisesRegex(ValueError, '^invalid-record:'):
                    pack.binomial_interval(**args)
        for level in (0, .499, 1, True, float('inf'), float('nan'), '0.95'):
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.binomial_interval(1, 2, level)
        for level in (.5, .999):
            self.assertGreater(pack.binomial_interval(1, 2, level)['lower'], 0)
        with self.assertRaisesRegex(ValueError, '^invalid-record:'):
            pack.binomial_interval(0, 0)
        for constant in ('MAX_ITERATIONS', 'QUANTILE_STEPS'):
            with patch.object(pack, constant, 0), self.assertRaisesRegex(ValueError, '^binomial-convergence:'):
                pack.binomial_interval(1, 2)
        for value in (0, 1e-16):
            with self.assertRaisesRegex(ValueError, '^binomial-convergence:'):
                pack._denominator(value, 1)
        self.assertEqual(pack._denominator(1e-20, 1e-20), 1e-20)

    def test_integer_fields_and_missing_counts(self):
        rules = self.documents['rules']
        row = self.documents['counts']['rows'][0]
        fields = [(rules, key) for key in ('minimum_per_square', 'maximum_per_square', 'minimum_total_cells')]
        fields += [(rules['mixing_ratio'], key) for key in ('sample_parts', 'dye_parts')]
        fields += [(row, key) for key in ('live', 'dead')]
        for node, key in fields:
            original = node[key]
            for value in (True, float(original), str(original), [], -1):
                node[key] = value
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, '^invalid-record:'):
                    pack.compute_cell_count_viability(self.documents['counts'], rules)
            node[key] = original
        for value in (0, 1, [], 'false'):
            row['clumped'] = value
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.compute_cell_count_viability(self.documents['counts'], rules)
        row['clumped'] = False
        row['live'] = None
        with self.assertRaisesRegex(ValueError, '^missing-count:'):
            pack.compute_cell_count_viability(self.documents['counts'], rules)
        row['dead'] = None
        self.refresh_report()
        result = pack.validate_cell_count_viability_pack(self.save())['computation']['samples'][0]
        self.assertEqual(result['cells_per_ml'], 'unavailable')
        self.assertEqual(result['recorded_live'], 24)
        for value in (True, 2.0, '2', []):
            self.documents['report']['summary']['n'] = value
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.validate_cell_count_viability_pack(self.save())

    def test_minimum_and_countability_edges(self):
        rules = self.documents['rules']
        for total in (0, 4, 5, 50, 51):
            for row in self.documents['counts']['rows'][:4]:
                row.update(live=total, dead=0)
            result = pack.compute_cell_count_viability(self.documents['counts'], rules)['samples'][0]
            self.assertEqual(result['classification'], 'quantified' if 5 <= total <= 50 else 'unavailable')
            self.assertEqual(result['recorded_live'], 4 * total)
        for row in self.documents['counts']['rows'][:4]:
            row.update(live=5, dead=0)
        rules['minimum_total_cells'] = 21
        self.assertEqual(pack.compute_cell_count_viability(self.documents['counts'], rules)['samples'][0]['viability'],
                         'unavailable')
        rules['minimum_total_cells'] = 20
        self.assertEqual(pack.compute_cell_count_viability(self.documents['counts'], rules)['samples'][0]['viability'], 1)

    def test_all_unavailable_counts_preserve_missingness(self):
        for row in self.documents['counts']['rows']:
            row.update(live=None, dead=None)
        self.refresh_report()
        result = pack.validate_cell_count_viability_pack(self.save())['computation']
        self.assertEqual(result['summary']['unavailable'], 2)
        for row in result['samples']:
            self.assertEqual(row['recorded_live'], 'unavailable')
            self.assertEqual(row['recorded_dead'], 'unavailable')
            self.assertEqual(row['recorded_squares'], 0)
        self.documents['report']['samples'][0]['recorded_live'] = 0
        with self.assertRaisesRegex(ValueError, '^unavailable-as-zero:'):
            pack.validate_cell_count_viability_pack(self.save())

    def test_replicate_bound_equal_and_zero(self):
        rules = self.documents['rules']
        for row in self.documents['counts']['rows'][2:4]:
            row.update(live=13, dead=2)
        rules['maximum_disagreement'] = .4
        self.refresh_report()
        self.assertEqual(pack.validate_cell_count_viability_pack(self.save())['status'], 'arithmetic-only')
        rules['maximum_disagreement'] = .399
        with self.assertRaisesRegex(ValueError, '^replicate-disagreement:'):
            pack.compute_cell_count_viability(self.documents['counts'], rules)
        rules['maximum_disagreement'] = 0
        for row in self.documents['counts']['rows'][2:4]:
            row.update(live=8, dead=2)
        pack.compute_cell_count_viability(self.documents['counts'], rules)

    def test_clumping_preserved_and_exploratory_squares(self):
        self.documents['counts']['rows'][0]['clumped'] = True
        self.refresh_report()
        result = pack.validate_cell_count_viability_pack(self.save())['computation']['samples'][0]
        self.assertEqual(result['cells_per_ml'], 'unavailable')
        self.assertEqual(result['recorded_live'], 32)
        report = self.documents['report']
        report.update(exploratory=True, square_ids=['s2'])
        self.refresh_report(report['square_ids'])
        result = pack.validate_cell_count_viability_pack(self.save())
        self.assertTrue(result['exploratory'])
        self.assertTrue(math.isclose(result['computation']['samples'][0]['cells_per_ml'], 400000, rel_tol=1e-12, abs_tol=0))

    def test_identity_and_frozen_before_count_read(self):
        rules = self.documents['rules']
        rules['chambers'][1]['counter_id'] = rules['chambers'][0]['counter_id']
        with self.assertRaisesRegex(ValueError, '^duplicate-chamber:'):
            pack.compute_cell_count_viability(self.documents['counts'], rules)
        rules['chambers'][1]['counter_id'] = 'counter-A2'
        self.documents['counts']['rows'][0]['square_id'] = []
        with self.assertRaisesRegex(ValueError, '^invalid-record:'):
            pack.compute_cell_count_viability(self.documents['counts'], rules)
        self.documents['pack']['frozen_before_counts_read'] = False
        entry = self.save()
        real_read = pack._Bundle._read
        def read(store, name):
            if name == 'counts.json':
                self.fail('counts read before rule freeze')
            return real_read(store, name)
        with patch.object(pack._Bundle, '_read', read), self.assertRaisesRegex(ValueError, '^rule-freeze:'):
            pack.validate_cell_count_viability_pack(entry)

    def test_collection_limits_before_work(self):
        for constant, limit in (('MAX_ROWS', 7), ('MAX_SAMPLES', 1), ('MAX_CHAMBERS', 3), ('MAX_SQUARES', 1)):
            with patch.object(pack, constant, limit), self.assertRaisesRegex(ValueError, '^input-limit:'):
                pack.compute_cell_count_viability(self.documents['counts'], self.documents['rules'])
        for constant, limit in (('MAX_ROWS', 8), ('MAX_SAMPLES', 2), ('MAX_CHAMBERS', 4), ('MAX_SQUARES', 2)):
            with patch.object(pack, constant, limit):
                pack.compute_cell_count_viability(self.documents['counts'], self.documents['rules'])
        self.documents['rules']['maximum_per_square'] = 40
        with patch.object(pack, 'MAX_CELLS', 40):
            pack.compute_cell_count_viability(self.documents['counts'], self.documents['rules'])
        with patch.object(pack, 'MAX_CELLS', 39), self.assertRaisesRegex(ValueError, '^input-limit:'):
            self.documents['rules']['maximum_per_square'] = 39
            pack.compute_cell_count_viability(self.documents['counts'], self.documents['rules'])
        with patch.object(pack, 'MAX_RECORDS', 0), self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack._claims([self.documents['report']['claims'][0]], {})
        for constant in ('MAX_ROWS', 'MAX_SAMPLES', 'MAX_CHAMBERS', 'MAX_SQUARES'):
            with patch.object(pack, constant, 0), self.assertRaisesRegex(ValueError, '^input-limit:'):
                pack.compute_cell_count_viability(self.documents['counts'], self.documents['rules'])
        with self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack._json(json.dumps({'x': [0] * (pack.MAX_ROWS + 1)}).encode())
        for value in ([], 0, None, {}, 'rows'):
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack._list(value, 'rows', 2)
        self.assertEqual(pack._list([1, 2], 'rows', 2), [1, 2])

    def test_artifact_limit_and_empty_file(self):
        (self.root / 'tiny.json').write_bytes(b'{"x":1}')
        (self.root / 'empty').write_bytes(b'')
        for limit in (0, 1):
            with patch.object(pack, 'MAX_ARTIFACTS', limit):
                store = pack._Bundle(self.root)
                try:
                    if limit:
                        self.assertEqual(store.load('tiny.json'), {'x': 1})
                    with self.assertRaisesRegex(ValueError, '^input-limit:'):
                        store.load('empty')
                finally:
                    store.close()
        with patch.object(pack, 'MAX_BYTES', 0), patch.object(pack, 'MAX_TOTAL_BYTES', 0):
            store = pack._Bundle(self.root)
            try:
                self.assertEqual(store.load('empty', parse=False), hashlib.sha256(b'').hexdigest())
                with self.assertRaisesRegex(ValueError, '^invalid-json:'):
                    store.load('empty')
            finally:
                store.close()

    def test_rule_numeric_bounds_and_definitions(self):
        rules = self.documents['rules']
        for key, low, high in (('volume_ml', 1e-12, 1), ('dilution_factor', 1, 1e6),
                               ('maximum_disagreement', 0, 2), ('interval_level', .5, .999)):
            original = rules[key]
            for value in (low, high):
                rules[key] = value
                pack._rules(rules)
            for value in (None, [], True, '1', -1, high * 2, float('inf'), float('nan')):
                rules[key] = value
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, '^invalid-record:'):
                    pack._rules(rules)
            rules[key] = original
        for key, code in (('interval_method', 'binomial-interval'), ('viability_definition', 'viability-definition')):
            original = rules[key]
            rules[key] = []
            with self.assertRaisesRegex(ValueError, '^' + code + ':'):
                pack._rules(rules)
            rules[key] = original
        for key in ('sample_parts', 'dye_parts'):
            rules['mixing_ratio'][key] = 1000
            pack._rules(rules)
            for value in (0, 1001):
                rules['mixing_ratio'][key] = value
                with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                    pack._rules(rules)
            rules['mixing_ratio'][key] = 1

    def test_list_and_object_limits_before_item_work(self):
        counts = {'schema': 'cell-counts-v1', 'fixture': 'synthetic fixture', 'rows': [None] * (pack.MAX_ROWS + 1)}
        with self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack.compute_cell_count_viability(counts, self.documents['rules'])
        with patch.object(pack, 'MAX_ROWS', 2):
            self.assertEqual(pack._json(b'{"x":1,"y":2}')[0], {'x': 1, 'y': 2})
            with self.assertRaisesRegex(ValueError, '^input-limit:'):
                pack._json(b'{"x":1,"y":2,"z":3}')
        with patch.object(pack, 'MAX_STRING', 3):
            self.assertEqual(pack._json(b'{"x":"abc"}')[0], {'x': 'abc'})
        with patch.object(pack, 'MAX_DEPTH', 1):
            self.assertEqual(pack._json(b'{"x":1}')[0], {'x': 1})
        with patch.object(pack, 'MAX_NUMBER', 1):
            self.assertEqual(pack._json(b'{"x":1}')[0], {'x': 1})
            with self.assertRaisesRegex(ValueError, '^invalid-json:'):
                pack._json(b'{"x":2}')

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

    def test_overflowing_json_floats_are_invalid_json(self):
        for raw in (b'{"x":1e400}', b'{"x":-1e400}'):
            (self.root / 'pack.json').write_bytes(raw)
            with self.assertRaisesRegex(ValueError, '^invalid-json:'):
                pack.validate_cell_count_viability_pack(self.root / 'pack.json')

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
            pack.validate_cell_count_viability_pack(self.root / 'pack.json')
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
            pack.validate_cell_count_viability_pack(self.root / 'pack.json')

    def test_final_hash_and_root_recheck(self):
        real_finish = pack._Bundle.finish
        def change(store):
            with (self.root / 'counts.json').open('ab') as stream:
                stream.write(b' ')
            return real_finish(store)
        with patch.object(pack._Bundle, 'finish', change), self.assertRaisesRegex(ValueError, '^input-changed:'):
            pack.validate_cell_count_viability_pack(self.root / 'pack.json')

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
                    pack.validate_cell_count_viability_pack(self.root / 'pack.json')
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
            pack.validate_cell_count_viability_pack(self.root / 'pack.json')

    def evidence(self, kind='computed', result='numerical-agreement', origin='internal'):
        identity = self.documents['pack']['counts']
        self.documents['evidence'] = {'schema': 'cell-evidence-v1', 'fixture': 'synthetic fixture',
                                     'records': [{'id': 'E1', 'kind': kind, 'result': result, 'origin': origin,
                                                  'source': copy.deepcopy(identity)}]}
        self.documents['report']['claims'] = [{'id': 'C1', 'kind': 'descriptive', 'status': 'supported',
                                               'text': 'Synthetic fixture arithmetic matches the supplied table.',
                                               'evidence': ['E1']}]

    def test_claim_kind_and_result_not_labels(self):
        for kind, result in (('review-approval', 'observed'), ('observed', 'review-approval'),
                             ('computed', 'observed'), ('observed', 'numerical-agreement'),
                             ('observed', 'arithmetic-only'), ('cell-result-v1', 'observed')):
            self.evidence(kind, result)
            with self.subTest(kind=kind, result=result), self.assertRaisesRegex(ValueError, '^non-evidence-support:'):
                pack.validate_cell_count_viability_pack(self.save())

    def test_unavailable_mixed_evidence_all_statuses(self):
        for status in sorted(pack.STATUSES - {'unavailable'}):
            self.evidence('unavailable', 'unavailable')
            self.documents['evidence']['records'].append({**self.documents['evidence']['records'][0],
                                                          'id': 'E2', 'kind': 'observed', 'result': 'observed'})
            self.documents['report']['claims'][0].update(status=status, evidence=['E1', 'E2'])
            with self.subTest(status=status), self.assertRaisesRegex(ValueError, '^unavailable-evidence:'):
                pack.validate_cell_count_viability_pack(self.save())

    def test_claim_empty_unavailable_replication_and_types(self):
        claim = self.documents['report']['claims'][0]
        claim['status'] = 'supported'
        with self.assertRaisesRegex(ValueError, '^missing-evidence:'):
            pack.validate_cell_count_viability_pack(self.save())
        claim.update(status='unavailable', text='Supported synthetic result')
        with self.assertRaisesRegex(ValueError, '^unavailable-positive:'):
            pack.validate_cell_count_viability_pack(self.save())
        self.evidence('observed', 'observed')
        self.documents['report']['claims'][0]['status'] = 'replicated'
        with self.assertRaisesRegex(ValueError, '^claim-replication:'):
            pack.validate_cell_count_viability_pack(self.save())
        for field in ('status', 'kind', 'id'):
            self.documents['report']['claims'][0][field] = []
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.validate_cell_count_viability_pack(self.save())
            self.evidence('observed', 'observed')

    def test_wording_families_and_refusal_order(self):
        words = ('causes', 'mechanism', 'therapeutic', 'clinical', 'efficacy', 'effective', 'treatment', 'cures',
                 'prevents', 'recommended', 'prescribe', 'binding', 'affinity', 'inhibition', 'activation',
                 'regulation', 'drives', 'induction', 'sterile', 'safe', 'potency', 'truth', 'physical validity')
        for word in words:
            self.evidence()
            self.documents['report']['claims'][0].update(kind='descriptive', text='Synthetic ' + word)
            with self.subTest(word=word), self.assertRaisesRegex(ValueError, '^claim-overreach:'):
                pack.validate_cell_count_viability_pack(self.save())
        self.documents['report']['headline'] = 'Synthetic safety'
        self.documents['counts']['rows'][0]['live'] = -1
        with self.assertRaisesRegex(ValueError, '^claim-overreach:'):
            pack.validate_cell_count_viability_pack(self.save())

    def test_external_alias_path_hash_and_hardlink(self):
        for origin in ('external', 'independent', 'preregistered'):
            self.evidence('observed', 'observed', origin)
            with self.subTest(origin=origin), self.assertRaisesRegex(ValueError, '^external-alias:'):
                pack.validate_cell_count_viability_pack(self.save())
        alias = self.root / 'aliased-source'
        os.link(self.root / 'counts.json', alias)
        self.documents['evidence']['records'][0]['source']['path'] = alias.name
        with self.assertRaisesRegex(ValueError, '^external-alias:'):
            pack.validate_cell_count_viability_pack(self.save())

    def test_near_zero_comparison_has_no_absolute_tolerance(self):
        with self.assertRaisesRegex(ValueError, '^reported-number:'):
            pack._same(2e-20, 1e-20, 'small distinct number')
        pack._same(1e-20 * (1 + 1e-10), 1e-20, 'small relative tie')
        pack._same(1e-20 * (1 + 5e-9), 1e-20, 'documented relative tolerance')

    def test_frozen_echo_paths_use_edge_tolerance(self):
        def nest(path, value):
            return {path[0]: nest(path[1:], value)} if path else value
        drifted = 0.95 * (1 + 5e-9)
        with self.assertRaisesRegex(ValueError, '^reported-number:'):
            pack._same(nest(('viability_interval', 'level'), drifted), nest(('viability_interval', 'level'), 0.95), 'root')
        pack._same(nest(('means', 'level'), drifted), nest(('means', 'level'), 0.95), 'root')

    def test_cli_success_refusal_arguments_and_help(self):
        command = [sys.executable, str(ROOT / 'scripts/validate_cell_count_viability_pack.py')]
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
        self.assertEqual(json.loads(success.stdout)['schema'], 'cell-result-v1')
        self.documents['counts']['rows'][0]['live'] = True
        refused = subprocess.run(command + [str(self.save())], capture_output=True, text=True, timeout=CALL_TIMEOUT)
        self.assertEqual(refused.returncode, 2)
        self.assertTrue(json.loads(refused.stderr)['finding'].startswith('invalid-record:'))


def _seeded_test(case):
    def test(self):
        self.run_case(case)
    return test


for _case in CASES:
    setattr(CellPackTests, 'test_seed_' + _case['id'].replace('-', '_'), _seeded_test(_case))


if __name__ == '__main__':
    unittest.main()
