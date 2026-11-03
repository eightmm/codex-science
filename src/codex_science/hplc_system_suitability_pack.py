"""Read-only synthetic HPLC peak-table admission and suitability reference arithmetic."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import statistics

STAGES = ("01-rule-freeze", "02-table-qc", "03-suitability", "04-summary", "05-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_ROWS = 10000
MAX_PEAKS = 128
MAX_RECORDS = 128
MAX_NODES = 4000000
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
    r"physical[\s-]+validity|method[\s-]+(?:is[\s-]+)?valid\w*|product[\s-]+quality|"
    r"system[\s-]+qualif\w*|release|patient[\s-]+benefit\w*)\b", re.I,
)
ASSERTION = re.compile(r"\b(?:supported|replicated|suggestive|significan\w*)\b", re.I)
NON_EVIDENCE = re.compile(r"review|approv|comput|numer|arithmet|hplc-result|agreement|truth|physical|clinic", re.I)
LIMIT_KEYS = ("retention_time_rsd_max", "peak_area_rsd_max", "tailing_max", "plates_min",
              "resolution_min", "signal_to_noise_min", "carryover_max")


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


def _same(actual, expected, label):
    if type(expected) in (int, float):
        _number(actual, label, -MAX_NUMBER, integer=label == "replicate_count")
        _require(math.isclose(actual, expected, rel_tol=1e-9, abs_tol=0),
                 "reported-number", f"reported {label} disagrees with reference")
    elif type(expected) is dict:
        _fields(actual, expected, label)
        for key in expected:
            _same(actual[key], expected[key], key)
    elif type(expected) is list:
        _list(actual, label, MAX_ROWS, True)
        _require(len(actual) == len(expected), "reported-result", "reported criterion count differs")
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


def _limits(value):
    _fields(value, LIMIT_KEYS, "acceptance limits")
    for key in LIMIT_KEYS:
        _number(value[key], key, 0, 1e12)
    return value


def _rules(value):
    _record(value, "hplc-rules-v1", "analyte_peak_id reference_peak_id standard_ids blank_ids injection_count "
            "minimum_injections limits rsd_method plates_width plates_constant tailing_height "
            "resolution_width blank_rule time_unit area_unit")
    analyte = _text(value["analyte_peak_id"], "analyte peak")
    if value["reference_peak_id"] is not None:
        _require(_text(value["reference_peak_id"], "reference peak") != analyte,
                 "peak-identity", "reference and analyte must differ")
    standards = _names(value["standard_ids"], "standard IDs", MAX_ROWS)
    blanks = _names(value["blank_ids"], "blank IDs", MAX_ROWS)
    _require(not set(standards).intersection(blanks), "blank-replicate", "blank IDs cannot be standards")
    _number(value["injection_count"], "planned injections", 2, MAX_ROWS, True)
    _number(value["minimum_injections"], "minimum injections", 2, value["injection_count"], True)
    _require(len(standards) == value["injection_count"], "injection-count", "planned standard count differs")
    _limits(value["limits"])
    _require(value["rsd_method"] == "sample-stdev", "rsd-method", "RSD requires sample standard deviation")
    _require(value["plates_width"] == "half-height" and type(value["plates_constant"]) in (int, float)
             and value["plates_constant"] == 5.54, "plates-method", "half-height plates require constant 5.54")
    _require(type(value["tailing_height"]) in (int, float) and value["tailing_height"] == 0.05,
             "tailing-height", "USP tailing requires widths and front distance at five percent height")
    _require(value["resolution_width"] == "baseline", "resolution-width", "resolution uses frozen baseline widths")
    _require(value["blank_rule"] == "preceding-standard", "blank-rule", "blank must follow its standard immediately")
    _require(value["time_unit"] == "minute" and value["area_unit"] == "arbitrary",
             "invalid-record", "synthetic table units must be minute and arbitrary area")
    return value


def sample_rsd(values, minimum):
    """Percent RSD with sample stdev; insufficient replicates remain unavailable."""
    _number(minimum, "minimum injections", 2, MAX_ROWS, True)
    values = _list(values, "RSD values", MAX_ROWS, True)
    for value in values:
        _number(value, "replicate measurement", 1e-12, 1e12)
    if len(values) < minimum:
        return "unavailable"
    mean = math.fsum(values) / len(values)
    deviation = statistics.stdev(values)
    _require(deviation > 0, "degenerate-rsd", "zero replicate variance cannot establish precision")
    return 100 * deviation / mean


def _criterion(value, limit, maximum=False):
    if value == "unavailable":
        return {"value": value, "status": "unavailable"}
    passed = value <= limit if maximum else value >= limit
    return {"value": value, "status": "pass" if passed else "fail"}


def compute_suitability(table, rules, applied_limits=None):
    """Compute frozen synthetic peak quantities, preserving failures and missingness."""
    rules = _rules(rules)
    limits = _limits(rules["limits"] if applied_limits is None else applied_limits)
    _record(table, "hplc-table-v1", "rows")
    rows = _list(table["rows"], "injection rows", MAX_ROWS)
    standard_ids, blank_ids = set(rules["standard_ids"]), set(rules["blank_ids"])
    seen, blanks, standards, measurements = set(), set(), [], []
    carryover, injections = [], []
    previous_order = 0
    previous = None
    for row in rows:
        _fields(row, "injection_id order kind peaks", "injection row")
        identity = _text(row["injection_id"], "injection ID")
        kind = _text(row["kind"], "injection kind")
        _require(identity not in seen, "duplicate-injection", "injection IDs must be unique")
        seen.add(identity)
        _number(row["order"], "injection order", 1, MAX_ROWS, True)
        _require(row["order"] > previous_order, "injection-order", "injection order must increase strictly")
        previous_order = row["order"]
        _require(kind in {"standard", "blank"}, "invalid-record", "unknown injection kind")
        _require((kind == "standard" and identity in standard_ids) or (kind == "blank" and identity in blank_ids),
                 "blank-replicate", "injection kind differs from frozen standard/blank identity")
        peaks = _list(row["peaks"], "injection peaks", MAX_PEAKS, True)
        indexed = {}
        for peak in peaks:
            _fields(peak, "peak_id retention_time area width_half_height width_five_percent front_five_percent "
                    "width_baseline signal_to_noise", "peak")
            peak_id = _text(peak["peak_id"], "peak ID")
            _require(peak_id not in indexed, "peak-identity", "duplicate peak ID within injection")
            for key in ("retention_time", "width_half_height", "width_five_percent", "front_five_percent", "width_baseline"):
                _number(peak[key], key, 1e-12, 1e12)
            _number(peak["area"], "peak area", 1e-12 if kind == "standard" else 0, 1e12)
            if peak["signal_to_noise"] is not None:
                _number(peak["signal_to_noise"], "signal to noise", 0, 1e12)
            _require(peak["front_five_percent"] < peak["width_five_percent"],
                     "peak-width", "front distance must lie inside five-percent width")
            _require(peak["width_half_height"] <= peak["width_five_percent"],
                     "peak-width", "half-height width exceeds five-percent width")
            indexed[peak_id] = peak
        analyte = indexed.get(rules["analyte_peak_id"])
        if kind == "blank":
            blanks.add(identity)
            _require(previous is not None and previous["kind"] == "standard",
                     "blank-rule", "blank needs the immediately preceding recorded standard")
            area = analyte["area"] if analyte is not None else "unavailable"
            value = 100 * area / previous["area"] if area != "unavailable" else "unavailable"
            carryover.append({"injection_id": identity, "preceding_standard_id": previous["id"],
                              **_criterion(value, limits["carryover_max"], True)})
        else:
            _require(analyte is not None, "peak-identity", "standard requires the frozen analyte peak")
            reference = rules["reference_peak_id"]
            _require(reference is None or reference in indexed, "peak-identity", "frozen reference peak missing")
            neighbors = [peak for key, peak in indexed.items() if key != rules["analyte_peak_id"]]
            nearest = None
            for peak in neighbors:
                distance = abs(peak["retention_time"] - analyte["retention_time"])
                if nearest is None or (distance < best and not math.isclose(distance, best, rel_tol=1e-9)):
                    nearest, best = peak, distance
            resolution = (2 * abs(nearest["retention_time"] - analyte["retention_time"]) /
                          (nearest["width_baseline"] + analyte["width_baseline"])) if nearest else "unavailable"
            sn = analyte["signal_to_noise"] if analyte["signal_to_noise"] is not None else "unavailable"
            standards.append(identity)
            measurements.append((analyte["retention_time"], analyte["area"]))
            record = {"injection_id": identity, "nearest_peak_id": nearest["peak_id"] if nearest else "unavailable",
                      "plates": _criterion(5.54 * (analyte["retention_time"] / analyte["width_half_height"]) ** 2,
                                           limits["plates_min"]),
                      "tailing": _criterion(analyte["width_five_percent"] / (2 * analyte["front_five_percent"]),
                                            limits["tailing_max"], True),
                      "resolution": _criterion(resolution, limits["resolution_min"]),
                      "signal_to_noise": _criterion(sn, limits["signal_to_noise_min"])}
            previous = {"id": identity, "kind": kind, "area": analyte["area"]}
            injections.append(record)
            continue
        previous = {"id": identity, "kind": kind}
    _require(blanks == blank_ids, "blank-rule", "all frozen blank injections must be recorded")
    replicate_criteria = {
        "retention_time_rsd": _criterion(sample_rsd([row[0] for row in measurements], rules["minimum_injections"]),
                                          limits["retention_time_rsd_max"], True),
        "peak_area_rsd": _criterion(sample_rsd([row[1] for row in measurements], rules["minimum_injections"]),
                                     limits["peak_area_rsd_max"], True)}
    summary = {}
    for criterion in ("retention_time_rsd", "peak_area_rsd", "plates", "tailing", "resolution", "signal_to_noise", "carryover"):
        if criterion in replicate_criteria:
            statuses = [replicate_criteria[criterion]["status"]]
        elif criterion == "carryover":
            statuses = [row["status"] for row in carryover]
        else:
            statuses = [row[criterion]["status"] for row in injections]
        summary[criterion] = "fail" if "fail" in statuses else ("unavailable" if not statuses or "unavailable" in statuses else "pass")
    return {"replicate_count": len(standards), "replicate_ids": standards, "injections": injections,
            "replicate_criteria": replicate_criteria, "carryover": carryover, "summary": summary}


def validate_hplc_system_suitability_pack(bundle):
    """Validate one hash-bound offline bundle without creating or changing files."""
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
        pack = _record(store.load(path.name), "hplc-pack-v1",
                       "rules frozen_rules_sha256 frozen_before_table_read table report evidence")
        rules = _rules(store.artifact(pack["rules"]))
        _require(_text(pack["frozen_rules_sha256"], "frozen rules hash") == pack["rules"]["sha256"]
                 and _boolean(pack["frozen_before_table_read"], "frozen before table read"),
                 "rule-freeze", "rules must be hash-frozen before peak tables are opened")
        report = _record(store.artifact(pack["report"]), "hplc-report-v1", "rules_sha256 exploratory applied_limits "
                         "rsd_method plates_width plates_constant tailing_height resolution_width headline claims "
                         "replicate_count replicate_ids injections replicate_criteria carryover summary")
        _require(_text(report["rules_sha256"], "rules hash") == pack["rules"]["sha256"],
                 "rule-freeze", "report cites a different frozen rule revision")
        exploratory = _boolean(report["exploratory"], "exploratory")
        limits = _limits(report["applied_limits"])
        _require(limits == rules["limits"] or exploratory, "post-hoc-limits", "changed limits require exploratory label")
        _require(report["rsd_method"] == rules["rsd_method"], "rsd-method", "population RSD is refused")
        _require(report["plates_width"] == rules["plates_width"] and type(report["plates_constant"]) in (int, float)
                 and report["plates_constant"] == rules["plates_constant"], "plates-method", "plate constant/width changed")
        _require(type(report["tailing_height"]) in (int, float) and report["tailing_height"] == rules["tailing_height"],
                 "tailing-height", "tailing height differs from frozen five-percent rule")
        _require(report["resolution_width"] == rules["resolution_width"], "resolution-width", "resolution width changed")
        _require(not OVERREACH.search(_text(report["headline"], "headline")),
                 "claim-overreach", "headline exceeds bounded synthetic arithmetic")
        descriptors = _list(pack["evidence"], "evidence artifacts", MAX_RECORDS, True)
        own_paths = {path.name}
        own_hashes = {store.snapshots[path.name][2]}
        for descriptor in (pack["rules"], pack["table"], pack["report"], *descriptors):
            _fields(descriptor, "path sha256", "artifact identity")
            own_paths.add(str(_relative(descriptor["path"])))
            own_hashes.add(_text(descriptor["sha256"], "sha256"))
        evidence = {}
        for descriptor in descriptors:
            document = _record(store.artifact(descriptor), "hplc-evidence-v1", "records")
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
        result = compute_suitability(store.artifact(pack["table"]), rules, limits)
        replicate_ids = _names(report["replicate_ids"], "reported replicate IDs", MAX_ROWS, True)
        _require(not set(replicate_ids).intersection(rules["blank_ids"]), "blank-replicate", "blank included in RSD replicates")
        _fields(report["replicate_criteria"], result["replicate_criteria"], "replicate criteria")
        for key, expected in result["replicate_criteria"].items():
            actual = _fields(report["replicate_criteria"][key], "value status", "RSD criterion")
            if expected["status"] == "unavailable":
                _require(actual == expected, "replicate-minimum", "too few injections require unavailable RSDs, never zero or pass")
        _require(type(report["summary"]) is dict and set(report["summary"]) == set(result["summary"]),
                 "summary-omission", "summary must retain every criterion, including failures")
        _require(report["summary"] == result["summary"], "summary-result", "summary hides a failed or unavailable criterion")
        for key in result:
            _same(report[key], result[key], key)
        store.finish()
        return {"schema": "hplc-result-v1", "fixture": "synthetic fixture", "status": "arithmetic-only",
                "review": "unavailable", "stages": list(STAGES), "exploratory": exploratory,
                "inputs": [{"path": name, "sha256": item[2]} for name, item in sorted(store.snapshots.items())],
                "computation": result, "claims": report["claims"],
                "limitations": ["Synthetic peak tables establish software arithmetic only.",
                                "Recorded peak identity, widths and signal-to-noise are not independently verified.",
                                "Zero replicate variance is refused; insufficient replicates remain unavailable.",
                                "Hashes cannot establish historical freeze timing or true independence.",
                                "Independent record, source and method review remains unavailable."]}
    finally:
        store.close()
