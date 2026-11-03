import copy
import json
import os
import tempfile
from pathlib import Path
import subprocess
import sys
import unittest
from codex_science.protein_variants import analyze_protein_variants

ROOT = Path(__file__).resolve().parents[1]


class ProteinVariantWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.record = json.loads((ROOT / 'examples/protein-variant-evaluation/input.json').read_text())
        self.p = self.record['proteins'][0]

    def test_sequences_direction_ties_missing_baseline(self):
        result = analyze_protein_variants(self.record)
        p = result['proteins'][0]
        self.assertEqual(p['variants'][2]['sequence'], 'VSDEFG')
        self.assertEqual(p['variants'][2]['edit_distance'], 2)
        self.assertEqual(p['variants'][1]['model_rank'], 2.5)
        self.assertAlmostEqual(p['model_vs_assay_spearman']['value'], 1)
        self.assertAlmostEqual(p['baseline_vs_assay_spearman']['value'], 0.9486832980505138)
        self.assertEqual((p['total'], p['paired']), (5, 4))
        self.assertEqual(p['variants'][-1]['model']['status'], 'failed')
        self.assertIsNone(result['pooled_metric'])
        self.assertTrue(result['baseline']['model_free'])

    def test_wt_offset_indel_overlap_noop(self):
        for edits in [['C11V'], ['A1V'], ['A11del'], ['A11V','A11L'], ['A11A']]:
            with self.subTest(edits=edits):
                r = copy.deepcopy(self.record)
                r['proteins'][0]['variants'][1]['substitutions'] = edits
                with self.assertRaises(ValueError): analyze_protein_variants(r)
        self.p['coordinate_offset'] = True
        with self.assertRaises(ValueError): analyze_protein_variants(self.record)

    def test_duplicate_ids_and_sequences(self):
        for change in ('id','sequence','protein'):
            r = copy.deepcopy(self.record)
            if change == 'id': r['proteins'][0]['variants'][1]['id'] = 'WT'
            elif change == 'sequence': r['proteins'][0]['variants'][1]['substitutions'] = []
            else: r['proteins'].append(copy.deepcopy(self.p))
            with self.subTest(change=change), self.assertRaises(ValueError): analyze_protein_variants(r)

    def test_leakage(self):
        for mode in ('homology','exact','variant'):
            r = copy.deepcopy(self.record)
            q = copy.deepcopy(self.p)
            q.update(id='other',split='train')
            if mode != 'homology': q['homology_group'] = 'different'
            if mode == 'homology': q['reference'] = 'ACDEFA'
            if mode == 'variant': q['reference'] = 'VCDEFG'
            r['proteins'].append(q)
            with self.subTest(mode=mode), self.assertRaises(ValueError): analyze_protein_variants(r)

    def test_constant_and_unavailable(self):
        for v in self.p['variants']:
            v['assay']['value'] = 1
        p = analyze_protein_variants(self.record)['proteins'][0]
        self.assertEqual(p['model_vs_assay_spearman']['reason'], 'constant-ranks')
        for v in self.p['variants']:
            v['model'] = {'status':'missing','value':None,'units':'toy-NLL','reason':'not supplied'}
        p = analyze_protein_variants(self.record)['proteins'][0]
        self.assertEqual(p['paired'], 0)
        self.assertEqual(p['model_vs_assay_spearman']['reason'], 'fewer-than-two-pairs')

    def test_invalid_numeric_direction_units_status(self):
        for value in (True, '1', float('nan'), float('inf'), 10**400):
            r = copy.deepcopy(self.record)
            r['proteins'][0]['variants'][0]['model']['value'] = value
            with self.subTest(value=str(value)), self.assertRaises(ValueError): analyze_protein_variants(r)
        for field,value in [('direction','up'),('units','')]:
            r = copy.deepcopy(self.record)
            r['proteins'][0]['model'][field] = value
            with self.assertRaises(ValueError): analyze_protein_variants(r)
        self.p['variants'][0]['model']['units'] = 'wrong'
        with self.assertRaises(ValueError): analyze_protein_variants(self.record)

    def test_failed_control_blocks_candidates(self):
        self.p['controls'][0]['status'] = 'failed'
        p = analyze_protein_variants(self.record)['proteins'][0]
        self.assertEqual(p['candidate_status'], 'blocked-controls')
        self.assertEqual(p['total'], 5)

    def test_direction_changes_signed_correlation(self):
        self.p['model']['direction'] = 'higher'
        p = analyze_protein_variants(self.record)['proteins'][0]
        self.assertAlmostEqual(p['model_vs_assay_spearman']['value'], -1)
        self.assertEqual(p['variants'][3]['model_rank'], 1)

    def test_multiple_proteins_separate_scales(self):
        q = copy.deepcopy(self.p)
        q.update(id='toy-B', reference='ACDEFA', homology_group='toy-family-B')
        q['assay']['units'] = 'other-scale'
        for variant in q['variants']:
            variant['assay']['units'] = 'other-scale'
            variant['assay']['value'] *= 100
        self.record['proteins'].append(q)
        result = analyze_protein_variants(self.record)
        self.assertEqual(len(result['proteins']), 2)
        self.assertIsNone(result['pooled_metric'])
        self.assertEqual(result['proteins'][0]['model_vs_assay_spearman'],
                         result['proteins'][1]['model_vs_assay_spearman'])

    def test_required_control_and_status_value_consistency(self):
        for change in ('no-essential', 'missing-has-value', 'ok-null', 'invalid-control'):
            r = copy.deepcopy(self.record)
            p = r['proteins'][0]
            if change == 'no-essential': p['controls'][0]['essential'] = False
            elif change == 'missing-has-value': p['variants'][0]['model']['status'] = 'missing'
            elif change == 'ok-null': p['variants'][0]['model']['value'] = None
            else: p['controls'][0]['status'] = 'unknown'
            with self.subTest(change=change), self.assertRaises(ValueError):
                analyze_protein_variants(r)

    def test_cli_foreign_cwd_without_pythonpath_and_runtime_wrapper(self):
        env = os.environ.copy()
        env.pop('PYTHONPATH', None)
        env['CODEX_SCIENCE_PYTHON'] = sys.executable
        script = str(ROOT / 'scripts/analyze_protein_variants.py')
        fixture = str(ROOT / 'examples/protein-variant-evaluation/input.json')
        commands = [[sys.executable, script, fixture],
                    ['bash', str(ROOT / 'scripts/python_runtime.sh'), script, fixture]]
        with tempfile.TemporaryDirectory() as cwd:
            for command in commands:
                proc = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(proc.stderr, '')
                self.assertEqual(json.loads(proc.stdout)['execution'], 'offline-supplied-score-analysis')

    def test_cli_rejects_nonstandard_numbers_and_duplicate_keys(self):
        metadata = copy.deepcopy(self.record)
        metadata['proteins'][0]['variants'][0]['model']['uncertainty'] = float('nan')
        cases = [json.dumps(metadata), json.dumps(metadata).replace('NaN', 'Infinity'),
                 json.dumps(metadata).replace('NaN', '-Infinity'),
                 json.dumps(metadata).replace('NaN', '1e999'),
                 '{"schema":"first","schema":"protein-variant-input-v1"}']
        for payload in cases:
            with self.subTest(payload=payload[-100:]):
                proc = subprocess.run([sys.executable, str(ROOT / 'scripts/analyze_protein_variants.py'), '-'],
                                      input=payload, text=True, capture_output=True)
                self.assertEqual(proc.returncode, 2)
                self.assertEqual(proc.stderr, '')
                self.assertEqual(json.loads(proc.stdout)['status'], 'invalid')

    def test_cli_json_success_and_error(self):
        for record,code in [(self.record,0), ({},2)]:
            proc = subprocess.run([sys.executable, str(ROOT/'scripts/analyze_protein_variants.py'),'-'], input=json.dumps(record),text=True,capture_output=True)
            self.assertEqual(proc.returncode,code,proc.stderr)
            self.assertEqual(proc.stderr,'')
            self.assertIsInstance(json.loads(proc.stdout),dict)


if __name__ == '__main__':
    unittest.main()
