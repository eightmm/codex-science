"""Offline synthetic ddPCR acceptance, seeded refusals and hostile-input checks."""
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

from codex_science import ddpcr_absolute_quantification_pack as pack

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'examples/workflow-ddpcr-absolute-quantification'
CALL_TIMEOUT = float(os.environ.get('OMS_TEST_CALL_TIMEOUT', '30'))
CASES = json.loads((EXAMPLE / 'negative-cases.json').read_text())['cases']


class DDPCRPackTests(unittest.TestCase):
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
            entry[name] = [identity] if name == 'evidence' else identity
        entry['frozen_rules_sha256'] = entry['rules']['sha256']
        (self.root / 'pack.json').write_text(json.dumps(entry, sort_keys=True) + '\n')
        return self.root / 'pack.json'

    def refresh_report(self, thresholds=None):
        self.documents['report'].update(pack.compute_ddpcr(self.documents['counts'], self.documents['rules'], thresholds))

    def run_case(self, case):
        node = self.documents[case['target']]
        for key in case['path'][:-1]:
            node = node[key]
        if case['remove']:
            del node[case['path'][-1]]
        else:
            node[case['path'][-1]] = copy.deepcopy(case['value'])
        if case.get('refresh_wells'):
            self.documents['report']['wells'] = pack.compute_ddpcr(self.documents['counts'], self.documents['rules'])['wells']
        with self.assertRaisesRegex(ValueError, '^' + case['finding'] + ':'):
            pack.validate_ddpcr_absolute_quantification_pack(self.save())

    def test_fixture_hand_arithmetic_and_exact_tails(self):
        result = pack.validate_ddpcr_absolute_quantification_pack(self.root / 'pack.json')
        expected = json.loads((EXAMPLE / 'expected.json').read_text())['computation']
        pack._same(result['computation'], expected, 'synthetic expected artifact')
        a, zero = result['computation']['samples']
        self.assertEqual((a['positive'], a['total']), (4, 8))
        self.assertTrue(math.isclose(a['lambda'], math.log(2), rel_tol=1e-12))
        self.assertTrue(math.isclose(a['concentration_copies_per_ul'], 12 * math.log(2), rel_tol=1e-12))
        self.assertTrue(math.isclose(zero['concentration_copies_per_ul'], 0, rel_tol=1e-12, abs_tol=0))
        self.assertTrue(math.isclose(zero['interval']['upper'], -12 * math.log(.025) / 8, rel_tol=1e-12))
        self.assertEqual(result['computation']['summary']['n'], 2)
        self.assertEqual(result['review'], 'unavailable')
        self.assertEqual(result['stages'], list(pack.STAGES))
        for k, n in ((1, 2), (2, 4), (4, 8), (1, 20), (19, 20)):
            interval = pack.exact_binomial_interval(k, n)
            # Finite binomial sums independently define the two exact tail equations.
            lower_tail = math.fsum(math.comb(n, j) * interval['lower'] ** j * (1 - interval['lower']) ** (n - j)
                                   for j in range(k, n + 1))
            upper_tail = math.fsum(math.comb(n, j) * interval['upper'] ** j * (1 - interval['upper']) ** (n - j)
                                   for j in range(k + 1))
            self.assertTrue(math.isclose(lower_tail, .025, rel_tol=1e-10))
            self.assertTrue(math.isclose(upper_tail, .025, rel_tol=1e-10))
        interval = pack.exact_binomial_interval(1, 2)
        self.assertTrue(math.isclose(interval['lower'], 1 - math.sqrt(.975), rel_tol=1e-12))
        self.assertTrue(math.isclose(interval['upper'], math.sqrt(.975), rel_tol=1e-12))

    def test_binomial_edges_types_and_convergence(self):
        for n in (1, pack.MAX_PARTITIONS):
            for k in (0, n):
                interval = pack.exact_binomial_interval(k, n)
                self.assertLess(interval['lower'], interval['upper'])
                self.assertGreater(interval['upper'], 0)
        for k, n, level in ((True, 4, .95), (2.0, 4, .95), ('2', 4, .95), (-1, 4, .95),
                            (0, 0, .95), (0, [], .95), (0, 4.0, .95), (0, True, .95),
                            (0, pack.MAX_PARTITIONS + 1, .95), (0, 4, True), (0, 4, 1), (0, 4, 0)):
            with self.subTest(k=k, n=n, level=level), self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.exact_binomial_interval(k, n, level)
        with self.assertRaisesRegex(ValueError, '^partition-count:'):
            pack.exact_binomial_interval(5, 4)
        for level in (.5, .999):
            self.assertGreater(pack.exact_binomial_interval(0, 4, level)['upper'], 0)
        for constant in ('MAX_ITERATIONS', 'QUANTILE_STEPS'):
            with patch.object(pack, constant, 0), self.assertRaisesRegex(ValueError, '^binomial-convergence:'):
                pack.exact_binomial_interval(2, 4)

    def test_qc_failures_preserve_unavailable_and_counts(self):
        for index, update, reason in ((0, {'positive': 4}, 'singular-positive-fraction'),
                                      (0, {'positive': 3}, 'saturated-well'),
                                      (0, {'total': 3}, 'insufficient-partitions'),
                                      (0, {'positive': 0, 'total': 0}, 'insufficient-partitions'),
                                      (0, {'flag': 'unavailable', 'positive': None, 'total': None}, 'missing-counts'),
                                      (4, {'positive': 1}, 'ntc-failure'),
                                      (4, {'flag': 'unavailable', 'positive': None, 'total': None}, 'ntc-failure')):
            counts = copy.deepcopy(self.documents['counts'])
            counts['rows'][index].update(update)
            result = pack.compute_ddpcr(counts, self.documents['rules'])
            row = result['samples'][0]
            self.assertEqual(row['reason'], reason)
            self.assertEqual(row['concentration_copies_per_ul'], 'unavailable')
            self.assertEqual(row['interval'], 'unavailable')
            if index == 4:
                self.assertEqual(result['summary']['unavailable'], 2)
                self.assertFalse(result['summary']['ntc_passed'])
            self.documents['counts'] = counts
            self.documents['report'].update(result)
            self.assertEqual(pack.validate_ddpcr_absolute_quantification_pack(self.save())['status'], 'arithmetic-only')
            self.documents['counts'] = json.loads((EXAMPLE / 'counts.json').read_text())

    def test_threshold_edges_agreement_and_exploratory(self):
        rules, counts = self.documents['rules'], self.documents['counts']
        rules['saturation_bound'] = .5
        rules['agreement_bound'] = 0
        self.assertEqual(pack.compute_ddpcr(counts, rules)['samples'][0]['status'], 'quantified')
        counts['rows'][1]['positive'] = 1
        bound = (math.log(2) + math.log(.75)) / math.log(2)
        rules['agreement_bound'] = bound
        self.assertEqual(pack.compute_ddpcr(counts, rules)['samples'][0]['status'], 'quantified')
        rules['agreement_bound'] = bound * (1 - 1e-10)
        self.assertEqual(pack.compute_ddpcr(counts, rules)['samples'][0]['reason'], 'replicate-disagreement')
        rounded = float('%.15g' % bound)
        self.assertLess(rounded, bound)
        rules['agreement_bound'] = rounded
        self.assertEqual(pack.compute_ddpcr(counts, rules)['samples'][0]['status'], 'quantified')
        thresholds = {key: rules[key] for key in pack.THRESHOLDS.split()}
        thresholds['saturation_bound'] = .6
        self.documents['report'].update(exploratory=True, thresholds=thresholds)
        self.refresh_report(thresholds)
        self.assertTrue(pack.validate_ddpcr_absolute_quantification_pack(self.save())['exploratory'])
        rules['ntc_maximum_positive'] = 1
        counts['rows'][4]['positive'] = 1
        self.assertTrue(pack.compute_ddpcr(counts, rules)['summary']['ntc_passed'])

    def test_integer_fields_and_numeric_rule_bounds(self):
        rules, counts = self.documents['rules'], self.documents['counts']
        fields = [(rules, key) for key in ('minimum_accepted_partitions', 'ntc_maximum_positive', 'replicate_wells_per_sample')]
        fields += [(counts['rows'][0], key) for key in ('positive', 'total')]
        for record, key in fields:
            original = record[key]
            for value in (True, float(original), str(original), [], -1):
                record[key] = value
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, '^invalid-record:'):
                    pack.compute_ddpcr(counts, rules)
            record[key] = original
        for key in ('partition_volume_ul', 'dilution_factor', 'reaction_to_sample_scaling', 'saturation_bound', 'confidence_level'):
            original = rules[key]
            for value in (0, '1', [], True, float('nan'), float('inf')):
                rules[key] = value
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, '^invalid-record:'):
                    pack.compute_ddpcr(counts, rules)
            rules[key] = original
        for value in (True, 2.0, '2', []):
            self.documents['report']['summary']['n'] = value
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.validate_ddpcr_absolute_quantification_pack(self.save())

    def test_identities_missing_empty_and_pooled_limit(self):
        for target, update, finding in (('counts', lambda doc: doc['rows'][1].update(well_id='a1'), 'duplicate-well'),
                                        ('rules', lambda doc: doc['wells'][1].update(well_id='a1'), 'duplicate-well'),
                                        ('counts', lambda doc: doc['rows'][0].update(sample_id=[]), 'invalid-record'),
                                        ('counts', lambda doc: doc['rows'].pop(0), 'missing-well'),
                                        ('counts', lambda doc: doc.update(rows=[]), 'invalid-record'),
                                        ('rules', lambda doc: doc.update(sample_ids=[]), 'invalid-record'),
                                        ('rules', lambda doc: doc.update(wells=[]), 'invalid-record'),
                                        ('rules', lambda doc: doc.update(replicate_wells_per_sample=1), 'replicate-identity')):
            documents = copy.deepcopy(self.documents)
            update(documents[target])
            with self.subTest(finding=finding), self.assertRaisesRegex(ValueError, '^' + finding + ':'):
                pack.compute_ddpcr(documents['counts'], documents['rules'])
        with patch.object(pack, 'MAX_PARTITIONS', 7), self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack.compute_ddpcr(self.documents['counts'], self.documents['rules'])
        with patch.object(pack, 'MAX_PARTITIONS', 8):
            self.assertEqual(pack.compute_ddpcr(self.documents['counts'], self.documents['rules'])['samples'][0]['total'], 8)

    def test_collection_limits_before_work(self):
        for constant, limit in (('MAX_ROWS', 4), ('MAX_SAMPLES', 1)):
            with patch.object(pack, constant, limit), self.assertRaisesRegex(ValueError, '^input-limit:'):
                pack.compute_ddpcr(self.documents['counts'], self.documents['rules'])
        with patch.object(pack, 'MAX_ROWS', 5), patch.object(pack, 'MAX_SAMPLES', 2):
            pack.compute_ddpcr(self.documents['counts'], self.documents['rules'])
        for value in ([], 0, None, {}, 'rows'):
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack._list(value, 'rows', 2)
        self.assertEqual(pack._list([1, 2], 'edge', 2), [1, 2])
        with patch.object(pack, 'MAX_RECORDS', 0), self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack._claims([self.documents['report']['claims'][0]], {})
        with self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack._json(json.dumps({'x': [0] * (pack.MAX_ROWS + 1)}).encode())

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
            pack.validate_ddpcr_absolute_quantification_pack(self.root / 'pack.json')
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
            pack.validate_ddpcr_absolute_quantification_pack(self.root / 'pack.json')

    def test_final_hash_and_root_recheck(self):
        real_finish = pack._Bundle.finish
        def change(store):
            with (self.root / 'counts.json').open('ab') as stream:
                stream.write(b' ')
            return real_finish(store)
        with patch.object(pack._Bundle, 'finish', change), self.assertRaisesRegex(ValueError, '^input-changed:'):
            pack.validate_ddpcr_absolute_quantification_pack(self.root / 'pack.json')

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
                    pack.validate_ddpcr_absolute_quantification_pack(self.root / 'pack.json')
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
            pack.validate_ddpcr_absolute_quantification_pack(self.root / 'pack.json')

    def evidence(self, kind='computed', result='numerical-agreement', origin='internal'):
        identity = self.documents['pack']['counts']
        self.documents['evidence'] = {'schema': 'ddpcr-evidence-v1', 'fixture': 'synthetic fixture',
                                     'records': [{'id': 'E1', 'kind': kind, 'result': result, 'origin': origin,
                                                  'source': copy.deepcopy(identity)}]}
        self.documents['report']['claims'] = [{'id': 'C1', 'kind': 'descriptive', 'status': 'supported',
                                               'text': 'Synthetic fixture arithmetic matches the supplied table.',
                                               'evidence': ['E1']}]

    def test_claim_kind_and_result_not_labels(self):
        for kind, result in (('review-approval', 'observed'), ('observed', 'review-approval'),
                             ('computed', 'observed'), ('observed', 'numerical-agreement'),
                             ('observed', 'arithmetic-only'), ('ddpcr-result-v1', 'observed')):
            for status in sorted(pack.POSITIVE):
                self.evidence(kind, result)
                self.documents['report']['claims'][0]['status'] = status
                with self.subTest(kind=kind, result=result, status=status), self.assertRaisesRegex(ValueError, '^non-evidence-support:'):
                    pack.validate_ddpcr_absolute_quantification_pack(self.save())

    def test_unavailable_mixed_evidence_all_statuses(self):
        for status in sorted(pack.STATUSES - {'unavailable'}):
            self.evidence('unavailable', 'unavailable')
            self.documents['evidence']['records'].append({**self.documents['evidence']['records'][0],
                                                          'id': 'E2', 'kind': 'observed', 'result': 'observed'})
            self.documents['report']['claims'][0].update(status=status, evidence=['E1', 'E2'])
            with self.subTest(status=status), self.assertRaisesRegex(ValueError, '^unavailable-evidence:'):
                pack.validate_ddpcr_absolute_quantification_pack(self.save())

    def test_claim_empty_unavailable_replication_and_types(self):
        claim = self.documents['report']['claims'][0]
        claim['status'] = 'supported'
        with self.assertRaisesRegex(ValueError, '^missing-evidence:'):
            pack.validate_ddpcr_absolute_quantification_pack(self.save())
        claim.update(status='unavailable', text='Supported synthetic result')
        with self.assertRaisesRegex(ValueError, '^unavailable-positive:'):
            pack.validate_ddpcr_absolute_quantification_pack(self.save())
        self.evidence('observed', 'observed')
        self.documents['report']['claims'][0]['status'] = 'replicated'
        with self.assertRaisesRegex(ValueError, '^claim-replication:'):
            pack.validate_ddpcr_absolute_quantification_pack(self.save())
        for field in ('status', 'kind', 'id'):
            self.documents['report']['claims'][0][field] = []
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.validate_ddpcr_absolute_quantification_pack(self.save())
            self.evidence('observed', 'observed')

    def test_wording_families_and_refusal_order(self):
        words = ('causes', 'mechanism', 'therapeutic', 'clinical', 'efficacy', 'effective', 'treatment', 'cures',
                 'prevents', 'recommended', 'prescribe', 'binding', 'affinity', 'inhibition', 'activation',
                 'regulation', 'drives', 'induction', 'copy-number state', 'gene dosage', 'disease', 'sample suitability', 'truth', 'physical validity')
        for word in words:
            self.evidence()
            self.documents['report']['claims'][0].update(kind='descriptive', text='Synthetic ' + word)
            with self.subTest(word=word), self.assertRaisesRegex(ValueError, '^claim-overreach:'):
                pack.validate_ddpcr_absolute_quantification_pack(self.save())
        self.documents['report']['headline'] = 'Synthetic clinical relevance'
        self.documents['counts']['rows'][0]['positive'] = -1
        with self.assertRaisesRegex(ValueError, '^claim-overreach:'):
            pack.validate_ddpcr_absolute_quantification_pack(self.save())

    def test_external_alias_path_hash_and_hardlink(self):
        for origin in ('external', 'independent', 'preregistered'):
            self.evidence('observed', 'observed', origin)
            with self.subTest(origin=origin), self.assertRaisesRegex(ValueError, '^external-alias:'):
                pack.validate_ddpcr_absolute_quantification_pack(self.save())
        alias = self.root / 'aliased-source'
        os.link(self.root / 'counts.json', alias)
        self.documents['evidence']['records'][0]['source']['path'] = alias.name
        with self.assertRaisesRegex(ValueError, '^external-alias:'):
            pack.validate_ddpcr_absolute_quantification_pack(self.save())

    def test_near_zero_comparison_has_no_absolute_tolerance(self):
        with self.assertRaisesRegex(ValueError, '^reported-number:'):
            pack._same(2e-20, 1e-20, 'small distinct number')
        pack._same(1e-20 * (1 + 1e-10), 1e-20, 'small relative tie')
        pack._same(1e-20 * (1 + 5e-9), 1e-20, 'documented relative tolerance')

    def test_reported_threshold_cannot_drift_within_report_tolerance(self):
        self.documents['report']['thresholds']['saturation_bound'] = 0.7 * (1 + 5e-9)
        with self.assertRaisesRegex(ValueError, '^post-hoc-threshold:'):
            pack.validate_ddpcr_absolute_quantification_pack(self.save())

    def test_saturation_bound_is_inclusive_at_decimal_edge(self):
        rules, counts = self.documents['rules'], self.documents['counts']
        rules['saturation_bound'] = 0.49999999999999994
        self.assertNotEqual(pack.compute_ddpcr(counts, rules)['wells'][1]['reason'], 'saturated-well')

    def test_frozen_echo_paths_use_edge_tolerance(self):
        def nest(path, value):
            return {path[0]: nest(path[1:], value)} if path else value
        drifted = 0.95 * (1 + 5e-9)
        with self.assertRaisesRegex(ValueError, '^reported-number:'):
            pack._same(nest(('interval', 'level'), drifted), nest(('interval', 'level'), 0.95), 'root')
        pack._same(nest(('means', 'level'), drifted), nest(('means', 'level'), 0.95), 'root')

    def test_cli_success_refusal_arguments_and_help(self):
        command = [sys.executable, str(ROOT / 'scripts/validate_ddpcr_absolute_quantification_pack.py')]
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
        self.assertEqual(json.loads(success.stdout)['schema'], 'ddpcr-result-v1')
        self.documents['counts']['rows'][0]['positive'] = True
        refused = subprocess.run(command + [str(self.save())], capture_output=True, text=True, timeout=CALL_TIMEOUT)
        self.assertEqual(refused.returncode, 2)
        self.assertTrue(json.loads(refused.stderr)['finding'].startswith('invalid-record:'))


    def test_artifact_limit_hash_binding_and_freeze_order(self):
        with patch.object(pack, 'MAX_ARTIFACTS', 0), self.assertRaisesRegex(ValueError, '^input-limit:'):
            pack.validate_ddpcr_absolute_quantification_pack(self.root / 'pack.json')
        with patch.object(pack, 'MAX_ARTIFACTS', 4):
            pack.validate_ddpcr_absolute_quantification_pack(self.root / 'pack.json')
        self.documents['pack']['counts']['sha256'] = '0' * 64
        (self.root / 'pack.json').write_text(json.dumps(self.documents['pack']))
        with self.assertRaisesRegex(ValueError, '^input-hash:'):
            pack.validate_ddpcr_absolute_quantification_pack(self.root / 'pack.json')
        self.save()
        self.documents['pack']['frozen_before_counts_read'] = False
        (self.root / 'pack.json').write_text(json.dumps(self.documents['pack']))
        real_load = pack._Bundle.load
        def no_counts(store, name, *args, **kwargs):
            self.assertNotEqual(name, 'counts.json')
            return real_load(store, name, *args, **kwargs)
        with patch.object(pack._Bundle, 'load', no_counts), self.assertRaisesRegex(ValueError, '^rule-freeze:'):
            pack.validate_ddpcr_absolute_quantification_pack(self.root / 'pack.json')

    def test_unavailable_flags_and_report_method(self):
        self.documents['counts']['rows'][0]['flag'] = 'unavailable'
        with self.assertRaisesRegex(ValueError, '^unavailable-as-zero:'):
            pack.compute_ddpcr(self.documents['counts'], self.documents['rules'])
        self.documents['counts']['rows'][0].update(positive=None, total=None)
        self.refresh_report()
        self.assertEqual(pack.validate_ddpcr_absolute_quantification_pack(self.save())['computation']['samples'][0]['reason'],
                         'missing-counts')
        del self.documents['report']['interval_method']
        with self.assertRaisesRegex(ValueError, '^binomial-interval:'):
            pack.validate_ddpcr_absolute_quantification_pack(self.save())


    def test_all_report_integer_fields_are_strict(self):
        report = self.documents['report']
        fields = [(row, key) for row in report['wells'] + report['samples'] for key in ('positive', 'total')]
        fields += [(report['summary'], key) for key in ('n', 'quantified', 'unavailable')]
        for row, key in fields:
            original = row[key]
            for value in (True, float(original), str(original), []):
                row[key] = value
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, '^invalid-record:'):
                    pack.validate_ddpcr_absolute_quantification_pack(self.save())
            row[key] = original

    def test_transformed_interval_singularity_and_nonfinite(self):
        rules = self.documents['rules']
        interval = {'method': 'clopper-pearson-exact', 'level': .95, 'lower': 0, 'upper': 1}
        for upper in (1, 1 - 5e-13):
            interval['upper'] = upper
            with patch.object(pack, 'exact_binomial_interval', return_value=interval):
                with self.assertRaisesRegex(ValueError, '^singular-interval:'):
                    pack._quantities(0, 4, rules)
        interval['upper'] = 1 - 2e-12
        with patch.object(pack, 'exact_binomial_interval', return_value=interval):
            self.assertGreater(pack._quantities(0, 4, rules)['interval']['upper'], 0)
        with patch.object(pack, 'exact_binomial_interval', return_value=interval), \
                patch.object(pack.math, 'log1p', return_value=float('inf')):
            with self.assertRaisesRegex(ValueError, '^degenerate-numerics:'):
                pack._quantities(2, 4, rules)
        for positive, total in ((0, 0), (4, 4)):
            with self.assertRaisesRegex(ValueError, '^singular-positive-fraction:'):
                pack._quantities(positive, total, rules)

    def test_record_key_types_and_empty_evidence_documents(self):
        self.evidence('observed', 'observed')
        for field in ('origin', 'kind', 'result', 'id'):
            original = self.documents['evidence']['records'][0][field]
            self.documents['evidence']['records'][0][field] = []
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, '^invalid-record:'):
                pack.validate_ddpcr_absolute_quantification_pack(self.save())
            self.documents['evidence']['records'][0][field] = original
        self.documents['evidence']['records'] = []
        self.documents['report']['claims'][0].update(status='unavailable', evidence=[])
        pack.validate_ddpcr_absolute_quantification_pack(self.save())
        self.documents['report']['claims'] = []
        pack.validate_ddpcr_absolute_quantification_pack(self.save())


    def test_partition_weighted_pooling_not_mean_concentration(self):
        rules, counts = self.documents['rules'], self.documents['counts']
        rules['agreement_bound'] = .3
        counts['rows'][1]['total'] = 5
        self.documents['report']['thresholds']['agreement_bound'] = .3
        self.refresh_report()
        result = pack.validate_ddpcr_absolute_quantification_pack(self.save())
        a = result['computation']['samples'][0]
        self.assertEqual((a['positive'], a['total']), (4, 9))
        self.assertTrue(math.isclose(a['lambda'], -math.log(5 / 9), rel_tol=1e-12))
        average = math.fsum(row['concentration_copies_per_ul'] for row in result['computation']['wells'][:2]) / 2
        self.assertFalse(math.isclose(average, a['concentration_copies_per_ul'], rel_tol=pack.RELATIVE_TOLERANCE))
        self.documents['report']['samples'][0]['concentration_copies_per_ul'] = average
        with self.assertRaisesRegex(ValueError, '^concentration-scaling:'):
            pack.validate_ddpcr_absolute_quantification_pack(self.save())

    def test_interval_label_cannot_hide_normal_numbers(self):
        self.documents['report']['samples'][0]['interval'].update(lower=0, upper=12)
        with self.assertRaisesRegex(ValueError, '^reported-number:'):
            pack.validate_ddpcr_absolute_quantification_pack(self.save())
        self.refresh_report()
        for key in ('dilution_factor', 'reaction_to_sample_scaling', 'partition_volume_ul'):
            original = self.documents['rules'][key]
            self.documents['rules'][key] = original * 2
            result = pack.compute_ddpcr(self.documents['counts'], self.documents['rules'])
            expected = 6 * math.log(2) if key == 'partition_volume_ul' else 24 * math.log(2)
            self.assertTrue(math.isclose(result['samples'][0]['concentration_copies_per_ul'], expected, rel_tol=1e-12))
            self.documents['rules'][key] = original


    def test_rule_numeric_limit_edges_and_failure_exits(self):
        bounds = {'minimum_accepted_partitions': (1, pack.MAX_PARTITIONS),
                  'ntc_maximum_positive': (0, pack.MAX_PARTITIONS),
                  'saturation_bound': (1e-9, 1 - 1e-9), 'agreement_bound': (0, 1),
                  'partition_volume_ul': (1e-12, 1e6), 'dilution_factor': (1e-12, 1e12),
                  'reaction_to_sample_scaling': (1e-12, 1e12), 'confidence_level': (.5, .999)}
        rules, counts = self.documents['rules'], self.documents['counts']
        for key, (low, high) in bounds.items():
            original = rules[key]
            for edge in (low, high):
                rules[key] = edge
                pack.compute_ddpcr(counts, rules)
            for invalid in (low - 1 if type(low) is int else low / 2, high * 2, []):
                rules[key] = invalid
                with self.subTest(key=key, invalid=invalid), self.assertRaisesRegex(ValueError, '^invalid-record:'):
                    pack.compute_ddpcr(counts, rules)
            rules[key] = original

    def test_empty_zero_and_equal_resource_limits(self):
        with patch.object(pack, 'MAX_DEPTH', 0):
            self.assertEqual(pack._json(b'{}')[0], {})
            with self.assertRaisesRegex(ValueError, '^invalid-json:'):
                pack._json(b'{"x":0}')
        with patch.object(pack, 'MAX_STRING', 1):
            pack._json(b'{"x":"y"}')
            for raw in (b'{"x":""}', b'{"x":"yy"}'):
                with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                    pack._json(raw)
        (self.root / 'tiny.json').write_bytes(b'{}')
        with patch.object(pack, 'MAX_BYTES', 2), patch.object(pack, 'MAX_TOTAL_BYTES', 2), \
                patch.object(pack, 'MAX_NODES', 1), patch.object(pack, 'MAX_ARTIFACTS', 1):
            store = pack._Bundle(self.root)
            try:
                self.assertEqual(store.load('tiny.json'), {})
                self.assertEqual(store.load('tiny.json'), {})
                store.finish()
                with self.assertRaisesRegex(ValueError, '^input-limit:'):
                    store.load('counts.json')
            finally:
                store.close()
        for constant in ('MAX_BYTES', 'MAX_TOTAL_BYTES', 'MAX_NODES', 'MAX_ARTIFACTS'):
            with patch.object(pack, constant, 0):
                store = pack._Bundle(self.root)
                try:
                    with self.assertRaisesRegex(ValueError, '^(input-file|input-limit):'):
                        store.load('tiny.json')
                finally:
                    store.close()


def _seeded_test(case):
    def test(self):
        self.run_case(case)
    return test


for _case in CASES:
    setattr(DDPCRPackTests, 'test_seed_' + _case['id'].replace('-', '_'), _seeded_test(_case))


if __name__ == '__main__':
    unittest.main()
