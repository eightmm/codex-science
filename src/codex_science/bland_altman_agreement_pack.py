"""Read-only synthetic paired-method agreement admission and stdlib reference arithmetic."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat


STAGES = ("01-rule-freeze", "02-pair-qc", "03-agreement", "04-summary", "05-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_ROWS = 10000
MAX_UNITS = 10000
MAX_REPLICATES = 128
MAX_NODES = 4000000
MAX_ITERATIONS = 10000
QUANTILE_STEPS = 96
REL_TOL = 1e-9
SINGULAR_REL = 1e-12
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
    r"physical[\s-]+validity|patient[\s-]+benefit\w*|interchange\w*|equivalen\w*|method[\s-]+valid\w*)\b", re.I,
)
CORRELATION = re.compile(r"\bcorrelat\w*\b", re.I)
ASSERTION = re.compile(r"\b(?:supported|replicated|suggestive|significan\w*)\b", re.I)
NON_EVIDENCE = re.compile(r"review|approv|comput|numer|arithmet|result-v1|agreement|truth|physical|clinic", re.I)


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
    _require(len(pairs) <= MAX_ROWS, "input-limit", "JSON object exceeds limit")
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

def _beta_fraction(a, b, x):
    tiny = 1e-300
    c = 1.0
    d = 1 - (a + b) * x / (a + 1)
    d = 1 / (d if abs(d) >= tiny else math.copysign(tiny, d))
    value = d
    for step in range(1, MAX_ITERATIONS + 1):
        for term in (step * (b - step) * x / ((a + 2 * step - 1) * (a + 2 * step)),
                     -(a + step) * (a + b + step) * x / ((a + 2 * step) * (a + 2 * step + 1))):
            d = 1 + term * d
            c = 1 + term / c
            d = 1 / (d if abs(d) >= tiny else math.copysign(tiny, d))
            c = c if abs(c) >= tiny else math.copysign(tiny, c)
            delta = d * c
            value *= delta
        if abs(delta - 1) <= 1e-14:
            return value
    raise ValueError("t-convergence: incomplete beta fraction did not converge")


def student_t_pvalue(t, degrees_of_freedom):
    """Two-sided Student t tail via regularized incomplete beta; no normal fallback."""
    _number(t, "t statistic", -MAX_NUMBER)
    _number(degrees_of_freedom, "degrees of freedom", 1, MAX_UNITS, True)
    if t == 0:
        return 1.0
    a, b = degrees_of_freedom / 2, 0.5
    x = degrees_of_freedom / (degrees_of_freedom + t * t)
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                     + a * math.log(x) + b * math.log1p(-x)) if x < 1 else 0.0
    if x < (a + 1) / (a + b + 2):
        value = front * _beta_fraction(a, b, x) / a
    else:
        value = 1 - front * _beta_fraction(b, a, 1 - x) / b
    _require(math.isfinite(value) and value > 0, "degenerate-numeric", "t tail underflowed")
    return min(1.0, value)


def _t_critical(degrees_of_freedom, level):
    low, high = 0.0, 16.0
    target = 1 - level
    _require(student_t_pvalue(high, degrees_of_freedom) < target,
             "t-convergence", "t quantile outside bounded bracket")
    for _ in range(QUANTILE_STEPS):
        middle = (low + high) / 2
        if student_t_pvalue(middle, degrees_of_freedom) > target:
            low = middle
        else:
            high = middle
    _require(high - low <= high * 1e-12, "t-convergence", "t quantile failed to converge")
    return (low + high) / 2


def _rules(value):
    _record(value, "ba-rules-v1", "unit_ids reference_method units scale difference_definition "
            "replicate_rule minimum_pairs interval_minimum_pairs loa_multiplier interval_method "
            "interval_level proportional_bias_method proportional_bias_alpha "
            "normality_max_abs_skewness normality_max_abs_excess_kurtosis maximum_allowed_difference")
    _names(value["unit_ids"], "unit identities", MAX_UNITS)
    _require(_text(value["reference_method"], "reference method") in {"A", "B"},
             "invalid-record", "reference method must be A or B")
    _text(value["units"], "measurement units")
    _require(_text(value["scale"], "scale") in {"original", "log"}, "difference-scale", "unknown scale")
    _require(value["difference_definition"] == "A - B", "difference-scale", "difference must be A - B")
    _require(_text(value["replicate_rule"], "replicate rule") in
             {"one-pair-per-unit", "mean-per-method-before-transform"},
             "repeated-measures", "unknown replicate collapse rule")
    _number(value["minimum_pairs"], "minimum pairs", 3, MAX_UNITS, True)
    _number(value["interval_minimum_pairs"], "interval minimum pairs", 30, 30, True)
    _number(value["loa_multiplier"], "limits multiplier", 1, 3)
    _require(math.isclose(value["loa_multiplier"], 1.96, rel_tol=REL_TOL, abs_tol=0),
             "limits-multiplier", "limits require frozen multiplier 1.96")
    _require(value["interval_method"] == "bland-altman-1986-t", "agreement-interval", "t-based intervals required")
    _number(value["interval_level"], "interval level", 0.5, 0.999)
    _require(value["proportional_bias_method"] == "exact-t-regression", "proportional-bias", "exact t test required")
    _number(value["proportional_bias_alpha"], "proportional bias alpha", 0.001, 0.5)
    _number(value["normality_max_abs_skewness"], "skewness bound", 0, 100)
    _number(value["normality_max_abs_excess_kurtosis"], "kurtosis bound", 0, 100)
    _number(value["maximum_allowed_difference"], "maximum difference", 1e-100)
    return value


def _pair_values(pairs, rules):
    _record(pairs, "ba-pairs-v1", "rows")
    rows = _list(pairs["rows"], "paired units", MAX_UNITS)
    frozen = set(rules["unit_ids"])
    seen = set()
    output, differences, means = [], [], []
    for row in rows:
        _fields(row, "unit_id units method_a method_b", "paired unit")
        identity = _text(row["unit_id"], "unit id")
        _require(identity not in seen, "repeated-measures", "unique unit IDs required; collapse declared replicates")
        seen.add(identity)
        _require(identity in frozen, "unit-identity", "unit outside frozen identities")
        _require(_text(row["units"], "units") == rules["units"], "unit-mismatch", "measurement units differ")
        values = []
        sizes = []
        for method in ("method_a", "method_b"):
            raw = row[method]
            if raw is None:
                values.append(None)
                sizes.append(0)
                continue
            replicates = _list(raw, "method replicates", MAX_REPLICATES)
            sizes.append(len(replicates))
            _require(rules["replicate_rule"] != "one-pair-per-unit" or len(replicates) == 1,
                     "repeated-measures", "repeated measurements require frozen collapse rule")
            for item in replicates:
                _number(item, "measurement", -MAX_NUMBER)
                _require(rules["scale"] != "log" or item > 0,
                         "difference-scale", "log scale needs strictly positive measurements")
            magnitude = max(abs(item) for item in replicates)
            mean = (math.fsum(item / magnitude for item in replicates) / len(replicates) * magnitude
                    if magnitude > 0 else 0.0)
            values.append(math.log(mean) if rules["scale"] == "log" else mean)
        result = {"unit_id": identity, "status": "unavailable", "replicate_count": 0,
                  "difference": "unavailable", "mean": "unavailable"}
        if None not in values:
            _require(sizes[0] == sizes[1], "repeated-measures", "paired replicate counts must agree")
            a, b = values
            difference, mean = a - b, a / 2 + b / 2
            _number(difference, "difference", -MAX_NUMBER)
            _number(mean, "pair mean", -MAX_NUMBER)
            result.update(status="included", replicate_count=sizes[0], difference=difference, mean=mean)
            differences.append(difference)
            means.append(mean)
        output.append(result)
    _require(seen == frozen, "unpaired-unit", "every frozen unit needs an explicit row including missing methods")
    return output, differences, means


def compute_agreement(pairs, rules, maximum_allowed_difference=None):
    """Compute descriptive A-minus-B quantities for synthetic paired units only."""
    rules = _rules(rules)
    bound = rules["maximum_allowed_difference"] if maximum_allowed_difference is None else maximum_allowed_difference
    _number(bound, "applied maximum difference", 1e-100)
    units, differences, means = _pair_values(pairs, rules)
    n = len(differences)
    _require(n >= rules["minimum_pairs"], "insufficient-pairs", "too few complete independent units")
    scale = max(abs(d) for d in differences)
    _require(scale > 0, "degenerate-numeric", "zero difference variance")
    normalized = [d / scale for d in differences]
    average = math.fsum(normalized) / n
    centered = [d - average for d in normalized]
    ss = math.fsum(d * d for d in centered)
    sd_normalized = math.sqrt(ss / (n - 1))
    _require(sd_normalized > SINGULAR_REL, "degenerate-numeric", "difference variance is relatively singular")
    bias, sd = average * scale, sd_normalized * scale
    _require(sd > 0, "degenerate-numeric", "difference deviation underflowed")
    standardized = [d / sd_normalized for d in centered]
    skewness = math.fsum(d ** 3 for d in standardized) / n
    kurtosis = math.fsum(d ** 4 for d in standardized) / n - 3
    _require(abs(skewness) <= rules["normality_max_abs_skewness"]
             and abs(kurtosis) <= rules["normality_max_abs_excess_kurtosis"],
             "normality-screen", "frozen skewness or excess kurtosis screen failed")
    xscale = max(abs(x) for x in means)
    _require(xscale > 0, "degenerate-numeric", "pair means have zero variance")
    x = [mean / xscale for mean in means]
    xbar = math.fsum(x) / n
    xc = [mean - xbar for mean in x]
    sxx = math.fsum(v * v for v in xc)
    _require(math.sqrt(sxx / (n - 1)) > SINGULAR_REL,
             "degenerate-numeric", "pair means are relatively singular")
    slope_normalized = math.fsum(a * b for a, b in zip(xc, centered)) / sxx
    residual_ss = math.fsum((d - slope_normalized * m) ** 2 for m, d in zip(xc, centered))
    _require(residual_ss > SINGULAR_REL ** 2 * ss,
             "degenerate-numeric", "regression residual variance is relatively singular")
    standard_error = math.sqrt(residual_ss / (n - 2) / sxx)
    t = slope_normalized / standard_error
    p = student_t_pvalue(t, n - 2)
    slope = slope_normalized * (scale / xscale)
    _number(slope, "slope", -MAX_NUMBER)
    lower, upper = bias - 1.96 * sd, bias + 1.96 * sd
    intervals = "unavailable"
    if n >= rules["interval_minimum_pairs"]:
        critical = _t_critical(n - 1, rules["interval_level"])
        bias_width = critical * sd / math.sqrt(n)
        limit_width = critical * sd * math.sqrt(3 / n)
        intervals = {"method": rules["interval_method"], "level": rules["interval_level"],
                     "degrees_of_freedom": n - 1,
                     "bias": {"lower": bias - bias_width, "upper": bias + bias_width},
                     "lower_limit": {"lower": lower - limit_width, "upper": lower + limit_width},
                     "upper_limit": {"lower": upper - limit_width, "upper": upper + limit_width}}
    return {"units": units, "summary": {"n": n, "unavailable": len(units) - n,
            "bias": bias, "sd_difference": sd, "lower_limit": lower, "upper_limit": upper,
            "intervals": intervals, "proportional_bias": {"method": "exact-t-regression", "slope": slope,
            "t": t, "degrees_of_freedom": n - 2, "p_value": p,
            "screen": "detected" if p < rules["proportional_bias_alpha"] else "not-detected"},
            "normality": {"skewness": skewness, "excess_kurtosis": kurtosis, "screen": "passed"},
            "limits_within_bound": lower >= -bound and upper <= bound}}


def _same(actual, expected, label):
    if type(expected) is bool:
        _require(_boolean(actual, label) is expected, "reported-result", f"reported {label} differs")
    elif type(expected) in (int, float):
        _number(actual, label, -MAX_NUMBER, integer=type(expected) is int)
        _require(math.isclose(actual, expected, rel_tol=REL_TOL, abs_tol=0),
                 "reported-number", f"reported {label} disagrees with reference")
    elif type(expected) is dict:
        _fields(actual, expected, label)
        for key in expected:
            _same(actual[key], expected[key], key)
    elif type(expected) is list:
        _list(actual, label, MAX_UNITS, True)
        _require(len(actual) == len(expected), "unit-identity", "reported unit count differs")
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
        _require(not CORRELATION.search(text), "correlation-as-agreement", "correlation wording cannot establish agreement")
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


def validate_bland_altman_agreement_pack(bundle):
    """Validate one offline synthetic bundle without creating or changing files."""
    try:
        value = _text(os.fspath(bundle), "bundle path")
        _require(all(ord(c) >= 32 for c in value), "input-path", "control character in bundle path")
        _require(".." not in Path(value).parts and "\\" not in value,
                 "input-path", "bundle path must not contain traversal or backslashes")
        path = Path(os.path.abspath(value))
    except (TypeError, ValueError) as error:
        raise ValueError("input-path: invalid bundle path") from error
    store = _Bundle(path.parent)
    try:
        pack = _record(store.load(path.name), "ba-pack-v1",
                       "rules frozen_rules_sha256 frozen_before_values_read pairs report evidence")
        rules = _rules(store.artifact(pack["rules"]))
        _require(_text(pack["frozen_rules_sha256"], "frozen rules hash") == pack["rules"]["sha256"]
                 and _boolean(pack["frozen_before_values_read"], "frozen before values read"),
                 "rule-freeze", "rules must be hash-frozen before values are opened")
        report = store.artifact(pack["report"])
        _require(type(report.get("summary")) is dict and "intervals" in report["summary"],
                 "agreement-interval", "report must retain intervals or explicit unavailable")
        _require("proportional_bias" in report["summary"], "proportional-bias", "proportional bias must be reported")
        _record(report, "ba-report-v1", "rules_sha256 exploratory maximum_allowed_difference "
                "agreement_measure scale difference_definition units summary headline claims")
        _require(_text(report["rules_sha256"], "rules hash") == pack["rules"]["sha256"],
                 "rule-freeze", "report cites a different frozen rule revision")
        exploratory = _boolean(report["exploratory"], "exploratory")
        bound = _number(report["maximum_allowed_difference"], "applied maximum difference", 1e-100)
        _require(math.isclose(bound, rules["maximum_allowed_difference"], rel_tol=REL_TOL, abs_tol=0) or exploratory,
                 "post-hoc-bound", "post-outcome bound change requires exploratory label")
        _require(report["agreement_measure"] == "limits-of-agreement",
                 "correlation-as-agreement", "correlation cannot substitute for limits of agreement")
        _require(report["scale"] == rules["scale"] and report["difference_definition"] == rules["difference_definition"],
                 "difference-scale", "reported difference scale differs from frozen rule")
        headline = _text(report["headline"], "headline")
        _require(not CORRELATION.search(headline), "correlation-as-agreement", "correlation wording cannot establish agreement")
        _require(not OVERREACH.search(headline), "claim-overreach", "headline exceeds bounded synthetic arithmetic")
        descriptors = _list(pack["evidence"], "evidence artifacts", MAX_RECORDS, True)
        own_paths = {path.name}
        own_hashes = {store.snapshots[path.name][2]}
        for descriptor in (pack["rules"], pack["pairs"], pack["report"], *descriptors):
            _fields(descriptor, "path sha256", "artifact identity")
            own_paths.add(str(_relative(descriptor["path"])))
            own_hashes.add(_text(descriptor["sha256"], "sha256"))
        evidence = {}
        for descriptor in descriptors:
            document = _record(store.artifact(descriptor), "ba-evidence-v1", "records")
            records = _list(document["records"], "evidence records", MAX_RECORDS, True)
            _require(len(evidence) + len(records) <= MAX_RECORDS, "input-limit", "too many evidence records")
            for record in records:
                _fields(record, "id kind result origin source", "evidence record")
                identity = _text(record["id"], "evidence id")
                _require(identity not in evidence, "invalid-record", "duplicate evidence identity")
                for key in ("kind", "result", "origin"):
                    _text(record[key], key)
                _require(record["origin"] in {"internal", "external", "independent", "preregistered"},
                         "invalid-record", "unknown source origin")
                digest = store.artifact(record["source"], parse=False)
                if record["origin"] != "internal":
                    _require(record["source"]["path"] not in own_paths and digest not in own_hashes,
                             "external-alias", "independence label aliases own artifacts")
                evidence[identity] = record
        _claims(report["claims"], evidence)
        result = compute_agreement(store.artifact(pack["pairs"]), rules, bound)
        expected = result["summary"]
        intervals = report["summary"]["intervals"]
        _require((type(intervals) is str and intervals == "unavailable") if expected["intervals"] == "unavailable"
                 else type(intervals) is dict, "agreement-interval", "interval availability differs from pair count")
        if type(intervals) is dict:
            _require(set(intervals) == set(expected["intervals"])
                     and intervals.get("method") == rules["interval_method"],
                     "agreement-interval", "bias and both limits require t-based confidence intervals")
        _require(type(report["summary"]["proportional_bias"]) is dict,
                 "proportional-bias", "proportional bias cannot be ignored")
        _same(report["units"], result["units"], "units")
        _same(report["summary"], expected, "summary")
        store.finish()
        return {"schema": "ba-result-v1", "fixture": "synthetic fixture", "status": "arithmetic-only",
                "review": "unavailable", "stages": list(STAGES), "exploratory": exploratory,
                "inputs": [{"path": name, "sha256": item[2]} for name, item in sorted(store.snapshots.items())],
                "computation": result, "claims": report["claims"],
                "limitations": ["Synthetic pairs establish software arithmetic only.",
                                "Normal independent differences and linear regression assumptions remain unvalidated.",
                                "The frozen moment screen cannot establish normality or constant variance.",
                                "Limits and bounds cannot establish interchangeability or clinical acceptability.",
                                "Hash declarations cannot establish historical freeze timing or independence.",
                                "Independent record, source and method review remains unavailable."]}
    finally:
        store.close()
