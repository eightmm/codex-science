"""Offline synthetic nucleic-acid acceptance, refusal and hostile-file regression checks."""
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

from codex_science import nucleic_acid_quant_purity_pack as pack

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'examples/workflow-nucleic-acid-quant-purity'
CALL_TIMEOUT = float(os.environ.get('OMS_TEST_CALL_TIMEOUT', '30'))
CASES = json.loads((EXAMPLE / 'negative-cases.json').read_text())['cases']


class NucPackTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'parent' / 'bundle'
        self.root.mkdir(parents=True)
        for name in ('pack.json', 'rules.json', 'readings.json', 'report.json'):
            shutil.copyfile(EXAMPLE / name, self.root / name)
        self.documents = {name: json.loads((self.root / (name + '.json')).read_text())
                          for name in ('pack', 'rules', 'readings', 'report')}

    def save(self):
        entry = self.documents['pack']
        for name in ('rules', 'readings', 'report', 'evidence'):
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

    def refresh_report(self, bands=None):
        self.documents['report'].update(pack.compute_quant_purity(self.documents['readings'], self.documents['rules'], bands))

    def run_case(self, case):
        node = self.documents[case['target']]
        for key in case['path'][:-1]:
            node = node[key]
        if case['remove']:
            del node[case['path'][-1]]
        else:
            node[case['path'][-1]] = case['value']
        with self.assertRaisesRegex(ValueError, '^' + case['finding'] + ':'):
            pack.validate_nucleic_acid_quant_purity_pack(self.save())

    def test_fixture_hand_arithmetic(self):
        result = pack.validate_nucleic_acid_quant_purity_pack(self.root / 'pack.json')
        expected = json.loads((EXAMPLE / 'expected.json').read_text())['computation']
        pack._same(result['computation'], expected, 'expected synthetic fixture')
        for sample, concentration, a260, denominator in zip(result['computation']['samples'],
                                                           (400, 200), (.4, .5), (.2, .25)):
            self.assertTrue(math.isclose(sample['concentration_ng_ul'], concentration, rel_tol=1e-12))
            for ratio in ('a260_a280', 'a260_a230'):
                self.assertTrue(math.isclose(sample[ratio], 2, rel_tol=1e-12))
            corrected = sample['replicates'][0]['corrected']
            self.assertTrue(math.isclose(corrected['A260'], a260, rel_tol=1e-12))
            self.assertTrue(math.isclose(corrected['A280'], denominator, rel_tol=1e-12))
        self.assertEqual(result['computation']['summary'], {'n':2, 'quantified':2, 'unavailable':0, 'flagged':0})
        self.assertEqual(result['review'], 'unavailable')
        self.assertEqual(result['stages'], list(pack.STAGES))

    def test_unavailable_and_ratio_flags(self):
        rows = self.documents['readings']['samples'][0]['replicates']
        for row in rows:
            row['A280'] = .03
        self.refresh_report()
        result = pack.validate_nucleic_acid_quant_purity_pack(self.save())['computation']
        self.assertEqual(result['samples'][0]['concentration_ng_ul'], 'unavailable')
        self.assertIn('non-positive-denominator', result['samples'][0]['flags'])
        for row in rows:
            row['A280'] = .43
        self.refresh_report()
        result = pack.validate_nucleic_acid_quant_purity_pack(self.save())['computation']
        self.assertIn('a260_a280-outside-band', result['samples'][0]['flags'])
        self.assertEqual(result['samples'][0]['classification'], 'quantified')
        for sample in self.documents['readings']['samples']:
            for row in sample['replicates']:
                row['availability'] = 'unavailable'
                for key in pack.WAVELENGTHS:
                    row[key] = None
        self.refresh_report()
        result = pack.validate_nucleic_acid_quant_purity_pack(self.save())['computation']
        self.assertEqual(result['summary']['unavailable'], 2)
        for sample in result['samples']:
            for key in ('concentration_ng_ul', 'a260_a280', 'a260_a230'):
                self.assertEqual(sample[key], 'unavailable')

    def test_relative_singular_and_zero_signal(self):
        rules, readings = self.documents['rules'], self.documents['readings']
        for magnitude in (0, 1e-15):
            readings['blank']['reading'].update(A230=0, A260=0, A280=0, A320=0)
            for row in readings['samples'][0]['replicates']:
                row.update(A230=.2, A260=.4, A280=magnitude, A320=0)
            result = pack.compute_quant_purity(readings, rules)
            self.assertIn('non-positive-denominator', result['samples'][0]['flags'])
            self.assertEqual(result['samples'][0]['a260_a280'], 'unavailable')
        for row in readings['samples'][0]['replicates']:
            row.update(A260=0, A280=.2)
        rules['linear_a260_range']['minimum'] = 0
        self.assertIn('degenerate-signal', pack.compute_quant_purity(readings, rules)['samples'][0]['flags'])

    def test_exploratory_bands_and_equal_endpoints(self):
        report = self.documents['report']
        report['exploratory'] = True
        report['purity_bands']['dsDNA']['a260_a280']['minimum'] = 2.1
        self.refresh_report(report['purity_bands'])
        self.assertTrue(pack.validate_nucleic_acid_quant_purity_pack(self.save())['exploratory'])
        readings, rules = self.documents['readings'], self.documents['rules']
        readings['blank']['reading'].update(A230=0, A260=0, A280=0, A320=0)
        rules['linear_a260_range'].update(minimum=.125, maximum=.5)
        rules['replicate_max_relative_difference'] = .75
        for row, a260 in zip(readings['samples'][0]['replicates'], (.125, .5)):
            row.update(A230=.125, A260=a260, A280=.125, A320=0)
        result = pack.compute_quant_purity(readings, rules)
        self.assertTrue(math.isclose(result['samples'][0]['replicate_relative_difference'], .75, rel_tol=1e-12))
        rules['replicate_max_relative_difference'] = .74
        with self.assertRaisesRegex(ValueError, '^replicate-disagreement:'):
            pack.compute_quant_purity(readings, rules)

    def test_types_identities_and_minimums(self):
        rules, readings = self.documents['rules'], self.documents['readings']
        for field, original in (('minimum_replicates', 2), ('path_length_cm', .5), ('replicate_max_relative_difference', .1)):
            for value in (True, '2', [], -1, float('nan'), float('inf')):
                rules[field] = value
                with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, '^invalid-record:'):
                    pack.compute_quant_purity(readings, rules)
            rules[field] = original
        for value in (2.0, 0, 1, pack.MAX_REPLICATES + 1):
            rules['minimum_replicates'] = value
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.compute_quant_purity(readings, rules)
        rules['minimum_replicates'] = 3
        with self.assertRaisesRegex(ValueError, '^insufficient-replicates:'):
            pack.compute_quant_purity(readings, rules)
        rules['minimum_replicates'] = 2
        readings['samples'][1]['sample_id'] = 'dna-fixture'
        with self.assertRaisesRegex(ValueError, '^sample-identity:'):
            pack.compute_quant_purity(readings, rules)
        readings['samples'][1]['sample_id'] = []
        with self.assertRaisesRegex(ValueError, '^invalid-record:'):
            pack.compute_quant_purity(readings, rules)

    def test_numeric_rule_edges(self):
        readings, rules = self.documents['readings'], self.documents['rules']
        for field in ('path_length_cm', 'replicate_max_relative_difference'):
            original = rules[field]
            for value in (0, 10 if field == 'path_length_cm' else 1):
                rules[field] = value
                if field == 'path_length_cm' and value == 0:
                    with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                        pack.compute_quant_purity(readings, rules)
                else:
                    pack.compute_quant_purity(readings, rules)
            rules[field] = original
        for value in (0, -1, True, '10', [], 1e12 + 1):
            rules['samples'][0]['dilution_factor'] = value
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.compute_quant_purity(readings, rules)
        rules['samples'][0]['dilution_factor'] = 1e12
        pack.compute_quant_purity(readings, rules)
        for value in (0, .5):
            rules['linear_a260_range'].update(minimum=value, maximum=value)
            with self.assertRaisesRegex(ValueError, '^linear-range:'):
                pack.compute_quant_purity(readings, rules)

    def test_collection_limits_before_work(self):
        readings, rules = self.documents['readings'], self.documents['rules']
        for constant in ('MAX_SAMPLES', 'MAX_ROWS'):
            with patch.object(pack, constant, 0), self.assertRaisesRegex(ValueError, '^input-limit:'):
                pack.compute_quant_purity(readings, rules)
        with patch.object(pack, 'MAX_REPLICATES', 0), self.assertRaisesRegex(ValueError, '^invalid-record:'):
            pack.compute_quant_purity(readings, rules)
        with patch.object(pack, 'MAX_ROWS', 4), patch.object(pack, 'MAX_SAMPLES', 2), patch.object(pack, 'MAX_REPLICATES', 2):
            pack.compute_quant_purity(readings, rules)
        with patch.object(pack, 'MAX_ROWS', 3), self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack.compute_quant_purity(readings, rules)
        with patch.object(pack, 'MAX_RECORDS', 0), self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack._claims([self.documents['report']['claims'][0]], {})
        raw = json.dumps({'x': [0] * (pack.MAX_ROWS + 1)}).encode()
        with self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack._json(raw)
        for value in ([], 0, None, {}, 'rows'):
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack._list(value, 'rows', 2)

    def test_rule_and_reading_refusal_matrix(self):
        base_rules, base_readings = self.documents['rules'], self.documents['readings']
        cases = [('rules', ['blank_rule'], 'none', 'blank-rule'),
                 ('rules', ['wavelengths'], [], 'wavelength-rule'),
                 ('rules', ['samples', 0, 'analyte'], 'ssDNA', 'analyte-rule'),
                 ('rules', ['samples', 0, 'analyte'], [], 'invalid-record'),
                 ('rules', ['samples', 0, 'sample_id'], 'blank-fixture', 'blank-mixed'),
                 ('readings', ['blank', 'sample_id'], 'unknown', 'blank-control'),
                 ('readings', ['blank', 'reading', 'A230'], -.1, 'blank-control'),
                 ('readings', ['samples', 0, 'replicates', 0, 'replicate_id'], 'blank-1', 'replicate-identity'),
                 ('readings', ['samples', 0, 'replicates', 0, 'availability'], [], 'invalid-record'),
                 ('readings', ['samples', 0, 'replicates', 0, 'availability'], 'unavailable', 'unavailable-as-zero'),
                 ('readings', ['samples'], [], 'invalid-record'),
                 ('readings', ['samples', 0, 'replicates'], [], 'invalid-record')]
        for target, path, value, finding in cases:
            rules, readings = copy.deepcopy(base_rules), copy.deepcopy(base_readings)
            node = rules if target == 'rules' else readings
            for key in path[:-1]:
                node = node[key]
            node[path[-1]] = value
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, '^' + finding + ':'):
                pack.compute_quant_purity(readings, rules)
        for key in ('n', 'quantified', 'unavailable', 'flagged'):
            original = self.documents['report']['summary'][key]
            for value in (True, float(original), str(original), []):
                self.documents['report']['summary'][key] = value
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, '^invalid-record:'):
                    pack.validate_nucleic_acid_quant_purity_pack(self.save())
            self.documents['report']['summary'][key] = original

    def test_limits_equal_empty_and_malformed(self):
        with patch.object(pack, 'MAX_DEPTH', 0):
            self.assertEqual(pack._json(b'{}'), ({}, 1))
            with self.assertRaisesRegex(ValueError, '^invalid-json:'):
                pack._json(b'{"x":1}')
        with patch.object(pack, 'MAX_DEPTH', 1), patch.object(pack, 'MAX_STRING', 3):
            self.assertEqual(pack._json(b'{"x":"abc"}')[0], {'x':'abc'})
            for raw in (b'{"x":""}', b'{"x":"abcd"}'):
                with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                    pack._json(raw)
        self.assertEqual(pack._names(['a', 'b'], 'edge', 2), ['a', 'b'])
        self.assertEqual(pack._names([], 'edge', 0, True), [])
        for values in (['a', 'a'], [[]], 0):
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack._names(values, 'edge', 2)
        with self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack._names(['a'], 'edge', 0)
        rules, readings = self.documents['rules'], self.documents['readings']
        readings['samples'][0]['replicates'].append(copy.deepcopy(readings['samples'][0]['replicates'][0]))
        with patch.object(pack, 'MAX_REPLICATES', 2), self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack.compute_quant_purity(readings, rules)
        for value in (1e100, -1e100):
            self.assertEqual(pack._number(value, 'edge', -1e100), value)
        for value in (1e101, -1e101, None, {}, ''):
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack._number(value, 'edge', -1e100)

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
            with patch.object(pack, constant, 0):
                store = pack._Bundle(self.root)
                try:
                    with self.assertRaisesRegex(ValueError, '^(input-file|input-limit):'):
                        store.load('tiny.json')
                finally:
                    store.close()
            with patch.object(pack, constant, size - 1):
                store = pack._Bundle(self.root)
                try:
                    with self.assertRaisesRegex(ValueError, '^(input-file|input-limit):'):
                        store.load('tiny.json')
                finally:
                    store.close()

    def test_paths_special_files_and_missing(self):
        for value in ('../readings.json', '/readings.json', 'a\\b', 'a/./b', 'a//b', '.', ''):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, '^(input-path|invalid-record):'):
                pack._relative(value)
        target = self.root / 'special'
        for kind in ('directory', 'fifo', 'symlink', 'missing'):
            if kind == 'directory':
                target.mkdir()
            elif kind == 'fifo':
                os.mkfifo(target)
            elif kind == 'symlink':
                target.symlink_to('readings.json')
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
                store.load('link/readings.json')
        finally:
            store.close()

    def test_file_replacement_and_growth(self):
        target = self.root / 'readings.json'
        real_open, real_fstat = os.open, os.fstat
        replaced = False
        def replace(name, flags, *args, **kwargs):
            nonlocal replaced
            if name == target.name and not replaced:
                replaced = True
                raw = target.read_bytes()
                target.rename(self.root / 'old-readings')
                target.write_bytes(raw)
            return real_open(name, flags, *args, **kwargs)
        with patch.object(pack.os, 'open', side_effect=replace), self.assertRaisesRegex(ValueError, '^input-file:'):
            pack.validate_nucleic_acid_quant_purity_pack(self.root / 'pack.json')
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
            pack.validate_nucleic_acid_quant_purity_pack(self.root / 'pack.json')

    def test_final_hash_and_root_recheck(self):
        real_finish = pack._Bundle.finish
        def change(store):
            with (self.root / 'readings.json').open('ab') as stream:
                stream.write(b' ')
            return real_finish(store)
        with patch.object(pack._Bundle, 'finish', change), self.assertRaisesRegex(ValueError, '^input-changed:'):
            pack.validate_nucleic_acid_quant_purity_pack(self.root / 'pack.json')

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
                    pack.validate_nucleic_acid_quant_purity_pack(self.root / 'pack.json')
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
            pack.validate_nucleic_acid_quant_purity_pack(self.root / 'pack.json')

    def evidence(self, kind='computed', result='numerical-agreement', origin='internal'):
        identity = self.documents['pack']['readings']
        self.documents['evidence'] = {'schema': 'nuc-evidence-v1', 'fixture': 'synthetic fixture',
                                     'records': [{'id': 'E1', 'kind': kind, 'result': result, 'origin': origin,
                                                  'source': copy.deepcopy(identity)}]}
        self.documents['report']['claims'] = [{'id': 'C1', 'kind': 'descriptive', 'status': 'supported',
                                               'text': 'Synthetic fixture arithmetic matches the supplied table.',
                                               'evidence': ['E1']}]

    def test_claim_kind_and_result_not_labels(self):
        for status in sorted(pack.POSITIVE):
            for kind, result in (('review-approval', 'observed'), ('observed', 'review-approval'),
                                 ('computed', 'observed'), ('observed', 'numerical-agreement'),
                             ('observed', 'arithmetic-only'), ('nuc-result-v1', 'observed')):
                self.evidence(kind, result)
                self.documents['report']['claims'][0]['status'] = status
                with self.subTest(status=status, kind=kind, result=result), self.assertRaisesRegex(ValueError, '^non-evidence-support:'):
                    pack.validate_nucleic_acid_quant_purity_pack(self.save())

    def test_unavailable_mixed_evidence_all_statuses(self):
        for status in sorted(pack.STATUSES - {'unavailable'}):
            self.evidence('unavailable', 'unavailable')
            self.documents['evidence']['records'].append({**self.documents['evidence']['records'][0],
                                                          'id': 'E2', 'kind': 'observed', 'result': 'observed'})
            self.documents['report']['claims'][0].update(status=status, evidence=['E1', 'E2'])
            with self.subTest(status=status), self.assertRaisesRegex(ValueError, '^unavailable-evidence:'):
                pack.validate_nucleic_acid_quant_purity_pack(self.save())

    def test_claim_empty_unavailable_replication_and_types(self):
        claim = self.documents['report']['claims'][0]
        claim['status'] = 'supported'
        with self.assertRaisesRegex(ValueError, '^missing-evidence:'):
            pack.validate_nucleic_acid_quant_purity_pack(self.save())
        claim.update(status='unavailable', text='Supported synthetic result')
        with self.assertRaisesRegex(ValueError, '^unavailable-positive:'):
            pack.validate_nucleic_acid_quant_purity_pack(self.save())
        self.evidence('observed', 'observed')
        self.documents['report']['claims'][0]['status'] = 'replicated'
        with self.assertRaisesRegex(ValueError, '^claim-replication:'):
            pack.validate_nucleic_acid_quant_purity_pack(self.save())
        for field in ('status', 'kind', 'id'):
            self.documents['report']['claims'][0][field] = []
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.validate_nucleic_acid_quant_purity_pack(self.save())
            self.evidence('observed', 'observed')

    def test_wording_families_and_refusal_order(self):
        words = ('causes', 'mechanism', 'therapeutic', 'clinical', 'efficacy', 'effective', 'treatment', 'cures',
                 'prevents', 'recommended', 'prescribe', 'binding', 'affinity', 'inhibition', 'activation',
                 'regulation', 'drives', 'induction', 'quality', 'sequencing', 'PCR', 'truth', 'physical validity')
        for word in words:
            self.evidence()
            self.documents['report']['claims'][0].update(kind='descriptive', text='Synthetic ' + word)
            with self.subTest(word=word), self.assertRaisesRegex(ValueError, '^claim-overreach:'):
                pack.validate_nucleic_acid_quant_purity_pack(self.save())
        self.documents['report']['headline'] = 'Synthetic quality'
        self.documents['readings']['samples'][0]['replicates'][0]['A260'] = -1
        with self.assertRaisesRegex(ValueError, '^claim-overreach:'):
            pack.validate_nucleic_acid_quant_purity_pack(self.save())

    def test_external_alias_path_hash_and_hardlink(self):
        for origin in ('external', 'independent', 'preregistered'):
            self.evidence('observed', 'observed', origin)
            with self.subTest(origin=origin), self.assertRaisesRegex(ValueError, '^external-alias:'):
                pack.validate_nucleic_acid_quant_purity_pack(self.save())
        alias = self.root / 'aliased-source'
        os.link(self.root / 'readings.json', alias)
        self.documents['evidence']['records'][0]['source']['path'] = alias.name
        with self.assertRaisesRegex(ValueError, '^external-alias:'):
            pack.validate_nucleic_acid_quant_purity_pack(self.save())

    def test_near_zero_comparison_has_no_absolute_tolerance(self):
        with self.assertRaisesRegex(ValueError, '^reported-number:'):
            pack._same(2e-20, 1e-20, 'small distinct number')
        pack._same(1e-20 * (1 + 1e-10), 1e-20, 'small relative tie')
        pack._same(1e-20 * (1 + 5e-9), 1e-20, 'documented relative tolerance')

    def test_decimal_band_edges_are_inclusive(self):
        self.assertTrue(pack._inside(2.0000000000000004, 1, 2))
        self.assertTrue(pack._inside(0.9999999999999999, 1, 2))
        self.assertFalse(pack._inside(2.000000001, 1, 2))

    def test_cli_success_refusal_arguments_and_help(self):
        command = [sys.executable, str(ROOT / 'scripts/validate_nucleic_acid_quant_purity_pack.py')]
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
        self.assertEqual(json.loads(success.stdout)['schema'], 'nuc-result-v1')
        self.documents['readings']['samples'][0]['replicates'][0]['A260'] = True
        refused = subprocess.run(command + [str(self.save())], capture_output=True, text=True, timeout=CALL_TIMEOUT)
        self.assertEqual(refused.returncode, 2)
        self.assertTrue(json.loads(refused.stderr)['finding'].startswith('invalid-record:'))


def _seeded_test(case):
    def test(self):
        self.run_case(case)
    return test


for _case in CASES:
    setattr(NucPackTests, 'test_seed_' + _case['id'].replace('-', '_'), _seeded_test(_case))


if __name__ == '__main__':
    unittest.main()
