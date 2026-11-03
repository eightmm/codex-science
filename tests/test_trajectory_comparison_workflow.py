import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from codex_science.trajectory_comparison import analyze_trajectory_comparison

ROOT = Path(__file__).resolve().parents[1]


class TrajectoryComparisonTests(unittest.TestCase):
    def setUp(self):
        self.record = json.loads((ROOT / 'examples/trajectory-comparison/series.json').read_text())

    def test_known_difference_and_independent_uncertainty(self):
        result = analyze_trajectory_comparison(self.record)
        self.assertEqual(result['status'], 'qualified-descriptive')
        self.assertAlmostEqual(result['contrast']['mean_difference'], 2)
        self.assertAlmostEqual(result['contrast']['replica_se'], 2 ** .5 * .1)
        self.assertEqual(len(result['replicas'][0]['block_means']), 8)
        self.assertAlmostEqual(result['replicas'][0]['block_se'], 0)

    def test_nonzero_block_error(self):
        for replica in self.record['replicas']:
            replica['values'] = [value for level in [0, 2] * 4 for value in [level, level]]
        self.record['contract']['max_half_drift'] = 1
        result = analyze_trajectory_comparison(self.record)
        self.assertAlmostEqual(result['replicas'][0]['block_se'], (1 / 7) ** .5)
        self.assertAlmostEqual(result['replicas'][0]['double_block_se'], 0)
        expected = json.loads((ROOT / 'examples/trajectory-comparison/expected-result.json').read_text())
        original = json.loads((ROOT / 'examples/trajectory-comparison/series.json').read_text())
        self.assertEqual(analyze_trajectory_comparison(original), expected)

    def test_identity_and_processing_fail_closed(self):
        for key, value in [('unit', 'angstrom'), ('time_unit', 'ns'), ('topology_id', 'other'),
                           ('atom_selection', 'other'), ('observable', 'other'), ('pbc', 'unwrapped'),
                           ('model_id', 'other')]:
            with self.subTest(key=key):
                record = copy.deepcopy(self.record)
                record['replicas'][0][key] = value
                with self.assertRaises(ValueError):
                    analyze_trajectory_comparison(record)

    def test_duplicate_ancestry(self):
        for key in ('replica_id', 'independent_run_id', 'source_id'):
            record = copy.deepcopy(self.record)
            record['replicas'][1][key] = record['replicas'][0][key]
            with self.assertRaises(ValueError):
                analyze_trajectory_comparison(record)

    def test_bad_frames_pbc_and_values(self):
        for change in ('missing', 'nonmonotonic', 'pbc', 'nan', 'boolean', 'block'):
            record = copy.deepcopy(self.record)
            if change == 'missing': record['replicas'][0]['values'].pop()
            if change == 'nonmonotonic': record['contract']['times'][1] = 0
            if change == 'pbc': record['contract']['pbc'] = 'unknown'
            if change == 'nan': record['replicas'][0]['values'][0] = float('nan')
            if change == 'boolean': record['replicas'][0]['values'][0] = True
            if change == 'block': record['contract']['block_frames'] = 3
            with self.subTest(change=change), self.assertRaises(ValueError):
                analyze_trajectory_comparison(record)

    def test_drift_and_controls_change_conclusion(self):
        for change in ('drift', 'control'):
            record = copy.deepcopy(self.record)
            if change == 'drift': record['replicas'][0]['values'] = list(range(16))
            else: record['controls'][0]['passed'] = False
            result = analyze_trajectory_comparison(record)
            self.assertEqual(result['status'], 'exploratory')
            self.assertIsNone(result['contrast']['replica_se'])
            self.assertTrue(result['reasons'])

    def test_insufficient_blocks_or_replicas(self):
        record = copy.deepcopy(self.record)
        record['contract']['block_frames'] = 8
        result = analyze_trajectory_comparison(record)
        self.assertIsNone(result['replicas'][0]['block_se'])
        self.assertEqual(result['status'], 'exploratory')
        self.record['replicas'].pop()
        result = analyze_trajectory_comparison(self.record)
        self.assertIsNone(result['conditions']['changed']['replica_se'])
        self.assertIsNone(result['contrast']['replica_se'])

    def test_tiny_time_interval_and_replica_time_types(self):
        for times in ([0] * 16, [-i * 1e-12 for i in range(16)]):
            record = copy.deepcopy(self.record)
            record['contract'].update(frame_interval=1e-12, times=times)
            with self.assertRaises(ValueError):
                analyze_trajectory_comparison(record)
        self.record['replicas'][0]['times'][1] = True
        with self.assertRaises(ValueError):
            analyze_trajectory_comparison(self.record)

    def test_odd_base_blocks_never_drop_trailing_frames(self):
        record = copy.deepcopy(self.record)
        record['contract']['times'] = list(range(18))
        for replica in record['replicas']:
            replica['times'] = list(range(18))
            replica['values'] = [0] * 16 + [1, 1]
        result = analyze_trajectory_comparison(record)
        self.assertEqual(len(result['replicas'][0]['block_means']), 9)
        self.assertEqual(result['replicas'][0]['frame_count'], 18)
        self.assertIsNone(result['replicas'][0]['double_block_se'])
        self.assertGreater(result['replicas'][0]['block_se'], 0)

    def test_overflow_and_nonfinite_metadata_refuse(self):
        for change in ('huge', 'derived', 'metadata', 'duplicate-control'):
            record = copy.deepcopy(self.record)
            if change == 'huge': record['replicas'][0]['values'][0] = 10 ** 400
            if change == 'derived':
                for replica in record['replicas']:
                    replica['values'] = [(-1 if replica['condition'] == 'baseline' else 1) * 1e308] * 16
            if change == 'metadata': record['extra'] = {'uncertainty': float('nan')}
            if change == 'duplicate-control': record['controls'].append(copy.deepcopy(record['controls'][0]))
            with self.subTest(change=change), self.assertRaises(ValueError):
                analyze_trajectory_comparison(record)

    def test_cli_bad_numeric_and_duplicate_keys_json_refusal(self):
        huge = copy.deepcopy(self.record)
        huge['replicas'][0]['values'][0] = 10 ** 400
        derived = copy.deepcopy(self.record)
        for replica in derived['replicas']:
            replica['values'] = [(-1 if replica['condition'] == 'baseline' else 1) * 1e308] * 16
        bodies = [json.dumps(huge), json.dumps(derived),
                  json.dumps(self.record)[:-1] + ',"extra":NaN}',
                  json.dumps(self.record)[:-1] + ',"extra":Infinity}',
                  json.dumps(self.record)[:-1] + ',"schema":"other"}']
        for body in bodies:
            with tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / 'input.json'
                path.write_text(body)
                result = subprocess.run([sys.executable, str(ROOT / 'scripts/analyze_trajectory_comparison.py'), str(path)],
                                        text=True, capture_output=True)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(result.stderr, '')
                self.assertEqual(json.loads(result.stdout)['status'], 'invalid')

    def test_cli_json_only(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/analyze_trajectory_comparison.py'),
                                 str(ROOT / 'examples/trajectory-comparison/series.json')],
                                capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout)['status'], 'qualified-descriptive')
        self.assertEqual(result.stderr, '')
        bad = subprocess.run([sys.executable, str(ROOT / 'scripts/analyze_trajectory_comparison.py')],
                             capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1)
        self.assertEqual(json.loads(bad.stdout)['status'], 'invalid')


if __name__ == '__main__':
    unittest.main()
