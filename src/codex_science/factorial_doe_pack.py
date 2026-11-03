"""Read-only synthetic factorial contrasts, alias sets and pure-error reference arithmetic."""
from __future__ import annotations

from itertools import combinations, product
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import random
import stat


STAGES = ("01-rule-freeze", "02-table-qc", "03-effects", "04-summary", "05-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_ROWS = 10000
MAX_FACTORS = 4
MAX_RUNS = 17
MAX_REPLICATES = 128
MAX_OBSERVATIONS = 4096
MAX_ITERATIONS = 512
QUANTILE_STEPS = 96
MAX_NODES = 4000000
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
    r"physical[\s-]+validity|patient[\s-]+benefit\w*|optim\w*|scale[\s-]*up|"
    r"process[\s-]+validity)\b", re.I,
)
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
            _require(len(self.snapshots) < MAX_RECORDS, "input-limit", "too many artifact paths")
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
        _require(len(actual) == len(expected), "reported-result", "reported list length differs")
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


def _beta_fraction(a, b, x):
    tiny = 1e-300
    c = 1.0
    d = 1 - (a + b) * x / (a + 1)
    d = 1 / (d if abs(d) >= tiny else tiny)
    result = d
    for m in range(1, MAX_ITERATIONS + 1):
        for numerator in (m * (b - m) * x / ((a + 2*m - 1) * (a + 2*m)),
                          -(a + m) * (a + b + m) * x / ((a + 2*m) * (a + 2*m + 1))):
            d = 1 + numerator * d
            c = 1 + numerator / c
            d = 1 / (d if abs(d) >= tiny else math.copysign(tiny, d))
            c = c if abs(c) >= tiny else math.copysign(tiny, c)
            delta = c * d
            result *= delta
        if abs(delta - 1) <= 1e-14:
            return result
    raise ValueError("t-convergence: incomplete beta fraction did not converge")


def _beta(a, b, x):
    if x == 0:
        return 0.0
    if x == 1:
        return 1.0
    weight = math.exp(math.lgamma(a+b) - math.lgamma(a) - math.lgamma(b)
                      + a * math.log(x) + b * math.log1p(-x))
    if x < (a+1) / (a+b+2):
        return weight * _beta_fraction(a, b, x) / a
    return 1 - weight * _beta_fraction(b, a, 1-x) / b


def student_t_critical(df, level=0.95):
    """Positive equal-tail Student t critical value, using incomplete-beta inversion."""
    _number(df, "pure-error degrees of freedom", 1, MAX_OBSERVATIONS, True)
    _number(level, "interval level", .5, .999)
    low, high = 0.0, 1e6
    for _ in range(QUANTILE_STEPS):
        middle = (low + high) / 2
        tail = _beta(df/2, .5, df / (df + middle*middle))
        if tail > 1 - level:
            low = middle
        else:
            high = middle
    _require(high-low <= high * 1e-11, "t-convergence", "Student t inversion did not converge")
    return (low + high) / 2


def _terms(factors):
    return [()] + [item for size in range(1, len(factors)+1) for item in combinations(range(len(factors)), size)]


def _check_design(levels, factors, design):
    n = len(levels)
    columns = list(zip(*levels))
    _require(n > 0 and all(sum(column) == 0 for column in columns)
             and all(sum(x*y for x, y in zip(a, b)) == 0 for a, b in combinations(columns, 2)),
             "non-orthogonal", "factor columns must be exactly balanced and pairwise orthogonal")
    indices = {factor: i for i, factor in enumerate(factors)}
    for generator in design["generators"]:
        target = indices[generator["factor"]]
        terms = [indices[item] for item in generator["terms"]]
        _require(all(row[target] == generator["sign"] * math.prod(row[i] for i in terms) for row in levels),
                 "fraction-generators", "coded levels disagree with frozen fraction generators")
    dependent = {row["factor"] for row in design["generators"]}
    base = [i for i, name in enumerate(factors) if name not in dependent]
    _require(len(set(levels)) == n and n == 2**len(base)
             and {tuple(row[i] for i in base) for row in levels} == set(product((-1, 1), repeat=len(base))),
             "design-identity", "table is not the frozen full or regular fraction")
    defining = [term for term in _terms(factors)[1:]
                if len({math.prod(row[i] for i in term) for row in levels}) == 1]
    resolution = min(map(len, defining)) if defining else 0
    _require(design["resolution"] == resolution, "fraction-resolution", "stated resolution differs from defining relation")


def _rules(value):
    _record(value, "doe-rules-v1", "factors design runs response units effect_rule error_rule interval_level randomisation_seed")
    factors = _list(value["factors"], "factors", MAX_FACTORS)
    ids = []
    for index, factor in enumerate(factors):
        _fields(factor, "id low high", "factor")
        _require(_text(factor["id"], "factor id") == chr(65+index),
                 "factor-identity", "factor IDs must be ordered A through D")
        _text(factor["low"], "low level")
        _text(factor["high"], "high level")
        _require(factor["low"] != factor["high"], "factor-identity", "low and high levels must differ")
        ids.append(factor["id"])
    design = _fields(value["design"], "type name generators resolution", "design")
    kind = _text(design["type"], "design type")
    _require(kind in {"full", "regular-fraction"}, "design-identity", "unsupported design type")
    generators = _list(design["generators"], "generators", MAX_FACTORS, True)
    _number(design["resolution"], "resolution", 0, MAX_FACTORS, True)
    dependent = []
    for generator in generators:
        _fields(generator, "factor terms sign", "generator")
        factor = _text(generator["factor"], "generator factor")
        terms = _names(generator["terms"], "generator terms", MAX_FACTORS)
        _number(generator["sign"], "generator sign", -1, 1, True)
        _require(generator["sign"] in (-1, 1) and factor in ids and factor not in dependent
                 and all(term in ids and term != factor for term in terms),
                 "fraction-generators", "invalid generator factor, terms or sign")
        dependent.append(factor)
    base = [name for name in ids if name not in dependent]
    _require(all(term in base for row in generators for term in row["terms"]),
             "fraction-generators", "generators must use independent base factors")
    _require((kind == "full" and not generators) or (kind == "regular-fraction" and generators),
             "fraction-generators", "fraction must name its generators; full design has none")
    name = f"2^{len(ids)}" if kind == "full" else f"2^({len(ids)}-{len(generators)})"
    _require(_text(design["name"], "design name") == name, "design-identity", "named design differs from factor count")
    runs = _list(value["runs"], "frozen runs", MAX_RUNS)
    seen, levels, centres, total, replicates = set(), [], 0, 0, set()
    for row in runs:
        _fields(row, "run_id levels replicates", "frozen run")
        identity = _text(row["run_id"], "run id")
        _require(identity not in seen, "duplicate-run", "run IDs must be unique")
        seen.add(identity)
        coded = _list(row["levels"], "coded levels", MAX_FACTORS)
        _require(len(coded) == len(ids) and all(type(x) is int and x in (-1, 0, 1) for x in coded)
                 and (all(x == 0 for x in coded) or all(x in (-1, 1) for x in coded)),
                 "coded-levels", "factorial rows need -1/+1; centre rows need all zero")
        _number(row["replicates"], "replicates", 1, MAX_NUMBER, True)
        _require(row["replicates"] <= MAX_REPLICATES, "input-limit", "replicate count exceeds reference budget")
        total += row["replicates"]
        _require(total <= MAX_OBSERVATIONS, "input-limit", "total observations exceed reference budget")
        if all(x == 0 for x in coded):
            centres += 1
        else:
            levels.append(tuple(coded))
            replicates.add(row["replicates"])
    _require(centres <= 1, "design-identity", "use one centre condition with its recorded replicates")
    _require(len(replicates) == 1, "unbalanced-replicates", "factorial conditions require equal replicate counts")
    _check_design(levels, ids, design)
    for key in ("response", "units"):
        _text(value[key], key)
    _require(value["effect_rule"] == "half-difference-of-level-means", "effect-rule", "frozen half-difference rule required")
    _require(value["error_rule"] == "pure-error-from-replicates", "error-rule", "only within-condition pure error is admitted")
    _number(value["interval_level"], "interval level", .5, .999)
    _number(value["randomisation_seed"], "randomisation seed", 0, 2**32-1, True)
    return value


def _coding(value, factors):
    _fields(value, factors, "applied coding")
    for sign in value.values():
        _number(sign, "coding sign", -1, 1, True)
        _require(sign in (-1, 1), "coded-levels", "coding orientation must be -1 or +1")
    return value


def compute_factorial_effects(table, rules, coding=None):
    """Return half-difference coefficients per identifiable alias set, never causal effects."""
    rules = _rules(rules)
    factors = [row["id"] for row in rules["factors"]]
    coding = _coding({name: 1 for name in factors} if coding is None else coding, factors)
    _record(table, "doe-table-v1", "rows run_order")
    rows = _list(table["rows"], "response rows", MAX_RUNS)
    by_id, levels, total = {}, [], 0
    for row in rows:
        _fields(row, "run_id levels responses", "response row")
        identity = _text(row["run_id"], "run id")
        _require(identity not in by_id, "duplicate-run", "run IDs must be unique")
        by_id[identity] = row
        coded = _list(row["levels"], "coded levels", MAX_FACTORS)
        _require(len(coded) == len(factors) and all(type(x) is int and x in (-1, 0, 1) for x in coded)
                 and (all(x == 0 for x in coded) or all(x in (-1, 1) for x in coded)),
                 "coded-levels", "coded levels must be factorial -1/+1 or centre zero")
        responses = _list(row["responses"], "replicate responses", MAX_REPLICATES)
        total += len(responses)
        _require(total <= MAX_OBSERVATIONS, "input-limit", "total response budget exceeded")
        for response in responses:
            _number(response, "response", -MAX_NUMBER)
        if any(coded):
            levels.append(tuple(coded))
    _check_design(levels, factors, rules["design"])
    _require(set(by_id) == {row["run_id"] for row in rules["runs"]}, "design-identity", "table run IDs differ from freeze")
    for rule in rules["runs"]:
        row = by_id[rule["run_id"]]
        _require(row["levels"] == rule["levels"], "design-identity", "coded levels changed from frozen identities")
        _require(len(row["responses"]) == rule["replicates"], "replicate-count", "response counts differ from freeze")
    order = _names(table["run_order"], "run order", MAX_RUNS)
    expected_order = [row["run_id"] for row in rules["runs"]]
    random.Random(rules["randomisation_seed"]).shuffle(expected_order)
    _require(order == expected_order, "run-order", "run order differs from frozen randomisation seed")
    totals = {name: math.fsum(row["responses"]) for name, row in by_id.items()}
    means = {name: totals[name]/len(row["responses"]) for name, row in by_id.items()}
    df = sum(len(row["responses"])-1 for row in rows)
    run_sse = []
    for name, row in by_id.items():
        spread = math.fsum((response-means[name])**2 for response in row["responses"])
        run_sse.append(0.0 if spread <= 1e-28 * math.fsum(r*r for r in row["responses"]) else spread)
    sse = math.fsum(run_sse)
    _require(df == 0 or sse > 0, "degenerate-error", "zero pure-error variance cannot support inference")
    mse = sse/df if df else "unavailable"
    critical = student_t_critical(df, rules["interval_level"]) if df else "unavailable"
    factorial = [by_id[row["run_id"]] for row in rules["runs"] if any(row["levels"])]
    n = sum(len(row["responses"]) for row in factorial)
    factorial_totals = [totals[row["run_id"]] for row in factorial]
    grand_mean = math.fsum(factorial_totals)/n
    se = math.sqrt(mse/n) if df else "unavailable"

    def interval(estimate, error):
        return ({"level": rules["interval_level"], "df": df, "lower": estimate-critical*error,
                 "upper": estimate+critical*error, "method": "student-t-pure-error"} if df else "unavailable")

    groups, aliases = {}, []
    for term in _terms(factors):
        column = tuple(math.prod(row["levels"][i]*coding[factors[i]] for i in term) for row in factorial)
        opposite = tuple(-x for x in column)
        if column in groups:
            group, sign = groups[column], 1
        elif opposite in groups:
            group, sign = groups[opposite], -1
        else:
            estimate = math.fsum(x*total for x, total in zip(column, factorial_totals))/n
            group = {"terms": [], "estimate": estimate, "standard_error": se, "interval": interval(estimate, se)}
            groups[column] = group
            aliases.append(group)
            sign = 1
        group["terms"].append({"term": ''.join(factors[i] for i in term) or "I", "sign": sign})
    centres = [row for row in rows if not any(row["levels"])]
    curvature = "unavailable"
    if centres:
        centre = centres[0]
        estimate = means[centre["run_id"]] - grand_mean
        error = math.sqrt(mse*(1/len(centre["responses"])+1/n)) if df else "unavailable"
        bounds = interval(estimate, error)
        departure = ("detected" if bounds["lower"] > 0 or bounds["upper"] < 0 else "not-detected") if df else "unavailable"
        curvature = {"estimate": estimate, "standard_error": error, "interval": bounds, "departure": departure}
    return {"alias_sets": aliases, "pure_error": {"df": df, "sum_squares": sse, "variance": mse},
            "curvature": curvature, "summary": {"factorial_runs": len(factorial), "observations": total,
                                                "centre_runs": len(centres), "grand_mean": grand_mean}}


def _evidence(store, entry, path):
    descriptors = _list(entry["evidence"], "evidence artifacts", MAX_RECORDS, True)
    own_paths = {path.name}
    own_hashes = {store.snapshots[path.name][2]}
    for descriptor in (entry["rules"], entry["table"], entry["report"], *descriptors):
        _fields(descriptor, "path sha256", "artifact identity")
        own_paths.add(str(_relative(descriptor["path"])))
        own_hashes.add(_text(descriptor["sha256"], "sha256"))
    evidence = {}
    for descriptor in descriptors:
        document = _record(store.artifact(descriptor), "doe-evidence-v1", "records")
        records = _list(document["records"], "evidence records", MAX_RECORDS, True)
        _require(len(evidence)+len(records) <= MAX_RECORDS, "input-limit", "too many evidence records")
        for record in records:
            _fields(record, "id kind result origin source", "evidence record")
            identity = _text(record["id"], "evidence id")
            _require(identity not in evidence, "invalid-record", "duplicate evidence id")
            for key in ("kind", "result", "origin"):
                _text(record[key], key)
            _require(record["origin"] in {"internal", "external", "independent", "preregistered"},
                     "invalid-record", "unknown source origin")
            digest = store.artifact(record["source"], parse=False)
            if record["origin"] != "internal":
                _require(record["source"]["path"] not in own_paths and digest not in own_hashes,
                         "external-alias", "independence label aliases own artifacts")
            evidence[identity] = record
    return evidence


def validate_factorial_doe_pack(bundle):
    """Admit one offline synthetic bundle; no files, records or refs are written."""
    try:
        value = _text(os.fspath(bundle), "bundle path")
        _require(all(ord(c) >= 32 for c in value) and ".." not in Path(value).parts and "\\" not in value,
                 "input-path", "bundle path contains traversal or control characters")
        path = Path(os.path.abspath(value))
    except (TypeError, ValueError) as error:
        raise ValueError("input-path: invalid bundle path") from error
    store = _Bundle(path.parent)
    try:
        entry = _record(store.load(path.name), "doe-pack-v1", "rules frozen_rules_sha256 frozen_before_responses_read table report evidence")
        rules = _rules(store.artifact(entry["rules"]))
        _require(_text(entry["frozen_rules_sha256"], "frozen rule hash") == entry["rules"]["sha256"]
                 and _boolean(entry["frozen_before_responses_read"], "frozen before responses read"),
                 "rule-freeze", "rules must be hash-frozen before responses are opened")
        report = store.artifact(entry["report"])
        _require(type(report) is dict and "curvature" in report,
                 "curvature-omitted", "report must retain curvature check or explicit unavailable")
        _record(report, "doe-report-v1", "rules_sha256 exploratory coding alias_sets pure_error curvature summary headline claims")
        _require(_text(report["rules_sha256"], "rules hash") == entry["rules"]["sha256"],
                 "rule-freeze", "report cites a different rule revision")
        exploratory = _boolean(report["exploratory"], "exploratory")
        coding = _coding(report["coding"], [factor["id"] for factor in rules["factors"]])
        _require(all(x == 1 for x in coding.values()) or exploratory,
                 "post-hoc-coding", "post-outcome level recoding requires exploratory label")
        headline = _text(report["headline"], "headline")
        _require(not OVERREACH.search(headline), "claim-overreach", "headline exceeds synthetic arithmetic")
        evidence = _evidence(store, entry, path)
        _claims(report["claims"], evidence)
        result = compute_factorial_effects(store.artifact(entry["table"]), rules, coding)
        actual_sets = _list(report["alias_sets"], "reported alias sets", 2**MAX_FACTORS)
        _require(len(actual_sets) == len(result["alias_sets"]),
                 "alias-separation", "aliased terms must be reported together, once per identifiable contrast")
        for actual, expected in zip(actual_sets, result["alias_sets"]):
            _require(type(actual) is dict and actual.get("terms") == expected["terms"],
                     "alias-separation", "reported alias membership or sign differs from fraction")
            if result["pure_error"]["df"] == 0:
                _require(actual.get("interval") == "unavailable" and actual.get("standard_error") == "unavailable",
                         "inference-without-replicates", "intervals need replicated pure-error evidence")
            _same(actual, expected, "alias set")
        if result["pure_error"]["df"] == 0:
            texts = [headline] + [claim["text"] for claim in report["claims"]]
            _require(not any(re.search(r"\b(?:significan\w*|p[\s-]*value\w*|reject\w*)\b", text, re.I) for text in texts),
                     "inference-without-replicates", "significance wording needs replicated pure error")
        _require(result["curvature"] == "unavailable" or type(report["curvature"]) is dict,
                 "curvature-omitted", "centre points require the explicit curvature contrast")
        for key in ("pure_error", "curvature", "summary"):
            _same(report[key], result[key], key)
        store.finish()
        return {"schema": "doe-result-v1", "fixture": "synthetic fixture", "status": "arithmetic-only",
                "review": "unavailable", "stages": list(STAGES), "exploratory": exploratory,
                "inputs": [{"path": name, "sha256": item[2]} for name, item in sorted(store.snapshots.items())],
                "computation": result, "claims": report["claims"],
                "limitations": ["Synthetic responses establish software arithmetic only.",
                                "Intervals assume independent homoscedastic replicate errors; these assumptions are unverified.",
                                "Alias sets cannot identify their individual terms; centre curvature cannot identify a quadratic term.",
                                "Hashes cannot establish historical freeze timing or true source independence.",
                                "Independent record, source and method review remains unavailable."]}
    finally:
        store.close()
