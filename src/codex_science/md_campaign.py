"""Offline identity and network diagnostics for supplied free-energy results."""

from collections import deque
import hashlib
import json
import math
import statistics


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be nonempty text")
    return value


def _number(value, label):
    try:
        valid = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f"{label} must be finite numeric data")
    return value


def _sha(value, label):
    if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError(f"{label} must be a lowercase sha256")
    return value


def _tree_path(tree, start, end):
    queue = deque([(start, [])])
    seen = {start}
    while queue:
        node, path = queue.popleft()
        if node == end:
            return path
        for neighbor, edge, sign in tree[node]:
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append((neighbor, path + [(edge, sign)]))
    return None


def _analyze(record):
    if not isinstance(record, dict) or record.get('schema') != 'md-free-energy-campaign-v1':
        raise ValueError('expected md-free-energy-campaign-v1')
    contract = record['contract']
    identity_fields = ('target_id', 'construct_id', 'forcefield_id', 'protocol_id', 'mapping_policy_id')
    for field in identity_fields:
        _text(contract[field], field)
    unit = contract['unit']
    if unit not in ('kcal/mol', 'kJ/mol'):
        raise ValueError('explicit kcal/mol or kJ/mol required; no automatic unit conversion')
    if _number(contract['temperature_kelvin'], 'temperature_kelvin') <= 0:
        raise ValueError('temperature_kelvin must be positive')
    minimum = contract['minimum_replicas']
    if type(minimum) is not int or minimum < 2:
        raise ValueError('minimum_replicas must be an integer >= 2')
    threshold = _number(contract['max_cycle_z'], 'max_cycle_z')
    if threshold <= 0:
        raise ValueError('max_cycle_z must be a positive prespecified diagnostic threshold')
    for key in ('edge_errors_independent', 'require_cycle'):
        if type(contract[key]) is not bool:
            raise ValueError(f'{key} must be boolean')
    ligands = record['ligands']
    if not isinstance(ligands, list) or len(ligands) < 2:
        raise ValueError('at least two ligands required')
    ligand_ids, ligand_hashes = set(), set()
    for ligand in ligands:
        identity = _text(ligand['id'], 'ligand id')
        digest = _sha(ligand['identity_sha256'], 'ligand identity_sha256')
        if identity in ligand_ids or digest in ligand_hashes:
            raise ValueError('duplicate ligand ID or molecular identity')
        ligand_ids.add(identity)
        ligand_hashes.add(digest)
    controls = record['controls']
    if not isinstance(controls, list) or not controls:
        raise ValueError('explicit essential controls required')
    control_ids, reasons = set(), []
    for control in controls:
        identity = _text(control['id'], 'control id')
        if identity in control_ids or type(control['passed']) is not bool:
            raise ValueError('duplicate control or nonboolean control outcome')
        control_ids.add(identity)
        if not control['passed']:
            reasons.append('failed-control:' + identity)
    edges = record['edges']
    if not isinstance(edges, list) or not edges:
        raise ValueError('free-energy edges required')
    edge_ids, edge_pairs = set(), set()
    replica_ids, run_ids, source_ids = set(), set(), set()
    summaries = []
    for edge in edges:
        identity = _text(edge['id'], 'edge id')
        a, b = edge['ligand_a'], edge['ligand_b']
        if a not in ligand_ids or b not in ligand_ids or a == b:
            raise ValueError('edge endpoints must be distinct known ligands')
        pair = tuple(sorted((a, b)))
        if identity in edge_ids or pair in edge_pairs:
            raise ValueError('duplicate edge or reversed pair; consolidate independent repeats')
        edge_ids.add(identity)
        edge_pairs.add(pair)
        _sha(edge['mapping_sha256'], 'mapping_sha256')
        replicas = edge['replicas']
        if not isinstance(replicas, list) or not replicas:
            raise ValueError('edge requires supplied independent replicas')
        values, errors = [], []
        for replica in replicas:
            for key, seen in (('replica_id', replica_ids), ('independent_run_id', run_ids), ('source_id', source_ids)):
                item = _text(replica[key], key)
                if item in seen:
                    raise ValueError('duplicated ' + key + '; restart segments are not replicas')
                seen.add(item)
            for key in (*identity_fields, 'unit', 'temperature_kelvin'):
                if replica[key] != contract[key] or type(replica[key]) is not type(contract[key]):
                    raise ValueError('replica mismatched ' + key)
            values.append(_number(replica['delta_delta_g'], 'delta_delta_g'))
            error = _number(replica['standard_error'], 'standard_error')
            if error <= 0:
                raise ValueError('standard_error must be positive, not a missing-value placeholder')
            errors.append(error)
        if len(replicas) < minimum:
            reasons.append('insufficient-replicas:' + identity)
        propagated = math.hypot(*errors) / len(errors)
        if not math.isfinite(propagated) or propagated <= 0:
            raise ValueError('reported uncertainty exceeds finite diagnostic range')
        summaries.append({'edge_id': identity, 'ligand_a': a, 'ligand_b': b,
                          'mapping_sha256': edge['mapping_sha256'], 'replicas': len(replicas),
                          'mean_delta_delta_g': statistics.mean(values),
                          'replica_se': statistics.stdev(values) / math.sqrt(len(values)) if len(values) > 1 else None,
                          'reported_error_se': propagated})
    tree = {key: [] for key in sorted(ligand_ids)}
    cycles = []
    for edge in summaries:
        a, b = edge['ligand_a'], edge['ligand_b']
        path = _tree_path(tree, b, a)
        if path is None:
            tree[a].append((b, edge, 1))
            tree[b].append((a, edge, -1))
            continue
        terms = [(edge, 1)] + path
        residual = math.fsum(item['mean_delta_delta_g'] * sign for item, sign in terms)
        error = math.hypot(*(item['reported_error_se'] for item, _ in terms)) if contract['edge_errors_independent'] else None
        z = abs(residual) / error if error is not None else None
        if z is not None and z > threshold:
            reasons.append('cycle-closure:' + edge['edge_id'])
        cycles.append({'edges': [{'edge_id': item['edge_id'], 'sign': sign} for item, sign in terms],
                       'closure_residual': residual, 'reported_error_se': error,
                       'absolute_z_diagnostic': z})
    start = min(ligand_ids)
    if any(_tree_path(tree, start, node) is None for node in ligand_ids):
        raise ValueError('disconnected ligand network; do not compare unlinked components')
    if contract['require_cycle'] and not cycles:
        reasons.append('no-cycle-diagnostic')
    if not contract['edge_errors_independent']:
        reasons.append('edge-dependence-unresolved')
    return {'schema': 'md-free-energy-analysis-v1',
            'input_sha256': hashlib.sha256(json.dumps(record, sort_keys=True, allow_nan=False).encode()).hexdigest(),
            'status': 'exploratory' if reasons else 'qualified-descriptive',
            'unit': unit, 'edge_direction': 'ligand_b - ligand_a', 'reasons': reasons,
            'ligand_count': len(ligand_ids), 'edges': summaries, 'fundamental_cycles': cycles,
            'engine_executed': False,
            'limitations': ['Supplied results only; no simulation, atom mapping or force-field validation.',
                            'Cycle error propagation assumes declared independent edge errors; cycles themselves need not be independent.',
                            'Reported estimator error and between-repeat variation are separate diagnostics; neither proves convergence.',
                            'A zero cycle residual cannot validate affinity, ranking, physical accuracy or biological effect.',
                            'No absolute free energies or MLE ligand ranking inferred.']}


def analyze_md_campaign(record):
    """Refuse nonfinite input/derived values rather than emitting invalid JSON."""
    try:
        json.dumps(record, allow_nan=False)
        result = _analyze(record)
        json.dumps(result, allow_nan=False)
        return result
    except OverflowError as error:
        raise ValueError('numeric range exceeds finite diagnostic capacity') from error
