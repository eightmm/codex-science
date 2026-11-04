"""Read-only admission of synthetic LC-MS feature QC and stdlib reference arithmetic."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import statistics

STAGES = ("01-freeze", "02-table", "03-features", "04-samples", "05-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_TOTAL_NODES = 4000000
MAX_ARTIFACTS = 128
MAX_ITEMS = 20000
MAX_DEPTH = 32
MAX_STRING = 4096
MAX_NUMBER = 1e100
MAX_SAMPLES = 256
MAX_FEATURES = 1000
MAX_CELLS = 200000
MAX_WINDOW = 101
MAX_RECORDS = 128
POSITIVE = {"supported", "replicated", "suggestive"}
STATUSES = POSITIVE | {"planned", "conflicting", "unsupported", "withdrawn", "unavailable"}
WORDING_FAMILIES = (
    "caus*, mechanis*, therap*, clinic*, efficac*, effective*, treat*, cure*, prevent*, "
    "recommend*, prescri*, bind*, affinit*, inhibit*, activat*, regulat*, drive/drives/driv*, induc*"
)
OVERREACH = re.compile(
    r"\b(?:caus\w*|mechanis\w*|therap\w*|clinic\w*|efficac\w*|effective\w*|"
    r"treat\w*|cure\w*|prevent\w*|recommend\w*|prescri\w*|bind\w*|affinit\w*|"
    r"inhibit\w*|activat\w*|regulat\w*|driv\w*|induc\w*|biomarker\w*|pathway\w*|"
    r"identif\w*|compound[\s-]+identity|truth|physical[\s-]+validity)\b", re.I,
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
    _require(value["schema"] == schema and value["fixture"] == "synthetic fixture",
             "invalid-record", f"expected synthetic fixture {schema}")
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
    # Count an upper bound without building a match list or a parsed JSON tree.
    count = 1 + raw.count(b",") + sum(1 for _ in re.finditer(rb"[\[{](?=\s*[^\s\]}])", raw))
    _require(count <= allowance, "input-limit", "bundle JSON value allowance exceeded before parsing")
    try:
        root = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=_constant, parse_int=_int, parse_float=_float)
        _require(type(root) is dict, "invalid-json", "JSON root must be an object")
        pending = [(root, 0)]
        while pending:
            value, depth = pending.pop()
            _require(depth <= MAX_DEPTH, "invalid-json", "JSON nesting limit exceeded")
            if type(value) in (dict, list):
                _require(len(value) <= MAX_ITEMS, "input-limit", "JSON container exceeds limit")
                if type(value) is dict:
                    for key in value:
                        _text(key, "JSON key")
                children = value.values() if type(value) is dict else value
                pending.extend((child, depth + 1) for child in children)
            elif type(value) is str:
                _require(len(value) <= MAX_STRING and not any(0xD800 <= ord(c) <= 0xDFFF for c in value),
                         "input-limit", "JSON string exceeds limit or contains a surrogate")
        return root, count
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
    """Pin every ancestor from the filesystem root without following links."""
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
        self.total_bytes = 0
        self.total_nodes = 0
        self.rechecked = None
        try:
            self.fd, self.identities = _open_root(root)
            self._check_root()
        except (OSError, ValueError) as error:
            self.close()
            if isinstance(error, ValueError):
                raise
            raise ValueError("input-root: cannot pin bundle directory") from error

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

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
                before = os.lstat(part, dir_fd=directory)
                _require(stat.S_ISDIR(before.st_mode), "input-file", "symlinked artifact directory refused")
                directory = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
                opened_dirs.append(directory)
                actual = os.fstat(directory)
                _require(stat.S_ISDIR(actual.st_mode)
                         and (before.st_dev, before.st_ino) == (actual.st_dev, actual.st_ino),
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
                raw = handle.read(min(MAX_BYTES, actual.st_size) + 1)
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
            _require(len(self.snapshots) < MAX_ARTIFACTS, "input-limit", "too many input artifacts")
            raw, signature = self._read(name)
            identity = signature[:2]
            if identity not in self.cache:
                self.cache[identity] = (raw, signature, hashlib.sha256(raw).hexdigest())
                self.total_bytes += len(raw)
            self.snapshots[name] = self.cache[identity]
        raw, signature, actual = self.snapshots[name]
        if digest is not None:
            _require(type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
                     and digest == actual, "input-hash", "artifact hash differs from parsed bytes")
        if not parse:
            return actual
        identity = signature[:2]
        if identity not in self.parsed:
            result, count = _json(raw, MAX_TOTAL_NODES - self.total_nodes)
            self.total_nodes += count
            self.parsed[identity] = result
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
            _require(identities == self.identities, "input-root", "bundle ancestor chain replaced")
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
    _record(value, "metab-rules-v1", "blank_ratio_max qc_rsd_max study_missing_max qc_missing_max "
            "drift normalization dilution_r2_min dilution_slope_min minimum_qc minimum_dilution "
            "mz_min mz_max rt_min rt_max missing_policy sample_outlier_distance minimum_distance_features")
    for key in ("blank_ratio_max", "qc_rsd_max", "sample_outlier_distance", "dilution_slope_min"):
        _number(value[key], key, 0, 1e12)
    for key in ("study_missing_max", "qc_missing_max", "dilution_r2_min"):
        _number(value[key], key, 0, 1)
    for key, high in (("minimum_qc", MAX_SAMPLES), ("minimum_dilution", MAX_SAMPLES),
                      ("minimum_distance_features", MAX_FEATURES)):
        _number(value[key], key, 1 if key == "minimum_distance_features" else 3, high, True)
    for key in ("mz_min", "mz_max", "rt_min", "rt_max"):
        _number(value[key], key, 0, 1e12)
    _require(0 < value["mz_min"] < value["mz_max"] and value["rt_min"] < value["rt_max"],
             "invalid-record", "m/z and retention-time ranges must have positive width")
    _require(value["missing_policy"] == "preserve", "missing-imputation", "missing values must remain missing")
    _text(value["normalization"], "normalization")
    _require(value["normalization"] in {"none", "median"}, "invalid-record", "unsupported normalization")
    drift = _fields(value["drift"], "method window anchors", "drift")
    _text(drift["method"], "drift method")
    _require(drift["method"] in {"none", "running-median-qc"}, "invalid-record", "unsupported drift method")
    _require(drift["anchors"] == "pooled-qc", "study-drift-anchors", "drift anchors must be pooled QC only")
    _number(drift["window"], "drift window", 1, MAX_WINDOW, True)
    _require(drift["window"] % 2 == 1, "invalid-record", "drift window must be odd")
    return value


def _sheet(value):
    _record(value, "metab-sheet-v1", "groups samples")
    groups = _names(value["groups"], "frozen groups", 2)
    _require(len(groups) == 2, "invalid-record", "two frozen study groups required")
    rows = _list(value["samples"], "samples", MAX_SAMPLES)
    ids, orders, group_batches = set(), set(), {group: set() for group in groups}
    for row in rows:
        _fields(row, "id injection_order sample_type batch group dilution", "sample")
        identity = _text(row["id"], "sample id")
        order = _number(row["injection_order"], "injection order", 1, MAX_NUMBER, True)
        _require(identity not in ids and order not in orders, "table-identity", "sample IDs and injection orders must be unique")
        ids.add(identity)
        orders.add(order)
        kind = _text(row["sample_type"], "sample type")
        batch = _text(row["batch"], "batch")
        _require(kind in {"study", "pooled-qc", "blank", "dilution-series"}, "invalid-record", "unknown sample type")
        if kind == "study":
            group = _text(row["group"], "study group")
            _require(group in group_batches, "invalid-record", "study group absent from frozen sheet")
            group_batches[group].add(batch)
        else:
            _require(row["group"] is None, "invalid-record", "only study samples carry a group")
        if kind == "dilution-series":
            _number(row["dilution"], "dilution concentration", 1e-12, 1e12)
        else:
            _require(row["dilution"] is None, "invalid-record", "only dilution samples carry concentrations")
    _require(all(group_batches.values()), "invalid-record", "both study groups require samples")
    return rows, not bool(group_batches[groups[0]] & group_batches[groups[1]])


def relative_standard_deviation(values, minimum=3):
    """Sample SD / mean; identical positive QC values correctly yield zero RSD."""
    _number(minimum, "minimum QC count", 3, MAX_SAMPLES, True)
    values = _list(values, "QC values", MAX_SAMPLES, True)
    for value in values:
        _number(value, "QC intensity", 0, 1e12)
    _require(len(values) >= minimum and max(values) > 0, "degenerate-qc", "insufficient or zero QC signal")
    scale = max(values)
    scaled = [value / scale for value in values]
    mean = math.fsum(scaled) / len(scaled)
    return math.sqrt(math.fsum((value - mean)**2 for value in scaled) / (len(scaled) - 1)) / mean


def dilution_linearity(concentrations, values, minimum=3):
    """Scaled ordinary least-squares R-squared and slope, with degenerate data refused."""
    _number(minimum, "minimum dilution count", 3, MAX_SAMPLES, True)
    concentrations = _list(concentrations, "dilution concentrations", MAX_SAMPLES)
    values = _list(values, "dilution intensities", MAX_SAMPLES)
    _require(len(values) == len(concentrations) and len(values) >= minimum,
             "degenerate-dilution", "insufficient matched dilution points")
    for value in concentrations:
        _number(value, "dilution concentration", 1e-12, 1e12)
    for value in values:
        _number(value, "dilution intensity", 0, 1e12)
    sx, sy = max(concentrations), max(values)
    _require(sy > 0, "degenerate-dilution", "zero dilution response")
    x, y = [v / sx for v in concentrations], [v / sy for v in values]
    mx, my = math.fsum(x) / len(x), math.fsum(y) / len(y)
    xx = math.fsum((v - mx)**2 for v in x)
    yy = math.fsum((v - my)**2 for v in y)
    xy = math.fsum((a - mx) * (b - my) for a, b in zip(x, y))
    _require(xx > 0 and yy > 0, "degenerate-dilution", "zero dilution variance")
    slope = (xy / xx) * (sy / sx)
    r2 = min(1.0, (xy / math.sqrt(xx) / math.sqrt(yy))**2)
    _require(math.isfinite(slope) and math.isfinite(r2), "numerical-range", "non-finite linearity result")
    return {"r_squared": r2, "slope": slope}


def _table(value, samples, rules):
    _record(value, "metab-table-v1", "sample_ids features")
    ids = _names(value["sample_ids"], "table sample IDs", MAX_SAMPLES)
    _require(set(ids) == {row["id"] for row in samples}, "table-identity", "table and sheet samples differ")
    rows = _list(value["features"], "features", MAX_FEATURES)
    _require(len(rows) * len(ids) <= MAX_CELLS, "input-limit", "feature-by-sample cell budget exceeded")
    batches = {row["id"]: row["batch"] for row in samples}
    seen = set()
    for row in rows:
        _fields(row, "id mz retention_time values imputed unavailable_batches", "feature")
        identity = _text(row["id"], "feature id")
        _require(identity not in seen, "table-identity", "duplicate feature id")
        seen.add(identity)
        _number(row["mz"], "m/z", rules["mz_min"], rules["mz_max"])
        _number(row["retention_time"], "retention time", rules["rt_min"], rules["rt_max"])
        missing_batches = _names(row["unavailable_batches"], "unavailable batches", MAX_SAMPLES, True)
        _require(set(missing_batches) <= set(batches.values()), "invalid-record", "unknown unavailable batch")
        values = _list(row["values"], "intensities", MAX_SAMPLES)
        imputed = _list(row["imputed"], "imputation mask", MAX_SAMPLES)
        _require(len(values) == len(ids) == len(imputed), "table-identity", "feature vectors must match samples")
        for identity, intensity, replaced in zip(ids, values, imputed):
            _boolean(replaced, "imputed")
            _require(not replaced, "missing-imputation", "undeclared imputation cannot replace missing values with zero")
            if intensity is not None:
                _number(intensity, "intensity", 0, 1e12)
            _require(batches[identity] not in missing_batches or intensity is None,
                     "unavailable-absence", "unmeasured failed-batch values must be null, never zero or absent")
    return ids, rows


def compute_feature_qc(table, sheet, rules):
    """Compute preserved feature and sample records; no differential comparison is performed."""
    rules = _rules(rules)
    samples, confounded = _sheet(sheet)
    ids, features = _table(table, samples, rules)
    by_id = {row["id"]: row for row in samples}
    samples = [by_id[identity] for identity in ids]
    indices = {kind: [i for i, row in enumerate(samples) if row["sample_type"] == kind]
               for kind in ("study", "pooled-qc", "blank", "dilution-series")}
    _require(all(indices.values()), "missing-controls", "study, pooled QC, blank and dilution samples are required")
    batch_indices = {}
    for i, sample in enumerate(samples):
        batch_indices.setdefault(sample["batch"], []).append(i)
    nearest = {i: sorted((j for j in indices["pooled-qc"] if samples[j]["batch"] == sample["batch"]),
                         key=lambda j: (abs(samples[j]["injection_order"] - sample["injection_order"]),
                                        samples[j]["injection_order"])) for i, sample in enumerate(samples)}
    results, corrected_rows = [], []
    for feature in features:
        raw = feature["values"]
        corrected = list(raw)
        reasons = []
        unavailable = set(feature["unavailable_batches"])
        if unavailable:
            reasons.append("unavailable-batch")
        if rules["drift"]["method"] == "running-median-qc":
            for batch, positions in batch_indices.items():
                anchors = [j for j in indices["pooled-qc"] if samples[j]["batch"] == batch
                           and raw[j] is not None and raw[j] > 0]
                if len(anchors) < rules["minimum_qc"]:
                    reasons.append("drift-unavailable")
                    continue
                anchor_set = set(anchors)
                target = statistics.median(raw[j] for j in anchors)
                for i in positions:
                    if raw[i] is not None:
                        local = [j for j in nearest[i] if j in anchor_set][:rules["drift"]["window"]]
                        value = (raw[i] / statistics.median(raw[j] for j in local)) * target
                        _require(math.isfinite(value) and 0 <= value <= 1e12,
                                 "numerical-range", "drift-corrected intensity outside reference range")
                        corrected[i] = value
        qc = [raw[i] for i in indices["pooled-qc"] if raw[i] is not None]
        after = [corrected[i] for i in indices["pooled-qc"] if corrected[i] is not None]
        before_rsd = after_rsd = None
        try:
            before_rsd = relative_standard_deviation(qc, rules["minimum_qc"])
            after_rsd = relative_standard_deviation(after, rules["minimum_qc"])
        except ValueError as error:
            if not str(error).startswith("degenerate-qc:"):
                raise
            reasons.append("qc-degenerate")
        if after_rsd is not None and after_rsd > rules["qc_rsd_max"]:
            reasons.append("qc-rsd")
        blanks = [raw[i] for i in indices["blank"] if raw[i] is not None]
        ratio = None
        if blanks and qc and math.fsum(qc) > 0:
            ratio = (math.fsum(blanks) / len(blanks)) / (math.fsum(qc) / len(qc))
            _require(math.isfinite(ratio), "numerical-range", "blank ratio outside finite range")
            if ratio > rules["blank_ratio_max"]:
                reasons.append("blank-ratio")
        else:
            reasons.append("blank-unavailable")
        study_missing = sum(raw[i] is None for i in indices["study"]) / len(indices["study"])
        qc_missing = sum(raw[i] is None for i in indices["pooled-qc"]) / len(indices["pooled-qc"])
        if study_missing > rules["study_missing_max"]:
            reasons.append("study-missingness")
        if qc_missing > rules["qc_missing_max"]:
            reasons.append("qc-missingness")
        dilution_positions = [i for i in indices["dilution-series"] if corrected[i] is not None]
        linearity = None
        try:
            _require(len(dilution_positions) >= rules["minimum_dilution"],
                     "degenerate-dilution", "insufficient observed dilution points")
            linearity = dilution_linearity([samples[i]["dilution"] for i in dilution_positions],
                                          [corrected[i] for i in dilution_positions], rules["minimum_dilution"])
        except ValueError as error:
            if not str(error).startswith("degenerate-dilution:"):
                raise
            reasons.append("dilution-degenerate")
        if linearity is not None and (linearity["r_squared"] < rules["dilution_r2_min"]
                                     or linearity["slope"] <= 0 or linearity["slope"] < rules["dilution_slope_min"]):
            reasons.append("dilution-linearity")
        reasons = sorted(set(reasons))
        results.append({"id": feature["id"], "mz": feature["mz"], "retention_time": feature["retention_time"],
                        "status": "unavailable" if unavailable else "fail" if reasons else "pass",
                        "retained": not reasons, "reasons": reasons, "blank_ratio": ratio,
                        "qc_rsd_before": before_rsd, "qc_rsd_after": after_rsd,
                        "study_missingness": study_missing, "qc_missingness": qc_missing,
                        "dilution": linearity, "corrected": corrected})
        corrected_rows.append(corrected)
    medians = [statistics.median(values) if values else None for values in
               ([row[i] for row in corrected_rows if row[i] is not None and row[i] > 0] for i in range(len(ids)))]
    factors = [1.0] * len(ids)
    if rules["normalization"] == "median":
        _require(all(value is not None and value > 0 for value in medians),
                 "normalization-unavailable", "median normalization requires observed positive sample signal")
        target = statistics.median(medians)
        factors = [target / value for value in medians]
        _require(all(math.isfinite(value) and value > 0 for value in factors),
                 "numerical-range", "non-finite normalization factor")
    for row in results:
        row["normalized"] = [None if value is None else value * factors[i] for i, value in enumerate(row["corrected"])]
        _require(all(value is None or math.isfinite(value) and 0 <= value <= 1e12 for value in row["normalized"]),
                 "numerical-range", "normalized intensity outside reference range")
    kept = [row for row in results if row["retained"]]
    centers = {}
    for batch in batch_indices:
        qc_positions = [i for i in indices["pooled-qc"] if samples[i]["batch"] == batch]
        centers[batch] = []
        for row in kept:
            values = [math.log1p(row["normalized"][i]) for i in qc_positions if row["normalized"][i] is not None]
            centers[batch].append(statistics.median(values) if len(values) >= rules["minimum_qc"] else None)
    sample_results = []
    for i, sample in enumerate(samples):
        values = [row["normalized"][i] for row in results if row["normalized"][i] is not None]
        squares = [(math.log1p(row["normalized"][i]) - center)**2
                   for row, center in zip(kept, centers[sample["batch"]])
                   if center is not None and row["normalized"][i] is not None]
        distance = math.sqrt(math.fsum(squares)) if len(squares) >= rules["minimum_distance_features"] else None
        flags = ["distance-unavailable"] if distance is None else ["qc-distance-outlier"] if distance > rules["sample_outlier_distance"] else []
        sample_results.append({"id": sample["id"], "median_intensity": statistics.median(values) if values else None,
                               "qc_log_distance": distance, "distance_features": len(squares), "flags": flags})
    return {"features": results, "samples": sample_results, "normalization_factors": factors,
            "retained_feature_count": len(kept), "reason_counts": dict(sorted(Counter(reason for row in results for reason in row["reasons"]).items())),
            "batch_confounded": confounded}


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
                 "claim-overreach", "feature QC cannot establish identity, biomarkers, pathways or physical validity")
        _require(status in STATUSES, "invalid-record", "unknown claim status")
        ids = _names(claim["evidence"], "claim evidence", MAX_RECORDS, True)
        _require(ids or status == "unavailable", "missing-evidence", "empty evidence requires unavailable")
        _require(status != "unavailable" or not ASSERTION.search(text),
                 "unavailable-positive", "unavailable claim asserts positive evidence")
        for identity in ids:
            _require(identity in evidence, "missing-evidence", "unknown evidence identity")
            record = evidence[identity]
            _require("unavailable" not in (record["kind"].casefold(), record["result"].casefold()) or status == "unavailable",
                     "unavailable-evidence", "unavailable sources require an unavailable claim")
            _require(status not in POSITIVE or not any(NON_EVIDENCE.search(record[key]) for key in ("kind", "result")),
                     "non-evidence-support", "review approval and computed records are not positive evidence")
        _require(status != "replicated", "claim-replication", "one synthetic bundle cannot establish independent replication")


def _validate(store, entry):
    pack = _record(store.load(entry), "metab-pack-v1", "frozen_rules rules sheet table report evidence "
                   "frozen_rules_sha256 frozen_sheet_sha256 frozen_before_table_read stages")
    _require(_names(pack["stages"], "stage IDs", len(STAGES)) == list(STAGES), "stage-order", "ordered stage IDs required")
    frozen = _rules(store.artifact(pack["frozen_rules"]))
    rules = _rules(store.artifact(pack["rules"]))
    sheet = store.artifact(pack["sheet"])
    _sheet(sheet)
    _require(_text(pack["frozen_rules_sha256"], "frozen rules hash") == pack["frozen_rules"]["sha256"]
             and _text(pack["frozen_sheet_sha256"], "frozen sheet hash") == pack["sheet"]["sha256"]
             and _boolean(pack["frozen_before_table_read"], "frozen before table read"),
             "rule-freeze", "rules and sheet must be hash-frozen before the table is read")
    report = _record(store.artifact(pack["report"]), "metab-report-v1", "rules_sha256 exploratory rsd_population "
                     "drift_anchors features samples batch_confounded headline claims")
    exploratory = _boolean(report["exploratory"], "exploratory")
    _require(frozen == rules or exploratory, "post-hoc-rules", "changed rules require an exploratory label")
    _require(_text(report["rules_sha256"], "report rules hash") == pack["rules"]["sha256"],
             "rule-freeze", "report must bind the rules used")
    _require(report["rsd_population"] == "pooled-qc", "study-rsd", "RSD must be computed on pooled QC, never study samples")
    _require(report["drift_anchors"] == "pooled-qc", "study-drift-anchors", "drift anchors must be pooled QC only")
    headline = _text(report["headline"], "headline")
    _require(not OVERREACH.search(headline), "claim-overreach", "headline exceeds offline feature QC")
    result = compute_feature_qc(store.artifact(pack["table"]), sheet, rules)
    _require(_boolean(report["batch_confounded"], "batch confounded") == result["batch_confounded"],
             "batch-confounding", "confounding of batch with the frozen study group must be flagged")
    rows = _list(report["features"], "reported features", MAX_FEATURES, True)
    actual = {row["id"]: row for row in result["features"]}
    seen = set()
    for row in rows:
        _fields(row, "id retained reasons status", "reported feature")
        identity = _text(row["id"], "reported feature id")
        _require(identity in actual and identity not in seen, "feature-accounting", "unknown or duplicate reported feature")
        seen.add(identity)
        expected = actual[identity]
        status = _text(row["status"], "reported feature status")
        _require(expected["status"] != "unavailable" or status == "unavailable",
                 "unavailable-absence", "unmeasured features must be unavailable, never absent")
        retained = _boolean(row["retained"], "retained")
        reasons = _names(row["reasons"], "feature reasons", MAX_RECORDS, True)
        _require(not retained or "blank-ratio" not in expected["reasons"],
                 "blank-contamination", "blank-contaminated features cannot be retained")
        _require(reasons == expected["reasons"] and retained == expected["retained"] and status == expected["status"],
                 "feature-accounting", "feature decisions require every computed named reason")
    _require(seen == set(actual), "feature-accounting", "no feature may silently disappear")
    rows = _list(report["samples"], "reported samples", MAX_SAMPLES, True)
    actual = {row["id"]: row["flags"] for row in result["samples"]}
    seen = set()
    for row in rows:
        _fields(row, "id flags", "reported sample")
        identity = _text(row["id"], "reported sample id")
        flags = _names(row["flags"], "sample flags", MAX_RECORDS, True)
        _require(identity in actual and identity not in seen and flags == actual[identity],
                 "sample-preservation", "all samples and their outlier flags must be preserved")
        seen.add(identity)
    _require(seen == set(actual), "sample-preservation", "flagged samples must remain in the table")
    descriptors = _list(pack["evidence"], "evidence artifacts", MAX_RECORDS, True)
    own_paths = {entry}
    own_hashes = {store.snapshots[entry][2]}
    for descriptor in (pack["frozen_rules"], pack["rules"], pack["sheet"], pack["table"], pack["report"], *descriptors):
        _fields(descriptor, "path sha256", "artifact identity")
        own_paths.add(str(_relative(descriptor["path"])))
        own_hashes.add(_text(descriptor["sha256"], "sha256"))
    evidence = {}
    for descriptor in descriptors:
        document = _record(store.artifact(descriptor), "metab-evidence-v1", "records")
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
                         "external-alias", "external independence label aliases study output")
            evidence[identity] = record
    _claims(report["claims"], evidence)
    store.finish()
    return {"schema": "metab-result-v1", "fixture": "synthetic fixture", "status": "offline-arithmetic-only",
            "review": "unavailable", "stages": list(STAGES), "exploratory": exploratory,
            "inputs": [{"path": name, "sha256": item[2]} for name, item in sorted(store.snapshots.items())],
            "computation": result, "claims": report["claims"],
            "limitations": ["Synthetic arithmetic agreement establishes software behavior only.",
                            "Hashes cannot prove historical freezing or actual independence.",
                            "The conservative English lexical claim gate is incomplete.",
                            "Independent review and rigor classification remain coordinator-owned and unavailable."]}


def validate_metabolomics_feature_qc_pack(bundle):
    """Validate one immutable fixture bundle, return JSON-compatible results, write nothing."""
    try:
        value = _text(os.fspath(bundle), "bundle path")
        _require(all(ord(c) >= 32 for c in value), "input-path", "control character in bundle path")
        path = Path(os.path.abspath(value))
        with _Bundle(path.parent) as store:
            return _validate(store, path.name)
    except (OSError, UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError("input-file: bounded readable bundle required") from error
    except TypeError as error:
        raise ValueError("invalid-record: invalid bundle value type") from error
