"""Offline substitution mapping and within-protein rank analysis; no model inference."""
import hashlib
import math
import re

AA = frozenset('ACDEFGHIKLMNPQRSTVWY')


def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{field} must be a nonempty string')
    return value


def _number(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('scores must be finite JSON numbers or null')
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError('scores must be finite JSON numbers or null')
    return value


def _ranks(values):
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        for index in order[start:end]:
            ranks[index] = (start + 1 + end) / 2
        start = end
    return ranks


def _correlation(x, y):
    if len(x) < 2:
        return {'value': None, 'reason': 'fewer-than-two-pairs', 'n': len(x)}
    x, y = _ranks(x), _ranks(y)
    mx, my = sum(x) / len(x), sum(y) / len(y)
    xx = sum((v - mx) ** 2 for v in x)
    yy = sum((v - my) ** 2 for v in y)
    if not xx or not yy:
        return {'value': None, 'reason': 'constant-ranks', 'n': len(x)}
    return {'value': sum((a-mx)*(b-my) for a, b in zip(x, y)) / math.sqrt(xx*yy),
            'reason': None, 'n': len(x)}


def analyze_protein_variants(record):
    """Validate pack-local v1 input and retain all scores, failures and denominators."""
    if not isinstance(record, dict) or record.get('schema') != 'protein-variant-input-v1':
        raise ValueError('expected protein-variant-input-v1')
    proteins = record.get('proteins')
    if not isinstance(proteins, list) or not proteins:
        raise ValueError('proteins must be nonempty')
    seen_ids, identities, split_groups, sequences = set(), set(), {}, {}
    results = []
    for protein in proteins:
        if not isinstance(protein, dict):
            raise ValueError('protein must be an object')
        pid = _text(protein.get('id'), 'protein id')
        if pid in seen_ids:
            raise ValueError('duplicate protein identity')
        seen_ids.add(pid)
        reference = _text(protein.get('reference'), 'reference')
        if not set(reference) <= AA:
            raise ValueError('reference contains unsupported residues')
        offset = protein.get('coordinate_offset')
        if type(offset) is not int:
            raise ValueError('coordinate_offset must be an integer')
        split = protein.get('split')
        if split not in ('train', 'validation', 'test'):
            raise ValueError('split must be train, validation or test')
        group = _text(protein.get('homology_group'), 'homology_group')
        for mapping, key in ((split_groups, group), (sequences, reference)):
            if key in mapping and mapping[key] != split:
                raise ValueError('split/homology leakage')
            mapping[key] = split
        specs = {}
        for field in ('model', 'assay'):
            spec = protein.get(field)
            if not isinstance(spec, dict) or spec.get('direction') not in ('higher', 'lower'):
                raise ValueError(f'{field} direction must be higher or lower')
            _text(spec.get('units'), f'{field} units')
            _text(spec.get('definition'), f'{field} definition')
            specs[field] = spec
        controls = protein.get('controls')
        if not isinstance(controls, list) or not controls:
            raise ValueError('declare controls, including unavailable controls')
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
            raise ValueError('at least one essential control must be declared')
        rows, variant_ids = [], set()
        variants = protein.get('variants')
        if not isinstance(variants, list) or not variants:
            raise ValueError('variants must be nonempty')
        for variant in variants:
            if not isinstance(variant, dict):
                raise ValueError('variant must be an object')
            vid = _text(variant.get('id'), 'variant id')
            if vid in variant_ids:
                raise ValueError('duplicate variant identity')
            variant_ids.add(vid)
            edits = variant.get('substitutions')
            if not isinstance(edits, list):
                raise ValueError('substitutions must be a list; indels unsupported')
            seq, positions = list(reference), set()
            for edit in edits:
                match = re.fullmatch(r'([ACDEFGHIKLMNPQRSTVWY])([1-9][0-9]*)([ACDEFGHIKLMNPQRSTVWY])', edit) if isinstance(edit, str) else None
                if not match:
                    raise ValueError('only canonical substitutions are supported; indels unsupported')
                wt, position, alt = match.groups()
                index = int(position) - offset - 1
                if index < 0 or index >= len(reference) or reference[index] != wt:
                    raise ValueError('WT mismatch or coordinate offset out of bounds')
                if index in positions or wt == alt:
                    raise ValueError('overlapping or no-op substitution')
                positions.add(index)
                seq[index] = alt
            sequence = ''.join(seq)
            if sequence in sequences and sequences[sequence] != split:
                raise ValueError('variant sequence split leakage')
            sequences[sequence] = split
            identity = (reference, sequence)
            if identity in identities:
                raise ValueError('duplicate reference/variant sequence identity')
            identities.add(identity)
            row = {'id': vid, 'sequence': sequence, 'sequence_sha256': hashlib.sha256(sequence.encode()).hexdigest(),
                   'edit_distance': len(positions), 'baseline': -len(positions)}
            for field in ('model', 'assay'):
                score = variant.get(field)
                if not isinstance(score, dict) or score.get('status') not in ('ok', 'failed', 'missing'):
                    raise ValueError('score requires ok, failed or missing status')
                value = _number(score.get('value'))
                if (score['status'] == 'ok') != (value is not None):
                    raise ValueError('score status/value mismatch')
                if score['status'] != 'ok':
                    _text(score.get('reason'), 'missing/failed score reason')
                if score.get('units') != specs[field]['units']:
                    raise ValueError('score units mismatch')
                row[field] = dict(score)
            rows.append(row)
        paired = [r for r in rows if r['model']['status'] == r['assay']['status'] == 'ok']
        sign = lambda field: 1 if specs[field]['direction'] == 'higher' else -1
        assay = [r['assay']['value'] * sign('assay') for r in paired]
        admissible = all(c['status'] == 'passed' for c in controls if c['essential'])
        model_rows = [r for r in rows if r['model']['status'] == 'ok']
        ranks = _ranks([-r['model']['value'] * sign('model') for r in model_rows])
        for row, rank in zip(model_rows, ranks):
            row['model_rank'] = rank
        results.append({'id': pid, 'reference_sha256': hashlib.sha256(reference.encode()).hexdigest(),
                        'coordinate_offset': offset, 'split': split, 'homology_group': group,
                        'score_definitions': specs, 'controls': controls, 'variants': rows,
                        'total': len(rows), 'paired': len(paired),
                        'model_vs_assay_spearman': _correlation([r['model']['value'] * sign('model') for r in paired], assay),
                        'baseline_vs_assay_spearman': _correlation([r['baseline'] for r in paired], assay),
                        'candidate_status': 'unreviewed' if admissible else 'blocked-controls',
                        'review_required': True})
    return {'schema': 'protein-variant-analysis-v1', 'execution': 'offline-supplied-score-analysis',
            'baseline': {'definition': 'negative substitution count', 'direction': 'higher', 'units': 'substitutions', 'model_free': True},
            'proteins': results, 'pooled_metric': None,
            'limitations': ['No model executed.', 'Declared homology groups checked; homology and pretraining overlap not independently established.',
                            'Scores do not establish function, pathogenicity or clinical effect.', 'Candidates require independent review.']}
