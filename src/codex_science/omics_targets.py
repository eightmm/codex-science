"""Donor-level descriptive expression contrasts and dependency-aware target evidence."""

from collections import defaultdict
import json
import math
from statistics import fmean, variance

from codex_science.protein_variants import _number, _text


def _real(value, label):
    result = _number(value)
    if result is None:
        raise ValueError(f'{label} must be finite')
    return result


def _mean(values):
    return _real(fmean(values), 'derived mean')


def _batch_diagnostic(samples, reference, case, gene=None):
    donors = defaultdict(lambda: {reference: set(), case: set()})
    for sample in samples:
        if gene is None or sample['expression'][gene] is not None:
            donors[sample['batch']][sample['condition']].add(sample['donor_id'])
    rows, ratios = [], set()
    for batch, conditions in sorted(donors.items()):
        n_ref, n_case = len(conditions[reference]), len(conditions[case])
        total = n_ref + n_case
        divisor = math.gcd(n_case, total)
        ratios.add((n_case // divisor, total // divisor))
        rows.append({'batch_id': batch, 'condition_donor_counts': {reference: n_ref, case: n_case},
                     'case_donor_proportion': n_case / total,
                     'single_condition': not n_ref or not n_case})
    unresolved = any(row['single_condition'] for row in rows) or len(ratios) > 1
    return {'batches': rows, 'unresolved_unadjusted_imbalance': unresolved,
            'diagnostic': 'unavailable-no-observed-donors' if not rows else
                          'unadjusted-batch-imbalance' if unresolved else 'balanced-declared-donor-proportions'}


def _evidence_groups(rows, expression_cohorts):
    groups = []
    for row in rows:
        linked = [group for group in groups if row['origin_id'] in group['origins']
                  or set(row['cohort_ids']) & group['cohorts']]
        merged = {'records': [row], 'origins': {row['origin_id']}, 'cohorts': set(row['cohort_ids'])}
        for group in linked:
            merged['records'].extend(group['records'])
            merged['origins'].update(group['origins'])
            merged['cohorts'].update(group['cohorts'])
            groups.remove(group)
        groups.append(merged)
    return [{'record_ids': sorted(row['record_id'] for row in group['records']),
             'origin_ids': sorted(group['origins']), 'cohort_ids': sorted(group['cohorts']),
             'directions': sorted({row['direction'] for row in group['records']}),
             'overlaps_expression_cohort': bool(group['cohorts'] & expression_cohorts)}
            for group in groups]


def analyze_omics_targets(record):
    """Describe frozen two-condition log-expression data without DE/causal inference."""
    try:
        json.dumps(record, allow_nan=False)
        result = _analyze_omics_targets(record)
        json.dumps(result, allow_nan=False)
    except (TypeError, OverflowError, RecursionError) as error:
        raise ValueError('input and derived output must be finite JSON') from error
    return result


def _analyze_omics_targets(record):
    if not isinstance(record, dict) or record.get('schema') != 'omics-target-input-v1':
        raise ValueError('expected omics-target-input-v1')
    if type(record.get('synthetic')) is not bool:
        raise ValueError('synthetic must be explicitly boolean')
    if record.get('expression_unit') != 'log2-normalized-expression':
        raise ValueError('supply comparable log2-normalized-expression; raw counts unsupported')
    _text(record.get('normalization_provenance'), 'normalization_provenance')
    reference = _text(record.get('reference_condition'), 'reference_condition')
    case = _text(record.get('case_condition'), 'case_condition')
    if reference == case:
        raise ValueError('conditions must differ')
    paired = record.get('paired')
    if type(paired) is not bool:
        raise ValueError('paired must be boolean')
    minimum = record.get('minimum_donors')
    if type(minimum) is not int or minimum < 2:
        raise ValueError('minimum_donors must be an integer >= 2')
    direction = record.get('desired_direction')
    if direction not in ('higher', 'lower'):
        raise ValueError('desired_direction must be higher or lower')
    threshold = _real(record.get('minimum_signed_difference'), 'minimum_signed_difference')
    if threshold < 0:
        raise ValueError('minimum_signed_difference must be nonnegative')
    genes = record.get('gene_ids')
    if not isinstance(genes, list) or not genes or any(not isinstance(g, str) or not g.strip() for g in genes):
        raise ValueError('gene_ids must be nonempty stable identifiers')
    if len(set(genes)) != len(genes):
        raise ValueError('duplicate gene identity')
    controls = record.get('controls')
    if not isinstance(controls, list) or not controls:
        raise ValueError('declare essential controls')
    control_ids = set()
    for control in controls:
        if not isinstance(control, dict):
            raise ValueError('control must be an object')
        cid = _text(control.get('id'), 'control id')
        if cid in control_ids or type(control.get('essential')) is not bool:
            raise ValueError('duplicate control or invalid essential flag')
        control_ids.add(cid)
        if control.get('status') not in ('passed', 'failed', 'unavailable'):
            raise ValueError('invalid control status')
        _text(control.get('evidence'), 'control evidence')
    if not any(c['essential'] for c in controls):
        raise ValueError('declare at least one essential control')
    controls_passed = all(c['status'] == 'passed' for c in controls if c['essential'])
    samples = record.get('samples')
    if not isinstance(samples, list) or not samples:
        raise ValueError('samples must be nonempty')
    ids, donor_cohorts, donor_conditions = set(), {}, defaultdict(set)
    donor_rows, batches, cohort_conditions = defaultdict(list), defaultdict(set), defaultdict(set)
    for sample in samples:
        if not isinstance(sample, dict):
            raise ValueError('sample must be an object')
        sid = _text(sample.get('sample_id'), 'sample_id')
        donor = _text(sample.get('donor_id'), 'donor_id')
        cohort = _text(sample.get('cohort_id'), 'cohort_id')
        batch = _text(sample.get('batch'), 'batch')
        condition = sample.get('condition')
        if sid in ids:
            raise ValueError('duplicate sample identity')
        ids.add(sid)
        if condition not in (reference, case):
            raise ValueError('unknown condition')
        if donor in donor_cohorts and donor_cohorts[donor] != cohort:
            raise ValueError('same donor reused across declared independent cohorts')
        donor_cohorts[donor] = cohort
        donor_conditions[donor].add(condition)
        expression = sample.get('expression')
        if not isinstance(expression, dict) or set(expression) != set(genes):
            raise ValueError('sample expression must cover frozen gene_ids; mark missing as null')
        for value in expression.values():
            _number(value)
        donor_rows[(cohort, condition, donor)].append(sample)
        batches[(cohort, batch)].add(condition)
        cohort_conditions[cohort].add(condition)
    for cohort, conditions in cohort_conditions.items():
        if conditions != {reference, case}:
            raise ValueError('cohort/condition confounding')
        if not any(cs == {reference, case} for (c, _), cs in batches.items() if c == cohort):
            raise ValueError('batch/condition confounding')
    if paired and any(cs != {reference, case} for cs in donor_conditions.values()):
        raise ValueError('paired design requires both conditions for every donor')
    if not paired and any(len(cs) != 1 for cs in donor_conditions.values()):
        raise ValueError('unpaired design reuses a donor across conditions')
    cohort_samples = {cohort: [sample for sample in samples if sample['cohort_id'] == cohort]
                      for cohort in cohort_conditions}
    batch_diagnostics = [{'cohort_id': cohort, **_batch_diagnostic(rows, reference, case)}
                         for cohort, rows in sorted(cohort_samples.items())]
    evidence = record.get('evidence')
    if not isinstance(evidence, list):
        raise ValueError('evidence must be a list, including empty if unavailable')
    record_ids, evidence_by_gene = set(), defaultdict(list)
    for row in evidence:
        if not isinstance(row, dict):
            raise ValueError('evidence must be an object')
        rid = _text(row.get('record_id'), 'evidence record_id')
        _text(row.get('origin_id'), 'evidence origin_id')
        _text(row.get('source'), 'evidence source')
        _text(row.get('source_release'), 'source_release')
        if rid in record_ids or row.get('gene_id') not in genes:
            raise ValueError('duplicate evidence identity or unknown gene')
        record_ids.add(rid)
        cohorts = row.get('cohort_ids')
        if not isinstance(cohorts, list) or len(set(cohorts)) != len(cohorts):
            raise ValueError('declare unique evidence cohort_ids')
        for cid in cohorts:
            _text(cid, 'evidence cohort_id')
        if row.get('direction') not in ('supports', 'contradicts', 'neutral'):
            raise ValueError('invalid evidence direction')
        evidence_by_gene[row['gene_id']].append(dict(row))
    results = []
    for gene in genes:
        cohort_results = []
        for cohort in sorted(cohort_conditions):
            values = {condition: {} for condition in (reference, case)}
            missing_samples = 0
            for (cid, condition, donor), rows in donor_rows.items():
                if cid != cohort:
                    continue
                present = [r['expression'][gene] for r in rows if r['expression'][gene] is not None]
                missing_samples += len(rows) - len(present)
                if present:
                    values[condition][donor] = _mean(present)
            if paired:
                common = sorted(set(values[reference]) & set(values[case]))
                contrasts = [_real(values[case][d] - values[reference][d], 'paired difference') for d in common]
                n_reference = n_case = len(common)
                difference = _mean(contrasts) if contrasts else None
                se = math.sqrt(variance(contrasts) / len(contrasts)) if len(contrasts) > 1 else None
            else:
                left, right = list(values[reference].values()), list(values[case].values())
                n_reference, n_case = len(left), len(right)
                difference = _real(_mean(right) - _mean(left), 'unpaired difference') if left and right else None
                se = math.sqrt(variance(left) / len(left) + variance(right) / len(right)) if min(len(left), len(right)) > 1 else None
            if se is not None:
                se = _real(se, 'standard error')
            cohort_results.append({'cohort_id': cohort, 'reference_donors': n_reference, 'case_donors': n_case,
                                   'difference': difference, 'standard_error': se, 'missing_samples': missing_samples,
                                   'batch_design': _batch_diagnostic(cohort_samples[cohort], reference, case, gene),
                                   'sufficient': min(n_reference, n_case) >= minimum})
        sufficient = all(c['sufficient'] for c in cohort_results)
        effects = [c['difference'] for c in cohort_results if c['difference'] is not None]
        effect = _mean(effects) if len(effects) == len(cohort_results) else None
        sign = 1 if direction == 'higher' else -1
        signed_effect = _real(effect * sign, 'signed effect') if effect is not None else None
        discordant = bool(effects) and min(effects) < 0 < max(effects)
        reasons = []
        if not sufficient:
            reasons.append('insufficient-donors-or-missingness')
        if any(cohort['batch_design']['unresolved_unadjusted_imbalance'] for cohort in cohort_results):
            reasons.append('unresolved-unadjusted-batch-imbalance')
        if not controls_passed:
            reasons.append('essential-control-not-passed')
        if discordant:
            reasons.append('discordant-cohort-directions')
        if signed_effect is None or signed_effect < threshold:
            reasons.append('below-prespecified-directional-threshold')
        groups = _evidence_groups(evidence_by_gene[gene], set(cohort_conditions))
        if any(row['direction'] == 'contradicts' for row in evidence_by_gene[gene]):
            reasons.append('contradictory-external-evidence')
        results.append({'gene_id': gene, 'cohorts': cohort_results, 'equal_cohort_mean_difference': effect,
                        'signed_difference': signed_effect, 'exclusion_reasons': reasons,
                        'status': 'exploratory-candidate' if not reasons else 'not-prioritized',
                        'evidence': evidence_by_gene[gene], 'dependency_groups': groups,
                        'evidence_unavailable': not evidence_by_gene[gene]})
    prioritized = sorted((r for r in results if not r['exclusion_reasons']),
                         key=lambda r: (-r['signed_difference'], r['gene_id']))
    return {'schema': 'omics-target-analysis-v1', 'execution': 'offline-donor-expression-and-evidence-analysis',
            'synthetic': record['synthetic'],
            'contrast': {'case': case, 'reference': reference, 'paired': paired,
                         'unit': 'difference-of-mean-log2-normalized-expression',
                         'estimator': 'technical-sample means within donor, donor contrasts within cohort, equal-cohort mean'},
            'sample_count': len(samples), 'donor_count': len(donor_conditions), 'gene_count': len(genes),
            'batch_diagnostics': batch_diagnostics,
            'controls': controls, 'targets': results, 'prioritized_gene_ids': [r['gene_id'] for r in prioritized],
            'p_values': None, 'causal_target_claim': False,
            'limitations': ['No normalization, differential-expression model, cell annotation or source retrieval executed.',
                            'Unadjusted descriptive effects from partially imbalanced batches are retained but cannot prioritize a target; balanced declared proportions do not prove absence of batch effects.',
                            'Descriptive means and standard errors are not p-values or adjusted differential-expression evidence.',
                            'Evidence grouping uses declared origin/cohort identity and cannot establish independence or causal relevance.',
                            'Expression differences and external associations do not establish a therapeutic target; independent review required.']}
