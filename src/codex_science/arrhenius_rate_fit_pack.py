"""Read-only synthetic Arrhenius admission and replicate-collapsed reference arithmetic."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat


STAGES = ("01-rule-freeze", "02-table-qc", "03-fit", "04-summary", "05-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_ROWS = 10000
MAX_TEMPERATURES = 128
MAX_NODES = 4000000
MAX_ITERATIONS = 10000
QUANTILE_STEPS = 96
MAX_RECORDS = 128
MAX_STRING = 4096
MAX_DEPTH = 32
MAX_NUMBER = 1e100
POSITIVE = {"supported", "replicated", "suggestive"}
STATUSES = POSITIVE | {"planned", "conflicting", "unsupported", "withdrawn", "unavailable"}
WORDING_FAMILIES = (
    "caus*, mechanis*, therap*, clinic*, efficac*, effective*, treat*, cure*, prevent*, "
    "recommend*, prescri*, bind*, affinit*, inhibit*, activat*, regulat*, "
    "drive/drives/driv*, induc*"
)
OVERREACH = re.compile(
    r"\b(?:caus\w*|mechanis\w*|therap\w*|clinic\w*|efficac\w*|effective\w*|"
    r"treat\w*|cure\w*|prevent\w*|recommend\w*|prescri\w*|bind\w*|affinit\w*|"
    r"inhibit\w*|activat\w*|regulat\w*|driv\w*|induc\w*|truth|"
    r"physical[\s-]+validity|patient[\s-]+benefit\w*|shelf[\s-]*life|"
    r"process[\s-]+safety|reaction[\s-]+order|safe\w*)\b", re.I,
)
ASSERTION = re.compile(r"\b(?:supported|replicated|suggestive|significan\w*)\b", re.I)
NON_EVIDENCE = re.compile(r"review|approv|comput|numer|agreement|truth|physical|clinic", re.I)


def _require(condition, code, message):
    if not condition:
        raise ValueError(f"{code}: {message}")


def _text(value, label):
    _require(type(value) is str and 0 < len(value) <= MAX_STRING and bool(value.strip())
             and not any(0xD800 <= ord(c) <= 0xDFFF for c in value),
             "invalid-record", f"{label} must be bounded nonempty text")
    return value


def _number(value, label, low=0, high=MAX_NUMBER, integer=False):
    valid = type(value) is int if integer else type(value) in (int, float)
    _require(valid and -MAX_NUMBER <= value <= MAX_NUMBER and math.isfinite(value)
             and low <= value <= high, "invalid-record", f"{label} has invalid numeric type or range")
    return value


def _boolean(value, label):
    _require(type(value) is bool, "invalid-record", f"{label} must be boolean")
    return value


def _fields(value, fields, label):
    expected = fields.split() if type(fields) is str else fields
    _require(type(value) is dict and set(value) == set(expected),
             "invalid-record", f"{label} fields differ from its pack-local schema")
    return value


def _list(value, label, limit, empty=False):
    _require(type(value) is list, "invalid-record", f"{label} must be a list")
    _require(len(value) <= limit, "input-limit", f"{label} exceeds its declared count limit")
    _require(empty or len(value) > 0, "invalid-record", f"{label} must not be empty")
    return value


def _names(value, label, limit, empty=False):
    value = _list(value, label, limit, empty)
    for item in value:
        _text(item, label)
    _require(len(set(value)) == len(value), "invalid-record", f"duplicate {label}")
    return value


def _record(value, schema, fields):
    _fields(value, "schema fixture " + fields, schema)
    _require(value["schema"] == schema, "invalid-record", "wrong pack-local schema")
    _require(value["fixture"] == "synthetic fixture", "invalid-record", "fixture label required")
    return value


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "invalid-json", "duplicate JSON key")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("invalid-json: non-finite JSON number")


def _int(value):
    _require(len(value.lstrip("-")) <= 101, "invalid-json", "huge JSON integer")
    number = int(value)
    _require(abs(number) <= MAX_NUMBER, "invalid-json", "huge JSON integer")
    return number


def _float(value):
    number = float(value)
    _require(math.isfinite(number) and abs(number) <= MAX_NUMBER,
             "invalid-json", "non-finite or huge JSON number")
    return number


def _json(raw, allowance=None):
    allowance = MAX_NODES if allowance is None else allowance
    _require(1 + raw.count(b",") + sum(1 for _ in re.finditer(rb"[\[{](?=\s*[^\s\]}])", raw)) <= allowance,
             "input-limit", "bundle JSON value allowance exceeded before parsing")
    try:
        root = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=_constant, parse_int=_int, parse_float=_float)
        _require(type(root) is dict, "invalid-json", "JSON root must be an object")
        pending = [(root, 0)]
        nodes = 0
        while pending:
            value, depth = pending.pop()
            nodes += 1
            _require(nodes <= allowance, "input-limit", "bundle JSON value allowance exceeded")
            _require(depth <= MAX_DEPTH, "invalid-json", "JSON nesting limit exceeded")
            if type(value) in (dict, list):
                _require(len(value) <= MAX_ROWS, "input-limit", "JSON container exceeds limit")
                children = value.items() if type(value) is dict else enumerate(value)
                for key, child in children:
                    if type(key) is str:
                        _text(key, "JSON key")
                    pending.append((child, depth + 1))
            elif type(value) is str:
                _text(value, "JSON string")
        return root, nodes
    except (UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError("invalid-json: bounded finite UTF-8 JSON required") from error
    except json.JSONDecodeError as error:
        raise ValueError("invalid-json: malformed JSON") from error


def _relative(value):
    value = _text(value, "artifact path")
    path = PurePosixPath(value)
    _require(not path.is_absolute() and ".." not in path.parts and "\\" not in value
             and path.as_posix() == value and value != "." and ":" not in value
             and all(ord(c) >= 32 for c in value),
             "input-path", "canonical bundle-relative path required")
    return path


def _signature(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _open_root(root):
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
    descriptor = os.open(root.anchor, flags)
    try:
        opened = os.fstat(descriptor)
        identities = [(opened.st_dev, opened.st_ino)]
        for part in root.parts[1:]:
            before = os.lstat(part, dir_fd=descriptor)
            _require(stat.S_ISDIR(before.st_mode), "input-root", "root ancestors must be real directories")
            child = os.open(part, flags, dir_fd=descriptor)
            try:
                opened = os.fstat(child)
                _require(stat.S_ISDIR(opened.st_mode)
                         and (before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino),
                         "input-root", "root ancestor changed during pinning")
            except BaseException:
                os.close(child)
                raise
            os.close(descriptor)
            descriptor = child
            identities.append((opened.st_dev, opened.st_ino))
        return descriptor, identities
    except BaseException:
        os.close(descriptor)
        raise


class _Bundle:
    def __init__(self, root):
        self.root = root
        self.fd = None
        self.snapshots = {}
        self.cache = {}
        self.parsed = {}
        self.nodes = 0
        self.total_bytes = 0
        self.rechecked = None
        try:
            self.fd, self.identities = _open_root(root)
        except (OSError, ValueError) as error:
            self.close()
            if isinstance(error, ValueError):
                raise
            raise ValueError("input-root: cannot pin bundle directory") from error

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def _read(self, name):
        relative = _relative(name)
        opened_dirs = []
        try:
            directory = self.fd
            flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
            for part in relative.parts[:-1]:
                info = os.lstat(part, dir_fd=directory)
                _require(stat.S_ISDIR(info.st_mode), "input-file", "symlinked directory refused")
                directory = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
                opened_dirs.append(directory)
                actual = os.fstat(directory)
                _require((actual.st_dev, actual.st_ino) == (info.st_dev, info.st_ino),
                         "input-file", "artifact directory replaced")
            before = os.lstat(relative.name, dir_fd=directory)
            _require(stat.S_ISREG(before.st_mode) and before.st_size <= MAX_BYTES,
                     "input-file", "regular input at most 64 MiB required")
            descriptor = os.open(relative.name, flags, dir_fd=directory)
            with os.fdopen(descriptor, "rb") as handle:
                actual = os.fstat(handle.fileno())
                _require(stat.S_ISREG(actual.st_mode) and actual.st_size <= MAX_BYTES
                         and _signature(before) == _signature(actual),
                         "input-file", "input changed before descriptor validation")
                identity = actual.st_dev, actual.st_ino
                signature = _signature(actual)
                if self.rechecked is not None:
                    _require(signature == self.snapshots[name][1],
                             "input-changed", "input replaced during validation")
                cached = self.cache.get(identity)
                if cached is not None:
                    _require(signature == cached[1], "input-changed", "cached input changed")
                    if self.rechecked is None or identity in self.rechecked:
                        return cached[0], signature
                if self.rechecked is None:
                    _require(self.total_bytes + actual.st_size <= MAX_TOTAL_BYTES,
                             "input-limit", "aggregate artifact bytes exceed 256 MiB")
                raw = handle.read(actual.st_size + 1)
                after = os.fstat(handle.fileno())
            _require(len(raw) <= MAX_BYTES and len(raw) == actual.st_size
                     and _signature(actual) == _signature(after),
                     "input-file", "input grew or changed during bounded read")
            return raw, _signature(after)
        except (OSError, UnicodeError) as error:
            raise ValueError("input-file: unavailable input or symlinked component") from error
        finally:
            for descriptor in reversed(opened_dirs):
                os.close(descriptor)

    def load(self, name, digest=None, parse=True):
        _relative(name)
        if name not in self.snapshots:
            raw, signature = self._read(name)
            identity = signature[:2]
            if identity not in self.cache:
                self.cache[identity] = (raw, signature, hashlib.sha256(raw).hexdigest())
                self.total_bytes += len(raw)
            self.snapshots[name] = self.cache[identity]
        raw, _, actual = self.snapshots[name]
        if digest is not None:
            _text(digest, "sha256")
            _require(re.fullmatch(r"[0-9a-f]{64}", digest) is not None and digest == actual,
                     "input-hash", "artifact hash differs from parsed bytes")
        if not parse:
            return actual
        identity = self.snapshots[name][1][:2]
        if identity not in self.parsed:
            record, nodes = _json(raw, MAX_NODES - self.nodes)
            self.nodes += nodes
            self.parsed[identity] = record
        return self.parsed[identity]

    def artifact(self, descriptor, parse=True):
        _fields(descriptor, "path sha256", "artifact identity")
        _require(type(descriptor["sha256"]) is str
                 and re.fullmatch(r"[0-9a-f]{64}", descriptor["sha256"]) is not None,
                 "input-hash", "artifact requires a lowercase 64-hex SHA-256")
        return self.load(descriptor["path"], descriptor["sha256"], parse)

    def _check_root(self):
        descriptor, identities = _open_root(self.root)
        try:
            _require(identities == self.identities, "input-root", "bundle root replaced")
        finally:
            os.close(descriptor)

    def finish(self):
        try:
            self._check_root()
            self.rechecked = set()
            for name, (_, signature, digest) in self.snapshots.items():
                raw, current = self._read(name)
                _require(current == signature and hashlib.sha256(raw).hexdigest() == digest,
                         "input-changed", "input replaced during validation")
                self.rechecked.add(current[:2])
            self._check_root()
        except OSError as error:
            raise ValueError("input-root: root unavailable at final recheck") from error
        finally:
            self.rechecked = None


GAS_CONSTANT = 8.31446261815324
WEIGHTINGS = {'ordinary-least-squares', 'replicate-variance'}


def _beta_fraction(a, b, x):
    """Lentz continued fraction for the regularized incomplete beta integral."""
    tiny = 1e-300
    c = 1.0
    d = 1 - (a + b) * x / (a + 1)
    d = 1 / (d if abs(d) >= tiny else math.copysign(tiny, d))
    result = d
    for step in range(1, MAX_ITERATIONS + 1):
        for numerator in (step * (b - step) * x / ((a + 2 * step - 1) * (a + 2 * step)),
                          -(a + step) * (a + b + step) * x / ((a + 2 * step) * (a + 2 * step + 1))):
            d = 1 + numerator * d
            c = 1 + numerator / c
            d = 1 / (d if abs(d) >= tiny else math.copysign(tiny, d))
            c = c if abs(c) >= tiny else math.copysign(tiny, c)
            delta = d * c
            result *= delta
        if abs(delta - 1) <= 1e-14:
            return result
    raise ValueError('interval-convergence: beta fraction did not converge')


def _beta(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    factor = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                      + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1) / (a + b + 2):
        result = factor * _beta_fraction(a, b, x) / a
    else:
        result = 1 - factor * _beta_fraction(b, a, 1 - x) / b
    _require(math.isfinite(result), 'interval-convergence', 'non-finite beta integral')
    return min(1.0, max(0.0, result))


def student_t_critical(df, level=0.95):
    """Positive equal-tail Student t critical value, using bounded inversion."""
    _number(df, 'degrees of freedom', 1, MAX_ROWS, True)
    _number(level, 'interval level', 0.5, 0.999)
    low, high = 0.0, 1000.0
    target = 1 - level
    _require(_beta(df / 2, .5, df / (df + high * high)) <= target,
             'interval-convergence', 't critical value exceeds bracket')
    for _ in range(QUANTILE_STEPS):
        middle = (low + high) / 2
        if _beta(df / 2, .5, df / (df + middle * middle)) > target:
            low = middle
        else:
            high = middle
    _require(high - low <= high * 1e-12, 'interval-convergence', 't inversion did not converge')
    return (low + high) / 2


def _weighting(value):
    value = _text(value, 'weighting')
    _require(value in WEIGHTINGS, 'weighting-rule', 'unknown log-rate weighting')
    return value


def _rules(value):
    _record(value, 'arr-rules-v1', 'temperature_unit rate_unit energy_unit gas_constant gas_constant_unit '
            'runs replicate_rule weighting minimum_temperatures minimum_span_kelvin '
            'prediction_temperature_kelvin extrapolation interval_level lack_of_fit_alpha')
    _require(value['temperature_unit'] == 'K', 'temperature-unit', 'positive kelvin temperatures required')
    _text(value['rate_unit'], 'rate unit')
    energy = _text(value['energy_unit'], 'energy unit')
    _require(energy in {'J/mol', 'kJ/mol'}, 'gas-constant-units', 'energy unit must be J/mol or kJ/mol')
    unit = 'J/(mol K)' if energy == 'J/mol' else 'kJ/(mol K)'
    expected = GAS_CONSTANT if energy == 'J/mol' else GAS_CONSTANT / 1000
    _require(value['gas_constant_unit'] == unit, 'gas-constant-units', 'gas constant and energy units differ')
    _number(value['gas_constant'], 'gas constant', 1e-6, 100)
    _require(math.isclose(value['gas_constant'], expected, rel_tol=1e-12, abs_tol=0),
             'gas-constant-value', 'gas constant differs from the fixed SI value')
    _require(value['replicate_rule'] == 'mean-log-within-temperature',
             'replicate-rule', 'replicates must collapse by mean log rate at each temperature')
    _weighting(value['weighting'])
    _number(value['minimum_temperatures'], 'minimum distinct temperatures', 4, MAX_TEMPERATURES, True)
    _number(value['minimum_span_kelvin'], 'minimum temperature span', 1e-6, 1e6)
    _number(value['prediction_temperature_kelvin'], 'prediction temperature', 1e-6, 1e6)
    _require(value['extrapolation'] == 'forbidden', 'extrapolation', 'extrapolation is forbidden')
    _number(value['interval_level'], 'interval level', 0.5, 0.999)
    _number(value['lack_of_fit_alpha'], 'lack-of-fit alpha', .001, .5)
    runs = _list(value['runs'], 'frozen runs', MAX_ROWS)
    seen, temperatures, replicates = set(), set(), set()
    for row in runs:
        _fields(row, 'run_id temperature_kelvin replicate_id', 'frozen run')
        identity = _text(row['run_id'], 'run id')
        replicate = _text(row['replicate_id'], 'replicate id')
        temperature = _number(row['temperature_kelvin'], 'temperature kelvin', 1e-6, 1e6)
        _require(identity not in seen, 'duplicate-run', 'run IDs must be unique')
        _require((temperature, replicate) not in replicates, 'replicate-identity', 'duplicate replicate within temperature')
        seen.add(identity)
        replicates.add((temperature, replicate))
        if temperature not in temperatures:
            _require(len(temperatures) < MAX_TEMPERATURES, 'input-limit', 'too many distinct temperatures')
            temperatures.add(temperature)
    return value


def _interval(value, error, critical):
    width = error * critical
    return [value - width, value + width]


def _fit(rates, rules, weighting):
    _record(rates, 'arr-rates-v1', 'rows')
    rows = _list(rates['rows'], 'rate rows', MAX_ROWS)
    frozen = {row['run_id']: row for row in rules['runs']}
    seen, grouped = set(), {}
    for row in rows:
        _fields(row, 'run_id replicate_id temperature_kelvin temperature_unit rate rate_unit', 'rate row')
        identity = _text(row['run_id'], 'run id')
        replicate = _text(row['replicate_id'], 'replicate id')
        _require(identity not in seen, 'duplicate-run', 'run IDs must be unique')
        seen.add(identity)
        _require(identity in frozen and replicate == frozen[identity]['replicate_id'],
                 'run-identity', 'rate row differs from frozen replicate structure')
        _require(row['temperature_unit'] == 'K', 'temperature-unit', 'Celsius is never admitted as kelvin')
        temperature = _number(row['temperature_kelvin'], 'temperature kelvin', 1e-6, 1e6)
        _require(temperature == frozen[identity]['temperature_kelvin'],
                 'temperature-identity', 'temperature differs from frozen kelvin identity')
        _require(row['rate_unit'] == rules['rate_unit'], 'rate-units', 'rate units must be consistent')
        rate = _number(row['rate'], 'rate constant', -MAX_NUMBER)
        _require(rate > 0, 'nonpositive-rate', 'non-positive rates must never be log-transformed')
        grouped.setdefault(temperature, []).append(math.log(rate))
    _require(seen == set(frozen), 'missing-run', 'every frozen run must be present')
    collapsed = []
    for temperature, values in sorted(grouped.items()):
        count = len(values)
        mean = math.fsum(values) / count
        pure_error = math.fsum((value - mean) ** 2 for value in values)
        collapsed.append({'temperature_kelvin': temperature, 'n_replicates': count, 'mean_log_rate': mean,
                          'variance_log_rate': pure_error / (count - 1) if count > 1 else 'unavailable'})
    n = len(collapsed)
    span = collapsed[-1]['temperature_kelvin'] - collapsed[0]['temperature_kelvin']
    result = {'status': 'unavailable', 'n_runs': len(rows), 'n_temperatures': n, 'temperature_span_kelvin': span,
              'weighting': weighting, 'rate_unit': rules['rate_unit'], 'energy_unit': rules['energy_unit'],
              'temperatures': collapsed, 'df': 'unavailable', 'Ea': 'unavailable', 'Ea_se': 'unavailable',
              'Ea_interval': 'unavailable', 'ln_A': 'unavailable', 'ln_A_se': 'unavailable',
              'ln_A_interval': 'unavailable', 'slope': 'unavailable', 'slope_se': 'unavailable',
              'residual_standard_error': 'unavailable', 't_critical': 'unavailable',
              'lack_of_fit': 'unavailable', 'prediction': {'temperature_kelvin': rules['prediction_temperature_kelvin'],
                  'status': 'unavailable', 'ln_rate': 'unavailable', 'rate': 'unavailable',
                  'ln_rate_se': 'unavailable', 'ln_rate_interval': 'unavailable', 'rate_interval': 'unavailable'}}
    inverse_requested = 1 / rules['prediction_temperature_kelvin']
    outside = (inverse_requested < 1 / collapsed[-1]['temperature_kelvin']
               or inverse_requested > 1 / collapsed[0]['temperature_kelvin'])
    if outside:
        result['prediction']['status'] = 'outside-range'
    if n < rules['minimum_temperatures'] or span < rules['minimum_span_kelvin']:
        return result
    xs = [1 / row['temperature_kelvin'] for row in collapsed]
    ys = [row['mean_log_rate'] for row in collapsed]
    weights = [1.0] * n
    if weighting == 'replicate-variance':
        for row in collapsed:
            _require(type(row['variance_log_rate']) is float and row['variance_log_rate'] > 0,
                     'replicate-variance', 'variance weighting needs positive variance at every temperature')
        weights = [row['n_replicates'] / row['variance_log_rate'] for row in collapsed]
        _require(all(math.isfinite(w) and w > 0 for w in weights), 'degenerate-fit', 'non-finite replicate weights')
        maximum = max(weights)
        scaled = [weight / maximum for weight in weights]
        total = math.fsum(scaled)
        weights = [weight * n / total for weight in scaled]
        _require(all(weight > 0 for weight in weights), 'degenerate-fit', 'weight normalization underflow')
    total = math.fsum(weights)
    xmean = math.fsum(w * x for w, x in zip(weights, xs)) / total
    ymean = math.fsum(w * y for w, y in zip(weights, ys)) / total
    sxx = math.fsum(w * (x - xmean) ** 2 for w, x in zip(weights, xs))
    syy = math.fsum(w * (y - ymean) ** 2 for w, y in zip(weights, ys))
    _require(sxx > 0 and syy > 0, 'degenerate-fit', 'temperature or log-rate variance is zero')
    slope = math.fsum(w * (x - xmean) * (y - ymean) for w, x, y in zip(weights, xs, ys)) / sxx
    intercept = ymean - slope * xmean
    residuals = [y - (ymean + slope * (x - xmean)) for x, y in zip(xs, ys)]
    ss = math.fsum(w * residual ** 2 for w, residual in zip(weights, residuals))
    df = n - 2
    variance = ss / df
    slope_se = math.sqrt(variance / sxx)
    intercept_se = math.sqrt(variance * (1 / total + xmean ** 2 / sxx))
    critical = student_t_critical(df, rules['interval_level'])
    gas = rules['gas_constant']
    energy, energy_se = -gas * slope, gas * slope_se
    result.update(status='fitted', df=df, Ea=energy, Ea_se=energy_se,
                  Ea_interval=_interval(energy, energy_se, critical), ln_A=intercept, ln_A_se=intercept_se,
                  ln_A_interval=_interval(intercept, intercept_se, critical), slope=slope, slope_se=slope_se,
                  residual_standard_error=math.sqrt(variance), t_critical=critical)
    # Classical pure-error F requires equal replicate counts and unweighted means.
    counts = [row['n_replicates'] for row in collapsed]
    if weighting == 'ordinary-least-squares' and min(counts) > 1 and len(set(counts)) == 1:
        pure_df = len(rows) - n
        pure_ss = math.fsum((row['n_replicates'] - 1) * row['variance_log_rate'] for row in collapsed)
        if pure_ss > 0:
            f_value = (counts[0] * ss / df) / (pure_ss / pure_df)
            _require(math.isfinite(f_value), 'degenerate-fit', 'lack-of-fit ratio is non-finite')
            p_value = _beta(pure_df / 2, df / 2, pure_df / (pure_df + df * f_value))
            result['lack_of_fit'] = {'F': f_value, 'df_numerator': df, 'df_denominator': pure_df,
                                     'p': p_value, 'flag': p_value < rules['lack_of_fit_alpha']}
    prediction = result['prediction']
    x = inverse_requested
    if not outside:
        log_rate = ymean + slope * (x - xmean)
        error = math.sqrt(variance * (1 / total + (x - xmean) ** 2 / sxx))
        interval = _interval(log_rate, error, critical)
        _require(all(-700 <= value <= 700 for value in (*interval, log_rate)),
                 'prediction-numeric', 'propagated rate interval exceeds finite reference range')
        prediction.update(status='inside-range', ln_rate=log_rate, rate=math.exp(log_rate), ln_rate_se=error,
                          ln_rate_interval=interval, rate_interval=[math.exp(value) for value in interval])
    return result


def compute_arrhenius(rates, rules, weighting=None):
    """Fit synthetic log rates; intervals describe the mean log response, not future runs."""
    rules = _rules(rules)
    weighting = rules['weighting'] if weighting is None else _weighting(weighting)
    try:
        return _fit(rates, rules, weighting)
    except (OverflowError, ZeroDivisionError) as error:
        raise ValueError('degenerate-fit: arithmetic exceeds finite reference range') from error

def _same(actual, expected, label):
    if type(expected) in (int, float):
        _number(actual, label, -MAX_NUMBER, integer=type(expected) is int)
        _require(math.isclose(actual, expected, rel_tol=1e-9, abs_tol=0),
                 "reported-number", f"reported {label} disagrees with reference")
    elif type(expected) is dict:
        _fields(actual, expected, label)
        for key in expected:
            _same(actual[key], expected[key], key)
    elif type(expected) is list:
        _list(actual, label, MAX_ROWS, True)
        _require(len(actual) == len(expected), "reported-result", "reported array count differs")
        for a, b in zip(actual, expected):
            _same(a, b, label)
    else:
        _require(type(actual) is type(expected) and actual == expected,
                 "reported-result", f"reported {label} differs from reference")


def _claims(claims, evidence):
    claims = _list(claims, "claims", MAX_RECORDS, True)
    seen = set()
    for claim in claims:
        _fields(claim, "id kind status text evidence", "claim")
        identity = _text(claim["id"], "claim id")
        _require(identity not in seen, "invalid-record", "duplicate claim id")
        seen.add(identity)
        kind = _text(claim["kind"], "claim kind")
        status = _text(claim["status"], "claim status")
        text = _text(claim["text"], "claim text")
        _require(kind in {"descriptive", "associational"} and not OVERREACH.search(text),
                 "claim-overreach", "claim exceeds bounded synthetic arithmetic")
        _require(status in STATUSES, "invalid-record", "unknown claim status")
        ids = _names(claim["evidence"], "claim evidence", MAX_RECORDS, True)
        _require(ids or status == "unavailable", "missing-evidence", "empty evidence requires unavailable")
        _require(status != "unavailable" or not ASSERTION.search(text),
                 "unavailable-positive", "unavailable claim asserts positive evidence")
        for identity in ids:
            _require(identity in evidence, "missing-evidence", "unknown evidence identity")
            record = evidence[identity]
            _require("unavailable" not in (record["kind"], record["result"]) or status == "unavailable",
                     "unavailable-evidence", "unavailable records require unavailable claims")
            _require(status not in POSITIVE or not any(NON_EVIDENCE.search(record[key]) for key in ("kind", "result")),
                     "non-evidence-support", "review approval and computed agreement are not positive evidence")
        _require(status != "replicated", "claim-replication", "one synthetic fixture cannot establish replication")


def validate_arrhenius_rate_fit_pack(bundle):
    """Validate one offline synthetic bundle; write no files and leave review unavailable."""
    try:
        value = _text(os.fspath(bundle), 'bundle path')
        _require(all(ord(c) >= 32 for c in value), 'input-path', 'control character in bundle path')
        _require('..' not in Path(value).parts and '\\' not in value,
                 'input-path', 'bundle path must not contain traversal or backslashes')
        path = Path(os.path.abspath(value))
    except (TypeError, ValueError) as error:
        raise ValueError('input-path: invalid bundle path') from error
    store = _Bundle(path.parent)
    try:
        pack = _record(store.load(path.name), 'arr-pack-v1',
                       'rules frozen_rules_sha256 frozen_before_rates_read rates report evidence')
        rules = _rules(store.artifact(pack['rules']))
        _require(_text(pack['frozen_rules_sha256'], 'frozen rules hash') == pack['rules']['sha256']
                 and _boolean(pack['frozen_before_rates_read'], 'frozen before rates read'),
                 'rule-freeze', 'rules must be hash-frozen before rates are opened')
        report = _record(store.artifact(pack['report']), 'arr-report-v1',
                         'rules_sha256 exploratory weighting computation headline claims')
        _require(_text(report['rules_sha256'], 'rules hash') == pack['rules']['sha256'],
                 'rule-freeze', 'report cites a different frozen rule revision')
        exploratory = _boolean(report['exploratory'], 'exploratory')
        weighting = _weighting(report['weighting'])
        _require(weighting == rules['weighting'] or exploratory,
                 'post-hoc-weighting', 'post-outcome weighting change requires exploratory label')
        headline = _text(report['headline'], 'headline')
        _require(not OVERREACH.search(headline), 'claim-overreach', 'headline exceeds bounded synthetic arithmetic')
        descriptors = _list(pack['evidence'], 'evidence artifacts', MAX_RECORDS, True)
        own_paths = {path.name}
        own_hashes = {store.snapshots[path.name][2]}
        for descriptor in (pack['rules'], pack['rates'], pack['report'], *descriptors):
            _fields(descriptor, 'path sha256', 'artifact identity')
            own_paths.add(str(_relative(descriptor['path'])))
            own_hashes.add(_text(descriptor['sha256'], 'sha256'))
        evidence = {}
        for descriptor in descriptors:
            document = _record(store.artifact(descriptor), 'arr-evidence-v1', 'records')
            records = _list(document['records'], 'evidence records', MAX_RECORDS, True)
            _require(len(evidence) + len(records) <= MAX_RECORDS, 'input-limit', 'too many evidence records')
            for record in records:
                _fields(record, 'id kind result origin source', 'evidence record')
                identity = _text(record['id'], 'evidence id')
                _require(identity not in evidence, 'invalid-record', 'duplicate evidence identity')
                for key in ('kind', 'result', 'origin'):
                    _text(record[key], key)
                _require(record['origin'] in {'internal', 'external', 'independent', 'preregistered'},
                         'invalid-record', 'unknown source origin')
                digest = store.artifact(record['source'], parse=False)
                if record['origin'] != 'internal':
                    _require(record['source']['path'] not in own_paths and digest not in own_hashes,
                             'external-alias', 'independence label aliases own artifacts')
                evidence[identity] = record
        _claims(report['claims'], evidence)
        computation = compute_arrhenius(store.artifact(pack['rates']), rules, weighting)
        actual = report['computation']
        _fields(actual, computation, 'reported computation')
        _number(actual['n_temperatures'], 'reported distinct temperatures', 1, MAX_TEMPERATURES, True)
        _require(actual['n_temperatures'] == computation['n_temperatures'],
                 'pseudoreplication', 'technical replicates are not independent temperatures')
        if computation['n_temperatures'] < rules['minimum_temperatures']:
            _require(actual['status'] == 'unavailable' and actual['Ea'] == 'unavailable'
                     and actual['ln_A'] == 'unavailable',
                     'insufficient-temperatures', 'below frozen distinct-temperature minimum needs unavailable parameters')
        if computation['temperature_span_kelvin'] < rules['minimum_span_kelvin']:
            _require(actual['status'] == 'unavailable' and actual['Ea'] == 'unavailable'
                     and actual['ln_A'] == 'unavailable',
                     'temperature-span', 'below frozen span needs unavailable parameters')
        _fields(actual['prediction'], computation['prediction'], 'reported prediction')
        if computation['prediction']['status'] == 'outside-range':
            _require(actual['prediction']['status'] == 'outside-range'
                     and actual['prediction']['rate'] == 'unavailable'
                     and actual['prediction']['ln_rate'] == 'unavailable',
                     'extrapolated-prediction', 'outside-range prediction must never be extrapolated')
        _same(actual, computation, 'computation')
        store.finish()
        return {'schema': 'arr-result-v1', 'fixture': 'synthetic fixture', 'status': 'arithmetic-only',
                'review': 'unavailable', 'stages': list(STAGES), 'exploratory': exploratory,
                'inputs': [{'path': name, 'sha256': item[2]} for name, item in sorted(store.snapshots.items())],
                'computation': computation, 'claims': report['claims'],
                'limitations': ['Synthetic rates establish offline software arithmetic only.',
                                'Log-linear errors and replicate precision are assumptions, not physical validation.',
                                'Intervals propagate mean log-rate uncertainty, not future-rate or lifetime uncertainty.',
                                'Pure-error lack-of-fit is available only for balanced unweighted replicates with positive variance.',
                                'Hashes cannot prove historical freeze timing or independent source identity.',
                                'Independent record, source and method review remains unavailable.']}
    finally:
        store.close()
