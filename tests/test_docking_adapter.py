import copy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from codex_science.compute_backends import JobSpec, LocalBackend, build_approval_receipt
from codex_science.docking_adapter import parse_vina_output, prepare_cpu_docking, submit_cpu_docking

ROOT = Path(__file__).resolve().parents[1]
ATOM = 'ATOM      1  C   UNK A   1       0.000   0.000   0.000  1.00  0.00     0.000 C\n'
POSE = 'MODEL 1\nREMARK VINA RESULT: -5.25 0.0 0.0\n' + ATOM + 'ENDMDL\n'


class DockingAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('receptor.pdbqt', 'ligand.pdbqt'):
            (self.root / name).write_text(ATOM)
        self.record = {'schema': 'cpu-docking-v1', 'executable': 'vina-not-installed-test-fixture',
                       'receptor': {'path': 'receptor.pdbqt', 'sha256': hashlib.sha256(ATOM.encode()).hexdigest()},
                       'ligand': {'path': 'ligand.pdbqt', 'sha256': hashlib.sha256(ATOM.encode()).hexdigest()},
                       'box': {'unit': 'angstrom', 'center': [0, 1, 2], 'size': [10, 10, 10]},
                       'seed': 123, 'exhaustiveness': 1, 'num_modes': 3, 'timeout_seconds': 30,
                       'output': 'poses.pdbqt'}

    def test_missing_engine_returns_actionable_preflight_without_launch(self):
        result = prepare_cpu_docking(self.record, self.root)
        self.assertFalse(result['ready'])
        self.assertFalse(result['engine_executed'])
        self.assertIsNone(result['executable_identity']['path'])
        self.assertTrue(result['job_spec']['approval_required'])
        self.assertFalse((self.root / '.docking-preflight').exists())
        self.assertFalse((self.root / 'poses.pdbqt').exists())

    def test_fake_executable_identity_and_exact_bounded_argv(self):
        executable = self.root / 'fake-vina'
        executable.write_text('#!/bin/sh\nexit 99\n')
        executable.chmod(0o755)
        self.record['executable'] = str(executable)
        digest = hashlib.sha256(executable.read_bytes()).hexdigest()
        self.record['executable_sha256'] = digest
        result = prepare_cpu_docking(self.record, self.root)
        self.assertTrue(result['ready'])
        self.assertEqual(result['executable_identity']['sha256'], digest)
        command = result['job_spec']['command']
        for option, value in [('--cpu', '1'), ('--seed', '123'), ('--exhaustiveness', '1'),
                              ('--scoring', 'vina'), ('--size_x', '10')]:
            self.assertEqual(command[command.index(option) + 1], value)
        self.assertEqual(result['job_spec']['resources']['gpus'], 0)
        self.assertEqual(result['job_spec']['timeout_seconds'], 30)
        executable.write_text('#!/bin/sh\nexit 0\n')
        with self.assertRaisesRegex(ValueError, 'executable identity'):
            prepare_cpu_docking(self.record, self.root)

    def _fake_preparation(self):
        # Executes only a shell fixture emitting invented scores, never docking.
        executable = self.root / 'fake-vina'
        executable.write_text("#!/bin/sh\ncat > poses.pdbqt <<'POSE'\n" + POSE + 'POSE\n')
        executable.chmod(0o755)
        self.record['executable'] = str(executable)
        preparation = prepare_cpu_docking(self.record, self.root)
        spec = JobSpec.from_payload(preparation['job_spec'])
        approval = build_approval_receipt(spec, approved_by='test-fixture', target='local fake interface test')
        return executable, preparation, approval

    def test_explicitly_approved_fake_process_executes_via_existing_backend(self):
        _, preparation, approval = self._fake_preparation()
        state_dir = self.root / 'job-state'
        submitted = submit_cpu_docking(preparation, state_dir, approval)
        backend = LocalBackend(state_dir)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            state = backend.status(submitted['job_id'])
            if state['state'] not in ('submitted', 'running'):
                break
            time.sleep(.02)
        self.assertEqual(state['state'], 'completed', state)
        self.assertEqual(state['exit_code'], 0)
        parsed = parse_vina_output((self.root / 'poses.pdbqt').read_text())
        self.assertEqual(parsed['best_score'], -5.25)
        self.assertEqual(parsed['pose_count'], 1)
        preserved = (self.root / 'poses.pdbqt').read_bytes() + b'REMARK preserved completed output\n'
        (self.root / 'poses.pdbqt').write_bytes(preserved)
        recovered = submit_cpu_docking(preparation, state_dir, approval)
        self.assertEqual(recovered['job_id'], submitted['job_id'])
        self.assertEqual(recovered['state'], 'completed')
        self.assertEqual((self.root / 'poses.pdbqt').read_bytes(), preserved)
        self.assertEqual(len(list((state_dir / 'jobs').iterdir())), 1)

    def test_concurrent_same_spec_submission_launches_exactly_one_fake_process(self):
        executable, preparation, _ = self._fake_preparation()
        executable.write_text("#!/bin/sh\nprintf 'run\\n' >> invocations.log\nsleep 0.1\ncat > poses.pdbqt <<'POSE'\n" + POSE + 'POSE\n')
        preparation = prepare_cpu_docking(self.record, self.root)
        approval = build_approval_receipt(JobSpec.from_payload(preparation['job_spec']),
                                          approved_by='test-fixture', target='local fake concurrent interface')
        state_dir = self.root / 'job-state'
        with ThreadPoolExecutor(max_workers=4) as pool:
            receipts = list(pool.map(lambda _: submit_cpu_docking(preparation, state_dir, approval), range(4)))
        self.assertEqual(len({receipt['job_id'] for receipt in receipts}), 1)
        backend = LocalBackend(state_dir)
        state = backend.wait(receipts[0]['job_id'], timeout_seconds=10, poll_seconds=.02)
        self.assertEqual(state['state'], 'completed')
        self.assertEqual((self.root / 'invocations.log').read_text().splitlines(), ['run'])
        self.assertEqual(len(list((state_dir / 'jobs').iterdir())), 1)

    def test_existing_output_and_ambiguous_job_record_prevent_fresh_submission(self):
        _, preparation, approval = self._fake_preparation()
        state_dir = self.root / 'job-state'
        (self.root / 'poses.pdbqt').write_text('other result appeared')
        with self.assertRaisesRegex(ValueError, 'output appeared'):
            submit_cpu_docking(preparation, state_dir, approval)
        self.assertEqual((self.root / 'poses.pdbqt').read_text(), 'other result appeared')
        (self.root / 'poses.pdbqt').unlink()
        broken = state_dir / 'jobs' / 'local-ambiguous'
        broken.mkdir(parents=True)
        (broken / 'spec.json').write_text('{"broken": true}')
        with self.assertRaisesRegex(ValueError, 'ambiguous backend job record'):
            submit_cpu_docking(preparation, state_dir, approval)
        self.assertFalse((self.root / 'poses.pdbqt').exists())

    def test_different_spec_cannot_overwrite_existing_job_output(self):
        _, preparation, approval = self._fake_preparation()
        self.record['seed'] = 124
        other = prepare_cpu_docking(self.record, self.root)
        other_approval = build_approval_receipt(JobSpec.from_payload(other['job_spec']),
                                                approved_by='test-fixture', target='different seed fixture')
        state_dir = self.root / 'job-state'
        receipt = submit_cpu_docking(preparation, state_dir, approval)
        LocalBackend(state_dir).wait(receipt['job_id'], timeout_seconds=10, poll_seconds=.02)
        before = (self.root / 'poses.pdbqt').read_bytes()
        with self.assertRaisesRegex(ValueError, 'output appeared'):
            submit_cpu_docking(other, state_dir, other_approval)
        self.assertEqual((self.root / 'poses.pdbqt').read_bytes(), before)
        self.assertEqual(len(list((state_dir / 'jobs').iterdir())), 1)

    def test_existing_receipt_identity_mismatch_requires_reconciliation(self):
        _, preparation, approval = self._fake_preparation()
        state_dir = self.root / 'job-state'
        receipt = submit_cpu_docking(preparation, state_dir, approval)
        state = LocalBackend(state_dir).wait(receipt['job_id'], timeout_seconds=10, poll_seconds=.02)
        state['job_spec_sha256'] = '0' * 64
        state.pop('fingerprint')
        state['fingerprint'] = hashlib.sha256(json.dumps(state, sort_keys=True, separators=(',', ':'),
                                                       ensure_ascii=False).encode()).hexdigest()
        (state_dir / 'jobs' / receipt['job_id'] / 'state.json').write_text(json.dumps(state))
        with self.assertRaisesRegex(ValueError, 'ambiguous backend job record'):
            submit_cpu_docking(preparation, state_dir, approval)

    def test_submission_denies_missing_or_other_spec_approval_and_changed_engine(self):
        executable, preparation, approval = self._fake_preparation()
        state_dir = self.root / 'job-state'
        with self.assertRaisesRegex(ValueError, 'approval'):
            submit_cpu_docking(preparation, state_dir, None)
        tampered = copy.deepcopy(preparation)
        tampered['job_spec']['command'].append('--tampered')
        with self.assertRaisesRegex(ValueError, 'spec identity'):
            submit_cpu_docking(tampered, state_dir, approval)
        wrong = copy.deepcopy(approval)
        wrong['job_spec_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            submit_cpu_docking(preparation, state_dir, wrong)
        executable.write_text('#!/bin/sh\nexit 0\n')
        with self.assertRaisesRegex(ValueError, 'bytes changed'):
            submit_cpu_docking(preparation, state_dir, approval)
        tampered = copy.deepcopy(preparation)
        tampered['executable_identity']['sha256'] = hashlib.sha256(executable.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, 'bound to the approved job spec'):
            submit_cpu_docking(tampered, state_dir, approval)
        self.assertFalse((state_dir / 'jobs').exists())

    def test_submission_rechecks_prepared_input_hash(self):
        _, preparation, approval = self._fake_preparation()
        (self.root / 'ligand.pdbqt').write_text(ATOM + 'REMARK changed input\n')
        with self.assertRaisesRegex(ValueError, 'preflight'):
            submit_cpu_docking(preparation, self.root / 'job-state', approval)

    def test_stale_inputs_and_existing_output_refused(self):
        (self.root / 'ligand.pdbqt').write_text(ATOM + 'REMARK changed\n')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            prepare_cpu_docking(self.record, self.root)
        (self.root / 'ligand.pdbqt').write_text(ATOM)
        (self.root / 'poses.pdbqt').write_text('previous attempt')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            prepare_cpu_docking(self.record, self.root)

    def test_escape_symlink_and_absent_input_refused(self):
        for path in ('../ligand.pdbqt', '/tmp/ligand.pdbqt', 'absent.pdbqt'):
            record = copy.deepcopy(self.record)
            record['ligand']['path'] = path
            with self.subTest(path=path), self.assertRaises(ValueError):
                prepare_cpu_docking(record, self.root)
        (self.root / 'alias.pdbqt').symlink_to(self.root / 'ligand.pdbqt')
        self.record['ligand']['path'] = 'alias.pdbqt'
        with self.assertRaisesRegex(ValueError, 'symlinks'):
            prepare_cpu_docking(self.record, self.root)

    def test_bad_box_and_resource_inputs_refused(self):
        for key, value in [('size', [0, 1, 1]), ('center', [0, True, 1]),
                           ('size', [1, float('inf'), 1]), ('unit', 'nm'), ('center', [1, 2])]:
            record = copy.deepcopy(self.record)
            record['box'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                prepare_cpu_docking(record, self.root)
        for key, value in [('seed', True), ('seed', 0), ('timeout_seconds', 301), ('exhaustiveness', 0)]:
            record = copy.deepcopy(self.record)
            record[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                prepare_cpu_docking(record, self.root)

    def test_score_parser_preserves_pose_scores_and_affinity_boundary(self):
        second = POSE.replace('MODEL 1', 'MODEL 2').replace('-5.25', '-4.0')
        result = parse_vina_output(POSE + second)
        self.assertEqual(result['pose_count'], 2)
        self.assertEqual(result['best_score'], -5.25)
        self.assertEqual(result['poses'][0]['atom_count'], 1)
        self.assertIn('not measured affinity', result['evidence_boundary'])

    def test_score_parser_refuses_nonfinite_incomplete_and_duplicate_models(self):
        bodies = [POSE.replace('-5.25', 'nan'), POSE.replace('0.0 0.0', '1.0 0.0'),
                  POSE.replace(ATOM, ''), POSE.replace('ENDMDL', ''), POSE + POSE,
                  'REMARK VINA RESULT: -5 0 0\n', POSE.replace('MODEL 1', 'MODEL 1.5')]
        for body in bodies:
            with self.subTest(body=body[:40]), self.assertRaises(ValueError):
                parse_vina_output(body)

    def test_foreign_cwd_cli_prepare_and_parse(self):
        source = self.root / 'input.json'
        source.write_text(json.dumps(self.record))
        output = subprocess.run([sys.executable, str(ROOT / 'scripts/prepare_cpu_docking.py'), str(source)],
                                cwd='/tmp', text=True, capture_output=True)
        self.assertEqual(output.returncode, 0, output.stderr)
        self.assertFalse(json.loads(output.stdout)['ready'])
        source.write_text(POSE)
        output = subprocess.run([sys.executable, str(ROOT / 'scripts/prepare_cpu_docking.py'), str(source), '--parse-output'],
                                cwd='/tmp', text=True, capture_output=True)
        self.assertEqual(output.returncode, 0, output.stderr)
        self.assertEqual(json.loads(output.stdout)['best_score'], -5.25)


if __name__ == '__main__':
    unittest.main()
