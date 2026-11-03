"""Offline synthetic factorial acceptance, seeded defects and hostile input checks."""
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

from codex_science import factorial_doe_pack as pack

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'examples/workflow-factorial-doe-effects'
CALL_TIMEOUT = float(os.environ.get('OMS_TEST_CALL_TIMEOUT', '30'))
CASES = json.loads((EXAMPLE / 'negative-cases.json').read_text())['cases']


class DOEPackTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'parent' / 'bundle'
        self.root.mkdir(parents=True)
        self.load_fixture()

    def load_fixture(self, name='full'):
        directory = EXAMPLE / 'fraction' if name == 'fraction' else EXAMPLE
        for item in ('pack', 'rules', 'table', 'report'):
            shutil.copyfile(directory / (item+'.json'), self.root / (item+'.json'))
        self.documents = {name: json.loads((self.root / (name+'.json')).read_text())
                          for name in ('pack', 'rules', 'table', 'report')}
        if name == 'unreplicated':
            for row in self.documents['rules']['runs']:
                row['replicates'] = 1
            for row in self.documents['table']['rows']:
                row['responses'] = [math.fsum(row['responses'])/len(row['responses'])]
            self.refresh_report()
            self.save()

    def refresh_report(self):
        self.documents['report'].update(pack.compute_factorial_effects(
            self.documents['table'], self.documents['rules'], self.documents['report']['coding']))

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
            target = self.root / (name+'.json')
            target.write_text(json.dumps(self.documents[name], sort_keys=True)+'\n')
            identity = {'path': target.name, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
            entry[name] = [identity] if name == 'evidence' else identity
        entry['frozen_rules_sha256'] = entry['rules']['sha256']
        (self.root / 'pack.json').write_text(json.dumps(entry, sort_keys=True)+'\n')
        return self.root / 'pack.json'

    def run_case(self, case):
        self.load_fixture(case['bundle'])
        node = self.documents[case['target']]
        for key in case['path'][:-1]:
            node = node[key]
        if case['remove']:
            del node[case['path'][-1]]
        else:
            node[case['path'][-1]] = copy.deepcopy(case['value'])
        with self.assertRaisesRegex(ValueError, '^'+case['finding']+':'):
            pack.validate_factorial_doe_pack(self.save())

    def test_full_fixture_hand_contrasts_pure_error_and_curvature(self):
        result = pack.validate_factorial_doe_pack(self.root / 'pack.json')
        expected = json.loads((EXAMPLE / 'expected.json').read_text())['computation']
        self.assertEqual(result['computation'], expected)
        computation = result['computation']
        effects = {row['terms'][0]['term']: row for row in computation['alias_sets']}
        self.assertEqual({key: row['estimate'] for key, row in effects.items()},
                         {'I': 10, 'A': 2, 'B': -3, 'C': 0, 'AB': 1.5, 'AC': 0, 'BC': 0, 'ABC': .5})
        self.assertEqual(computation['pure_error'], {'df': 9, 'sum_squares': 18, 'variance': 2})
        self.assertAlmostEqual(effects['A']['standard_error'], math.sqrt(2/16))
        self.assertAlmostEqual(effects['A']['interval']['upper'], 2+2.262157162798205*math.sqrt(2/16), places=11)
        curvature = computation['curvature']
        self.assertEqual(curvature['estimate'], 4)
        self.assertAlmostEqual(curvature['standard_error'], math.sqrt(2*(1/2+1/16)))
        self.assertEqual(curvature['departure'], 'detected')
        self.assertEqual(result['review'], 'unavailable')
        self.assertEqual(result['stages'], list(pack.STAGES))

    def test_fraction_fixture_hand_alias_sets(self):
        self.load_fixture('fraction')
        result = pack.validate_factorial_doe_pack(self.root / 'pack.json')['computation']
        expected = json.loads((EXAMPLE / 'fraction/expected.json').read_text())['computation']
        self.assertEqual(result, expected)
        aliases = {tuple(term['term'] for term in row['terms']): row['estimate'] for row in result['alias_sets']}
        self.assertEqual(aliases, {('I','ABCD'):20, ('A','BCD'):4, ('B','ACD'):-2, ('C','ABD'):0,
                                   ('D','ABC'):0, ('AB','CD'):3, ('AC','BD'):0, ('AD','BC'):0})
        self.assertEqual(result['pure_error'], {'df':8, 'sum_squares':16, 'variance':2})
        self.assertEqual(result['curvature'], 'unavailable')

    def test_negative_generator_sign_and_exploratory_coding(self):
        self.load_fixture('fraction')
        self.documents['rules']['design']['generators'][0]['sign'] = -1
        for rows in (self.documents['rules']['runs'], self.documents['table']['rows']):
            for row in rows:
                row['levels'][3] *= -1
        self.refresh_report()
        result = pack.validate_factorial_doe_pack(self.save())['computation']
        self.assertEqual(result['alias_sets'][0]['terms'], [{'term':'I','sign':1}, {'term':'ABCD','sign':-1}])
        self.documents['report'].update(exploratory=True, coding={'A':-1, 'B':1, 'C':1, 'D':1})
        self.refresh_report()
        result = pack.validate_factorial_doe_pack(self.save())
        self.assertTrue(result['exploratory'])
        self.assertEqual(result['computation']['alias_sets'][1]['estimate'], -4)

    def test_no_replicates_and_significance_wording(self):
        self.load_fixture('unreplicated')
        result = pack.validate_factorial_doe_pack(self.save())['computation']
        self.assertEqual(result['pure_error']['df'], 0)
        for row in result['alias_sets']:
            self.assertEqual(row['interval'], 'unavailable')
            self.assertEqual(row['standard_error'], 'unavailable')
        self.assertEqual(result['curvature']['interval'], 'unavailable')
        for wording in ('significant contrasts', 'p-value below threshold', 'reject null'):
            self.documents['report']['headline'] = 'Synthetic fixture '+wording
            with self.assertRaisesRegex(ValueError, '^inference-without-replicates:'):
                pack.validate_factorial_doe_pack(self.save())

    def test_t_quantiles_against_closed_forms(self):
        for level in (.5, .95, .999):
            self.assertAlmostEqual(pack.student_t_critical(1, level), math.tan(math.pi*level/2), places=7)
            self.assertAlmostEqual(pack.student_t_critical(2, level), math.sqrt(2*level*level/(1-level*level)), places=8)
        self.assertAlmostEqual(pack.student_t_critical(8), 2.306004135204166, places=11)
        self.assertGreater(pack.student_t_critical(pack.MAX_OBSERVATIONS), 1.95)
        for df in (0, -1, True, 2.0, '2', [], pack.MAX_OBSERVATIONS+1):
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.student_t_critical(df)
        for level in (0, .499, 1, True, '0.95', float('inf')):
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.student_t_critical(2, level)
        for constant in ('MAX_ITERATIONS', 'QUANTILE_STEPS'):
            with patch.object(pack, constant, 0), self.assertRaisesRegex(ValueError, '^t-convergence:'):
                pack.student_t_critical(2)

    def test_integer_fields_types_and_degenerate_error(self):
        targets = [(self.documents['rules'], 'randomisation_seed'), (self.documents['rules']['design'], 'resolution'),
                   (self.documents['rules']['runs'][0], 'replicates'), (self.documents['table']['rows'][0]['levels'], 0)]
        for row, field in targets:
            original = row[field]
            for value in (True, float(original), str(original), [], None):
                row[field] = value
                with self.subTest(field=field,value=value), self.assertRaisesRegex(ValueError, '^(invalid-record|coded-levels):'):
                    pack.compute_factorial_effects(self.documents['table'], self.documents['rules'])
            row[field] = original
        self.load_fixture('fraction')
        row = self.documents['rules']['design']['generators'][0]
        for value in (True, 1.0, '1', [], 0):
            row['sign'] = value
            with self.assertRaisesRegex(ValueError, '^(invalid-record|fraction-generators):'):
                pack.compute_factorial_effects(self.documents['table'], self.documents['rules'])
        self.load_fixture()
        for row in self.documents['table']['rows']:
            row['responses'] = [1,1]
        with self.assertRaisesRegex(ValueError, '^degenerate-error:'):
            pack.compute_factorial_effects(self.documents['table'], self.documents['rules'])
        for row in self.documents['table']['rows']:
            row['responses'] = [0.1, 0.3 - 0.2]
        with self.assertRaisesRegex(ValueError, '^degenerate-error:'):
            pack.compute_factorial_effects(self.documents['table'], self.documents['rules'])

    def test_table_identity_counts_resolution_and_response_types(self):
        mutations = [('table',['rows',0,'run_id'],'r02','duplicate-run'),
                     ('table',['rows',0,'responses'],[1],'replicate-count'),
                     ('rules',['design','resolution'],3,'fraction-resolution'),
                     ('rules',['effect_rule'],'difference','effect-rule'),
                     ('rules',['error_rule'],'model-residual','error-rule')]
        for target, path, value, code in mutations:
            self.load_fixture()
            node = self.documents[target]
            for key in path[:-1]: node = node[key]
            node[path[-1]] = value
            with self.assertRaisesRegex(ValueError, '^'+code+':'):
                pack.compute_factorial_effects(self.documents['table'], self.documents['rules'])
        self.load_fixture()
        for response in (True, '1', [], None, float('nan'), float('inf')):
            self.documents['table']['rows'][0]['responses'][0] = response
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.compute_factorial_effects(self.documents['table'], self.documents['rules'])

    def test_new_dimension_limits_before_work(self):
        for constant, value in (('MAX_FACTORS',2), ('MAX_RUNS',8), ('MAX_REPLICATES',1), ('MAX_OBSERVATIONS',17)):
            with patch.object(pack, constant, value), self.assertRaisesRegex(ValueError, '^input-limit:'):
                pack.compute_factorial_effects(self.documents['table'], self.documents['rules'])
        with patch.object(pack, 'MAX_OBSERVATIONS',18):
            self.assertEqual(pack.compute_factorial_effects(self.documents['table'], self.documents['rules'])['summary']['observations'],18)
        for value in ([], 0, None, {}, 'rows'):
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack._list(value, 'rows', 2)
        self.assertEqual(pack._list([], 'empty', 0, True), [])
        self.assertEqual(pack._list([1,2], 'edge', 2), [1,2])
        with self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack._list([1,2,3], 'excess', 2)
        raw = json.dumps({'x':[0]*(pack.MAX_ROWS+1)}).encode()
        with self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack._json(raw)
        for constant in ('MAX_RECORDS', 'MAX_ROWS'):
            with patch.object(pack, constant, 0), self.assertRaisesRegex(ValueError, '^input-limit:'):
                pack.validate_factorial_doe_pack(self.root / 'pack.json')

    def test_maximum_design_and_replicate_limits(self):
        self.load_fixture('fraction')
        rules, table = self.documents['rules'], self.documents['table']
        for row in rules['runs']: row['replicates'] = pack.MAX_REPLICATES
        for row in table['rows']: row['responses'] = [1,3]*(pack.MAX_REPLICATES//2)
        result = pack.compute_factorial_effects(table,rules)
        self.assertEqual(result['summary']['observations'],8*pack.MAX_REPLICATES)
        table['rows'][0]['responses'].append(1)
        with self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack.compute_factorial_effects(table,rules)

    def test_full_k_four_and_k_one(self):
        from itertools import product
        import random
        for k in (1,4):
            self.load_fixture()
            rules,table = self.documents['rules'],self.documents['table']
            rules['factors'] = [{'id':chr(65+i),'low':'synthetic low','high':'synthetic high'} for i in range(k)]
            rules['design']['name'] = f'2^{k}'
            rules['runs'] = [{'run_id':f'r{i:02d}','levels':list(level),'replicates':2} for i,level in enumerate(product((-1,1),repeat=k))]
            table['rows'] = [{'run_id':row['run_id'],'levels':row['levels'],'responses':[10+2*row['levels'][0]-1,10+2*row['levels'][0]+1]} for row in rules['runs']]
            table['run_order'] = [row['run_id'] for row in rules['runs']]
            random.Random(rules['randomisation_seed']).shuffle(table['run_order'])
            result = pack.compute_factorial_effects(table,rules)
            self.assertEqual(len(result['alias_sets']),2**k)
            self.assertEqual(result['alias_sets'][1]['estimate'],2)
            if k == 4:
                rules['runs'].append({'run_id':'centre','levels':[0]*k,'replicates':2})
                table['rows'].append({'run_id':'centre','levels':[0]*k,'responses':[9,11]})
                table['run_order'] = [row['run_id'] for row in rules['runs']]
                random.Random(rules['randomisation_seed']).shuffle(table['run_order'])
                self.assertEqual(pack.compute_factorial_effects(table,rules)['summary']['centre_runs'],1)
                self.assertEqual(len(table['rows']),pack.MAX_RUNS)
            rules['factors'].append({'id':chr(65+k),'low':'synthetic low','high':'synthetic high'})
            with self.assertRaises(ValueError): pack.compute_factorial_effects(table,rules)

    def test_lstat_ancestor_swap_and_root_swap(self):
        real_lstat = os.lstat
        for component in ('parent', 'bundle'):
            target = self.root.parent if component == 'parent' else self.root
            parked = target.with_name(component+'-parked')
            swapped = False
            def swap(name, *args, **kwargs):
                nonlocal swapped
                before = real_lstat(name, *args, **kwargs)
                if name == component and not swapped:
                    swapped = True
                    target.rename(parked)
                    target.symlink_to(parked, target_is_directory=True)
                return before
            try:
                with patch.object(pack.os, 'lstat', side_effect=swap), self.assertRaisesRegex(ValueError, '^input-root:'):
                    pack.validate_factorial_doe_pack(self.root/'pack.json')
            finally:
                if swapped:
                    target.unlink()
                    parked.rename(target)

    def test_integer_report_and_interval_fields(self):
        targets = [(self.documents['report']['pure_error'],'df'),
                   (self.documents['report']['summary'],'observations'),
                   (self.documents['report']['summary'],'factorial_runs'),
                   (self.documents['report']['summary'],'centre_runs'),
                   (self.documents['report']['alias_sets'][1]['interval'],'df'),
                   (self.documents['report']['alias_sets'][1]['terms'][0],'sign')]
        for row, field in targets:
            original = row[field]
            for value in (True, float(original), str(original), []):
                row[field] = value
                with self.subTest(field=field,value=value), self.assertRaisesRegex(ValueError, '^(invalid-record|alias-separation):'):
                    pack.validate_factorial_doe_pack(self.save())
            row[field] = original

    def test_empty_design_lists_and_numeric_bounds(self):
        for target, field in ((self.documents['rules'],'factors'),(self.documents['rules'],'runs'),
                              (self.documents['table'],'rows'),(self.documents['table']['rows'][0],'responses'),
                              (self.documents['table'],'run_order')):
            original = target[field]
            for value in ([], 0, {}, None):
                target[field] = value
                with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                    pack.compute_factorial_effects(self.documents['table'],self.documents['rules'])
            target[field] = original
        for seed in (0,2**32-1):
            self.documents['rules']['randomisation_seed'] = seed
            self.assertIs(pack._rules(self.documents['rules']),self.documents['rules'])
        for seed in (-1,2**32):
            self.documents['rules']['randomisation_seed'] = seed
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack._rules(self.documents['rules'])
        self.load_fixture()
        for replicas in (0,-1):
            self.documents['rules']['runs'][0]['replicates'] = replicas
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack._rules(self.documents['rules'])

    def test_response_totals_cached_once_per_condition(self):
        rows = self.documents['table']['rows']
        counts = {id(row['responses']):0 for row in rows}
        real_fsum = math.fsum
        def counted(values):
            if id(values) in counts:
                counts[id(values)] += 1
            return real_fsum(values)
        with patch.object(pack.math, 'fsum', side_effect=counted):
            pack.compute_factorial_effects(self.documents['table'],self.documents['rules'])
        self.assertEqual(list(counts.values()),[1]*len(rows))

    def test_centre_curvature_zero_crossing_and_negative(self):
        centre = self.documents['table']['rows'][-1]
        for responses, departure in (([9,11],'not-detected'),([9.5,11.5],'not-detected'),([5,7],'detected')):
            centre['responses'] = responses
            self.refresh_report()
            computation = pack.validate_factorial_doe_pack(self.save())['computation']
            self.assertEqual(computation['curvature']['departure'],departure)
            self.assertEqual(computation['curvature']['estimate'],math.fsum(responses)/2-10)

    def test_near_zero_comparison_has_no_absolute_tolerance(self):
        with self.assertRaisesRegex(ValueError, '^reported-number:'):
            pack._same(2e-20,1e-20,'small distinct coefficient')
        pack._same(1e-20*(1+1e-10),1e-20,'relative tie')

    def test_cli_success_refusal_arguments_and_help(self):
        command = [sys.executable,str(ROOT / 'scripts/validate_factorial_doe_pack.py')]
        for arguments in ([], ['--unknown'], [str(self.root/'pack.json'),'extra'], ['--output','x']):
            result = subprocess.run(command+arguments,capture_output=True,text=True,timeout=CALL_TIMEOUT)
            self.assertEqual(result.returncode,2)
            self.assertEqual(result.stdout,'')
            self.assertTrue(json.loads(result.stderr)['finding'].startswith('invalid-arguments:'))
        result = subprocess.run(command+['--help'],capture_output=True,text=True,timeout=CALL_TIMEOUT)
        self.assertEqual(result.returncode,0)
        self.assertEqual(result.stderr,'')
        self.assertIn('usage:',result.stdout)
        result = subprocess.run(command+[str(self.root/'pack.json')],capture_output=True,text=True,timeout=CALL_TIMEOUT)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['schema'],'doe-result-v1')
        self.documents['table']['rows'][0]['responses'][0] = True
        result = subprocess.run(command+[str(self.save())],capture_output=True,text=True,timeout=CALL_TIMEOUT)
        self.assertEqual(result.returncode,2)
        self.assertTrue(json.loads(result.stderr)['finding'].startswith('invalid-record:'))

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
            pack.validate_factorial_doe_pack(self.root / 'pack.json')
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
            pack.validate_factorial_doe_pack(self.root / 'pack.json')

    def test_final_hash_and_root_recheck(self):
        real_finish = pack._Bundle.finish
        def change(store):
            with (self.root / 'table.json').open('ab') as stream:
                stream.write(b' ')
            return real_finish(store)
        with patch.object(pack._Bundle, 'finish', change), self.assertRaisesRegex(ValueError, '^input-changed:'):
            pack.validate_factorial_doe_pack(self.root / 'pack.json')

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
                    pack.validate_factorial_doe_pack(self.root / 'pack.json')
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
            pack.validate_factorial_doe_pack(self.root / 'pack.json')

    def evidence(self, kind='computed', result='numerical-agreement', origin='internal'):
        identity = self.documents['pack']['table']
        self.documents['evidence'] = {'schema': 'doe-evidence-v1', 'fixture': 'synthetic fixture',
                                     'records': [{'id': 'E1', 'kind': kind, 'result': result, 'origin': origin,
                                                  'source': copy.deepcopy(identity)}]}
        self.documents['report']['claims'] = [{'id': 'C1', 'kind': 'descriptive', 'status': 'supported',
                                               'text': 'Synthetic fixture arithmetic matches the supplied table.',
                                               'evidence': ['E1']}]

    def test_claim_kind_and_result_not_labels(self):
        for kind, result in (('review-approval', 'observed'), ('observed', 'review-approval'),
                             ('computed', 'observed'), ('observed', 'numerical-agreement'),
                             ('observed', 'arithmetic-only'), ('doe-result-v1', 'observed')):
            self.evidence(kind, result)
            with self.subTest(kind=kind, result=result), self.assertRaisesRegex(ValueError, '^non-evidence-support:'):
                pack.validate_factorial_doe_pack(self.save())

    def test_unavailable_mixed_evidence_all_statuses(self):
        for status in sorted(pack.STATUSES - {'unavailable'}):
            self.evidence('unavailable', 'unavailable')
            self.documents['evidence']['records'].append({**self.documents['evidence']['records'][0],
                                                          'id': 'E2', 'kind': 'observed', 'result': 'observed'})
            self.documents['report']['claims'][0].update(status=status, evidence=['E1', 'E2'])
            with self.subTest(status=status), self.assertRaisesRegex(ValueError, '^unavailable-evidence:'):
                pack.validate_factorial_doe_pack(self.save())

    def test_claim_empty_unavailable_replication_and_types(self):
        claim = self.documents['report']['claims'][0]
        claim['status'] = 'supported'
        with self.assertRaisesRegex(ValueError, '^missing-evidence:'):
            pack.validate_factorial_doe_pack(self.save())
        claim.update(status='unavailable', text='Supported synthetic result')
        with self.assertRaisesRegex(ValueError, '^unavailable-positive:'):
            pack.validate_factorial_doe_pack(self.save())
        self.evidence('observed', 'observed')
        self.documents['report']['claims'][0]['status'] = 'replicated'
        with self.assertRaisesRegex(ValueError, '^claim-replication:'):
            pack.validate_factorial_doe_pack(self.save())
        for field in ('status', 'kind', 'id'):
            self.documents['report']['claims'][0][field] = []
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.validate_factorial_doe_pack(self.save())
            self.evidence('observed', 'observed')

    def test_wording_families_and_refusal_order(self):
        words = ('causes', 'mechanism', 'therapeutic', 'clinical', 'efficacy', 'effective', 'treatment', 'cures',
                 'prevents', 'recommended', 'prescribe', 'binding', 'affinity', 'inhibition', 'activation',
                 'regulation', 'drives', 'induction', 'optimal conditions', 'scale-up', 'process validity', 'truth', 'physical validity')
        for word in words:
            self.evidence()
            self.documents['report']['claims'][0].update(kind='descriptive', text='Synthetic ' + word)
            with self.subTest(word=word), self.assertRaisesRegex(ValueError, '^claim-overreach:'):
                pack.validate_factorial_doe_pack(self.save())
        self.documents['report']['headline'] = 'Synthetic optimal conditions'
        self.documents['table']['rows'][0]['responses'][0] = True
        with self.assertRaisesRegex(ValueError, '^claim-overreach:'):
            pack.validate_factorial_doe_pack(self.save())

    def test_external_alias_path_hash_and_hardlink(self):
        for origin in ('external', 'independent', 'preregistered'):
            self.evidence('observed', 'observed', origin)
            with self.subTest(origin=origin), self.assertRaisesRegex(ValueError, '^external-alias:'):
                pack.validate_factorial_doe_pack(self.save())
        alias = self.root / 'aliased-source'
        os.link(self.root / 'table.json', alias)
        self.documents['evidence']['records'][0]['source']['path'] = alias.name
        with self.assertRaisesRegex(ValueError, '^external-alias:'):
            pack.validate_factorial_doe_pack(self.save())



def _seeded_test(case):
    def test(self):
        self.run_case(case)
    return test


for _case in CASES:
    setattr(DOEPackTests, 'test_seed_'+_case['id'].replace('-', '_'), _seeded_test(_case))


if __name__ == '__main__':
    unittest.main()
