"""Synthetic growth arithmetic, public refusals and descriptor-pinned input checks."""
from __future__ import annotations

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

from codex_science import growth_curve_pack as growth


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'examples' / 'workflow-growth-curve'
CLI = ROOT / 'scripts' / 'validate_growth_curve_pack.py'
CALL_TIMEOUT = float(os.environ.get('OMS_TEST_CALL_TIMEOUT', '30'))
CASES = json.loads((FIXTURE / 'negative-cases.json').read_bytes())['cases']


def _read(path):
    return json.loads(path.read_bytes())


def _write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False) + '\n')


def _identity(path):
    return {'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


class _FixtureTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name) / 'fixture'
        shutil.copytree(FIXTURE, self.directory)

    def _refresh(self):
        protocol = _identity(self.directory / 'protocol.json')
        report = _read(self.directory / 'report.json')
        report['protocol_sha256'] = protocol['sha256']
        _write(self.directory / 'report.json', report)
        evidence = _read(self.directory / 'evidence.json')
        for item in evidence['records']:
            source = self.directory / item['source']['path']
            if source.is_file():
                item['source']['sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
        _write(self.directory / 'evidence.json', evidence)
        pack = _read(self.directory / 'pack.json')
        for field in ('protocol', 'data', 'report'):
            pack[field] = _identity(self.directory / (field + '.json'))
        pack['evidence'] = [_identity(self.directory / 'evidence.json')]
        pack['frozen_protocol_sha256'] = protocol['sha256']
        _write(self.directory / 'pack.json', pack)

    def _edit(self, target, path, value):
        file = self.directory / (target + '.json')
        record = _read(file)
        owner = record
        for item in path[:-1]:
            owner = owner[item]
        owner[path[-1]] = value
        _write(file, record)

    def _case(self, case):
        for change in case['changes']:
            self._edit(change['target'], change['path'], change['value'])
        self._refresh()

    def _validate(self):
        return growth.validate_growth_curve_pack(self.directory / 'pack.json')

    def _cli(self, *args):
        return subprocess.run([sys.executable, str(CLI), *map(str, args)],
                              capture_output=True, text=True, timeout=CALL_TIMEOUT)

    def _compute(self):
        return growth.compute_growth_curve(_read(self.directory / 'data.json'), _read(self.directory / 'protocol.json'))


class GrowthReferenceTests(_FixtureTest):
    def test_accepting_fixture(self):
        result = self._validate()
        self.assertEqual('offline-arithmetic-only', result['status'])
        self.assertEqual('unavailable', result['review'])
        self.assertEqual(list(growth.STAGES), result['stages'])
        self.assertEqual(_read(self.directory / 'report.json')['computation'], result['computation'])

    def test_hand_derived_logistic_descriptors_and_group_errors(self):
        result = self._compute()
        expected = _read(self.directory / 'expected.json')
        generator = expected['logistic_generator']
        data = _read(self.directory / 'data.json')
        for row, scale in zip(data['wells'][2:5], (1, .75, 2)):
            for time, observed in zip(row['times'], row['od']):
                generated = scale * generator['carrying_capacity'] / (1 + math.exp(-generator['rate'] * (time - generator['midpoint'])))
                self.assertAlmostEqual(generated, observed - .05)
        for name, value in expected['reference_A1'].items():
            self.assertAlmostEqual(value, result['wells'][0]['parameters'][name]['value'])
        self.assertNotAlmostEqual(math.log(2), result['wells'][0]['parameters']['maximum_specific_growth_rate']['value'])
        group = result['groups'][0]['parameters']
        for name, mean, error in [('carrying_capacity', .7, .1), ('area_under_curve', 1.75, .25)]:
            self.assertAlmostEqual(mean, group[name]['mean'])
            self.assertAlmostEqual(error, group[name]['standard_error'])
            self.assertEqual(2, group[name]['n'])
            self.assertEqual(1, group[name]['n_biological_units'])
            self.assertEqual(['A1', 'A2'], group[name]['well_ids'])
        self.assertEqual('unavailable', group['doubling_time']['standard_error'])
        for row, reason in zip(result['wells'][2:], ['saturation', 'non-converged']):
            for item in row['parameters'].values():
                self.assertEqual('unreliable', item['status'])
                self.assertEqual(reason, item['reason'])

    def test_exploratory_window_is_recomputed(self):
        protocol = _read(self.directory / 'protocol.json')
        protocol['window_points'] = 2
        report = _read(self.directory / 'report.json')
        report.update(exploratory=True, window_points=2, computation=growth.compute_growth_curve(_read(self.directory / 'data.json'), protocol))
        _write(self.directory / 'report.json', report)
        self._refresh()
        self.assertTrue(self._validate()['exploratory'])

    def test_saturation_equality_too_few_and_qc_flags(self):
        protocol = _read(self.directory / 'protocol.json')
        data = _read(self.directory / 'data.json')
        protocol['linear_range_upper'] = max(data['wells'][4]['od'])
        result = growth.compute_growth_curve(data, protocol)
        self.assertEqual('reliable', result['wells'][2]['parameters']['carrying_capacity']['status'])
        protocol['minimum_points'] = 6
        result = growth.compute_growth_curve(data, protocol)
        self.assertEqual('too-few-points', result['wells'][0]['parameters']['carrying_capacity']['reason'])
        self.assertEqual('unavailable', result['groups'][0]['parameters']['carrying_capacity']['mean'])
        protocol['minimum_points'] = 3
        for flag in ('edge', 'evaporation'):
            data['wells'][2][flag] = True
            result = growth.compute_growth_curve(data, protocol)
            self.assertEqual('declared-qc-flag', result['wells'][0]['parameters']['carrying_capacity']['reason'])
            data['wells'][2][flag] = False
        data['wells'][2]['contamination'] = True
        with self.assertRaisesRegex(ValueError, '^contamination-limit:'):
            growth.compute_growth_curve(data, protocol)
        protocol['maximum_contamination_flags'] = 1
        self.assertEqual('unreliable', growth.compute_growth_curve(data, protocol)['wells'][0]['parameters']['lag_time']['status'])

    def test_nonpositive_and_degenerate_curves(self):
        data = _read(self.directory / 'data.json')
        protocol = _read(self.directory / 'protocol.json')
        data['wells'][2]['od'] = [.25]*5
        result = growth.compute_growth_curve(data, protocol)
        self.assertEqual('unreliable', result['wells'][0]['parameters']['doubling_time']['status'])
        for value in (0, -.01):
            data['wells'][2]['od'][0] = .05 + value
            with self.assertRaisesRegex(ValueError, '^nonpositive-log-od:'):
                growth.compute_growth_curve(data, protocol)
        with self.assertRaisesRegex(ValueError, '^degenerate-window:'):
            growth._slope([0, 0], [1, 2])

    def test_relative_ties_and_near_zero_distinct_slopes(self):
        protocol = _read(self.directory / 'protocol.json')
        protocol.update(window_points=2, minimum_points=2)
        well = {'fit_converged': True, 'contamination': False, 'edge': False, 'evaporation': False}
        # Both slopes are near zero but differ by a factor of four; absolute tie tolerance loses the maximum.
        values = [math.exp(value) for value in (0, 1e-13, 5e-13)]
        protocol['linear_range_upper'] = 2
        result, window = growth._well_parameters([0, 1, 2], values, values, protocol, well)
        self.assertEqual([1, 2], window)
        self.assertGreater(result['maximum_specific_growth_rate']['value'], 3e-13)
        _, window = growth._well_parameters([0, 1, 2], [1, 2, 4], [1, 2, 4], dict(protocol, linear_range_upper=5), well)
        self.assertEqual([0, 1], window)
        with self.assertRaisesRegex(ValueError, '^reported-number:'):
            growth._compare(2e-30, 1e-30)

    def test_all_seeded_refusals_through_cli(self):
        for case in CASES:
            with self.subTest(case=case['name']):
                shutil.rmtree(self.directory)
                shutil.copytree(FIXTURE, self.directory)
                self._case(case)
                result = self._cli(self.directory / 'pack.json')
                self.assertEqual(2, result.returncode)
                self.assertEqual('', result.stdout)
                self.assertTrue(json.loads(result.stderr)['finding'].startswith(case['finding'] + ':'))
                self.assertNotIn('Traceback', result.stderr)


class GrowthSeededTests(_FixtureTest):
    pass


def _seeded(case):
    def test(self):
        self._case(case)
        with self.assertRaisesRegex(ValueError, '^' + case['finding'] + ':'):
            self._validate()
    return test


for _case_record in CASES:
    setattr(GrowthSeededTests, 'test_' + _case_record['name'].replace('-', '_'), _seeded(_case_record))


class GrowthClaimTests(_FixtureTest):
    def test_wording_families_all_statuses_and_unhashable_fields(self):
        words = ['causal', 'mechanistic', 'therapeutic', 'clinical', 'efficacy', 'effective', 'treatment', 'cure', 'prevention', 'recommendation', 'prescribing', 'binding', 'affinity', 'inhibition', 'activation', 'regulation', 'drives', 'induced', 'fitness', 'resistance', 'drug effect', 'physical validity', 'truth']
        for status in growth.STATUSES:
            for word in words:
                with self.subTest(status=status, word=word), self.assertRaisesRegex(ValueError, '^claim-overreach:'):
                    growth._claims([{'id':'C','kind':'descriptive','status':status,'text':word,'evidence':[]}], {})
        claim = {'id':'C','kind':'descriptive','status':'unavailable','text':'Evidence unavailable.','evidence':[]}
        for field in ('id','kind','status','text'):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, '^invalid-record:'):
                growth._claims([dict(claim, **{field:[]})], {})

    def test_positive_record_kind_and_result_and_unavailable_mixture(self):
        claim = {'id':'C','kind':'descriptive','status':'supported','text':'Synthetic fixture OD increased.','evidence':['E']}
        record = {'kind':'observed','result':'observed'}
        for status in growth.POSITIVE:
            for field in ('kind','result'):
                for label in ('review-approval','computed','numerical-agreement'):
                    with self.subTest(status=status, field=field, label=label), self.assertRaisesRegex(ValueError, '^non-evidence-support:'):
                        growth._claims([dict(claim, status=status)], {'E':dict(record, **{field:label})})
        for status in growth.STATUSES - {'unavailable'}:
            for field in ('kind','result'):
                with self.subTest(status=status, field=field), self.assertRaisesRegex(ValueError, '^unavailable-evidence:'):
                    growth._claims([dict(claim, status=status, evidence=['E','F'])], {'E':record,'F':dict(record, **{field:'unavailable'})})
        with self.assertRaisesRegex(ValueError, '^claim-replication:'):
            growth._claims([dict(claim,status='replicated')], {'E':record})

    def test_arithmetic_status_and_result_schema_cannot_support_positive_claims(self):
        for field in ('kind', 'result'):
            for label in ('arithmetic-only', 'growth-result-v1'):
                self._edit('evidence', ['records', 0, 'kind'], 'observed')
                self._edit('evidence', ['records', 0, 'result'], 'observed')
                self._edit('evidence', ['records', 0, field], label)
                record = _read(self.directory / 'evidence.json')['records'][0]
                self._edit('report', ['claims', 0, 'evidence'], [record['id']])
                self._edit('report', ['claims', 0, 'status'], 'unsupported')
                self._refresh()
                self._validate()
                for status in growth.POSITIVE:
                    with self.subTest(field=field, label=label, status=status):
                        self._edit('report', ['claims', 0, 'status'], status)
                        self._refresh()
                        with self.assertRaisesRegex(ValueError, '^non-evidence-support:'):
                            self._validate()

    def test_external_identity_aliases_and_boundary_order(self):
        for origin in ('external','independent','preregistered'):
            self._edit('evidence',['records',0,'origin'],origin)
            self._refresh()
            with self.assertRaisesRegex(ValueError, '^external-alias:'):
                self._validate()
        shutil.copyfile(self.directory / 'data.json', self.directory / 'other.json')
        self._edit('evidence',['records',0,'source','path'],'other.json')
        self._edit('report',['computation','groups',0,'parameters','carrying_capacity','mean'],1)
        self._refresh()
        with self.assertRaisesRegex(ValueError, '^external-alias:'):
            self._validate()


class GrowthInputTests(_FixtureTest):
    def test_reads_once_and_rechecks_once_per_inode(self):
        reads = []
        original = os.fdopen
        def opened(fd, *args, **kwargs):
            handle = original(fd, *args, **kwargs)
            read = handle.read
            def tracked(*args, **kwargs):
                reads.append(os.fstat(handle.fileno()).st_ino)
                return read(*args, **kwargs)
            handle.read = tracked
            return handle
        with patch.object(growth.os, 'fdopen', opened):
            self._validate()
        self.assertEqual(10, len(reads))
        self.assertEqual(5, len(set(reads)))
        for identity in set(reads):
            self.assertEqual(2, reads.count(identity))

    def test_cli_argument_success_help_and_refusal_channels(self):
        result = self._cli(self.directory / 'pack.json')
        self.assertEqual(0, result.returncode)
        self.assertEqual('', result.stderr)
        self.assertEqual('offline-arithmetic-only', json.loads(result.stdout)['status'])
        for args in ([], ['--unknown'], [str(self.directory/'pack.json'),'extra'], ['--output','x']):
            result = self._cli(*args)
            self.assertEqual(2, result.returncode)
            self.assertEqual('', result.stdout)
            self.assertTrue(json.loads(result.stderr)['finding'].startswith('invalid-arguments:'))
        result = self._cli('--help')
        self.assertEqual(0, result.returncode)
        self.assertIn('bundle', result.stdout)
        self.assertEqual('', result.stderr)

    def test_nonregular_symlink_and_oversized_inputs(self):
        file = self.directory / 'protocol.json'
        raw = file.read_bytes()
        for kind in ('fifo','directory','symlink','oversize'):
            with self.subTest(kind=kind):
                file.unlink()
                if kind == 'fifo':
                    os.mkfifo(file)
                elif kind == 'directory':
                    file.mkdir()
                elif kind == 'symlink':
                    file.symlink_to('data.json')
                else:
                    with file.open('wb') as handle:
                        handle.truncate(growth.MAX_BYTES + 1)
                result = self._cli(self.directory / 'pack.json')
                self.assertEqual(2, result.returncode)
                self.assertTrue(json.loads(result.stderr)['finding'].startswith('input-file:'))
                if file.is_dir():
                    file.rmdir()
                else:
                    file.unlink()
                file.write_bytes(raw)

    def test_canonical_paths_hashes_and_symlink_components(self):
        for name in ('../data.json','/data.json','a\\b','./data.json','a//b','a/../b',''):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, '^(input-path|invalid-record):'):
                growth._relative(name)
        pack = _read(self.directory / 'pack.json')
        for digest in (None, [], 'x', '0'*64):
            pack['protocol']['sha256'] = digest
            _write(self.directory / 'pack.json', pack)
            with self.subTest(digest=digest), self.assertRaisesRegex(ValueError, '^input-hash:'):
                self._validate()
        self._refresh()
        (self.directory / 'linked').symlink_to(self.directory, target_is_directory=True)
        pack = _read(self.directory/'pack.json')
        pack['protocol']['path'] = 'linked/protocol.json'
        _write(self.directory/'pack.json',pack)
        with self.assertRaisesRegex(ValueError, '^input-file:'):
            self._validate()

    def test_strict_json_preparse_budget_and_no_findall_allocation(self):
        bad = [b'[]', b'{"a":1,"a":2}', b'{"a":{"b":1,"b":2}}', b'{"a":NaN}', b'{"a":Infinity}', b'{"a":1e999}', b'{"a":'+b'9'*102+b'}', b'\xff', b'{', b'{"a":'+b'['*1000+b'0'+b']'*1000+b'}']
        for raw in bad:
            with self.subTest(raw=raw[:30]), self.assertRaisesRegex(ValueError, '^invalid-json:'):
                growth._json(raw, growth.MAX_JSON_VALUES)
        with patch.object(growth.re,'findall',side_effect=AssertionError('match-list allocation')):
            self._validate()
        with patch.object(growth,'MAX_DEPTH',0), self.assertRaisesRegex(ValueError, '^invalid-json:'):
            self._validate()
        raw = b'{"x":[1,2]}'
        _, count = growth._json(raw, 4)
        self.assertEqual(4,count)
        for allowance in (0,3):
            with self.assertRaisesRegex(ValueError, '^input-limit:'):
                growth._json(raw, allowance)

    def test_aggregate_budgets_equality_zero_and_hardlink_cache(self):
        names = ['pack.json','protocol.json','data.json','report.json','evidence.json']
        total = sum((self.directory/name).stat().st_size for name in names)
        for budget in (0,total-1):
            with patch.object(growth,'MAX_TOTAL_BYTES',budget), self.assertRaisesRegex(ValueError,'^input-limit:'):
                self._validate()
        with patch.object(growth,'MAX_TOTAL_BYTES',total):
            self._validate()
        with patch.object(growth,'MAX_JSON_VALUES',0), self.assertRaisesRegex(ValueError,'^input-limit:'):
            self._validate()
        counts = []
        original = growth._json
        def parsed(raw, allowance):
            result = original(raw, allowance)
            counts.append(result[1])
            return result
        with patch.object(growth,'_json',parsed):
            self._validate()
        self.assertEqual(5,len(counts))
        with patch.object(growth,'MAX_JSON_VALUES',sum(counts)):
            self._validate()
        with patch.object(growth,'MAX_JSON_VALUES',sum(counts)-1), self.assertRaisesRegex(ValueError,'^input-limit:'):
            self._validate()
        os.link(self.directory/'data.json', self.directory/'alias.json')
        store = growth._Bundle(self.directory)
        try:
            with patch.object(growth,'_json',parsed):
                first = store.load('data.json')
                second = store.load('alias.json')
            self.assertIs(first,second)
            self.assertEqual((self.directory/'data.json').stat().st_size,store.total_bytes)
            self.assertEqual(6,len(counts))
            store.finish()
        finally:
            store.close()

    def test_root_and_ancestor_swap_between_lstat_and_open(self):
        original = os.open
        for name in (self.directory.name,self.directory.parent.name):
            fired = []
            target = self.directory if name == self.directory.name else self.directory.parent
            moved = target.with_name(target.name+'-moved')
            def opened(path, flags, *args, **kwargs):
                if path == name and not fired:
                    fired.append(True)
                    target.rename(moved)
                    target.symlink_to(moved, target_is_directory=True)
                return original(path, flags, *args, **kwargs)
            try:
                with patch.object(growth.os,'open',opened), self.assertRaisesRegex(ValueError,'^input-root:'):
                    self._validate()
                self.assertTrue(fired)
            finally:
                if fired:
                    target.unlink()
                    moved.rename(target)

    def test_parent_replaced_while_bundle_inode_is_preserved(self):
        original = growth._Bundle.finish
        parent = self.directory.parent
        moved = parent.with_name(parent.name+'-saved')
        def finish(store):
            parent.rename(moved)
            parent.mkdir()
            (moved/self.directory.name).rename(self.directory)
            return original(store)
        try:
            with patch.object(growth._Bundle,'finish',finish), self.assertRaisesRegex(ValueError,'^input-root:'):
                self._validate()
        finally:
            if moved.exists():
                self.directory.rename(moved/self.directory.name)
                parent.rmdir()
                moved.rename(parent)

    def test_directory_replaced_after_lstat_and_root_replaced_at_finish(self):
        original_lstat = os.lstat
        original_finish = growth._Bundle.finish
        saved = self.directory.with_name('saved-fixture')
        changed = []
        def inspected(name, *args, **kwargs):
            result = original_lstat(name, *args, **kwargs)
            if name == self.directory.name and not changed:
                changed.append(True)
                self.directory.rename(saved)
                self.directory.mkdir()
            return result
        try:
            with patch.object(growth.os, 'lstat', inspected), self.assertRaisesRegex(ValueError, '^input-root:'):
                self._validate()
        finally:
            if saved.exists():
                self.directory.rmdir()
                saved.rename(self.directory)
        def finish(store):
            self.directory.rename(saved)
            self.directory.mkdir()
            return original_finish(store)
        try:
            with patch.object(growth._Bundle, 'finish', finish), self.assertRaisesRegex(ValueError, '^input-root:'):
                self._validate()
        finally:
            if saved.exists():
                self.directory.rmdir()
                saved.rename(self.directory)

    def test_well_identity_blank_controls_and_strict_grids(self):
        data = _read(self.directory/'data.json')
        protocol = _read(self.directory/'protocol.json')
        for name in ('well','times','od','contamination','fit_converged'):
            broken = json.loads(json.dumps(data))
            broken['wells'][2][name] = [] if name not in ('times','od') else [True]
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, '^(invalid-record|time-grid):'):
                growth.compute_growth_curve(broken, protocol)
        broken = json.loads(json.dumps(data))
        broken['wells'][2]['well'] = 'B1'
        with self.assertRaisesRegex(ValueError, '^well-identity:'):
            growth.compute_growth_curve(broken, protocol)
        for times in ([0,1,1,3,4],[0,2,1,3,4]):
            broken = json.loads(json.dumps(data))
            broken['wells'][0]['times'] = times
            with self.assertRaisesRegex(ValueError, '^time-grid:'):
                growth.compute_growth_curve(broken, protocol)
        # Equality at the declared stability limit passes; an excess refuses.
        data['wells'][0]['od'][-1] = .0625
        protocol['blank_stability'] = .0625-.05
        growth.compute_growth_curve(data, protocol)
        protocol['blank_stability'] = 0
        with self.assertRaisesRegex(ValueError, '^unstable-blank:'):
            growth.compute_growth_curve(data, protocol)

    def test_input_replaced_and_growing_during_read(self):
        original = growth._Bundle.finish
        def finish(store):
            raw = (self.directory/'data.json').read_bytes()
            (self.directory/'data.json').unlink()
            (self.directory/'data.json').write_bytes(raw)
            original(store)
        with patch.object(growth._Bundle,'finish',finish), self.assertRaisesRegex(ValueError,'^input-changed:'):
            self._validate()
        self._refresh()
        real_fstat = os.fstat
        calls = {}
        def growing(fd):
            info = real_fstat(fd)
            if info.st_ino == (self.directory/'protocol.json').stat().st_ino:
                calls[fd] = calls.get(fd,0)+1
                if calls[fd] == 2:
                    with (self.directory/'protocol.json').open('ab') as handle:
                        handle.write(b' ')
                    return real_fstat(fd)
            return info
        with patch.object(growth.os,'fstat',growing), self.assertRaisesRegex(ValueError,'^input-file:'):
            self._validate()

    def test_protocol_freeze_precedes_od_and_repeated_concurrent_calls_write_nothing(self):
        self._edit('pack',['frozen_before_od_read'],False)
        calls = []
        original = growth._Bundle.load
        def load(store,name,*args,**kwargs):
            calls.append(name)
            return original(store,name,*args,**kwargs)
        with patch.object(growth._Bundle,'load',load), self.assertRaisesRegex(ValueError,'^protocol-freeze:'):
            self._validate()
        self.assertNotIn('data.json',calls)
        self._edit('pack',['frozen_before_od_read'],True)
        before = {path.name:path.read_bytes() for path in self.directory.iterdir()}
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self._validate) for _ in range(2)]
            for future in futures:
                self.assertEqual('offline-arithmetic-only',future.result(timeout=CALL_TIMEOUT)['status'])
        after = {path.name:path.read_bytes() for path in self.directory.iterdir()}
        self.assertEqual(before,after)


class GrowthLimitTests(_FixtureTest):
    def test_dimension_limits_equal_zero_empty_malformed_and_oversize(self):
        for constant, equal in [('MAX_WELLS',6),('MAX_POINTS',5),('MAX_RECORDS',5),('MAX_WINDOW_WORK',36)]:
            with self.subTest(constant=constant), patch.object(growth,constant,equal):
                self._validate()
            for limit in (0,equal-1):
                with self.subTest(constant=constant,limit=limit), patch.object(growth,constant,limit), self.assertRaisesRegex(ValueError,'^(input-limit|invalid-record):'):
                    self._validate()
        for values in ([],None,{},'x'):
            self._edit('data',['wells'],values)
            self._refresh()
            with self.subTest(values=values), self.assertRaisesRegex(ValueError,'^invalid-record:'):
                self._validate()
        self._edit('data',['wells'],[{}]*(growth.MAX_WELLS+1))
        self._refresh()
        with self.assertRaisesRegex(ValueError,'^input-limit:'):
            self._validate()
        raw = (self.directory/'protocol.json').read_bytes()
        for limit in (0,len(raw)-1):
            store = growth._Bundle(self.directory)
            try:
                with patch.object(growth,'MAX_BYTES',limit), self.assertRaisesRegex(ValueError,'^input-file:'):
                    store.load('protocol.json')
            finally:
                store.close()
        with patch.object(growth,'MAX_STRING',0), self.assertRaisesRegex(ValueError,'^(input-path|invalid-record):'):
            self._validate()
        with patch.object(growth,'MAX_ITEMS',0), self.assertRaisesRegex(ValueError,'^input-limit:'):
            self._validate()

    def test_every_declared_integer_and_nonfinite_numeric_types(self):
        protocol = _read(self.directory/'protocol.json')
        for name in ('window_points','minimum_points','maximum_contamination_flags','minimum_wells'):
            for value in (True,2.0,'2',-1,0 if name != 'maximum_contamination_flags' else -2):
                with self.subTest(name=name,value=value), self.assertRaisesRegex(ValueError,'^invalid-record:'):
                    growth._protocol(dict(protocol,**{name:value}))
        for value in (True,float('nan'),float('inf'),[],1e101):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError,'^invalid-record:'):
                growth._number(value,'value')
        report = _read(self.directory/'report.json')
        for path in (['window_points'],['computation','groups',0,'parameters','carrying_capacity','n'],['computation','groups',0,'parameters','carrying_capacity','n_biological_units'],['computation','wells',0,'window_indices',0]):
            self._edit('report',path,True)
            self._refresh()
            with self.subTest(path=path), self.assertRaisesRegex(ValueError,'^invalid-record:'):
                self._validate()
            _write(self.directory/'report.json',report)

    def test_metadata_plan_and_named_failure_coverage(self):
        directory = ROOT/'authored-skills'/'workflow-growth-curve'
        quality = _read(directory/'quality.json')
        self.assertEqual('L4',quality['declared_maturity'])
        self.assertEqual({'growth-'+name+'-v1' for name in ['pack','protocol','data','report','evidence','result']},set(quality['output_schemas']))
        self.assertEqual([case['name'] for case in CASES],quality['seeded_failures'])
        self.assertEqual(['tests/test_workflow_growth_pack.py'],quality['test_files'])
        plan = _read(directory/'references'/'plan.json')['plan']
        self.assertEqual(list(growth.STAGES),[step['id'] for step in plan])
        for step in plan:
            self.assertEqual({'id','description','status'},set(step))
        skill = (directory/'SKILL.md').read_text()
        description = skill.split('description: ',1)[1].split('\n',1)[0].lower()
        for generic in ('workflow','analysis','statistics','pipeline'):
            self.assertNotIn(generic,description)
        for file in ('index.json','stages.md','plan.json'):
            self.assertIn('](references/'+file+')',skill)


if __name__ == '__main__':
    unittest.main()
