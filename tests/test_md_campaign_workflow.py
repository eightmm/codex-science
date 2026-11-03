import copy
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from codex_science.md_campaign import analyze_md_campaign

ROOT = Path(__file__).resolve().parents[1]


class MDCampaignTests(unittest.TestCase):
    def setUp(self):
        self.record = json.loads((ROOT / 'examples/md-free-energy-campaign/network.json').read_text())

    def test_triangle_mean_repeat_error_and_signed_closure(self):
        result = analyze_md_campaign(self.record)
        self.assertEqual(result['status'], 'qualified-descriptive')
        self.assertFalse(result['engine_executed'])
        self.assertEqual(result['edges'][0]['mean_delta_delta_g'], 1)
        self.assertAlmostEqual(result['edges'][0]['replica_se'], .1)
        self.assertAlmostEqual(result['edges'][0]['reported_error_se'], math.sqrt(.02))
        cycle = result['fundamental_cycles'][0]
        self.assertAlmostEqual(cycle['closure_residual'], 0)
        self.assertAlmostEqual(cycle['reported_error_se'], math.sqrt(.06))
        self.assertEqual([item['sign'] for item in cycle['edges']], [1, -1, -1])

    def test_reversing_orientation_and_values_preserves_closure(self):
        edge = self.record['edges'][1]
        edge['ligand_a'], edge['ligand_b'] = edge['ligand_b'], edge['ligand_a']
        for replica in edge['replicas']:
            replica['delta_delta_g'] *= -1
        cycle = analyze_md_campaign(self.record)['fundamental_cycles'][0]
        self.assertAlmostEqual(cycle['closure_residual'], 0)
        self.assertEqual([item['sign'] for item in cycle['edges']], [1, 1, -1])

    def test_cycle_failure_changes_conclusion(self):
        for replica in self.record['edges'][2]['replicas']:
            replica['delta_delta_g'] += 2
        result = analyze_md_campaign(self.record)
        self.assertEqual(result['status'], 'exploratory')
        self.assertIn('cycle-closure:A-C', result['reasons'])
        self.assertAlmostEqual(result['fundamental_cycles'][0]['closure_residual'], 2)

    def test_contract_identity_mismatch_refused(self):
        for key, value in [('unit', 'kJ/mol'), ('forcefield_id', 'other'), ('protocol_id', 'other'),
                           ('construct_id', 'other'), ('target_id', 'other'),
                           ('mapping_policy_id', 'other'), ('temperature_kelvin', 301)]:
            record = copy.deepcopy(self.record)
            record['edges'][0]['replicas'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                analyze_md_campaign(record)

    def test_duplicate_repeat_ancestry_refused(self):
        for key in ('replica_id', 'source_id', 'independent_run_id'):
            record = copy.deepcopy(self.record)
            record['edges'][1]['replicas'][0][key] = record['edges'][0]['replicas'][0][key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                analyze_md_campaign(record)

    def test_disconnected_network_refused(self):
        self.record['ligands'].append({'id': 'D', 'identity_sha256': '7' * 64})
        with self.assertRaisesRegex(ValueError, 'disconnected'):
            analyze_md_campaign(self.record)

    def test_duplicate_edge_ligand_and_mapping_fail(self):
        for change in ('reverse', 'ligand-id', 'ligand-hash', 'mapping-hash'):
            record = copy.deepcopy(self.record)
            if change == 'reverse':
                record['edges'][2].update(ligand_a='B', ligand_b='A')
            elif change == 'ligand-id':
                record['ligands'][1]['id'] = 'A'
            elif change == 'ligand-hash':
                record['ligands'][1]['identity_sha256'] = record['ligands'][0]['identity_sha256']
            else:
                record['edges'][0]['mapping_sha256'] = 'unresolved'
            with self.subTest(change=change), self.assertRaises(ValueError):
                analyze_md_campaign(record)

    def test_controls_repeats_and_dependence_qualify(self):
        for change, reason in [('control', 'failed-control:'), ('replicas', 'insufficient-replicas:'),
                               ('dependence', 'edge-dependence-unresolved')]:
            record = copy.deepcopy(self.record)
            if change == 'control': record['controls'][0]['passed'] = False
            elif change == 'replicas': record['edges'][0]['replicas'].pop()
            else: record['contract']['edge_errors_independent'] = False
            result = analyze_md_campaign(record)
            self.assertEqual(result['status'], 'exploratory')
            self.assertTrue(any(item.startswith(reason) for item in result['reasons']))
            if change == 'replicas': self.assertIsNone(result['edges'][0]['replica_se'])
            if change == 'dependence':
                self.assertIsNone(result['fundamental_cycles'][0]['reported_error_se'])
                self.assertIsNone(result['fundamental_cycles'][0]['absolute_z_diagnostic'])

    def test_tree_cycle_requirement_is_explicit(self):
        self.record['edges'].pop()
        self.assertIn('no-cycle-diagnostic', analyze_md_campaign(self.record)['reasons'])
        self.record['contract']['require_cycle'] = False
        self.assertEqual(analyze_md_campaign(self.record)['status'], 'qualified-descriptive')

    def test_invalid_numeric_and_boolean_inputs(self):
        for value in (float('nan'), float('inf'), True, 10 ** 400):
            record = copy.deepcopy(self.record)
            record['edges'][0]['replicas'][0]['delta_delta_g'] = value
            with self.subTest(value=type(value)), self.assertRaises(ValueError):
                analyze_md_campaign(record)
        for value in (0, -.1):
            self.record['edges'][0]['replicas'][0]['standard_error'] = value
            with self.assertRaises(ValueError): analyze_md_campaign(self.record)
        for field, value in [('minimum_replicas', True), ('require_cycle', 'yes'), ('max_cycle_z', 0)]:
            record = copy.deepcopy(self.record)
            record['contract'][field] = value
            with self.assertRaises(ValueError): analyze_md_campaign(record)

    def test_derived_uncertainty_underflow_refused(self):
        for edge in self.record['edges']:
            for replica in edge['replicas']:
                replica['standard_error'] = 5e-324
        with self.assertRaisesRegex(ValueError, 'finite diagnostic range'):
            analyze_md_campaign(self.record)

    def test_foreign_cwd_cli_and_bad_json(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/analyze_md_campaign.py'),
                                     str(ROOT / 'examples/md-free-energy-campaign/network.json')],
                                    cwd=directory, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['status'], 'qualified-descriptive')
            for body in ('{"schema":"one","schema":"two"}', '{"bad":NaN}'):
                source = Path(directory) / 'bad.json'
                source.write_text(body)
                result = subprocess.run([sys.executable, str(ROOT / 'scripts/analyze_md_campaign.py'), str(source)],
                                        cwd=directory, text=True, capture_output=True)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stderr, '')
                self.assertEqual(json.loads(result.stdout)['status'], 'invalid')


if __name__ == '__main__':
    unittest.main()
