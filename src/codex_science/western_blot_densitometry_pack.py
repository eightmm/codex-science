"""Read-only synthetic band densitometry admission and biological-unit reference arithmetic."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat


STAGES = ("01-rule-freeze", "02-table-qc", "03-normalisation", "04-summary", "05-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_ROWS = 10000
MAX_UNITS = 128
MAX_GROUPS = 16
MAX_BLOTS = 128
MAX_ANTIBODIES = 16
MAX_DILUTIONS = 64
MAX_INTENSITY = 1e12
MAX_NODES = 4000000
MAX_ITERATIONS = 256
QUANTILE_STEPS = 96
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
    r"physical[\s-]+validity|patient[\s-]+benefit\w*|protein[\s-]+abundan\w*|express\w*)\b", re.I,
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
    _require(len(pairs) <= MAX_ROWS, "input-limit", "JSON object exceeds limit")
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


def _beta_fraction(a, b, x):
    """Bounded continued fraction for the regularized incomplete beta function."""
    tiny = 1e-300
    c, d = 1.0, 1 - (a + b) * x / (a + 1)
    d = 1 / (d if abs(d) >= tiny else tiny)
    h = d
    for m in range(1, MAX_ITERATIONS + 1):
        for numerator in (m * (b - m) * x / ((a + 2*m - 1) * (a + 2*m)),
                          -(a + m) * (a + b + m) * x / ((a + 2*m) * (a + 2*m + 1))):
            d = 1 + numerator * d
            c = 1 + numerator / c
            d = 1 / (d if abs(d) >= tiny else tiny)
            c = c if abs(c) >= tiny else tiny
            delta = d * c
            h *= delta
        if abs(delta - 1) <= 1e-14:
            return h
    raise ValueError("welch-convergence: beta fraction did not converge")


def _beta(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    factor = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                      + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1) / (a + b + 2):
        return factor * _beta_fraction(a, b, x) / a
    return 1 - factor * _beta_fraction(b, a, 1 - x) / b


def _t_quantile(df, level):
    low, high = 0.0, 1e6
    tail = (1 - level) / 2
    for _ in range(QUANTILE_STEPS):
        middle = (low + high) / 2
        survival = .5 * _beta(df / 2, .5, df / (df + middle * middle))
        if survival > tail:
            low = middle
        else:
            high = middle
    _require(high - low <= high * 1e-12, "welch-convergence", "t quantile did not converge")
    return (low + high) / 2


def _moments(values):
    mean = math.fsum(values) / len(values)
    variance = math.fsum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return mean, variance


def welch_fold_interval(first, reference, level=.95, minimum=3):
    """Delta-method log ratio of arithmetic means with Welch-Satterthwaite df.

    Independent biological units, positive means and nonzero within-group variance
    are assumptions. This approximate interval does not propagate reference-lane
    calibration uncertainty or establish physical validity.
    """
    _number(minimum, "minimum biological units", 3, MAX_UNITS, True)
    _number(level, "interval level", .5, .999)
    for values in (first, reference):
        _list(values, "biological values", MAX_UNITS)
        _require(len(values) >= minimum, "insufficient-biological-units", "Welch interval needs frozen minimum")
        for value in values:
            _number(value, "normalised biological value", 1e-24, 1e24)
    mean, variance = _moments(first)
    baseline, baseline_variance = _moments(reference)
    _require(variance > 0 and baseline_variance > 0,
             "degenerate-variance", "zero within-group variance cannot support a Welch interval")
    a = variance / len(first) / mean ** 2
    b = baseline_variance / len(reference) / baseline ** 2
    total = math.fsum((a, b))
    _require(total > 0 and a > 0 and b > 0, "degenerate-variance", "variance underflow")
    df = total ** 2 / math.fsum((a ** 2 / (len(first)-1), b ** 2 / (len(reference)-1)))
    width = _t_quantile(df, level) * math.sqrt(total)
    centre = math.log(mean) - math.log(baseline)
    _require(-700 <= centre - width and centre + width <= 700,
             "degenerate-interval", "fold interval exceeds finite reference range")
    return {"method": "welch-log-delta", "level": level, "degrees_of_freedom": df,
            "lower": math.exp(centre - width), "upper": math.exp(centre + width)}


def _rules(value):
    _record(value, "wb-rules-v1", "groups reference_group lanes antibodies reference_lanes "
            "background_rule normalisation replicate_rule minimum_biological_units maximum_loading_control_cv "
            "interval_method interval_level")
    groups = _names(value["groups"], "groups", MAX_GROUPS)
    _require(len(groups) >= 2, "invalid-record", "at least two groups required")
    _require(_text(value["reference_group"], "reference group") in groups,
             "group-identity", "reference group must be frozen")
    _require(value["background_rule"] == "local-per-lane", "background-rule", "local per-lane subtraction required")
    _require(value["normalisation"] == "target-over-loading-control", "normalisation-rule", "lane ratio required")
    _require(value["replicate_rule"] == "collapse-technical-before-biological",
             "technical-replicates", "technical lanes cannot count as biological units")
    _number(value["minimum_biological_units"], "minimum biological units", 3, MAX_UNITS, True)
    _number(value["maximum_loading_control_cv"], "maximum loading-control CV", 0, 1)
    _require(value["interval_method"] == "welch-log-delta", "welch-interval", "frozen Welch interval required")
    _number(value["interval_level"], "interval level", .5, .999)
    antibodies = _list(value["antibodies"], "antibodies", MAX_ANTIBODIES)
    antibody_ids = set()
    for antibody in antibodies:
        _fields(antibody, "antibody_id minimum maximum saturation_ceiling dilution_series", "antibody")
        identity = _text(antibody["antibody_id"], "antibody id")
        _require(identity not in antibody_ids, "invalid-record", "duplicate antibody")
        antibody_ids.add(identity)
        low = _number(antibody["minimum"], "linear minimum", 1e-12, MAX_INTENSITY)
        high = _number(antibody["maximum"], "linear maximum", low, MAX_INTENSITY)
        ceiling = _number(antibody["saturation_ceiling"], "saturation ceiling", high, MAX_INTENSITY)
        _require(low < high < ceiling, "dilution-series", "linear range must precede saturation")
        series = _list(antibody["dilution_series"], "dilution series", MAX_DILUTIONS)
        _require(len(series) >= 3, "dilution-series", "at least three frozen dilution points required")
        previous, slopes, intensities = 0, [], []
        for row in series:
            _fields(row, "amount intensity", "dilution point")
            amount = _number(row["amount"], "dilution amount", 1e-12, MAX_INTENSITY)
            intensity = _number(row["intensity"], "dilution intensity", low, high)
            _require(amount > previous, "dilution-series", "dilution amounts must increase")
            previous = amount
            slopes.append(intensity / amount)
            intensities.append(intensity)
        _require(min(intensities) == low and max(intensities) == high
                 and all(math.isclose(slope, slopes[0], rel_tol=1e-9, abs_tol=0) for slope in slopes),
                 "dilution-series", "bounds must match a proportional synthetic dilution series")
    lanes = _list(value["lanes"], "frozen lanes", MAX_ROWS)
    ids, blots, units, samples = set(), set(), {}, {}
    for row in lanes:
        _fields(row, "lane_id sample_id blot_id biological_unit group target_band loading_control_band", "lane rule")
        for key in row:
            _text(row[key], key)
        _require(row["lane_id"] not in ids, "duplicate-lane", "lane identities must be unique")
        ids.add(row["lane_id"])
        blots.add(row["blot_id"])
        _require(len(blots) <= MAX_BLOTS, "input-limit", "too many blots")
        _require(row["group"] in groups, "group-identity", "lane group differs from frozen groups")
        unit = row["biological_unit"]
        _require(units.get(unit, row["group"]) == row["group"],
                 "technical-replicates", "biological unit cannot cross groups")
        _require(samples.get(row["sample_id"], unit) == unit,
                 "technical-replicates", "one sample cannot become multiple biological units")
        units[unit], samples[row["sample_id"]] = row["group"], unit
        _require(len(units) <= MAX_UNITS, "input-limit", "too many biological units")
        _require(row["target_band"] in antibody_ids and row["loading_control_band"] in antibody_ids
                 and row["target_band"] != row["loading_control_band"],
                 "band-identity", "target and loading control need distinct frozen antibodies")
    _require(type(value["reference_lanes"]) is dict, "invalid-record", "reference lanes must be an object")
    _require(set(value["reference_lanes"]) == blots, "reference-lane", "every blot needs a frozen reference lane")
    by_id = {row["lane_id"]: row for row in lanes}
    for blot, lane in value["reference_lanes"].items():
        _text(lane, "reference lane")
        _require(lane in by_id and by_id[lane]["blot_id"] == blot,
                 "reference-lane", "each blot needs its own frozen reference lane")
    for row in lanes:
        reference = by_id[value["reference_lanes"][row["blot_id"]]]
        _require(all(row[key] == reference[key] for key in ("target_band", "loading_control_band")),
                 "band-identity", "blot scaling requires the same antibody pair as its reference")
    return value


def _compute(table, rules, reported_lanes=None):
    rules = _rules(rules)
    _record(table, "wb-table-v1", "rows")
    rows = _list(table["rows"], "intensity rows", MAX_ROWS)
    frozen = {row["lane_id"]: row for row in rules["lanes"]}
    antibodies = {row["antibody_id"]: row for row in rules["antibodies"]}
    measured, controls = {}, []
    for row in rows:
        _fields(row, "lane_id target_intensity target_background loading_control_intensity loading_control_background",
                "intensity row")
        lane = _text(row["lane_id"], "lane id")
        _require(lane not in measured, "duplicate-lane", "intensity lane identities must be unique")
        _require(lane in frozen, "lane-identity", "unknown intensity lane")
        values = [row[key] for key in row if key != "lane_id"]
        reasons, corrected = [], {}
        if all(value is None for value in values):
            reasons.append("unavailable")
        else:
            for band, key in (("target", "target_band"), ("loading_control", "loading_control_band")):
                raw = _number(row[band + "_intensity"], band + " intensity", 0, MAX_INTENSITY)
                background = _number(row[band + "_background"], band + " background", 0, MAX_INTENSITY)
                limits = antibodies[frozen[lane][key]]
                corrected[band] = raw - background
                if corrected[band] < 0:
                    reasons.append("negative-after-background")
                if raw >= limits["saturation_ceiling"]:
                    reasons.append("saturated-band")
                if not limits["minimum"] <= corrected[band] <= limits["maximum"]:
                    reasons.append("target-range" if band == "target" else "loading-control-range")
            if corrected["loading_control"] >= 0:
                controls.append(corrected["loading_control"])
        measured[lane] = {"lane_id": lane, "classification": "unreliable" if reasons else "reliable",
                          "reasons": list(dict.fromkeys(reasons)), "ratio": "unavailable", "scaled_ratio": "unavailable"}
        if not reasons:
            measured[lane]["ratio"] = corrected["target"] / corrected["loading_control"]
    _require(set(measured) == set(frozen), "missing-lane", "missing lanes require explicit unavailable rows")
    if reported_lanes is not None:
        lanes = _list(reported_lanes, "reported lanes", MAX_ROWS)
        _require(len(lanes) == len(measured), "reported-result", "report omits lanes")
        for observed, expected in zip(lanes, measured.values()):
            _require(type(observed) is dict, "invalid-record", "reported lane must be an object")
            if expected["classification"] == "unreliable":
                _require(observed.get("classification") == "unreliable"
                         and observed.get("ratio") == "unavailable" and observed.get("scaled_ratio") == "unavailable",
                         expected["reasons"][0], "unreliable lane must be excluded before log or division")
    cv = "unavailable"
    if len(controls) >= 2:
        mean, variance = _moments(controls)
        _require(mean > 0, "loading-control-cv", "zero loading-control mean")
        cv = math.sqrt(variance) / mean
        _require(cv <= rules["maximum_loading_control_cv"],
                 "loading-control-cv", "loading-control CV exceeds frozen bound")
    by_unit = {}
    for lane, row in measured.items():
        if row["classification"] != "reliable":
            continue
        identity = frozen[lane]
        reference = measured[rules["reference_lanes"][identity["blot_id"]]]
        _require(reference["classification"] == "reliable", "reference-lane", "blot reference is unreliable")
        row["scaled_ratio"] = row["ratio"] / reference["ratio"]
        by_unit.setdefault(identity["biological_unit"], []).append(row["scaled_ratio"])
    # A blot with no reliable sample still needs an explicit reliable calibration lane.
    for lane in rules["reference_lanes"].values():
        _require(measured[lane]["classification"] == "reliable", "reference-lane", "blot reference is unavailable")
    unit_groups = {row["biological_unit"]: row["group"] for row in rules["lanes"]}
    units = [{"biological_unit": unit, "group": group, "n_lanes": len(by_unit.get(unit, [])),
              "mean": math.fsum(by_unit[unit]) / len(by_unit[unit]) if unit in by_unit else "unavailable"}
             for unit, group in unit_groups.items()]
    values = {group: [] for group in rules["groups"]}
    for unit in units:
        if unit["mean"] != "unavailable":
            values[unit["group"]].append(unit["mean"])
    groups = []
    baseline = values[rules["reference_group"]]
    for group, sample in values.items():
        mean = math.fsum(sample) / len(sample) if sample else "unavailable"
        sem = math.sqrt(_moments(sample)[1] / len(sample)) if len(sample) >= 2 else "unavailable"
        interval = "unavailable"
        if group != rules["reference_group"] and min(len(sample), len(baseline)) >= rules["minimum_biological_units"]:
            interval = welch_fold_interval(sample, baseline, rules["interval_level"], rules["minimum_biological_units"])
        fold = mean / (math.fsum(baseline) / len(baseline)) if sample and baseline else "unavailable"
        groups.append({"group": group, "n": len(sample), "mean": mean, "standard_error": sem,
                       "fold_change": fold, "interval": interval})
    return {"lanes": list(measured.values()), "biological_units": units, "groups": groups, "loading_control_cv": cv}


def compute_densitometry(table, rules):
    """Exclude unreliable bands before division; average technical lanes first."""
    return _compute(table, rules)


def _same(actual, expected, label):
    if type(expected) in (int, float):
        _number(actual, label, 0 if type(expected) is int else -MAX_NUMBER, integer=type(expected) is int)
        _require(math.isclose(actual, expected, rel_tol=1e-9, abs_tol=0),
                 "reported-number", f"reported {label} disagrees with reference")
    elif type(expected) is dict:
        _fields(actual, expected, label)
        for key in expected:
            _same(actual[key], expected[key], key)
    elif type(expected) is list:
        _list(actual, label, MAX_ROWS, True)
        _require(len(actual) == len(expected), "reported-result", "reported record count differs")
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


def validate_western_blot_densitometry_pack(bundle):
    """Validate a frozen, read-only offline synthetic bundle; never self-review."""
    try:
        value = _text(os.fspath(bundle), "bundle path")
        _require(all(ord(c) >= 32 for c in value) and ".." not in Path(value).parts and "\\" not in value,
                 "input-path", "invalid bundle path")
        path = Path(os.path.abspath(value))
    except (TypeError, ValueError) as error:
        raise ValueError("input-path: invalid bundle path") from error
    store = _Bundle(path.parent)
    try:
        pack = _record(store.load(path.name), "wb-pack-v1",
                       "rules frozen_rules_sha256 frozen_before_intensities_read table report evidence")
        rules = _rules(store.artifact(pack["rules"]))
        _require(_text(pack["frozen_rules_sha256"], "frozen rules hash") == pack["rules"]["sha256"]
                 and _boolean(pack["frozen_before_intensities_read"], "frozen before intensities read"),
                 "rule-freeze", "rules must be hash-frozen before intensity bytes are opened")
        report = _record(store.artifact(pack["report"]), "wb-report-v1",
                         "rules_sha256 exploratory applied_rules computation headline claims")
        exploratory = _boolean(report["exploratory"], "exploratory")
        _require(_text(report["rules_sha256"], "report rules hash") == pack["rules"]["sha256"],
                 "rule-freeze", "report must retain original frozen identity")
        applied = _rules(report["applied_rules"])
        _require(applied == rules or exploratory,
                 "post-outcome-rules", "changed rules require exploratory label and recomputation")
        _require(not OVERREACH.search(_text(report["headline"], "headline")),
                 "claim-overreach", "headline exceeds bounded synthetic arithmetic")
        descriptors = _list(pack["evidence"], "evidence artifacts", MAX_RECORDS, True)
        own_paths, own_hashes = {path.name}, {store.snapshots[path.name][2]}
        for descriptor in (pack["rules"], pack["table"], pack["report"], *descriptors):
            _fields(descriptor, "path sha256", "artifact identity")
            own_paths.add(str(_relative(descriptor["path"])))
            own_hashes.add(_text(descriptor["sha256"], "sha256"))
        evidence = {}
        for descriptor in descriptors:
            document = _record(store.artifact(descriptor), "wb-evidence-v1", "records")
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
        actual = _fields(report["computation"], "lanes biological_units groups loading_control_cv", "reported computation")
        result = _compute(store.artifact(pack["table"]), applied, actual["lanes"])
        units = _list(actual["biological_units"], "reported biological units", MAX_UNITS)
        _require(len(units) == len(result["biological_units"]),
                 "technical-replicates", "technical lane repeats cannot increase biological n")
        groups = _list(actual["groups"], "reported groups", MAX_GROUPS)
        _require(len(groups) == len(result["groups"]), "group-identity", "report omits groups")
        for observed, expected in zip(groups, result["groups"]):
            _require(type(observed) is dict and "n" in observed, "invalid-record", "reported group needs n")
            _number(observed["n"], "biological n", 0, MAX_UNITS, True)
            _require(observed["n"] == expected["n"], "technical-replicates", "group n must count reliable biological units")
        _same(actual, result, "computation")
        store.finish()
        return {"schema": "wb-result-v1", "fixture": "synthetic fixture", "status": "arithmetic-only",
                "review": "unavailable", "stages": list(STAGES), "exploratory": exploratory,
                "inputs": [{"path": name, "sha256": item[2]} for name, item in sorted(store.snapshots.items())],
                "computation": result, "claims": report["claims"],
                "limitations": ["Synthetic intensities establish software arithmetic only.",
                                "Welch log-delta bounds are approximate and assume independent biological units.",
                                "Reference-lane calibration uncertainty is not propagated.",
                                "Hashes cannot establish historical freeze timing or true independence.",
                                "Independent record, source and method review remains unavailable."]}
    finally:
        store.close()
