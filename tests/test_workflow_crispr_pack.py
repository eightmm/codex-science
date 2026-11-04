"""Synthetic CRISPR arithmetic, frozen controls and hostile-input acceptance."""
import copy
import hashlib
import importlib
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

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'examples/workflow-crispr-screen-qc'
CLI = ROOT / 'scripts/validate_crispr_screen_pack.py'
CALL_TIMEOUT = float(os.environ.get('OMS_TEST_CALL_TIMEOUT', '30'))


class _Fixture(unittest.TestCase):
    def setUp(self):
        self.api = importlib.import_module('codex_science.crispr_screen_pack')
        self.pack = json.loads((FIXTURE / 'pack.json').read_bytes())
        self.values = {name: json.loads((FIXTURE / self.pack['inputs'][name]['path']).read_bytes())
                       for name in self.pack['inputs']}

    def folder(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        parent = Path(temporary.name) / 'parent'
        folder = parent / 'bundle'
        folder.mkdir(parents=True)
        for source in FIXTURE.glob('*.json'):
            shutil.copyfile(source, folder / source.name)
        return folder

    def write(self, folder, name, value):
        raw = (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode()
        (folder / name).write_bytes(raw)
        return {'path': name, 'sha256': hashlib.sha256(raw).hexdigest()}

    def input(self, folder, name, value, freeze=True):
        self.pack['inputs'][name] = self.write(folder, name + '.json', value)
        if freeze and name in ('library', 'design'):
            self.pack['frozen_' + name + '_sha256'] = self.pack['inputs'][name]['sha256']

    def compute(self):
        return self.api.reference_computation(*(self.values[key] for key in ('rules', 'library', 'design', 'counts')))

    def run_pack(self, folder, recompute=False):
        if recompute:
            self.input(folder, 'report', self.compute())
        self.write(folder, 'pack.json', self.pack)
        return self.api.validate_crispr_screen_pack(folder / 'pack.json')

    def cli(self, *args):
        return subprocess.run([sys.executable, str(CLI), *map(str, args)], capture_output=True,
                              text=True, timeout=CALL_TIMEOUT)


class CrisprReferenceTests(_Fixture):
    def test_fixture_expected_and_hand_calculations(self):
        actual = self.api.validate_crispr_screen_pack(FIXTURE / 'pack.json')
        self.assertEqual(json.loads((FIXTURE / 'expected.json').read_bytes()), actual)
        self.assertEqual(actual, self.api.validate_crispr_screen_pack(FIXTURE / 'pack.json'))
        self.assertEqual('unavailable', actual['review'])
        report = actual['report']
        self.assertEqual([1100, 2550, 2200, 5100], [row['total_reads'] for row in report['qc']])
        self.assertEqual([total / 2375 for total in [1100, 2550, 2200, 5100]], report['normalization_factors'])
        self.assertEqual(1, report['library_coverage'])
        self.assertEqual(0, report['qc'][0]['gini'])
        counts = [50, 100, 100, 100, 100, 100, 200, 200, 400, 400, 800]
        hand_gini = sum(abs(a-b) for a in counts for b in counts) / (2 * 11 * 2550)
        self.assertAlmostEqual(hand_gini, report['qc'][1]['gini'])
        genes = {row['gene_id']: row for row in report['genes']}
        def change(count):
            return math.log2((count * 2375 / 2550 + 1) / (100 * 2375 / 1100 + 1))
        null_center = (change(100) + change(200)) / 2
        self.assertAlmostEqual(change(400) - null_center, genes['A']['log2_fold_change'])
        # Every size-three subset of four ordered controls has an inner median.
        # A exceeds both inner absolute values: zero of 99 null draws exceed it.
        self.assertEqual(1 / 100, genes['A']['p_value'])
        self.assertEqual(2 / 100, genes['A']['q_value'])
        self.assertTrue(genes['A']['significant'])
        self.assertFalse(genes['B']['significant'])
        self.assertEqual(1, genes['B']['p_value'])
        self.assertEqual('unavailable', genes['U']['status'])
        self.assertIsNone(genes['U']['significant'])
        self.assertEqual(1, report['concordance'][0]['pearson'])
        result = self.cli(FIXTURE / 'pack.json')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(actual, json.loads(result.stdout))

    def test_reference_numerics_and_degenerate_vectors(self):
        self.assertEqual([0.03, 0.04, 0.04], self.api.benjamini_hochberg([0.01, 0.04, 0.03]))
        self.assertEqual([], self.api.benjamini_hochberg([]))
        self.assertEqual([0, 1], self.api.benjamini_hochberg([0, 1]))
        self.assertAlmostEqual(-1, self.api.pearson([1, 2, 3], [3, 2, 1]))
        self.assertAlmostEqual(-1, self.api.pearson([1e-200, 2e-200, 3e-200], [3e-200, 2e-200, 1e-200]))
        for first, second in [([], []), ([1], [1]), ([1, 2], [1, 2]), ([1, 1, 1], [1, 2, 3]),
                              ([1, 2, 3], [2, 2, 2]), ([1, 2, 3], [1, 2]),
                              ([True, 2, 3], [1, 2, 3]), ([float('nan'), 2, 3], [1, 2, 3])]:
            with self.subTest(first=first, second=second), self.assertRaisesRegex(ValueError, r'^[a-z-]+:'):
                self.api.pearson(first, second)
        for value in [[True], [-0.1], [1.1], [float('inf')], 'bad']:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, r'^invalid-record:'):
                self.api.benjamini_hochberg(value)
        for row in self.values['counts']['rows'][-4:]:
            row['counts'] = [100, 100, 200, 200]
        with self.assertRaisesRegex(ValueError, '^degenerate-null:'):
            self.compute()

    def test_failed_qc_and_concordance_remain_unavailable(self):
        folder = self.folder()
        negative = json.loads((FIXTURE / 'negative.low-reads-summary.counts.json').read_bytes())
        self.values['counts'] = negative
        self.input(folder, 'counts', negative)
        actual = self.run_pack(folder, recompute=True)['report']
        self.assertFalse(actual['pooled'])
        self.assertIn('minimum-reads', actual['qc'][1]['failures'])
        self.assertTrue(all(row['status'] == 'unavailable' and row['significant'] is None for row in actual['genes']))
        negative = json.loads((FIXTURE / 'negative.discordant-pooling.counts.json').read_bytes())
        self.values['counts'] = negative
        self.input(folder, 'counts', negative)
        actual = self.run_pack(folder, recompute=True)['report']
        self.assertFalse(actual['pooled'])
        self.assertFalse(actual['concordance'][0]['passed'])
        self.assertTrue(all(row['status'] == 'unavailable' for row in actual['genes']))

    def test_exploration_missing_guides_and_equal_thresholds(self):
        folder = self.folder()
        self.pack['exploratory'] = True
        self.values['rules']['normalization'] = 'median-of-ratios'
        self.input(folder, 'rules', self.values['rules'])
        self.assertTrue(self.run_pack(folder, recompute=True)['exploratory'])
        self.values['counts']['rows'].pop(0)
        self.input(folder, 'counts', self.values['counts'])
        report = self.run_pack(folder, recompute=True)['report']
        self.assertAlmostEqual(10 / 11, report['library_coverage'])
        self.assertEqual('unavailable', report['genes'][0]['status'])
        self.assertNotIn('a1', [row['guide_id'] for row in report['guide_fold_changes']])
        rules = self.values['rules']
        rules.update(minimum_total_reads=min(row['total_reads'] for row in report['qc']),
                     minimum_detection_fraction=10/11, concordance_threshold=report['concordance'][0]['pearson'])
        self.assertTrue(self.compute()['pooled'])
        rules['minimum_detection_fraction'] = 1
        self.assertTrue(all(row['status'] == 'unavailable' for row in self.compute()['genes']))

    def test_integer_fields_and_wrong_types(self):
        folder = self.folder()
        integer_keys = ('schema_version', 'minimum_total_reads', 'minimum_guides', 'minimum_controls',
                        'minimum_replicates', 'permutation_seed', 'permutation_count')
        for key in integer_keys:
            for value in (True, float(self.values['rules'][key]), str(self.values['rules'][key])):
                rules = copy.deepcopy(self.values['rules']); rules[key] = value
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, '^invalid-record:'):
                    self.api.reference_computation(rules, self.values['library'], self.values['design'], self.values['counts'])
        for record in ('library', 'design', 'counts'):
            value = copy.deepcopy(self.values[record]); value['schema_version'] = 1.0
            self.input(folder, record, value)
            with self.subTest(record=record), self.assertRaisesRegex(ValueError, '^invalid-record:'):
                self.run_pack(folder)
            self.input(folder, record, self.values[record])
        for field in ('status', 'kind', 'gene_id', 'id'):
            claim = self.pack['claims'][0]; original = claim[field]; claim[field] = []
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, '^invalid-record:'):
                self.run_pack(folder)
            claim[field] = original
        for value in (True, 0.5, '0'):
            self.values['design']['samples'][0]['timepoint'] = value
            with self.subTest(timepoint=value), self.assertRaisesRegex(ValueError, '^invalid-record:'):
                self.compute()
        report = copy.deepcopy(self.values['report']); report['qc'][0]['total_reads'] = 1100.0
        self.input(folder, 'report', report)
        with self.assertRaisesRegex(ValueError, '^report-mismatch:'):
            self.run_pack(folder)

    def test_freeze_order_and_pack_contract(self):
        names = []
        snapshot = self.api._Bundle.snapshot
        def record(bundle, path):
            names.append(path.as_posix())
            return snapshot(bundle, path)
        with patch.object(self.api._Bundle, 'snapshot', record):
            self.api.validate_crispr_screen_pack(FIXTURE / 'pack.json')
        for name in ('frozen_rules.json', 'rules.json', 'library.json', 'design.json'):
            self.assertLess(names.index(name), names.index('counts.json'))
        skill = ROOT / 'authored-skills/workflow-crispr-screen-qc'
        text = (skill / 'SKILL.md').read_text()
        description = next(line for line in text.splitlines() if line.startswith('description:'))
        self.assertNotRegex(description.lower(), r'\b(?:workflow|analysis|statistics|pipeline)\b')
        quality = json.loads((skill / 'quality.json').read_bytes())
        cases = json.loads((FIXTURE / 'negative-cases.json').read_bytes())['cases']
        self.assertEqual({case['id'] for case in cases}, set(quality['seeded_failures']))
        self.assertEqual(['tests/test_workflow_crispr_pack.py'], quality['test_files'])
        plan = json.loads((skill / 'references/plan.json').read_bytes())['plan']
        self.assertEqual(list(self.api.STAGES), [step['id'] for step in plan])
        for step in plan:
            self.assertEqual({'id', 'description', 'status'}, set(step))


class CrisprLimitsTests(_Fixture):
    def test_dimension_limits_before_scaled_work(self):
        for constant, equal, finding in [('MAX_GUIDES', 11, 'input-limit'), ('MAX_GENES', 3, 'input-limit'),
                                          ('MAX_VALUES', 44, 'input-limit'), ('MAX_DRAWS', 99, 'invalid-record'),
                                          ('MAX_DRAW_WORK', 693, 'input-limit')]:
            with self.subTest(constant=constant), patch.object(self.api, constant, equal):
                self.compute()
            with self.subTest(constant=constant), patch.object(self.api, constant, equal-1):
                with self.assertRaisesRegex(ValueError, '^' + finding + ':'):
                    self.compute()
            with self.subTest(constant=constant), patch.object(self.api, constant, 0):
                with self.assertRaisesRegex(ValueError, r'^[a-z-]+:'):
                    self.compute()
        with patch.object(self.api, 'MAX_SAMPLES', 4):
            self.compute()
            self.values['design']['samples'].append(copy.deepcopy(self.values['design']['samples'][0]))
            with self.assertRaisesRegex(ValueError, '^input-limit:'):
                self.compute()
        library = copy.deepcopy(self.values['library'])
        library['guides'] = [library['guides'][0]] * (self.api.MAX_GUIDES + 1)
        with self.assertRaisesRegex(ValueError, '^input-limit:'):
            self.api.reference_computation(self.values['rules'], library, self.values['design'], self.values['counts'])
        for key in ('guides',):
            library[key] = []
            with self.assertRaisesRegex(ValueError, '^invalid-record:'):
                self.api.reference_computation(self.values['rules'], library, self.values['design'], self.values['counts'])

    def test_bytes_nodes_artifacts_and_hardlink_cache(self):
        folder = self.folder()
        frozen = folder / 'frozen_rules.json'
        (folder / 'rules.json').unlink()
        os.link(frozen, folder / 'rules.json')
        total = sum((folder / name).stat().st_size for name in ['pack.json','frozen_rules.json','library.json','design.json','counts.json','report.json'])
        with self.api._Bundle(folder / 'pack.json') as bundle:
            self.api._validate(bundle)
            self.assertEqual(total, bundle.bytes_read)
            nodes = bundle.nodes_read
            self.assertEqual(6, len(bundle.artifacts))
        with patch.object(self.api, 'MAX_TOTAL_BYTES', total), patch.object(self.api, 'MAX_TOTAL_NODES', nodes), patch.object(self.api.re, 'findall', side_effect=AssertionError('must use finditer')):
            self.api.validate_crispr_screen_pack(folder / 'pack.json')
        for constant, value in [('MAX_TOTAL_BYTES', total-1), ('MAX_TOTAL_NODES', nodes-1), ('MAX_ARTIFACTS', 6)]:
            with self.subTest(constant=constant), patch.object(self.api, constant, value):
                with self.assertRaisesRegex(ValueError, '^input-limit:'):
                    self.api.validate_crispr_screen_pack(folder / 'pack.json')
        with patch.object(self.api, 'MAX_ARTIFACTS', 7):
            self.api.validate_crispr_screen_pack(folder / 'pack.json')
        with patch.object(self.api.json, 'loads', side_effect=AssertionError('preparse allowance first')):
            with self.assertRaisesRegex(ValueError, '^input-limit:'):
                self.api._json(b'{"x":[1,2,3]}', 2)
        raw = b'{"a":[1]}'
        self.api._json(raw, 3)
        with self.assertRaisesRegex(ValueError, '^input-limit:'):
            self.api._json(raw, 2)
        with patch.object(self.api, 'MAX_DEPTH', 1):
            self.api._json(b'{"x":[]}', 20)
            with self.assertRaisesRegex(ValueError, '^invalid-json:'):
                self.api._json(b'{"x":[[]]}', 20)
        with patch.object(self.api, 'MAX_TEXT', 1):
            self.api._json(b'{"x":"y"}', 20)
            with self.assertRaisesRegex(ValueError, '^input-limit:'):
                self.api._json(b'{"x":"yy"}', 20)

    def test_integer_ranges_empty_zero_equal_and_malformed(self):
        for key, low, high in [('permutation_count',1,99), ('permutation_seed',0,2**32-1),
                               ('minimum_guides',1,11), ('minimum_controls',2,4), ('minimum_replicates',2,2)]:
            for value in ([], '', -1, True, 1.5):
                rules = copy.deepcopy(self.values['rules']); rules[key] = value
                with self.subTest(key=key,value=value), self.assertRaisesRegex(ValueError, '^invalid-record:'):
                    self.api._rules(rules)
            for value in (low,high):
                rules = copy.deepcopy(self.values['rules']); rules[key] = value
                self.api._rules(rules)
        self.values['rules']['permutation_count'] = 1
        self.assertTrue(all(row['p_value'] in (None,0.5,1) for row in self.compute()['genes']))
        self.values['counts']['rows'][0]['counts'][0] = 0
        self.assertEqual('unavailable', self.compute()['genes'][0]['status'])
        self.values['counts']['rows'] = []
        with self.assertRaisesRegex(ValueError, '^invalid-record:'):
            self.compute()

    def test_remaining_container_and_numeric_edges(self):
        folder = self.folder()
        files = [folder / name for name in ['pack.json', 'frozen_rules.json', 'rules.json',
                                             'library.json', 'design.json', 'counts.json', 'report.json']]
        limit = max(path.stat().st_size for path in files)
        with patch.object(self.api, 'MAX_BYTES', limit):
            self.api.validate_crispr_screen_pack(folder / 'pack.json')
        with patch.object(self.api, 'MAX_BYTES', limit-1), self.assertRaisesRegex(ValueError, '^input-file:'):
            self.api.validate_crispr_screen_pack(folder / 'pack.json')
        with patch.object(self.api, 'MAX_ITEMS', 1):
            self.api._json(b'{"a":[]}', 20)
            with self.assertRaisesRegex(ValueError, '^input-limit:'):
                self.api._json(b'{"a":1,"b":2}', 20)
        with patch.object(self.api, 'MAX_CLAIMS', 1):
            self.run_pack(folder)
            self.pack['claims'].append(copy.deepcopy(self.pack['claims'][0]))
            with self.assertRaisesRegex(ValueError, '^input-limit:'):
                self.run_pack(folder)
        self.pack['claims'] = []
        with patch.object(self.api, 'MAX_CLAIMS', 0):
            self.run_pack(folder)
        self.values['counts']['rows'][0]['counts'][0] = self.api.MAX_COUNT
        self.compute()
        self.values['counts']['rows'][0]['counts'][0] += 1
        with self.assertRaisesRegex(ValueError, '^invalid-count:'):
            self.compute()


class CrisprInputTests(_Fixture):
    def test_json_refusals(self):
        folder = self.folder()
        for raw in (b'[]', b'{', b'{"x":1,"x":2}', b'{"x":{"y":1,"y":2}}', b'{"x":NaN}',
                    b'{"x":Infinity}', b'{"x":1e10000}', b'{"x":' + b'9'*5000 + b'}', b'\xff',
                    b'{"x":' + b'['*1500 + b'0' + b']'*1500 + b'}'):
            (folder / 'pack.json').write_bytes(raw)
            with self.subTest(raw=raw[:40]), self.assertRaisesRegex(ValueError, r'^(invalid-json|invalid-record):'):
                self.api.validate_crispr_screen_pack(folder / 'pack.json')
        result = self.cli(folder / 'pack.json')
        self.assertEqual(2, result.returncode)
        self.assertEqual('refused', json.loads(result.stderr)['status'])
        self.assertNotIn('Traceback', result.stderr)

    def test_path_special_file_and_size_refusals(self):
        folder = self.folder()
        for path in ('../counts.json', '/counts.json', 'a\\counts.json', './counts.json', 'a//b', 'C:counts.json', 'a\x00b'):
            original = self.pack['inputs']['counts']['path']; self.pack['inputs']['counts']['path'] = path
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, '^input-path:'):
                self.run_pack(folder)
            self.pack['inputs']['counts']['path'] = original
        target = folder / 'counts.json'
        target.unlink(); os.mkfifo(target)
        with self.assertRaisesRegex(ValueError, '^input-file:'):
            self.run_pack(folder)
        target.unlink(); target.mkdir()
        with self.assertRaisesRegex(ValueError, '^input-file:'):
            self.run_pack(folder)
        target.rmdir(); target.symlink_to(folder / 'library.json')
        with self.assertRaisesRegex(ValueError, '^input-file:'):
            self.run_pack(folder)
        target.unlink()
        with target.open('wb') as handle: handle.truncate(self.api.MAX_BYTES+1)
        with self.assertRaisesRegex(ValueError, '^input-file:'):
            self.run_pack(folder)
        sub = folder / 'alias'; sub.symlink_to(folder, target_is_directory=True)
        self.pack['inputs']['counts']['path'] = 'alias/counts.json'
        with self.assertRaisesRegex(ValueError, '^input-file:'):
            self.run_pack(folder)

    def test_hash_replacement_and_growing_read(self):
        folder = self.folder()
        self.pack['inputs']['counts']['sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, '^input-hash:'):
            self.run_pack(folder)
        self.pack = json.loads((FIXTURE / 'pack.json').read_bytes())
        real_claims = self.api._claims
        def replace(bundle, pack, report):
            real_claims(bundle, pack, report)
            target = folder / 'counts.json'
            target.rename(folder / 'old-counts.json')
            target.write_bytes((folder / 'old-counts.json').read_bytes())
        with patch.object(self.api, '_claims', replace), self.assertRaisesRegex(ValueError, '^input-changed:'):
            self.run_pack(folder)
        folder = self.folder()
        real_fdopen = os.fdopen
        class Growing:
            def __init__(self, handle): self.handle = handle
            def __enter__(self): return self
            def __exit__(self, *args): self.handle.close()
            def fileno(self): return self.handle.fileno()
            def read(self, size):
                raw = self.handle.read(size)
                with (folder / 'pack.json').open('ab') as handle: handle.write(b' ')
                return raw
        with patch.object(self.api.os, 'fdopen', lambda fd, mode: Growing(real_fdopen(fd, mode))):
            with self.assertRaisesRegex(ValueError, '^input-file:'):
                self.run_pack(folder)

    def test_root_and_transient_ancestor_swaps(self):
        for swap in ('bundle','parent'):
            folder = self.folder(); real_open = os.open; done = []
            victim = folder if swap == 'bundle' else folder.parent
            def swapped(name, flags, *args, **kwargs):
                if name == victim.name and kwargs.get('dir_fd') is not None and not done:
                    done.append(True)
                    parked = victim.with_name(victim.name+'-parked')
                    victim.rename(parked); victim.symlink_to(parked, target_is_directory=True)
                return real_open(name,flags,*args,**kwargs)
            with self.subTest(swap=swap), patch.object(self.api.os, 'open', swapped):
                with self.assertRaisesRegex(ValueError, r'^(input-root|input-file):'):
                    self.api.validate_crispr_screen_pack(folder / 'pack.json')
            self.assertTrue(done)
        folder = self.folder(); real_lstat = os.lstat; done = []
        def lstat_swap(name, *args, **kwargs):
            info = real_lstat(name,*args,**kwargs)
            if name == folder.name and kwargs.get('dir_fd') is not None and not done:
                done.append(True); folder.rename(folder.with_name('parked')); folder.mkdir()
            return info
        with patch.object(self.api.os,'lstat',lstat_swap), self.assertRaisesRegex(ValueError,'^input-root:'):
            self.api.validate_crispr_screen_pack(folder / 'pack.json')

    def test_full_ancestor_chain_when_bundle_inode_stays(self):
        folder = self.folder(); original_inode = folder.stat().st_ino
        real_claims = self.api._claims
        def swap_parent(bundle, pack, report):
            real_claims(bundle,pack,report)
            parent = folder.parent; parked = parent.with_name('parked-parent')
            parent.rename(parked); parent.mkdir(); (parked / folder.name).rename(folder)
            self.assertEqual(original_inode, folder.stat().st_ino)
        with patch.object(self.api,'_claims',swap_parent), self.assertRaisesRegex(ValueError,'^input-changed:'):
            self.api.validate_crispr_screen_pack(folder / 'pack.json')

    def test_cli_argument_errors_help_and_no_writes(self):
        for args in ((), ('one','two'), ('--unknown',), (FIXTURE / 'pack.json','--output','other.json')):
            result = self.cli(*args)
            with self.subTest(args=args):
                self.assertEqual(2,result.returncode)
                self.assertEqual('',result.stdout)
                self.assertTrue(json.loads(result.stderr)['finding'].startswith('invalid-arguments:'))
        result = self.cli('--help')
        self.assertEqual(0,result.returncode); self.assertEqual('',result.stderr)
        self.assertIn('usage:',result.stdout)
        folder = self.folder()
        before = {path.name:path.read_bytes() for path in folder.iterdir()}
        self.api.validate_crispr_screen_pack(folder / 'pack.json')
        self.api.validate_crispr_screen_pack(folder / 'pack.json')
        self.assertEqual(before,{path.name:path.read_bytes() for path in folder.iterdir()})


class CrisprClaimTests(_Fixture):
    def test_wording_families_and_status_types(self):
        folder = self.folder()
        words = ('causes','mechanisms','therapeutic','clinical','efficacy','effective','treatment','cures',
                 'prevention','recommendation','prescription','binding','affinity','inhibition','activation',
                 'regulation','drive','drives','driven','induction','essentiality','drug target','physical validity')
        for word in words:
            self.pack['claims'][0]['text'] = 'Synthetic fixture establishes ' + word.upper() + '.'
            with self.subTest(word=word), self.assertRaisesRegex(ValueError, '^claim-boundary:'):
                self.run_pack(folder)
        self.pack['claims'][0]['text'] = 'Synthetic fixture observation.'
        for status in ('supported','suggestive','replicated','planned','conflicting','unsupported','withdrawn'):
            self.pack['claims'][0]['status'] = status
            with self.subTest(status=status), self.assertRaisesRegex(ValueError,'^unavailable-evidence:'):
                self.run_pack(folder)

    def test_any_unavailable_citation_and_external_aliases(self):
        folder = self.folder()
        def evidence(kind,result,origin='study'):
            return {'schema':'crispr-evidence-v1','schema_version':1,'fixture':True,
                    'kind':kind,'result':result,'origin':origin,'gene_id':'A'}
        observed = self.write(folder,'observed.json',evidence('guide-count-observation','gene-level-association'))
        missing = self.write(folder,'missing.json',evidence('unavailable','unavailable'))
        for status in ('supported','suggestive','replicated','planned','conflicting','unsupported','withdrawn'):
            self.pack['claims'][0].update(status=status,support=[observed,missing])
            with self.subTest(status=status), self.assertRaisesRegex(ValueError,'^unavailable-evidence:'):
                self.run_pack(folder)
        self.pack['claims'][0].update(status='unavailable',support=[observed,missing])
        self.run_pack(folder)
        for origin in ('external','independent','preregistered'):
            own = self.write(folder,'own.json',evidence('guide-count-observation','gene-level-association',origin))
            self.pack['study_outputs']=[own]
            alias = dict(own); alias['path']='copy.json'; shutil.copyfile(folder / 'own.json',folder / 'copy.json')
            self.pack['claims'][0].update(status='supported',support=[alias])
            with self.subTest(origin=origin), self.assertRaisesRegex(ValueError,'^dependent-evidence:'):
                self.run_pack(folder)

    def test_arithmetic_and_result_schema_are_non_evidence(self):
        folder = self.folder()
        for field in ('kind', 'result'):
            for value in ('arithmetic-only', 'crispr-result-v1'):
                with self.subTest(field=field, value=value):
                    record = {'schema': 'crispr-evidence-v1', 'schema_version': 1, 'fixture': True,
                              'kind': 'guide-count-observation', 'result': 'gene-level-association',
                              'origin': 'study', 'gene_id': 'A'}
                    record[field] = value
                    identity = self.write(folder, 'observed.json', record)
                    self.pack['claims'][0].update(status='supported', support=[identity])
                    with self.assertRaisesRegex(ValueError, '^claim-evidence:'):
                        self.run_pack(folder)
                    # The exact evidence whitelist also refuses these records.
                    self.assertIsNotNone(self.api.NON_EVIDENCE.search(value))

    def test_support_limits_and_positive_exploratory_claims(self):
        folder = self.folder()
        record = {'schema':'crispr-evidence-v1','schema_version':1,'fixture':True,
                  'kind':'guide-count-observation','result':'gene-level-association','origin':'study','gene_id':'A'}
        identity = self.write(folder, 'observed.json', record)
        self.pack['claims'][0].update(status='supported',support=[identity])
        with patch.object(self.api, 'MAX_SUPPORT', 1):
            self.run_pack(folder)
            self.pack['claims'][0]['support'].append(identity)
            with self.assertRaisesRegex(ValueError, '^input-limit:'):
                self.run_pack(folder)
        self.pack['claims'][0]['support'] = [identity]
        self.pack['exploratory'] = True
        with self.assertRaisesRegex(ValueError, '^claim-boundary:'):
            self.run_pack(folder)
        self.pack['claims'][0]['status'] = 'suggestive'
        self.run_pack(folder)
        for field in ('kind','result','origin','gene_id'):
            original = record[field]; record[field] = []
            self.pack['claims'][0]['support'] = [self.write(folder, 'observed.json', record)]
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, '^invalid-record:'):
                self.run_pack(folder)
            record[field] = original


class CrisprSeededTests(_Fixture):
    pass


def _seeded(case):
    def test(self):
        with self.assertRaisesRegex(ValueError, '^' + case['finding'] + ':'):
            self.api.validate_crispr_screen_pack(FIXTURE / case['bundle'])
        result = self.cli(FIXTURE / case['bundle'])
        self.assertEqual(2,result.returncode)
        self.assertEqual('',result.stdout)
        self.assertTrue(json.loads(result.stderr)['finding'].startswith(case['finding'] + ':'))
    return test


for _case in json.loads((FIXTURE / 'negative-cases.json').read_bytes())['cases']:
    setattr(CrisprSeededTests,'test_'+_case['id'].replace('-','_'),_seeded(_case))


if __name__ == '__main__':
    unittest.main()
