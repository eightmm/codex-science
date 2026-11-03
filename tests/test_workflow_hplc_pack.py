"""Offline synthetic HPLC arithmetic, claim boundaries and hostile-input checks."""
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

from codex_science import hplc_system_suitability_pack as pack

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'examples/workflow-hplc-system-suitability'
CALL_TIMEOUT = float(os.environ.get('OMS_TEST_CALL_TIMEOUT', '30'))
CASES = json.loads((EXAMPLE / 'negative-cases.json').read_text())['cases']


class HPLCPackTests(unittest.TestCase):
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

    def refresh_report(self, limits=None):
        self.documents['report'].update(pack.compute_suitability(self.documents['table'], self.documents['rules'], limits))

    def run_case(self, case):
        node = self.documents[case['target']]
        for key in case['path'][:-1]:
            node = node[key]
        if case['remove']:
            del node[case['path'][-1]]
        else:
            node[case['path'][-1]] = case['value']
        with self.assertRaisesRegex(ValueError, '^' + case['finding'] + ':'):
            pack.validate_hplc_system_suitability_pack(self.save())

    def evidence(self, kind='computed', result='numerical-agreement', origin='internal'):
        identity = self.documents['pack']['table']
        self.documents['evidence'] = {'schema': 'hplc-evidence-v1', 'fixture': 'synthetic fixture',
                                     'records': [{'id': 'E1', 'kind': kind, 'result': result, 'origin': origin,
                                                  'source': copy.deepcopy(identity)}]}
        self.documents['report']['claims'] = [{'id': 'C1', 'kind': 'descriptive', 'status': 'supported',
                                               'text': 'Synthetic fixture arithmetic matches the supplied table.',
                                               'evidence': ['E1']}]

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
                pack.validate_hplc_system_suitability_pack(self.root / 'pack.json')
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
                pack.validate_hplc_system_suitability_pack(self.root / 'pack.json')

    def test_final_hash_and_root_recheck(self):
            real_finish = pack._Bundle.finish
            def change(store):
                with (self.root / 'table.json').open('ab') as stream:
                    stream.write(b' ')
                return real_finish(store)
            with patch.object(pack._Bundle, 'finish', change), self.assertRaisesRegex(ValueError, '^input-changed:'):
                pack.validate_hplc_system_suitability_pack(self.root / 'pack.json')

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
                        pack.validate_hplc_system_suitability_pack(self.root / 'pack.json')
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
                pack.validate_hplc_system_suitability_pack(self.root / 'pack.json')

    def test_claim_kind_and_result_not_labels(self):
            for kind, result in (('review-approval', 'observed'), ('observed', 'review-approval'),
                                 ('computed', 'observed'), ('observed', 'numerical-agreement'),
                             ('arithmetic-only', 'observed'), ('observed', 'arithmetic-only'), ('hplc-result-v1', 'pass')):
                self.evidence(kind, result)
                with self.subTest(kind=kind, result=result), self.assertRaisesRegex(ValueError, '^non-evidence-support:'):
                    pack.validate_hplc_system_suitability_pack(self.save())

    def test_unavailable_mixed_evidence_all_statuses(self):
            for status in sorted(pack.STATUSES - {'unavailable'}):
                self.evidence('unavailable', 'unavailable')
                self.documents['evidence']['records'].append({**self.documents['evidence']['records'][0],
                                                              'id': 'E2', 'kind': 'observed', 'result': 'observed'})
                self.documents['report']['claims'][0].update(status=status, evidence=['E1', 'E2'])
                with self.subTest(status=status), self.assertRaisesRegex(ValueError, '^unavailable-evidence:'):
                    pack.validate_hplc_system_suitability_pack(self.save())

    def test_claim_empty_unavailable_replication_and_types(self):
            claim = self.documents['report']['claims'][0]
            claim['status'] = 'supported'
            with self.assertRaisesRegex(ValueError, '^missing-evidence:'):
                pack.validate_hplc_system_suitability_pack(self.save())
            claim.update(status='unavailable', text='Supported synthetic result')
            with self.assertRaisesRegex(ValueError, '^unavailable-positive:'):
                pack.validate_hplc_system_suitability_pack(self.save())
            self.evidence('observed', 'observed')
            self.documents['report']['claims'][0]['status'] = 'replicated'
            with self.assertRaisesRegex(ValueError, '^claim-replication:'):
                pack.validate_hplc_system_suitability_pack(self.save())
            for field in ('status', 'kind', 'id'):
                self.documents['report']['claims'][0][field] = []
                with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                    pack.validate_hplc_system_suitability_pack(self.save())
                self.evidence('observed', 'observed')

    def test_external_alias_path_hash_and_hardlink(self):
            for origin in ('external', 'independent', 'preregistered'):
                self.evidence('observed', 'observed', origin)
                with self.subTest(origin=origin), self.assertRaisesRegex(ValueError, '^external-alias:'):
                    pack.validate_hplc_system_suitability_pack(self.save())
            alias = self.root / 'aliased-source'
            os.link(self.root / 'table.json', alias)
            self.documents['evidence']['records'][0]['source']['path'] = alias.name
            with self.assertRaisesRegex(ValueError, '^external-alias:'):
                pack.validate_hplc_system_suitability_pack(self.save())

    def test_near_zero_comparison_has_no_absolute_tolerance(self):
            with self.assertRaisesRegex(ValueError, '^reported-number:'):
                pack._same(2e-20, 1e-20, 'small distinct number')
            pack._same(1e-20 * (1 + 1e-10), 1e-20, 'small relative tie')

    def test_cli_success_refusal_arguments_and_help(self):
            command = [sys.executable, str(ROOT / 'scripts/validate_hplc_system_suitability_pack.py')]
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
            self.assertEqual(json.loads(success.stdout)['schema'], 'hplc-result-v1')
            self.documents['table']['rows'][0]['order'] = True
            refused = subprocess.run(command + [str(self.save())], capture_output=True, text=True, timeout=CALL_TIMEOUT)
            self.assertEqual(refused.returncode, 2)
            self.assertTrue(json.loads(refused.stderr)['finding'].startswith('invalid-record:'))

    def test_fixture_hand_arithmetic(self):
        result = pack.validate_hplc_system_suitability_pack(self.root / 'pack.json')
        expected = json.loads((EXAMPLE / 'expected.json').read_text())['computation']
        self.assertEqual(result['computation'], expected)
        numbers = result['computation']
        self.assertEqual(len(self.documents['table']['rows']), 6)
        self.assertEqual(numbers['replicate_count'], 5)
        # Five times have squared deviations .04+.01+0+.01+.04 = .1, divided by n-1 = 4.
        self.assertAlmostEqual(numbers['replicate_criteria']['retention_time_rsd']['value'], 100 * math.sqrt(.1 / 4) / 5)
        self.assertAlmostEqual(numbers['replicate_criteria']['peak_area_rsd']['value'], 100 * math.sqrt(10 / 4) / 100)
        first = numbers['injections'][0]
        self.assertAlmostEqual(first['plates']['value'], 12764.16)
        self.assertEqual(first['tailing'], {'value': 2, 'status': 'fail'})
        self.assertAlmostEqual(first['resolution']['value'], 2.5)
        self.assertEqual(first['nearest_peak_id'], 'R')
        self.assertEqual(numbers['carryover'][0]['preceding_standard_id'], 's5')
        self.assertEqual(numbers['carryover'][0]['value'], .5)
        self.assertEqual(numbers['summary']['tailing'], 'fail')
        self.assertEqual(numbers['summary']['peak_area_rsd'], 'pass')
        self.assertEqual(result['review'], 'unavailable')
        self.assertEqual(result['stages'], list(pack.STAGES))

    def test_sample_rsd_empty_minimum_and_zero_variance(self):
        for values in ([], [1], [1,2,3,4]):
            self.assertEqual(pack.sample_rsd(values, 5), 'unavailable')
        self.assertAlmostEqual(pack.sample_rsd([1,2,3,4,5], 5), 100 * math.sqrt(2.5) / 3)
        for values in ([1]*5, [0]*5, [float('inf')]*5, [float('nan')]*5, [True]*5, ['1']*5, [None]*5):
            with self.subTest(values=values), self.assertRaisesRegex(ValueError, '^(invalid-record|degenerate-rsd):'):
                pack.sample_rsd(values, 5)
        for minimum in (0, 1, True, 5.0, '5', [], pack.MAX_ROWS+1):
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.sample_rsd([1,2,3,4,5], minimum)

    def test_short_replicates_are_unavailable_and_blank_area_zero(self):
        self.documents['table']['rows'].pop(4)
        self.documents['table']['rows'][-1]['peaks'][0]['area'] = 0
        self.refresh_report()
        result = pack.validate_hplc_system_suitability_pack(self.save())['computation']
        self.assertEqual(result['replicate_count'], 4)
        self.assertEqual(result['replicate_criteria']['peak_area_rsd'], {'value':'unavailable','status':'unavailable'})
        self.assertEqual(result['summary']['retention_time_rsd'], 'unavailable')
        self.assertEqual(result['carryover'][0]['value'], 0)
        self.documents['report']['replicate_criteria']['peak_area_rsd']['value'] = 0
        with self.assertRaisesRegex(ValueError, '^replicate-minimum:'):
            pack.validate_hplc_system_suitability_pack(self.save())

    def test_missing_peaks_and_signal_remain_unavailable(self):
        self.documents['rules']['reference_peak_id'] = None
        for row in self.documents['table']['rows']:
            row['peaks'] = row['peaks'][:1]
            row['peaks'][0]['signal_to_noise'] = None
        self.documents['table']['rows'][-1]['peaks'] = []
        self.refresh_report()
        numbers = pack.validate_hplc_system_suitability_pack(self.save())['computation']
        for key in ('resolution','signal_to_noise','carryover'):
            self.assertEqual(numbers['summary'][key], 'unavailable')
        self.documents['table']['rows'][0]['peaks'] = []
        with self.assertRaisesRegex(ValueError, '^peak-identity:'):
            pack.compute_suitability(self.documents['table'],self.documents['rules'])

    def test_exploratory_limits_and_exact_thresholds(self):
        report = self.documents['report']
        report['exploratory'] = True
        report['applied_limits']['tailing_max'] = 2
        self.refresh_report(report['applied_limits'])
        self.assertEqual(pack.validate_hplc_system_suitability_pack(self.save())['computation']['summary']['tailing'], 'pass')
        for maximum in (False,True):
            self.assertEqual(pack._criterion(2,2,maximum)['status'], 'pass')
            self.assertEqual(pack._criterion(0,0,maximum)['status'], 'pass')
        for key in pack.LIMIT_KEYS:
            limits = copy.deepcopy(self.documents['rules']['limits'])
            limits[key] = 0
            pack._limits(limits)
            for invalid in (-1,True,'0',[],None,float('nan'),float('inf'),1e12+1):
                limits[key] = invalid
                with self.subTest(key=key,invalid=invalid), self.assertRaisesRegex(ValueError,'^invalid-record:'):
                    pack._limits(limits)

    def test_rule_method_types_and_integer_fields(self):
        rules = self.documents['rules']
        for field in ('injection_count','minimum_injections'):
            original = rules[field]
            for invalid in (True,float(original),str(original),[],0,1,pack.MAX_ROWS+1):
                rules[field] = invalid
                with self.subTest(field=field,invalid=invalid), self.assertRaisesRegex(ValueError,'^invalid-record:'):
                    pack.compute_suitability(self.documents['table'],rules)
            rules[field] = original
        for key, invalid, finding in (('rsd_method',[], 'rsd-method'),('plates_width','baseline','plates-method'),
                                      ('plates_constant',True,'plates-method'),('tailing_height',True,'tailing-height'),
                                      ('resolution_width','half-height','resolution-width'),('blank_rule','any-blank','blank-rule')):
            original = rules[key]
            rules[key] = invalid
            with self.assertRaisesRegex(ValueError,'^'+finding+':'):
                pack.compute_suitability(self.documents['table'],rules)
            rules[key] = original
        for invalid in (True,5.0,'5',[],0):
            self.documents['report']['replicate_count'] = invalid
            with self.assertRaisesRegex(ValueError,'^(invalid-record|reported-number):'):
                pack.validate_hplc_system_suitability_pack(self.save())

    def test_identity_order_width_and_blank_controls(self):
        mutations = [('injection_id','s1','duplicate-injection',1),('order',1,'injection-order',1),
                     ('order',True,'invalid-record',0),('kind','blank','blank-replicate',0)]
        for key,value,finding,index in mutations:
            original = self.documents['table']['rows'][index][key]
            self.documents['table']['rows'][index][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError,'^'+finding+':'):
                pack.compute_suitability(self.documents['table'],self.documents['rules'])
            self.documents['table']['rows'][index][key] = original
        peak = self.documents['table']['rows'][0]['peaks'][0]
        for key in ('retention_time','width_half_height','width_five_percent','front_five_percent','width_baseline','area'):
            original = peak[key]
            for invalid in (0,-1,True,[],None,float('inf')):
                peak[key] = invalid
                with self.assertRaisesRegex(ValueError,'^invalid-record:'):
                    pack.compute_suitability(self.documents['table'],self.documents['rules'])
            peak[key] = original
        peak['front_five_percent'] = peak['width_five_percent']
        with self.assertRaisesRegex(ValueError,'^peak-width:'):
            pack.compute_suitability(self.documents['table'],self.documents['rules'])
        peak['front_five_percent'] = .1
        peak['width_half_height'] = .5
        with self.assertRaisesRegex(ValueError,'^peak-width:'):
            pack.compute_suitability(self.documents['table'],self.documents['rules'])
        peak['width_half_height'] = .1
        self.documents['table']['rows'].pop()
        with self.assertRaisesRegex(ValueError,'^blank-rule:'):
            pack.compute_suitability(self.documents['table'],self.documents['rules'])

    def test_blank_requires_immediate_preceding_standard(self):
        rows = self.documents['table']['rows']
        blank = rows.pop()
        blank['order'] = 1
        for row in rows:
            row['order'] += 1
        rows.insert(0,blank)
        with self.assertRaisesRegex(ValueError,'^blank-rule:'):
            pack.compute_suitability(self.documents['table'],self.documents['rules'])

    def test_actual_numbers_recomputed_and_summary_preserved(self):
        report = self.documents['report']
        for field in ('plates','tailing','resolution','signal_to_noise'):
            actual = report['injections'][0][field]
            original = actual['value']
            actual['value'] = original * 1.1
            with self.subTest(field=field), self.assertRaisesRegex(ValueError,'^reported-number:'):
                pack.validate_hplc_system_suitability_pack(self.save())
            actual['value'] = original
        rsd = report['replicate_criteria']['peak_area_rsd']
        rsd['value'] *= math.sqrt(4/5)
        with self.assertRaisesRegex(ValueError,'^reported-number:'):
            pack.validate_hplc_system_suitability_pack(self.save())
        rsd['value'] /= math.sqrt(4/5)
        report['summary']['tailing'] = 'pass'
        with self.assertRaisesRegex(ValueError,'^summary-result:'):
            pack.validate_hplc_system_suitability_pack(self.save())

    def test_collection_limits_before_work(self):
        with patch.object(pack,'MAX_ROWS',5), self.assertRaisesRegex(ValueError,'^input-limit:'):
            pack.compute_suitability(self.documents['table'],self.documents['rules'])
        with patch.object(pack,'MAX_PEAKS',2), self.assertRaisesRegex(ValueError,'^input-limit:'):
            pack.compute_suitability(self.documents['table'],self.documents['rules'])
        with patch.object(pack,'MAX_RECORDS',0), self.assertRaisesRegex(ValueError,'^input-limit:'):
            pack._claims(self.documents['report']['claims'],{})
        with patch.object(pack,'MAX_ROWS',6), patch.object(pack,'MAX_PEAKS',3):
            pack.compute_suitability(self.documents['table'],self.documents['rules'])
        for value in ([],0,None,{},'rows'):
            with self.assertRaisesRegex(ValueError,'^invalid-record:'):
                pack._list(value,'rows',2)
        self.assertEqual(pack._list([1,2],'edge',2),[1,2])
        with self.assertRaisesRegex(ValueError,'^input-limit:'):
            pack._json(json.dumps({'x':[0]*(pack.MAX_ROWS+1)}).encode())

    def test_wording_families_and_refusal_order(self):
        words = ('causes','mechanism','therapeutic','clinical','efficacy','effective','treatment','cures',
                 'prevents','recommended','prescribe','binding','affinity','inhibition','activation',
                 'regulation','drives','induction','truth','physical validity','method validity','method is valid',
                 'system qualification','release','product quality','regulatory status')
        for word in words:
            self.evidence()
            self.documents['report']['claims'][0]['text'] = 'Synthetic '+word
            with self.subTest(word=word), self.assertRaisesRegex(ValueError,'^claim-overreach:'):
                pack.validate_hplc_system_suitability_pack(self.save())
        self.documents['table']['rows'][0]['order'] = -1
        with self.assertRaisesRegex(ValueError,'^claim-overreach:'):
            pack.validate_hplc_system_suitability_pack(self.save())

    def test_freeze_precedes_table_read_and_hash_checks(self):
        self.documents['pack']['frozen_before_table_read'] = False
        path = self.save()
        real_load = pack._Bundle.load
        def guard(store,name,*args,**kwargs):
            if name == 'table.json':
                self.fail('read table before freeze validation')
            return real_load(store,name,*args,**kwargs)
        with patch.object(pack._Bundle,'load',guard), self.assertRaisesRegex(ValueError,'^rule-freeze:'):
            pack.validate_hplc_system_suitability_pack(path)
        self.documents['pack']['frozen_before_table_read'] = True
        self.save()
        with (self.root/'table.json').open('ab') as stream:
            stream.write(b' ')
        with self.assertRaisesRegex(ValueError,'^input-hash:'):
            pack.validate_hplc_system_suitability_pack(path)


    def test_empty_zero_equal_and_malformed_limits(self):
        self.assertEqual(pack._json(b'{}')[0], {})
        with patch.object(pack,'MAX_STRING',4):
            self.assertEqual(pack._text('four','edge'),'four')
        for value in ('',0,True,[],{},None):
            with self.assertRaisesRegex(ValueError,'^invalid-record:'):
                pack._text(value,'text')
        with patch.object(pack,'MAX_DEPTH',1):
            self.assertEqual(pack._json(b'{"x":1}')[0],{'x':1})
        with patch.object(pack,'MAX_DEPTH',0), self.assertRaisesRegex(ValueError,'^invalid-json:'):
            pack._json(b'{"x":1}')
        with patch.object(pack,'MAX_ROWS',1):
            self.assertEqual(pack._json(b'{"x":[1]}')[0],{'x':[1]})
        with patch.object(pack,'MAX_ROWS',0), self.assertRaisesRegex(ValueError,'^input-limit:'):
            pack._json(b'{"x":[1]}')
        claim=self.documents['report']['claims']
        with patch.object(pack,'MAX_RECORDS',1):
            pack._claims(claim,{})
        pack._claims([],{})
        (self.root/'tiny').write_bytes(b'x')
        for constant in ('MAX_BYTES','MAX_TOTAL_BYTES'):
            with patch.object(pack,constant,0):
                store=pack._Bundle(self.root)
                try:
                    with self.assertRaisesRegex(ValueError,'^(input-file|input-limit):'):
                        store.load('tiny',parse=False)
                finally:
                    store.close()
        for invalid in (None,[],{},0,True):
            with self.assertRaisesRegex(ValueError,'^input-path:'):
                pack.validate_hplc_system_suitability_pack(invalid)

    def test_peak_identity_width_fields_and_reference(self):
        rows=self.documents['table']['rows']
        original=copy.deepcopy(rows[0]['peaks'])
        rows[0]['peaks'].append(copy.deepcopy(rows[0]['peaks'][0]))
        with self.assertRaisesRegex(ValueError,'^peak-identity:'):
            pack.compute_suitability(self.documents['table'],self.documents['rules'])
        rows[0]['peaks']=copy.deepcopy(original)
        del rows[0]['peaks'][0]['width_five_percent']
        with self.assertRaisesRegex(ValueError,'^invalid-record:'):
            pack.compute_suitability(self.documents['table'],self.documents['rules'])
        rows[0]['peaks']=original[:1]
        with self.assertRaisesRegex(ValueError,'^peak-identity:'):
            pack.compute_suitability(self.documents['table'],self.documents['rules'])
        self.documents['rules']['reference_peak_id']='A'
        with self.assertRaisesRegex(ValueError,'^peak-identity:'):
            pack.compute_suitability(self.documents['table'],self.documents['rules'])
        self.documents['rules']['reference_peak_id']=None
        rows[0]['peaks']=original
        rows[0]['peaks'][1]['retention_time']=original[0]['retention_time']
        numbers=pack.compute_suitability(self.documents['table'],self.documents['rules'])
        self.assertEqual(numbers['injections'][0]['resolution'],{'value':0,'status':'fail'})
        rows[0]['peaks'][0]['signal_to_noise']=0
        self.assertEqual(pack.compute_suitability(self.documents['table'],self.documents['rules'])['injections'][0]['signal_to_noise']['status'],'fail')

    def test_decimal_distance_tie_uses_first_neighbor(self):
        peaks = self.documents['table']['rows'][0]['peaks']
        for peak, time in zip(peaks, (0.2, 0.1, 0.3)):
            peak.update(retention_time=time, width_baseline=0.05)
        peaks[2]['width_baseline'] = 0.5
        self.documents['rules']['reference_peak_id'] = None
        numbers = pack.compute_suitability(self.documents['table'], self.documents['rules'])
        self.assertEqual(numbers['injections'][0]['nearest_peak_id'], peaks[1]['peak_id'])
        self.assertAlmostEqual(numbers['injections'][0]['resolution']['value'], 2.0)

    def test_nearer_peak_wins_over_relative_near_tie(self):
        peaks = self.documents['table']['rows'][0]['peaks']
        for peak, time, width in zip(peaks, (0.2, 0.09999999995, 0.3), (0.05, 0.05, 0.5)):
            peak.update(retention_time=time, width_baseline=width)
        self.documents['rules']['reference_peak_id'] = None
        record = pack.compute_suitability(self.documents['table'], self.documents['rules'])['injections'][0]
        self.assertEqual(record['nearest_peak_id'], peaks[2]['peak_id'])
        self.assertAlmostEqual(record['resolution']['value'], 0.2 / 0.55, places=9)
        self.assertEqual(record['resolution']['status'], 'fail')

    def test_roundoff_replicate_spread_is_degenerate_rsd(self):
        with self.assertRaisesRegex(ValueError, '^degenerate-rsd:'):
            pack.sample_rsd([0.1, 0.3 - 0.2, 0.1, 0.3 - 0.2, 0.1], 5)

    def test_lstat_race_and_final_root_replacement(self):
        real_lstat=os.lstat
        component=self.root.name
        parked=self.root.with_name('parked')
        swapped=False
        def swap(name,*args,**kwargs):
            nonlocal swapped
            result=real_lstat(name,*args,**kwargs)
            if name==component and not swapped:
                swapped=True
                self.root.rename(parked)
                self.root.mkdir()
            return result
        with patch.object(pack.os,'lstat',side_effect=swap), self.assertRaisesRegex(ValueError,'^input-root:'):
            pack.validate_hplc_system_suitability_pack(self.root/'pack.json')
        self.root.rmdir()
        parked.rename(self.root)
        real_finish=pack._Bundle.finish
        def replace(store):
            self.root.rename(parked)
            self.root.mkdir()
            return real_finish(store)
        with patch.object(pack._Bundle,'finish',replace), self.assertRaisesRegex(ValueError,'^input-root:'):
            pack.validate_hplc_system_suitability_pack(self.root/'pack.json')

    def test_blank_controls_and_frozen_count(self):
        rules=self.documents['rules']
        rules['blank_ids']=['s1']
        with self.assertRaisesRegex(ValueError,'^blank-replicate:'):
            pack.compute_suitability(self.documents['table'],rules)
        rules['blank_ids']=['b1']
        rules['standard_ids'].pop()
        with self.assertRaisesRegex(ValueError,'^injection-count:'):
            pack.compute_suitability(self.documents['table'],rules)
        rules['standard_ids'].append('s5')
        rules['blank_ids'].append('b2')
        self.documents['table']['rows'].append({'injection_id':'b2','order':7,'kind':'blank','peaks':[]})
        with self.assertRaisesRegex(ValueError,'^blank-rule:'):
            pack.compute_suitability(self.documents['table'],rules)
        self.documents['table']['rows']=[]
        with self.assertRaisesRegex(ValueError,'^invalid-record:'):
            pack.compute_suitability(self.documents['table'],rules)


def _seeded_test(case):
    def test(self):
        self.run_case(case)
    return test


for _case in CASES:
    setattr(HPLCPackTests,'test_seed_'+_case['id'].replace('-','_'),_seeded_test(_case))


if __name__ == '__main__':
    unittest.main()
