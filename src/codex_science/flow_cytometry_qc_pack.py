"""Read-only synthetic flow cytometry QC and compensated gate-count arithmetic."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat


STAGES = ("01-rule-freeze", "02-event-qc", "03-compensation-gates", "04-summary", "05-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_JSON_VALUES = 4_000_000
MAX_ARTIFACTS = 128
MAX_ROWS = 10000
MAX_SAMPLES = 32
MAX_CHANNELS = 16
MAX_GATES = 32
MAX_BINS = 128
MAX_RECORDS = 128
MAX_ITEMS = 20000
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
    r"inhibit\w*|activat\w*|regulat\w*|driv\w*|induc\w*|diagnos\w*|disease\w*|"
    r"cell[\s-]+identity|functional[\s-]+state|physical[\s-]+validity|truth)\b", re.I,
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
    allowance = MAX_JSON_VALUES if allowance is None else allowance
    upper = 1 + raw.count(b",") + sum(1 for _ in re.finditer(rb"[\[{](?=\s*[^\s\]}])", raw))
    _require(upper <= allowance, "input-limit", "bundle JSON value allowance exceeded before parsing")
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
        self.json_values = 0
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
            document, count = _json(raw, MAX_JSON_VALUES - self.json_values)
            self.json_values += count
            self.parsed[identity] = document
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

def _solve(matrix, vector):
    """Partial-pivot Gaussian elimination; the matrix maps true to measured values."""
    size = len(matrix)
    rows = [list(row) + [value] for row, value in zip(matrix, vector)]
    scale = max([abs(value) for row in matrix for value in row] + [1.0])
    for col in range(size):
        pivot = max(range(col, size), key=lambda index: abs(rows[index][col]))
        _require(abs(rows[pivot][col]) > scale * 1e-12, "compensation-singular", "compensation matrix is singular")
        rows[col], rows[pivot] = rows[pivot], rows[col]
        divisor = rows[col][col]
        rows[col] = [value / divisor for value in rows[col]]
        for index in range(size):
            if index != col:
                factor = rows[index][col]
                products = [factor * b for b in rows[col]]
                _require(all(math.isfinite(number) for number in products),
                         "compensation-degenerate", "non-finite elimination product")
                rows[index] = [math.fsum((a, -b)) for a, b in zip(rows[index], products)]
        _require(all(math.isfinite(value) and abs(value) <= MAX_NUMBER for row in rows for value in row),
                 "compensation-degenerate", "compensation produced non-finite or excessive values")
    return [row[-1] for row in rows]


def _rules(value):
    _record(value, "flow-cytometry-qc-rules-v1",
            "panel units scale compensation time singlet live populations controls order "
            "min_gate_events min_percentage_events hashed_before_events outcomes_seen exploratory")
    for field in ("hashed_before_events", "outcomes_seen", "exploratory"):
        _boolean(value[field], field)
    _require(value["hashed_before_events"], "rule-freeze", "rules must be hash-frozen before event admission")
    _require(not value["outcomes_seen"] or value["exploratory"],
             "post-outcome-gates", "gates placed after outcomes require an exploratory label")
    panel = _list(value["panel"], "panel", MAX_CHANNELS)
    channels = []
    for item in panel:
        _fields(item, "channel fluorochrome", "panel entry")
        channels.append(_text(item["channel"], "channel"))
        _text(item["fluorochrome"], "fluorochrome")
    _require(len(set(channels)) == len(channels), "invalid-record", "duplicate panel channel")
    _require(_text(value["scale"], "scale") == "linear", "unsupported-scale", "only linear event values supported")
    _text(value["units"], "units")
    comp = _fields(value["compensation"], "matrix source", "compensation")
    matrix = _list(comp["matrix"], "matrix rows", MAX_CHANNELS)
    _require(len(matrix) == len(channels), "invalid-record", "compensation must be square in panel order")
    for index, row in enumerate(matrix):
        _list(row, "matrix columns", MAX_CHANNELS)
        _require(len(row) == len(channels), "invalid-record", "compensation must be square")
        for number in row:
            _number(number, "matrix coefficient")
        _require(row[index] == 1, "invalid-record", "compensation needs a unit diagonal")
    _solve(matrix, [0] * len(channels))
    time = _fields(value["time"], "units bin_edges max_rate_variation", "time rule")
    _require(_text(time["units"], "time units") == "seconds", "invalid-record", "time must be in seconds")
    edges = _list(time["bin_edges"], "time edges", MAX_BINS + 1)
    _require(len(edges) >= 2, "invalid-record", "at least one time bin required")
    for edge in edges:
        _number(edge, "time edge")
    _require(all(left < right for left, right in zip(edges, edges[1:])),
             "invalid-record", "time bin edges must strictly increase")
    _number(time["max_rate_variation"], "rate variation bound", high=100)
    singlet = _fields(value["singlet"], "area height ratio_bounds", "singlet gate")
    live = _fields(value["live"], "channel max", "live gate")
    for channel in (singlet["area"], singlet["height"], live["channel"]):
        _require(_text(channel, "gate channel") in channels, "channel-not-in-panel", "gate channel absent from panel")
    _require(singlet["area"] != singlet["height"], "invalid-record", "area and height must be distinct")
    bounds = _list(singlet["ratio_bounds"], "ratio bounds", 2)
    _require(len(bounds) == 2, "invalid-record", "two ratio bounds required")
    for bound in bounds:
        _number(bound, "ratio bound", low=1e-12)
    _require(bounds[0] < bounds[1], "invalid-record", "ratio interval must have positive width")
    _number(live["max"], "live threshold")
    for field in ("min_gate_events", "min_percentage_events"):
        _number(value[field], field, low=1, high=MAX_ROWS, integer=True)
    controls = _list(value["controls"], "controls", MAX_SAMPLES)
    control_map = {}
    for control in controls:
        _fields(control, "id type channel max_positive_percentage", "control")
        identity = _text(control["id"], "control id")
        _require(identity not in control_map, "invalid-record", "duplicate control id")
        _require(_text(control["type"], "control type") in {"FMO", "isotype"}, "invalid-record", "FMO or isotype required")
        _require(_text(control["channel"], "control channel") in channels,
                 "channel-not-in-panel", "control channel absent from panel")
        _number(control["max_positive_percentage"], "control maximum", high=100)
        control_map[identity] = control
    populations = _list(value["populations"], "populations", MAX_GATES)
    names = ["stability", "singlets", "live"]
    for population in populations:
        _fields(population, "id parent bounds", "population")
        identity = _text(population["id"], "population id")
        _require(identity not in names and identity != "input", "invalid-record", "duplicate or reserved gate id")
        _require(_text(population["parent"], "gate parent") in names,
                 "gate-order", "population parent must precede it")
        # Every population descends from the frozen live and singlet exclusions.
        allowed_parents = {"live"} | set(names[3:])
        _require(population["parent"] in allowed_parents, "dead-retained", "populations must descend from live events")
        names.append(identity)
        intervals = _list(population["bounds"], "gate bounds", MAX_CHANNELS)
        used = set()
        for interval in intervals:
            _fields(interval, "channel low high low_control high_control", "interval")
            channel = _text(interval["channel"], "interval channel")
            _require(channel in channels, "channel-not-in-panel", "population channel absent from panel")
            _require(channel not in used, "invalid-record", "duplicate rectangular dimension")
            used.add(channel)
            _number(interval["low"], "lower boundary", low=-MAX_NUMBER)
            _number(interval["high"], "upper boundary", low=-MAX_NUMBER)
            _require(interval["low"] < interval["high"], "invalid-record", "gate interval must have positive width")
            for field in ("low_control", "high_control"):
                control = _text(interval[field], "boundary control")
                _require(control in control_map and control_map[control]["channel"] == channel,
                         "missing-control", "each boundary needs a matching frozen FMO or isotype control")
    order = _names(value["order"], "gate order", MAX_GATES + 3)
    _require("singlets" in order, "doublets-retained", "frozen order must exclude doublets")
    _require("live" in order, "dead-retained", "frozen order must exclude dead events")
    _require(order == names, "gate-order", "gates differ from frozen order")
    return channels, control_map


def _events(value, rules, channels, controls):
    _record(value, "flow-cytometry-qc-events-v1", "units scale samples")
    _require(_text(value["units"], "event units") == rules["units"]
             and _text(value["scale"], "event scale") == rules["scale"],
             "event-scale", "event units and scale differ from frozen panel")
    samples = _list(value["samples"], "samples", MAX_SAMPLES)
    seen_samples, seen_events = set(), set()
    total_rows = 0
    for sample in samples:
        _fields(sample, "id role status compensation_applied events", "sample")
        identity = _text(sample["id"], "sample id")
        _require(identity not in seen_samples, "duplicate-sample", "sample IDs must be unique")
        seen_samples.add(identity)
        role = _text(sample["role"], "sample role")
        status = _text(sample["status"], "sample status")
        _require(role in {"sample", "FMO", "isotype"} and status in {"available", "unavailable"},
                 "invalid-record", "unknown sample role or status")
        _number(sample["compensation_applied"], "compensation count", high=MAX_ROWS, integer=True)
        _require(sample["compensation_applied"] == 0, "compensation-twice", "events are already compensated")
        rows = _list(sample["events"], "events", MAX_ROWS, empty=True)
        total_rows += len(rows)
        _require(total_rows <= MAX_ROWS, "input-limit", "aggregate event count exceeded")
        _require((status == "unavailable") == (len(rows) == 0),
                 "empty-events", "empty samples must be unavailable; available samples need events")
        if role != "sample":
            _require(identity in controls and role == controls[identity]["type"] and status == "available",
                     "missing-control", "required controls must be available with matching roles")
        last_time = -1
        for row in rows:
            _fields(row, "id time values", "event")
            event = _text(row["id"], "event id")
            _require(event not in seen_events, "duplicate-event", "event IDs must be globally unique")
            seen_events.add(event)
            moment = _number(row["time"], "event time")
            _require(moment >= last_time, "time-not-monotonic", "event times must be nondecreasing per sample")
            last_time = moment
            _require(rules["time"]["bin_edges"][0] <= moment < rules["time"]["bin_edges"][-1],
                     "time-outside-bins", "events must lie in the frozen half-open time range")
            values = row["values"]
            _require(type(values) is dict, "invalid-record", "event values must map named channels")
            _require(all(channel in channels for channel in values),
                     "channel-not-in-panel", "event channel absent from panel")
            _fields(values, channels, "event channels")
            for number in values.values():
                _number(number, "raw event intensity")
            _require(values[rules["singlet"]["height"]] > 0,
                     "degenerate-singlet", "area-height ratio requires positive height")
    roles = {sample["id"]: sample["role"] for sample in samples}
    _require(all(roles.get(identity) == control["type"] for identity, control in controls.items()),
             "missing-control", "frozen control absent from table or relabelled as another role")
    _require(any(sample["role"] == "sample" for sample in samples), "empty-events", "at least one sample required")
    return samples


def reference_computation(rules, event_table):
    """Compute frozen synthetic gate counts; compensated intensities may be negative."""
    channels, controls = _rules(rules)
    samples = _events(event_table, rules, channels, controls)
    indices = {name: index for index, name in enumerate(channels)}
    singlet, live = rules["singlet"], rules["live"]
    edges = rules["time"]["bin_edges"]
    output = []
    selected = {}
    for sample in samples:
        if sample["status"] == "unavailable":
            output.append({"id": sample["id"], "status": "unavailable", "stability": "unavailable",
                           "gates": [{"id": name, "parent": "unavailable", "count": "unavailable",
                                      "parent_count": "unavailable", "percentage": "unavailable"}
                                     for name in rules["order"]]})
            selected[sample["id"]] = {}
            continue
        compensated = [_solve(rules["compensation"]["matrix"], [row["values"][name] for name in channels])
                       for row in sample["events"]]
        bins = [0] * (len(edges) - 1)
        for row in sample["events"]:
            for index, (low, high) in enumerate(zip(edges, edges[1:])):
                if low <= row["time"] < high:
                    bins[index] += 1
                    break
        rates = [count / (high - low) for count, low, high in zip(bins, edges, edges[1:])]
        _require(all(math.isfinite(rate) and rate <= MAX_NUMBER for rate in rates),
                 "degenerate-stability", "event rate exceeds finite arithmetic envelope")
        mean = math.fsum(rates) / len(rates)
        _require(mean > 0 and all(math.isfinite(rate) for rate in rates),
                 "degenerate-stability", "finite nonempty event rates required")
        variation = (max(rates) - min(rates)) / mean
        _require(variation <= rules["time"]["max_rate_variation"],
                 "flow-unstable", "event rate variation exceeds frozen maximum")
        masks = {"input": list(range(len(compensated))), "stability": list(range(len(compensated)))}
        area, height = indices[singlet["area"]], indices[singlet["height"]]
        _require(all(row[height] > 0 for row in compensated),
                 "degenerate-singlet", "compensated height must be positive")
        ratios = [row[area] / row[height] for row in compensated]
        _require(all(math.isfinite(ratio) and abs(ratio) <= MAX_NUMBER for ratio in ratios),
                 "degenerate-singlet", "area-height ratio must be finite within the arithmetic envelope")
        masks["singlets"] = [index for index in masks["stability"]
                             if singlet["ratio_bounds"][0] <= ratios[index] <= singlet["ratio_bounds"][1]]
        masks["live"] = [index for index in masks["singlets"] if compensated[index][indices[live["channel"]]] <= live["max"]]
        parents = {"stability": "input", "singlets": "stability", "live": "singlets"}
        for population in rules["populations"]:
            identity = population["id"]
            parents[identity] = population["parent"]
            masks[identity] = [index for index in masks[population["parent"]]
                               if all(bound["low"] <= compensated[index][indices[bound["channel"]]] <= bound["high"]
                                      for bound in population["bounds"])]
        gates = []
        for identity in rules["order"]:
            count, parent = len(masks[identity]), len(masks[parents[identity]])
            percentage = 100 * count / parent if count >= rules["min_gate_events"] and parent >= rules["min_percentage_events"] else "unavailable"
            gates.append({"id": identity, "parent": parents[identity], "count": count,
                          "parent_count": parent, "percentage": percentage})
        selected[sample["id"]] = masks
        output.append({"id": sample["id"], "status": "available", "gates": gates,
                       "stability": {"bin_counts": bins, "rates": rates, "variation": variation}})
    control_results = []
    for population in rules["populations"]:
        used = {bound[field] for bound in population["bounds"] for field in ("low_control", "high_control")}
        for identity in sorted(used):
            masks = selected[identity]
            denominator = len(masks["live"])
            _require(denominator >= rules["min_percentage_events"],
                     "insufficient-control", "control percentage denominator is below the frozen minimum")
            count = len(masks[population["id"]])
            percentage = 100 * count / denominator
            _require(percentage <= controls[identity]["max_positive_percentage"],
                     "fmo-positive-rate", "FMO or isotype positive rate exceeds the frozen maximum")
            control_results.append({"control": identity, "gate": population["id"], "count": count,
                                    "parent_count": denominator, "percentage": percentage})
    return {"samples": output, "controls": control_results, "exploratory": rules["exploratory"]}


def _compare(actual, expected, label="report"):
    if type(expected) is dict:
        _fields(actual, expected, label)
        for key in expected:
            _compare(actual[key], expected[key], key)
    elif type(expected) is list:
        _list(actual, label, MAX_ITEMS, empty=True)
        if label == "gates":
            ids = [_text(_fields(gate, "id parent count parent_count percentage", "reported gate")["id"], "gate id") for gate in actual]
            _require("singlets" in ids, "doublets-retained", "reported gates omit doublet exclusion")
            _require("live" in ids, "dead-retained", "reported gates omit live exclusion")
            _require(ids == [gate["id"] for gate in expected], "gate-order", "reported gate order differs from freeze")
        _require(len(actual) == len(expected), "report-mismatch", f"{label} length differs")
        for item, other in zip(actual, expected):
            _compare(item, other, label)
    elif type(expected) in (int, float):
        _number(actual, label, integer=type(expected) is int)
        _require(math.isclose(actual, expected, rel_tol=1e-9, abs_tol=0),
                 "report-mismatch", f"{label} differs from reference arithmetic")
    else:
        code = "percentage-unavailable" if expected == "unavailable" else "report-mismatch"
        _require(type(actual) is type(expected) and actual == expected, code, f"{label} differs; unavailable is never zero")


def _claims(claims, evidence):
    claims = _list(claims, "claims", MAX_RECORDS, empty=True)
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
                 "claim-overreach", "only synthetic counts and QC descriptions are permitted")
        _require(status in STATUSES, "invalid-record", "unknown claim status")
        ids = _names(claim["evidence"], "claim evidence", MAX_RECORDS, empty=True)
        _require(ids or status == "unavailable", "missing-evidence", "empty evidence requires unavailable")
        _require(status != "unavailable" or not ASSERTION.search(text),
                 "unavailable-positive", "unavailable claim asserts positive evidence")
        for identity in ids:
            _require(identity in evidence, "missing-evidence", "unknown evidence identity")
            record = evidence[identity]
            _require("unavailable" not in (record["kind"], record["result"]) or status == "unavailable",
                     "unavailable-evidence", "unavailable evidence requires an unavailable claim")
            _require(status not in POSITIVE or not any(NON_EVIDENCE.search(record[key]) for key in ("kind", "result")),
                     "non-evidence-support", "review approval or computed records cannot support positive claims")
        _require(status != "replicated", "claim-replication", "a synthetic fixture cannot establish independent replication")


def validate_flow_cytometry_qc_pack(bundle):
    """Validate exactly the bytes hashed, then recheck inputs; write nothing."""
    try:
        value = _text(os.fspath(bundle), "bundle path")
        _require(all(ord(char) >= 32 for char in value), "input-path", "control character in bundle path")
        path = Path(os.path.abspath(value))
    except (TypeError, ValueError) as error:
        raise ValueError("input-path: invalid bundle path") from error
    store = _Bundle(path.parent)
    try:
        pack = _record(store.load(path.name), "flow-cytometry-qc-pack-v1",
                       "stages rules frozen_rules_sha256 events report evidence claims")
        _require(_names(pack["stages"], "stages", len(STAGES)) == list(STAGES), "stage-order", "five fixed stages required")
        rules = store.artifact(pack["rules"])
        _rules(rules)
        _require(_text(pack["frozen_rules_sha256"], "frozen rules hash") == pack["rules"]["sha256"],
                 "rule-freeze", "rules hash must be frozen before events are read")
        source_digest = store.artifact(rules["compensation"]["source"], parse=False)
        event_table = store.artifact(pack["events"])
        result = reference_computation(rules, event_table)
        report = _record(store.artifact(pack["report"]), "flow-cytometry-qc-report-v1",
                         "rules_sha256 events_sha256 kind samples controls exploratory")
        _require(_text(report["rules_sha256"], "rules hash") == pack["rules"]["sha256"]
                 and _text(report["events_sha256"], "events hash") == pack["events"]["sha256"],
                 "input-hash", "report handoff hashes differ")
        _require(_text(report["kind"], "report kind") == "computed", "invalid-record", "reference report must declare computed")
        _compare({key: report[key] for key in result}, result)
        records = _list(pack["evidence"], "evidence records", MAX_RECORDS, empty=True)
        own_paths = {path.name, pack["rules"]["path"], pack["events"]["path"], pack["report"]["path"], rules["compensation"]["source"]["path"]}
        own_hashes = {entry[2] for entry in store.snapshots.values()} | {source_digest}
        evidence = {}
        for record in records:
            _fields(record, "id kind result origin source", "evidence")
            identity = _text(record["id"], "evidence id")
            _require(identity not in evidence, "invalid-record", "duplicate evidence id")
            for field in ("kind", "result", "origin"):
                _text(record[field], field)
            _require(record["origin"] in {"internal", "external", "independent", "preregistered"},
                     "invalid-record", "unknown evidence origin")
            digest = store.artifact(record["source"], parse=False)
            if record["origin"] != "internal":
                _require(record["source"]["path"] not in own_paths and digest not in own_hashes,
                         "external-alias", "external label aliases this study's artifacts")
            evidence[identity] = record
        _claims(pack["claims"], evidence)
        store.finish()
        return {"schema": "flow-cytometry-qc-result-v1", "fixture": "synthetic fixture", "status": "arithmetic-only",
                "review": "unavailable", "stages": list(STAGES), "computation": result,
                "inputs": [{"path": name, "sha256": item[2]} for name, item in sorted(store.snapshots.items())],
                "limitations": ["Synthetic QC arithmetic cannot establish cell identity, function or disease state.",
                                "Historical freeze timing and real source independence are not proved by hashes.",
                                "Independent review remains coordinator-owned and unavailable here."]}
    except OSError as error:
        raise ValueError("input-file: input unavailable or changed") from error
    finally:
        store.close()
