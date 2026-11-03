"""Read-only admission and reference arithmetic for synthetic Michaelis-Menten fixtures."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import statistics


STAGES = ("01-freeze", "02-identity-qc", "03-fit", "04-summary", "05-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_JSON_VALUES = 4_000_000
MAX_ARTIFACTS = 128
MAX_ROWS = 128
MAX_CURVE_POINTS = 512
MAX_ITERATIONS = 200
MAX_BACKTRACK = 24
MAX_CLAIMS = 100
MAX_SUPPORT = 100
MAX_ITEMS = 20000
MAX_TEXT = 4096
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
    r"physical[\s-]+validity|diagnos\w*|patient\w*|drug\w*)\b", re.I,
)
ASSERTION = re.compile(r"\b(?:supported|replicated|suggestive|significan\w*)\b", re.I)
NON_EVIDENCE = re.compile(r"review|approv|comput|numer|agreement|truth|physical|clinic", re.I)


def _require(condition, code, message):
    if not condition:
        raise ValueError(f"{code}: {message}")


def _text(value, label):
    _require(type(value) is str and 0 < len(value) <= MAX_TEXT and bool(value.strip())
             and not any(0xD800 <= ord(c) <= 0xDFFF for c in value),
             "invalid-record", f"{label} must be bounded nonempty text")
    return value


def _number(value, label, low=-MAX_NUMBER, high=MAX_NUMBER, integer=False):
    valid = type(value) is int if integer else type(value) in (int, float)
    _require(valid and -MAX_NUMBER <= value <= MAX_NUMBER and math.isfinite(value)
             and low <= value <= high, "invalid-record", f"{label} has invalid numeric type or range")
    return value


def _boolean(value, label):
    _require(type(value) is bool, "invalid-record", f"{label} must be boolean")
    return value


def _fields(value, fields, label):
    _require(type(value) is dict and set(value) == set(fields.split()),
             "invalid-record", f"{label} fields differ from its pack-local schema")
    return value


def _items(value, label, limit, empty=False):
    _require(type(value) is list, "invalid-record", f"{label} must be a list")
    _require(len(value) <= limit, "input-limit", f"{label} exceeds its count limit")
    _require(empty or bool(value), "invalid-record", f"{label} must not be empty")
    return value


def _record(value, schema, fields):
    _fields(value, "schema schema_version fixture " + fields, schema)
    _require(value["schema"] == schema, "invalid-record", f"expected {schema}")
    _number(value["schema_version"], "schema_version", 1, 1, integer=True)
    _require(value["fixture"] is True, "fixture-only", "only synthetic fixtures are admitted")
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
    return _number(int(value), "JSON integer")


def _json(raw, allowance):
    # Count without allocating a match list, before the parser allocates a tree.
    estimate = 1 + raw.count(b",") + sum(
        1 for _ in re.finditer(rb"[\[{](?=\s*[^\s\]}])", raw)
    )
    _require(estimate <= allowance, "input-limit", "bundle JSON value allowance exceeded")
    try:
        root = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=_constant, parse_int=_int,
                          parse_float=lambda value: _number(float(value), "JSON number"))
        _require(type(root) is dict, "invalid-json", "JSON root must be an object")
        pending = [(root, 0)]
        while pending:
            value, depth = pending.pop()
            _require(depth <= MAX_DEPTH, "invalid-json", "JSON nesting exceeds limit")
            if type(value) in (dict, list):
                _require(len(value) <= MAX_ITEMS, "input-limit", "JSON container exceeds limit")
                children = value.items() if type(value) is dict else enumerate(value)
                for key, child in children:
                    if type(key) is str:
                        _text(key, "JSON key")
                    pending.append((child, depth + 1))
            elif type(value) is str:
                _require(len(value) <= MAX_TEXT and not any(0xD800 <= ord(c) <= 0xDFFF for c in value),
                         "input-limit", "JSON string exceeds limit or contains a surrogate")
        return root, estimate
    except (UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError("invalid-json: bounded finite UTF-8 JSON object required") from error
    except json.JSONDecodeError as error:
        raise ValueError("invalid-json: malformed JSON") from error


def _relative(value):
    value = _text(value, "artifact path")
    path = PurePosixPath(value)
    _require(not path.is_absolute() and path.as_posix() == value and value != "."
             and ".." not in path.parts and "\\" not in value
             and not re.match(r"^[A-Za-z]:", value) and all(ord(c) >= 32 for c in value),
             "input-path", "canonical bundle-relative artifact path required")
    return path


def _signature(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _pin_root(root):
    """Keep identities for the entire ancestor chain, including the filesystem root."""
    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_DIRECTORY
    descriptor = os.open(root.anchor, flags)
    chain = [_signature(os.fstat(descriptor))[:2]]
    try:
        for part in root.parts[1:]:
            before = os.lstat(part, dir_fd=descriptor)
            _require(stat.S_ISDIR(before.st_mode), "input-root", "bundle ancestors must be real directories")
            child = os.open(part, flags, dir_fd=descriptor)
            try:
                opened = os.fstat(child)
                _require(stat.S_ISDIR(opened.st_mode) and _signature(before)[:2] == _signature(opened)[:2],
                         "input-changed", "bundle ancestor replaced during open")
            except BaseException:
                os.close(child)
                raise
            os.close(descriptor)
            descriptor = child
            chain.append(_signature(opened)[:2])
        return descriptor, tuple(chain)
    except BaseException:
        os.close(descriptor)
        raise


class _Bundle:
    def __init__(self, path):
        _require(isinstance(path, (str, os.PathLike)), "input-path", "bundle path must be text or path-like")
        path = os.fspath(path)
        _require(type(path) is str and ".." not in Path(path).parts and all(ord(c) >= 32 for c in path),
                 "input-path", "bundle path must not contain traversal or control characters")
        self.path = Path(os.path.abspath(path))
        self.root = self.path.parent
        self.cache = {}
        self.artifacts = {}
        self.bytes_read = 0
        self.values_read = 0
        self.descriptor, self.chain = _pin_root(self.root)

    def close(self):
        os.close(self.descriptor)

    def _check_root(self):
        descriptor, chain = _pin_root(self.root)
        try:
            _require(chain == self.chain, "input-changed", "bundle ancestor chain replaced")
        finally:
            os.close(descriptor)

    def _read(self, path, checked=None):
        flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
        directory = os.dup(self.descriptor)
        try:
            for part in path.parts[:-1]:
                before = os.lstat(part, dir_fd=directory)
                _require(stat.S_ISDIR(before.st_mode), "input-file", "artifact components must be real directories")
                child = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
                try:
                    opened = os.fstat(child)
                    _require(_signature(before)[:2] == _signature(opened)[:2],
                             "input-changed", "artifact component replaced")
                except BaseException:
                    os.close(child)
                    raise
                os.close(directory)
                directory = child
            before = os.lstat(path.name, dir_fd=directory)
            _require(stat.S_ISREG(before.st_mode) and before.st_size <= MAX_BYTES,
                     "input-file", "regular input file at most 64 MiB required")
            descriptor = os.open(path.name, flags, dir_fd=directory)
            with os.fdopen(descriptor, "rb") as handle:
                opened = os.fstat(handle.fileno())
                signature = _signature(opened)
                _require(stat.S_ISREG(opened.st_mode) and opened.st_size <= MAX_BYTES
                         and _signature(before) == signature, "input-file", "input replaced during open")
                inode = signature[:2]
                cached = self.artifacts.get(inode)
                if cached is not None:
                    _require(signature == cached[2], "input-changed", "cached artifact changed")
                    if checked is None or inode in checked:
                        return None, signature
                limit = min(MAX_BYTES, MAX_TOTAL_BYTES - self.bytes_read)
                _require(opened.st_size <= limit, "input-limit", "total raw byte allowance exceeded")
                raw = handle.read(limit + 1)
                after = os.fstat(handle.fileno())
            _require(len(raw) <= limit and len(raw) == opened.st_size and signature == _signature(after),
                     "input-changed", "input grew or changed during read")
            self.bytes_read += len(raw)
            return raw, signature
        finally:
            os.close(directory)

    def snapshot(self, name):
        path = _relative(name)
        if name not in self.cache:
            _require(len(self.cache) < MAX_ARTIFACTS, "input-limit", "too many artifact paths")
            raw, signature = self._read(path)
            inode = signature[:2]
            if raw is not None:
                value, count = _json(raw, MAX_JSON_VALUES - self.values_read)
                self.artifacts[inode] = (value, hashlib.sha256(raw).hexdigest(), signature)
                self.values_read += count
            self.cache[name] = self.artifacts[inode]
        return self.cache[name][:2]

    def load(self, identity):
        _fields(identity, "path sha256", "artifact identity")
        name = _relative(identity["path"]).as_posix()
        digest = _text(identity["sha256"], "SHA-256")
        _require(re.fullmatch(r"[0-9a-f]{64}", digest) is not None, "input-hash", "invalid SHA-256")
        record, actual = self.snapshot(name)
        _require(actual == digest, "input-hash", "artifact hash mismatch")
        return record

    def recheck(self):
        self._check_root()
        checked = set()
        for name, (_, digest, signature) in self.cache.items():
            raw, current = self._read(_relative(name), checked)
            _require(signature == current and (raw is None or hashlib.sha256(raw).hexdigest() == digest),
                     "input-changed", "input replaced during validation")
            checked.add(current[:2])
        self._check_root()


def _time(value):
    try:
        result = datetime.fromisoformat(_text(value, "timestamp").replace("Z", "+00:00"))
        _require(result.tzinfo is not None, "protocol-freeze", "timezone required")
        return result
    except (ValueError, OverflowError) as error:
        raise ValueError("protocol-freeze: valid timezone-aware timestamps required") from error


def _protocol(record):
    _record(record, "enzyme-kinetics-protocol-v1", "substrate concentration_unit enzyme_concentration "
            "enzyme_unit time_unit product_unit rate_unit model method weighting exclusion_rule "
            "substrate_levels min_levels window start tolerance max_iterations")
    _text(record["substrate"], "substrate")
    for key, expected in (("concentration_unit", "uM"), ("enzyme_unit", "uM"),
                          ("product_unit", "uM"), ("time_unit", "s"), ("rate_unit", "uM/s")):
        _require(_text(record[key], key) == expected, "unit-mismatch", "reference units are uM, s and uM/s")
    if record["enzyme_concentration"] is not None:
        _number(record["enzyme_concentration"], "enzyme concentration", 1e-12, 1e6)
    _require(_text(record["model"], "model") == "Michaelis-Menten", "model-choice", "freeze Michaelis-Menten only")
    _require(_text(record["method"], "method") == "gauss-newton", "primary-fit", "primary fit must use nonlinear Gauss-Newton, never Lineweaver-Burk")
    _require(_text(record["weighting"], "weighting") == "none", "weighting-choice", "freeze unweighted least squares")
    _require(_text(record["exclusion_rule"], "exclusion rule") == "none", "exclusion-rule", "no exclusions are permitted")
    _number(record["min_levels"], "minimum levels", 4, MAX_ROWS, integer=True)
    levels = _items(record["substrate_levels"], "substrate levels", MAX_ROWS)
    _require(len(levels) >= record["min_levels"], "substrate-levels", "too few frozen substrate levels")
    previous = 0
    for level in levels:
        _number(level, "substrate level", 1e-12, 1e6)
        _require(level > previous, "substrate-levels", "frozen levels must be unique, positive and increasing")
        previous = level
    window = _fields(record["window"], "start stop min_points min_r_squared max_depletion_fraction", "window")
    _number(window["start"], "window start", 0, 0)
    _number(window["stop"], "window stop", 1e-9, 1e6)
    _number(window["min_points"], "window minimum points", 3, MAX_CURVE_POINTS, integer=True)
    _number(window["min_r_squared"], "minimum R-squared", 0, 1)
    _number(window["max_depletion_fraction"], "maximum depletion", 1e-12, 0.2)
    start = _fields(record["start"], "Vmax Km", "start values")
    for name in start:
        _number(start[name], name, 1e-12, 1e6)
    _number(record["tolerance"], "fit tolerance", 1e-12, 1e-4)
    _number(record["max_iterations"], "maximum iterations", 1, MAX_ITERATIONS, integer=True)
    return record


def _rates(data, protocol):
    _record(data, "enzyme-kinetics-data-v1", "concentration_unit enzyme_concentration enzyme_unit time_unit "
            "product_unit rate_unit curves")
    for key in ("concentration_unit", "enzyme_unit", "time_unit", "product_unit", "rate_unit"):
        _require(_text(data[key], key) == protocol[key], "unit-mismatch", "data units differ from frozen units")
    if data["enzyme_concentration"] is not None:
        _number(data["enzyme_concentration"], "recorded enzyme concentration", 1e-12, 1e6)
    _require(data["enzyme_concentration"] == protocol["enzyme_concentration"],
             "enzyme-concentration", "recorded enzyme concentration differs from freeze")
    curves = _items(data["curves"], "curves", MAX_ROWS)
    _require(len(curves) == len(protocol["substrate_levels"]), "substrate-levels", "every frozen substrate level must appear once")
    window = protocol["window"]
    rates = []
    seen = set()
    for index, row in enumerate(curves):
        _fields(row, "id substrate time product rate rate_window", "curve")
        name = _text(row["id"], "curve id")
        _require(name not in seen, "duplicate-id", "curve identities must be unique")
        seen.add(name)
        level = _number(row["substrate"], "substrate", 1e-12, 1e6)
        _require(level == protocol["substrate_levels"][index], "substrate-levels", "observed levels must match the frozen ordered range")
        declared = _fields(row["rate_window"], "start stop", "rate window")
        for key in ("start", "stop"):
            _number(declared[key], "rate window " + key, 0, 1e6)
        _require(declared == {key: window[key] for key in ("start", "stop")},
                 "rate-window", "rates must use exactly the frozen linear window")
        times = _items(row["time"], "curve times", MAX_CURVE_POINTS)
        products = _items(row["product"], "curve products", MAX_CURVE_POINTS)
        _require(len(times) == len(products), "progress-curve", "paired time and product points required")
        previous = -1
        selected = []
        for time, product in zip(times, products):
            _number(time, "time", 0, 1e6)
            _number(product, "product", 0, 1e6)
            _require(time > previous, "progress-time", "progress times must increase strictly")
            previous = time
            if window["start"] <= time <= window["stop"]:
                selected.append((time, product))
        _require(len(selected) >= window["min_points"] and selected[0][0] == window["start"]
                 and selected[-1][0] == window["stop"], "rate-window", "frozen endpoints and enough linear-window points required")
        baseline = selected[0][1]
        depletion = (max(point[1] for point in selected) - baseline) / level
        _require(depletion <= window["max_depletion_fraction"], "substrate-depletion", "frozen substrate depletion fraction exceeded")
        n = len(selected)
        mean_t = math.fsum(point[0] for point in selected) / n
        mean_p = math.fsum(point[1] for point in selected) / n
        tt = math.fsum((point[0] - mean_t) ** 2 for point in selected)
        pp = math.fsum((point[1] - mean_p) ** 2 for point in selected)
        _require(tt > 0 and pp > 0, "degenerate-curve", "nonzero time and product variance required")
        slope = math.fsum((t - mean_t) * (p - mean_p) for t, p in selected) / tt
        _require(math.isfinite(slope) and slope > 0, "degenerate-curve", "positive finite initial rate required")
        residual = math.fsum((p - mean_p - slope * (t - mean_t)) ** 2 for t, p in selected)
        r_squared = 1 - residual / pp
        _require(r_squared >= window["min_r_squared"], "nonlinear-window", "frozen minimum linear-window R-squared failed")
        rate = _number(row["rate"], "declared initial rate", 1e-12, 1e6)
        _require(math.isclose(rate, slope, rel_tol=1e-9, abs_tol=1e-12),
                 "rate-window", "declared rate differs from frozen-window recomputation")
        rates.append({"id": name, "substrate": level, "rate": slope,
                      "r_squared": r_squared, "depletion_fraction": depletion, "n": n})
    values = [row["rate"] for row in rates]
    _require(max(values) > min(values), "degenerate-fit", "rates must have nonzero variance")
    return rates


def _system(levels, rates, vmax, km):
    fractions = [s / (km + s) for s in levels]
    predicted = [vmax * fraction for fraction in fractions]
    residuals = [y - p for y, p in zip(rates, predicted)]
    # Log-parameter Jacobian keeps positivity without silently clipping steps.
    j0 = predicted
    j1 = [-vmax * f * km / (km + s) for s, f in zip(levels, fractions)]
    a = math.fsum(v * v for v in j0)
    b = math.fsum(x * y for x, y in zip(j0, j1))
    c = math.fsum(v * v for v in j1)
    g0 = math.fsum(x * r for x, r in zip(j0, residuals))
    g1 = math.fsum(x * r for x, r in zip(j1, residuals))
    return math.fsum(r * r for r in residuals), residuals, (a, b, c, g0, g1)


def reference_computation(protocol, data):
    """Compute fixture rates and an unweighted positive Michaelis-Menten fit, without writes."""
    _protocol(protocol)
    rows = _rates(data, protocol)
    levels = [row["substrate"] for row in rows]
    rates = [row["rate"] for row in rows]
    vmax, km = (protocol["start"][key] for key in ("Vmax", "Km"))
    tolerance = protocol["tolerance"]
    converged = False
    scale = math.fsum(y * y for y in rates)
    for iteration in range(1, protocol["max_iterations"] + 1):
        sse, residuals, (a, b, c, g0, g1) = _system(levels, rates, vmax, km)
        determinant = a * c - b * b
        _require(determinant > 1e-14 * a * c, "degenerate-fit", "Jacobian has insufficient rank")
        delta0 = (c * g0 - b * g1) / determinant
        delta1 = (a * g1 - b * g0) / determinant
        if max(abs(delta0), abs(delta1)) <= tolerance:
            converged = True
            break
        accepted = False
        for backtrack in range(MAX_BACKTRACK):
            factor = 0.5 ** backtrack
            log_v = math.log(vmax) + factor * delta0
            log_k = math.log(km) + factor * delta1
            if not (math.log(1e-12) <= log_v <= math.log(1e6) and math.log(1e-12) <= log_k <= math.log(1e6)):
                continue
            trial_v, trial_k = math.exp(log_v), math.exp(log_k)
            trial_sse = _system(levels, rates, trial_v, trial_k)[0]
            if trial_sse < sse:
                vmax, km = trial_v, trial_k
                accepted = True
                break
        if not accepted:
            # Roundoff may prevent an improvement at the stationary point.
            converged = max(abs(g0), abs(g1)) <= tolerance * scale
            break
    sse, residuals, (a, b, c, _, _) = _system(levels, rates, vmax, km)
    determinant = a * c - b * b
    _require(determinant > 1e-14 * a * c, "degenerate-fit", "final Jacobian has insufficient rank")
    bracketed = levels[-1] >= 2 * km and levels[0] <= 0.5 * km
    usable = converged and bracketed
    enzyme = protocol["enzyme_concentration"]
    df = len(rows) - 2
    variance = sse / df
    # Transform inverse log-Jacobian covariance back to natural parameters.
    var_v, var_k = variance * c / determinant * vmax * vmax, variance * a / determinant * km * km
    cov_vk = -variance * b / determinant * vmax * km
    se_v, se_k = math.sqrt(var_v), math.sqrt(var_k)
    efficiency = vmax / (enzyme * km) if enzyme is not None else None
    ratio_variance = var_v / (vmax * vmax) + var_k / (km * km) - 2 * cov_vk / (vmax * km)
    _require(ratio_variance >= -1e-12, "degenerate-fit", "invalid derived covariance")
    parameters = {"Vmax": vmax if usable else None, "Km": km if usable else None,
                  "kcat": vmax / enzyme if usable and enzyme is not None else None,
                  "kcat/Km": efficiency if usable else None}
    errors = {"Vmax": se_v if usable else None, "Km": se_k if usable else None,
              "kcat": se_v / enzyme if usable and enzyme is not None else None,
              "kcat/Km": efficiency * math.sqrt(max(0, ratio_variance)) if usable and enzyme is not None else None}
    signs = [r > 0 for r in residuals if abs(r) > 1e-10 * max(rates)]
    changes = sum(left != right for left, right in zip(signs, signs[1:]))
    return {"rates": rows, "converged": converged, "iterations": iteration,
            "last_iterate": {"Vmax": vmax, "Km": km}, "parameters": parameters,
            "standard_errors": errors, "covariance_Vmax_Km": cov_vk,
            "units": {"Vmax": "uM/s", "Km": "uM", "kcat": "1/s", "kcat/Km": "1/(uM*s)"},
            "reliability": "reliable" if usable else "unreliable", "bracketed": bracketed,
            "sse": sse, "df": df, "residuals": residuals,
            "residual_pattern": {"sign_changes": changes, "flag": bool(signs) and changes < 2},
            "excluded_ids": []}


def _matching(actual, expected, label="calculation"):
    if type(expected) is dict:
        _fields(actual, " ".join(expected), label)
        for name in expected:
            _matching(actual[name], expected[name], label + "." + name)
    elif type(expected) is list:
        _items(actual, label, max(MAX_ROWS, MAX_CURVE_POINTS), empty=True)
        _require(len(actual) == len(expected), "report-mismatch", label + " length differs")
        for left, right in zip(actual, expected):
            _matching(left, right, label)
    elif type(expected) is bool:
        _require(_boolean(actual, label) == expected, "report-mismatch", label + " differs")
    elif type(expected) in (int, float):
        _number(actual, label, integer=type(expected) is int)
        _require(math.isclose(actual, expected, rel_tol=1e-7, abs_tol=1e-10), "report-mismatch", label + " differs")
    else:
        _require(type(actual) is type(expected) and actual == expected, "report-mismatch", label + " differs")


def _report(record, protocol, result):
    _record(record, "enzyme-kinetics-report-v1", "model method weighting exploratory calculation")
    exploratory = _boolean(record["exploratory"], "exploratory")
    _text(record["model"], "reported model")
    _require(record["model"] == protocol["model"] or exploratory, "post-outcome-model", "changed model requires exploratory labelling")
    _require(record["model"] == protocol["model"], "exploratory-rerun", "changed model needs a separate frozen exploratory bundle")
    _require(_text(record["method"], "reported method") == protocol["method"], "primary-fit", "primary fit must remain nonlinear Gauss-Newton")
    _require(_text(record["weighting"], "reported weighting") == protocol["weighting"], "weighting-choice", "reported weighting differs from freeze")
    calc = record["calculation"]
    _require(type(calc) is dict, "invalid-record", "calculation must be an object")
    errors = calc.get("standard_errors")
    _require(type(errors) is dict and set(errors) == {"Vmax", "Km", "kcat", "kcat/Km"},
             "standard-errors", "all four asymptotic standard error fields are mandatory")
    params = _fields(calc.get("parameters"), "Vmax Km kcat kcat/Km", "parameters")
    if protocol["enzyme_concentration"] is None:
        _require(params["kcat"] is None and params["kcat/Km"] is None,
                 "enzyme-missing", "kcat requires a recorded enzyme concentration")
    _require(type(calc.get("units")) is dict and calc["units"].get("Km") == protocol["concentration_unit"],
             "unit-mismatch", "Km and substrate concentration units must agree")
    if not result["converged"] or calc.get("converged") is False:
        _require(params["Vmax"] is None, "fit-nonconverged", "non-converged fit cannot report Vmax")
    if not result["bracketed"]:
        _require(params["Km"] is None and calc.get("reliability") == "unreliable",
                 "km-unreliable", "substrate range must bracket Km before parameter reporting")
    _matching(calc, result)


def _evidence(record):
    _record(record, "enzyme-kinetics-evidence-v1", "kind result")
    return _text(record["kind"], "evidence kind"), _text(record["result"], "evidence result")


def _claims(bundle, claims, own):
    claims = _items(claims, "claims", MAX_CLAIMS, empty=True)
    seen = set()
    for claim in claims:
        _fields(claim, "id kind status text support", "claim")
        name = _text(claim["id"], "claim id")
        _require(name not in seen, "invalid-record", "duplicate claim id")
        seen.add(name)
        kind = _text(claim["kind"], "claim kind")
        status = _text(claim["status"], "claim status")
        text = _text(claim["text"], "claim text")
        _require(status in STATUSES, "invalid-record", "unknown claim status")
        _require(kind in {"descriptive", "associational"} and OVERREACH.search(text) is None,
                 "claim-boundary", "only bounded descriptive synthetic arithmetic is admitted")
        support = _items(claim["support"], "claim support", MAX_SUPPORT, empty=True)
        _require(bool(support) or status == "unavailable", "claim-support", "empty evidence requires unavailable status")
        if status == "unavailable":
            _require(ASSERTION.search(text) is None, "unavailable-positive", "unavailable claim cannot assert positive evidence")
        sources = []
        for identity in support:
            _fields(identity, "path sha256 origin", "claim support identity")
            origin = _text(identity["origin"], "evidence origin")
            _require(origin in {"study", "external", "independent", "preregistered"}, "invalid-record", "unknown evidence origin")
            plain = {key: identity[key] for key in ("path", "sha256")}
            if origin != "study":
                _require(not any(identity["path"] == item["path"] or identity["sha256"] == item["sha256"] for item in own),
                         "evidence-independence", "outside evidence aliases this study's input or output")
            evidence_kind, evidence_result = _evidence(bundle.load(plain))
            sources.append((evidence_kind, evidence_result))
        _require(status == "unavailable" or all("unavailable" not in source for source in sources),
                 "unavailable-evidence", "any unavailable citation requires unavailable status")
        if status in POSITIVE:
            for evidence_kind, evidence_result in sources:
                _require(NON_EVIDENCE.search(evidence_kind) is None and NON_EVIDENCE.search(evidence_result) is None,
                         "non-evidence", "computed agreement and review approval cannot support positive claims")
        _require(status != "replicated", "claim-replication", "one synthetic fixture cannot establish replication")
        _require(status not in POSITIVE, "synthetic-evidence", "synthetic arithmetic cannot establish positive scientific evidence")


def validate_enzyme_kinetics_pack(path):
    """Validate one immutable, hashed, synthetic enzyme-kinetics bundle; never write files."""
    bundle = None
    try:
        bundle = _Bundle(path)
        bundle._check_root()
        pack, digest = bundle.snapshot(bundle.path.name)
        _record(pack, "enzyme-kinetics-pack-v1", "stages inputs frozen_protocol_sha256 freeze_before_rates "
                "frozen_at rates_read_at study_outputs claims")
        _require(pack["stages"] == list(STAGES), "stage-order", "exactly five ordered stages required")
        inputs = _fields(pack["inputs"], "protocol data report", "inputs")
        protocol = _protocol(bundle.load(inputs["protocol"]))
        _require(_boolean(pack["freeze_before_rates"], "freeze_before_rates") and
                 pack["frozen_protocol_sha256"] == inputs["protocol"]["sha256"] and
                 _time(pack["frozen_at"]) < _time(pack["rates_read_at"]),
                 "protocol-freeze", "rules must be hash-frozen before rates are read")
        result = reference_computation(protocol, bundle.load(inputs["data"]))
        _report(bundle.load(inputs["report"]), protocol, result)
        outputs = _items(pack["study_outputs"], "study outputs", MAX_SUPPORT, empty=True)
        for identity in outputs:
            _evidence(bundle.load(identity))
        own = [*inputs.values(), *outputs, {"path": bundle.path.name, "sha256": digest}]
        _claims(bundle, pack["claims"], own)
        bundle.recheck()
        return {"schema": "enzyme-kinetics-result-v1", "schema_version": 1, "fixture": True,
                "stages": list(STAGES), "evidence_level": "synthetic-arithmetic-only", "review": "unavailable",
                "protocol_sha256": pack["frozen_protocol_sha256"], "calculation": result, "claims": pack["claims"],
                "input_identities": [{"path": name, "sha256": value[1]} for name, value in sorted(bundle.cache.items())],
                "limitations": ["Synthetic arithmetic is not physical, biological or clinical validity.",
                                "Hashes and timestamps cannot prove historical freezing or source authenticity.",
                                "Asymptotic standard errors assume an adequate model and fixed known enzyme concentration.",
                                "The conservative English lexical filter is incomplete and refuses negations too.",
                                "Independent review and rigor classification remain coordinator responsibilities."]}
    except OSError as error:
        raise ValueError("input-file: unavailable regular input or symlinked component") from error
    except (RecursionError, OverflowError, UnicodeError, ZeroDivisionError) as error:
        raise ValueError("invalid-record: bounded nondegenerate finite inputs required") from error
    finally:
        if bundle is not None:
            bundle.close()
