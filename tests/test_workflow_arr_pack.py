"""Offline synthetic Arrhenius acceptance, refusal and hostile-file regression checks."""
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

from codex_science import arrhenius_rate_fit_pack as pack

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'examples/workflow-arrhenius-rate-fit'
CALL_TIMEOUT = float(os.environ.get('OMS_TEST_CALL_TIMEOUT', '30'))
CASES = json.loads((EXAMPLE / 'negative-cases.json').read_text())['cases']


class ArrheniusPackTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'parent' / 'bundle'
        self.root.mkdir(parents=True)
        for name in ('pack.json', 'rules.json', 'rates.json', 'report.json'):
            shutil.copyfile(EXAMPLE / name, self.root / name)
        self.documents = {name: json.loads((self.root / (name + '.json')).read_text())
                          for name in ('pack', 'rules', 'rates', 'report')}

    def save(self):
        entry = self.documents['pack']
        for name in ('rules', 'rates', 'report', 'evidence'):
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

    def refresh_report(self, weighting=None):
        self.documents['report']['computation'] = pack.compute_arrhenius(
            self.documents['rates'], self.documents['rules'], weighting)

    def run_case(self, case):
        node = self.documents[case['target']]
        for key in case['path'][:-1]:
            node = node[int(key)] if type(node) is list else node[key]
        key = case['path'][-1]
        node[int(key) if type(node) is list else key] = case['value']
        with self.assertRaisesRegex(ValueError, '^' + case['finding'] + ':'):
            pack.validate_arrhenius_rate_fit_pack(self.save())

    def test_noisy_hand_arithmetic(self):
        result = pack.validate_arrhenius_rate_fit_pack(self.root / 'pack.json')
        fit = result['computation']
        expected = json.loads((EXAMPLE / 'expected.json').read_text())['computation']
        self.assertEqual(fit, expected)
        self.assertEqual((fit['n_runs'], fit['n_temperatures'], fit['df']), (8, 4, 2))
        self.assertAlmostEqual(fit['ln_A'], 4)
        self.assertAlmostEqual(fit['Ea'], 1000 * pack.GAS_CONSTANT)
        # x = .004,.003,.002,.001; centered sum squares = .000005.
        # Residuals .1,-.1,-.1,.1 give SSE .04, df 2, variance .02.
        self.assertAlmostEqual(fit['residual_standard_error'], math.sqrt(.02))
        self.assertAlmostEqual(fit['slope_se'], math.sqrt(.02 / .000005))
        self.assertAlmostEqual(fit['ln_A_se'], math.sqrt(.03))
        self.assertAlmostEqual(fit['Ea_se'], pack.GAS_CONSTANT * math.sqrt(4000))
        self.assertAlmostEqual(fit['t_critical'], 4.30265272974946, places=11)
        self.assertAlmostEqual(fit['Ea_interval'][0], fit['Ea'] - fit['t_critical'] * fit['Ea_se'])
        # Pure error .32/4 and lack-of-fit .08/2 give F .5, upper tail .64.
        self.assertAlmostEqual(fit['lack_of_fit']['F'], .5)
        self.assertAlmostEqual(fit['lack_of_fit']['p'], .64)
        self.assertFalse(fit['lack_of_fit']['flag'])
        prediction = fit['prediction']
        self.assertAlmostEqual(prediction['ln_rate'], 1.5)
        self.assertAlmostEqual(prediction['ln_rate_se'], math.sqrt(.005))
        self.assertAlmostEqual(prediction['rate'], math.exp(1.5))
        self.assertAlmostEqual(prediction['rate_interval'][0], math.exp(1.5 - fit['t_critical'] * math.sqrt(.005)))
        self.assertEqual(result['stages'], list(pack.STAGES))
        self.assertEqual(result['review'], 'unavailable')

    def test_noiseless_known_series(self):
        fit = pack.validate_arrhenius_rate_fit_pack(EXAMPLE / 'noiseless-pack.json')['computation']
        expected = json.loads((EXAMPLE / 'noiseless-expected.json').read_text())['computation']
        self.assertEqual(fit, expected)
        self.assertAlmostEqual(fit['Ea'], 1000 * pack.GAS_CONSTANT)
        self.assertAlmostEqual(math.exp(fit['ln_A']), math.exp(4))
        self.assertLess(fit['residual_standard_error'], 1e-14)
        self.assertEqual(fit['lack_of_fit'], 'unavailable')

    def test_kelvin_units_and_positive_rates(self):
        for value in (True, '300', [], 0, -1, float('inf'), float('nan')):
            self.documents['rates']['rows'][0]['temperature_kelvin'] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.compute_arrhenius(self.documents['rates'], self.documents['rules'])
        self.documents['rates']['rows'][0]['temperature_kelvin'] = 250
        for value in (True, '1', [], float('inf'), float('nan')):
            self.documents['rates']['rows'][0]['rate'] = value
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.compute_arrhenius(self.documents['rates'], self.documents['rules'])
        self.documents['rates']['rows'][0]['rate'] = 1
        self.documents['rates']['rows'][0]['rate_unit'] = 'min^-1'
        with self.assertRaisesRegex(ValueError, '^rate-units:'):
            pack.compute_arrhenius(self.documents['rates'], self.documents['rules'])

    def test_unavailable_minimum_span_and_prediction_edges(self):
        rules = self.documents['rules']
        for count in (1, 2, 3):
            limited = copy.deepcopy(rules)
            limited['runs'] = limited['runs'][:2 * count]
            rates = {**self.documents['rates'], 'rows': self.documents['rates']['rows'][:2 * count]}
            fit = pack.compute_arrhenius(rates, limited)
            self.assertEqual(fit['status'], 'unavailable')
            for name in ('Ea', 'Ea_se', 'ln_A', 'ln_A_se', 'residual_standard_error'):
                self.assertEqual(fit[name], 'unavailable')
            limited['prediction_temperature_kelvin'] = 200
            self.assertEqual(pack.compute_arrhenius(rates, limited)['prediction']['status'], 'outside-range')
        rules['minimum_span_kelvin'] = 751
        self.assertEqual(pack.compute_arrhenius(self.documents['rates'], rules)['status'], 'unavailable')
        self.refresh_report()
        self.assertEqual(pack.validate_arrhenius_rate_fit_pack(self.save())['computation']['status'], 'unavailable')
        rules['minimum_span_kelvin'] = 750
        for temperature, status in ((250, 'inside-range'), (1000, 'inside-range'),
                                    (249, 'outside-range'), (1001, 'outside-range')):
            rules['prediction_temperature_kelvin'] = temperature
            self.refresh_report()
            prediction = pack.validate_arrhenius_rate_fit_pack(self.save())['computation']['prediction']
            self.assertEqual(prediction['status'], status)
            if status == 'outside-range':
                self.assertEqual(prediction['rate'], 'unavailable')

    def test_replicate_weighting_and_exploratory_revision(self):
        rules = self.documents['rules']
        fit = pack.compute_arrhenius(self.documents['rates'], rules, 'replicate-variance')
        self.assertAlmostEqual(fit['ln_A'], 4)
        self.assertAlmostEqual(fit['Ea'], 1000 * pack.GAS_CONSTANT)
        self.assertEqual(fit['lack_of_fit'], 'unavailable')
        self.documents['report'].update(exploratory=True, weighting='replicate-variance')
        self.refresh_report('replicate-variance')
        self.assertTrue(pack.validate_arrhenius_rate_fit_pack(self.save())['exploratory'])
        # Known variances .08,.32,.08,.08 give relative mean-precision weights 16:4:16:16.
        self.documents['rates']['rows'][2]['rate'] = math.exp(.5)
        self.documents['rates']['rows'][3]['rate'] = math.exp(1.3)
        fit = pack.compute_arrhenius(self.documents['rates'], rules, 'replicate-variance')
        xs, ys, ws = [.004, .003, .002, .001], [.1, .9, 1.9, 3.1], [16, 4, 16, 16]
        xmean, ymean = 124 / 52000, 85.2 / 52
        sxx = math.fsum(w * (x - xmean) ** 2 for w, x in zip(ws, xs))
        slope = math.fsum(w * (x - xmean) * (y - ymean) for w, x, y in zip(ws, xs, ys)) / sxx
        self.assertAlmostEqual(fit['slope'], slope)
        self.assertAlmostEqual(fit['ln_A'], ymean - slope * xmean)
        for row in self.documents['rates']['rows']:
            row['rate'] = math.exp(row['temperature_kelvin'] / 1000)
        with self.assertRaisesRegex(ValueError, '^replicate-variance:'):
            pack.compute_arrhenius(self.documents['rates'], rules, 'replicate-variance')
        self.documents['rates']['rows'] = self.documents['rates']['rows'][::2]
        rules['runs'] = rules['runs'][::2]
        with self.assertRaisesRegex(ValueError, '^replicate-variance:'):
            pack.compute_arrhenius(self.documents['rates'], rules, 'replicate-variance')
        self.assertEqual(pack.compute_arrhenius(self.documents['rates'], rules)['lack_of_fit'], 'unavailable')

    def test_lack_of_fit_failure_and_unbalanced_unavailable(self):
        for index, row in enumerate(self.documents['rates']['rows']):
            row['rate'] = math.exp([0, 1, 2, 10][index // 2] + (-.001 if index % 2 else .001))
        fit = pack.compute_arrhenius(self.documents['rates'], self.documents['rules'])
        self.assertTrue(fit['lack_of_fit']['flag'])
        self.refresh_report()
        self.assertTrue(pack.validate_arrhenius_rate_fit_pack(self.save())['computation']['lack_of_fit']['flag'])
        self.documents['rates']['rows'].pop()
        self.documents['rules']['runs'].pop()
        self.assertEqual(pack.compute_arrhenius(self.documents['rates'], self.documents['rules'])['lack_of_fit'], 'unavailable')

    def test_lack_of_fit_threshold_equality(self):
        for index, row in enumerate(self.documents['rates']['rows']):
            row['rate'] = math.exp([.3, .7, 1.7, 3.3][index // 2] + (-.2 if index % 2 else .2))
        fit = pack.compute_arrhenius(self.documents['rates'], self.documents['rules'])
        self.assertAlmostEqual(fit['lack_of_fit']['F'], 4.5)
        self.assertAlmostEqual(fit['lack_of_fit']['p'], (4 / 13) ** 2)
        self.documents['rules']['lack_of_fit_alpha'] = fit['lack_of_fit']['p']
        fit = pack.compute_arrhenius(self.documents['rates'], self.documents['rules'])
        self.assertFalse(fit['lack_of_fit']['flag'])

    def test_integer_fields_and_degenerate_inputs(self):
        for value in (True, 4.0, '4', [], 0, 3):
            rules = {**self.documents['rules'], 'minimum_temperatures': value}
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.compute_arrhenius(self.documents['rates'], rules)
        for key in ('df', 'n_runs', 'n_temperatures'):
            original = self.documents['report']['computation'][key]
            for value in (True, float(original), str(original), []):
                self.documents['report']['computation'][key] = value
                with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                    pack.validate_arrhenius_rate_fit_pack(self.save())
            self.documents['report']['computation'][key] = original
        for row in self.documents['rates']['rows']:
            row['rate'] = 1
        with self.assertRaisesRegex(ValueError, '^degenerate-fit:'):
            pack.compute_arrhenius(self.documents['rates'], self.documents['rules'])
        for index, row in enumerate(self.documents['rates']['rows']):
            row['rate'] = math.exp(0.1) * (1 + 2e-16 * (index // 2 % 2))
        with self.assertRaisesRegex(ValueError, '^degenerate-fit:'):
            pack.compute_arrhenius(self.documents['rates'], self.documents['rules'])
        self.documents['rates']['rows'] = []
        with self.assertRaisesRegex(ValueError, '^invalid-record:'):
            pack.compute_arrhenius(self.documents['rates'], self.documents['rules'])

    def test_identity_controls_and_empty_rules(self):
        for target, code in (('run_id', 'duplicate-run'), ('replicate_id', 'run-identity')):
            rows = copy.deepcopy(self.documents['rates'])
            rows['rows'][1][target] = rows['rows'][0][target]
            with self.assertRaisesRegex(ValueError, '^' + code + ':'):
                pack.compute_arrhenius(rows, self.documents['rules'])
        rows = copy.deepcopy(self.documents['rates'])
        rows['rows'].pop()
        with self.assertRaisesRegex(ValueError, '^missing-run:'):
            pack.compute_arrhenius(rows, self.documents['rules'])
        rules = copy.deepcopy(self.documents['rules'])
        rules['runs'][1]['replicate_id'] = rules['runs'][0]['replicate_id']
        with self.assertRaisesRegex(ValueError, '^replicate-identity:'):
            pack.compute_arrhenius(self.documents['rates'], rules)
        rules['runs'] = []
        with self.assertRaisesRegex(ValueError, '^invalid-record:'):
            pack.compute_arrhenius(self.documents['rates'], rules)

    def test_rule_units_bounds_and_interval_convergence(self):
        for field, value, finding in (('gas_constant', 8, 'gas-constant-value'),
                                      ('replicate_rule', 'mean-rate', 'replicate-rule'),
                                      ('weighting', [], 'invalid-record'),
                                      ('weighting', 'arbitrary', 'weighting-rule'),
                                      ('extrapolation', 'allowed', 'extrapolation'),
                                      ('energy_unit', 'cal/mol', 'gas-constant-units')):
            rules = {**self.documents['rules'], field: value}
            with self.assertRaisesRegex(ValueError, '^' + finding + ':'):
                pack.compute_arrhenius(self.documents['rates'], rules)
        rules = {**self.documents['rules'], 'energy_unit': 'kJ/mol', 'gas_constant_unit': 'kJ/(mol K)',
                 'gas_constant': pack.GAS_CONSTANT / 1000}
        self.assertAlmostEqual(pack.compute_arrhenius(self.documents['rates'], rules)['Ea'], pack.GAS_CONSTANT)
        for df in (True, 2.0, '2', [], 0, -1):
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.student_t_critical(df)
        for level in (.5, .999):
            self.assertGreater(pack.student_t_critical(2, level), 0)
        self.assertAlmostEqual(pack.student_t_critical(1), 1 / math.tan(math.pi * .025), places=10)
        for level in (0, 1, True, [], '0.95'):
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.student_t_critical(2, level)
        for constant in ('MAX_ITERATIONS', 'QUANTILE_STEPS'):
            with patch.object(pack, constant, 0), self.assertRaisesRegex(ValueError, '^interval-convergence:'):
                pack.student_t_critical(2)

    def test_collection_limits_before_work(self):
        with patch.object(pack, 'MAX_ROWS', 2), self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack.compute_arrhenius(self.documents['rates'], self.documents['rules'])
        rules = copy.deepcopy(self.documents['rules'])
        rules['runs'].append({'run_id': 'fifth', 'replicate_id': 'r1', 'temperature_kelvin': 750})
        with patch.object(pack, 'MAX_TEMPERATURES', 4), self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack.compute_arrhenius(self.documents['rates'], rules)
        with patch.object(pack, 'MAX_RECORDS', 0), self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack._claims([self.documents['report']['claims'][0]], {})
        raw = json.dumps({'x': [0] * (pack.MAX_ROWS + 1)}).encode()
        with self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack._json(raw)
        self.assertEqual(pack._list([1, 2], 'edge', 2), [1, 2])
        for value in ([], 0, None, {}, 'rows'):
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack._list(value, 'rows', 2)

    def test_zero_and_equal_resource_limits(self):
        with patch.object(pack, 'MAX_NODES', 1):
            self.assertEqual(pack._json(b'{}'), ({}, 1))
        with patch.object(pack, 'MAX_NODES', 0), self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack._json(b'{}')
        with patch.object(pack, 'MAX_DEPTH', 0):
            self.assertEqual(pack._json(b'{}'), ({}, 1))
            with self.assertRaisesRegex(ValueError, '^invalid-json:'):
                pack._json(b'{"a":1}')
        with patch.object(pack, 'MAX_STRING', 3):
            self.assertEqual(pack._text('abc', 'edge'), 'abc')
        with patch.object(pack, 'MAX_STRING', 0), self.assertRaisesRegex(ValueError, '^invalid-record:'):
            pack._text('a', 'edge')
        for raw in (b'{"x":1e100}', b'{"x":-1e100}'):
            self.assertTrue(math.isfinite(pack._json(raw)[0]['x']))
        (self.root / 'empty').write_bytes(b'')
        with patch.object(pack, 'MAX_BYTES', 0), patch.object(pack, 'MAX_TOTAL_BYTES', 0):
            store = pack._Bundle(self.root)
            try:
                self.assertEqual(store.load('empty', parse=False), hashlib.sha256(b'').hexdigest())
                with self.assertRaisesRegex(ValueError, '^invalid-json:'):
                    store.load('empty')
            finally:
                store.close()

    def test_numeric_limits_prediction_and_integer_nested_reports(self):
        rules = self.documents['rules']
        for field in ('minimum_span_kelvin', 'prediction_temperature_kelvin', 'interval_level', 'lack_of_fit_alpha'):
            for value in (0, True, [], '1', float('inf')):
                with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, '^invalid-record:'):
                    pack.compute_arrhenius(self.documents['rates'], {**rules, field: value})
        for field, value in (('minimum_temperatures', pack.MAX_TEMPERATURES),
                             ('minimum_span_kelvin', 1e-6), ('minimum_span_kelvin', 1e6),
                             ('prediction_temperature_kelvin', 1e-6), ('prediction_temperature_kelvin', 1e6),
                             ('lack_of_fit_alpha', .001), ('lack_of_fit_alpha', .5)):
            self.assertIn(pack.compute_arrhenius(self.documents['rates'], {**rules, field: value})['status'],
                          {'fitted', 'unavailable'})
        fit = self.documents['report']['computation']
        for row, key in ((fit['temperatures'][0], 'n_replicates'),
                         (fit['lack_of_fit'], 'df_numerator'), (fit['lack_of_fit'], 'df_denominator')):
            original = row[key]
            for value in (True, float(original), str(original), []):
                row[key] = value
                with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                    pack.validate_arrhenius_rate_fit_pack(self.save())
            row[key] = original
        rules['minimum_span_kelvin'] = 1e-6
        rules['prediction_temperature_kelvin'] = 250
        for index, row in enumerate(self.documents['rates']['rows']):
            row['rate'] = math.exp([-700, 230, -700, 230][index // 2])
        with self.assertRaisesRegex(ValueError, '^prediction-numeric:'):
            pack.compute_arrhenius(self.documents['rates'], rules)

    def test_frozen_rules_checked_before_rate_open(self):
        self.documents['pack']['frozen_before_rates_read'] = False
        bundle = self.save()
        real_open = os.open
        def no_rates(name, flags, *args, **kwargs):
            if name == 'rates.json':
                raise AssertionError('rates opened before rule freeze')
            return real_open(name, flags, *args, **kwargs)
        with patch.object(pack.os, 'open', side_effect=no_rates), self.assertRaisesRegex(ValueError, '^rule-freeze:'):
            pack.validate_arrhenius_rate_fit_pack(bundle)

    def test_concurrent_calls_and_no_writes(self):
        before = {path.name: path.read_bytes() for path in self.root.iterdir()}
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(pack.validate_arrhenius_rate_fit_pack, self.root / 'pack.json') for _ in range(2)]
            results = [future.result(timeout=CALL_TIMEOUT) for future in futures]
        self.assertEqual(results[0], results[1])
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.root.iterdir()})

    def test_lstat_ancestor_and_root_symlink_swaps(self):
        real_lstat = os.lstat
        for component in ('parent', 'bundle'):
            target = self.root.parent if component == 'parent' else self.root
            parked = target.with_name(component + '-parked')
            swapped = False
            def swap(name, *args, **kwargs):
                nonlocal swapped
                info = real_lstat(name, *args, **kwargs)
                if name == component and not swapped:
                    swapped = True
                    target.rename(parked)
                    target.symlink_to(parked, target_is_directory=True)
                return info
            try:
                with patch.object(pack.os, 'lstat', side_effect=swap), self.assertRaisesRegex(ValueError, '^input-root:'):
                    pack.validate_arrhenius_rate_fit_pack(self.root / 'pack.json')
            finally:
                if swapped:
                    target.unlink()
                    parked.rename(target)

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
        for value in ('../rates.json', '/rates.json', 'a\\b', 'a/./b', 'a//b', '.', ''):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, '^(input-path|invalid-record):'):
                pack._relative(value)
        target = self.root / 'special'
        for kind in ('directory', 'fifo', 'symlink', 'missing'):
            if kind == 'directory':
                target.mkdir()
            elif kind == 'fifo':
                os.mkfifo(target)
            elif kind == 'symlink':
                target.symlink_to('rates.json')
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
                store.load('link/rates.json')
        finally:
            store.close()

    def test_file_replacement_and_growth(self):
        target = self.root / 'rates.json'
        real_open, real_fstat = os.open, os.fstat
        replaced = False
        def replace(name, flags, *args, **kwargs):
            nonlocal replaced
            if name == target.name and not replaced:
                replaced = True
                raw = target.read_bytes()
                target.rename(self.root / 'old-rates')
                target.write_bytes(raw)
            return real_open(name, flags, *args, **kwargs)
        with patch.object(pack.os, 'open', side_effect=replace), self.assertRaisesRegex(ValueError, '^input-file:'):
            pack.validate_arrhenius_rate_fit_pack(self.root / 'pack.json')
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
            pack.validate_arrhenius_rate_fit_pack(self.root / 'pack.json')

    def test_final_hash_and_root_recheck(self):
        real_finish = pack._Bundle.finish
        def change(store):
            with (self.root / 'rates.json').open('ab') as stream:
                stream.write(b' ')
            return real_finish(store)
        with patch.object(pack._Bundle, 'finish', change), self.assertRaisesRegex(ValueError, '^input-changed:'):
            pack.validate_arrhenius_rate_fit_pack(self.root / 'pack.json')

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
                    pack.validate_arrhenius_rate_fit_pack(self.root / 'pack.json')
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
            pack.validate_arrhenius_rate_fit_pack(self.root / 'pack.json')

    def evidence(self, kind='computed', result='numerical-agreement', origin='internal'):
        identity = self.documents['pack']['rates']
        self.documents['evidence'] = {'schema': 'arr-evidence-v1', 'fixture': 'synthetic fixture',
                                     'records': [{'id': 'E1', 'kind': kind, 'result': result, 'origin': origin,
                                                  'source': copy.deepcopy(identity)}]}
        self.documents['report']['claims'] = [{'id': 'C1', 'kind': 'descriptive', 'status': 'supported',
                                               'text': 'Synthetic fixture arithmetic matches the supplied table.',
                                               'evidence': ['E1']}]

    def test_claim_kind_and_result_not_labels(self):
        for kind, result in (('review-approval', 'observed'), ('observed', 'review-approval'),
                             ('computed', 'observed'), ('observed', 'numerical-agreement'),
                             ('observed', 'arithmetic-only'), ('arr-result-v1', 'observed')):
            for status in pack.POSITIVE:
                self.evidence(kind, result)
                self.documents['report']['claims'][0]['status'] = status
                with self.subTest(kind=kind, result=result, status=status), self.assertRaisesRegex(ValueError, '^non-evidence-support:'):
                    pack.validate_arrhenius_rate_fit_pack(self.save())

    def test_unavailable_mixed_evidence_all_statuses(self):
        for status in sorted(pack.STATUSES - {'unavailable'}):
            self.evidence('unavailable', 'unavailable')
            self.documents['evidence']['records'].append({**self.documents['evidence']['records'][0],
                                                          'id': 'E2', 'kind': 'observed', 'result': 'observed'})
            self.documents['report']['claims'][0].update(status=status, evidence=['E1', 'E2'])
            with self.subTest(status=status), self.assertRaisesRegex(ValueError, '^unavailable-evidence:'):
                pack.validate_arrhenius_rate_fit_pack(self.save())

    def test_claim_empty_unavailable_replication_and_types(self):
        claim = self.documents['report']['claims'][0]
        claim['status'] = 'supported'
        with self.assertRaisesRegex(ValueError, '^missing-evidence:'):
            pack.validate_arrhenius_rate_fit_pack(self.save())
        claim.update(status='unavailable', text='Supported synthetic result')
        with self.assertRaisesRegex(ValueError, '^unavailable-positive:'):
            pack.validate_arrhenius_rate_fit_pack(self.save())
        self.evidence('observed', 'observed')
        self.documents['report']['claims'][0]['status'] = 'replicated'
        with self.assertRaisesRegex(ValueError, '^claim-replication:'):
            pack.validate_arrhenius_rate_fit_pack(self.save())
        for field in ('status', 'kind', 'id'):
            self.documents['report']['claims'][0][field] = []
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.validate_arrhenius_rate_fit_pack(self.save())
            self.evidence('observed', 'observed')

    def test_wording_families_and_refusal_order(self):
        words = ('causes', 'mechanism', 'therapeutic', 'clinical', 'efficacy', 'effective', 'treatment', 'cures',
                 'prevents', 'recommended', 'prescribe', 'binding', 'affinity', 'inhibition', 'activation',
                 'regulation', 'drives', 'induction', 'shelf life', 'process safety', 'reaction order', 'truth', 'physical validity')
        for word in words:
            self.evidence()
            self.documents['report']['claims'][0].update(kind='descriptive', text='Synthetic ' + word)
            with self.subTest(word=word), self.assertRaisesRegex(ValueError, '^claim-overreach:'):
                pack.validate_arrhenius_rate_fit_pack(self.save())
        self.documents['report']['headline'] = 'Synthetic safety'
        self.documents['rates']['rows'][0]['rate'] = -1
        with self.assertRaisesRegex(ValueError, '^claim-overreach:'):
            pack.validate_arrhenius_rate_fit_pack(self.save())

    def test_external_alias_path_hash_and_hardlink(self):
        for origin in ('external', 'independent', 'preregistered'):
            self.evidence('observed', 'observed', origin)
            with self.subTest(origin=origin), self.assertRaisesRegex(ValueError, '^external-alias:'):
                pack.validate_arrhenius_rate_fit_pack(self.save())
        alias = self.root / 'aliased-source'
        os.link(self.root / 'rates.json', alias)
        self.documents['evidence']['records'][0]['source']['path'] = alias.name
        with self.assertRaisesRegex(ValueError, '^external-alias:'):
            pack.validate_arrhenius_rate_fit_pack(self.save())

    def test_near_zero_comparison_has_no_absolute_tolerance(self):
        with self.assertRaisesRegex(ValueError, '^reported-number:'):
            pack._same(2e-20, 1e-20, 'small distinct number')
        pack._same(1e-20 * (1 + 1e-10), 1e-20, 'small relative tie')

    def test_cli_success_refusal_arguments_and_help(self):
        command = [sys.executable, str(ROOT / 'scripts/validate_arrhenius_rate_fit_pack.py')]
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
        self.assertEqual(json.loads(success.stdout)['schema'], 'arr-result-v1')
        self.documents['rates']['rows'][0]['rate'] = True
        refused = subprocess.run(command + [str(self.save())], capture_output=True, text=True, timeout=CALL_TIMEOUT)
        self.assertEqual(refused.returncode, 2)
        self.assertTrue(json.loads(refused.stderr)['finding'].startswith('invalid-record:'))


def _seeded_test(case):
    def test(self):
        self.run_case(case)
    return test


for _case in CASES:
    setattr(ArrheniusPackTests, 'test_seed_' + _case['id'].replace('-', '_'), _seeded_test(_case))


if __name__ == '__main__':
    unittest.main()
