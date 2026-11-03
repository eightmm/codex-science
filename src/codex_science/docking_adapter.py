"""Prepare and explicitly submit bounded Vina jobs through the existing backend."""

import hashlib
import json
import math
from pathlib import Path
import re
import shutil

from codex_science.compute_backends import JobSpec, LocalBackend, TERMINAL_STATES, _job_state_lock, validate_approval_receipt


def _number(value, label):
    try:
        valid = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(label + ' must be finite numeric data')
    return value


def _integer(value, label, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f'{label} must be an integer in [{minimum}, {maximum}]')
    return value


def _path(root, value, label):
    if not isinstance(value, str) or not value or '\x00' in value:
        raise ValueError(label + ' requires a relative file path')
    relative = Path(value)
    if relative.is_absolute() or '..' in relative.parts or relative == Path('.'):
        raise ValueError(label + ' must stay inside the working directory')
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(label + ' cannot traverse symlinks')
    resolved = current.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(label + ' escapes the working directory')
    return relative, resolved


def _digest(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_cpu_docking(record, working_directory):
    """Bind exact prepared inputs to a local JobSpec; readiness is not approval."""
    if not isinstance(record, dict) or record.get('schema') != 'cpu-docking-v1':
        raise ValueError('expected cpu-docking-v1')
    root = Path(working_directory).resolve()
    if not root.is_dir():
        raise ValueError('working directory must exist')
    command = record.get('executable', 'vina')
    if not isinstance(command, str) or not command.strip() or '\x00' in command:
        raise ValueError('executable must be nonempty text')
    executable = shutil.which(command)
    expected_executable = record.get('executable_sha256')
    executable_hash = _digest(Path(executable)) if executable else None
    if expected_executable is not None and expected_executable != executable_hash:
        raise ValueError('executable identity mismatch or executable unavailable')
    inputs, paths = [], {}
    for key in ('receptor', 'ligand'):
        item = record[key]
        relative, path = _path(root, item['path'], key)
        if not path.is_file() or path.suffix.lower() != '.pdbqt':
            raise ValueError(key + ' must be an existing prepared PDBQT file')
        if not any(line.startswith(('ATOM  ', 'HETATM')) for line in path.read_text().splitlines()):
            raise ValueError(key + ' lacks PDBQT atom records')
        digest = _digest(path)
        if item.get('sha256') != digest:
            raise ValueError(key + ' hash mismatch')
        inputs.append({'id': key, 'path': relative.as_posix(), 'sha256': digest})
        paths[key] = relative.as_posix()
    if paths['receptor'] == paths['ligand']:
        raise ValueError('receptor and ligand must be distinct files')
    if executable:
        inputs.append({'id': 'vina-executable', 'identifier': 'file:' + executable,
                       'sha256': executable_hash})
    output_relative, output_path = _path(root, record['output'], 'output')
    if output_path.exists():
        raise ValueError('output already exists; use a fresh attempt directory')
    if output_path.suffix.lower() != '.pdbqt' or not output_path.parent.is_dir():
        raise ValueError('output must be a PDBQT file under an existing directory')
    box = record['box']
    if box.get('unit') != 'angstrom':
        raise ValueError('Vina box unit must be angstrom')
    center, size = box['center'], box['size']
    if not isinstance(center, list) or not isinstance(size, list) or len(center) != 3 or len(size) != 3:
        raise ValueError('box center and size each require three coordinates')
    for value in center:
        _number(value, 'box center')
    for value in size:
        if _number(value, 'box size') <= 0:
            raise ValueError('box sizes must be positive')
    seed = _integer(record['seed'], 'seed', 1, 2147483647)
    exhaustiveness = _integer(record['exhaustiveness'], 'exhaustiveness', 1, 32)
    modes = _integer(record.get('num_modes', 3), 'num_modes', 1, 20)
    timeout = _integer(record['timeout_seconds'], 'timeout_seconds', 1, 300)
    argv = [executable or command, '--receptor', paths['receptor'], '--ligand', paths['ligand'],
            '--scoring', 'vina', '--cpu', '1', '--seed', str(seed),
            '--exhaustiveness', str(exhaustiveness), '--num_modes', str(modes),
            '--out', output_relative.as_posix()]
    for index, axis in enumerate('xyz'):
        argv.extend(['--center_' + axis, str(center[index]), '--size_' + axis, str(size[index])])
    spec = JobSpec.from_payload({'schema_version': 1, 'backend': 'local', 'name': 'cpu-vina-pilot',
                                'command': argv, 'working_directory': str(root),
                                'environment': {}, 'inherit_environment': False,
                                'inputs': inputs, 'outputs': [output_relative.as_posix()],
                                'resources': {'cpus': 1, 'gpus': 0, 'wall_time_seconds': timeout},
                                'timeout_seconds': timeout, 'cost_cap': 0,
                                'approval_required': True})
    preflight = LocalBackend(root / '.docking-preflight').preflight(spec)
    return {'schema': 'cpu-docking-preparation-v1', 'ready': preflight['ready'],
            'engine_executed': False, 'executable_identity': {'path': executable, 'sha256': executable_hash},
            'job_spec': spec.to_dict(), 'job_spec_sha256': spec.fingerprint, 'preflight': preflight,
            'limitations': ['Prepared PDBQT atom-record presence is not chemical or geometric validation.',
                            'Preparation launches nothing; separate submission rechecks bytes and requires an existing exact-spec approval.',
                            'A Vina score is not measured affinity; no control or scientific acceptance is implied.']}


def submit_cpu_docking(preparation, state_dir, approval):
    """Recheck exact prepared bytes and submit only with an existing approval."""
    if not isinstance(preparation, dict) or preparation.get('schema') != 'cpu-docking-preparation-v1':
        raise ValueError('expected cpu-docking-preparation-v1')
    if preparation.get('ready') is not True or not isinstance(approval, dict):
        raise ValueError('ready preparation and explicit existing approval receipt required')
    spec = JobSpec.from_payload(preparation['job_spec'])
    if spec.fingerprint != preparation.get('job_spec_sha256'):
        raise ValueError('prepared job spec identity mismatch')
    if spec.backend != 'local' or not spec.approval_required or spec.resources.cpus != 1 or spec.resources.gpus != 0:
        raise ValueError('adapter requires approval-gated single-CPU local execution')
    if spec.timeout_seconds > 300:
        raise ValueError('adapter timeout cannot exceed 300 seconds')
    identity = preparation['executable_identity']
    executable = identity.get('path')
    if not isinstance(executable, str) or spec.command[0] != executable:
        raise ValueError('prepared executable path mismatch')
    engine_inputs = [item for item in spec.inputs if item['id'] == 'vina-executable']
    if len(engine_inputs) != 1 or engine_inputs[0].get('sha256') != identity.get('sha256') or engine_inputs[0].get('identifier') != 'file:' + executable:
        raise ValueError('executable identity must be bound to the approved job spec')
    backend = LocalBackend(Path(state_dir))
    validate_approval_receipt(approval, spec)
    backend.state_dir.mkdir(parents=True, exist_ok=True)
    # Use the existing durable lock primitive at the state-directory level to
    # serialize reconciliation and submission across adapter processes.
    with _job_state_lock(backend.state_dir):
        matches = []
        if backend.jobs_dir.exists():
            if not backend.jobs_dir.is_dir() or backend.jobs_dir.is_symlink():
                raise ValueError('ambiguous backend jobs directory; reconcile before submission')
            for directory in sorted(backend.jobs_dir.iterdir()):
                try:
                    if not directory.is_dir() or directory.is_symlink():
                        raise ValueError('unexpected job record')
                    if any((directory / name).is_symlink() for name in ('spec.json', 'state.json')):
                        raise ValueError('symlinked job identity record')
                    existing_spec = JobSpec.from_payload(json.loads((directory / 'spec.json').read_text()))
                    receipt = backend.status(directory.name)
                    if receipt['job_id'] != directory.name or receipt['job_spec_sha256'] != existing_spec.fingerprint or receipt['backend'] != 'local':
                        raise ValueError('job record identity mismatch')
                except (ValueError, KeyError, TypeError, OSError) as error:
                    raise ValueError('ambiguous backend job record; reconcile before submission') from error
                if existing_spec.fingerprint == spec.fingerprint:
                    matches.append(receipt)
                elif receipt['state'] not in TERMINAL_STATES or receipt['state'] == 'lost':
                    reserved = {(Path(existing_spec.working_directory) / item).resolve() for item in existing_spec.outputs}
                    requested = {(Path(spec.working_directory) / item).resolve() for item in spec.outputs}
                    if reserved & requested:
                        raise ValueError('output path is reserved by an unresolved different-spec job')
        if len(matches) > 1:
            raise ValueError('multiple same-spec jobs already exist; reconcile before submission')
        if matches:
            return matches[0]
        path = Path(executable)
        if not path.is_file() or _digest(path) != identity.get('sha256'):
            raise ValueError('prepared executable bytes changed')
        root = Path(spec.working_directory)
        for relative in spec.outputs:
            _, output = _path(root, relative, 'output')
            if output.exists():
                raise ValueError('output appeared after preparation; use a fresh attempt directory')
        preflight = backend.preflight(spec)
        if not preflight['ready']:
            raise ValueError('prepared input or executable no longer passes preflight')
        return backend.submit(spec, approval=approval)


def parse_vina_output(text):
    """Parse one score and atom-bearing pose per explicit Vina MODEL record."""
    if not isinstance(text, str):
        raise ValueError('Vina output must be text')
    poses, current, seen = [], None, set()
    for line in text.splitlines():
        if line.startswith('MODEL'):
            if current is not None or not re.fullmatch(r'MODEL\s+[1-9][0-9]*\s*', line):
                raise ValueError('malformed or nested MODEL')
            identity = int(line.split()[1])
            if identity in seen:
                raise ValueError('duplicate pose model ID')
            seen.add(identity)
            current = {'model': identity, 'atom_count': 0}
        elif line.startswith('REMARK VINA RESULT:'):
            if current is None or 'score' in current:
                raise ValueError('score outside MODEL or duplicate score')
            fields = line.split(':', 1)[1].split()
            if len(fields) != 3:
                raise ValueError('Vina result requires score and two RMSD bounds')
            score, lower, upper = (_number(float(item), 'Vina result') for item in fields)
            if lower < 0 or upper < lower:
                raise ValueError('invalid Vina RMSD bounds')
            current.update(score=score, rmsd_lower=lower, rmsd_upper=upper)
        elif line.startswith(('ATOM  ', 'HETATM')):
            if current is None:
                raise ValueError('pose atoms outside MODEL')
            current['atom_count'] += 1
        elif line.strip() == 'ENDMDL':
            if current is None or current['atom_count'] == 0 or 'score' not in current:
                raise ValueError('incomplete Vina pose')
            poses.append(current)
            current = None
    if current is not None or not poses:
        raise ValueError('unfinished or absent Vina poses')
    return {'schema': 'cpu-docking-poses-v1', 'poses': poses, 'pose_count': len(poses),
            'best_score': min(pose['score'] for pose in poses), 'score_direction': 'lower-is-favorable',
            'score_unit': 'kcal/mol', 'evidence_boundary': 'Vina scoring diagnostics only, not measured affinity or binding.'}
