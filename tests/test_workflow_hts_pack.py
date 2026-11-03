"""Synthetic plate fixtures, hand calculations, labelled refusals and reader races."""
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
FIXTURE = ROOT / 'examples/workflow-hts-plate-qc'
CLI = ROOT / 'scripts/validate_hts_plate_qc_pack.py'
CALL_TIMEOUT = float(os.environ.get('OMS_TEST_CALL_TIMEOUT', '30'))
CASES = json.loads((FIXTURE / 'negative-cases.json').read_bytes())['cases']


class _Fixture(unittest.TestCase):
    def setUp(self):
        self.api = importlib.import_module('codex_science.hts_plate_qc_pack')
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name) / 'bundle'
        self.folder.mkdir()
        for path in FIXTURE.glob('*.json'):
            shutil.copyfile(path, self.folder / path.name)
        self.pack = self.read('pack')

    def read(self, name):
        return json.loads((self.folder / (name + '.json')).read_bytes())

    def write(self, name, value):
        raw = (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode()
        (self.folder / (name + '.json')).write_bytes(raw)
        return {'path': name + '.json', 'sha256': hashlib.sha256(raw).hexdigest()}

    def save(self, name, value, freeze=True):
        if name == 'layout' and not freeze and self.pack['frozen_layout']['path'] == 'layout.json':
            self.pack['frozen_layout'] = self.write('frozen-layout', self.read('layout'))
        identity = self.write(name, value)
        if name in self.pack['inputs']:
            self.pack['inputs'][name] = identity
        if name == 'layout' and freeze:
            self.pack['frozen_layout'] = identity
        if name == 'evidence':
            self.pack['claims'][0]['support'] = [identity]
        return identity

    def run_pack(self):
        self.write('pack', self.pack)
        return self.api.validate_hts_plate_qc_pack(self.folder / 'pack.json')

    def recompute(self):
        layout, signals = self.read('layout'), self.read('signals')
        plates, controls = self.api._inventory(signals, layout)
        self.save('reported', self.api._compute(plates, controls, layout))

    def refusal(self, code):
        with self.assertRaisesRegex(ValueError, '^' + code + ':'):
            self.run_pack()

    def seed(self, case):
        values = {name: self.read(name) for name in ('layout', 'signals', 'reported', 'evidence')}
        values['pack'] = self.pack
        for edit in case['edits']:
            target = values[edit['artifact']]
            for part in edit['path'][:-1]:
                target = target[part]
            target[edit['path'][-1]] = copy.deepcopy(edit['value'])
        changed = {edit['artifact'] for edit in case['edits']}
        for name in sorted(changed - {'pack'}):
            self.save(name, values[name], freeze=case['freeze'])
        if case['alias']:
            self.pack['study_outputs'] = self.pack['claims'][0]['support'][:]
        self.refusal(case['code'])
        result = subprocess.run([sys.executable, str(CLI), str(self.folder / 'pack.json')],
                                capture_output=True, text=True, timeout=CALL_TIMEOUT)
        self.assertEqual(2, result.returncode, result.stderr)
        self.assertTrue(json.loads(result.stderr)['finding'].startswith(case['code'] + ':'))


class HTSReferenceTests(_Fixture):
    def test_fixture_expected_and_hand_calculations(self):
        actual = self.api.validate_hts_plate_qc_pack(FIXTURE / 'pack.json')
        self.assertEqual(self.read('expected'), actual)
        self.assertEqual(actual, self.api.validate_hts_plate_qc_pack(FIXTURE / 'pack.json'))
        first, second = actual['plates']
        # Positive mean=100, sample variance=4/3; negative mean=12, variance=40/7.
        spread = math.sqrt(4 / 3) + math.sqrt(40 / 7)
        self.assertAlmostEqual(1 - 3 * spread / 88, first['z_prime'])
        self.assertAlmostEqual(88 / math.sqrt(4 / 3 + 40 / 7), first['ssmd'])
        self.assertAlmostEqual(100 / 12, first['signal_to_background'])
        self.assertAlmostEqual(1 - 3 * spread / 8, second['z_prime'])
        self.assertEqual('failed', second['status'])
        self.assertEqual(4, first['drift'])
        self.assertTrue(first['drift_flagged'])
        self.assertEqual((12, 2), (first['median'], first['mad']))
        self.assertEqual(['B3', 'C3'], [h['well_id'] for h in actual['hits']])
        for hit in actual['hits']:
            self.assertAlmostEqual(48 / (1.4826 * 2), hit['robust_z'])
        self.assertEqual(60, actual['replicates'][0]['mean_signal'])
        self.assertEqual(2, actual['replicates'][0]['agreeing_replicates'])
        self.assertEqual('unavailable', actual['review'])
        self.assertEqual('screening-signal-only', actual['evidence_level'])

    def test_public_math_degeneracy_and_integer_types(self):
        for values in ([], [1], [1, 1], [float('nan'), 2], [True, 2]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.api.control_metrics(values, [9, 11])
        for values in ([], [1, 2], [1, 1, 1], [1, 2, float('inf')]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.api.robust_scores(values)
        for value in (True, 2.0, '2', 0):
            with self.subTest(minimum=value), self.assertRaises(ValueError):
                self.api.control_metrics([1, 2], [3, 4], value)
        self.assertAlmostEqual(1 - 6 * math.sqrt(2), self.api.control_metrics([1, 3], [2, 4])['z_prime'])
        center, mad, scores = self.api.robust_scores([-1, 0, 1])
        self.assertEqual((0, 1), (center, mad))
        self.assertAlmostEqual(-1 / 1.4826, scores[0])

    def test_equal_thresholds_and_replication_limit(self):
        result = self.run_pack()
        layout = self.read('layout')
        layout.update(minimum_z_prime=result['plates'][0]['z_prime'],
                      minimum_ssmd=abs(result['plates'][0]['ssmd']),
                      maximum_drift=4, hit_threshold=result['hits'][0]['robust_z'])
        self.save('layout', layout)
        self.recompute()
        actual = self.run_pack()
        self.assertFalse(actual['plates'][0]['drift_flagged'])
        self.assertEqual(2, len(actual['hits']))
        layout['replicate_requirement'] = 3
        self.save('layout', layout)
        self.recompute()
        self.pack['claims'] = []
        self.assertEqual([], self.run_pack()['hits'])

    def test_exploratory_edge_flag_and_lower_direction(self):
        layout = self.read('layout')
        layout['edge_rule'] = 'flag'
        layout['replicate_requirement'] = 1
        self.save('layout', layout, freeze=False)
        self.pack['exploratory'] = True
        self.pack['claims'][0]['status'] = 'suggestive'
        self.recompute()
        self.assertTrue(any(h['edge'] for h in self.run_pack()['hits']))
        layout['direction'] = 'lower'
        self.save('layout', layout)
        self.pack['claims'] = []
        self.recompute()
        self.assertEqual([], self.run_pack()['hits'])
        signals = self.read('signals')
        controls = set(layout['positive_controls'] + layout['negative_controls'] + layout['solvent_controls'])
        for plate in signals['plates']:
            for well in plate['wells']:
                if well['well_id'] not in controls:
                    well['value'] = -well['value']
        self.save('signals', signals)
        self.recompute()
        self.assertEqual(3, len(self.run_pack()['hits']))
        self.assertTrue(all(hit['robust_z'] < 0 for hit in self.run_pack()['hits']))

    def test_failed_degenerate_plate_preserved(self):
        signals = self.read('signals')
        for well in signals['plates'][0]['wells']:
            if well['well_id'] in self.read('layout')['positive_controls']:
                well['value'] = 100
        self.save('signals', signals)
        self.recompute()
        self.pack['claims'] = []
        result = self.run_pack()
        self.assertEqual('failed', result['plates'][0]['status'])
        self.assertIsNone(result['plates'][0]['z_prime'])
        self.assertEqual([], result['hits'])

    def test_plate_without_sample_wells_fails_alone(self):
        layout = self.read('layout')
        names = layout['positive_controls'] + layout['negative_controls'] + layout['solvent_controls']
        wells = {well: {'value': (100 + 10 * (index % 2)) if well in layout['positive_controls'] else 1 + index % 2,
                        'sample_id': 'control', 'replicate_id': 'r1', 'well_id': well}
                 for index, well in enumerate(names)}
        result = self.api._compute([('P1', wells)], set(names), layout)
        self.assertEqual(['insufficient-samples'], result['plates'][0]['reasons'])
        self.assertEqual('failed', result['plates'][0]['status'])
        self.assertEqual([], result['hits'])

    def test_zero_background_zero_mad_and_sample_minimum(self):
        for positive, negative, code in (([1, 2], [1, 2], 'undefined-zprime'),
                                         ([1, 2], [-1, 1], 'zero-background')):
            with self.subTest(code=code), self.assertRaisesRegex(ValueError, '^' + code + ':'):
                self.api.control_metrics(positive, negative)
        layout = self.read('layout')
        layout['minimum_samples'] = 23
        self.save('layout', layout)
        self.recompute()
        self.pack['claims'] = []
        self.assertIn('insufficient-samples', self.run_pack()['plates'][0]['reasons'])
        layout['minimum_samples'] = 22
        self.save('layout', layout)
        self.recompute()
        self.assertEqual('passed', self.run_pack()['plates'][0]['status'])
        signals = self.read('signals')
        controls = set(layout['positive_controls'] + layout['negative_controls'] + layout['solvent_controls'])
        for well in signals['plates'][0]['wells']:
            if well['well_id'] not in controls:
                well['value'] = 12
        self.save('signals', signals)
        self.recompute()
        result = self.run_pack()
        self.assertIn('undefined-robust-z', result['plates'][0]['reasons'])
        self.assertEqual([], result['hits'])
        self.save('signals', json.loads((FIXTURE / 'signals.json').read_bytes()))
        layout['minimum_ssmd'] = 34
        self.save('layout', layout)
        self.recompute()
        self.assertIn('minimum-ssmd', self.run_pack()['plates'][0]['reasons'])

    def test_cli_success_refusal_help_and_no_writes(self):
        before = {p.name: p.read_bytes() for p in self.folder.iterdir()}
        for args, expected in (([str(self.folder / 'pack.json')], 0),
                               ([str(self.folder / 'missing.json')], 2), ([], 2),
                               ([str(self.folder / 'pack.json'), 'extra'], 2), (['--help'], 0)):
            result = subprocess.run([sys.executable, str(CLI), *args], capture_output=True,
                                    text=True, timeout=CALL_TIMEOUT)
            self.assertEqual(expected, result.returncode, result.stderr)
            self.assertNotIn('Traceback', result.stderr)
            if args != ['--help']:
                json.loads(result.stdout if expected == 0 else result.stderr)
            else:
                self.assertIn('bundle', result.stdout)
                self.assertNotIn('--output', result.stdout)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.folder.iterdir()})


class HTSSeededTests(_Fixture):
    pass


def _seed_test(case):
    def test(self):
        self.seed(case)
    return test


for _case in CASES:
    setattr(HTSSeededTests, 'test_seed_' + _case['id'].replace('-', '_'), _seed_test(_case))


class HTSHardeningTests(_Fixture):
    def test_json_parser_refuses_malformed_duplicates_nonobjects_and_huge(self):
        for raw in (b'{', b'[]', b'{"a":1,"a":2}', b'{"a":{"b":1,"b":2}}',
                    b'{"a":NaN}', b'{"a":Infinity}', b'{"a":1e999}',
                    b'{"a":' + b'1' * 200 + b'}', b'\xff',
                    b'{"a":' + b'[' * 1100 + b'0' + b']' * 1100 + b'}'):
            with self.subTest(raw=raw[:30]), self.assertRaises(ValueError):
                self.api._json(raw)

    def test_path_types_aliases_and_nonregular_files(self):
        original = copy.deepcopy(self.pack)
        for value in ('../layout.json', '/layout.json', 'a\\b', './layout.json', 'a//b', [], ''):
            self.pack = copy.deepcopy(original)
            self.pack['inputs']['layout']['path'] = value
            with self.subTest(path=value), self.assertRaises(ValueError):
                self.run_pack()
        self.pack = original
        path = self.folder / 'layout.json'
        path.unlink()
        path.symlink_to('signals.json')
        self.refusal('input-file')
        path.unlink()
        path.mkdir()
        self.refusal('input-file')
        path.rmdir()
        os.mkfifo(path)
        # The public CLI is bounded too: opening a FIFO must never block.
        self.write('pack', self.pack)
        result = subprocess.run([sys.executable, str(CLI), str(self.folder / 'pack.json')],
                                capture_output=True, text=True, timeout=CALL_TIMEOUT)
        self.assertEqual(2, result.returncode)
        self.assertIn('input-file:', result.stderr)

    def test_bounds_before_parse_and_hardlink_cache(self):
        raw = b'{"x":[[],[]]}'
        for allowance in (0, 1):
            with self.subTest(allowance=allowance), self.assertRaisesRegex(ValueError, '^input-limit:'):
                self.api._json_nodes(raw, allowance)
        count = self.api._json_nodes(raw, 100)
        self.assertEqual(count, self.api._json_nodes(raw, count))
        with patch.object(self.api, 'MAX_TOTAL_NODES', 0):
            self.refusal('input-limit')
        for name in ('MAX_BYTES', 'MAX_TOTAL_BYTES', 'MAX_RECORDS', 'MAX_TEXT', 'MAX_DEPTH', 'MAX_ITEMS'):
            with self.subTest(limit=name), patch.object(self.api, name, 0), self.assertRaises(ValueError):
                self.run_pack()
        for name in ('MAX_PLATES', 'MAX_WELLS', 'MAX_ROWS', 'MAX_CLAIMS'):
            with self.subTest(limit=name), patch.object(self.api, name, 0), self.assertRaises(ValueError):
                self.run_pack()
        alias = self.folder / 'alias.json'
        os.link(self.folder / 'layout.json', alias)
        with self.api._Bundle(self.folder / 'pack.json') as bundle:
            first, digest = bundle.snapshot(self.api._relative('layout.json'))
            size, nodes = bundle.bytes_read, bundle.nodes_read
            second, _ = bundle.snapshot(self.api._relative('alias.json'))
            self.assertIs(first, second)
            self.assertEqual((size, nodes), (bundle.bytes_read, bundle.nodes_read))
            bundle.recheck()
        layout = self.read('layout')
        with patch.object(self.api, 'MAX_TOTAL_BYTES', size), self.api._Bundle(self.folder / 'pack.json') as bundle:
            bundle.snapshot(self.api._relative('layout.json'))
            with self.assertRaisesRegex(ValueError, '^input-limit:'):
                bundle.snapshot(self.api._relative('signals.json'))
        with patch.object(self.api, 'MAX_BYTES', size - 1):
            self.refusal('input-file')
        # Deterministic oversize dimension checked before indexing wells.
        signals = self.read('signals')
        signals['plates'] *= self.api.MAX_PLATES + 1
        self.save('signals', signals)
        self.refusal('input-limit')

    def test_count_limit_edges_and_wrong_types(self):
        layout, signals = self.read('layout'), self.read('signals')
        for name, value in (('MAX_PLATES', 2), ('MAX_WELLS', 36), ('MAX_ROWS', 72),
                            ('MAX_CLAIMS', 1), ('MAX_RECORDS', 5)):
            with self.subTest(equal_limit=name), patch.object(self.api, name, value):
                self.assertEqual(2, len(self.run_pack()['hits']))
        for field in ('plates',):
            for value in ([], {}, 0, None):
                changed = copy.deepcopy(signals)
                changed[field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    self.api._inventory(changed, layout)
        for value in ([], {}, 0, None):
            changed = copy.deepcopy(signals)
            changed['plates'][0]['wells'] = value
            with self.subTest(wells=value), self.assertRaises(ValueError):
                self.api._inventory(changed, layout)
        for field in ('positive_controls', 'negative_controls', 'solvent_controls'):
            for value in ([], {}, 0, None):
                changed = copy.deepcopy(layout)
                changed[field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    self.api._layout(changed)

    def test_declared_integers_and_unhashable_claim_fields(self):
        for key in ('rows', 'columns', 'replicate_requirement', 'minimum_controls', 'minimum_samples'):
            for value in (True, 2.0, '2', 0):
                with self.subTest(key=key, value=value):
                    layout = json.loads((FIXTURE / 'layout.json').read_bytes())
                    layout[key] = value
                    self.save('layout', layout)
                    self.refusal('invalid-record')
        self.save('layout', json.loads((FIXTURE / 'layout.json').read_bytes()))
        signals = self.read('signals')
        signals['plates'][0]['wells'][8]['replicate_id'] = 1.0
        self.save('signals', signals)
        self.refusal('invalid-record')
        self.save('signals', json.loads((FIXTURE / 'signals.json').read_bytes()))
        base_pack = copy.deepcopy(self.pack)
        for key in ('id', 'status', 'kind', 'sample_id'):
            self.pack = copy.deepcopy(base_pack)
            self.pack['claims'][0][key] = []
            with self.subTest(key=key):
                self.refusal('invalid-record')

    def test_replaced_and_growing_artifact_refused(self):
        original = self.api._Bundle.recheck
        def replaced(bundle):
            current = self.folder / 'signals.json'
            raw = current.read_bytes()
            current.unlink()
            current.write_bytes(raw)
            return original(bundle)
        with patch.object(self.api._Bundle, 'recheck', replaced):
            self.refusal('input-changed')
        self.pack = json.loads((FIXTURE / 'pack.json').read_bytes())
        real_fstat = self.api.os.fstat
        state = {'reads': 0}
        def grow(fd):
            info = real_fstat(fd)
            if info.st_ino == os.stat(self.folder / 'pack.json').st_ino:
                state['reads'] += 1
                if state['reads'] == 2:
                    with (self.folder / 'pack.json').open('ab') as handle:
                        handle.write(b' ')
                    info = real_fstat(fd)
            return info
        with patch.object(self.api.os, 'fstat', grow):
            self.refusal('input-file')

    def test_transient_ancestor_and_root_swaps_refused(self):
        real_open = self.api.os.open
        for target in (self.folder.parent, self.folder):
            moved = target.with_name(target.name + '-held')
            triggered = []
            def swapped(path, flags, *args, **kwargs):
                if not triggered and path == target.name and kwargs.get('dir_fd') is not None:
                    triggered.append(True)
                    target.rename(moved)
                    target.symlink_to(moved, target_is_directory=True)
                    try:
                        return real_open(path, flags, *args, **kwargs)
                    finally:
                        target.unlink()
                        moved.rename(target)
                return real_open(path, flags, *args, **kwargs)
            with self.subTest(target=target.name), patch.object(self.api.os, 'open', swapped):
                self.refusal('input-file')
            self.assertTrue(triggered)

    def test_root_replaced_at_final_recheck(self):
        original = self.api._Bundle.recheck
        moved = self.folder.with_name('old-bundle')
        def replaced(bundle):
            self.folder.rename(moved)
            self.folder.mkdir()
            return original(bundle)
        with patch.object(self.api._Bundle, 'recheck', replaced):
            self.refusal('input-changed')

    def test_ancestor_replaced_with_same_bundle_inode(self):
        original = self.api._Bundle.recheck
        parent = self.folder.parent
        moved = parent.with_name(parent.name + '-old')
        def replaced(bundle):
            parent.rename(moved)
            parent.mkdir()
            (moved / self.folder.name).rename(self.folder)
            return original(bundle)
        try:
            with patch.object(self.api._Bundle, 'recheck', replaced):
                self.refusal('input-changed')
        finally:
            self.folder.rename(moved / self.folder.name)
            parent.rmdir()
            moved.rename(parent)

    def test_claim_families_unavailable_mixed_and_independence(self):
        for family in self.api.WORDING_FAMILIES:
            self.pack = json.loads((FIXTURE / 'pack.json').read_bytes())
            self.pack['claims'][0]['text'] = family + 'ing screening signal'
            with self.subTest(family=family):
                self.refusal('claim-boundary')
        self.pack = json.loads((FIXTURE / 'pack.json').read_bytes())
        extra = self.read('evidence')
        extra['result'] = 'unavailable'
        identity = self.write('missing-evidence', extra)
        self.pack['claims'][0]['support'].append(identity)
        for status in ('supported', 'unsupported', 'planned', 'conflicting', 'withdrawn', 'suggestive', 'replicated'):
            self.pack['claims'][0]['status'] = status
            with self.subTest(status=status):
                self.refusal('unavailable-evidence')
        self.pack['claims'][0]['status'] = 'unavailable'
        self.assertEqual('unavailable', self.run_pack()['claims'][0]['status'])
        self.pack['claims'][0]['support'] = []
        self.assertEqual('unavailable', self.run_pack()['claims'][0]['status'])


if __name__ == '__main__':
    unittest.main()
