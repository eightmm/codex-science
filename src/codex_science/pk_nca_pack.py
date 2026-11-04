"""Offline arithmetic checks for supplied preclinical concentration-time fixtures."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import statistics

STAGES = ("01-rule-freeze", "02-profile-qc", "03-subject-parameters", "04-group-summary", "05-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_JSON_VALUES = 4_000_000
MAX_ARTIFACTS = 128
MAX_ROWS = 10000
MAX_ITEMS = 20000
MAX_SUBJECTS = 128
MAX_POINTS = 1024
MAX_RECORDS = 128
MAX_STRING = 4096
MAX_DEPTH = 32
MAX_NUMBER = 1e100
PARAMETERS = ("cmax", "tmax", "auc_0_tlast", "lambda_z", "half_life", "auc_0_inf", "extrapolated_fraction")
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
    r"bioavailab\w*|safe[\s-]+dose|human[\s-]+exposure|exposure[\s-]+response|"
    r"physical[\s-]+validity)\b", re.I,
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
    _require(type(value) is dict and len(value) == len(expected) and set(value) == set(expected),
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
    _require(len(pairs) <= MAX_ITEMS, "input-limit", "JSON object exceeds entry limit")
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


def _json(raw, allowance):
    estimate = 1 + raw.count(b",") + sum(1 for _ in re.finditer(rb"[\[{](?=\s*[^\s\]}])", raw))
    _require(estimate <= allowance, "input-limit", "bundle JSON value allowance exceeded")
    try:
        root = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=_constant, parse_int=_int, parse_float=_float)
        _require(type(root) is dict, "invalid-json", "JSON root must be an object")
        pending = [(root, 0)]
        while pending:
            value, depth = pending.pop()
            _require(depth <= MAX_DEPTH, "invalid-json", "JSON nesting limit exceeded")
            if type(value) is dict:
                _require(len(value) <= MAX_ITEMS, "input-limit", "JSON object too large")
                children = list(value.keys()) + list(value.values())
            elif type(value) is list:
                _require(len(value) <= MAX_ITEMS, "input-limit", "JSON list too large")
                children = value
            else:
                if type(value) is str:
                    _require(len(value) <= MAX_STRING and not any(0xD800 <= ord(c) <= 0xDFFF for c in value),
                             "invalid-record", "JSON string exceeds bounds or has surrogate characters")
                continue
            pending.extend((child, depth + 1) for child in children)
        return root, estimate
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
        self.total_bytes = 0
        self.nodes = 0
        self.parsed = {}
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
            _require(len(self.snapshots) < MAX_ARTIFACTS, "input-limit", "too many artifacts")
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
            value, count = _json(raw, MAX_JSON_VALUES - self.nodes)
            self.nodes += count
            self.parsed[identity] = value
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


def _rules(value):
    _require(type(value) is dict and all(name in value for name in ("nominal_dose", "dose_unit", "route", "time_unit", "concentration_unit")),
             "dose-units", "dose, route and units must be supplied")
    _record(value, "pk-nca-rules-v1", "subject_unit system route nominal_dose dose_unit time_unit "
            "concentration_unit sampling_schedule lloq below_limit_rule substitution trapezoid "
            "terminal_window minimum_terminal_points minimum_adjusted_r_squared "
            "maximum_extrapolated_fraction parameters")
    for field in ("subject_unit", "route", "dose_unit", "time_unit", "concentration_unit"):
        _require(field in value and type(value[field]) is str and bool(value[field].strip()),
                 "dose-units", "subject, route, dose and units must be recorded")
        _text(value[field], field)
    _require(type(value["system"]) is str and value["system"] in {"animal", "in-vitro"},
             "preclinical-only", "only animal or in-vitro supplied profiles are admitted")
    _require(type(value["nominal_dose"]) in (int, float) and 0 < value["nominal_dose"] <= 1e12,
             "dose-units", "nominal dose must be positive and finite")
    _number(value["lloq"], "lloq", 0, 1e12)
    schedule = _list(value["sampling_schedule"], "sampling_schedule", MAX_POINTS)
    for time in schedule:
        _number(time, "scheduled time", 0, 1e12)
    _require(all(a < b for a, b in zip(schedule, schedule[1:])),
             "sampling-schedule", "scheduled times must be unique and strictly increasing")
    _require(type(value["below_limit_rule"]) is str and value["below_limit_rule"] in {"censored", "substitute"},
             "below-limit-rule", "censoring rule must be frozen")
    if value["below_limit_rule"] == "censored":
        _require(value["substitution"] is None, "below-limit-rule", "no implicit substitution")
    else:
        _number(value["substitution"], "substitution", 0, value["lloq"])
    _require(value["trapezoid"] == "linear-up/log-down", "trapezoid-method", "unsupported trapezoid method")
    _number(value["minimum_terminal_points"], "minimum_terminal_points", 3, MAX_POINTS, True)
    _number(value["minimum_adjusted_r_squared"], "minimum_adjusted_r_squared", 0, 1)
    _number(value["maximum_extrapolated_fraction"], "maximum_extrapolated_fraction", 0, 1)
    window = _list(value["terminal_window"], "terminal_window", MAX_POINTS)
    for time in window:
        _number(time, "terminal time", 0, 1e12)
    _require(all(a < b for a, b in zip(window, window[1:])) and set(window) <= set(schedule),
             "terminal-window", "frozen window must be ordered scheduled times")
    _require(_names(value["parameters"], "parameters", len(PARAMETERS)) == list(PARAMETERS),
             "parameters", "all reference parameters must be declared in order")
    return value


def _profiles(value, rules):
    _record(value, "pk-nca-profiles-v1", "subjects")
    subjects = _list(value["subjects"], "subjects", MAX_SUBJECTS)
    # Bound the aggregate before validating or computing any per-subject table.
    total = 0
    for subject in subjects:
        _fields(subject, "subject_id concentration_unit time_unit points", "subject")
        total += len(_list(subject["points"], "points", MAX_POINTS))
        _require(total <= MAX_ROWS, "input-limit", "total profile rows exceed limit")
    seen = set()
    schedule = set(rules["sampling_schedule"])
    for subject in subjects:
        identity = _text(subject["subject_id"], "subject_id")
        _require(identity not in seen, "subject-identity", "duplicate subject")
        seen.add(identity)
        _require(subject["concentration_unit"] == rules["concentration_unit"]
                 and subject["time_unit"] == rules["time_unit"],
                 "units-mismatch", "units must match frozen rules for every subject")
        _fields(subject["points"][0], "time concentration censored", "point")
        _require(subject["points"][0]["time"] == 0, "time-origin", "AUC(0-tlast) requires a measured time-zero point")
        previous = -1
        quantified = []
        for point in subject["points"]:
            _fields(point, "time concentration censored", "point")
            time = _number(point["time"], "time", 0, 1e12)
            _require(time > previous, "profile-time", "times must be unique and strictly increasing")
            previous = time
            _require(time in schedule, "sampling-schedule", "unscheduled measured time")
            _boolean(point["censored"], "censored")
            if point["censored"]:
                _require(point["concentration"] is None, "below-limit-zero", "censored values must remain null, never zero")
            else:
                concentration = _number(point["concentration"], "concentration", 0, 1e12)
                _require(concentration >= rules["lloq"], "below-limit-unmarked", "below-limit measurement must be censored")
                quantified.append(point)
        _require(bool(quantified), "empty-profile", "no quantifiable measured concentrations")
        last_time = quantified[-1]["time"]
        _require(rules["below_limit_rule"] == "substitute" or
                 all(not p["censored"] for p in subject["points"] if p["time"] <= last_time),
                 "censored-gap", "interior censored point requires frozen substitution")
    return subjects


def _terminal(points, rules):
    selected = set(rules["terminal_window"])
    tail = [p for p in points if p["time"] in selected and not p["censored"] and p["concentration"] > 0]
    count = len(tail)
    if count < rules["minimum_terminal_points"]:
        return count, "unavailable", "unavailable", ["terminal-points"]
    times = [p["time"] for p in tail]
    logs = [math.log(p["concentration"]) for p in tail]
    tx, ly = statistics.mean(times), statistics.mean(logs)
    dx = [time - tx for time in times]
    dy = [value - ly for value in logs]
    xx = math.fsum(value * value for value in dx)
    yy = math.fsum(value * value for value in dy)
    if xx == 0 or yy == 0:
        return count, "unavailable", "unavailable", ["terminal-degenerate"]
    slope = math.fsum(x * y for x, y in zip(dx, dy)) / xx
    residual = math.fsum((y - slope * x) ** 2 for x, y in zip(dx, dy))
    adjusted = 1 - (residual / yy) * (count - 1) / (count - 2)
    if not math.isfinite(slope) or not math.isfinite(adjusted):
        return count, "unavailable", "unavailable", ["terminal-degenerate"]
    reasons = []
    if slope >= 0:
        reasons.append("terminal-nondecreasing")
    if adjusted < rules["minimum_adjusted_r_squared"]:
        reasons.append("terminal-fit")
    return count, adjusted, -slope if slope < 0 else "unavailable", reasons


def compute_nca(profiles, rules):
    """Compute arithmetic summaries; censored tails never enter the terminal fit."""
    rules = _rules(rules)
    subjects = _profiles(profiles, rules)
    results = []
    for subject in subjects:
        points = subject["points"]
        observed = [p for p in points if not p["censored"]]
        peak = max(observed, key=lambda p: p["concentration"])
        last = observed[-1]
        numeric = [(p["time"], rules["substitution"] if p["censored"] else p["concentration"])
                   for p in points if p["time"] <= last["time"]]
        pieces = []
        for (ta, ca), (tb, cb) in zip(numeric, numeric[1:]):
            if ca > cb > 0:
                ratio_log = math.log1p((ca - cb) / cb) if ca - cb <= cb else math.log(ca) - math.log(cb)
                area = (tb - ta) * (ca - cb) / ratio_log
            else:
                area = (tb - ta) * (ca + cb) / 2
            pieces.append(area)
        auc = math.fsum(pieces)
        count, adjusted, rate, reasons = _terminal(points, rules)
        fraction = "unavailable"
        half_life = auc_inf = "unreliable"
        if type(rate) in (int, float):
            tail_auc = last["concentration"] / rate
            total_auc = auc + tail_auc
            if total_auc <= 0 or not math.isfinite(total_auc):
                reasons.append("terminal-degenerate")
            else:
                fraction = tail_auc / total_auc
                if fraction > rules["maximum_extrapolated_fraction"]:
                    reasons.append("extrapolated-fraction")
                if not reasons:
                    half_life = math.log(2) / rate
                    auc_inf = total_auc
        results.append({"subject_id": subject["subject_id"], "cmax": peak["concentration"],
                        "tmax": peak["time"], "cmax_source": "observed",
                        "auc_0_tlast": auc, "terminal_points": count,
                        "adjusted_r_squared": adjusted, "lambda_z": rate,
                        "half_life": half_life, "auc_0_inf": auc_inf,
                        "extrapolated_fraction": fraction,
                        "status": "unreliable" if reasons else "reliable", "reasons": reasons})
    included = [row for row in results if row["status"] == "reliable"]
    summary = {}
    for name in PARAMETERS:
        values = [row[name] for row in included]
        summary[name] = {"n": len(values), "geometric_mean":
                         math.exp(statistics.mean(math.log(v) for v in values)) if values and min(values) > 0 else "unavailable",
                         "range": [min(values), max(values)] if values else "unavailable"}
    return {"subjects": results, "group": {"subject_ids": [row["subject_id"] for row in included],
                                           "n": len(included), "parameters": summary}}


def _same(actual, expected, label):
    if type(expected) is dict:
        _fields(actual, expected, label)
        for name in expected:
            _same(actual[name], expected[name], name)
    elif type(expected) is list:
        _list(actual, label, MAX_ROWS, True)
        _require(len(actual) == len(expected), "reported-value", f"{label} length differs")
        for left, right in zip(actual, expected):
            _same(left, right, label)
    elif type(expected) is int and label in {"n", "terminal_points"}:
        _require(type(actual) is int and actual == expected, "reported-value", f"{label} differs or is not an integer")
    elif type(expected) in (int, float):
        _number(actual, label, -MAX_NUMBER)
        _require(math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-12), "reported-value", f"{label} differs")
    else:
        _require(type(actual) is type(expected) and actual == expected, "reported-value", f"{label} differs")


def _claims(claims, records):
    claims = _list(claims, "claims", MAX_RECORDS, True)
    seen = set()
    for claim in claims:
        _fields(claim, "id kind status text evidence", "claim")
        identity = _text(claim["id"], "claim id")
        _require(identity not in seen, "claim-identity", "duplicate claim id")
        seen.add(identity)
        kind = _text(claim["kind"], "claim kind")
        status = _text(claim["status"], "claim status")
        text = _text(claim["text"], "claim text")
        _require(status in STATUSES and kind in {"descriptive", "associational", "causal", "confirmatory"},
                 "claim-status", "unknown status or kind")
        support = _names(claim["evidence"], "claim evidence", MAX_RECORDS, True)
        _require(all(name in records for name in support), "claim-evidence", "unknown evidence identity")
        unavailable = not support or any(records[name]["kind"] == "unavailable" or
                                         records[name]["result"] == "unavailable" for name in support)
        _require(not unavailable or status == "unavailable", "unavailable-evidence", "missing evidence requires unavailable status")
        _require(not OVERREACH.search(text) and kind != "causal", "claim-boundary", "wording exceeds supplied-profile arithmetic")
        _require(status != "unavailable" or not ASSERTION.search(text), "unavailable-positive", "unavailable text asserts positive evidence")
        _require(status != "replicated", "replication", "synthetic fixtures cannot establish replication")
        if status in POSITIVE:
            _require(all(not NON_EVIDENCE.search(records[name][field]) for name in support for field in ("kind", "result")),
                     "claim-computed", "computed quantities and review approval cannot support positive claims")


def validate_pk_nca_pack(bundle):
    """Validate one hash-bound bundle, print no claims of independent review, write nothing."""
    _require(isinstance(bundle, (str, os.PathLike)), "input-path", "bundle must be a filesystem path")
    spelling = os.fspath(bundle)
    _require(type(spelling) is str and 0 < len(spelling) <= MAX_STRING and all(ord(c) >= 32 for c in spelling),
             "input-path", "bounded bundle path without control characters required")
    root = Path(os.path.abspath(spelling))
    reader = None
    try:
        reader = _Bundle(root.parent)
        pack = reader.load(root.name)
        _record(pack, "pk-nca-pack-v1", "stages frozen_rules rules profiles report evidence")
        _require(_names(pack["stages"], "stages", len(STAGES)) == list(STAGES), "stage-order", "five ordered stages required")
        _rules(reader.artifact(pack["frozen_rules"]))
        rules = _rules(reader.artifact(pack["rules"]))
        report = reader.artifact(pack["report"])
        _record(report, "pk-nca-report-v1", "rules_sha256 exploratory computation claims statement")
        _boolean(report["exploratory"], "exploratory")
        _require(report["rules_sha256"] == pack["rules"]["sha256"], "rule-identity", "reported rule hash differs")
        _require(pack["frozen_rules"]["sha256"] == pack["rules"]["sha256"] or report["exploratory"],
                 "post-hoc-rules", "changed rules require an exploratory label")
        profiles = reader.artifact(pack["profiles"])
        computed = compute_nca(profiles, rules)
        own = [pack[name] for name in ("frozen_rules", "rules", "profiles", "report")]
        records = {}
        evidence = reader.artifact(pack["evidence"])
        _record(evidence, "pk-nca-evidence-v1", "records")
        for record in _list(evidence["records"], "records", MAX_RECORDS, True):
            _fields(record, "id kind result origin source", "evidence record")
            identity = _text(record["id"], "record id")
            _require(identity not in records, "evidence-identity", "duplicate evidence id")
            for field in ("kind", "result", "origin"):
                _text(record[field], field)
            _require(record["origin"] in {"internal", "external", "independent", "preregistered"},
                     "evidence-origin", "unknown origin")
            digest = reader.artifact(record["source"], False)
            if record["origin"] != "internal":
                _require(all(record["source"]["path"] != item["path"] and digest != item["sha256"] for item in own)
                         and record["source"]["path"] != pack["evidence"]["path"]
                         and digest != pack["evidence"]["sha256"],
                         "external-alias", "external label aliases this study's own artifact")
            records[identity] = record
        _claims(report["claims"], records)
        statement = _text(report["statement"], "statement")
        _require(not OVERREACH.search(statement), "claim-boundary", "statement exceeds supplied-profile arithmetic")
        _require(statement == "Arithmetic summaries of the supplied profiles only.", "output-boundary", "fixed arithmetic boundary required")
        claimed = _fields(report["computation"], "subjects group", "computation")
        rows = _list(claimed["subjects"], "reported subjects", MAX_SUBJECTS)
        _require(len(rows) == len(computed["subjects"]), "reported-value", "subject count differs")
        for row, expected in zip(rows, computed["subjects"]):
            _fields(row, expected, "reported subject")
            _require(row["cmax_source"] == "observed", "cmax-interpolated", "Cmax must be an observed concentration")
            if "terminal-points" in expected["reasons"]:
                _require(row["auc_0_inf"] == "unreliable" and row["half_life"] == "unreliable",
                         "terminal-points", "terminal fit used fewer than frozen minimum points")
            if "terminal-fit" in expected["reasons"] or "terminal-degenerate" in expected["reasons"] or "terminal-nondecreasing" in expected["reasons"]:
                _require(row["auc_0_inf"] == "unreliable" and row["half_life"] == "unreliable",
                         "terminal-fit", "terminal slope fails frozen criteria")
            if "extrapolated-fraction" in expected["reasons"]:
                _require(row["auc_0_inf"] == "unreliable" and row["half_life"] == "unreliable",
                         "extrapolated-fraction", "excess extrapolation must remain unreliable")
        group = _fields(claimed["group"], "subject_ids n parameters", "group")
        _require(_names(group["subject_ids"], "group subject_ids", MAX_SUBJECTS, True) == computed["group"]["subject_ids"],
                 "unreliable-group", "group includes unreliable subjects or omits reliable subjects")
        _same(claimed, computed, "computation")
        reader.finish()
        return {"schema": "pk-nca-result-v1", "fixture": "synthetic fixture", "status": "arithmetic-only",
                "review": "unavailable", "stages": list(STAGES), "exploratory": report["exploratory"],
                "rules_sha256": pack["rules"]["sha256"], "computation": computed, "statement": statement}
    except (OSError, UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError("input-file: bounded accessible fixture inputs required") from error
    finally:
        if reader is not None:
            reader.close()
