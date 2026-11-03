import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from codex_science.protein_engineering import analyze_protein_engineering

ROOT = Path(__file__).resolve().parents[1]


class ProteinEngineeringWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.record = json.loads((ROOT / 'examples/protein-engineering-cycle/input.json').read_text())

    def test_feedback_retains_negative_failed_and_replicate_uncertainty(self):
        result = analyze_protein_engineering(self.record)
        self.assertTrue(result['synthetic'])
        self.assertEqual(result['measurement_summaries']['parent']['failed'], 1)
        self.assertAlmostEqual(result['measurement_summaries']['parent']['mean'], 1.1)
        self.assertAlmostEqual(result['measurement_summaries']['parent']['standard_error'], 0.1)
        self.assertAlmostEqual(result['measurement_summaries']['eval-low']['mean'], -0.1)
        self.assertEqual(result['evaluation_only_spearman']['value'], 1)
        self.assertEqual([r['id'] for r in result['next_library']['selected']], ['next-a', 'next-c'])
        self.assertFalse(result['next_library']['executed'])

    def test_feedback_changes_next_library_without_using_evaluation_labels(self):
        for row in self.record['measurements']:
            if row['variant_id'] == 'WT':
                row['value'] += 3
        result = analyze_protein_engineering(self.record)
        self.assertEqual(result['next_library']['selected'][0]['id'], 'next-b')
        selected = copy.deepcopy(result['next_library'])
        for row in self.record['measurements']:
            if row['variant_id'].startswith('eval-'):
                row['value'] *= -100
        changed = analyze_protein_engineering(self.record)
        self.assertEqual(changed['next_library'], selected)
        self.assertEqual(changed['evaluation_only_spearman']['value'], -1)

    def test_evaluation_leakage_and_unknown_training_identity(self):
        for change in ('training', 'parent', 'unknown'):
            record = copy.deepcopy(self.record)
            if change == 'training':
                record['model_training_variant_ids'].append('eval-low')
            elif change == 'parent':
                record['candidate_parents']['next-b'] = 'eval-low'
            else:
                record['model_training_variant_ids'].append('unknown')
            with self.subTest(change=change), self.assertRaises(ValueError):
                analyze_protein_engineering(record)

    def test_measurement_identity_units_duplicate_and_status(self):
        for field, value in [('construct_id', 'other'), ('assay_id', 'other'), ('units', 'nM'),
                             ('variant_id', 'next-a'), ('status', 'missing'), ('value', float('nan'))]:
            record = copy.deepcopy(self.record)
            record['measurements'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                analyze_protein_engineering(record)
        self.record['measurements'].append(copy.deepcopy(self.record['measurements'][0]))
        with self.assertRaises(ValueError):
            analyze_protein_engineering(self.record)

    def test_failed_controls_block_every_candidate(self):
        self.record['variant_input']['proteins'][0]['controls'][0]['status'] = 'failed'
        result = analyze_protein_engineering(self.record)
        self.assertIsNone(result['next_library'])
        self.assertEqual(len(result['excluded_candidates']), 3)
        self.assertEqual(len(result['measurements']), 9)

    def test_missing_parent_replicates_and_score_preserve_exclusions(self):
        self.record['measurements'] = [r for r in self.record['measurements']
                                       if not (r['variant_id'] == 'parent' and r['independent_replicate_id'] == 'culture-1')]
        result = analyze_protein_engineering(self.record)
        self.assertEqual([r['id'] for r in result['next_library']['selected']], ['next-b'])
        self.assertEqual(len(result['excluded_candidates']), 2)
        variant = self.record['variant_input']['proteins'][0]['variants'][5]
        variant['model'] = {'status': 'failed', 'value': None, 'units': 'toy-score', 'reason': 'not run'}
        result = analyze_protein_engineering(self.record)
        self.assertIsNone(result['next_library'])

    def test_wt_parent_distance_and_authoritative_raw_assay(self):
        for change in ('wt', 'distance', 'assay'):
            record = copy.deepcopy(self.record)
            variants = record['variant_input']['proteins'][0]['variants']
            if change == 'wt':
                variants[1]['substitutions'] = ['C1V']
            elif change == 'distance':
                record['candidate_parents']['next-b'] = 'parent'
            else:
                variants[0]['assay'].update(status='ok', value=1)
            with self.subTest(change=change), self.assertRaises(ValueError):
                analyze_protein_engineering(record)

    def test_score_direction_propagates_to_selection(self):
        self.record['variant_input']['proteins'][0]['assay']['direction'] = 'lower'
        result = analyze_protein_engineering(self.record)
        self.assertEqual(result['next_library']['selected'][0]['id'], 'next-b')

    def test_model_and_assay_scales_are_normalized_separately_not_raw_blended(self):
        first = analyze_protein_engineering(self.record)
        for variant in self.record['variant_input']['proteins'][0]['variants']:
            variant['model']['value'] = 1000 * variant['model']['value'] + 400
        for row in self.record['measurements']:
            if row['status'] == 'ok':
                row['value'] = 50 * row['value'] - 12
        second = analyze_protein_engineering(self.record)
        self.assertEqual([r['id'] for r in first['next_library']['selected']],
                         [r['id'] for r in second['next_library']['selected']])
        for left, right in zip(first['next_library']['selected'], second['next_library']['selected']):
            for objective in left['normalized_objectives']:
                self.assertAlmostEqual(left['normalized_objectives'][objective],
                                       right['normalized_objectives'][objective])
        self.assertEqual(first['evaluation_only_spearman'], second['evaluation_only_spearman'])

    def test_cli_foreign_cwd_and_nonfinite_metadata(self):
        env = os.environ.copy()
        env.pop('PYTHONPATH', None)
        script = str(ROOT / 'scripts/analyze_protein_engineering.py')
        with tempfile.TemporaryDirectory() as cwd:
            proc = subprocess.run([sys.executable, script, str(ROOT / 'examples/protein-engineering-cycle/input.json')],
                                  cwd=cwd, env=env, text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)['schema'], 'protein-engineering-analysis-v1')
        for payload in ['{"schema":"x","schema":"y"}', json.dumps({**self.record, 'extra': float('nan')}),
                        json.dumps({**self.record, 'extra': float('inf')}).replace('Infinity', '1e999')]:
            proc = subprocess.run([sys.executable, script, '-'], input=payload, text=True, capture_output=True)
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(proc.stderr, '')
            self.assertEqual(json.loads(proc.stdout)['status'], 'invalid')

    def test_direct_api_rejects_nested_nonfinite_measurement_metadata(self):
        for value in (float('nan'), float('inf'), -float('inf')):
            record = copy.deepcopy(self.record)
            record['measurements'][0]['extra'] = {'value': value}
            with self.subTest(value=value), self.assertRaises(ValueError):
                analyze_protein_engineering(record)


if __name__ == '__main__':
    unittest.main()
