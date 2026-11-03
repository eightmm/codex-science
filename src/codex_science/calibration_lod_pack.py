"""Read-only admission and reference arithmetic for synthetic assay calibration fixtures."""
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


STAGES = ("01-freeze", "02-identity-qc", "03-fit-limits", "04-summary", "05-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_JSON_VALUES = 4_000_000
MAX_ARTIFACTS = 128
MAX_ROWS = 10000
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
    r"physical[\s-]+validity|diagnos\w*|patient\w*)\b", re.I,
)
ASSERTION = re.compile(r"\b(?:supported|replicated|suggestive|significan\w*)\b", re.I)
NON_EVIDENCE = re.compile(r"review|approv|comput|numer|agreement|truth|physical|clinic", re.I)
ACCEPTANCE_EVIDENCE = ["back-calculated-deviations", "replicate-counts", "residuals"]


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
                limit = MAX_BYTES if checked is not None else min(MAX_BYTES, MAX_TOTAL_BYTES - self.bytes_read)
                _require(opened.st_size <= limit, "input-limit", "total raw byte allowance exceeded")
                raw = handle.read(limit + 1)
                after = os.fstat(handle.fileno())
            _require(len(raw) <= limit and len(raw) == opened.st_size and signature == _signature(after),
                     "input-changed", "input grew or changed during read")
            if checked is None:
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
    _record(record, "calibration-lod-protocol-v1", "analyte concentration_unit response_unit model weighting "
            "intercept acceptance min_levels min_replicates limit_rule validity exclusion_rule")
    for key in ("analyte", "concentration_unit", "response_unit"):
        _text(record[key], key)
    model = _text(record["model"], "model")
    weighting = _text(record["weighting"], "weighting")
    intercept = _text(record["intercept"], "intercept")
    _require((model == "linear" and weighting == "none") or
             (model == "weighted-linear" and weighting in {"1/x", "1/x^2"}),
             "model-choice", "freeze linear or weighted-linear with one supported weighting")
    _require(intercept in {"free", "zero"}, "intercept-choice", "freeze a free or zero intercept")
    acceptance = _fields(record["acceptance"], "percent_deviation lowest_percent_deviation", "acceptance")
    regular = _number(acceptance["percent_deviation"], "percent deviation", 0, 100)
    lowest = _number(acceptance["lowest_percent_deviation"], "lowest deviation", 0, 100)
    _require(lowest > regular, "acceptance-rule", "lowest level requires a looser deviation limit")
    _number(record["min_levels"], "minimum levels", 3, MAX_ROWS, integer=True)
    _number(record["min_replicates"], "minimum replicates", 2, MAX_ROWS, integer=True)
    rule = _fields(record["limit_rule"], "method min_blanks lod_k loq_k", "limit rule")
    method = _text(rule["method"], "limit method")
    _require(method in {"blank-mean", "calibration-slope"}, "limit-rule", "unsupported detection rule")
    _number(rule["min_blanks"], "minimum blanks", 3, MAX_ROWS, integer=True)
    lod_k = _number(rule["lod_k"], "LOD multiplier", 0, 100)
    loq_k = _number(rule["loq_k"], "LOQ multiplier", 0, 100)
    _require(0 < lod_k < loq_k and (method != "calibration-slope" or (lod_k == 3.3 and loq_k == 10)),
             "limit-rule", "freeze ordered positive multipliers; slope rule requires 3.3 and 10")
    validity = _fields(record["validity"], "min max", "validity")
    low = _number(validity["min"], "validity minimum", 0)
    high = _number(validity["max"], "validity maximum", 0)
    _require(0 < low < high, "validity-range", "positive ordered validity endpoints required")
    exclusion = _text(record["exclusion_rule"], "exclusion rule")
    _require(exclusion in {"none", "failed-back-calculation-once"},
             "exclusion-rule", "only no exclusion or one frozen deviation-based refit is supported")
    return record


def _data(record, protocol):
    _record(record, "calibration-lod-data-v1", "standards blanks unknowns")
    standards = _items(record["standards"], "standards", MAX_ROWS)
    blanks = _items(record["blanks"], "blanks", MAX_ROWS, empty=True)
    unknowns = _items(record["unknowns"], "unknowns", MAX_ROWS, empty=True)
    seen = set()
    previous = 0
    levels = {}
    for category, rows in (("standards", standards), ("blanks", blanks), ("unknowns", unknowns)):
        for row in rows:
            _fields(row, "id response concentration_unit response_unit" +
                    (" concentration" if category == "standards" else ""), category)
            name = _text(row["id"], "row id")
            _require(name not in seen, "data-identity", "all standard, blank and unknown IDs must be unique")
            seen.add(name)
            _number(row["response"], "response")
            for unit in ("concentration_unit", "response_unit"):
                _text(row[unit], unit)
                _require(row[unit] == protocol[unit], "unit-mismatch", "standards, blanks and unknowns require frozen units")
            if category == "standards":
                concentration = _number(row["concentration"], "nominal concentration")
                _require(concentration > 0, "nonpositive-concentration", "nominal concentrations must be strictly positive")
                _require(concentration >= previous, "level-order", "standard levels must be strictly increasing with contiguous replicates")
                previous = concentration
                levels[concentration] = levels.get(concentration, 0) + 1
    _counts(standards, protocol)
    _require(min(levels) <= protocol["validity"]["min"] < protocol["validity"]["max"] <= max(levels),
             "validity-range", "validity cannot exceed the supplied standards")
    _require(len(blanks) >= protocol["limit_rule"]["min_blanks"],
             "insufficient-blanks", "both rules require the frozen minimum independent blank responses")
    return standards, blanks, unknowns


def _counts(rows, protocol):
    levels = {}
    for row in rows:
        x = row["concentration"]
        levels[x] = levels.get(x, 0) + 1
    _require(len(levels) >= protocol["min_levels"] and
             all(n >= protocol["min_replicates"] for n in levels.values()),
             "insufficient-standards", "frozen minimum levels and replicates must survive exclusion")
    return levels


def _fit(rows, protocol):
    x = [row["concentration"] for row in rows]
    y = [row["response"] for row in rows]
    power = {"none": 0, "1/x": 1, "1/x^2": 2}[protocol["weighting"]]
    # Normalizing weights preserves the fit and avoids inverse powers of tiny x.
    minimum = min(x)
    weights = [(minimum / value) ** power for value in x]
    _require(all(w > 0 for w in weights), "degenerate-fit", "weights underflowed")
    total = math.fsum(weights)
    xmean = math.fsum(w * value for w, value in zip(weights, x)) / total
    ymean = math.fsum(w * value for w, value in zip(weights, y)) / total
    centered = protocol["intercept"] == "free"
    xcenter = xmean if centered else 0
    ycenter = ymean if centered else 0
    denominator = math.fsum(w * (value - xcenter) ** 2 for w, value in zip(weights, x))
    _require(denominator > 0, "degenerate-fit", "zero concentration variance")
    slope = math.fsum(w * (a - xcenter) * (b - ycenter) for w, a, b in zip(weights, x, y)) / denominator
    _require(math.isfinite(slope) and slope > 0, "degenerate-fit", "finite positive slope required")
    intercept = ymean - slope * xmean if centered else 0.0
    residuals = [b - (intercept + slope * a) for a, b in zip(x, y)]
    sst = math.fsum(w * (b - ymean) ** 2 for w, b in zip(weights, y))
    _require(sst > 0, "degenerate-fit", "zero response variance")
    sse = math.fsum(w * r ** 2 for w, r in zip(weights, residuals))
    df = len(rows) - (2 if centered else 1)
    _require(df > 0, "degenerate-fit", "not enough residual degrees of freedom")
    back = []
    lowest = min(x)
    for row, residual in zip(rows, residuals):
        nominal = row["concentration"]
        value = (row["response"] - intercept) / slope
        deviation = 100 * (value - nominal) / nominal
        threshold = protocol["acceptance"]["lowest_percent_deviation" if nominal == lowest else "percent_deviation"]
        back.append({"id": row["id"], "concentration": value, "percent_deviation": deviation,
                     "limit_percent": threshold, "failed": abs(deviation) > threshold, "residual": residual})
    return {"slope": slope, "intercept": intercept, "r_squared": 1 - sse / sst,
            "residual_standard_error": math.sqrt(math.fsum(r ** 2 for r in residuals) / df),
            "n": len(rows), "df": df, "back_calculated": back}


def reference_computation(protocol, data):
    """Compute one frozen synthetic fixture; never extrapolate unknown concentrations."""
    try:
        protocol = _protocol(protocol)
        standards, blanks, unknowns = _data(data, protocol)
        initial = _fit(standards, protocol)
        failed = [item["id"] for item in initial["back_calculated"] if item["failed"]]
        excluded = failed if protocol["exclusion_rule"] == "failed-back-calculation-once" else []
        removed = set(excluded)
        retained = [row for row in standards if row["id"] not in removed]
        counts = _counts(retained, protocol)
        fit = _fit(retained, protocol) if excluded else initial
        _require(min(counts) <= protocol["validity"]["min"] and protocol["validity"]["max"] <= max(counts),
                 "validity-range", "exclusion cannot remove validity support")
        responses = [row["response"] for row in blanks]
        mean = math.fsum(responses) / len(responses)
        sd = statistics.stdev(responses)
        _require(math.isfinite(sd) and sd > 0, "degenerate-blanks", "nonzero blank sample standard deviation required")
        rule = protocol["limit_rule"]
        offset = mean - fit["intercept"] if rule["method"] == "blank-mean" else 0
        lod = (offset + rule["lod_k"] * sd) / fit["slope"]
        loq = (offset + rule["loq_k"] * sd) / fit["slope"]
        _require(0 <= lod < loq, "limit-order", "nonnegative ordered detection limits required")
        _require(min(counts) <= loq <= max(counts) and
                 protocol["validity"]["min"] <= loq <= protocol["validity"]["max"],
                 "loq-range", "LOQ must lie within the retained standard levels and frozen validity range")
        acceptance = "failed" if any(row["failed"] for row in fit["back_calculated"]) else "passed"
        unknown_results = []
        for row in unknowns:
            value = (row["response"] - fit["intercept"]) / fit["slope"]
            _require(math.isfinite(value), "degenerate-fit", "unknown back-calculation is non-finite")
            if not protocol["validity"]["min"] <= value <= protocol["validity"]["max"]:
                status, concentration = "out-of-range", None
            elif acceptance == "failed":
                status, concentration = "unavailable", None
            else:
                status, concentration = ("below-loq" if value < loq else "in-range"), value
            unknown_results.append({"id": row["id"], "status": status, "concentration": concentration})
        original_counts = _counts(standards, protocol)
        result = {"initial_fit": initial, "fit": fit, "excluded_ids": excluded,
                  "levels": [{"concentration": x, "n_initial": n, "n_retained": counts.get(x, 0)}
                             for x, n in original_counts.items()],
                  "limits": {"method": rule["method"], "blank_n": len(blanks), "blank_mean": mean,
                             "blank_sd": sd, "lod": lod, "loq": loq},
                  "unknowns": unknown_results, "acceptance": acceptance}
        _finite_tree(result)
        return result
    except (OverflowError, ZeroDivisionError) as error:
        raise ValueError("degenerate-fit: numerical range exceeded") from error


def _finite_tree(value):
    if type(value) in (int, float):
        _require(math.isfinite(value), "degenerate-fit", "non-finite computation")
    elif type(value) is dict:
        for child in value.values():
            _finite_tree(child)
    elif type(value) is list:
        for child in value:
            _finite_tree(child)


def _matching(actual, expected):
    if type(expected) is dict:
        _require(type(actual) is dict and set(actual) == set(expected), "report-mismatch", "incomplete calculation evidence")
        for key, value in expected.items():
            _matching(actual[key], value)
    elif type(expected) is list:
        _require(type(actual) is list and len(actual) == len(expected), "report-mismatch", "calculation row mismatch")
        for a, b in zip(actual, expected):
            _matching(a, b)
    elif type(expected) is int:
        _require(type(actual) is int and actual == expected, "report-mismatch", "integer evidence mismatch")
    elif type(expected) is float:
        _number(actual, "reported number")
        _require(math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-10), "report-mismatch", "numerical evidence mismatch")
    else:
        _require(type(actual) is type(expected) and actual == expected, "report-mismatch", "calculation evidence mismatch")


def _report(report, protocol, result):
    _record(report, "calibration-lod-report-v1", "model weighting intercept exploratory acceptance_evidence calculation")
    for key in ("model", "weighting", "intercept"):
        _text(report[key], key)
    exploratory = _boolean(report["exploratory"], "exploratory")
    _require(report["intercept"] == protocol["intercept"], "intercept-choice", "reported intercept differs from frozen choice")
    _require(report["model"] == protocol["model"], "model-choice", "reported model differs from frozen choice")
    _require(report["weighting"] == protocol["weighting"] or exploratory,
             "post-outcome-weights", "changed weights require an exploratory label and a separate frozen rerun")
    _require(report["weighting"] == protocol["weighting"], "exploratory-rerun", "exploratory changes need a separate bundle; preserve this frozen calculation")
    _require(report["acceptance_evidence"] == ACCEPTANCE_EVIDENCE,
             "r-squared-only", "R-squared alone is insufficient: deviations, replicates and residuals are required")
    calculation = report["calculation"]
    _require(type(calculation) is dict, "invalid-record", "calculation must be an object")
    _require(calculation.get("excluded_ids") == result["excluded_ids"],
             "unfrozen-exclusion", "standards may be excluded only by the frozen rule, with initial fit and refit retained")
    _require(type(calculation.get("unknowns")) is list, "invalid-record", "unknown results must be a list")
    _items(calculation["unknowns"], "reported unknowns", MAX_ROWS, empty=True)
    expected_unknowns = {row["id"]: row for row in result["unknowns"]}
    for row in calculation["unknowns"]:
        _fields(row, "id status concentration", "reported unknown")
        name = _text(row["id"], "reported unknown id")
        if name in expected_unknowns and expected_unknowns[name]["status"] == "out-of-range":
            _require(row["status"] == "out-of-range" and row["concentration"] is None,
                     "unknown-extrapolation", "out-of-range unknowns cannot have extrapolated concentrations")
    limits = calculation.get("limits")
    _require(type(limits) is dict, "invalid-record", "reported limits must be an object")
    loq = _number(limits.get("loq"), "reported LOQ")
    _require(protocol["validity"]["min"] <= loq <= protocol["validity"]["max"],
             "loq-range", "reported LOQ cannot fall outside supplied standards and frozen validity")
    _matching(calculation, result)


def _evidence(record):
    _record(record, "calibration-lod-evidence-v1", "kind result")
    return _text(record["kind"], "evidence kind"), _text(record["result"], "evidence result")


def _claims(bundle, claims, own, acceptance):
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
                 "claim-boundary", "only bounded descriptive arithmetic is admitted")
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
            evidence = bundle.load(plain)
            evidence_kind, evidence_result = _evidence(evidence)
            if origin != "study":
                _require(not any(identity["path"] == item["path"] or identity["sha256"] == item["sha256"] for item in own),
                         "evidence-independence", "outside evidence aliases this study's input or output")
            sources.append((evidence_kind, evidence_result))
        _require(status == "unavailable" or all("unavailable" not in source for source in sources),
                 "unavailable-evidence", "any unavailable citation requires unavailable status")
        if status in POSITIVE:
            for evidence_kind, evidence_result in sources:
                _require(NON_EVIDENCE.search(evidence_kind) is None and NON_EVIDENCE.search(evidence_result) is None,
                         "non-evidence", "review approval and computed agreement are not positive scientific evidence")
        _require(status != "replicated", "claim-replication", "one synthetic fixture cannot establish replication")
        _require(status not in POSITIVE or acceptance == "passed", "failed-controls", "failed standards cannot support a positive claim")
        _require(status not in POSITIVE, "synthetic-evidence", "synthetic arithmetic cannot establish positive scientific evidence")
    return claims


def validate_calibration_lod_pack(path):
    """Validate an immutable pack JSON and its relative hashed synthetic input records."""
    bundle = None
    try:
        bundle = _Bundle(path)
        bundle._check_root()
        pack, digest = bundle.snapshot(bundle.path.name)
        _record(pack, "calibration-lod-pack-v1", "stages inputs frozen_protocol_sha256 freeze_before_responses "
                "frozen_at responses_read_at study_outputs claims")
        _require(pack["stages"] == list(STAGES), "stage-order", "exactly five ordered stages required")
        inputs = _fields(pack["inputs"], "protocol data report", "inputs")
        protocol = _protocol(bundle.load(inputs["protocol"]))
        _require(_boolean(pack["freeze_before_responses"], "freeze_before_responses") and
                 pack["frozen_protocol_sha256"] == inputs["protocol"]["sha256"] and
                 _time(pack["frozen_at"]) < _time(pack["responses_read_at"]),
                 "protocol-freeze", "rules must be hash-frozen before reading responses")
        result = reference_computation(protocol, bundle.load(inputs["data"]))
        _report(bundle.load(inputs["report"]), protocol, result)
        outputs = _items(pack["study_outputs"], "study outputs", MAX_SUPPORT, empty=True)
        for identity in outputs:
            _evidence(bundle.load(identity))
        own = [*inputs.values(), *outputs, {"path": bundle.path.name, "sha256": digest}]
        claims = _claims(bundle, pack["claims"], own, result["acceptance"])
        bundle.recheck()
        return {"schema": "calibration-lod-result-v1", "schema_version": 1, "fixture": True,
                "stages": list(STAGES), "evidence_level": "synthetic-arithmetic-only", "review": "unavailable",
                "protocol_sha256": pack["frozen_protocol_sha256"], "calculation": result, "claims": claims,
                "input_identities": [{"path": name, "sha256": value[1]} for name, value in sorted(bundle.cache.items())],
                "limitations": ["Synthetic fixtures check arithmetic only; supplied standards bound every estimate.",
                                "Hashes and timestamps cannot prove historical freeze timing or source authenticity.",
                                "No physical, clinical, diagnostic or patient-level meaning is established.",
                                "The conservative English lexical claim filter is incomplete and refuses negations too.",
                                "The coordinator owns rigor and independent review; approval is never truth."]}
    except OSError as error:
        raise ValueError("input-file: unavailable regular input or symlinked component") from error
    except (RecursionError, OverflowError, UnicodeError) as error:
        raise ValueError("invalid-record: bounded finite inputs required") from error
    finally:
        if bundle is not None:
            bundle.close()
