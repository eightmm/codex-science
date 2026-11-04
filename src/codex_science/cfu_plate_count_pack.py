"""Read-only synthetic CFU plate-count admission and exact Poisson reference arithmetic."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat


STAGES = ("01-rule-freeze", "02-count-qc", "03-cfu", "04-summary", "05-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_ROWS = 10000
MAX_SAMPLES = 128
MAX_NODES = 4000000
MAX_COLONIES = 100000
MAX_ITERATIONS = 10000
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
    r"physical[\s-]+validity|patient[\s-]+benefit\w*|steril\w*|safe\w*|poten\w*)\b", re.I,
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


def _gamma_p(shape, x):
    """Regularized integer-shape gamma CDF, without a normal approximation."""
    if x == 0:
        return 0.0
    factor = math.exp(shape * math.log(x) - x - math.lgamma(shape))
    if x < shape + 1:
        term = 1.0 / shape
        total = term
        for step in range(1, MAX_ITERATIONS + 1):
            term *= x / (shape + step)
            total = math.fsum((total, term))
            if term <= total * 1e-14:
                return min(1.0, max(0.0, total * factor))
    else:
        tiny = 1e-300
        b = x + 1 - shape
        c = 1 / tiny
        d = 1 / b
        product = d
        for step in range(1, MAX_ITERATIONS + 1):
            a = -step * (step - shape)
            b += 2
            d = a * d + b
            if abs(d) < tiny:
                d = math.copysign(tiny, d)
            c = b + a / c
            if abs(c) < tiny:
                c = math.copysign(tiny, c)
            d = 1 / d
            delta = d * c
            product *= delta
            if abs(delta - 1) <= 1e-14:
                return min(1.0, max(0.0, 1 - factor * product))
    raise ValueError("poisson-convergence: exact gamma tail did not converge")


def _gamma_quantile(shape, probability):
    low, high = 0.0, float(2 * shape + 100)
    _require(_gamma_p(shape, high) >= probability,
             "poisson-convergence", "gamma quantile is outside its bounded bracket")
    for _ in range(QUANTILE_STEPS):
        middle = (low + high) / 2
        if _gamma_p(shape, middle) < probability:
            low = middle
        else:
            high = middle
    _require(high - low <= high * 1e-12,
             "poisson-convergence", "gamma quantile bisection did not converge")
    return (low + high) / 2


def poisson_interval(count, exposure, level=0.95):
    """Garwood equal-tail interval for a Poisson count per mL-equivalent exposure."""
    _number(count, "count", 0, MAX_COLONIES, True)
    _number(exposure, "exposure", 1e-24, 1e12)
    _number(level, "interval level", 0.5, 0.999)
    tail = (1 - level) / 2
    lower = _gamma_quantile(count, tail) / exposure if count else 0.0
    upper = _gamma_quantile(count + 1, 1 - tail) / exposure
    return {"method": "garwood-exact", "level": level, "lower": lower, "upper": upper}


def _ranges(value, ids):
    _fields(value, ids, "countable ranges")
    for plate in ids:
        row = _fields(value[plate], "minimum maximum", "countable range")
        _number(row["minimum"], "countable minimum", 1, MAX_COLONIES, True)
        _number(row["maximum"], "countable maximum", row["minimum"], MAX_COLONIES, True)
    return value


def _rules(value):
    _record(value, "cfu-rules-v1", "sample_ids plates dilution_ratio minimum_countable_plates "
            "duplicate_maximum_ratio weighted_mean_rule interval_method interval_level detection_rule")
    samples = _names(value["sample_ids"], "sample identities", MAX_SAMPLES)
    plates = _list(value["plates"], "plate rules", MAX_ROWS)
    _number(value["dilution_ratio"], "dilution ratio", 1.000001, 1e6)
    _number(value["minimum_countable_plates"], "minimum countable plates", 1, MAX_ROWS, True)
    _number(value["duplicate_maximum_ratio"], "duplicate ratio", 1, 100)
    _require(value["weighted_mean_rule"] == "sum-counts-over-sum-volume-equivalents",
             "weighted-mean-rule", "only the frozen exposure-weighted mean is admitted")
    _require(value["interval_method"] == "garwood-exact", "poisson-interval", "exact Poisson interval required")
    _number(value["interval_level"], "interval level", 0.5, 0.999)
    _require(value["detection_rule"] == "one-sided-poisson-upper",
             "detection-rule", "below-countable needs a positive one-sided Poisson upper bound")
    seen = set()
    by_sample = {sample: set() for sample in samples}
    for row in plates:
        _require(type(row) is dict and "dilution_factor" in row and "volume_ml" in row,
                 "plate-exposure", "every plate needs a dilution factor and volume")
        _fields(row, "plate_id sample_id dilution_factor volume_ml minimum maximum", "plate rule")
        plate = _text(row["plate_id"], "plate id")
        sample = _text(row["sample_id"], "sample id")
        _require(plate not in seen, "duplicate-plate", "plate IDs must be unique")
        seen.add(plate)
        _require(sample in by_sample, "sample-identity", "plate sample is outside frozen identities")
        _number(row["dilution_factor"], "dilution factor", 1e-12, 1)
        _number(row["volume_ml"], "plated mL", 1e-12, 100)
        _ranges({plate: {key: row[key] for key in ("minimum", "maximum")}}, [plate])
        by_sample[sample].add(row["dilution_factor"])
    for dilutions in by_sample.values():
        _require(bool(dilutions), "sample-identity", "each frozen sample needs plate rules")
        ordered = sorted(dilutions)
        _require(all(math.isclose(b / a, value["dilution_ratio"], rel_tol=1e-12, abs_tol=0)
                     for a, b in zip(ordered, ordered[1:])),
                 "dilution-series", "dilutions must follow the frozen geometric ratio")
    return value


def compute_cfu(counts, rules, countable_ranges=None):
    """Compute synthetic CFU quantities; technical plates never increase sample n."""
    rules = _rules(rules)
    _record(counts, "cfu-counts-v1", "rows")
    rows = _list(counts["rows"], "plate counts", MAX_ROWS)
    plate_rules = {row["plate_id"]: row for row in rules["plates"]}
    ranges = ({plate: {key: row[key] for key in ("minimum", "maximum")}
               for plate, row in plate_rules.items()} if countable_ranges is None else countable_ranges)
    _ranges(ranges, plate_rules)
    seen = set()
    grouped = {sample: [] for sample in rules["sample_ids"]}
    for row in rows:
        _require(type(row) is dict and "dilution_factor" in row and "volume_ml" in row,
                 "plate-exposure", "count table must preserve dilution and volume")
        _fields(row, "plate_id sample_id dilution_factor volume_ml count flag", "plate count")
        plate = _text(row["plate_id"], "plate id")
        sample = _text(row["sample_id"], "sample id")
        flag = _text(row["flag"], "plate flag")
        _require(plate not in seen, "duplicate-plate", "plate IDs must be unique")
        seen.add(plate)
        _require(plate in plate_rules and sample == plate_rules[plate]["sample_id"],
                 "sample-identity", "count table identity differs from frozen plates")
        for name in ("dilution_factor", "volume_ml"):
            _number(row[name], name, 1e-12, 100)
            _require(row[name] == plate_rules[plate][name], "plate-exposure", "exposure differs from frozen rule")
        _require(flag in {"observed", "spreader", "uncountable", "unavailable"},
                 "plate-flag", "unknown count availability flag")
        if flag != "observed":
            _require(row["count"] is None, "flagged-as-zero", "flagged or unavailable plate needs null count")
        else:
            _number(row["count"], "colony count", 0, MAX_COLONIES, True)
        grouped[sample].append(row)
    _require(seen == set(plate_rules), "missing-plate", "missing plates must be explicit unavailable rows")
    output = []
    for sample, plates in grouped.items():
        observed = [row for row in plates if row["flag"] == "observed"]
        countable = [row for row in observed if ranges[row["plate_id"]]["minimum"] <= row["count"]
                     <= ranges[row["plate_id"]]["maximum"]]
        duplicates = {}
        for row in countable:
            duplicates.setdefault((row["dilution_factor"], row["volume_ml"]), []).append(row["count"])
        for replicate_counts in duplicates.values():
            _require(max(replicate_counts) / min(replicate_counts) <= rules["duplicate_maximum_ratio"],
                     "duplicate-disagreement", "countable duplicate plates exceed frozen agreement ratio")
        included = [row["plate_id"] for row in countable]
        included_set = set(included)
        result = {"sample_id": sample, "classification": "unavailable", "included_plate_ids": included,
                  "excluded_plate_ids": [row["plate_id"] for row in plates if row["plate_id"] not in included_set],
                  "total_colonies": sum(row["count"] for row in countable),
                  "volume_equivalent_ml": math.fsum(row["volume_ml"] * row["dilution_factor"] for row in countable),
                  "cfu_per_ml": "unavailable", "log10_cfu_per_ml": "unavailable", "interval": "unavailable",
                  "lod_upper_cfu_per_ml": "unavailable", "lower_bound_cfu_per_ml": "unavailable"}
        _require(result["total_colonies"] <= MAX_COLONIES, "input-limit", "pooled colony sum exceeds reference limit")
        if countable:
            _require(len(countable) >= rules["minimum_countable_plates"],
                     "insufficient-countable", "too few countable plates under frozen minimum")
            result["classification"] = "quantified"
            result["cfu_per_ml"] = result["total_colonies"] / result["volume_equivalent_ml"]
            result["log10_cfu_per_ml"] = math.log10(result["cfu_per_ml"])
            result["interval"] = poisson_interval(result["total_colonies"], result["volume_equivalent_ml"],
                                                  rules["interval_level"])
        elif len(observed) == len(plates):
            below = all(row["count"] < ranges[row["plate_id"]]["minimum"] for row in observed)
            above = all(row["count"] > ranges[row["plate_id"]]["maximum"] for row in observed)
            _require(below or above, "no-countable-bracket", "mixed below/above plates need review, never pooling")
            if below:
                count = sum(row["count"] for row in observed)
                _require(count <= MAX_COLONIES, "input-limit", "bounding colony sum exceeds reference limit")
                exposure = math.fsum(row["volume_ml"] * row["dilution_factor"] for row in observed)
                bound = _gamma_quantile(count + 1, rules["interval_level"]) / exposure
                result["classification"] = "below-countable"
                result["lod_upper_cfu_per_ml"] = bound
                result["interval"] = {"method": "garwood-exact-one-sided", "level": rules["interval_level"],
                                      "lower": "unavailable", "upper": bound}
            else:
                bound = max(ranges[row["plate_id"]]["maximum"] / (row["volume_ml"] * row["dilution_factor"])
                            for row in observed)
                result["classification"] = "above-countable"
                result["lower_bound_cfu_per_ml"] = bound
                result["interval"] = {"method": "countable-range-bound", "level": "unavailable",
                                      "lower": bound, "upper": "unavailable"}
        output.append(result)
    quantified = [row["log10_cfu_per_ml"] for row in output if row["classification"] == "quantified"]
    summary = {"n": len(output), "quantified": len(quantified),
               "below_countable": sum(row["classification"] == "below-countable" for row in output),
               "above_countable": sum(row["classification"] == "above-countable" for row in output),
               "unavailable": sum(row["classification"] == "unavailable" for row in output),
               "mean_log10_cfu_per_ml": math.fsum(quantified) / len(quantified) if quantified else "unavailable"}
    return {"samples": output, "summary": summary}


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
        _require(len(actual) == len(expected), "countable-selection", "reported plate or sample count differs")
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


def validate_cfu_plate_count_pack(bundle):
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
        pack = _record(store.load(path.name), "cfu-pack-v1",
                       "rules frozen_rules_sha256 frozen_before_counts_read counts report evidence")
        rules = _rules(store.artifact(pack["rules"]))
        _require(_text(pack["frozen_rules_sha256"], "frozen rules hash") == pack["rules"]["sha256"]
                 and _boolean(pack["frozen_before_counts_read"], "frozen before counts read"),
                 "rule-freeze", "rules must be hash-frozen before counts are opened")
        report = store.artifact(pack["report"])
        _require("interval_method" in report and "interval_level" in report,
                 "poisson-interval", "report must retain exact interval method and level")
        _record(report, "cfu-report-v1", "rules_sha256 exploratory countable_ranges weighted_mean_rule "
                "interval_method interval_level samples summary headline claims")
        _require(_text(report["rules_sha256"], "rules hash") == pack["rules"]["sha256"],
                 "rule-freeze", "report cites a different frozen rule revision")
        exploratory = _boolean(report["exploratory"], "exploratory")
        frozen_ranges = {row["plate_id"]: {key: row[key] for key in ("minimum", "maximum")} for row in rules["plates"]}
        ranges = _ranges(report["countable_ranges"], frozen_ranges)
        _require(ranges == frozen_ranges or exploratory,
                 "post-hoc-range", "post-outcome countable range change requires exploratory label")
        _require(report["weighted_mean_rule"] == rules["weighted_mean_rule"],
                 "weighted-mean-rule", "reported averaging rule differs from frozen rule")
        _require(report["interval_method"] == rules["interval_method"],
                 "poisson-interval", "normal approximation or omitted exact interval is refused")
        _number(report["interval_level"], "reported interval level", 0.5, 0.999)
        _require(report["interval_level"] == rules["interval_level"], "poisson-interval", "interval level changed")
        headline = _text(report["headline"], "headline")
        _require(not OVERREACH.search(headline), "claim-overreach", "headline exceeds bounded synthetic arithmetic")
        descriptors = _list(pack["evidence"], "evidence artifacts", MAX_RECORDS, True)
        own_paths = {path.name}
        own_hashes = {store.snapshots[path.name][2]}
        for descriptor in (pack["rules"], pack["counts"], pack["report"], *descriptors):
            _fields(descriptor, "path sha256", "artifact identity")
            own_paths.add(str(_relative(descriptor["path"])))
            own_hashes.add(_text(descriptor["sha256"], "sha256"))
        evidence = {}
        for descriptor in descriptors:
            document = _record(store.artifact(descriptor), "cfu-evidence-v1", "records")
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
        result = compute_cfu(store.artifact(pack["counts"]), rules, ranges)
        samples = _list(report["samples"], "reported samples", MAX_SAMPLES)
        _require(len(samples) == len(result["samples"]), "sample-identity", "report omits samples")
        for actual, expected in zip(samples, result["samples"]):
            _require(type(actual) is dict and "interval" in actual, "poisson-interval", "per-sample interval omitted")
            if expected["classification"] != "quantified":
                _require(actual.get("cfu_per_ml") == "unavailable" and actual.get("log10_cfu_per_ml") == "unavailable",
                         "unavailable-as-zero", "unquantified samples cannot have point CFU estimates")
            if expected["classification"] == "below-countable":
                _require(type(actual.get("lod_upper_cfu_per_ml")) in (int, float)
                         and actual["lod_upper_cfu_per_ml"] > 0,
                         "lod-zero", "detection upper bound must be positive, never zero")
            _require(actual.get("included_plate_ids") == expected["included_plate_ids"],
                     "countable-selection", "only countable plates may enter weighted mean")
            _same(actual, expected, "sample")
        _same(report["summary"], result["summary"], "summary")
        store.finish()
        return {"schema": "cfu-result-v1", "fixture": "synthetic fixture", "status": "arithmetic-only",
                "review": "unavailable", "stages": list(STAGES), "exploratory": exploratory,
                "inputs": [{"path": name, "sha256": item[2]} for name, item in sorted(store.snapshots.items())],
                "computation": result, "claims": report["claims"],
                "limitations": ["Synthetic counts establish software arithmetic only.",
                                "Poisson independence and dilution accuracy are assumptions, not validated observations.",
                                "The detection upper bound is not a validated assay detection limit.",
                                "Hash declarations cannot establish historical freeze timing or independence.",
                                "Independent record, source and method review remains unavailable."]}
    finally:
        store.close()
