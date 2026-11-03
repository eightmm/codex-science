"""Read-only two-group time-to-event fixture validation and stdlib reference math."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
from statistics import NormalDist


STAGES = ("01-protocol", "02-cohort", "03-integrity", "04-computation", "05-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_ROWS = 10000
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
    r"physical[\s-]+validity|patient[\s-]+benefit\w*)\b", re.I,
)
ASSERTION = re.compile(r"\b(?:supported|replicated|suggestive|significan\w*)\b", re.I)
NON_EVIDENCE = re.compile(r"review|approv|comput|numer|agreement|truth|physical|clinic", re.I)
HAZARD = re.compile(r"\b(?:hazard[\s-]+ratio|HR)\b", re.I)


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


def _json(raw):
    try:
        root = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=_constant, parse_int=_int, parse_float=_float)
        _require(type(root) is dict, "invalid-json", "JSON root must be an object")
        pending = [(root, 0)]
        while pending:
            value, depth = pending.pop()
            _require(depth <= MAX_DEPTH, "invalid-json", "JSON nesting limit exceeded")
            if type(value) is dict:
                _require(len(value) <= MAX_ROWS, "input-limit", "JSON object too large")
                children = list(value.keys()) + list(value.values())
            elif type(value) is list:
                _require(len(value) <= MAX_ROWS, "input-limit", "JSON list too large")
                children = value
            else:
                if type(value) is str:
                    _text(value, "JSON string")
                continue
            pending.extend((child, depth + 1) for child in children)
        return root
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
        return _json(raw) if parse else actual

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


def _groups(value):
    value = _names(value, "groups", 2)
    _require(len(value) == 2, "invalid-record", "exactly two groups required")
    return value


def _protocol(value):
    _record(value, "survival-protocol-v1", "time_origin event_definition censoring_rule groups "
            "group_assignment tie_handling test alpha minimum_events minimum_subjects_per_group "
            "maximum_censoring_imbalance time_unit")
    for name in ("time_origin", "event_definition", "censoring_rule", "group_assignment", "time_unit"):
        _text(value[name], name)
    _groups(value["groups"])
    _require(value["tie_handling"] == "events-before-censoring", "tie-handling", "unsupported ties rule")
    _require(value["test"] == "log-rank", "unsupported-test", "reference requires log-rank")
    _number(value["alpha"], "alpha", 1e-12, 0.5)
    _number(value["minimum_events"], "minimum_events", 2, MAX_ROWS, True)
    _number(value["minimum_subjects_per_group"], "minimum_subjects_per_group", 2, MAX_ROWS, True)
    _number(value["maximum_censoring_imbalance"], "maximum_censoring_imbalance", 0, 1)
    return value


def _cohort(value, protocol, groups):
    _record(value, "survival-cohort-v1", "rows")
    rows = _list(value["rows"], "cohort rows", MAX_ROWS)
    seen = set()
    counts = Counter()
    censored = Counter()
    events = 0
    for row in rows:
        _fields(row, "subject_id time event censored group group_assignment_time time_unit", "subject")
        identity = _text(row["subject_id"], "subject_id")
        _require(identity not in seen, "duplicate-subject", "subject identities must be unique")
        seen.add(identity)
        _number(row["time"], "time", 0, 1e12)
        _require(row["time"] > 0, "invalid-time", "follow-up time must be positive")
        _number(row["event"], "event", 0, 1, True)
        _boolean(row["censored"], "censored")
        _require(row["censored"] == (row["event"] == 0), "event-censoring", "inconsistent flags")
        group = _text(row["group"], "group")
        _require(group in groups, "group-identity", "subject group outside declared contrast")
        _number(row["group_assignment_time"], "group_assignment_time", -1e12, 1e12)
        _require(row["group_assignment_time"] <= 0, "immortal-time", "group assigned after time zero")
        _text(row["time_unit"], "time_unit")
        _require(row["time_unit"] == protocol["time_unit"], "mixed-time-units", "time units differ")
        counts[group] += 1
        censored[group] += row["censored"]
        events += row["event"]
    _require(all(counts[g] >= protocol["minimum_subjects_per_group"] for g in groups),
             "insufficient-subjects", "group below frozen subject minimum")
    _require(events >= protocol["minimum_events"], "insufficient-events", "below frozen event minimum")
    fractions = {g: censored[g] / counts[g] for g in groups}
    _require(abs(fractions[groups[0]] - fractions[groups[1]]) <= protocol["maximum_censoring_imbalance"],
             "censoring-imbalance", "censoring imbalance exceeds frozen threshold")
    return rows, fractions


def _km(rows, alpha):
    times = {}
    for row in rows:
        count = times.setdefault(row["time"], [0, 0])
        count[0] += row["event"]
        count[1] += row["censored"]
    risk = len(rows)
    survival = 1.0
    greenwood = 0.0
    median = "unavailable"
    curve = []
    z = NormalDist().inv_cdf(1 - alpha / 2)
    for time, (events, censored) in sorted(times.items()):
        if events:
            survival *= (risk - events) / risk
            if risk > events:
                greenwood = math.fsum((greenwood, events / (risk * (risk - events))))
        variance = survival * survival * greenwood
        if 0 < survival < 1:
            log_s = math.log(survival)
            se = math.sqrt(greenwood) / abs(log_s)
            center = math.log(-log_s)
            lower = math.exp(-math.exp(min(700, center + z * se)))
            upper = math.exp(-math.exp(min(700, center - z * se)))
            interval = [lower, upper]
        else:
            interval = [survival, survival]
        if median == "unavailable" and survival <= 0.5:
            median = time
        curve.append({"time": time, "at_risk": risk, "events": events, "censored": censored,
                      "survival": survival, "greenwood_variance": variance,
                      "log_log_interval": interval})
        risk -= events + censored
    return {"curve": curve, "median": median, "subjects": len(rows)}


def compute_survival(cohort, protocol, groups=None):
    """Validate and compute KM/Greenwood/log-log and the two-sided log-rank test.

    Tied events use the pooled risk set before removing tied censorings. The
    O/E ratio is exploratory and is unavailable if either observed count is zero.
    """
    protocol = _protocol(protocol)
    groups = _groups(protocol["groups"] if groups is None else groups)
    rows, fractions = _cohort(cohort, protocol, groups)
    by_group = {g: [] for g in groups}
    times = {}
    for row in rows:
        by_group[row["group"]].append(row)
        counts = times.setdefault(row["time"], {g: [0, 0] for g in groups})[row["group"]]
        counts[0] += row["event"]
        counts[1] += row["censored"]
    risk = {g: len(by_group[g]) for g in groups}
    observed = {g: 0 for g in groups}
    expected = {g: [] for g in groups}
    variances = []
    for _, counts in sorted(times.items()):
        n = sum(risk.values())
        d = sum(counts[g][0] for g in groups)
        for g in groups:
            observed[g] += counts[g][0]
            expected[g].append(d * risk[g] / n)
        if n > 1:
            variances.append(risk[groups[0]] * risk[groups[1]] * d * (n - d) / (n * n * (n - 1)))
        for g in groups:
            risk[g] -= sum(counts[g])
    expected = {g: math.fsum(expected[g]) for g in groups}
    variance = math.fsum(variances)
    _require(variance > 0 and math.isfinite(variance), "degenerate-log-rank", "zero or non-finite variance")
    a, b = groups
    z = (observed[a] - expected[a]) / math.sqrt(variance)
    p = math.erfc(abs(z) / math.sqrt(2))
    ratio = "unavailable"
    if all(observed[g] > 0 and expected[g] > 0 for g in groups):
        ratio = (observed[a] / expected[a]) / (observed[b] / expected[b])
    return {"groups": {g: _km(by_group[g], protocol["alpha"]) for g in groups},
            "censoring_fractions": fractions,
            "log_rank": {"observed": observed, "expected": expected, "variance": variance,
                         "chi_square": z * z, "p_value": p},
            "significant": p < protocol["alpha"],
            "hazard_ratio": {"value": ratio, "label": "exploratory log-rank O/E hazard ratio",
                             "proportional_hazards_claim": False}}


def _same_number(actual, expected, label):
    _number(actual, label, -MAX_NUMBER)
    _require(math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-12),
             "reported-number", f"reported {label} disagrees with reference")


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
                 "claim-overreach", "only bounded statistical evidence is permitted")
        _require(status in STATUSES, "invalid-record", "unknown claim status")
        ids = _names(claim["evidence"], "claim evidence", MAX_RECORDS, True)
        _require(ids or status == "unavailable", "missing-evidence", "empty evidence requires unavailable")
        _require(status != "unavailable" or not ASSERTION.search(text),
                 "unavailable-positive", "unavailable claim asserts positive evidence")
        _require(not HAZARD.search(text) or re.search(r"\bexploratory\b", text, re.I),
                 "hazard-label", "hazard ratio must carry the exploratory label")
        for identity in ids:
            _require(identity in evidence, "missing-evidence", "unknown evidence identity")
            record = evidence[identity]
            _require("unavailable" not in (record["kind"], record["result"]) or status == "unavailable",
                     "unavailable-evidence", "unavailable records require an unavailable claim")
            _require(status not in POSITIVE or not any(NON_EVIDENCE.search(record[key])
                     for key in ("kind", "result")),
                     "non-evidence-support", "review approval and computed agreement are not positive evidence")
        if status == "replicated":
            sources = [evidence[identity] for identity in ids]
            _require(len({record["source"]["path"] for record in sources}) >= 2
                     and len({record["source"]["sha256"] for record in sources}) >= 2
                     and any(record["origin"] != "internal" for record in sources),
                     "claim-replication", "replication requires a distinct declared independent second source")


def validate_survival_pack(bundle):
    """Validate a pack JSON and all hash-bound inputs without writing any files."""
    try:
        value = _text(os.fspath(bundle), "bundle path")
        _require(all(ord(c) >= 32 for c in value), "input-path", "control character in bundle path")
        path = Path(os.path.abspath(value))
    except (TypeError, ValueError) as error:
        raise ValueError("input-path: invalid bundle path") from error
    store = _Bundle(path.parent)
    try:
        pack = _record(store.load(path.name), "survival-pack-v1",
                       "protocol frozen_protocol_sha256 frozen_before_table_read cohort report evidence")
        protocol = _protocol(store.artifact(pack["protocol"]))
        _text(pack["frozen_protocol_sha256"], "frozen_protocol_sha256")
        _require(pack["frozen_protocol_sha256"] == pack["protocol"]["sha256"]
                 and _boolean(pack["frozen_before_table_read"], "frozen_before_table_read"),
                 "protocol-freeze", "protocol must be hash-frozen before table admission")
        report = _record(store.artifact(pack["report"]), "survival-report-v1",
                         "protocol_sha256 groups test exploratory significant medians censoring_fractions "
                         "hazard_ratio headline claims")
        _require(_text(report["protocol_sha256"], "protocol_sha256") == pack["protocol"]["sha256"],
                 "protocol-freeze", "report refers to a different frozen protocol")
        groups = _groups(report["groups"])
        _text(report["test"], "test")
        exploratory = _boolean(report["exploratory"], "exploratory")
        _require((groups == protocol["groups"] and report["test"] == protocol["test"]) or exploratory,
                 "post-hoc-change", "changed groups or test require an exploratory label")
        _require(report["test"] == "log-rank", "unsupported-test", "alternative tests need a separate reference")
        result = compute_survival(store.artifact(pack["cohort"]), protocol, groups)
        _require(_boolean(report["significant"], "significant") == result["significant"],
                 "significance-mismatch", "significance differs from frozen alpha")
        _fields(report["medians"], groups, "medians")
        _fields(report["censoring_fractions"], groups, "censoring fractions")
        for group in groups:
            expected = result["groups"][group]["median"]
            if expected == "unavailable":
                _require(report["medians"][group] == "unavailable", "median-unavailable", "curve never reaches 0.5")
            else:
                _same_number(report["medians"][group], expected, "median")
            _same_number(report["censoring_fractions"][group], result["censoring_fractions"][group], "censoring")
        hr = _fields(report["hazard_ratio"], "value label proportional_hazards_claim", "hazard ratio")
        _require(hr["label"] == result["hazard_ratio"]["label"]
                 and _boolean(hr["proportional_hazards_claim"], "proportional_hazards_claim") is False,
                 "hazard-label", "exploratory O/E ratio never establishes proportional hazards")
        if result["hazard_ratio"]["value"] == "unavailable":
            _require(hr["value"] == "unavailable", "hazard-unavailable", "zero O/E component")
        else:
            _same_number(hr["value"], result["hazard_ratio"]["value"], "hazard ratio")
        headline = _text(report["headline"], "headline")
        _require(not OVERREACH.search(headline), "claim-overreach", "headline exceeds statistical evidence")
        _require(not HAZARD.search(headline) or re.search(r"\bexploratory\b", headline, re.I),
                 "hazard-label", "hazard ratio headline requires exploratory label")
        descriptors = _list(pack["evidence"], "evidence artifacts", MAX_RECORDS, True)
        own_paths = {path.name}
        own_hashes = {store.snapshots[path.name][2]}
        for descriptor in (pack["protocol"], pack["cohort"], pack["report"], *descriptors):
            _fields(descriptor, "path sha256", "artifact identity")
            own_paths.add(str(_relative(descriptor["path"])))
            own_hashes.add(_text(descriptor["sha256"], "sha256"))
        evidence = {}
        for descriptor in descriptors:
            document = _record(store.artifact(descriptor), "survival-evidence-v1", "records")
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
                             "external-alias", "independence label aliases study artifacts")
                evidence[identity] = record
        _claims(report["claims"], evidence)
        store.finish()
        return {"schema": "survival-result-v1", "fixture": "synthetic fixture", "status": "statistical-evidence-only",
                "review": "unavailable", "stages": list(STAGES), "exploratory": exploratory,
                "inputs": [{"path": name, "sha256": item[2]} for name, item in sorted(store.snapshots.items())],
                "computation": result, "claims": report["claims"],
                "limitations": ["Synthetic fixtures establish software behavior only.",
                                "Hashes cannot establish historical freeze timing or real independence.",
                                "Independent source, record and method review remains unavailable.",
                                "Censoring fraction balance cannot establish noninformative censoring.",
                                "O/E hazard ratio is exploratory; proportional hazards are untested."]}
    finally:
        store.close()
