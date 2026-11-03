"""Assay-aware substitution cycles and proposed libraries; no model or assay execution."""

from collections import defaultdict
from copy import deepcopy
import json
import math
from statistics import fmean, stdev

from codex_science.experiment_planner import plan_next_experiment
from codex_science.protein_variants import _number, _text, analyze_protein_variants


def _finite(value, field):
    value = _number(value)
    if value is None:
        raise ValueError(f'{field} must be finite')
    return value


def analyze_protein_engineering(record):
    """Join replicates to one frozen construct and propose unmeasured substitutions."""
    try:
        json.dumps(record, allow_nan=False)
        result = _analyze_protein_engineering(record)
        json.dumps(result, allow_nan=False)
    except (TypeError, OverflowError, RecursionError) as error:
        raise ValueError('input and derived output must be finite JSON') from error
    return result


def _analyze_protein_engineering(record):
    if not isinstance(record, dict) or record.get('schema') != 'protein-engineering-input-v1':
        raise ValueError('expected protein-engineering-input-v1')
    if type(record.get('synthetic')) is not bool:
        raise ValueError('synthetic must be explicitly boolean')
    source = record.get('variant_input')
    initial = analyze_protein_variants(source)
    if len(initial['proteins']) != 1:
        raise ValueError('one construct and assay per engineering cycle')
    protein = source['proteins'][0]
    construct_id = _text(record.get('construct_id'), 'construct_id')
    assay_id = _text(record.get('assay_id'), 'assay_id')
    cycle_id = _text(record.get('cycle_id'), 'cycle_id')
    variants = {v['id']: v for v in protein['variants']}
    if any(v['assay']['status'] != 'missing' for v in variants.values()):
        raise ValueError('raw measurements are authoritative; initial assay scores must be missing')
    roles = record.get('variant_roles')
    if not isinstance(roles, dict) or set(roles) != set(variants):
        raise ValueError('variant_roles must cover every variant exactly')
    if any(role not in ('feedback', 'evaluation', 'candidate') for role in roles.values()):
        raise ValueError('invalid variant role')
    training = record.get('model_training_variant_ids')
    if not isinstance(training, list) or len(set(training)) != len(training):
        raise ValueError('declare unique model_training_variant_ids')
    if not set(training) <= set(variants):
        raise ValueError('unknown model-training variant identity')
    if any(roles[vid] == 'evaluation' for vid in training):
        raise ValueError('model training/evaluation leakage')
    minimum = record.get('minimum_replicates')
    if type(minimum) is not int or minimum < 2:
        raise ValueError('minimum_replicates must be an integer >= 2')
    distance_cap = record.get('maximum_parent_distance')
    if type(distance_cap) is not int or distance_cap < 1:
        raise ValueError('maximum_parent_distance must be an integer >= 1')
    measurements = record.get('measurements')
    if not isinstance(measurements, list):
        raise ValueError('measurements must be a list, including failures')
    by_variant = defaultdict(list)
    replicate_ids = set()
    for row in measurements:
        if not isinstance(row, dict):
            raise ValueError('measurement must be an object')
        vid = _text(row.get('variant_id'), 'measurement variant_id')
        if vid not in variants or roles[vid] == 'candidate':
            raise ValueError('unknown or unmeasured-candidate measurement identity')
        if row.get('construct_id') != construct_id or row.get('assay_id') != assay_id:
            raise ValueError('measurement construct/assay mismatch')
        if row.get('units') != protein['assay']['units']:
            raise ValueError('measurement unit mismatch')
        replicate = _text(row.get('independent_replicate_id'), 'independent_replicate_id')
        if (vid, replicate) in replicate_ids:
            raise ValueError('duplicate variant/independent replicate identity')
        replicate_ids.add((vid, replicate))
        status = row.get('status')
        if status not in ('ok', 'failed', 'missing'):
            raise ValueError('invalid measurement status')
        value = _number(row.get('value'))
        if (status == 'ok') != (value is not None):
            raise ValueError('measurement status/value mismatch')
        if status != 'ok':
            _text(row.get('reason'), 'measurement reason')
        by_variant[vid].append(dict(row))
    enriched = deepcopy(source)
    summaries = {}
    for variant in enriched['proteins'][0]['variants']:
        vid = variant['id']
        rows = by_variant[vid]
        values = [r['value'] for r in rows if r['status'] == 'ok']
        mean = _finite(fmean(values), 'replicate mean') if values else None
        se = _finite(stdev(values) / math.sqrt(len(values)), 'replicate SE') if len(values) > 1 else None
        summaries[vid] = {'total': len(rows), 'ok': len(values), 'mean': mean,
                          'standard_error': se, 'sufficient': len(values) >= minimum,
                          'failed': sum(r['status'] == 'failed' for r in rows),
                          'missing': sum(r['status'] == 'missing' for r in rows)}
        if values:
            variant['assay'] = {'status': 'ok', 'value': mean, 'units': protein['assay']['units']}
        elif rows:
            variant['assay'] = {'status': 'failed' if any(r['status'] == 'failed' for r in rows) else 'missing',
                                'value': None, 'units': protein['assay']['units'], 'reason': 'no successful replicate'}
    analyzed = analyze_protein_variants(enriched)['proteins'][0]
    enriched_rows = {v['id']: v for v in analyzed['variants']}
    # Evaluation rows remain descriptive diagnostics and never enter next-batch objectives.
    evaluation = deepcopy(enriched)
    evaluation['proteins'][0]['variants'] = [v for v in evaluation['proteins'][0]['variants']
                                            if roles[v['id']] == 'evaluation' and summaries[v['id']]['sufficient']]
    evaluation_summary = None
    if evaluation['proteins'][0]['variants']:
        evaluation_summary = analyze_protein_variants(evaluation)['proteins'][0]['model_vs_assay_spearman']
    parents = record.get('candidate_parents')
    candidate_ids = {vid for vid in variants if roles[vid] == 'candidate'}
    if not isinstance(parents, dict) or set(parents) != candidate_ids:
        raise ValueError('candidate_parents must cover each unmeasured candidate')
    costs = record.get('candidate_costs')
    if not isinstance(costs, dict) or set(costs) != candidate_ids:
        raise ValueError('candidate_costs must cover each unmeasured candidate')
    groups = record.get('diversity_groups')
    if not isinstance(groups, dict) or set(groups) != candidate_ids:
        raise ValueError('diversity_groups must cover each unmeasured candidate')
    weights = record.get('objective_weights')
    if not isinstance(weights, dict) or set(weights) != {'parent_observed', 'supplied_model'}:
        raise ValueError('declare parent_observed and supplied_model objective weights')
    if any(_finite(value, 'objective weight') < 0 for value in weights.values()) or not any(weights.values()):
        raise ValueError('objective weights must be nonnegative with a positive total')
    sign = lambda field: 1 if protein[field]['direction'] == 'higher' else -1
    eligible = []
    excluded = []
    controls_passed = analyzed['candidate_status'] != 'blocked-controls'
    for vid in sorted(candidate_ids):
        parent = parents[vid]
        if parent not in variants or roles[parent] != 'feedback':
            raise ValueError('candidate parent must be feedback; evaluation-label leakage forbidden')
        cost = _finite(costs[vid], 'candidate cost')
        if cost < 0:
            raise ValueError('candidate cost must be nonnegative')
        group = _text(groups[vid], 'diversity group')
        parent_sequence = enriched_rows[parent]['sequence']
        candidate_sequence = enriched_rows[vid]['sequence']
        distance = sum(left != right for left, right in zip(parent_sequence, candidate_sequence))
        if not 1 <= distance <= distance_cap:
            raise ValueError('candidate distance from observed parent violates frozen cap')
        reasons = []
        if not summaries[parent]['sufficient']:
            reasons.append('insufficient-parent-replicates')
        if variants[vid]['model']['status'] != 'ok':
            reasons.append('unavailable-model-score')
        if not controls_passed:
            reasons.append('failed-or-unavailable-essential-control')
        if reasons:
            excluded.append({'id': vid, 'parent_id': parent, 'reasons': reasons})
            continue
        eligible.append({'id': vid, 'properties': {
            'parent_observed': _finite(summaries[parent]['mean'] * sign('assay'), 'parent utility'),
            'supplied_model': _finite(variants[vid]['model']['value'] * sign('model'), 'model utility')},
            'cost': cost, 'uncertainty': summaries[parent]['standard_error'],
            'diversity_group': group, 'metadata': {'parent_id': parent, 'cycle_id': cycle_id}})
    proposal = None
    if eligible:
        proposal = plan_next_experiment({
            'decision': 'Propose an unmeasured substitution library for the frozen construct/assay',
            'objectives': [{'name': name, 'direction': 'maximize', 'weight': weights[name]}
                           for name in ('parent_observed', 'supplied_model')],
            'candidates': eligible, 'constraints': record.get('constraints'),
            'uncertainty_weight': 0, 'diversity_bonus': 0,
        }, created_at='not-recorded-offline-analysis')
    return {'schema': 'protein-engineering-analysis-v1', 'execution': 'offline-assay-feedback-analysis',
            'synthetic': record['synthetic'],
            'cycle_id': cycle_id, 'construct_id': construct_id, 'assay_id': assay_id,
            'units': protein['assay']['units'], 'assay_direction': protein['assay']['direction'],
            'roles': roles, 'measurements': measurements, 'measurement_summaries': summaries,
            'variants': analyzed['variants'], 'evaluation_only_spearman': evaluation_summary,
            'next_library': proposal, 'excluded_candidates': excluded,
            'status': 'proposed-unreviewed' if proposal else 'no-admissible-candidates',
            'limitations': ['No model, surrogate fitting, candidate generation or assay executed.',
                            'Selection combines supplied model utility and observed parent utility; it is a heuristic, not calibrated active learning.',
                            'Replicate independence and model-training exposure are supplied declarations, not established by this checker.',
                            'Independent review and new assays are required; scores do not establish biological function.']}
