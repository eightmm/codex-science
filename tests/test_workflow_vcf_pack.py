"""Offline synthetic callset QC acceptance and individually seeded refusal controls."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from codex_science import callset_qc_pack as qc

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'examples/workflow-callset-qc'
CASES = json.loads((FIXTURE / 'negative-cases.json').read_text())['cases']
CALL_TIMEOUT = float(os.environ.get('OMS_TEST_CALL_TIMEOUT', '60'))


class CallsetQCTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name) / 'bundle'
        shutil.copytree(FIXTURE, self.root)

    def read(self, name):
        return json.loads((self.root / name).read_bytes())

    def write(self, name, value):
        raw = (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()
        (self.root / name).write_bytes(raw)
        return {'path': name, 'sha256': hashlib.sha256(raw).hexdigest()}

    def identity(self, name):
        return {'path': name, 'sha256': hashlib.sha256((self.root / name).read_bytes()).hexdigest()}

    def refresh(self, frozen=True):
        pack = self.read('pack.json')
        for key, name in [('rules', 'rules.json'), ('table', 'table.json'), ('qc', 'qc.json')]:
            pack['inputs'][key] = self.identity(name)
        if frozen:
            pack['freeze']['rules'] = pack['inputs']['rules']
        self.write('pack.json', pack)

    def validate(self):
        return qc.validate_callset_qc_pack(self.root / 'pack.json')

    def refuse(self, code):
        return self.assertRaisesRegex(ValueError, '^' + re.escape(code) + ':')

    def seed(self, case):
        name = case['target'] + '.json'
        value = self.read(name)
        if case['operation'] == 'changed-rules':
            self.write('frozen-rules.json', value)
            pack = self.read('pack.json')
            pack['freeze']['rules'] = self.identity('frozen-rules.json')
            self.write('pack.json', pack)
        parent = value
        for key in case['path'][:-1]:
            parent = parent[key]
        key = case['path'][-1]
        if case['operation'] == 'remove':
            del parent[key]
        else:
            parent[key] = case['value']
        self.write(name, value)
        self.refresh(frozen=case['operation'] != 'changed-rules')

    def test_exact_hwe_hand_table(self):
        self.assertAlmostEqual(qc.hardy_weinberg_exact(1, 2, 1), 1)
        # Conditional weights for h=0,2,4 are 1:8:8/3, hence p=3/35.
        self.assertAlmostEqual(qc.hardy_weinberg_exact(2, 0, 2), 3 / 35)
        self.assertAlmostEqual(qc.hardy_weinberg_exact(0, 2, 0), 1)
        for counts in [(0, 0, 0), (1, 0, 0), (4, 0, 0), (-1, 2, 1), (True, 2, 1), (1.0, 2, 1), ('1', 2, 1)]:
            with self.subTest(counts=counts), self.assertRaises(ValueError):
                qc.hardy_weinberg_exact(*counts)
        for value in [0, 1, True, 2.0, '2']:
            with self.subTest(minimum=value), self.assertRaises(ValueError):
                qc.hardy_weinberg_exact(1, 2, 1, minimum=value)
        self.assertEqual(qc.hardy_weinberg_exact(1, 2, 1, minimum=4), 1)

    def test_hand_metrics_and_read_only_repeated_calls(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        result = self.validate()
        self.assertEqual(self.read('expected.json'), result['qc'])
        self.assertEqual(result, self.validate())
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})
        report = result['qc']
        self.assertEqual(.5, report['titv']['value'])
        self.assertEqual(1 / 6, report['sites'][0]['missingness'])
        self.assertEqual(1, report['sites'][0]['hwe']['p_value'])
        self.assertEqual(4, report['sites'][0]['hwe']['controls_called'])
        self.assertEqual(1 / 3, report['samples'][0]['heterozygosity'])
        self.assertEqual(0, report['samples'][-1]['call_rate'])
        self.assertIsNone(report['samples'][-1]['heterozygosity'])
        self.assertEqual(['fixture-site-2'], report['mendelian'][0]['errors'])
        self.assertEqual(['fixture-site-6'], report['mendelian'][0]['unavailable_sites'])
        self.assertIn('sex-check:father', report['failed_controls'])
        self.assertEqual('unavailable', result['review'])
        self.assertEqual(['minimum-quality', 'minimum-depth', 'allele-balance', 'maximum-missingness'], [row['reasons'][0] for row in report['removed_sites']])

    def test_controls_only_independent_of_case_genotypes(self):
        rules, table = self.read('rules.json'), self.read('table.json')
        baseline = qc.compute_callset_qc(table, rules)
        table['sites'][0]['calls'][2].update(gt='1/1', alt_depth=20)
        changed = qc.compute_callset_qc(table, rules)
        self.assertEqual(baseline['sites'][0]['hwe'], changed['sites'][0]['hwe'])
        self.assertNotEqual(baseline['samples'][2], changed['samples'][2])

    def test_filter_edges_and_empty_retained_sites(self):
        rules, table = self.read('rules.json'), self.read('table.json')
        rules['site_filters'].update(minimum_quality=30, minimum_depth=20, maximum_missingness=1 / 6)
        rules['allele_balance'] = [.5, .5]
        rules['sample_filters'] = {'minimum_call_rate': 0, 'heterozygosity_range': [0, 1]}
        report = qc.compute_callset_qc(table, rules)
        self.assertIn('fixture-site-1', report['retained_sites'])
        self.assertIn('fixture-site-2', report['retained_sites'])
        rules['site_filters']['minimum_quality'] = 0
        rules['site_filters']['minimum_depth'] = 0
        rules['site_filters']['maximum_missingness'] = 1
        rules['allele_balance'] = [0, 1]
        self.assertEqual(7, len(qc.compute_callset_qc(table, rules)['retained_sites']))
        rules['site_filters']['minimum_quality'] = 31
        with self.refuse('empty-retained-sites'):
            qc.compute_callset_qc(table, rules)

    def test_hwe_cutoff_equal_and_below(self):
        rules, table = self.read('rules.json'), self.read('table.json')
        for index, gt in zip((0, 1, 3, 4), ('0/0', '0/0', '1/1', '1/1')):
            table['sites'][0]['calls'][index].update(gt=gt, alt_depth=20 if gt == '1/1' else 0)
        p_value = qc.hardy_weinberg_exact(2, 0, 2)
        rules['site_filters']['hwe_p_cutoff'] = p_value
        self.assertIn('fixture-site-1', qc.compute_callset_qc(table, rules)['retained_sites'])
        rules['site_filters']['hwe_p_cutoff'] = p_value + .01
        report = qc.compute_callset_qc(table, rules)
        self.assertIn({'id': 'fixture-site-1', 'reasons': ['hwe-controls']}, report['removed_sites'])

    def test_unavailable_hwe_sex_and_titv(self):
        rules, table = self.read('rules.json'), self.read('table.json')
        for site in table['sites']:
            site['alt'] = 'G'
            site['ref'] = 'A'
            for index in (0, 1, 3, 4):
                site['calls'][index].update(gt='0/0', alt_depth=0)
        rules['sex_check']['enabled'] = False
        report = qc.compute_callset_qc(table, rules)
        self.assertEqual('unavailable', report['titv']['status'])
        self.assertEqual('unavailable', report['sites'][0]['hwe']['status'])
        self.assertTrue(all(row['status'] == 'unavailable' for row in report['sex_checks']))
        rules['strand_ambiguous'] = 'exclude'
        table['sites'][0]['alt'] = 'T'
        report = qc.compute_callset_qc(table, rules)
        self.assertIn({'id': 'fixture-site-1', 'reasons': ['strand-ambiguous']}, report['removed_sites'])

    def test_exploratory_changes_preserve_original_rules(self):
        case = next(case for case in CASES if case['id'] == 'post-outcome-filters')
        self.seed(case)
        pack = self.read('pack.json')
        pack['mode'] = 'exploratory'
        self.write('pack.json', pack)
        self.write('qc.json', qc.compute_callset_qc(self.read('table.json'), self.read('rules.json')))
        self.refresh(frozen=False)
        self.assertEqual('exploratory', self.validate()['mode'])
        self.assertTrue((self.root / 'frozen-rules.json').is_file())

    def test_structural_and_integer_fields(self):
        for target, path, values in [
            ('pack', ['schema_version'], [True, 1.0, '1']),
            ('rules', ['schema_version'], [True, 1.0, '1']),
            ('rules', ['site_filters', 'minimum_controls'], [True, 2.0, '2']),
            ('rules', ['sex_check', 'minimum_sites'], [True, 1.0, '1']),
            ('table', ['schema_version'], [True, 1.0, '1']),
            ('table', ['sites', 0, 'position'], [True, 10.0, '10']),
            ('qc', ['schema_version'], [True, 1.0, '1']),
            ('qc', ['mendelian', 0, 'error_count'], [True, 1.0, '1']),
            ('pack', ['claims', 0, 'status'], [[], {}, True]),
        ]:
            original = self.read(target + '.json')
            for value in values:
                data = deepcopy(original)
                parent = data
                for key in path[:-1]:
                    parent = parent[key]
                parent[path[-1]] = value
                self.write(target + '.json', data)
                self.refresh()
                with self.subTest(target=target, path=path, value=value), self.assertRaises(ValueError):
                    self.validate()
            self.write(target + '.json', original)
            self.refresh()

    def test_invalid_table_records(self):
        rules, original = self.read('rules.json'), self.read('table.json')
        changes = [(['sites'], []), (['samples'], []), (['samples', 1], 'father'),
                   (['sites', 1, 'id'], 'fixture-site-1'), (['sites', 1, 'position'], 10),
                   (['sites', 0, 'alt'], ['C', 'G']), (['sites', 0, 'ref'], 'N'),
                   (['sites', 0, 'calls', 0, 'gt'], '0|1'), (['sites', 0, 'calls', 0, 'depth'], -1),
                   (['sites', 0, 'calls', 0, 'quality'], True), (['sites', 0, 'calls', 0, 'depth'], float('inf')),
                   (['sites', 0, 'calls', 0, 'alt_depth'], 30), (['genome_build'], 'other')]
        for path, value in changes:
            table = deepcopy(original)
            parent = table
            for key in path[:-1]:
                parent = parent[key]
            parent[path[-1]] = value
            with self.subTest(path=path, value=value), self.assertRaises(ValueError):
                qc.compute_callset_qc(table, rules)

    def evidence_claim(self, kind='computed', result='arithmetic', origin='study', status='supported', source=None):
        pack = self.read('pack.json')
        record = {'schema': 'callset-qc-evidence-v1', 'schema_version': 1, 'fixture': True,
                  'id': 'fixture-evidence', 'kind': kind, 'result': result, 'source': source or self.identity('table.json')}
        identity = self.write('evidence.json', record)
        pack['claims'] = [{'id': 'fixture-claim', 'kind': 'descriptive', 'text': 'Synthetic table has six declared samples.',
                           'status': status, 'support': [dict(identity, origin=origin)]}]
        self.write('pack.json', pack)

    def test_claim_records_and_aliases(self):
        for field in ('kind', 'result'):
            for value in ('review-approval', 'computed', 'numerical-agreement'):
                kwargs = {'kind': 'synthetic-observation', 'result': 'observed', field: value}
                self.evidence_claim(**kwargs)
                with self.subTest(field=field, value=value), self.refuse('non-evidence-support'):
                    self.validate()
        for origin in ('external', 'independent', 'preregistered'):
            self.evidence_claim(kind='synthetic-observation', result='observed', origin=origin)
            with self.subTest(origin=origin), self.refuse('self-evidence'):
                self.validate()
        self.evidence_claim(kind='synthetic-observation', result='observed', status='replicated')
        with self.refuse('replication-unavailable'):
            self.validate()
        self.evidence_claim(kind='unavailable', result='observed', status='conflicting')
        with self.refuse('unavailable-evidence'):
            self.validate()
        self.evidence_claim(kind='synthetic-observation', result='unavailable', status='unsupported')
        with self.refuse('unavailable-evidence'):
            self.validate()

    def test_mixed_unavailable_evidence_and_wording(self):
        self.evidence_claim(kind='synthetic-observation', result='observed')
        pack = self.read('pack.json')
        unavailable = self.read('evidence.json')
        unavailable['result'] = 'unavailable'
        other = self.write('missing.json', unavailable)
        pack['claims'][0]['support'].append(dict(other, origin='study'))
        self.write('pack.json', pack)
        with self.refuse('unavailable-evidence'):
            self.validate()
        for family in qc.WORDING_FAMILIES + ('pathogenicity', 'diagnosis', 'disease association', 'physical validity', 'truth'):
            pack['claims'][0].update(status='unavailable', support=[], text='Synthetic ' + family.upper() + ' evidence.')
            self.write('pack.json', pack)
            with self.subTest(family=family), self.refuse('claim-boundary'):
                self.validate()

    def test_unavailable_and_computed_sources(self):
        self.evidence_claim(kind='synthetic-observation', result='observed', source=self.identity('qc.json'))
        with self.refuse('non-evidence-support'):
            self.validate()
        for field in ('kind', 'result'):
            for value, code in [('unavailable', 'unavailable-evidence'), ('computed', 'non-evidence-support'), ('review-approval', 'non-evidence-support')]:
                source = {'fixture': True, 'schema_version': 1, field: value}
                identity = self.write('source.json', source)
                self.evidence_claim(kind='synthetic-observation', result='observed', source=identity)
                with self.subTest(field=field, value=value), self.refuse(code):
                    self.validate()
        source = self.write('source.json', {'fixture': True, 'schema_version': 1.0})
        self.evidence_claim(kind='synthetic-observation', result='observed', source=source)
        with self.refuse('invalid-record'):
            self.validate()

    def test_seeded_guards_are_necessary(self):
        original = qc._require
        for case in CASES:
            worker = CallsetQCTests('test_seed_' + case['id'].replace('-', '_'))
            outcome = unittest.TestResult()
            def without_guard(condition, code, message):
                if code != case['finding']:
                    original(condition, code, message)
            with self.subTest(case=case['id']), patch.object(qc, '_require', side_effect=without_guard):
                worker.run(outcome)
                self.assertFalse(outcome.wasSuccessful(), 'seeded case passed with its refusal guard disabled')
                self.assertTrue(outcome.failures, 'guard removal should break the named refusal assertion')

    def test_json_refusals_and_preparse_budget(self):
        for raw in [b'{"a":1,"a":2}', b'{"x":{"a":1,"a":2}}', b'{"a":NaN}', b'{"a":Infinity}',
                    b'[]', b'null', b'{"a":1e999}', b'{"a":' + b'9' * 1000 + b'}',
                    b'{"a":' + b'[' * 2000 + b'0' + b']' * 2000 + b'}', b'{', b'\xff']:
            with self.subTest(raw=raw[:40]), self.assertRaises(ValueError):
                qc._json(raw)
        self.assertEqual({'value': -0.5}, qc._json(b'{"value":-0.5}')[0])
        with patch.object(qc.re, 'findall', side_effect=AssertionError('match-list allocation')):
            self.assertEqual({'fixture': True}, qc._json(b'{"fixture":true}')[0])
        with patch.object(qc.json, 'loads', side_effect=AssertionError('parsed over budget')):
            with self.refuse('input-limit'):
                qc._json(b'{"a":[0,0,0]}', allowance=2)
        self.assertEqual({'a': []}, qc._json(b'{"a":[]}', allowance=2)[0])
        for name, value, raw in [('MAX_DEPTH', 0, b'{"a":{}}'), ('MAX_ITEMS', 1, b'{"a":0,"b":0}'), ('MAX_TEXT', 2, b'{"a":"abc"}')]:
            with patch.object(qc, name, value), self.subTest(name=name), self.assertRaises(ValueError):
                qc._json(raw)

    def test_dimension_limits_before_work(self):
        rules, table = self.read('rules.json'), self.read('table.json')
        for name, equal in [('MAX_SAMPLES', 6), ('MAX_SITES', 7), ('MAX_CELLS', 42), ('MAX_TRIOS', 1)]:
            with patch.object(qc, name, equal):
                qc.compute_callset_qc(table, rules)
            with patch.object(qc, name, equal - 1), self.subTest(name=name), self.refuse('input-limit'):
                qc.compute_callset_qc(table, rules)
        with patch.object(qc, 'MAX_CLAIMS', 0), self.refuse('input-limit'):
            self.validate()
        with patch.object(qc, 'MAX_SUPPORT', 0):
            self.validate()
            self.evidence_claim()
            with self.refuse('input-limit'):
                self.validate()

    def test_reader_byte_node_and_artifact_budgets(self):
        total = sum((self.root / name).stat().st_size for name in ('pack.json', 'rules.json', 'table.json', 'qc.json'))
        maximum = max((self.root / name).stat().st_size for name in ('pack.json', 'rules.json', 'table.json', 'qc.json'))
        nodes = sum(qc._json((self.root / name).read_bytes())[1] for name in ('pack.json', 'rules.json', 'table.json', 'qc.json'))
        with patch.object(qc, 'MAX_TOTAL_NODES', nodes):
            self.validate()
        with patch.object(qc, 'MAX_TOTAL_BYTES', total), patch.object(qc, 'MAX_BYTES', maximum), patch.object(qc, 'MAX_RECORDS', 4):
            self.validate()
        for name, value, code in [('MAX_TOTAL_BYTES', total - 1, 'input-limit'), ('MAX_BYTES', maximum - 1, 'input-file'),
                                  ('MAX_RECORDS', 3, 'input-limit'), ('MAX_TOTAL_NODES', 5, 'input-limit')]:
            with self.subTest(name=name), patch.object(qc, name, value), self.refuse(code):
                self.validate()
        (self.root / 'large.json').write_bytes(b' ' * 1025)
        with patch.object(qc, 'MAX_BYTES', 1024), qc._Bundle(self.root / 'pack.json') as bundle, self.refuse('input-file'):
            bundle.snapshot('large.json')

    def test_hardlinks_read_and_parse_once(self):
        os.link(self.root / 'rules.json', self.root / 'alias.json')
        with qc._Bundle(self.root / 'pack.json') as bundle:
            with patch.object(qc, '_json', wraps=qc._json) as parse:
                first = bundle.snapshot('rules.json')
                second = bundle.snapshot('alias.json')
                self.assertIs(first[0], second[0])
                self.assertEqual(1, parse.call_count)
                self.assertEqual((self.root / 'rules.json').stat().st_size, bundle.bytes_read)
                bundle.recheck()

    def test_reader_nonregular_files_paths_and_missing(self):
        for name in ('fifo', 'directory', 'link'):
            path = self.root / name
            if name == 'fifo':
                os.mkfifo(path)
            elif name == 'directory':
                path.mkdir()
            else:
                path.symlink_to(self.root / 'rules.json')
            with self.subTest(name=name), qc._Bundle(self.root / 'pack.json') as bundle, self.refuse('input-file'):
                bundle.snapshot(name)
        for value in ('../rules.json', '/rules.json', 'x\\rules.json', './rules.json', 'x//rules.json', 'C:rules.json', ''):
            with self.subTest(value=value), self.assertRaises(ValueError):
                qc._relative(value)
        for value in (None, [], True, 'bad\x00path'):
            with self.subTest(bundle_path=repr(value)), self.refuse('input-path'):
                qc.validate_callset_qc_pack(value)
        (self.root / 'nested').symlink_to(self.root, target_is_directory=True)
        with qc._Bundle(self.root / 'pack.json') as bundle, self.refuse('input-file'):
            bundle.snapshot('nested/rules.json')
        (self.root / 'rules.json').unlink()
        with self.refuse('input-file'):
            self.validate()

    def test_reader_file_replacement_and_growth(self):
        with qc._Bundle(self.root / 'pack.json') as bundle:
            bundle.snapshot('rules.json')
            original = self.read('rules.json')
            self.write('replacement.json', original)
            os.replace(self.root / 'replacement.json', self.root / 'rules.json')
            with self.refuse('input-changed'):
                bundle.recheck()
        original_open = qc.os.open
        def grow(path, flags, *args, **kwargs):
            if path == 'table.json':
                with (self.root / 'table.json').open('ab') as handle:
                    handle.write(b' ')
            return original_open(path, flags, *args, **kwargs)
        with patch.object(qc.os, 'open', side_effect=grow), self.refuse('input-changed'):
            self.validate()

    def test_root_and_transient_ancestor_swap_during_open(self):
        original_open = qc.os.open
        for component in (self.root.name, self.root.parent.name):
            swapped = []
            absolute = self.root if component == self.root.name else self.root.parent
            moved = absolute.with_name(absolute.name + '-moved')
            def swap(path, flags, *args, **kwargs):
                if path == component and kwargs.get('dir_fd') is not None and not swapped:
                    absolute.rename(moved)
                    absolute.symlink_to(moved, target_is_directory=True)
                    swapped.append(True)
                return original_open(path, flags, *args, **kwargs)
            try:
                with patch.object(qc.os, 'open', side_effect=swap), self.assertRaises(ValueError):
                    self.validate()
            finally:
                if swapped:
                    absolute.unlink()
                    moved.rename(absolute)
            self.assertTrue(swapped)

    def test_parent_swap_preserving_bundle_inode(self):
        with qc._Bundle(self.root / 'pack.json') as bundle:
            bundle.snapshot('rules.json')
            parent = self.root.parent
            moved = parent.with_name(parent.name + '-moved')
            parent.rename(moved)
            parent.mkdir()
            (moved / self.root.name).rename(parent / self.root.name)
            try:
                with self.refuse('input-changed'):
                    bundle.recheck()
            finally:
                (parent / self.root.name).rename(moved / self.root.name)
                parent.rmdir()
                moved.rename(parent)

    def test_cli_json_arguments_and_no_writes(self):
        script = ROOT / 'scripts/validate_callset_qc_pack.py'
        for args in ([], ['--unknown'], ['a', 'b'], ['--output', 'x'], ['missing.json']):
            run = subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True, timeout=CALL_TIMEOUT)
            with self.subTest(args=args):
                self.assertEqual(2, run.returncode)
                self.assertEqual('', run.stdout)
                value = json.loads(run.stderr)
                self.assertEqual('refused', value['status'])
                self.assertNotIn('Traceback', run.stderr)
        help_run = subprocess.run([sys.executable, str(script), '--help'], capture_output=True, text=True, timeout=CALL_TIMEOUT)
        self.assertEqual(0, help_run.returncode)
        self.assertIn('bundle', help_run.stdout)
        self.assertEqual('', help_run.stderr)
        runs = [subprocess.Popen([sys.executable, str(script), str(self.root / 'pack.json')], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
        try:
            for run in runs:
                out, err = run.communicate(timeout=CALL_TIMEOUT)
                self.assertEqual(0, run.returncode, err)
                self.assertEqual('checked', json.loads(out)['status'])
        finally:
            for run in runs:
                if run.poll() is None:
                    run.kill()
                    run.communicate()


def _seeded_case(case):
    def test(self):
        self.seed(case)
        with self.refuse(case['finding']):
            self.validate()
    test.__name__ = 'test_seed_' + case['id'].replace('-', '_')
    return test


for _case in CASES:
    setattr(CallsetQCTests, 'test_seed_' + _case['id'].replace('-', '_'), _seeded_case(_case))


if __name__ == '__main__':
    unittest.main()
