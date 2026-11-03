"""Offline synthetic 4PL arithmetic and immutable, read-only bundle admission."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import statistics


STAGES = ("01-freeze", "02-qc", "03-fit", "04-summary", "05-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_TOTAL_VALUES = 4_000_000
MAX_ARTIFACTS = 128
MAX_ITEMS = 20_000
MAX_WELLS = 384
MAX_STANDARDS = 32
MAX_CLAIMS = 128
MAX_RECORDS = 128
MAX_TEXT = 4096
MAX_DEPTH = 32
MAX_ITERATIONS = 200
MAX_NUMBER = 1e100
WORDING_FAMILIES = (
    "caus", "mechanis", "therap", "clinic", "efficac", "effective", "treat", "cure",
    "prevent", "recommend", "prescri", "bind", "affinit", "inhibit", "activat",
    "regulat", "driv", "induc",
)
OVERREACH = re.compile(
    r"\b(?:" + "|".join(word + r"\w*" for word in WORDING_FAMILIES)
    + r"|diagnos\w*|patient\w*|truth|physical[\s-]+validity|cut[\s-]*off\w*)\b", re.I,
)
NON_EVIDENCE = re.compile(r"review|approv|comput|numer|agreement|truth|physical|clinic", re.I)
UNAVAILABLE_POSITIVE = re.compile(r"\b(?:supported|replicated|suggestive|significan\w*)\b", re.I)
POSITIVE = {"supported", "replicated", "suggestive"}
STATUSES = POSITIVE | {"planned", "conflicting", "unsupported", "withdrawn", "unavailable"}


def _require(condition, finding, message):
    if not condition:
        raise ValueError(f"{finding}: {message}")


def _obj(value, fields, label):
    _require(type(value) is dict and set(value) == set(fields.split()),
             "invalid-record", f"{label} has missing, unknown or malformed fields")
    return value


def _record(value, schema, fields):
    _obj(value, "schema fixture " + fields, schema)
    _require(value["schema"] == schema and value["fixture"] == "synthetic fixture",
             "invalid-record", f"expected {schema} synthetic fixture")
    return value


def _text(value, label):
    _require(type(value) is str and 0 < len(value) <= MAX_TEXT and bool(value.strip()),
             "invalid-record", f"{label} must be bounded nonempty text")
    return value


def _items(value, label, limit, empty=False):
    _require(type(value) is list and (empty or bool(value)), "invalid-record", f"{label} must be a list")
    _require(len(value) <= limit, "input-limit", f"{label} exceeds {limit}")
    return value


def _number(value, label, low=-MAX_NUMBER, high=MAX_NUMBER, integer=False):
    valid = type(value) is int if integer else type(value) in (int, float)
    _require(valid and low <= value <= high and math.isfinite(value),
             "invalid-record", f"{label} must have the declared finite numeric type and bounds")
    return value


def _bool(value, label):
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


def _integer(value):
    _require(len(value.lstrip("-")) <= 101, "invalid-json", "huge JSON integer")
    return _number(int(value), "JSON integer")


def _json(raw, allowance):
    count = 1 + raw.count(b",") + sum(1 for _ in re.finditer(rb"[\[{](?=\s*[^\s\]}])", raw))
    _require(count <= allowance, "input-limit", "aggregate JSON value allowance exceeded")
    try:
        root = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_int=_integer,
                          parse_float=lambda v: _number(float(v), "JSON number"), parse_constant=_constant)
        _require(type(root) is dict, "invalid-json", "JSON root must be an object")
        pending = [(root, 0)]
        while pending:
            value, depth = pending.pop()
            _require(depth <= MAX_DEPTH, "invalid-json", "JSON nesting exceeds limit")
            if type(value) is dict:
                _require(len(value) <= MAX_ITEMS, "input-limit", "too many JSON fields")
                for key, child in value.items():
                    _require(len(key) <= MAX_TEXT, "input-limit", "JSON key too long")
                    pending.append((child, depth + 1))
            elif type(value) is list:
                _require(len(value) <= MAX_ITEMS, "input-limit", "too many JSON items")
                pending.extend((child, depth + 1) for child in value)
            elif type(value) is str:
                _require(len(value) <= MAX_TEXT, "input-limit", "JSON string too long")
        return root, count
    except (UnicodeError, RecursionError, OverflowError, json.JSONDecodeError) as error:
        raise ValueError("invalid-json: bounded finite UTF-8 JSON object required") from error


def _relative(value):
    value = _text(value, "artifact path")
    path = PurePosixPath(value)
    _require(not path.is_absolute() and ".." not in path.parts and "\\" not in value
             and path.as_posix() == value and value != "." and ":" not in value
             and all(ord(c) >= 32 for c in value), "input-path", "canonical bundle-relative path required")
    return path


def _signature(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _open_root(root):
    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open(root.anchor, flags)
    try:
        opened = os.fstat(descriptor)
        chain = [(opened.st_dev, opened.st_ino)]
        for part in root.parts[1:]:
            before = os.lstat(part, dir_fd=descriptor)
            _require(stat.S_ISDIR(before.st_mode), "input-root", "symlinked root ancestor")
            child = os.open(part, flags, dir_fd=descriptor)
            try:
                opened = os.fstat(child)
                _require(stat.S_ISDIR(opened.st_mode) and
                         (opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino),
                         "input-root", "root ancestor replaced during pinning")
            except BaseException:
                os.close(child)
                raise
            os.close(descriptor)
            descriptor = child
            chain.append((opened.st_dev, opened.st_ino))
        return descriptor, chain
    except BaseException:
        os.close(descriptor)
        raise


class _Bundle:
    def __init__(self, path):
        self.path = Path(os.path.abspath(path))
        self.root = self.path.parent
        self.fd, self.chain = _open_root(self.root)
        self.paths = {}
        self.cache = {}
        self.bytes_read = 0
        self.values_read = 0

    def close(self):
        os.close(self.fd)

    def _read(self, name, rechecked=None):
        relative = _relative(name)
        directory = os.dup(self.fd)
        flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
        try:
            for part in relative.parts[:-1]:
                before = os.lstat(part, dir_fd=directory)
                _require(stat.S_ISDIR(before.st_mode), "input-file", "symlinked artifact component")
                child = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
                try:
                    opened = os.fstat(child)
                    _require((opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino),
                             "input-changed", "artifact directory replaced")
                except BaseException:
                    os.close(child)
                    raise
                os.close(directory)
                directory = child
            before = os.lstat(relative.name, dir_fd=directory)
            _require(stat.S_ISREG(before.st_mode) and before.st_size <= MAX_BYTES,
                     "input-file", "regular file at most 64 MiB required")
            descriptor = os.open(relative.name, flags, dir_fd=directory)
            with os.fdopen(descriptor, "rb") as handle:
                opened = os.fstat(handle.fileno())
                signature = _signature(opened)
                _require(stat.S_ISREG(opened.st_mode) and opened.st_size <= MAX_BYTES
                         and signature == _signature(before), "input-file", "input changed before open")
                identity = signature[:2]
                cached = self.cache.get(identity)
                if rechecked is not None:
                    _require(signature == self.paths[name][2], "input-changed", "input replaced")
                if cached is not None:
                    _require(signature == cached[2], "input-changed", "cached artifact changed")
                    if rechecked is None or identity in rechecked:
                        return None, signature
                if rechecked is None:
                    _require(self.bytes_read + opened.st_size <= MAX_TOTAL_BYTES,
                             "input-limit", "aggregate raw bytes exceed limit")
                raw = handle.read(opened.st_size + 1)
                after = os.fstat(handle.fileno())
            _require(len(raw) <= MAX_BYTES and len(raw) == opened.st_size and signature == _signature(after),
                     "input-changed", "input grew or changed during bounded read")
            return raw, signature
        finally:
            os.close(directory)

    def load(self, name, digest=None):
        _relative(name)
        if name not in self.paths:
            _require(len(self.paths) < MAX_ARTIFACTS, "input-limit", "too many artifact paths")
            raw, signature = self._read(name)
            identity = signature[:2]
            if raw is not None:
                value, count = _json(raw, MAX_TOTAL_VALUES - self.values_read)
                self.cache[identity] = (value, hashlib.sha256(raw).hexdigest(), signature)
                self.bytes_read += len(raw)
                self.values_read += count
            self.paths[name] = self.cache[identity]
        value, actual, _ = self.paths[name]
        if digest is not None:
            _require(type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
                     and actual == digest, "input-hash", "artifact hash differs from parsed bytes")
        return value

    def artifact(self, identity):
        _obj(identity, "path sha256", "artifact identity")
        _require(type(identity["sha256"]) is str and
                 re.fullmatch(r"[0-9a-f]{64}", identity["sha256"]) is not None,
                 "input-hash", "lowercase SHA-256 required")
        return self.load(identity["path"], identity["sha256"])

    def _check_root(self):
        descriptor, chain = _open_root(self.root)
        try:
            _require(chain == self.chain, "input-root", "root or ancestor replaced")
        finally:
            os.close(descriptor)

    def finish(self):
        self._check_root()
        checked = set()
        for name, (_, digest, signature) in self.paths.items():
            raw, current = self._read(name, checked)
            _require(signature == current and (raw is None or hashlib.sha256(raw).hexdigest() == digest),
                     "input-changed", "input replaced or modified")
            checked.add(current[:2])
        self._check_root()


def _parameters(values):
    _items(values, "4PL parameters [a,d,c,b]", 4)
    _require(len(values) == 4, "curve-parameters", "four parameters required")
    for value in values:
        _number(value, "4PL parameter", 0, 1e6)
    a, d, c, b = values
    _require(0 <= a < d <= 100 and 1e-12 <= c <= 1e6 and 1e-6 <= b <= 20,
             "curve-parameters", "increasing 4PL requires 0<=a<d, c>0 and b>0 within bounds")
    return values


def _curve(x, params):
    a, d, c, b = params
    z = b * (math.log(c) - math.log(x))
    s = math.exp(-z) / (1 + math.exp(-z)) if z >= 0 else 1 / (1 + math.exp(z))
    return a + (d - a) * s


def four_pl(x, parameters):
    """Increasing y=a+(d-a)/(1+(c/x)**b); parameters ordered [a,d,c,b]."""
    _number(x, "standard concentration", 1e-12, 1e6)
    return _curve(x, _parameters(parameters))


def _inverse(y, params):
    a, d, c, b = params
    _require(a < y < d, "inverse-undefined", "response must lie strictly between fitted asymptotes")
    value = c * math.exp((math.log(y - a) - math.log(d - y)) / b)
    _require(math.isfinite(value) and value > 0, "inverse-undefined", "inverse must be positive and finite")
    return value


def _jacobian(x, params):
    a, d, c, b = params
    s = (_curve(x, params) - a) / (d - a)
    common = (d - a) * s * (1 - s)
    return [1 - s, s, -common * b / c, -common * (math.log(c) - math.log(x))]


def _solve(matrix, rhs):
    rows = [list(row) + [value] for row, value in zip(matrix, rhs)]
    scale = max(abs(v) for row in matrix for v in row)
    _require(scale > 0, "degenerate-fit", "zero information matrix")
    for column in range(4):
        pivot = max(range(column, 4), key=lambda i: abs(rows[i][column]))
        _require(abs(rows[pivot][column]) > scale * 1e-14, "degenerate-fit", "singular information matrix")
        rows[column], rows[pivot] = rows[pivot], rows[column]
        divisor = rows[column][column]
        rows[column] = [v / divisor for v in rows[column]]
        for i in range(4):
            if i != column:
                factor = rows[i][column]
                rows[i] = [v - factor * w for v, w in zip(rows[i], rows[column])]
    return [row[4] for row in rows]


def _normal(xs, ys, params):
    residuals = [y - _curve(x, params) for x, y in zip(xs, ys)]
    jac = [_jacobian(x, params) for x in xs]
    matrix = [[math.fsum(row[i] * row[j] for row in jac) for j in range(4)] for i in range(4)]
    gradient = [math.fsum(row[i] * r for row, r in zip(jac, residuals)) for i in range(4)]
    return matrix, gradient, math.fsum(r * r for r in residuals)


def _fit(xs, ys, fitting):
    params = list(fitting["start"])
    damping = fitting["damping"]
    tolerance = fitting["tolerance"]
    converged = False
    iterations = 0
    for iterations in range(1, fitting["iteration_cap"] + 1):
        matrix, gradient, sse = _normal(xs, ys, params)
        if max(abs(v) for v in gradient) <= tolerance:
            converged = True
            break
        damped = [[v + (damping * max(matrix[i][i], 1e-12) if i == j else 0)
                   for j, v in enumerate(row)] for i, row in enumerate(matrix)]
        step = _solve(damped, gradient)
        trial = [p + delta for p, delta in zip(params, step)]
        try:
            _parameters(trial)
        except ValueError as error:
            if not str(error).startswith(("curve-parameters:", "invalid-record:")):
                raise
            damping *= 10
            continue
        _, _, trial_sse = _normal(xs, ys, trial)
        if trial_sse < sse:
            params = trial
            damping = max(damping / 3, 1e-12)
            if max(abs(v) / max(abs(p), 1) for v, p in zip(step, params)) <= tolerance:
                converged = True
                break
        else:
            damping *= 10
    _require(converged, "fit-not-converged", "frozen iteration cap reached; no interpolation permitted")
    matrix, _, sse = _normal(xs, ys, params)
    variance = sse / (len(xs) - 4)
    errors = []
    for i in range(4):
        unit = [float(j == i) for j in range(4)]
        diagonal = _solve(matrix, unit)[i]
        _require(diagonal > 0, "degenerate-fit", "undefined parameter uncertainty")
        errors.append(math.sqrt(variance * diagonal))
    return {"parameters": params, "standard_errors": errors, "converged": True,
            "iterations": iterations, "sse": sse, "degrees_of_freedom": len(xs) - 4}


def _band(value, label):
    _items(value, label, 2)
    _require(len(value) == 2, "invalid-record", f"{label} requires two bounds")
    for number in value:
        _number(number, label, 0, 1000)
    _require(value[0] <= 1 <= value[1], "invalid-record", f"{label} must contain one")
    return value


def _design(value):
    _record(value, "immunoassay-design-v1", "analyte units standards plate_map blank_rule parameterisation weighting fitting recovery_band maximum_cv parallelism_band standard_exclusion")
    for name in ("analyte", "units"):
        _text(value[name], name)
    _require(value["blank_rule"] in ("none", "subtract-mean"), "blank-rule", "unsupported blank handling")
    _require(value["parameterisation"] == "increasing-a-d-c-b" and value["weighting"] == "uniform",
             "curve-parameters", "only increasing constrained uniformly weighted 4PL is supported")
    _require(value["standard_exclusion"] == "none", "standard-exclusion", "all frozen standards must be fitted")
    fitting = _obj(value["fitting"], "method start tolerance iteration_cap damping", "fitting")
    _require(fitting["method"] == "levenberg-marquardt", "fit-method", "unsupported fitting method")
    _parameters(fitting["start"])
    _number(fitting["tolerance"], "tolerance", 1e-12, 1e-4)
    _number(fitting["iteration_cap"], "iteration cap", 1, MAX_ITERATIONS, True)
    _number(fitting["damping"], "initial damping", 1e-12, 1)
    _band(value["recovery_band"], "recovery band")
    _band(value["parallelism_band"], "parallelism band")
    _number(value["maximum_cv"], "maximum response CV percent", 0, 100)
    mapping = _items(value["plate_map"], "plate map", MAX_WELLS)
    standards = _items(value["standards"], "standards", MAX_STANDARDS)
    _require(len(standards) >= 5, "insufficient-standards", "at least five distinct standard levels required")
    known = {}
    previous = 0
    for standard in standards:
        _obj(standard, "id concentration replicates", "standard")
        name = _text(standard["id"], "standard ID")
        x = _number(standard["concentration"], "standard concentration", 1e-12, 1e6)
        _number(standard["replicates"], "standard replicates", 2, MAX_WELLS, True)
        _require(name not in known and x > previous, "standard-series", "unique ascending standard dilution series required")
        previous = x
        known[name] = standard
    wells = set()
    counts = {}
    for row in mapping:
        _obj(row, "well kind id dilution", "plate map row")
        well = _text(row["well"], "well ID")
        kind = _text(row["kind"], "well kind")
        name = _text(row["id"], "replicate ID")
        _number(row["dilution"], "dilution", 1, 1e6)
        _require(well not in wells, "duplicate-well", "well IDs must be unique")
        wells.add(well)
        _require(kind in ("blank", "standard", "sample"), "invalid-record", "unknown well kind")
        _require(kind == "sample" or row["dilution"] == 1, "invalid-record", "only samples can be diluted")
        if kind == "standard":
            _require(name in known, "standard-series", "standard absent from frozen series")
        key = (kind, name, row["dilution"])
        counts[key] = counts.get(key, 0) + 1
    _require(any(k[0] == "blank" for k in counts), "missing-blanks", "blanks required")
    _require(any(k[0] == "sample" for k in counts), "missing-samples", "unknown samples required")
    for key, count in counts.items():
        _require(count >= 2, "insufficient-replicates", "at least two replicates required per group")
    for name, standard in known.items():
        _require(counts.get(("standard", name, 1), 0) == standard["replicates"],
                 "plate-map", "frozen standard replicate count differs from map")
    return known


def _cv(values):
    mean = math.fsum(values) / len(values)
    deviation = statistics.stdev(values)
    _require(mean != 0 or deviation == 0, "degenerate-replicates", "CV undefined for a zero mean")
    return mean, 100 * deviation / abs(mean) if mean != 0 else 0.0


def _compute(plate, design):
    known = _design(design)
    _record(plate, "immunoassay-plate-v1", "analyte units wells")
    _require(plate["units"] == design["units"], "units-mismatch", "plate and frozen concentration units differ")
    _require(plate["analyte"] == design["analyte"], "analyte-mismatch", "plate and frozen analyte differ")
    rows = _items(plate["wells"], "responses", MAX_WELLS)
    responses = {}
    for row in rows:
        _obj(row, "well response", "response row")
        well = _text(row["well"], "well ID")
        _require(well not in responses, "duplicate-well", "response well IDs must be unique")
        responses[well] = _number(row["response"], "optical density", 0, 100)
    _require(set(responses) == {row["well"] for row in design["plate_map"]},
             "plate-map", "complete exact plate map required")
    blanks = [responses[row["well"]] for row in design["plate_map"] if row["kind"] == "blank"]
    blank_mean, blank_cv = _cv(blanks)
    offset = blank_mean if design["blank_rule"] == "subtract-mean" else 0
    grouped = {}
    for row in design["plate_map"]:
        if row["kind"] != "blank":
            key = (row["kind"], row["id"], row["dilution"])
            grouped.setdefault(key, []).append(responses[row["well"]] - offset)
    xs, ys = [], []
    for name, standard in known.items():
        values = grouped[("standard", name, 1)]
        xs.extend([standard["concentration"]] * len(values))
        ys.extend(values)
    _require(max(ys) > min(ys), "degenerate-fit", "standard responses have zero variance")
    fit = _fit(xs, ys, design["fitting"])
    standards = []
    for name, standard in known.items():
        mean, cv = _cv(grouped[("standard", name, 1)])
        back = _inverse(mean, fit["parameters"])
        ratio = back / standard["concentration"]
        cv_flag = cv > design["maximum_cv"]
        accepted = design["recovery_band"][0] <= ratio <= design["recovery_band"][1] and not cv_flag
        standards.append({"id": name, "concentration": standard["concentration"], "response_mean": mean,
                          "cv": cv, "cv_flag": cv_flag, "back_calculated": back,
                          "recovery_ratio": ratio, "accepted": accepted})
    accepted = [row["concentration"] for row in standards if row["accepted"]]
    _require(len(accepted) >= 2, "quantifiable-range", "at least two accepted standards required")
    low, high = min(accepted), max(accepted)
    lower_response, upper_response = [_curve(x, fit["parameters"]) for x in (low, high)]
    samples = []
    by_sample = {}
    for (kind, name, dilution), values in grouped.items():
        if kind != "sample":
            continue
        mean, cv = _cv(values)
        # Relative comparison only: small distinct responses must remain distinct.
        below = mean < lower_response and not math.isclose(mean, lower_response, rel_tol=1e-10, abs_tol=0)
        above = mean > upper_response and not math.isclose(mean, upper_response, rel_tol=1e-10, abs_tol=0)
        status = "below-range" if below else "above-range" if above else "in-range"
        concentration = None if below or above else min(high, max(low, _inverse(mean, fit["parameters"])))
        row = {"id": name, "dilution": dilution, "response_mean": mean, "cv": cv,
               "cv_flag": cv > design["maximum_cv"], "status": status, "concentration": concentration}
        samples.append(row)
        by_sample.setdefault(name, []).append(row)
    parallelism = []
    for name, rows in by_sample.items():
        rows = sorted(rows, key=lambda row: row["dilution"])
        eligible = len(rows) >= 2 and all(row["status"] == "in-range" and not row["cv_flag"] for row in rows)
        ratios = []
        if eligible:
            baseline = rows[0]["concentration"] * rows[0]["dilution"]
            ratios = [row["concentration"] * row["dilution"] / baseline for row in rows[1:]]
        passed = all(design["parallelism_band"][0] <= ratio <= design["parallelism_band"][1] for ratio in ratios)
        parallelism.append({"id": name, "ratios": ratios,
                            "status": "unavailable" if not eligible else "passed" if passed else "failed"})
    return {"fit": fit, "blank_mean": blank_mean, "blank_cv": blank_cv,
            "blank_cv_flag": blank_cv > design["maximum_cv"], "used_standards": list(known), "standards": standards,
            "quantifiable_range": [low, high], "samples": samples, "parallelism": parallelism,
            "qc_passed": blank_cv <= design["maximum_cv"] and all(not row["cv_flag"] for row in standards + samples)
            and all(row["accepted"] for row in standards)
            and all(row["status"] != "failed" for row in parallelism)}


def compute_immunoassay(plate, design):
    """Compute synthetic OD checks; never extrapolate or self-attest review."""
    try:
        return _compute(plate, design)
    except (ArithmeticError, RecursionError) as error:
        raise ValueError("numerical-failure: finite identifiable 4PL required") from error


def _same(actual, expected, label):
    if type(expected) is dict:
        _obj(actual, " ".join(expected), label)
        for key in expected:
            _same(actual[key], expected[key], label + "." + key)
    elif type(expected) is list:
        _items(actual, label, MAX_ITEMS, empty=True)
        _require(len(actual) == len(expected), "reported-result", f"{label} length differs")
        for left, right in zip(actual, expected):
            _same(left, right, label)
    elif type(expected) is bool:
        _require(_bool(actual, label) == expected, "reported-result", f"{label} differs")
    elif type(expected) is int:
        _require(_number(actual, label, integer=True) == expected, "reported-result", f"{label} differs")
    elif type(expected) is float:
        _number(actual, label)
        _require(math.isclose(actual, expected, rel_tol=1e-8, abs_tol=0), "reported-result", f"{label} differs")
    else:
        _require(type(actual) is type(expected) and actual == expected, "reported-result", f"{label} differs")


def _wording(text):
    _text(text, "claim text")
    _require(OVERREACH.search(text) is None, "claim-overreach", "claim exceeds synthetic arithmetic evidence")


def _claims(claims, records, unavailable_sources=(), computed_sources=()):
    seen = set()
    for claim in _items(claims, "claims", MAX_CLAIMS, empty=True):
        _obj(claim, "id kind status text evidence", "claim")
        name = _text(claim["id"], "claim ID")
        status = _text(claim["status"], "claim status")
        kind = _text(claim["kind"], "claim kind")
        _require(name not in seen and status in STATUSES, "invalid-record", "duplicate claim or invalid status")
        seen.add(name)
        citations = _items(claim["evidence"], "claim evidence", MAX_RECORDS, empty=True)
        for citation in citations:
            _text(citation, "evidence ID")
        _require(len(set(citations)) == len(citations) and all(c in records for c in citations),
                 "missing-evidence", "unknown or duplicated evidence ID")
        unavailable = not citations or any(c in unavailable_sources or
                                           records[c]["kind"].casefold() == "unavailable" or
                                           records[c]["result"].casefold() == "unavailable" or
                                           records[c]["source"] is None for c in citations)
        _require(not unavailable or status == "unavailable", "unavailable-evidence", "missing evidence requires unavailable status")
        if status in POSITIVE:
            _require(not any(c in computed_sources for c in citations) and
                     not any(NON_EVIDENCE.search(records[c][field]) for c in citations for field in ("kind", "result")),
                     "non-evidence-support", "review approval and computed records cannot support claims")
        _require(status != "replicated", "claim-replication", "one synthetic plate cannot establish replication")
        _wording(claim["text"])
        _require(kind in ("descriptive", "associational"), "claim-overreach", "unsupported claim kind")
        _require(status != "unavailable" or UNAVAILABLE_POSITIVE.search(claim["text"]) is None,
                 "unavailable-positive", "unavailable claim asserts positive evidence")


def _validate(bundle):
    pack = bundle.load(bundle.path.name)
    _record(pack, "immunoassay-pack-v1", "stages design plate report evidence frozen_design_sha256 frozen_before_responses")
    _require(pack["stages"] == list(STAGES), "stage-order", "five fixed stages required")
    _bool(pack["frozen_before_responses"], "freeze declaration")
    _require(pack["frozen_before_responses"], "design-freeze", "rules must be frozen before responses")
    design = bundle.artifact(pack["design"])
    _design(design)
    _require(pack["frozen_design_sha256"] == pack["design"]["sha256"], "design-freeze", "frozen hash differs")
    plate = bundle.artifact(pack["plate"])
    report = bundle.artifact(pack["report"])
    _record(report, "immunoassay-report-v1", "blank_rule exploratory computation headline claims")
    _bool(report["exploratory"], "exploratory label")
    _require(report["blank_rule"] == design["blank_rule"] or report["exploratory"],
             "post-hoc-blank", "changed blank subtraction needs retained freeze and exploratory label")
    effective_design = dict(design, blank_rule=report["blank_rule"])
    result = compute_immunoassay(plate, effective_design)
    declared = report["computation"]
    _obj(declared, " ".join(result), "reported computation")
    fit = _obj(declared["fit"], " ".join(result["fit"]), "reported fit")
    _require(_bool(fit["converged"], "convergence") is True, "fit-not-converged", "non-converged fit cannot be reported")
    _parameters(fit["parameters"])
    _require(declared["used_standards"] == result["used_standards"], "standard-exclusion", "frozen standards were dropped")
    for row in _items(declared["samples"], "reported samples", MAX_WELLS):
        _obj(row, "id dilution response_mean cv cv_flag status concentration", "reported sample")
        status = _text(row["status"], "range status")
        _require(status == "in-range" or row["concentration"] is None, "extrapolation", "outside-range concentration forbidden")
        if row["concentration"] is not None:
            concentration = _number(row["concentration"], "reported concentration")
            _require(result["quantifiable_range"][0] <= concentration <= result["quantifiable_range"][1],
                     "extrapolation", "reported concentration must remain between accepted standards")
    for actual, expected in zip(_items(declared["samples"], "reported samples", MAX_WELLS), result["samples"]):
        _require(expected["status"] == "in-range" or actual["concentration"] is None,
                 "extrapolation", "outside-range response cannot receive a concentration")
    for field in ("standards", "samples"):
        for actual, expected in zip(_items(declared[field], field, MAX_WELLS), result[field]):
            _require(type(actual) is dict, "invalid-record", "QC row must be object")
            _require(actual.get("cv_flag") == expected["cv_flag"], "replicate-cv-ignored", "replicate CV flag differs")
    _require(declared["parallelism"] == result["parallelism"], "parallelism-ignored", "dilution parallelism failure or unavailable result ignored")
    _same(declared, result, "computation")
    records = {}
    unavailable_sources, computed_sources = set(), set()
    evidence = _items(pack["evidence"], "evidence artifacts", MAX_ARTIFACTS, empty=True)
    own_paths = {bundle.path.name} | {pack[k]["path"] for k in ("design", "plate", "report")}
    own_hashes = {v[1] for v in bundle.paths.values()}
    for identity in evidence:
        own_paths.add(_relative(_obj(identity, "path sha256", "evidence identity")["path"]).as_posix())
        own_hashes.add(_text(identity["sha256"], "evidence hash"))
    for identity in evidence:
        wrapper = bundle.artifact(identity)
        _record(wrapper, "immunoassay-evidence-v1", "records")
        rows = _items(wrapper["records"], "evidence records", MAX_RECORDS, empty=True)
        _require(len(records) + len(rows) <= MAX_RECORDS, "input-limit", "aggregate evidence records exceed limit")
        for record in rows:
            _obj(record, "id kind result origin source", "evidence record")
            name = _text(record["id"], "evidence ID")
            _require(name not in records, "invalid-record", "duplicate evidence ID")
            for field in ("kind", "result", "origin"):
                _text(record[field], field)
            _require(record["origin"] in ("internal", "external", "independent", "preregistered"),
                     "invalid-record", "unknown evidence origin")
            if record["source"] is not None:
                source = _obj(record["source"], "path sha256", "source identity")
                source_record = bundle.artifact(source)
                for field in ("kind", "result"):
                    if field in source_record:
                        label = _text(source_record[field], "source " + field)
                        if label.casefold() == "unavailable":
                            unavailable_sources.add(name)
                        if NON_EVIDENCE.search(label):
                            computed_sources.add(name)
                if source_record.get("schema") in ("immunoassay-report-v1", "immunoassay-result-v1"):
                    computed_sources.add(name)
                if record["origin"] != "internal":
                    _require(source["path"] not in own_paths and source["sha256"] not in own_hashes,
                             "external-alias", "declared independent source aliases an internal artifact")
            else:
                _require(record["kind"].casefold() == "unavailable" or record["result"].casefold() == "unavailable",
                         "unavailable-evidence", "absent source requires unavailable record")
            records[name] = record
    _claims(report["claims"], records, unavailable_sources, computed_sources)
    _wording(report["headline"])
    bundle.finish()
    return {"schema": "immunoassay-result-v1", "fixture": "synthetic fixture", "status": "accepted",
            "review": "unavailable", "exploratory": report["exploratory"], "computation": result,
            "claims": report["claims"], "inputs": [{"path": name, "sha256": value[1]}
                                                    for name, value in bundle.paths.items()]}


def validate_immunoassay_4pl_pack(path):
    """Admit a hash-bound synthetic bundle; return JSON-compatible unreviewed arithmetic."""
    bundle = None
    try:
        _require(isinstance(path, (str, Path)), "input-path", "bundle path must be text or Path")
        _require("\x00" not in os.fspath(path), "input-path", "bundle path contains a null character")
        bundle = _Bundle(path)
        return _validate(bundle)
    except OSError as error:
        raise ValueError("input-file: unavailable, replaced or symlinked input") from error
    except (ArithmeticError, RecursionError) as error:
        raise ValueError("numerical-failure: finite bounded records required") from error
    finally:
        if bundle is not None:
            bundle.close()
