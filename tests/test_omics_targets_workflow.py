import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from codex_science.omics_targets import analyze_omics_targets

ROOT = Path(__file__).resolve().parents[1]


class OmicsTargetsWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.record = json.loads((ROOT / 'examples/omics-target-prioritization/input.json').read_text())

    def test_donor_contrasts_missingness_and_dependency_grouping(self):
        result = analyze_omics_targets(self.record)
        self.assertEqual(result['sample_count'], 9)
        self.assertEqual(result['donor_count'], 8)
        self.assertEqual(result['prioritized_gene_ids'], ['ENSG-toy-up'])
        up, flat, missing = result['targets']
        self.assertAlmostEqual(up['equal_cohort_mean_difference'], 2)
        self.assertEqual(up['cohorts'][0]['reference_donors'], 2)
        self.assertAlmostEqual(up['cohorts'][0]['standard_error'], 0.14142135623730956)
        self.assertEqual(len(up['dependency_groups']), 1)
        self.assertEqual(len(up['dependency_groups'][0]['record_ids']), 2)
        self.assertEqual(flat['equal_cohort_mean_difference'], 0)
        self.assertTrue(flat['evidence_unavailable'])
        self.assertIsNone(missing['equal_cohort_mean_difference'])
        self.assertIsNone(result['p_values'])
        self.assertFalse(result['causal_target_claim'])

    def test_technical_replicates_do_not_inflate_biological_n_or_weight(self):
        before = analyze_omics_targets(self.record)['targets'][0]['cohorts']
        for index in range(20):
            row = copy.deepcopy(self.record['samples'][0])
            row['sample_id'] = f'extra-technical-{index}'
            self.record['samples'].append(row)
        after = analyze_omics_targets(self.record)['targets'][0]['cohorts']
        self.assertEqual(before, after)

    def test_batch_and_cohort_confounding(self):
        for mode in ('batch', 'cohort'):
            record = copy.deepcopy(self.record)
            for sample in record['samples']:
                sample[mode if mode == 'batch' else 'cohort_id'] = sample['condition']
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                analyze_omics_targets(record)

    def test_partial_case_only_batch_retains_artifact_effect_but_blocks_priority(self):
        record = json.loads((ROOT / 'examples/omics-target-prioritization/batch-imbalance.json').read_text())
        result = analyze_omics_targets(record)
        self.assertEqual(result['prioritized_gene_ids'], [])
        up = result['targets'][0]
        self.assertAlmostEqual(up['cohorts'][0]['difference'], 52)
        self.assertIn('unresolved-unadjusted-batch-imbalance', up['exclusion_reasons'])
        diagnostic = result['batch_diagnostics'][0]
        self.assertTrue(diagnostic['unresolved_unadjusted_imbalance'])
        batches = {b['batch_id']: b for b in diagnostic['batches']}
        self.assertEqual(batches['balanced-batch']['condition_donor_counts'], {'reference': 2, 'case': 1})
        self.assertEqual(batches['case-only-artifact']['condition_donor_counts'], {'reference': 0, 'case': 1})

    def test_unequal_donor_proportions_across_mixed_batches_block_priority(self):
        cohort_a = [s for s in self.record['samples'] if s['cohort_id'] == 'cohort-A']
        for sample in cohort_a:
            if sample['sample_id'] in ('cohort-A-reference-1', 'cohort-A-case-1'):
                sample['batch'] = 'second-mixed-batch'
        extra = copy.deepcopy(cohort_a[0])
        extra.update(sample_id='new-reference-sample', donor_id='new-reference-donor')
        self.record['samples'].append(extra)
        result = analyze_omics_targets(self.record)
        diagnostic = result['batch_diagnostics'][0]
        self.assertTrue(diagnostic['unresolved_unadjusted_imbalance'])
        self.assertTrue(all(not batch['single_condition'] for batch in diagnostic['batches']))
        self.assertEqual(result['prioritized_gene_ids'], [])

    def test_gene_missingness_induces_batch_imbalance_even_when_design_is_balanced(self):
        for sample in self.record['samples']:
            if sample['cohort_id'] == 'cohort-A' and sample['sample_id'] in ('cohort-A-reference-1', 'cohort-A-case-1'):
                sample['batch'] = 'second-mixed-batch'
        sample = next(s for s in self.record['samples'] if s['sample_id'] == 'cohort-A-case-1')
        sample['expression']['ENSG-toy-up'] = None
        result = analyze_omics_targets(self.record)
        self.assertFalse(result['batch_diagnostics'][0]['unresolved_unadjusted_imbalance'])
        self.assertTrue(result['targets'][0]['cohorts'][0]['batch_design']['unresolved_unadjusted_imbalance'])
        self.assertIn('unresolved-unadjusted-batch-imbalance', result['targets'][0]['exclusion_reasons'])

    def test_donor_overlap_and_unpaired_repeated_condition(self):
        for mode in ('cohort', 'condition'):
            record = copy.deepcopy(self.record)
            index = 4 if mode == 'cohort' else 2
            record['samples'][index]['donor_id'] = record['samples'][0]['donor_id']
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                analyze_omics_targets(record)

    def test_paired_contrast_and_incomplete_pairs(self):
        self.record['paired'] = True
        for sample in self.record['samples']:
            sample['donor_id'] = sample['donor_id'].replace('-reference-', '-').replace('-case-', '-')
        result = analyze_omics_targets(self.record)
        self.assertEqual(result['donor_count'], 4)
        self.assertEqual(result['targets'][0]['cohorts'][0]['standard_error'], 0)
        self.record['samples'] = [s for s in self.record['samples'] if s['sample_id'] != 'cohort-A-case-0']
        with self.assertRaises(ValueError):
            analyze_omics_targets(self.record)

    def test_failed_controls_and_contradictions_change_prioritization(self):
        self.record['controls'][0]['status'] = 'unavailable'
        result = analyze_omics_targets(self.record)
        self.assertEqual(result['prioritized_gene_ids'], [])
        self.assertEqual(result['gene_count'], 3)
        self.record['controls'][0]['status'] = 'passed'
        self.record['evidence'][1]['direction'] = 'contradicts'
        result = analyze_omics_targets(self.record)
        self.assertEqual(result['prioritized_gene_ids'], [])
        self.assertIn('contradictory-external-evidence', result['targets'][0]['exclusion_reasons'])

    def test_discordant_cohorts_retained_and_blocked(self):
        for sample in self.record['samples']:
            if sample['cohort_id'] == 'cohort-B' and sample['condition'] == 'case':
                sample['expression']['ENSG-toy-up'] -= 4
        result = analyze_omics_targets(self.record)
        self.assertEqual(result['prioritized_gene_ids'], [])
        self.assertIn('discordant-cohort-directions', result['targets'][0]['exclusion_reasons'])

    def test_units_identity_numeric_and_missing_field_rejected(self):
        for mode in ('units', 'sample', 'gene', 'numeric', 'missing'):
            record = copy.deepcopy(self.record)
            if mode == 'units':
                record['expression_unit'] = 'counts'
            elif mode == 'sample':
                record['samples'][1]['sample_id'] = record['samples'][0]['sample_id']
            elif mode == 'gene':
                record['gene_ids'].append('ENSG-toy-up')
            elif mode == 'numeric':
                record['samples'][0]['expression']['ENSG-toy-up'] = True
            else:
                del record['samples'][0]['expression']['ENSG-toy-up']
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                analyze_omics_targets(record)

    def test_insufficient_donors_not_rescued_by_many_technical_samples(self):
        self.record['minimum_donors'] = 3
        result = analyze_omics_targets(self.record)
        self.assertEqual(result['prioritized_gene_ids'], [])
        self.assertIn('insufficient-donors-or-missingness', result['targets'][0]['exclusion_reasons'])

    def test_external_evidence_overlap_is_visible(self):
        self.record['evidence'][0]['cohort_ids'] = ['cohort-A']
        result = analyze_omics_targets(self.record)
        self.assertTrue(result['targets'][0]['dependency_groups'][0]['overlaps_expression_cohort'])

    def test_cli_foreign_cwd_and_strict_json(self):
        env = os.environ.copy()
        env.pop('PYTHONPATH', None)
        script = str(ROOT / 'scripts/analyze_omics_targets.py')
        with tempfile.TemporaryDirectory() as cwd:
            proc = subprocess.run([sys.executable, script, str(ROOT / 'examples/omics-target-prioritization/input.json')],
                                  cwd=cwd, env=env, text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)['schema'], 'omics-target-analysis-v1')
        for payload in ['{"schema":"x","schema":"y"}', json.dumps({**self.record, 'extra': float('nan')}),
                        json.dumps({**self.record, 'extra': float('inf')}).replace('Infinity', '1e999')]:
            proc = subprocess.run([sys.executable, script, '-'], input=payload, text=True, capture_output=True)
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(proc.stderr, '')
            self.assertEqual(json.loads(proc.stdout)['status'], 'invalid')

    def test_direct_api_rejects_nested_nonfinite_evidence_metadata(self):
        for value in (float('nan'), float('inf'), -float('inf')):
            record = copy.deepcopy(self.record)
            record['evidence'][0]['extra'] = {'value': value}
            with self.subTest(value=value), self.assertRaises(ValueError):
                analyze_omics_targets(record)


if __name__ == '__main__':
    unittest.main()
