"""Offline admission and arithmetic QC for synthetic, already-called diploid SNP tables."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat


STAGES = ("01-freeze", "02-table-qc", "03-metrics", "04-summary", "05-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_TOTAL_NODES = 4000000
MAX_DEPTH = 64
MAX_TEXT = 8192
MAX_ITEMS = 20000
MAX_SAMPLES = 256
MAX_SITES = 10000
MAX_CELLS = 1000000
MAX_TRIOS = 256
MAX_CLAIMS = 1000
MAX_SUPPORT = 100
MAX_RECORDS = 1000
MAX_NUMBER = 1e100
POSITIVE = {"supported", "replicated", "suggestive"}
WORDING_FAMILIES = (
    "caus", "mechanis", "therap", "clinic", "efficac", "effective", "treat", "cure",
    "prevent", "recommend", "prescri", "bind", "affinit", "inhibit", "activat",
    "regulat", "driv", "induc",
)
OVERREACH = re.compile(
    r"\b(?:" + "|".join(word + r"\w*" for word in WORDING_FAMILIES)
    + r"|pathogen\w*|diagnos\w*|disease[\s-]+association|truth|physical[\s-]+validity)\b", re.I,
)
UNAVAILABLE_POSITIVE = re.compile(r"\b(?:supported|replicated|suggestive|significan\w*)\b", re.I)
NON_EVIDENCE = re.compile(r"review|approv|comput|numer|arithmet|result-v1|physical|clinic|truth", re.I)


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
    _require(type(value) is str and 0 < len(value) <= MAX_TEXT and bool(value.strip()),
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


def _json(raw, allowance=None):
    allowance = MAX_TOTAL_NODES if allowance is None else allowance
    # Upper bound on value count before json.loads allocates the tree: the root,
    # one value per comma, and the first value of every non-empty container.
    _require(1 + raw.count(b",") + sum(1 for _ in re.finditer(rb"[\[{](?=\s*[^\s\]}])", raw)) <= allowance,
             "input-limit", "too many JSON values")
    try:
        root = _obj(json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                              parse_constant=_constant, parse_int=_int,
                              parse_float=_float), "JSON root")
        pending = [(root, 0)]
        nodes = 0
        while pending:
            value, depth = pending.pop()
            nodes += 1
            _require(nodes <= allowance, "input-limit", "too many JSON values")
            if type(value) in (dict, list):
                _require(depth <= MAX_DEPTH, "invalid-json", "JSON nesting exceeds limit")
                _require(len(value) <= MAX_ITEMS, "input-limit", "too many JSON entries")
                children = value.items() if type(value) is dict else enumerate(value)
                for key, child in children:
                    if type(key) is str:
                        _text(key, "JSON key")
                    pending.append((child, depth + 1))
            elif type(value) is str:
                _require(len(value) <= MAX_TEXT, "input-limit", "JSON string exceeds limit")
        return root, nodes
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


def _directory(root):
    """Pin every ancestor; comparing only the bundle inode misses parent swaps."""
    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_DIRECTORY
    descriptor = os.open(root.anchor, flags)
    info = os.fstat(descriptor)
    chain = [(info.st_dev, info.st_ino)]
    try:
        for part in root.parts[1:]:
            before = os.lstat(part, dir_fd=descriptor)
            _require(stat.S_ISDIR(before.st_mode), 'input-root', 'bundle ancestors must be real directories')
            child = os.open(part, flags, dir_fd=descriptor)
            try:
                info = os.fstat(child)
                identity = (info.st_dev, info.st_ino)
                _require(stat.S_ISDIR(info.st_mode) and identity == (before.st_dev, before.st_ino),
                         'input-changed', 'bundle ancestor replaced during open')
            except BaseException:
                os.close(child)
                raise
            os.close(descriptor)
            descriptor = child
            chain.append(identity)
        return descriptor, tuple(chain)
    except BaseException:
        os.close(descriptor)
        raise


class _Bundle:
    def __init__(self, path):
        _require(isinstance(path, (str, os.PathLike)), 'input-path', 'bundle path must be text or path-like')
        self.path = Path(os.path.abspath(path))
        _require(all(ord(char) >= 32 for char in str(self.path)), 'input-path', 'bundle path contains control characters')
        self.root = self.path.parent
        self.descriptor, self.chain = _directory(self.root)
        self.cache = {}
        self.artifacts = {}
        self.bytes_read = self.nodes = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        os.close(self.descriptor)

    def _read(self, path, checking=False, checked=None):
        directory = os.dup(self.descriptor)
        flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
        try:
            for part in path.parts[:-1]:
                before = os.lstat(part, dir_fd=directory)
                _require(stat.S_ISDIR(before.st_mode), 'input-file', 'artifact ancestors must be real directories')
                child = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
                info = os.fstat(child)
                if (info.st_dev, info.st_ino) != (before.st_dev, before.st_ino):
                    os.close(child)
                    raise ValueError('input-changed: artifact ancestor replaced')
                os.close(directory)
                directory = child
            before = os.lstat(path.name, dir_fd=directory)
            _require(stat.S_ISREG(before.st_mode) and before.st_size <= MAX_BYTES,
                     'input-file', 'artifact must be a regular file at most 64 MiB')
            descriptor = os.open(path.name, flags, dir_fd=directory)
            with os.fdopen(descriptor, 'rb') as handle:
                info = os.fstat(handle.fileno())
                signature = _signature(info)
                _require(stat.S_ISREG(info.st_mode) and info.st_size <= MAX_BYTES
                         and signature == _signature(before), 'input-changed', 'artifact replaced during open')
                identity = signature[:2]
                cached = self.artifacts.get(identity)
                if cached:
                    _require(signature == cached[2], 'input-changed', 'cached artifact changed')
                    if not checking or identity in checked:
                        return None, signature
                limit = MAX_BYTES if checking else min(MAX_BYTES, MAX_TOTAL_BYTES - self.bytes_read)
                _require(info.st_size <= limit, 'input-limit', 'total input byte budget exceeded')
                raw = handle.read(limit + 1)
                after = os.fstat(handle.fileno())
            _require(len(raw) <= limit and len(raw) == info.st_size and signature == _signature(after),
                     'input-changed', 'artifact grew or changed during read')
            if not checking:
                self.bytes_read += len(raw)
            return raw, signature
        finally:
            os.close(directory)

    def snapshot(self, name):
        path = _relative(name)
        if name not in self.cache:
            _require(len(self.cache) < MAX_RECORDS, 'input-limit', 'too many artifact paths')
            raw, signature = self._read(path)
            identity = signature[:2]
            if raw is not None:
                value, nodes = _json(raw, MAX_TOTAL_NODES - self.nodes)
                self.nodes += nodes
                self.artifacts[identity] = (value, hashlib.sha256(raw).hexdigest(), signature)
            self.cache[name] = self.artifacts[identity]
        value, digest, _ = self.cache[name]
        return value, digest

    def load(self, identity, schema):
        _obj(identity, 'artifact identity', ('path', 'sha256'))
        _text(identity['path'], 'artifact path')
        digest = _text(identity['sha256'], 'SHA-256')
        _require(re.fullmatch(r'[0-9a-f]{64}', digest) is not None, 'input-hash', 'invalid SHA-256')
        value, actual = self.snapshot(identity['path'])
        _require(actual == digest, 'input-hash', 'artifact hash mismatch')
        _require(schema is None or value.get('schema') == schema, 'invalid-record', f'expected {schema}')
        return value

    def _check_root(self):
        current, chain = _directory(self.root)
        try:
            _require(chain == self.chain, 'input-changed', 'bundle ancestor chain replaced during validation')
        finally:
            os.close(current)

    def recheck(self):
        self._check_root()
        checked = set()
        for name, (_, digest, signature) in self.cache.items():
            raw, current = self._read(_relative(name), checking=True, checked=checked)
            _require(current == signature and (raw is None or hashlib.sha256(raw).hexdigest() == digest),
                     'input-changed', 'artifact changed during validation')
            checked.add(current[:2])
        self._check_root()


def _record(value, schema, fields):
    _obj(value, schema, ('schema', 'schema_version', 'fixture', *fields))
    _require(value['schema'] == schema and value['fixture'] is True, 'invalid-record', f'expected synthetic fixture {schema}')
    _number(value['schema_version'], 'schema_version', 1, 1, integer=True)
    return value


def _range(value, label, low=0, high=1):
    values = _items(value, label, 2)
    _require(len(values) == 2, 'invalid-record', f'{label} requires two endpoints')
    for item in values:
        _number(item, label, low, high)
    _require(values[0] <= values[1], 'invalid-record', f'{label} endpoints out of order')
    return values


def _rules(value):
    _record(value, 'callset-qc-rules-v1', ('genome_build', 'samples', 'trios', 'site_filters',
             'sample_filters', 'titv_range', 'allele_balance', 'strand_ambiguous', 'multiallelic', 'sex_check'))
    _text(value['genome_build'], 'genome build')
    samples = _items(value['samples'], 'sample sheet', MAX_SAMPLES)
    names = []
    for sample in samples:
        _obj(sample, 'sample', ('id', 'sex', 'control', 'family'))
        names.append(_text(sample['id'], 'sample id'))
        sex = _text(sample['sex'], 'declared sex')
        _require(sex in ('female', 'male', 'unknown'), 'invalid-record', 'unknown sex vocabulary')
        _boolean(sample['control'], 'control')
        _text(sample['family'], 'family declaration')
    _require(len(set(names)) == len(names), 'sample-identity', 'sample IDs must be unique')
    by_id = {sample['id']: sample for sample in samples}
    trios = _items(value['trios'], 'trios', MAX_TRIOS, empty=True)
    trio_ids = []
    for trio in trios:
        _obj(trio, 'trio', ('id', 'father', 'mother', 'child'))
        trio_ids.append(_text(trio['id'], 'trio id'))
        members = [_text(trio[key], key) for key in ('father', 'mother', 'child')]
        _require(len(set(members)) == 3 and all(member in by_id for member in members),
                 'trio-identity', 'three distinct declared sample IDs required')
        families = {by_id[member]['family'] for member in members}
        _require(len(families) == 1 and 'unrelated' not in families, 'trio-identity', 'trio must share a declared family')
    _require(len(set(trio_ids)) == len(trio_ids), 'trio-identity', 'trio IDs must be unique')
    filters = _obj(value['site_filters'], 'site filters', ('minimum_quality', 'minimum_depth', 'maximum_missingness',
                   'hwe_p_cutoff', 'hwe_scope', 'minimum_controls'))
    for key in ('minimum_quality', 'minimum_depth'):
        _number(filters[key], key)
    for key in ('maximum_missingness', 'hwe_p_cutoff'):
        _number(filters[key], key, 0, 1)
    _require(filters['hwe_scope'] == 'controls-only', 'hwe-controls-only', 'HWE must use declared controls only')
    _number(filters['minimum_controls'], 'minimum_controls', 2, MAX_SAMPLES, integer=True)
    filters = _obj(value['sample_filters'], 'sample filters')
    _require('heterozygosity_range' in filters, 'unfrozen-heterozygosity', 'sample removal requires a frozen heterozygosity range')
    _obj(filters, 'sample filters', ('minimum_call_rate', 'heterozygosity_range'))
    _number(filters['minimum_call_rate'], 'minimum_call_rate', 0, 1)
    _range(filters['heterozygosity_range'], 'heterozygosity range')
    _range(value['titv_range'], 'Ti/Tv range', 0, MAX_NUMBER)
    _range(value['allele_balance'], 'allele balance')
    _require(value['strand_ambiguous'] in ('retain-labelled', 'exclude') and value['multiallelic'] == 'refuse',
             'allele-handling', 'explicit strand-ambiguous handling and multiallelic refusal required')
    sex = _obj(value['sex_check'], 'sex check', ('enabled', 'female_minimum', 'male_maximum', 'minimum_sites'))
    _boolean(sex['enabled'], 'sex check enabled')
    _number(sex['female_minimum'], 'female_minimum', 0, 1)
    _number(sex['male_maximum'], 'male_maximum', 0, 1)
    _require(sex['male_maximum'] < sex['female_minimum'], 'invalid-record', 'sex check ranges must be disjoint')
    _number(sex['minimum_sites'], 'minimum_sites', 1, MAX_SITES, integer=True)
    return value


def hardy_weinberg_exact(hom_ref, het, hom_alt, minimum=2):
    """Two-sided conditional enumeration, summing tables no likelier than observed."""
    _number(minimum, 'minimum controls', 2, MAX_SAMPLES, integer=True)
    for count in (hom_ref, het, hom_alt):
        _number(count, 'genotype count', 0, MAX_SAMPLES, integer=True)
    n = hom_ref + het + hom_alt
    _require(minimum <= n <= MAX_SAMPLES, 'hwe-unavailable', 'insufficient or excessive controls')
    rare = min(2 * hom_alt + het, 2 * hom_ref + het)
    _require(rare > 0, 'hwe-unavailable', 'monomorphic control genotypes')
    tables = []
    observed = None
    for heterozygotes in range(rare % 2, rare + 1, 2):
        minor = (rare - heterozygotes) // 2
        major = n - minor - heterozygotes
        weight = heterozygotes * math.log(2) - math.lgamma(minor + 1) - math.lgamma(major + 1) - math.lgamma(heterozygotes + 1)
        tables.append(weight)
        if heterozygotes == het:
            observed = weight
    maximum = max(tables)
    denominator = math.fsum(math.exp(weight - maximum) for weight in tables)
    numerator = math.fsum(math.exp(weight - maximum) for weight in tables if weight <= observed + 1e-12)
    return min(1.0, numerator / denominator)


def _table(table, rules):
    _record(table, 'callset-qc-table-v1', ('genome_build', 'samples', 'sites'))
    _require(table['genome_build'] == rules['genome_build'], 'build-mismatch', 'genome build differs from frozen rules')
    names = _names(table['samples'], 'table samples', MAX_SAMPLES)
    _require(names == [sample['id'] for sample in rules['samples']], 'sample-identity', 'table order must match frozen sample sheet')
    sites = _items(table['sites'], 'sites', MAX_SITES)
    _require(len(sites) * len(names) <= MAX_CELLS, 'input-limit', 'genotype cell budget exceeded')
    previous = None
    chromosomes = {str(i): i for i in range(1, 23)} | {'X': 23}
    genotypes = ('0/0', '0/1', '1/1', './.')
    ids = set()
    for site in sites:
        _obj(site, 'site', ('id', 'chrom', 'position', 'ref', 'alt', 'quality', 'calls'))
        identifier = _text(site['id'], 'site id')
        _require(identifier not in ids, 'site-identity', 'site IDs must be unique')
        ids.add(identifier)
        chrom = _text(site['chrom'], 'chromosome')
        _require(chrom in chromosomes, 'site-identity', 'only autosomes and X are supported')
        _number(site['position'], 'position', 1, 2**31 - 1, integer=True)
        key = (chromosomes[chrom], site['position'])
        _require(previous is None or previous < key, 'site-identity', 'sites must be unique and genome sorted')
        previous = key
        ref, alt = site['ref'], site['alt']
        _require(type(ref) is str and type(alt) is str and ref in ('A', 'C', 'G', 'T')
                 and alt in ('A', 'C', 'G', 'T') and ref != alt, 'allele-handling', 'biallelic single-base alleles required')
        _number(site['quality'], 'site quality')
        calls = _items(site['calls'], 'site calls', MAX_SAMPLES)
        _require(len(calls) == len(names), 'sample-identity', 'one call per declared sample required')
        for call in calls:
            _obj(call, 'call', ('gt', 'depth', 'quality', 'alt_depth'))
            gt = _text(call['gt'], 'genotype')
            _require(gt in genotypes, 'genotype-vocabulary', 'diploid unphased genotypes or ./. required')
            for field in ('depth', 'quality', 'alt_depth'):
                _number(call[field], field)
            _require(call['alt_depth'] <= call['depth'], 'invalid-record', 'alternate depth exceeds total depth')
    return names, sites


def _ratio(transitions, transversions, interval):
    value = transitions / transversions if transversions else None
    return {'transitions': transitions, 'transversions': transversions, 'value': value,
            'status': 'unavailable' if value is None else ('within-range' if interval[0] <= value <= interval[1] else 'outside-range')}


def compute_callset_qc(table, rules):
    """Recompute all exclusions and controls without mutating the synthetic inputs."""
    rules = _rules(rules)
    names, sites = _table(table, rules)
    controls = [i for i, sample in enumerate(rules['samples']) if sample['control']]
    indices = {name: i for i, name in enumerate(names)}
    filters = rules['site_filters']
    rows, kept, removed = [], [], []
    for site in sites:
        observed = [call for call in site['calls'] if call['gt'] != './.']
        missingness = (len(names) - len(observed)) / len(names)
        reasons = []
        if site['quality'] < filters['minimum_quality']:
            reasons.append('minimum-quality')
        if any(call['depth'] < filters['minimum_depth'] for call in observed):
            reasons.append('minimum-depth')
        if missingness > filters['maximum_missingness']:
            reasons.append('maximum-missingness')
        if any(call['gt'] == '0/1' and (call['depth'] == 0 or not rules['allele_balance'][0] <= call['alt_depth'] / call['depth'] <= rules['allele_balance'][1]) for call in observed):
            reasons.append('allele-balance')
        if rules['strand_ambiguous'] == 'exclude' and {site['ref'], site['alt']} in ({'A', 'T'}, {'C', 'G'}):
            reasons.append('strand-ambiguous')
        counts = [0, 0, 0]
        for index in controls:
            gt = site['calls'][index]['gt']
            if gt != './.':
                counts[{'0/0': 0, '0/1': 1, '1/1': 2}[gt]] += 1
        hwe = {'status': 'unavailable', 'p_value': None, 'reason': 'non-autosomal', 'controls_called': sum(counts)}
        if site['chrom'] != 'X':
            try:
                p_value = hardy_weinberg_exact(*counts, minimum=filters['minimum_controls'])
                hwe.update(status='computed', p_value=p_value, reason=None)
                if p_value < filters['hwe_p_cutoff']:
                    reasons.append('hwe-controls')
            except ValueError as error:
                if not str(error).startswith('hwe-unavailable:'):
                    raise
                hwe['reason'] = str(error)
        rows.append({'id': site['id'], 'missingness': missingness, 'hwe': hwe})
        if reasons:
            removed.append({'id': site['id'], 'reasons': reasons})
        else:
            kept.append(site)
    _require(bool(kept), 'empty-retained-sites', 'frozen filters removed every site')
    sample_rows, removed_samples = [], []
    transitions = {('A', 'G'), ('G', 'A'), ('C', 'T'), ('T', 'C')}
    for index, sample in enumerate(rules['samples']):
        calls = [site['calls'][index] for site in kept]
        called = sum(call['gt'] != './.' for call in calls)
        het = sum(call['gt'] == '0/1' for call in calls)
        call_rate = called / len(kept)
        heterozygosity = het / called if called else None
        ti = tv = 0
        for site, call in zip(kept, calls):
            if call['gt'] in ('0/1', '1/1'):
                if (site['ref'], site['alt']) in transitions:
                    ti += 1
                else:
                    tv += 1
        reasons = []
        if call_rate < rules['sample_filters']['minimum_call_rate']:
            reasons.append('minimum-call-rate')
        if heterozygosity is None:
            reasons.append('heterozygosity-unavailable')
        elif not rules['sample_filters']['heterozygosity_range'][0] <= heterozygosity <= rules['sample_filters']['heterozygosity_range'][1]:
            reasons.append('heterozygosity-range')
        if reasons:
            removed_samples.append({'id': sample['id'], 'reasons': reasons})
        sample_rows.append({'id': sample['id'], 'called': called, 'heterozygous': het,
                            'call_rate': call_rate, 'heterozygosity': heterozygosity, 'titv': _ratio(ti, tv, rules['titv_range'])})
    mendelian = []
    alleles = {'0/0': (0, 0), '0/1': (0, 1), '1/1': (1, 1)}
    for trio in rules['trios']:
        errors, unavailable, informative = [], [], 0
        for site in sites:
            if site['chrom'] == 'X':
                continue
            calls = [site['calls'][indices[trio[key]]]['gt'] for key in ('father', 'mother', 'child')]
            if './.' in calls:
                unavailable.append(site['id'])
                continue
            informative += 1
            father, mother, child = (alleles[gt] for gt in calls)
            possible = {tuple(sorted((first, second))) for first in father for second in mother}
            if child not in possible:
                errors.append(site['id'])
        mendelian.append({'id': trio['id'], 'errors': errors, 'error_count': len(errors),
                          'informative': informative, 'unavailable_sites': unavailable})
    sex_checks = []
    sex_rule = rules['sex_check']
    for index, sample in enumerate(rules['samples']):
        calls = [site['calls'][index]['gt'] for site in sites if site['chrom'] == 'X' and site['calls'][index]['gt'] != './.']
        heterozygosity = sum(gt == '0/1' for gt in calls) / len(calls) if calls else None
        status = 'unavailable'
        if sex_rule['enabled'] and sample['sex'] != 'unknown' and len(calls) >= sex_rule['minimum_sites']:
            consistent = heterozygosity <= sex_rule['male_maximum'] if sample['sex'] == 'male' else heterozygosity >= sex_rule['female_minimum']
            status = 'consistent' if consistent else 'contradiction'
        sex_checks.append({'id': sample['id'], 'x_called': len(calls), 'x_heterozygosity': heterozygosity, 'status': status})
    ti = sum((site['ref'], site['alt']) in transitions for site in kept)
    titv = _ratio(ti, len(kept) - ti, rules['titv_range'])
    failed = ([f"mendelian:{row['id']}" for row in mendelian if row['error_count']]
              + [f"sex-check:{row['id']}" for row in sex_checks if row['status'] == 'contradiction']
              + (['titv-outside-range'] if titv['status'] == 'outside-range' else []))
    removed_sample_ids = {row['id'] for row in removed_samples}
    return {'schema': 'callset-qc-report-v1', 'schema_version': 1, 'fixture': True,
            'hwe_scope': 'controls-only', 'missing_rule': 'unavailable', 'sites': rows, 'samples': sample_rows,
            'removed_sites': removed, 'removed_samples': removed_samples, 'mendelian': mendelian,
            'sex_checks': sex_checks, 'titv': titv, 'failed_controls': failed,
            'retained_sites': [site['id'] for site in kept],
            'retained_samples': [sample['id'] for sample in rules['samples'] if sample['id'] not in removed_sample_ids]}


def _same(actual, expected):
    if type(expected) is float:
        return type(actual) in (int, float) and math.isfinite(actual) and math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-14)
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return actual.keys() == expected.keys() and all(_same(actual[key], value) for key, value in expected.items())
    if type(expected) is list:
        return len(actual) == len(expected) and all(_same(first, second) for first, second in zip(actual, expected))
    return actual == expected


def _report(actual, computed):
    _record(actual, 'callset-qc-report-v1', tuple(key for key in computed if key not in ('schema', 'schema_version', 'fixture')))
    removed = _items(actual['removed_sites'], 'removed sites', MAX_SITES, empty=True)
    for row in removed:
        _obj(row, 'removed site', ('id', 'reasons'))
        _text(row['id'], 'removed site id')
        reasons = row['reasons']
        _require(type(reasons) is list and bool(reasons) and all(type(reason) is str and reason.strip() for reason in reasons),
                 'unnamed-site-filter', 'every removed site requires a named frozen reason')
    _require(_same(actual['removed_sites'], computed['removed_sites']), 'site-filter-mismatch', 'removed sites and reasons must match frozen rules')
    _require(actual['hwe_scope'] == 'controls-only', 'hwe-controls-only', 'HWE report must use declared controls only')
    _require(actual['missing_rule'] == 'unavailable', 'unavailable-as-reference', 'unavailable genotypes cannot count as reference')
    _require(_same(actual['mendelian'], computed['mendelian']), 'mendelian-ignored', 'all trio errors and unavailable sites must be preserved')
    _require(_same(actual['sex_checks'], computed['sex_checks']), 'sex-contradiction-ignored', 'X heterozygosity contradictions must be preserved')
    _require(_same(actual, computed), 'qc-report-mismatch', 'QC metrics, exclusions and failed controls differ from recomputation')


def _time(value):
    try:
        result = datetime.fromisoformat(_text(value, 'timestamp').replace('Z', '+00:00'))
        _require(result.tzinfo is not None, 'rule-freeze', 'timestamps require a timezone')
        return result
    except (ValueError, OverflowError) as error:
        raise ValueError('rule-freeze: valid timezone-aware timestamps required') from error


def _claims(bundle, claims, own):
    _items(claims, 'claims', MAX_CLAIMS, empty=True)
    ids = []
    statuses = POSITIVE | {'planned', 'conflicting', 'unsupported', 'withdrawn', 'unavailable'}
    own_paths = {item['path'] for item in own}
    own_hashes = {item['sha256'] for item in own}
    for claim in claims:
        _obj(claim, 'claim', ('id', 'kind', 'status', 'text', 'support'))
        ids.append(_text(claim['id'], 'claim id'))
        kind = _text(claim['kind'], 'claim kind')
        status = _text(claim['status'], 'claim status')
        text = _text(claim['text'], 'claim text')
        _require(kind in ('descriptive', 'associational', 'causal', 'confirmatory') and status in statuses,
                 'invalid-record', 'unknown claim kind or status')
        _require(kind != 'causal' and OVERREACH.search(text) is None, 'claim-boundary', 'QC arithmetic cannot support interpretation beyond descriptive evidence')
        support = _items(claim['support'], 'claim support', MAX_SUPPORT, empty=True)
        _require(bool(support) or status == 'unavailable', 'empty-evidence', 'claims without evidence must be unavailable')
        for identity in support:
            _obj(identity, 'claim support', ('origin', 'path', 'sha256'))
            origin = _text(identity['origin'], 'support origin')
            _require(origin in ('study', 'external', 'independent', 'preregistered'), 'invalid-record', 'unknown support origin')
            record = bundle.load({key: identity[key] for key in ('path', 'sha256')}, 'callset-qc-evidence-v1')
            _record(record, 'callset-qc-evidence-v1', ('id', 'kind', 'result', 'source'))
            for key in ('id', 'kind', 'result'):
                _text(record[key], key)
            source = _obj(record['source'], 'evidence source', ('path', 'sha256'))
            source_record = bundle.load(source, None)
            for field in ('schema', 'kind', 'result'):
                if field in source_record:
                    _text(source_record[field], 'source ' + field)
            if 'schema_version' in source_record:
                _number(source_record['schema_version'], 'source schema_version', 1, 1, integer=True)
            if origin != 'study':
                _require(identity['path'] not in own_paths and identity['sha256'] not in own_hashes
                         and source['path'] not in own_paths and source['sha256'] not in own_hashes,
                         'self-evidence', 'independence labels cannot refer to study outputs')
            unavailable = any(item.get(key) == 'unavailable' for item in (record, source_record) for key in ('kind', 'result'))
            _require(not unavailable or status == 'unavailable', 'unavailable-evidence', 'any unavailable source requires unavailable claim status')
            computed_source = source_record.get('schema') in ('callset-qc-report-v1', 'callset-qc-result-v1')
            _require(status not in POSITIVE or (not computed_source and not any(
                NON_EVIDENCE.search(item.get(key, '')) for item in (record, source_record) for key in ('kind', 'result'))),
                     'non-evidence-support', 'positive claims cannot cite review approval or computed records')
        _require(status != 'replicated', 'replication-unavailable', 'one synthetic fixture cannot establish independent replication')
        _require(status != 'unavailable' or UNAVAILABLE_POSITIVE.search(text) is None,
                 'unavailable-positive', 'unavailable claims cannot assert positive evidence')
    _require(len(set(ids)) == len(ids), 'invalid-record', 'claim IDs must be unique')


def validate_callset_qc_pack(path):
    """Validate one read-only bundle and return unreviewed, synthetic arithmetic."""
    try:
        with _Bundle(path) as bundle:
            pack, digest = bundle.snapshot(bundle.path.name)
            _record(pack, 'callset-qc-pack-v1', ('stages', 'mode', 'freeze', 'inputs', 'claims'))
            _require(pack['stages'] == list(STAGES), 'stage-order', 'exactly five ordered stage IDs required')
            mode = _text(pack['mode'], 'mode')
            _require(mode in ('frozen', 'exploratory'), 'invalid-record', 'mode must be frozen or exploratory')
            inputs = _obj(pack['inputs'], 'inputs', ('rules', 'table', 'qc'))
            freeze = _obj(pack['freeze'], 'freeze', ('rules', 'before_genotypes', 'frozen_at', 'genotypes_read_at'))
            _rules(bundle.load(freeze['rules'], 'callset-qc-rules-v1'))
            _require(freeze['before_genotypes'] is True and _time(freeze['frozen_at']) < _time(freeze['genotypes_read_at']),
                     'rule-freeze', 'rules must be hashed before genotypes are read')
            rules = _rules(bundle.load(inputs['rules'], 'callset-qc-rules-v1'))
            _require(mode == 'exploratory' or freeze['rules']['sha256'] == inputs['rules']['sha256'],
                     'post-outcome-filters', 'changed rules require an exploratory label')
            table = bundle.load(inputs['table'], 'callset-qc-table-v1')
            computed = compute_callset_qc(table, rules)
            actual = bundle.load(inputs['qc'], 'callset-qc-report-v1')
            _report(actual, computed)
            own = list(inputs.values()) + [freeze['rules'], {'path': bundle.path.name, 'sha256': digest}]
            _claims(bundle, pack['claims'], own)
            bundle.recheck()
            return {'schema': 'callset-qc-result-v1', 'schema_version': 1, 'fixture': True,
                    'status': 'checked', 'review': 'unavailable', 'evidence_boundary': 'synthetic-arithmetic-only',
                    'mode': mode, 'stages': list(STAGES), 'qc': computed,
                    'inputs': [{'path': name, 'sha256': item[1]} for name, item in bundle.cache.items()]}
    except (OSError, UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError('input-file: bounded ordinary bundle files required') from error
