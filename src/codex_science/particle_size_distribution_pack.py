"""Read-only synthetic particle-size admission and cumulative binned reference arithmetic."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat


STAGES = ("01-rule-freeze", "02-table-qc", "03-distribution", "04-summary", "05-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_ROWS = 10000
MAX_SAMPLES = 128
MAX_NODES = 4000000
MAX_BINS = 2048
MAX_COUNT = 1000000000000
MIN_EDGE = 1e-12
MAX_EDGE = 1e12
METRICS = ("D10_um", "D50_um", "D90_um", "span", "mean_by_number_um", "volume_weighted_mean_um")
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
    r"physical[\s-]+validity|patient[\s-]+benefit\w*|quality|stabil\w*|stabl\w*|perform\w*|approv\w*|certif\w*|compliance|compliant)\b", re.I,
)
ASSERTION = re.compile(r"\b(?:supported|replicated|suggestive|significan\w*)\b", re.I)
NON_EVIDENCE = re.compile(r"review|approv|comput|numer|agreement|truth|physical|clinic", re.I)


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


def _edges(value):
    edges = _list(value, "bin edges", MAX_BINS + 1)
    _require(len(edges) >= 2, "bin-edges", "at least two bin edges required")
    for edge in edges:
        _number(edge, "edge in micrometres", 0, MAX_EDGE)
        _require(edge == 0 or edge >= MIN_EDGE, "bin-edges", "nonzero edge below reference resolution")
    _require(all(a < b for a, b in zip(edges, edges[1:])),
             "bin-edges", "bin edges must be strictly increasing")
    return edges


def _rules(value):
    _record(value, "psd-rules-v1", "sample_ids measurements bin_edges_um basis interpolation_rule "
            "reported_statistics mean_rule minimum_total_count minimum_replicates "
            "d50_relative_range_max span_relative_range_max tail_fraction_max tail_rule")
    samples = _names(value["sample_ids"], "sample identities", MAX_SAMPLES)
    measurements = _list(value["measurements"], "measurement identities", MAX_ROWS)
    _edges(value["bin_edges_um"])
    basis = _text(value["basis"], "basis")
    _require(basis in {"count", "volume"}, "mixed-basis", "count or volume basis required")
    _require(value["interpolation_rule"] == "linear-cumulative-within-bin",
             "percentile-rule", "percentiles require linear interpolation on the cumulative curve")
    _require(_names(value["reported_statistics"], "reported quantities", len(METRICS)) == list(METRICS),
             "reported-statistics", "all six frozen quantities in canonical order required")
    _require(value["mean_rule"] == "bin-midpoints-spherical-volume",
             "mean-rule", "means require the frozen midpoint and spherical-volume convention")
    _number(value["minimum_total_count"], "minimum total count", 1, MAX_COUNT, True)
    _number(value["minimum_replicates"], "minimum replicates", 2, MAX_ROWS, True)
    for key in ("d50_relative_range_max", "span_relative_range_max"):
        _number(value[key], key, 0, 10)
    _number(value["tail_fraction_max"], "tail fraction limit", 0, .1)
    _require(value["tail_rule"] == "exclude-at-or-above-limit",
             "tail-rule", "tail mass may never be ignored")
    seen = set()
    for row in measurements:
        _fields(row, "measurement_id sample_id", "measurement identity")
        identity = _text(row["measurement_id"], "measurement id")
        sample = _text(row["sample_id"], "sample id")
        _require(identity not in seen, "duplicate-measurement", "measurement IDs must be unique")
        seen.add(identity)
        _require(sample in samples, "sample-identity", "measurement has an unfrozen sample")
    return value


def _quantities(edges, weights, lower, upper, basis):
    total = math.fsum(weights)
    _require(total > 0, "degenerate-distribution", "positive in-range mass required")
    weights = [weight / total for weight in weights]
    inside = 1 - math.fsum((lower, upper))
    percentiles = []
    for probability in (.1, .5, .9):
        cumulative = lower
        for left, right, weight in zip(edges, edges[1:], weights):
            mass = inside * weight
            following = math.fsum((cumulative, mass))
            if mass > 0 and probability <= following:
                fraction = (probability - cumulative) / mass
                percentiles.append(left + (right - left) * fraction)
                break
            cumulative = following
        else:
            raise ValueError("percentile-range: percentile outside measured bin edges")
    d10, d50, d90 = percentiles
    _require(d50 > 0 and d90 > d10, "degenerate-distribution", "positive median and spread required")
    centres = [left + (right - left) / 2 for left, right in zip(edges, edges[1:])]
    scale = max(centres)
    cubes = [(centre / scale) ** 3 for centre in centres]
    number_weights = weights if basis == "count" else [w / cube for w, cube in zip(weights, cubes)]
    volume_weights = weights if basis == "volume" else [w * cube for w, cube in zip(weights, cubes)]
    number_total, volume_total = math.fsum(number_weights), math.fsum(volume_weights)
    return dict(zip(METRICS, (d10, d50, d90, (d90 - d10) / d50,
                             math.fsum(w * d for w, d in zip(number_weights, centres)) / number_total,
                             math.fsum(w * d for w, d in zip(volume_weights, centres)) / volume_total)))


def compute_particle_size_distribution(table, rules, bin_edges_um=None):
    """Compute binned synthetic quantities; disagreeing replicates are never pooled."""
    rules = _rules(rules)
    _record(table, "psd-table-v1", "bin_edges_um rows")
    original = _edges(table["bin_edges_um"])
    _require(original == rules["bin_edges_um"], "bin-edges", "table edges differ from frozen edges")
    edges = original if bin_edges_um is None else _edges(bin_edges_um)
    original_indices = {edge: index for index, edge in enumerate(original)}
    _require(edges[0] == original[0] and edges[-1] == original[-1]
             and all(edge in original_indices for edge in edges),
             "bin-merge", "only adjacent frozen bins may be merged; outer edges stay fixed")
    indices = [original_indices[edge] for edge in edges]
    rows = _list(table["rows"], "measurement rows", MAX_ROWS)
    identities = {row["measurement_id"]: row["sample_id"] for row in rules["measurements"]}
    grouped = {sample: [] for sample in rules["sample_ids"]}
    seen = set()
    measurements = []
    for row in rows:
        _fields(row, "measurement_id sample_id basis values total_count below_range_fraction "
                "above_range_fraction availability", "measurement row")
        identity = _text(row["measurement_id"], "measurement id")
        sample = _text(row["sample_id"], "sample id")
        basis = _text(row["basis"], "measurement basis")
        availability = _text(row["availability"], "availability")
        _require(identity not in seen, "duplicate-measurement", "measurement IDs must be unique")
        seen.add(identity)
        _require(identity in identities and sample == identities[identity],
                 "sample-identity", "table identity differs from frozen measurement")
        _require(basis == rules["basis"], "mixed-basis", "count and volume bases cannot be mixed")
        _require(availability in {"observed", "unavailable"}, "invalid-record", "unknown availability")
        result = {"measurement_id": identity, "sample_id": sample, "classification": "unavailable",
                  "reasons": [], "statistics": "unavailable"}
        if availability == "unavailable":
            _require(all(row[key] is None for key in
                         ("values", "total_count", "below_range_fraction", "above_range_fraction")),
                     "unavailable-as-zero", "unavailable measurement requires null data, never zero")
            result["reasons"] = ["unavailable-record"]
        else:
            values = _list(row["values"], "bin values", MAX_BINS)
            _require(len(values) == len(original) - 1, "bin-values", "one value per frozen bin required")
            for value in values:
                _number(value, "bin value", 0, MAX_COUNT if basis == "count" else 1, basis == "count")
            total_count = _number(row["total_count"], "total count", 0, MAX_COUNT, True)
            mass = math.fsum(values)
            if basis == "volume":
                _require(abs(mass - 1) <= 1e-9, "fraction-sum", "volume fractions must sum to one within 1e-9")
            else:
                _require(mass == total_count, "count-total", "total count must equal in-range bin counts")
            lower = _number(row["below_range_fraction"], "lower tail fraction", 0, 1)
            upper = _number(row["above_range_fraction"], "upper tail fraction", 0, 1)
            tails = math.fsum((lower, upper))
            _require(tails <= 1, "tail-fraction", "tail fractions exceed one")
            reasons = []
            if total_count <= rules["minimum_total_count"]:
                reasons.append("count-rule")
            if tails >= rules["tail_fraction_max"]:
                reasons.append("tail-rule")
            result["reasons"] = reasons
            result["classification"] = "unreliable" if reasons else "reliable"
            if not reasons:
                merged = [math.fsum(values[a:b]) for a, b in zip(indices, indices[1:])]
                result["statistics"] = _quantities(edges, merged, lower, upper, basis)
        measurements.append(result)
        grouped[sample].append(result)
    _require(seen == set(identities), "missing-measurement", "missing measurements need explicit unavailable rows")
    samples = []
    for sample, records in grouped.items():
        reliable = [row for row in records if row["classification"] == "reliable"]
        agreement = "unavailable"
        agreeing = False
        if len(reliable) >= rules["minimum_replicates"]:
            agreement = {}
            for metric, key in (("D50_um", "d50"), ("span", "span")):
                values = [row["statistics"][metric] for row in reliable]
                mean = math.fsum(values) / len(values)
                _require(mean > 0, "degenerate-distribution", "positive agreement denominator required")
                agreement[key] = (max(values) - min(values)) / mean
            agreeing = (agreement["d50"] <= rules["d50_relative_range_max"]
                        and agreement["span"] <= rules["span_relative_range_max"])
        included = [row["measurement_id"] for row in reliable] if agreeing else []
        included_set = set(included)
        statistics = ({key: math.fsum(row["statistics"][key] for row in reliable) / len(reliable)
                       for key in METRICS} if agreeing else "unavailable")
        samples.append({"sample_id": sample, "classification": "summarized" if agreeing else "unavailable",
                        "included_measurement_ids": included,
                        "excluded_measurement_ids": [row["measurement_id"] for row in records
                                                     if row["measurement_id"] not in included_set],
                        "relative_ranges": agreement, "statistics": statistics})
    summary = {"n": len(samples), "summarized": sum(row["classification"] == "summarized" for row in samples),
               "unavailable": sum(row["classification"] == "unavailable" for row in samples),
               "reliable_measurements": sum(row["classification"] == "reliable" for row in measurements),
               "unreliable_measurements": sum(row["classification"] == "unreliable" for row in measurements),
               "unavailable_measurements": sum(row["classification"] == "unavailable" for row in measurements)}
    return {"measurements": measurements, "samples": samples, "summary": summary}

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
        _require(len(actual) == len(expected), "reported-selection", "reported measurement or sample count differs")
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


def validate_particle_size_distribution_pack(bundle):
    """Validate one immutable offline synthetic bundle; write no files or records."""
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
        pack = _record(store.load(path.name), "psd-pack-v1",
                       "rules frozen_rules_sha256 frozen_before_table_read table report evidence")
        rules = _rules(store.artifact(pack["rules"]))
        _require(_text(pack["frozen_rules_sha256"], "frozen rules hash") == pack["rules"]["sha256"]
                 and _boolean(pack["frozen_before_table_read"], "frozen before table read"),
                 "rule-freeze", "rules must be hash-frozen before the table is opened")
        report = _record(store.artifact(pack["report"]), "psd-report-v1",
                         "rules_sha256 exploratory bin_edges_um basis interpolation_rule tail_rule "
                         "measurements samples summary headline claims")
        _require(_text(report["rules_sha256"], "rules hash") == pack["rules"]["sha256"],
                 "rule-freeze", "report cites a different frozen rule revision")
        exploratory = _boolean(report["exploratory"], "exploratory")
        edges = _edges(report["bin_edges_um"])
        _require(edges == rules["bin_edges_um"] or exploratory,
                 "post-hoc-bins", "post-outcome bin merging requires an exploratory label")
        _require(report["basis"] == rules["basis"], "mixed-basis", "report basis differs from frozen basis")
        _require(report["interpolation_rule"] == rules["interpolation_rule"],
                 "percentile-rule", "non-cumulative percentile interpolation is refused")
        _require(report["tail_rule"] == rules["tail_rule"], "tail-rule", "out-of-range mass may not be ignored")
        headline = _text(report["headline"], "headline")
        _require(not OVERREACH.search(headline), "claim-overreach", "headline exceeds bounded synthetic arithmetic")
        descriptors = _list(pack["evidence"], "evidence artifacts", MAX_RECORDS, True)
        own_paths = {path.name}
        own_hashes = {store.snapshots[path.name][2]}
        for descriptor in (pack["rules"], pack["table"], pack["report"], *descriptors):
            _fields(descriptor, "path sha256", "artifact identity")
            own_paths.add(str(_relative(descriptor["path"])))
            own_hashes.add(_text(descriptor["sha256"], "sha256"))
        evidence = {}
        for descriptor in descriptors:
            document = _record(store.artifact(descriptor), "psd-evidence-v1", "records")
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
        result = compute_particle_size_distribution(store.artifact(pack["table"]), rules, edges)
        measurements = _list(report["measurements"], "reported measurements", MAX_ROWS)
        _require(len(measurements) == len(result["measurements"]), "missing-measurement", "report omits measurements")
        for actual, expected in zip(measurements, result["measurements"]):
            if expected["classification"] in {"unavailable", "unreliable"}:
                _require(type(actual) is dict and actual.get("classification") == expected["classification"]
                         and actual.get("statistics") == "unavailable",
                         "unreliable-included", "count/tail failures and absent data cannot have numerical summaries")
        samples = _list(report["samples"], "reported samples", MAX_SAMPLES)
        _require(len(samples) == len(result["samples"]), "sample-identity", "report omits samples")
        for actual, expected in zip(samples, result["samples"]):
            if expected["classification"] == "unavailable":
                _require(type(actual) is dict and actual.get("classification") == "unavailable"
                         and actual.get("statistics") == "unavailable" and actual.get("included_measurement_ids") == [],
                         "replicate-pooling", "too few or disagreeing reliable replicates cannot be pooled")
        _same(measurements, result["measurements"], "measurements")
        _same(samples, result["samples"], "samples")
        _same(report["summary"], result["summary"], "summary")
        store.finish()
        return {"schema": "psd-result-v1", "fixture": "synthetic fixture", "status": "arithmetic-only",
                "review": "unavailable", "stages": list(STAGES), "exploratory": exploratory,
                "inputs": [{"path": name, "sha256": item[2]} for name, item in sorted(store.snapshots.items())],
                "computation": result, "claims": report["claims"],
                "limitations": ["Synthetic tables establish software arithmetic only.",
                                "Percentiles assume uniform cumulative mass within each bin, including recorded tails.",
                                "Midpoint means assume spherical-volume scaling; they are in-range approximations.",
                                "Technical measurements never increase independent sample n.",
                                "Hashes cannot establish historical freeze timing or source independence.",
                                "Independent record, source and method review remains unavailable."]}
    finally:
        store.close()
