"""Offline, read-only plate-screen fixture admission and stdlib reference computation."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import statistics

STAGES = ("01-freeze", "02-inventory", "03-qc", "04-hits", "05-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_TOTAL_NODES = 4000000
MAX_DEPTH = 32
MAX_TEXT = 4096
MAX_ITEMS = 20000
MAX_PLATES = 128
MAX_WELLS = 1536
MAX_ROWS = 100000
MAX_CLAIMS = 128
MAX_RECORDS = 512
MAX_NUMBER = 1e100
POSITIVE = {"supported", "replicated", "suggestive"}
WORDING_FAMILIES = (
    "caus", "mechanis", "therap", "clinic", "efficac", "effective", "treat", "cure",
    "prevent", "recommend", "prescri", "bind", "affinit", "inhibit", "activat",
    "regulat", "driv", "induc",
)
OVERREACH = re.compile(
    r"\b(?:" + "|".join(word + r"\w*" for word in WORDING_FAMILIES)
    + r"|truth|physical[\s-]+validity|activ\w*|poten\w*)\b", re.I,
)
UNAVAILABLE_POSITIVE = re.compile(r"\b(?:supported|replicated|suggestive|significan\w*)\b", re.I)
NON_EVIDENCE = re.compile(r"review|approv|comput|numer|physical|clinic|truth", re.I)

def _require(condition, code, message):
    if not condition:
        raise ValueError(f"{code}: {message}")


def _obj(value, label, fields=None):
    _require(type(value) is dict, "invalid-record", f"{label} must be an object")
    if fields is not None:
        _require(set(value) == set(fields), "invalid-record", f"{label} has missing or unknown fields")
    return value


def _items(value, label, limit=MAX_ITEMS, empty=False):
    _require(type(value) is list and (empty or bool(value)), "invalid-record", f"{label} must be a list")
    _require(len(value) <= limit, "input-limit", f"{label} exceeds limit {limit}")
    return value


def _text(value, label):
    _require(type(value) is str and 0 < len(value) <= MAX_TEXT and bool(value.strip())
             and not any(0xD800 <= ord(c) <= 0xDFFF for c in value),
             "invalid-record", f"{label} must be bounded nonempty text")
    return value


def _names(value, label, limit=MAX_ITEMS, empty=False):
    values = _items(value, label, limit, empty)
    for item in values:
        _text(item, label)
    _require(len(set(values)) == len(values), "invalid-record", f"duplicate {label}")
    return values


def _number(value, label, low=0, high=MAX_NUMBER, integer=False):
    valid = type(value) is int if integer else type(value) in (int, float)
    _require(valid and -MAX_NUMBER <= value <= MAX_NUMBER and math.isfinite(value) and low <= value <= high,
             "invalid-record", f"{label} must be finite in [{low}, {high}] with the declared numeric type")
    return value


def _boolean(value, label):
    _require(type(value) is bool, "invalid-record", f"{label} must be boolean")
    return value


def _pairs(pairs):
    _require(len(pairs) <= MAX_ITEMS, "input-limit", "too many object fields")
    result = {}
    for key, value in pairs:
        _require(key not in result, "invalid-json", "duplicate JSON key")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("invalid-json: non-finite JSON number")


def _int(value):
    _require(len(value.lstrip("-")) <= 101, "invalid-json", "huge JSON integer")
    return _number(int(value), "JSON integer", -MAX_NUMBER)


def _float(value):
    return _number(float(value), "JSON number", -MAX_NUMBER)


def _json_nodes(raw, limit):
    """Count value tokens without allocating a parsed tree; _json validates syntax."""
    start = re.compile(rb'[^ \t\r\n,:}\]]')
    string_end = re.compile(rb'["\\]')
    space = re.compile(rb'[ \t\r\n]*')
    primitive = re.compile(rb'[^ \t\r\n,:{}\[\]"]+')
    position = nodes = 0
    while match := start.search(raw, position):
        position = match.end()
        char = raw[match.start()]
        if char == ord('"'):
            while True:
                end = string_end.search(raw, position)
                _require(end is not None, "invalid-json", "unterminated JSON string")
                position = end.end()
                if raw[end.start()] == ord('"'):
                    break
                position += 1
            position = space.match(raw, position).end()
            if raw[position:position + 1] == b':':
                continue
        elif char not in b'{[':
            position = primitive.match(raw, match.start()).end()
        nodes += 1
        _require(nodes <= limit, "input-limit", "total JSON node budget exceeded")
    return nodes


def _json(raw):
    try:
        root = _obj(json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                              parse_int=_int, parse_float=_float, parse_constant=_constant), "JSON root")
        pending = [(root, 0)]
        while pending:
            value, depth = pending.pop()
            if type(value) is str:
                _require(len(value) <= MAX_TEXT, "input-limit", "JSON text exceeds MAX_TEXT")
            elif type(value) in (dict, list):
                _require(depth <= MAX_DEPTH, "input-limit", "JSON nesting exceeds MAX_DEPTH")
                _require(len(value) <= MAX_ITEMS, "input-limit", "JSON container exceeds MAX_ITEMS")
                if type(value) is dict:
                    for key in value:
                        _require(len(key) <= MAX_TEXT, "input-limit", "JSON key exceeds MAX_TEXT")
                children = value.values() if type(value) is dict else value
                pending.extend((child, depth + 1) for child in children)
        return root
    except (UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError("invalid-json: bounded finite UTF-8 JSON object required") from error
    except json.JSONDecodeError as error:
        raise ValueError("invalid-json: malformed JSON") from error


def _relative(value):
    value = _text(value, "artifact path")
    path = PurePosixPath(value)
    _require(not path.is_absolute() and path.as_posix() == value and value != "."
             and ".." not in path.parts and "\\" not in value and not re.match(r"^[A-Za-z]:", value)
             and all(ord(char) >= 32 for char in value), "input-path", "canonical bundle-relative path required")
    return path


def _signature(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _open_root(root):
    """Pin each ancestor without following links, including a swap at open time."""
    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_DIRECTORY
    descriptor = os.open(root.anchor, flags)
    try:
        for part in root.parts[1:]:
            before = os.lstat(part, dir_fd=descriptor)
            _require(stat.S_ISDIR(before.st_mode), "input-root", "root ancestors must be real directories")
            child = os.open(part, flags, dir_fd=descriptor)
            opened = os.fstat(child)
            if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
                os.close(child)
                raise ValueError("input-root: root ancestor changed during open")
            os.close(descriptor)
            descriptor = child
        resolved = root.resolve(strict=True)
        current = os.stat(resolved, follow_symlinks=False)
        opened = os.fstat(descriptor)
        _require(resolved == root and (opened.st_dev, opened.st_ino) == (current.st_dev, current.st_ino),
                 "input-root", "root changed or resolved through a symlink")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


class _Bundle:
    def __init__(self, path):
        absolute = Path(os.path.abspath(path))
        self.root = absolute.parent
        self.entry = absolute.name
        self.cache = {}
        self.artifacts = {}
        self.bytes_read = 0
        self.nodes_read = 0
        self.descriptor = _open_root(self.root)
        opened = os.fstat(self.descriptor)
        self.root_identity = (opened.st_dev, opened.st_ino)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        os.close(self.descriptor)

    def read(self, path, *, checked=None):
        flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
        directory = os.dup(self.descriptor)
        try:
            for part in path.parts[:-1]:
                before = os.lstat(part, dir_fd=directory)
                _require(stat.S_ISDIR(before.st_mode), "input-file", "symlinked artifact component")
                child = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
                opened = os.fstat(child)
                if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
                    os.close(child)
                    raise ValueError("input-file: artifact ancestor changed")
                os.close(directory)
                directory = child
            before = os.lstat(path.name, dir_fd=directory)
            _require(stat.S_ISREG(before.st_mode) and before.st_size <= MAX_BYTES,
                     "input-file", "input must be a regular file at most 64 MiB")
            descriptor = os.open(path.name, flags, dir_fd=directory)
            with os.fdopen(descriptor, "rb") as handle:
                opened = os.fstat(handle.fileno())
                _require(stat.S_ISREG(opened.st_mode) and opened.st_size <= MAX_BYTES
                         and _signature(before) == _signature(opened), "input-file", "input changed during open")
                signature = _signature(opened)
                identity = signature[:2]
                cached = self.artifacts.get(identity)
                if cached is not None:
                    _require(signature == cached[2], "input-changed", "cached input modified during validation")
                    if checked is None or identity in checked:
                        return None, signature
                limit = MAX_BYTES if checked is not None else min(MAX_BYTES, MAX_TOTAL_BYTES - self.bytes_read)
                _require(opened.st_size <= limit, "input-limit", "total input byte budget exceeded")
                raw = handle.read(limit + 1)
                after = os.fstat(handle.fileno())
            _require(len(raw) <= limit and len(raw) == opened.st_size and _signature(opened) == _signature(after),
                     "input-file", "input grew or changed during read")
            if checked is None:
                self.bytes_read += len(raw)
            return raw, _signature(after)
        finally:
            os.close(directory)

    def load(self, identity, schema=None):
        _obj(identity, "artifact identity", ("path", "sha256"))
        path = _relative(identity["path"])
        expected = _text(identity["sha256"], "SHA-256")
        _require(re.fullmatch(r"[0-9a-f]{64}", expected) is not None, "input-hash", "invalid SHA-256")
        value, digest = self.snapshot(path)
        _require(expected == digest, "input-hash", "artifact hash mismatch")
        if schema is not None:
            _require(value.get("schema") == schema and value.get("fixture") is True,
                     "invalid-record", f"expected synthetic fixture {schema}")
        return value

    def snapshot(self, path):
        name = path.as_posix()
        if name not in self.cache:
            _require(len(self.cache) < MAX_RECORDS, "input-limit", "too many input artifacts")
            raw, signature = self.read(path)
            identity = signature[:2]
            if raw is not None:
                nodes = _json_nodes(raw, MAX_TOTAL_NODES - self.nodes_read)
                self.artifacts[identity] = (_json(raw), hashlib.sha256(raw).hexdigest(), signature)
                self.nodes_read += nodes
            self.cache[name] = self.artifacts[identity]
        value, digest, _ = self.cache[name]
        return value, digest

    def recheck(self):
        descriptor = _open_root(self.root)
        try:
            current = os.fstat(descriptor)
            _require((current.st_dev, current.st_ino) == self.root_identity,
                     "input-changed", "bundle root replaced during validation")
        finally:
            os.close(descriptor)
        checked = set()
        for name, (_, digest, signature) in self.cache.items():
            raw, current = self.read(_relative(name), checked=checked)
            _require(current == signature and (raw is None or hashlib.sha256(raw).hexdigest() == digest),
                     "input-changed", "input replaced or modified during validation")
            checked.add(current[:2])
        descriptor = _open_root(self.root)
        try:
            current = os.fstat(descriptor)
            _require((current.st_dev, current.st_ino) == self.root_identity,
                     "input-changed", "bundle root replaced during recheck")
        finally:
            os.close(descriptor)


def _record(value, schema, fields):
    _obj(value, schema, ('schema', 'fixture', *fields))
    _require(value['schema'] == schema and value['fixture'] is True,
             'invalid-record', f'expected synthetic fixture {schema}')
    return value


def _well(value, rows, columns):
    value = _text(value, 'well ID')
    match = re.fullmatch(r'([A-Z])([1-9][0-9]*)', value)
    _require(match is not None, 'well-identity', 'canonical well such as A1 required')
    row, column = ord(match[1]) - ord('A'), int(match[2]) - 1
    _require(row < rows and column < columns, 'well-identity', 'well outside frozen grid')
    return row, column


def _layout(value):
    _record(value, 'hts-layout-v1', ('rows', 'columns', 'assay', 'instrument', 'positive_controls',
            'negative_controls', 'solvent_controls', 'edge_rule', 'minimum_z_prime', 'minimum_ssmd',
            'maximum_drift', 'hit_threshold', 'direction', 'replicate_requirement',
            'minimum_controls', 'minimum_samples', 'baseline'))
    rows = _number(value['rows'], 'rows', 2, 26, True)
    columns = _number(value['columns'], 'columns', 2, MAX_WELLS, True)
    _require(rows * columns <= MAX_WELLS, 'input-limit', 'grid exceeds MAX_WELLS')
    for key in ('assay', 'instrument'):
        _text(value[key], key)
    _require(value['edge_rule'] in ('exclude', 'flag'), 'invalid-record', 'edge rule must be exclude or flag')
    _require(value['direction'] in ('higher', 'lower'), 'invalid-record', 'direction must be higher or lower')
    _require(value['baseline'] == 'all-samples', 'invalid-record', 'baseline must use all sample wells')
    _number(value['minimum_z_prime'], 'minimum_z_prime', -10, 1)
    _number(value['minimum_ssmd'], 'minimum_ssmd', 0)
    _number(value['maximum_drift'], 'maximum_drift', 0)
    _number(value['hit_threshold'], 'hit_threshold', 0)
    _require(value['hit_threshold'] > 0, 'invalid-record', 'hit threshold must be positive')
    _number(value['replicate_requirement'], 'replicate_requirement', 1, MAX_ROWS, True)
    minimum = _number(value['minimum_controls'], 'minimum_controls', 2, MAX_WELLS, True)
    _number(value['minimum_samples'], 'minimum_samples', 3, MAX_WELLS, True)
    used = set()
    for key in ('positive_controls', 'negative_controls', 'solvent_controls'):
        wells = _items(value[key], key, MAX_WELLS, True)
        _require(bool(wells), 'solvent-absent' if key == 'solvent_controls' else 'controls-absent',
                 'every control set must be present')
        _names(wells, key, MAX_WELLS)
        coordinates = [_well(well, rows, columns) for well in wells]
        _require(not used.intersection(wells), 'control-overlap', 'control sets must be disjoint')
        used.update(wells)
        if key != 'solvent_controls':
            _require(len(wells) >= minimum, 'insufficient-controls', 'control count below frozen minimum')
            _require(len({r for r, _ in coordinates}) >= 2 and len({c for _, c in coordinates}) >= 2,
                     'positional-confound', 'controls confined to one row or column')
    return value


def control_metrics(positive, negative, minimum=2):
    """Sample SD, signed SSMD, Z-prime and signal/background; refuse degenerate controls."""
    _number(minimum, 'minimum', 2, MAX_WELLS, True)
    for values in (positive, negative):
        _items(values, 'controls', MAX_WELLS)
        _require(len(values) >= minimum, 'insufficient-controls', 'too few control signals')
        for value in values:
            _number(value, 'signal', -MAX_NUMBER)
    means = [math.fsum(values) / len(values) for values in (positive, negative)]
    sd = [statistics.stdev(values) for values in (positive, negative)]
    _require(all(value > 0 for value in sd) and means[0] != means[1],
             'undefined-zprime', 'zero variance or equal control means cannot pass')
    _require(means[1] != 0, 'zero-background', 'signal/background denominator is zero')
    separation = means[0] - means[1]
    result = {'z_prime': 1 - 3 * math.fsum(sd) / abs(separation),
              'ssmd': separation / math.hypot(*sd), 'signal_to_background': means[0] / means[1]}
    _require(all(math.isfinite(v) for v in result.values()), 'undefined-zprime', 'non-finite control metrics')
    return result


def robust_scores(values, minimum=3):
    """Median/MAD scores using every sample well on one plate, before edge exclusion."""
    _number(minimum, 'minimum', 3, MAX_WELLS, True)
    _items(values, 'sample signals', MAX_WELLS)
    _require(len(values) >= minimum, 'insufficient-samples', 'too few sample signals')
    for value in values:
        _number(value, 'signal', -MAX_NUMBER)
    center = statistics.median(values)
    mad = statistics.median([abs(value - center) for value in values])
    _require(mad > 0, 'undefined-robust-z', 'zero MAD cannot yield hit scores')
    scores = [(value - center) / (1.4826 * mad) for value in values]
    _require(all(math.isfinite(v) for v in scores), 'undefined-robust-z', 'non-finite robust score')
    return center, mad, scores


def _inventory(value, layout):
    _record(value, 'hts-signals-v1', ('assay', 'instrument', 'plates'))
    _require(value['assay'] == layout['assay'] and value['instrument'] == layout['instrument'],
             'assay-identity', 'instrument and assay must match frozen identities')
    plates = _items(value['plates'], 'plates', MAX_PLATES)
    # Bound the aggregate before building indexes or doing any per-well computation.
    total = 0
    for plate in plates:
        _obj(plate, 'plate', ('plate_id', 'wells'))
        total += len(_items(plate['wells'], 'wells', MAX_WELLS))
        _require(total <= MAX_ROWS, 'input-limit', 'aggregate well count exceeds MAX_ROWS')
    seen_plates, seen_replicates = set(), set()
    controls = set(layout['positive_controls'] + layout['negative_controls'] + layout['solvent_controls'])
    admitted = []
    for plate in plates:
        identity = _text(plate['plate_id'], 'plate ID')
        _require(identity not in seen_plates, 'duplicate-plate', 'plate IDs must be unique')
        seen_plates.add(identity)
        wells = {}
        for item in plate['wells']:
            _obj(item, 'well', ('well_id', 'sample_id', 'replicate_id', 'value', 'observed'))
            well = _text(item['well_id'], 'well ID')
            _well(well, layout['rows'], layout['columns'])
            _require(well not in wells, 'duplicate-well', 'plate-well IDs must be unique')
            _text(item['sample_id'], 'sample ID')
            _number(item['replicate_id'], 'replicate ID', 0, MAX_ROWS, True)
            _require(_boolean(item['observed'], 'observed') and item['value'] is not None,
                     'missing-signal', 'missing signal cannot be filled or coerced to zero')
            _number(item['value'], 'signal', -MAX_NUMBER)
            if well not in controls:
                _require(item['replicate_id'] > 0, 'replicate-identity', 'sample replicates start at one')
                replicate = (item['sample_id'], item['replicate_id'])
                _require(replicate not in seen_replicates, 'replicate-identity', 'replicate identities must be unique')
                seen_replicates.add(replicate)
            wells[well] = item
        _require(controls <= wells.keys(), 'controls-absent', 'every plate must contain all frozen controls')
        _require(len(wells) == layout['rows'] * layout['columns'],
                 'incomplete-grid', 'all grid wells must be supplied; no missing well is zero-filled')
        admitted.append((identity, wells))
    return admitted, controls


def _compute(plates, controls, layout):
    qc, candidates = [], {}
    for identity, wells in plates:
        reasons = []
        metrics = dict.fromkeys(('z_prime', 'ssmd', 'signal_to_background'))
        try:
            metrics = control_metrics([wells[w]['value'] for w in layout['positive_controls']],
                                      [wells[w]['value'] for w in layout['negative_controls']],
                                      layout['minimum_controls'])
        except ValueError as error:
            code = str(error).split(':', 1)[0]
            if code not in ('undefined-zprime', 'zero-background'):
                raise
            reasons.append(code)
        if metrics['z_prime'] is not None:
            if metrics['z_prime'] < layout['minimum_z_prime']:
                reasons.append('minimum-zprime')
            if abs(metrics['ssmd']) < layout['minimum_ssmd']:
                reasons.append('minimum-ssmd')
        row_values, column_values = {}, {}
        for well in layout['negative_controls']:
            row, column = _well(well, layout['rows'], layout['columns'])
            row_values.setdefault(row, []).append(wells[well]['value'])
            column_values.setdefault(column, []).append(wells[well]['value'])
        medians = [[statistics.median(values) for values in axis.values()]
                   for axis in (row_values, column_values)]
        drift = max(max(axis) - min(axis) for axis in medians)
        samples = [item for well, item in wells.items() if well not in controls]
        center = mad = None
        scores = []
        try:
            if not samples:
                raise ValueError('insufficient-samples: plate has no sample wells')
            center, mad, scores = robust_scores([item['value'] for item in samples], layout['minimum_samples'])
        except ValueError as error:
            code = str(error).split(':', 1)[0]
            if code not in ('undefined-robust-z', 'insufficient-samples'):
                raise
            reasons.append(code)
        qc.append({'plate_id': identity, 'status': 'failed' if reasons else 'passed', **metrics,
                   'drift': drift, 'drift_flagged': drift > layout['maximum_drift'],
                   'reasons': reasons, 'median': center, 'mad': mad})
        if reasons:
            continue
        for item, score in zip(samples, scores):
            row, column = _well(item['well_id'], layout['rows'], layout['columns'])
            edge = row in (0, layout['rows'] - 1) or column in (0, layout['columns'] - 1)
            if edge and layout['edge_rule'] == 'exclude':
                continue
            passes = score >= layout['hit_threshold'] if layout['direction'] == 'higher' else score <= -layout['hit_threshold']
            if passes:
                candidates.setdefault(item['sample_id'], []).append({
                    'plate_id': identity, 'well_id': item['well_id'], 'sample_id': item['sample_id'],
                    'replicate_id': item['replicate_id'], 'robust_z': score, 'edge': edge})
    hits, replicates = [], []
    index = {identity: wells for identity, wells in plates}
    for sample, matching in sorted(candidates.items()):
        if len(matching) < layout['replicate_requirement']:
            continue
        hits.extend(matching)
        contributors = [{'plate_id': item['plate_id'], 'well_id': item['well_id']} for item in matching]
        signals = [index[item['plate_id']][item['well_id']]['value'] for item in matching]
        replicates.append({'sample_id': sample, 'agreeing_replicates': len(matching),
                           'mean_signal': math.fsum(signals) / len(signals), 'contributors': contributors})
    return {'schema': 'hts-result-v1', 'fixture': True, 'plates': qc, 'hits': hits, 'replicates': replicates}


def _same(actual, expected):
    if type(expected) is dict:
        return (type(actual) is dict and actual.keys() == expected.keys()
                and all(_same(actual[k], v) for k, v in expected.items()))
    if type(expected) is list:
        return (type(actual) is list and len(actual) == len(expected)
                and all(_same(a, b) for a, b in zip(actual, expected)))
    if type(expected) is float:
        return type(actual) in (int, float) and math.isfinite(actual) and math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-10)
    return type(actual) is type(expected) and actual == expected


def _reported(record, expected, plates, controls, layout):
    _record(record, 'hts-result-v1', ('plates', 'hits', 'replicates'))
    index = {identity: wells for identity, wells in plates}
    expected_qc = {item['plate_id']: item for item in expected['plates']}
    for item in _items(record['plates'], 'reported plates', MAX_PLATES):
        _obj(item, 'reported plate', expected['plates'][0].keys())
        identity = _text(item['plate_id'], 'plate ID')
        _require(identity in expected_qc, 'plate-identity', 'unknown reported plate')
        reference = expected_qc[identity]
        _require('undefined-zprime' not in reference['reasons'] or item['status'] == 'failed',
                 'undefined-zprime', 'zero-variance controls cannot be reported passing')
        _require(not reference['drift_flagged'] or item['drift_flagged'] is True,
                 'positional-drift', 'drift exceeding frozen limit must be flagged')
    for item in _items(record['hits'], 'reported hits', MAX_ROWS, True):
        _obj(item, 'reported hit', ('plate_id', 'well_id', 'sample_id', 'replicate_id', 'robust_z', 'edge'))
        identity, well = _text(item['plate_id'], 'plate ID'), _text(item['well_id'], 'well ID')
        _require(identity in index and well in index[identity], 'well-identity', 'unknown reported well')
        _require(well not in controls, 'control-hit', 'control wells never become hits')
        _require(expected_qc[identity]['status'] != 'failed', 'failed-plate-hit', 'failed plates contribute no hits')
        row, column = _well(well, layout['rows'], layout['columns'])
        edge = row in (0, layout['rows'] - 1) or column in (0, layout['columns'] - 1)
        _require(not edge or layout['edge_rule'] != 'exclude', 'edge-hit', 'frozen edge exclusion forbids this hit')
    for item in _items(record['replicates'], 'reported replicates', MAX_ROWS, True):
        _obj(item, 'reported replicate', ('sample_id', 'agreeing_replicates', 'mean_signal', 'contributors'))
        _text(item['sample_id'], 'sample ID')
        _number(item['agreeing_replicates'], 'agreeing replicates', 1, MAX_ROWS, True)
        for contributor in _items(item['contributors'], 'contributors', MAX_ROWS):
            _obj(contributor, 'contributor', ('plate_id', 'well_id'))
            identity = _text(contributor['plate_id'], 'plate ID')
            well = _text(contributor['well_id'], 'well ID')
            _require(identity in index and well in index[identity], 'well-identity', 'unknown replicate contributor')
            _require(expected_qc[identity]['status'] != 'failed', 'failed-plate-replicate', 'failed plate enters no replicate mean')
    _require(_same(record, expected), 'reported-result', 'reported numbers, hits or replicate agreement differ from recomputation')


def _claims(bundle, pack, result):
    claims = _items(pack['claims'], 'claims', MAX_CLAIMS, True)
    _names([_obj(claim, 'claim').get('id') for claim in claims], 'claim IDs', MAX_CLAIMS, True)
    own = list(pack['inputs'].values()) + [pack['frozen_layout']] + pack['study_outputs']
    own_paths = {item['path'] for item in own} | {bundle.entry}
    own_hashes = {item['sha256'] for item in own} | {bundle.cache[bundle.entry][1]}
    hits = {item['sample_id'] for item in result['replicates']}
    for claim in claims:
        _obj(claim, 'claim', ('id', 'kind', 'text', 'status', 'support', 'sample_id'))
        text, kind = _text(claim['text'], 'claim text'), _text(claim['kind'], 'claim kind')
        status = _text(claim['status'], 'claim status')
        sample = _text(claim['sample_id'], 'claim sample')
        _require(status in POSITIVE | {'planned', 'conflicting', 'unsupported', 'withdrawn', 'unavailable'},
                 'claim-boundary', 'unknown claim status')
        _require(kind in ('descriptive', 'associational') and OVERREACH.search(text) is None,
                 'claim-boundary', 'screening signal only; a hit is never an active compound')
        _require(status != 'unavailable' or UNAVAILABLE_POSITIVE.search(text) is None,
                 'claim-boundary', 'unavailable cannot assert positive evidence')
        support = _items(claim['support'], 'claim support', MAX_RECORDS, True)
        _require(support or status == 'unavailable', 'unavailable-evidence', 'no records means unavailable, never negative evidence')
        for identity in support:
            evidence = bundle.load(identity, 'hts-evidence-v1')
            _record(evidence, 'hts-evidence-v1', ('kind', 'result', 'origin', 'sample_id'))
            record_kind = _text(evidence['kind'], 'evidence kind')
            record_result = _text(evidence['result'], 'evidence result')
            origin = _text(evidence['origin'], 'evidence origin')
            evidence_sample = _text(evidence['sample_id'], 'evidence sample')
            _require(origin in ('study', 'external', 'independent', 'preregistered'), 'invalid-record', 'unknown origin')
            if origin != 'study':
                _require(identity['path'] not in own_paths and identity['sha256'] not in own_hashes,
                         'dependent-evidence', 'external identity aliases study input or output')
            _require('unavailable' not in (record_kind, record_result) or status == 'unavailable',
                     'unavailable-evidence', 'any unavailable citation requires unavailable status')
            if status in POSITIVE:
                _require(NON_EVIDENCE.search(record_kind + ' ' + record_result) is None
                         and record_kind == 'screening-evidence' and record_result == 'screening-signal'
                         and evidence_sample == sample, 'claim-evidence', 'approval and computed agreement are not screening evidence')
        if status in POSITIVE:
            _require(sample in hits, 'claim-evidence', 'positive screening claim requires replicate-agreed hit')
            _require(status != 'replicated', 'claim-boundary', 'one synthetic study cannot establish independent replication')
            _require(not pack['exploratory'] or status == 'suggestive', 'claim-boundary', 'exploratory claims remain suggestive')


def _analyze(bundle):
    pack, _ = bundle.snapshot(_relative(bundle.entry))
    _record(pack, 'hts-pack-v1', ('stages', 'frozen_layout', 'inputs', 'exploratory', 'claims', 'study_outputs'))
    _require(pack['stages'] == list(STAGES), 'stage-order', 'five ordered stages required')
    _boolean(pack['exploratory'], 'exploratory')
    _obj(pack['inputs'], 'inputs', ('layout', 'signals', 'reported'))
    frozen = _layout(bundle.load(pack['frozen_layout'], 'hts-layout-v1'))
    layout = _layout(bundle.load(pack['inputs']['layout'], 'hts-layout-v1'))
    _require(frozen == layout or pack['exploratory'], 'post-outcome-change', 'changed threshold or edge rule needs exploratory label')
    signals = bundle.load(pack['inputs']['signals'], 'hts-signals-v1')
    plates, controls = _inventory(signals, layout)
    result = _compute(plates, controls, layout)
    _reported(bundle.load(pack['inputs']['reported'], 'hts-result-v1'), result, plates, controls, layout)
    for identity in _items(pack['study_outputs'], 'study outputs', MAX_RECORDS, True):
        bundle.load(identity)
    _claims(bundle, pack, result)
    bundle.recheck()
    return {**result, 'stages': list(STAGES), 'evidence_level': 'screening-signal-only',
            'review': 'unavailable', 'exploratory': pack['exploratory'], 'claims': pack['claims'],
            'input_identities': [{'path': name, 'sha256': digest} for name, (_, digest, _) in bundle.cache.items()],
            'limitations': ['Synthetic fixtures only; no biological or physical validity.',
                            'Content hashes do not prove historical freezing or independence.',
                            'Conservative English claim wording gate is incomplete.',
                            'Coordinator owns rigor classification and independent science-review.']}


def validate_hts_plate_qc_pack(path: Path | str) -> dict:
    """Validate an immutable local bundle; return unreviewed JSON and write nothing."""
    _require(isinstance(path, (str, Path)), 'input-path', 'bundle must be a local text path')
    name = os.fspath(path)
    _require(0 < len(name) <= MAX_TEXT and all(ord(c) >= 32 for c in name),
             'input-path', 'bounded bundle path without control characters required')
    try:
        with _Bundle(path) as bundle:
            return _analyze(bundle)
    except (OSError, RuntimeError, OverflowError, RecursionError, UnicodeError) as error:
        raise ValueError(f'input-file: unavailable or changed bounded input ({type(error).__name__})') from error
