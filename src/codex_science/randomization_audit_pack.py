"""Offline synthetic allocation audit; immutable inputs and bounded reference arithmetic."""
from __future__ import annotations

from datetime import datetime
import hashlib
from itertools import combinations
import json
import math
import os
from pathlib import Path, PurePosixPath
import random
import re
import stat
import statistics

STAGES = ("01-freeze", "02-table-qc", "03-reproduction", "04-summary", "05-handoff")
ALGORITHM = "stdlib-mt19937-fisher-yates-v1"
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_JSON_VALUES = 4000000
MAX_ARTIFACTS = 128
MAX_UNITS = 10000
MAX_ARMS = 8
MAX_COVARIATES = 16
MAX_STRATA = 8
MAX_GROUPS = 128
MAX_METRICS = 60000
MAX_RECORDS = 128
MAX_ITEMS = 100000
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
    r"inhibit\w*|activat\w*|regulat\w*|driv\w*|induc\w*|unbiased|valid\w*|"
    r"confirmatory|truth|patient[\s-]+benefit\w*)\b", re.I)
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
    _fields(value, "schema schema_version fixture " + fields, schema)
    _number(value["schema_version"], "schema_version", 1, 1, integer=True)
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


def _json(raw, allowance):
    upper = 1 + raw.count(b",") + sum(1 for _ in re.finditer(rb"[\[{](?=\s*[^\s\]}])", raw))
    _require(upper <= allowance, "input-limit", "bundle JSON value allowance exceeded")
    try:
        root = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=_constant, parse_int=_int, parse_float=_float)
        _require(type(root) is dict, "invalid-json", "JSON root must be an object")
        pending = [(root, 0)]
        while pending:
            value, depth = pending.pop()
            _require(depth <= MAX_DEPTH, "invalid-json", "JSON nesting limit exceeded")
            if type(value) in (dict, list):
                _require(len(value) <= MAX_ITEMS, "input-limit", "JSON container too large")
                if type(value) is dict:
                    for key in value:
                        _text(key, "JSON key")
                    children = value.values()
                else:
                    children = value
                pending.extend((child, depth + 1) for child in children)
            elif type(value) is str:
                _text(value, "JSON string")
        return root, upper
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
                    _require(len(self.cache) < MAX_ARTIFACTS, "input-limit", "too many artifacts")
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
            record, count = _json(raw, MAX_JSON_VALUES - self.nodes)
            self.nodes += count
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


def _time(value):
    try:
        result = datetime.fromisoformat(_text(value, "time").replace("Z", "+00:00"))
        _require(result.tzinfo is not None, "allocation-time", "timezone-aware time required")
        return result
    except (ValueError, OverflowError) as error:
        raise ValueError("allocation-time: valid timezone-aware time required") from error


def _protocol(value):
    _require(type(value) is dict and "blinding" in value, "blinding-missing", "blinding statement missing")
    _record(value, "randomization-audit-protocol-v1", "units arms allocation_ratio method "
            "block_size strata seed algorithm blinding allocation_concealment thresholds "
            "covariates minimum_per_arm outcome_available_at")
    arms = _names(value["arms"], "arms", MAX_ARMS)
    _require(len(arms) >= 2, "invalid-record", "at least two arms required")
    ratio = _list(value["allocation_ratio"], "allocation_ratio", MAX_ARMS)
    _require(len(ratio) == len(arms), "allocation-ratio", "one ratio weight per arm required")
    for weight in ratio:
        _number(weight, "ratio weight", 1, MAX_UNITS, integer=True)
    _require(sum(ratio) <= MAX_UNITS, "input-limit", "ratio roster exceeds unit limit")
    _text(value["method"], "method")
    _require(value["method"] in {"simple", "permuted-block", "stratified-permuted-block"},
             "invalid-record", "unsupported allocation method")
    strata = _names(value["strata"], "strata", MAX_STRATA, True)
    if value["method"] == "stratified-permuted-block":
        _require(bool(strata), "strata-ignored", "stratified method requires named strata")
    else:
        _require(not strata, "strata-ignored", "non-stratified method cannot declare strata")
    if value["method"] == "simple":
        _require(value["block_size"] is None, "block-size", "simple method has no block size")
    else:
        size = _number(value["block_size"], "block_size", 1, MAX_UNITS, integer=True)
        _require(size % sum(ratio) == 0, "block-size", "block size must be a multiple of ratio sum")
    _number(value["seed"], "seed", 0, 2**64 - 1, integer=True)
    _require(value["algorithm"] == ALGORITHM, "random-procedure", "unknown random algorithm version")
    _require(type(value["blinding"]) is str and bool(value["blinding"].strip()),
             "blinding-missing", "explicit blinding statement required, including unblinded designs")
    _text(value["blinding"], "blinding")
    _text(value["allocation_concealment"], "allocation_concealment")
    covariates = value["covariates"]
    _require(type(covariates) is dict and 0 < len(covariates) <= MAX_COVARIATES,
             "input-limit", "bounded nonempty covariate map required")
    for name, kind in covariates.items():
        _text(name, "covariate name")
        _text(kind, "covariate kind")
        _require(kind in {"continuous", "binary"}, "invalid-record", "unsupported covariate kind")
    limits = _fields(value["thresholds"], "smd risk_difference", "thresholds")
    _number(limits["smd"], "smd threshold", 0, MAX_NUMBER)
    _number(limits["risk_difference"], "risk difference threshold", 0, 1)
    _number(value["minimum_per_arm"], "minimum_per_arm", 2, MAX_UNITS, integer=True)
    _time(value["outcome_available_at"])
    return value


def _units(value, protocol):
    _record(value, "randomization-audit-units-v1", "rows")
    rows = _list(value["rows"], "unit rows", MAX_UNITS)
    seen = set()
    groups = {}
    for row in rows:
        _fields(row, "unit_id covariates strata available", "unit row")
        identity = _text(row["unit_id"], "unit_id")
        _require(identity not in seen, "duplicate-unit", "unit IDs must be unique")
        seen.add(identity)
        _require(_boolean(row["available"], "available"), "unit-unavailable",
                 "unavailable units cannot be reported as balanced")
        covariates = _fields(row["covariates"], protocol["covariates"], "unit covariates")
        for name, kind in protocol["covariates"].items():
            _require(covariates[name] is not None, "unit-unavailable", "missing covariate is unavailable")
            _number(covariates[name], name, -MAX_NUMBER, MAX_NUMBER)
            if kind == "binary":
                _number(covariates[name], name, 0, 1, integer=True)
        _fields(row["strata"], protocol["strata"], "unit strata")
        key = tuple(_text(row["strata"][name], "stratum value") for name in protocol["strata"])
        if key not in groups:
            _require(len(groups) < MAX_GROUPS, "input-limit", "too many strata combinations")
            groups[key] = []
        groups[key].append(row)
    return rows, groups


def _shuffle(roster, rng):
    # Only Random.random() is used: this avoids version-dependent randrange/shuffle details.
    for index in range(len(roster) - 1, 0, -1):
        selected = int(rng.random() * (index + 1))
        roster[index], roster[selected] = roster[selected], roster[index]
    return roster


def _margins(size, ratio):
    total = sum(ratio)
    counts = [size * weight // total for weight in ratio]
    order = sorted(range(len(ratio)), key=lambda i: (-(size * ratio[i] % total), i))
    for index in order[:size - sum(counts)]:
        counts[index] += 1
    return counts


def _generate(protocol, groups):
    rng = random.Random()
    rng.seed(protocol["seed"], version=2)
    allocation = {}
    for key in sorted(groups):
        rows = sorted(groups[key], key=lambda row: row["unit_id"])
        size = len(rows) if protocol["method"] == "simple" else protocol["block_size"]
        counts = _margins(size, protocol["allocation_ratio"])
        template = [arm for arm, count in zip(protocol["arms"], counts) for _ in range(count)]
        for start in range(0, len(rows), size):
            roster = _shuffle(template.copy(), rng)
            for row, arm in zip(rows[start:start + size], roster):
                allocation[row["unit_id"]] = arm
    return allocation


def _scope(key):
    return "stratum:" + json.dumps(key, ensure_ascii=True, separators=(",", ":"))


def _metrics(protocol, rows, groups, allocation):
    arms = protocol["arms"]
    # Bound the full metric cross product before allocating or scanning it.
    scope_count = 1 + (len(groups) if protocol["strata"] else 0)
    _require(scope_count * len(arms) * (len(arms) - 1) // 2 * len(protocol["covariates"]) <= MAX_METRICS,
             "input-limit", "balance metric budget exceeded")
    scopes = [("overall", rows)]
    if protocol["strata"]:
        scopes.extend((_scope(key), groups[key]) for key in sorted(groups))
    balance, stratum_counts = [], {}
    for scope, members in scopes:
        by_arm = {arm: [] for arm in arms}
        for row in members:
            by_arm[allocation[row["unit_id"]]].append(row)
        counts = {arm: len(by_arm[arm]) for arm in arms}
        _require(all(count >= protocol["minimum_per_arm"] for count in counts.values()),
                 "insufficient-units", "each arm in each evaluated stratum needs the frozen minimum")
        if scope != "overall":
            stratum_counts[scope] = counts
        cached = {}
        for name, kind in protocol["covariates"].items():
            for arm in arms:
                values = [row["covariates"][name] for row in by_arm[arm]]
                mean = math.fsum(values) / len(values)
                variance = statistics.variance(values) if kind == "continuous" else mean * (1 - mean)
                cached[name, arm] = mean, variance
            for left, right in combinations(arms, 2):
                lm, lv = cached[name, left]
                rm, rv = cached[name, right]
                pooled = math.fsum((lv / 2, rv / 2))
                _require(pooled > 0 and math.isfinite(pooled), "degenerate-covariate",
                         "zero or nonfinite pooled variance cannot support balance")
                metric = "smd" if kind == "continuous" else "risk_difference"
                value = (lm - rm) / math.sqrt(pooled) if kind == "continuous" else lm - rm
                _require(math.isfinite(value), "degenerate-covariate", "nonfinite balance metric")
                balance.append({"scope": scope, "covariate": name, "arms": [left, right],
                                "metric": metric, "value": value,
                                "flag": abs(value) > protocol["thresholds"][metric]})
    counts = {arm: 0 for arm in arms}
    for arm in allocation.values():
        counts[arm] += 1
    return {"counts": counts, "stratum_counts": stratum_counts, "balance": balance,
            "balanced": not any(item["flag"] for item in balance)}


def reference_computation(protocol, unit_table):
    """Regenerate frozen allocation and balance; synthetic complete tables only."""
    protocol = _protocol(protocol)
    rows, groups = _units(unit_table, protocol)
    allocation = _generate(protocol, groups)
    return {"generated_allocation": allocation, **_metrics(protocol, rows, groups, allocation)}


def _allocation(value, protocol, rows, groups):
    _record(value, "randomization-audit-allocation-v1", "rows attempts after_balance_seen")
    entries = _list(value["rows"], "allocation rows", MAX_UNITS)
    _number(value["attempts"], "attempts", 1, MAX_UNITS, integer=True)
    _boolean(value["after_balance_seen"], "after_balance_seen")
    allocation = {}
    outcome_time = _time(protocol["outcome_available_at"])
    for entry in entries:
        _fields(entry, "unit_id arm recorded_at", "allocation row")
        identity = _text(entry["unit_id"], "unit_id")
        arm = _text(entry["arm"], "arm")
        _require(identity not in allocation, "duplicate-unit", "duplicate allocated unit")
        _require(arm in protocol["arms"], "unknown-arm", "allocated arm is not frozen")
        _require(_time(entry["recorded_at"]) < outcome_time,
                 "allocation-after-outcomes", "allocation must be recorded before outcomes are available")
        allocation[identity] = arm
    _require(set(allocation) == {row["unit_id"] for row in rows},
             "unit-unavailable", "allocation and frozen table IDs differ")
    ratio, arms = protocol["allocation_ratio"], protocol["arms"]
    for key in sorted(groups):
        members = sorted(groups[key], key=lambda row: row["unit_id"])
        size = len(members) if protocol["method"] == "simple" else protocol["block_size"]
        expected = _margins(size, ratio)
        for start in range(0, len(members), size):
            chunk = members[start:start + size]
            counts = {arm: 0 for arm in arms}
            for row in chunk:
                counts[allocation[row["unit_id"]]] += 1
            if len(chunk) == size:
                code = "allocation-ratio" if protocol["method"] == "simple" else "block-size"
                _require(list(counts.values()) == expected, code, "recorded allocation violates frozen margins")
            else:
                _require(all(counts[arm] <= count for arm, count in zip(arms, expected)),
                         "block-size", "partial block exceeds its full block capacity")
    return allocation


def _same(value, expected, code):
    if type(expected) is bool:
        _require(type(value) is bool and value == expected, code, "boolean differs from recomputation")
    elif type(expected) in (int, float):
        _number(value, "reported value", -MAX_NUMBER, MAX_NUMBER, integer=type(expected) is int)
        _require(math.isclose(value, expected, rel_tol=1e-12, abs_tol=0),
                 code, "reported number differs from recomputation")
    elif type(expected) is dict:
        _fields(value, expected, "reported map")
        for key in expected:
            _same(value[key], expected[key], code)
    elif type(expected) is list:
        _list(value, "reported list", MAX_METRICS, True)
        _require(len(value) == len(expected), code, "reported list length differs")
        for item, target in zip(value, expected):
            _same(item, target, code)
    else:
        _require(type(value) is type(expected) and value == expected, code, "reported label differs")


def _claims(claims, evidence):
    claims = _list(claims, "claims", MAX_RECORDS, True)
    seen = set()
    for claim in claims:
        _fields(claim, "id kind status text support", "claim")
        identity = _text(claim["id"], "claim id")
        _require(identity not in seen, "invalid-record", "duplicate claim id")
        seen.add(identity)
        kind = _text(claim["kind"], "claim kind")
        status = _text(claim["status"], "claim status")
        text = _text(claim["text"], "claim text")
        support = _names(claim["support"], "claim support", MAX_RECORDS, True)
        _require(status in STATUSES, "invalid-record", "unknown claim status")
        _require(kind in {"descriptive", "associational"} and not OVERREACH.search(text),
                 "claim-overreach", "allocation arithmetic cannot establish study merit or effects")
        _require(all(name in evidence for name in support), "unavailable-evidence", "unknown evidence record")
        records = [evidence[name] for name in support]
        _require((bool(support) and all(record["kind"].casefold() != "unavailable" and record["result"].casefold() != "unavailable"
                                       for record in records)) or status == "unavailable",
                 "unavailable-evidence", "any unavailable citation or empty support requires unavailable")
        _require(status != "unavailable" or not ASSERTION.search(text),
                 "unavailable-positive", "unavailable claim cannot assert positive evidence")
        if status in POSITIVE:
            _require(all(not NON_EVIDENCE.search(record["kind"]) and not NON_EVIDENCE.search(record["result"])
                         for record in records), "non-evidence", "computed records and review approval are not positive support")
        _require(status != "replicated", "claim-replication", "a synthetic allocation bundle cannot establish replication")


def validate_randomization_audit_pack(bundle):
    """Validate one hash-bound bundle; return JSON-compatible arithmetic, writing nothing."""
    try:
        value = _text(os.fspath(bundle), "bundle path")
        _require(all(ord(c) >= 32 for c in value), "input-path", "control character in bundle path")
        path = Path(os.path.abspath(value))
    except (TypeError, ValueError) as error:
        raise ValueError("input-path: invalid bundle path") from error
    store = _Bundle(path.parent)
    try:
        pack = _record(store.load(path.name), "randomization-audit-pack-v1", "stages protocol "
                       "frozen_protocol_sha256 frozen_at allocation_read_at allocation report evidence")
        _require(pack["stages"] == list(STAGES), "stage-order", "five ordered stages required")
        protocol = _protocol(store.artifact(pack["protocol"]))
        _require(type(pack["frozen_protocol_sha256"]) is str and
                 pack["frozen_protocol_sha256"] == pack["protocol"]["sha256"] and
                 _time(pack["frozen_at"]) < _time(pack["allocation_read_at"]) and
                 _time(pack["frozen_at"]) < _time(protocol["outcome_available_at"]),
                 "rule-freeze", "rules and unit identity must be hashed before allocation is read")
        table = store.artifact(protocol["units"])
        rows, groups = _units(table, protocol)
        allocation_record = store.artifact(pack["allocation"])
        allocation = _allocation(allocation_record, protocol, rows, groups)
        report = _record(store.artifact(pack["report"]), "randomization-audit-report-v1",
                         "protocol_sha256 applied_strata block_size reproduced exploratory counts "
                         "stratum_counts balance balanced headline claims")
        _require(_text(report["protocol_sha256"], "protocol_sha256") == pack["protocol"]["sha256"],
                 "rule-freeze", "report cites different frozen rules")
        _require(_names(report["applied_strata"], "applied_strata", MAX_STRATA, True) == protocol["strata"],
                 "strata-ignored", "reported stratification must match the frozen method")
        if report["block_size"] is not None:
            _number(report["block_size"], "reported block_size", 1, MAX_UNITS, integer=True)
        _require(report["block_size"] == protocol["block_size"], "block-size", "reported block size changed")
        exploratory = _boolean(report["exploratory"], "exploratory")
        _require(not (allocation_record["attempts"] > 1 or allocation_record["after_balance_seen"]) or exploratory,
                 "rerandomization-unlabelled", "multiple draws or inspection require an exploratory label")
        generated = _generate(protocol, groups)
        reproduced = allocation == generated
        claimed = _boolean(report["reproduced"], "reproduced")
        _require(not claimed or reproduced, "allocation-not-reproduced", "frozen seed does not reproduce recorded allocation")
        _require(claimed == reproduced, "reproduction-report", "reproduction flag differs from exact comparison")
        metrics = _metrics(protocol, rows, groups, allocation)
        for key in ("counts", "stratum_counts"):
            _same(report[key], metrics[key], "allocation-ratio")
        _same(report["balance"], metrics["balance"], "covariate-imbalance")
        _same(report["balanced"], metrics["balanced"], "covariate-imbalance")
        _require(not OVERREACH.search(_text(report["headline"], "headline")),
                 "claim-overreach", "headline exceeds arithmetic evidence")
        descriptors = _list(pack["evidence"], "evidence", MAX_RECORDS, True)
        own_paths = {path.name}
        own_hashes = {store.snapshots[path.name][2]}
        for descriptor in (pack["protocol"], protocol["units"], pack["allocation"], pack["report"], *descriptors):
            _fields(descriptor, "path sha256", "artifact identity")
            own_paths.add(str(_relative(descriptor["path"])))
            own_hashes.add(_text(descriptor["sha256"], "sha256"))
        evidence = {}
        for descriptor in descriptors:
            document = _record(store.artifact(descriptor), "randomization-audit-evidence-v1", "records")
            records = _list(document["records"], "evidence records", MAX_RECORDS, True)
            _require(len(evidence) + len(records) <= MAX_RECORDS, "input-limit", "too many evidence records")
            for record in records:
                _fields(record, "id kind result origin source", "evidence record")
                identity = _text(record["id"], "evidence id")
                _require(identity not in evidence, "invalid-record", "duplicate evidence id")
                for name in ("kind", "result", "origin"):
                    _text(record[name], name)
                _require(record["origin"] in {"internal", "external", "independent", "preregistered"},
                         "invalid-record", "unknown evidence origin")
                digest = store.artifact(record["source"], parse=False)
                if record["origin"] != "internal":
                    _require(record["source"]["path"] not in own_paths and digest not in own_hashes,
                             "evidence-independence", "declared independence aliases a study input or output")
                evidence[identity] = record
        _claims(report["claims"], evidence)
        store.finish()
        return {"schema": "randomization-audit-result-v1", "schema_version": 1,
                "fixture": "synthetic fixture", "status": "arithmetic-only", "review": "unavailable",
                "stages": list(STAGES), "protocol_sha256": pack["protocol"]["sha256"],
                "inputs": [{"path": name, "sha256": item[2]} for name, item in sorted(store.snapshots.items())],
                "reproduced": reproduced, "finding": "reproduced" if reproduced else "allocation-not-reproduced",
                "exploratory": exploratory, "computation": metrics, "claims": report["claims"],
                "limitations": ["Synthetic allocation arithmetic only; independent review remains unavailable.",
                                "Hash-bound declarations cannot establish historical timing or source independence.",
                                "Lexical wording checks are conservative English checks and incomplete.",
                                "Imbalance flags are retained; no rerandomization or outcome inference is performed."]}
    except (OSError, OverflowError, RecursionError) as error:
        raise ValueError("input-file: bounded readable inputs and finite arithmetic required") from error
    finally:
        store.close()
