"""Offline synthetic stability regression admission and stdlib reference arithmetic."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat


STAGES = ("01-rule-freeze", "02-data-qc", "03-regression", "04-summary", "05-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_JSON_VALUES = 4_000_000
MAX_ARTIFACTS = 256
MAX_ROWS = 10000
MAX_BATCHES = 128
MAX_TIME_POINTS = 512
MAX_RECORDS = 128
MAX_ITEMS = 20000
MAX_TEXT = 4096
MAX_DEPTH = 32
MAX_NUMBER = 1e100
MAX_MEASUREMENT = 1e12
MAX_TIME = 1e6
MAX_EXTRAPOLATION = 10
BETA_ITERATIONS = 1000
SOLVER_ITERATIONS = 100
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
    r"shelf[\s-]*life|expir\w*|product[\s-]+(?:quality|safety)|"
    r"physical[\s-]+validity|patient[\s-]+benefit\w*)\b", re.I,
)
ASSERTION = re.compile(r"\b(?:supported|replicated|suggestive|significan\w*)\b", re.I)
NON_EVIDENCE = re.compile(r"review|approv|comput|numer|arithmet|result-v1|agreement|truth|physical|clinic", re.I)


def _require(condition, code, message):
    if not condition:
        raise ValueError(f"{code}: {message}")


def _text(value, label):
    _require(type(value) is str and 0 < len(value) <= MAX_TEXT and bool(value.strip())
             and not any(0xD800 <= ord(c) <= 0xDFFF for c in value),
             "invalid-record", f"{label} must be bounded nonempty text")
    return value


def _number(value, label, low=-MAX_MEASUREMENT, high=MAX_MEASUREMENT, integer=False):
    valid = type(value) is int if integer else type(value) in (int, float)
    _require(valid and low <= value <= high and math.isfinite(value),
             "invalid-record", f"{label} has invalid numeric type or range")
    return value


def _boolean(value, label):
    _require(type(value) is bool, "invalid-record", f"{label} must be boolean")
    return value


def _fields(value, fields, label):
    expected = fields.split() if type(fields) is str else fields
    _require(type(value) is dict and len(value) == len(expected) and set(value) == set(expected),
             "invalid-record", f"{label} fields differ from its pack-local schema")
    return value


def _list(value, label, limit, empty=False):
    _require(type(value) is list, "invalid-record", f"{label} must be a list")
    _require(len(value) <= limit, "input-limit", f"{label} exceeds its count limit")
    _require(empty or bool(value), "invalid-record", f"{label} must not be empty")
    return value


def _names(value, label, limit, empty=False):
    value = _list(value, label, limit, empty)
    for item in value:
        _text(item, label)
    _require(len(set(value)) == len(value), "invalid-record", f"duplicate {label}")
    return value


def _record(value, schema, fields):
    _fields(value, "schema fixture " + fields, schema)
    _require(value["schema"] == schema and value["fixture"] == "synthetic fixture",
             "invalid-record", "named schema and synthetic fixture label required")
    return value


def _pairs(pairs):
    _require(len(pairs) <= MAX_ITEMS, "input-limit", "too many object fields")
    result = {}
    for key, value in pairs:
        _text(key, "JSON key")
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


def _json(raw, allowance):
    _require(1 + raw.count(b",") + sum(1 for _ in re.finditer(rb"[\[{](?=\s*[^\s\]}])", raw)) <= allowance,
             "input-limit", "bundle JSON value allowance exceeded before parsing")
    try:
        root = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=_constant, parse_int=_int, parse_float=_float)
        _require(type(root) is dict, "invalid-json", "JSON root must be an object")
        pending = [(root, 0)]
        count = 0
        while pending:
            value, depth = pending.pop()
            count += 1
            _require(count <= allowance, "input-limit", "bundle JSON value allowance exceeded")
            _require(depth <= MAX_DEPTH, "invalid-json", "JSON nesting limit exceeded")
            if type(value) in (dict, list):
                _require(len(value) <= MAX_ITEMS, "input-limit", "too many JSON entries")
                children = value.items() if type(value) is dict else enumerate(value)
                for key, child in children:
                    if type(key) is str:
                        _text(key, "JSON key")
                    pending.append((child, depth + 1))
            elif type(value) is str:
                _require(len(value) <= MAX_TEXT and not any(0xD800 <= ord(c) <= 0xDFFF for c in value),
                         "input-limit", "JSON string limit exceeded")
        return root, count
    except (UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError("invalid-json: bounded finite UTF-8 JSON object required") from error
    except json.JSONDecodeError as error:
        raise ValueError("invalid-json: malformed JSON") from error


def _relative(value):
    value = _text(value, "artifact path")
    path = PurePosixPath(value)
    _require(not path.is_absolute() and path.as_posix() == value and value != "."
             and ".." not in path.parts and "\\" not in value and ":" not in value
             and all(ord(c) >= 32 for c in value),
             "input-path", "canonical bundle-relative artifact path required")
    return path


def _signature(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _open_root(root):
    """Pin every ancestor through descriptors and retain the entire identity chain."""
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
    descriptor = os.open(root.anchor, flags)
    try:
        opened = os.fstat(descriptor)
        identities = [(opened.st_dev, opened.st_ino)]
        for part in root.parts[1:]:
            before = os.lstat(part, dir_fd=descriptor)
            _require(stat.S_ISDIR(before.st_mode), "input-root", "bundle ancestors must be real directories")
            child = os.open(part, flags, dir_fd=descriptor)
            try:
                opened = os.fstat(child)
                _require(stat.S_ISDIR(opened.st_mode)
                         and (before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino),
                         "input-root", "bundle ancestor changed during pinning")
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
        self.total_bytes = 0
        self.nodes = 0
        self.rechecked = None
        try:
            self.fd, self.identities = _open_root(root)
        except OSError as error:
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
                before = os.lstat(part, dir_fd=directory)
                _require(stat.S_ISDIR(before.st_mode), "input-file", "symlinked artifact component")
                directory = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
                opened_dirs.append(directory)
                actual = os.fstat(directory)
                _require((actual.st_dev, actual.st_ino) == (before.st_dev, before.st_ino),
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
                    _require(signature == self.snapshots[name][1], "input-changed", "input replaced during validation")
                cached = self.cache.get(identity)
                if cached is not None:
                    _require(signature == cached[1], "input-changed", "cached input changed")
                    if self.rechecked is None or identity in self.rechecked:
                        return cached[0], signature
                if self.rechecked is None:
                    _require(self.total_bytes + actual.st_size <= MAX_TOTAL_BYTES,
                             "input-limit", "aggregate raw byte allowance exceeded")
                raw = handle.read(min(MAX_BYTES, actual.st_size) + 1)
                after = os.fstat(handle.fileno())
            _require(len(raw) == actual.st_size and len(raw) <= MAX_BYTES
                     and _signature(actual) == _signature(after),
                     "input-file", "input grew or changed during bounded read")
            return raw, signature
        except (OSError, UnicodeError) as error:
            raise ValueError("input-file: unavailable input or symlinked component") from error
        finally:
            for descriptor in reversed(opened_dirs):
                os.close(descriptor)

    def load(self, name, digest=None, parse=True):
        _relative(name)
        if name not in self.snapshots:
            _require(len(self.snapshots) < MAX_ARTIFACTS, "input-limit", "too many input artifacts")
            raw, signature = self._read(name)
            identity = signature[:2]
            if identity not in self.cache:
                self.cache[identity] = [raw, signature, hashlib.sha256(raw).hexdigest(), None]
                self.total_bytes += len(raw)
            self.snapshots[name] = self.cache[identity]
        entry = self.snapshots[name]
        if digest is not None:
            _require(type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
                     and digest == entry[2], "input-hash", "artifact hash differs from parsed bytes")
        if not parse:
            return entry[2]
        if entry[3] is None:
            entry[3], count = _json(entry[0], MAX_JSON_VALUES - self.nodes)
            self.nodes += count
        return entry[3]

    def artifact(self, descriptor, parse=True):
        _fields(descriptor, "path sha256", "artifact identity")
        _require(type(descriptor["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", descriptor["sha256"]) is not None,
                 "input-hash", "artifact needs a lowercase 64-hex SHA-256")
        return self.load(descriptor["path"], descriptor["sha256"], parse)

    def _check_root(self):
        descriptor, identities = _open_root(self.root)
        try:
            _require(identities == self.identities, "input-root", "bundle ancestor identity chain changed")
        finally:
            os.close(descriptor)

    def finish(self):
        try:
            self._check_root()
            self.rechecked = set()
            for name, (_, signature, digest, _) in self.snapshots.items():
                raw, current = self._read(name)
                _require(current == signature and hashlib.sha256(raw).hexdigest() == digest,
                         "input-changed", "input hash changed during validation")
                self.rechecked.add(current[:2])
            self._check_root()
        except OSError as error:
            raise ValueError("input-root: bundle ancestor unavailable at final recheck") from error
        finally:
            self.rechecked = None


def _protocol(value):
    _record(value, "stability-shelf-life-protocol-v1", "attribute units time_unit specification_limit direction "
            "storage_condition time_points batches model poolability_rule alpha confidence_level "
            "extrapolation_multiple minimum_batches minimum_time_points")
    for key in ("attribute", "units", "time_unit", "storage_condition", "direction", "model", "poolability_rule"):
        _text(value[key], key)
    _number(value["specification_limit"], "specification_limit")
    _require(value["direction"] in {"lower", "upper"}, "invalid-record", "specification direction must be lower or upper")
    _require(value["model"] == "linear-in-time" and value["poolability_rule"] == "slope-then-intercept-else-individual",
             "unsupported-model", "frozen linear model and sequential F tests required")
    _number(value["alpha"], "alpha", 0, 1)
    _require(0 < value["alpha"] < 1, "invalid-record", "poolability alpha must lie strictly between zero and one")
    _number(value["confidence_level"], "confidence_level", 0, 1)
    _require(value["confidence_level"] == 0.95, "confidence-level", "one-sided 95 percent bound required")
    _number(value["extrapolation_multiple"], "extrapolation_multiple", 1, MAX_EXTRAPOLATION)
    _number(value["minimum_batches"], "minimum_batches", 3, MAX_BATCHES, True)
    _number(value["minimum_time_points"], "minimum_time_points", 3, MAX_TIME_POINTS, True)
    batches = _names(value["batches"], "batches", MAX_BATCHES)
    _require(len(batches) >= value["minimum_batches"], "insufficient-batches", "below frozen batch minimum")
    times = _list(value["time_points"], "time points", MAX_TIME_POINTS)
    for time in times:
        _number(time, "time point", 0, MAX_TIME)
    _require(len(times) >= value["minimum_time_points"], "insufficient-time-points", "below frozen time point minimum")
    _require(times[0] == 0, "missing-baseline", "time zero baseline required")
    _require(all(left < right for left, right in zip(times, times[1:])), "time-order", "time points must increase strictly")
    return value


def _data(value, protocol):
    _record(value, "stability-shelf-life-data-v1", "rows")
    rows = _list(value["rows"], "measurement rows", MAX_ROWS)
    groups = {batch: [] for batch in protocol["batches"]}
    seen = set()
    censored = False
    for row in rows:
        _fields(row, "batch time result units censored quantification_limit", "measurement")
        batch = _text(row["batch"], "batch")
        _require(batch in groups, "batch-identity", "unknown batch")
        time = _number(row["time"], "time", 0, MAX_TIME)
        _require((batch, time) not in seen, "duplicate-measurement", "batch and time identify one measurement")
        seen.add((batch, time))
        _require(not groups[batch] or groups[batch][-1]["time"] < time, "time-order", "batch times must increase strictly")
        _require(_text(row["units"], "units") == protocol["units"], "unit-mismatch", "attribute units differ")
        flag = _boolean(row["censored"], "censored")
        if flag:
            _require(row["result"] is None, "below-quantification-zero", "censored result must be null, never zero or a substituted number")
            _number(row["quantification_limit"], "quantification_limit", 0, MAX_MEASUREMENT)
            censored = True
        else:
            _number(row["result"], "result")
            _require(row["quantification_limit"] is None, "invalid-record", "uncensored result must not carry a censoring limit")
        groups[batch].append(row)
    present = [group for group in groups.values() if group]
    _require(len(present) >= protocol["minimum_batches"], "insufficient-batches", "measured batches below frozen minimum")
    _require(all(group and group[0]["time"] == 0 for group in groups.values()), "missing-baseline", "each batch needs time zero")
    _require(all(len(group) >= protocol["minimum_time_points"] for group in groups.values()),
             "insufficient-time-points", "measured time points below frozen minimum")
    _require(all([row["time"] for row in group] == protocol["time_points"] for group in groups.values()),
             "time-grid", "measurements must match the frozen batch and time grid")
    _require(not censored, "censored-fit-unavailable", "censored observations preserved; this OLS reference cannot fit them")
    return groups


def _beta_fraction(a, b, x):
    tiny = 1e-300
    def bounded(value):
        return value if abs(value) >= tiny else math.copysign(tiny, value)
    c = 1.0
    d = 1 / bounded(1 - (a + b) * x / (a + 1))
    h = d
    for m in range(1, BETA_ITERATIONS + 1):
        for numerator in (m * (b - m) * x / ((a + 2*m - 1) * (a + 2*m)),
                          -(a + m) * (a + b + m) * x / ((a + 2*m) * (a + 2*m + 1))):
            d = 1 / bounded(1 + numerator * d)
            c = bounded(1 + numerator / c)
            change = d * c
            h *= change
        if abs(change - 1) < 2e-14:
            return h
    raise ValueError("numeric-convergence: incomplete beta iteration limit reached")


def _beta(x, a, b):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    factor = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                      + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1) / (a + b + 2):
        value = factor * _beta_fraction(a, b, x) / a
    else:
        value = 1 - factor * _beta_fraction(b, a, 1 - x) / b
    _require(math.isfinite(value), "numeric-convergence", "non-finite beta result")
    return min(1.0, max(0.0, value))


def t_quantile(probability, df):
    """Invert the Student t CDF through regularized beta and bounded bisection."""
    _number(probability, "probability", 0, 1)
    _number(df, "degrees of freedom", 1, MAX_ROWS, True)
    _require(0.5 < probability < 1, "invalid-record", "upper t quantile needs probability between one half and one")
    low, high = 0.0, 1.0
    def cdf(value):
        return 1 - 0.5 * _beta(df / (df + value * value), df / 2, 0.5)
    for _ in range(SOLVER_ITERATIONS):
        if cdf(high) >= probability:
            break
        high *= 2
    else:
        raise ValueError("numeric-convergence: t quantile bracket unavailable")
    for _ in range(SOLVER_ITERATIONS):
        middle = (low + high) / 2
        if cdf(middle) < probability:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def _fit(rows):
    n = len(rows)
    _require(n >= 3, "degenerate-regression", "at least three measured points required")
    x_mean = math.fsum(row["time"] for row in rows) / n
    y_mean = math.fsum(row["result"] for row in rows) / n
    sxx = math.fsum((row["time"] - x_mean) ** 2 for row in rows)
    _require(sxx > 0, "degenerate-regression", "zero time variance")
    slope = math.fsum((row["time"] - x_mean) * (row["result"] - y_mean) for row in rows) / sxx
    intercept = y_mean - slope * x_mean
    sse = math.fsum((row["result"] - y_mean - slope * (row["time"] - x_mean)) ** 2 for row in rows)
    _require(sse > 0 and math.isfinite(sse) and sse / (n - 2) > 0, "degenerate-regression", "zero or non-finite residual variance")
    return {"n": n, "df": n - 2, "slope": slope, "intercept": intercept,
            "x_mean": x_mean, "sxx": sxx, "sse": sse, "mse": sse / (n - 2)}


def _f_test(reduced_sse, full_sse, df1, df2):
    difference = reduced_sse - full_sse
    _require(difference >= -1e-10 * max(reduced_sse, full_sse), "numeric-convergence", "nested residual sums reversed")
    f_value = max(0.0, difference) / df1 / (full_sse / df2)
    p_value = _beta(df2 / (df2 + df1 * f_value), df2 / 2, df1 / 2)
    return {"f": f_value, "df1": df1, "df2": df2, "p": p_value}


def _crossing(fit, protocol, limit, quantiles):
    horizon = protocol["time_points"][-1] * protocol["extrapolation_multiple"]
    q = quantiles[fit["df"]]
    def margin(time):
        mean = fit["intercept"] + fit["slope"] * time
        error = q * math.sqrt(fit["mse"] * (1 / fit["n"] + (time - fit["x_mean"]) ** 2 / fit["sxx"]))
        return (mean - limit if protocol["direction"] == "lower" else limit - mean) - error
    if margin(0) <= 0:
        return 0.0
    # The signed safe margin is concave: positive endpoints exclude interior crossings.
    if margin(horizon) > 0:
        return "not-reached-within-observed-range"
    low, high = 0.0, horizon
    for _ in range(SOLVER_ITERATIONS):
        middle = (low + high) / 2
        if margin(middle) > 0:
            low = middle
        else:
            high = middle
    return high


def _compute_stability(data, protocol, specification_limit=None):
    """Compute sequential ANCOVA F tests and pointwise one-sided mean-bound crossings.

    Unequal slopes or unequal intercepts select individual ordinary least squares
    fits. Crossings are descriptive arithmetic, conditional on linear-model assumptions.
    """
    protocol = _protocol(protocol)
    groups = _data(data, protocol)
    limit = protocol["specification_limit"] if specification_limit is None else _number(specification_limit, "specification_limit")
    fits = {batch: _fit(rows) for batch, rows in groups.items()}
    n = sum(fit["n"] for fit in fits.values())
    count = len(fits)
    full_sse = math.fsum(fit["sse"] for fit in fits.values())
    common_slope = math.fsum(fit["slope"] * fit["sxx"] for fit in fits.values()) / math.fsum(fit["sxx"] for fit in fits.values())
    common_sse = math.fsum(fit["sse"] + fit["sxx"] * (fit["slope"] - common_slope) ** 2 for fit in fits.values())
    slope_test = _f_test(common_sse, full_sse, count - 1, n - 2*count)
    intercept_test = "not-tested-after-slope-rejection"
    selected = "individual"
    selected_fits = fits
    if slope_test["p"] >= protocol["alpha"]:
        pooled = _fit([row for rows in groups.values() for row in rows])
        intercept_test = _f_test(pooled["sse"], common_sse, count - 1, n - count - 1)
        if intercept_test["p"] >= protocol["alpha"]:
            selected = "pooled"
            selected_fits = {"pooled": pooled}
    quantiles = {df: t_quantile(protocol["confidence_level"], df) for df in {fit["df"] for fit in selected_fits.values()}}
    crossings = {batch: _crossing(fit, protocol, limit, quantiles) for batch, fit in selected_fits.items()}
    reached = [time for time in crossings.values() if type(time) in (int, float)]
    return {"selected_model": selected, "poolability": {"slope": slope_test, "intercept": intercept_test},
            "per_batch": fits, "selected_fits": selected_fits, "n": n,
            "df": {batch: fit["df"] for batch, fit in selected_fits.items()},
            "bound": {"kind": "mean-response", "sides": "one-sided", "confidence_level": protocol["confidence_level"]},
            "t_quantiles": {str(df): value for df, value in quantiles.items()},
            "observed_duration": protocol["time_points"][-1],
            "maximum_time": protocol["time_points"][-1] * protocol["extrapolation_multiple"],
            "crossings": crossings, "earliest_crossing": min(reached) if reached else "not-reached-within-observed-range"}


def compute_stability(data, protocol, specification_limit=None):
    """Return bounded reference arithmetic or a labelled numerical refusal."""
    try:
        return _compute_stability(data, protocol, specification_limit)
    except ArithmeticError as error:
        raise ValueError("numeric-convergence: finite nondegenerate arithmetic required") from error


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
                 "claim-overreach", "claim exceeds offline arithmetic evidence")
        _require(status in STATUSES, "invalid-record", "unknown claim status")
        ids = _names(claim["evidence"], "claim evidence", MAX_RECORDS, True)
        _require(ids or status == "unavailable", "missing-evidence", "empty evidence requires unavailable")
        _require(status != "unavailable" or not ASSERTION.search(text),
                 "unavailable-positive", "unavailable claim asserts positive evidence")
        for identity in ids:
            _require(identity in evidence, "missing-evidence", "unknown evidence identity")
            record = evidence[identity]
            _require("unavailable" not in (record["kind"], record["result"]) or status == "unavailable",
                     "unavailable-evidence", "any unavailable citation requires unavailable status")
            _require(status not in POSITIVE or not any(NON_EVIDENCE.search(record[key]) for key in ("kind", "result")),
                     "non-evidence-support", "review approval and computed records cannot support positive claims")
        _require(status != "replicated", "claim-replication", "one synthetic fixture cannot establish replication")


def _same_number(value, expected, label):
    _number(value, label)
    _require(math.isclose(value, expected, rel_tol=1e-9, abs_tol=1e-10), "reported-number", f"reported {label} differs from reference")


def validate_stability_shelf_life_pack(bundle):
    """Validate one hash-bound synthetic bundle, return JSON, and write nothing."""
    try:
        value = _text(os.fspath(bundle), "bundle path")
        _require(all(ord(c) >= 32 for c in value), "input-path", "control character in bundle path")
        path = Path(os.path.abspath(value))
    except (TypeError, ValueError) as error:
        raise ValueError("input-path: invalid bundle path") from error
    store = _Bundle(path.parent)
    try:
        pack = _record(store.load(path.name), "stability-shelf-life-pack-v1",
                       "stages protocol frozen_protocol_sha256 frozen_before_results_read data report evidence")
        _require(_names(pack["stages"], "stages", len(STAGES)) == list(STAGES), "stage-order", "five ordered stages required")
        protocol = _protocol(store.artifact(pack["protocol"]))
        _require(_text(pack["frozen_protocol_sha256"], "frozen_protocol_sha256") == pack["protocol"]["sha256"]
                 and _boolean(pack["frozen_before_results_read"], "frozen_before_results_read"),
                 "rule-freeze", "protocol must be hash-frozen before results admission")
        report = _record(store.artifact(pack["report"]), "stability-shelf-life-report-v1",
                         "protocol_sha256 poolability_tested selected_model bound_sides bound_type specification_limit "
                         "exploratory evaluation_time summary headline claims")
        _require(_text(report["protocol_sha256"], "protocol_sha256") == pack["protocol"]["sha256"],
                 "rule-freeze", "report refers to another frozen protocol")
        _require(_boolean(report["poolability_tested"], "poolability_tested"),
                 "poolability-required", "batch pooling requires sequential slope and intercept F tests")
        _require(_text(report["bound_sides"], "bound_sides") == "one-sided", "one-sided-required", "two-sided bound is not the frozen one-sided bound")
        _require(_text(report["bound_type"], "bound_type") == "mean-response", "mean-bound-required", "prediction bound is not a mean-response bound")
        limit = _number(report["specification_limit"], "specification_limit")
        exploratory = _boolean(report["exploratory"], "exploratory")
        _require(limit == protocol["specification_limit"] or exploratory,
                 "post-outcome-specification", "changed specification requires an exploratory label")
        horizon = protocol["time_points"][-1] * protocol["extrapolation_multiple"]
        _require(_number(report["evaluation_time"], "evaluation_time", 0, MAX_TIME * MAX_EXTRAPOLATION) <= horizon,
                 "extrapolation-limit", "reported horizon exceeds the frozen extrapolation limit")
        headline = _text(report["headline"], "headline")
        _require(not OVERREACH.search(headline), "claim-overreach", "headline exceeds offline arithmetic evidence")
        descriptors = _list(pack["evidence"], "evidence artifacts", MAX_RECORDS, True)
        own_paths = {path.name}
        own_hashes = {store.snapshots[path.name][2]}
        for descriptor in (pack["protocol"], pack["data"], pack["report"], *descriptors):
            _fields(descriptor, "path sha256", "artifact identity")
            own_paths.add(str(_relative(descriptor["path"])))
            own_hashes.add(_text(descriptor["sha256"], "sha256"))
        evidence = {}
        for descriptor in descriptors:
            document = _record(store.artifact(descriptor), "stability-shelf-life-evidence-v1", "records")
            records = _list(document["records"], "evidence records", MAX_RECORDS, True)
            _require(len(evidence) + len(records) <= MAX_RECORDS, "input-limit", "too many evidence records")
            for record in records:
                _fields(record, "id kind result origin source", "evidence record")
                identity = _text(record["id"], "evidence id")
                _require(identity not in evidence, "invalid-record", "duplicate evidence id")
                for key in ("kind", "result", "origin"):
                    _text(record[key], key)
                _require(record["origin"] in {"internal", "external", "independent", "preregistered"}, "invalid-record", "unknown evidence origin")
                digest = store.artifact(record["source"], parse=False)
                if record["origin"] != "internal":
                    _require(record["source"]["path"] not in own_paths and digest not in own_hashes,
                             "external-alias", "independence label aliases this study's artifacts")
                evidence[identity] = record
        _claims(report["claims"], evidence)
        result = compute_stability(store.artifact(pack["data"]), protocol, limit)
        _require(_text(report["selected_model"], "selected_model") == result["selected_model"],
                 "poolability-decision", "reported pooling differs from the sequential F tests")
        _same_number(report["evaluation_time"], result["maximum_time"], "evaluation_time")
        summary = _fields(report["summary"], "n df earliest_crossing", "summary")
        _number(summary["n"], "n", 1, MAX_ROWS, True)
        _require(summary["n"] == result["n"], "reported-number", "reported n differs")
        _fields(summary["df"], tuple(result["df"]), "degrees of freedom")
        for batch, expected in result["df"].items():
            _number(summary["df"][batch], "df", 1, MAX_ROWS, True)
            _require(summary["df"][batch] == expected, "reported-number", "reported df differs")
        expected = result["earliest_crossing"]
        if type(expected) is str:
            _require(summary["earliest_crossing"] == expected, "crossing-not-reached", "bound does not cross inside frozen horizon")
        else:
            _same_number(summary["earliest_crossing"], expected, "earliest_crossing")
        store.finish()
        return {"schema": "stability-shelf-life-result-v1", "fixture": "synthetic fixture", "status": "arithmetic-only",
                "review": "unavailable", "stages": list(STAGES), "exploratory": exploratory,
                "inputs": [{"path": name, "sha256": entry[2]} for name, entry in sorted(store.snapshots.items())],
                "computation": result, "claims": report["claims"],
                "limitations": ["Synthetic fixtures verify arithmetic only.",
                                "Hashes cannot establish historical rule freeze or true source independence.",
                                "Pointwise mean bounds assume independent homoscedastic normal linear residuals; assumptions are unverified.",
                                "Censored OLS is unavailable; inputs are retained without substitution.",
                                "Independent review and physical validity remain unavailable."]}
    finally:
        store.close()
