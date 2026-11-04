"""Immutable offline batch-structure admission and bounded reference arithmetic."""
from __future__ import annotations

from datetime import datetime
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import random
import re
import stat
import statistics


STAGES = ("01-rule-freeze", "02-matrix-qc", "03-metrics", "04-summary", "05-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_TOTAL_NODES = 4000000
MAX_ARTIFACTS = 128
MAX_DEPTH = 32
MAX_TEXT = 4096
MAX_ITEMS = 20000
MAX_SAMPLES = 128
MAX_FEATURES = 256
MAX_COVARIATES = 8
MAX_VALUES = 32768
MAX_PERMUTATIONS = 999
MAX_METRIC_WORK = 8000000
MAX_CLAIMS = 100
MAX_SUPPORT = 100
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
    r"physical[\s-]+validity|biological[\s-]+signal|differential[\s-]+expression|"
    r"correct\w*|remov\w*)\b", re.I,
)
ASSERTION = re.compile(r"\b(?:supported|replicated|suggestive|significan\w*)\b", re.I)
NON_EVIDENCE = re.compile(r"review|approv|comput|numer|arithmet|result-v1|agreement|truth|physical|clinic", re.I)


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
    _require(len(value) <= limit, "input-limit", f"{label} exceeds its declared count limit")
    _require(empty or bool(value), "invalid-record", f"{label} must not be empty")
    return value


def _names(value, label, limit, empty=False):
    value = _items(value, label, limit, empty)
    for item in value:
        _text(item, label)
    _require(len(set(value)) == len(value), "duplicate-identity", f"duplicate {label}")
    return value


def _record(value, schema, fields):
    _fields(value, "schema schema_version fixture " + fields, schema)
    _require(value["schema"] == schema, "invalid-record", "wrong pack-local schema")
    _number(value["schema_version"], "schema_version", 1, 1, integer=True)
    _boolean(value["fixture"], "fixture")
    return value


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "invalid-json", "duplicate JSON key")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("invalid-json: non-finite JSON number")


def _integer(value):
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
    # Count without allocating a match list before the bundle-wide allowance.
    upper = 1 + raw.count(b",") + sum(1 for _ in re.finditer(rb"[\[{](?=\s*[^\s\]}])", raw))
    _require(upper <= allowance, "input-limit", "aggregate JSON value allowance exceeded")
    try:
        root = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=_constant, parse_int=_integer, parse_float=_float)
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
                _require(len(value) <= MAX_TEXT, "input-limit", "JSON string exceeds limit")
                if value:
                    _text(value, "JSON text")
        return root, upper
    except (UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError("invalid-json: bounded finite UTF-8 object required") from error
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
    """Pin every ancestor using relative descriptor opens and retain the identity chain."""
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
        self.total_nodes = 0
        self.rechecked = None
        self.fd, self.identities = _open_root(root)

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def _read(self, name):
        relative = _relative(name)
        directories = []
        try:
            directory = self.fd
            flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
            for part in relative.parts[:-1]:
                before = os.lstat(part, dir_fd=directory)
                _require(stat.S_ISDIR(before.st_mode), "input-file", "symlinked artifact component")
                child = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
                directories.append(child)
                actual = os.fstat(child)
                _require((actual.st_dev, actual.st_ino) == (before.st_dev, before.st_ino),
                         "input-changed", "artifact directory replaced")
                directory = child
            before = os.lstat(relative.name, dir_fd=directory)
            _require(stat.S_ISREG(before.st_mode) and before.st_size <= MAX_BYTES,
                     "input-file", "regular input at most 64 MiB required")
            descriptor = os.open(relative.name, flags, dir_fd=directory)
            with os.fdopen(descriptor, "rb") as handle:
                actual = os.fstat(handle.fileno())
                _require(stat.S_ISREG(actual.st_mode) and actual.st_size <= MAX_BYTES
                         and _signature(actual) == _signature(before),
                         "input-file", "input replaced before descriptor validation")
                signature = _signature(actual)
                identity = signature[:2]
                cached = self.cache.get(identity)
                if self.rechecked is not None:
                    _require(signature == self.snapshots[name][1], "input-changed", "input replaced")
                if cached is not None:
                    _require(signature == cached[1], "input-changed", "cached input changed")
                    if self.rechecked is None or identity in self.rechecked:
                        return cached[0], signature
                else:
                    _require(len(self.cache) < MAX_ARTIFACTS, "input-limit", "artifact count exceeds limit")
                    _require(self.total_bytes + actual.st_size <= MAX_TOTAL_BYTES,
                             "input-limit", "aggregate input bytes exceed 256 MiB")
                raw = handle.read(actual.st_size + 1)
                after = os.fstat(handle.fileno())
            _require(len(raw) == actual.st_size and _signature(actual) == _signature(after),
                     "input-changed", "input grew or changed during bounded read")
            return raw, signature
        except OSError as error:
            raise ValueError("input-file: unavailable input or symlinked component") from error
        finally:
            for descriptor in reversed(directories):
                os.close(descriptor)

    def load(self, name, digest=None):
        _relative(name)
        if name not in self.snapshots:
            raw, signature = self._read(name)
            identity = signature[:2]
            if identity not in self.cache:
                record, count = _json(raw, MAX_TOTAL_NODES - self.total_nodes)
                self.cache[identity] = (raw, signature, hashlib.sha256(raw).hexdigest(), record)
                self.total_bytes += len(raw)
                self.total_nodes += count
            self.snapshots[name] = self.cache[identity]
        _, _, actual, record = self.snapshots[name]
        if digest is not None:
            _require(type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
                     and digest == actual, "input-hash", "hash differs from parsed bytes")
        return record

    def artifact(self, identity):
        _fields(identity, "path sha256", "artifact identity")
        _require(type(identity["sha256"]) is str
                 and re.fullmatch(r"[0-9a-f]{64}", identity["sha256"]) is not None,
                 "input-hash", "lowercase SHA-256 required")
        return self.load(identity["path"], identity["sha256"])

    def _check_root(self):
        descriptor, identities = _open_root(self.root)
        try:
            _require(identities == self.identities, "input-root", "bundle ancestor chain replaced")
        finally:
            os.close(descriptor)

    def finish(self):
        self._check_root()
        self.rechecked = set()
        try:
            for name, (_, signature, digest, _) in self.snapshots.items():
                raw, current = self._read(name)
                _require(current == signature and hashlib.sha256(raw).hexdigest() == digest,
                         "input-changed", "input hash changed during validation")
                self.rechecked.add(current[:2])
            self._check_root()
        finally:
            self.rechecked = None


def _time(value):
    try:
        result = datetime.fromisoformat(_text(value, "time").replace("Z", "+00:00"))
        _require(result.tzinfo is not None, "rule-freeze", "timezone required")
        return result
    except ValueError as error:
        raise ValueError("rule-freeze: valid timezone-aware timestamp required") from error


def _rules(record):
    _record(record, "batch-effect-rules-v1", "samples covariates confounding_rule feature_filter "
            "transformation minimum_samples thresholds permutations thresholds_changed_after_outcomes exploratory")
    covariates = _names(record["covariates"], "covariates", MAX_COVARIATES, empty=True)
    _require(record["confounding_rule"] == "group-single-batch-or-rank-deficient",
             "confounding-rule", "the fixed confounding rule is required")
    feature_filter = _fields(record["feature_filter"], "method uses_group_labels frozen", "feature filter")
    uses_group = _boolean(feature_filter["uses_group_labels"], "uses_group_labels")
    frozen = _boolean(feature_filter["frozen"], "feature filter frozen")
    _require(not uses_group and frozen and feature_filter["method"] == "complete-nonconstant",
             "feature-filter", "reference filter must be frozen and independent of group labels")
    transformation = _text(record["transformation"], "transformation")
    _require(transformation in {"identity", "log2p1"}, "transformation", "identity or log2p1 required")
    _number(record["minimum_samples"], "minimum_samples", 4, MAX_SAMPLES, integer=True)
    thresholds = _fields(record["thresholds"], "median_batch_r2 batch_silhouette permutation_alpha qc_dispersion", "thresholds")
    _number(thresholds["median_batch_r2"], "median_batch_r2", 0, 1)
    _number(thresholds["batch_silhouette"], "batch_silhouette", -1, 1)
    _number(thresholds["permutation_alpha"], "permutation_alpha", 0, 1)
    _number(thresholds["qc_dispersion"], "qc_dispersion", 0, 1e100)
    permutations = _fields(record["permutations"], "seed count strata minimum_success_fraction", "permutations")
    _number(permutations["seed"], "seed", 0, 2**32 - 1, integer=True)
    _number(permutations["count"], "count", 1, MAX_PERMUTATIONS, integer=True)
    _number(permutations["minimum_success_fraction"], "minimum_success_fraction", 0, 1)
    _require(permutations["minimum_success_fraction"] > 0, "permutation-success", "positive success fraction required")
    _require(_text(permutations["strata"], "strata") == "group",
             "permutation-strata", "batch labels must be permuted only within group strata")
    changed = _boolean(record["thresholds_changed_after_outcomes"], "thresholds_changed_after_outcomes")
    exploratory = _boolean(record["exploratory"], "exploratory")
    _require(not changed or exploratory, "post-outcome-threshold", "changed thresholds require an exploratory label")
    samples = _items(record["samples"], "samples", MAX_SAMPLES)
    seen = set()
    replicates = {}
    for row in samples:
        _fields(row, "id batch group covariates qc replicate available reason", "sample sheet row")
        name = _text(row["id"], "sample id")
        _require(name not in seen, "duplicate-identity", "duplicate sample sheet id")
        seen.add(name)
        available = _boolean(row["available"], "available")
        _boolean(row["qc"], "qc")
        _require(type(row["covariates"]) is dict, "invalid-record", "sample covariates must be an object")
        if not available:
            _text(row["reason"], "unavailable sample reason")
            _require(row["batch"] is None and row["group"] is None and not row["covariates"]
                     and row["replicate"] is None and not row["qc"],
                     "unavailable-batch", "unavailable samples cannot define a batch, group or QC replicate")
            continue
        _text(row["batch"], "batch")
        _text(row["group"], "group")
        _require(row["reason"] is None, "sample-drop", "available samples must not have an exclusion reason")
        _require(set(row["covariates"]) == set(covariates), "covariates", "every declared covariate is required")
        for value in row["covariates"].values():
            _number(value, "covariate", -1e12, 1e12)
        if row["replicate"] is not None:
            replicate = _text(row["replicate"], "replicate")
            _require(replicate not in replicates or replicates[replicate] == row["group"],
                     "replicate-definition", "a technical replicate cannot cross biological groups")
            replicates[replicate] = row["group"]
    return record


def _rank(rows):
    """Exact elimination of decimal input values; no floating tolerance decides rank."""
    matrix = [[Fraction(str(value)) for value in row] for row in rows]
    rank = 0
    for column in range(len(matrix[0])):
        pivot = next((i for i in range(rank, len(matrix)) if matrix[i][column]), None)
        if pivot is None:
            continue
        matrix[rank], matrix[pivot] = matrix[pivot], matrix[rank]
        pivot_value = matrix[rank][column]
        matrix[rank] = [value / pivot_value for value in matrix[rank]]
        for i in range(rank + 1, len(matrix)):
            factor = matrix[i][column]
            if factor:
                matrix[i] = [a - factor * b for a, b in zip(matrix[i], matrix[rank])]
        rank += 1
        if rank == len(matrix):
            break
    return rank


def _confounding(samples, covariates):
    batches = sorted({row["batch"] for row in samples})
    groups = sorted({row["group"] for row in samples})
    _require(len(batches) >= 2 and len(groups) >= 2, "design-levels", "at least two batches and groups required")
    design = [[1, *(int(row["batch"] == batch) for batch in batches[1:]),
               *(int(row["group"] == group) for group in groups[1:]),
               *(row["covariates"][key] for key in covariates)] for row in samples]
    rank = _rank(design)
    single = [group for group in groups if len({row["batch"] for row in samples if row["group"] == group}) == 1]
    columns = len(design[0])
    return {"confounded": bool(single) or rank < columns, "rank": rank,
            "columns": columns, "single_batch_groups": single}


def _partition(labels):
    result = {}
    for index, label in enumerate(labels):
        result.setdefault(label, []).append(index)
    return list(result.values())


def _sums(values, partition):
    center = math.fsum(values) / len(values)
    means = [math.fsum(values[i] for i in group) / len(group) for group in partition]
    between = math.fsum(len(group) * (mean - center)**2 for group, mean in zip(partition, means))
    within = math.fsum((values[i] - mean)**2 for group, mean in zip(partition, means) for i in group)
    return between, within


def _anova(values, partition):
    scale = max(abs(value) for value in values)
    _require(scale > 0, "degenerate-data", "zero-variance feature")
    values = [value / scale for value in values]
    between, within = _sums(values, partition)
    _require(within > 0 and between + within > 0 and len(values) > len(partition),
             "degenerate-data", "finite one-way F requires residual variance and degrees of freedom")
    f_value = (between / within) * ((len(values) - len(partition)) / (len(partition) - 1))
    _require(math.isfinite(f_value), "degenerate-data", "one-way F exceeds finite precision")
    return {"r_squared": between / math.fsum((between, within)), "f": f_value}


def _pseudo(features, partition, code="degenerate-data"):
    sums = [_sums(values, partition) for values in features]
    between = math.fsum(pair[0] for pair in sums)
    within = math.fsum(pair[1] for pair in sums)
    n = len(features[0])
    _require(within > 0 and n > len(partition), code, "pseudo-F requires residual distance variance")
    result = (between / within) * ((n - len(partition)) / (len(partition) - 1))
    _require(math.isfinite(result), code, "pseudo-F exceeds finite precision")
    return result


def _distance(a, b):
    return math.sqrt(math.fsum((x - y)**2 for x, y in zip(a, b)))


def _silhouette(points, partition):
    centers = [[math.fsum(points[i][j] for i in group) / len(group)
                for j in range(len(points[0]))] for group in partition]
    scores = []
    for label, group in enumerate(partition):
        for i in group:
            a = _distance(points[i], centers[label])
            b = min(_distance(points[i], center) for other, center in enumerate(centers) if other != label)
            scores.append((b - a) / max(a, b) if max(a, b) > 0 else 0.0)
    return math.fsum(scores) / len(scores)


def _permutation_labels(labels, strata, generator):
    result = list(labels)
    for indices in strata:
        shuffled = [labels[i] for i in indices]
        generator.shuffle(shuffled)
        for i, value in zip(indices, shuffled):
            result[i] = value
    return result


def reference_computation(rules, matrix):
    """Compute unadjusted technical metrics, never correction or biological inference."""
    rules = _rules(rules)
    _record(matrix, "batch-effect-matrix-v1", "samples features values")
    names = _names(matrix["samples"], "matrix samples", MAX_SAMPLES)
    features = _names(matrix["features"], "features", MAX_FEATURES)
    _require(len(names) * len(features) <= MAX_VALUES, "input-limit", "matrix value count exceeds limit")
    _require(len(names) * len(features) * rules["permutations"]["count"] <= MAX_METRIC_WORK,
             "input-limit", "permutation arithmetic exceeds work limit")
    values = _items(matrix["values"], "feature rows", MAX_FEATURES)
    _require(len(values) == len(features), "matrix-shape", "one numeric row per feature required")
    sheet = {row["id"]: row for row in rules["samples"]}
    _require(all(name in sheet for name in names), "sample-coverage", "sample sheet must cover every matrix column")
    _require(all(sheet[name]["available"] for name in names), "unavailable-batch", "unavailable sample cannot count in the matrix")
    _require({row["id"] for row in rules["samples"] if row["available"]} == set(names),
             "sample-drop", "samples cannot be dropped without a named unavailable reason")
    _require(len(names) >= rules["minimum_samples"], "insufficient-samples", "sample count below frozen minimum")
    samples = [sheet[name] for name in names]
    confounding = _confounding(samples, rules["covariates"])
    filtered = []
    missing = {}
    retained = []
    for feature, row in zip(features, values):
        _items(row, "feature values", MAX_SAMPLES)
        _require(len(row) == len(names), "matrix-shape", "feature row width differs from sample count")
        for value in row:
            if value is not None:
                _number(value, "matrix value")
        count = sum(value is None for value in row)
        missing[feature] = count
        if count:
            filtered.append({"feature": feature, "reason": "missing-values", "missing": count})
            continue
        if rules["transformation"] == "log2p1":
            _require(all(value >= 0 for value in row), "transformation", "log2p1 requires nonnegative observed values")
            row = [math.log1p(value) / math.log(2) for value in row]
        if max(row) == min(row):
            filtered.append({"feature": feature, "reason": "zero-variance", "missing": 0})
            continue
        retained.append((feature, row))
    _require(bool(retained), "degenerate-data", "no complete nonconstant features remain")
    base = {"confounding": confounding, "missing_counts": missing, "filtered_features": filtered,
            "retained_features": [name for name, _ in retained],
            "unavailable_samples": [{"id": row["id"], "reason": row["reason"]}
                                    for row in rules["samples"] if not row["available"]],
            "sample_count": len(names), "exploratory": rules["exploratory"]}
    if confounding["confounded"]:
        return dict(base, status="unassessable", metrics=None, failed_controls=["confounded-design"])
    batch_labels = [row["batch"] for row in samples]
    batch_partition = _partition(batch_labels)
    group_partition = _partition([row["group"] for row in samples])
    _require(all(len(group) >= 2 for group in batch_partition + group_partition),
             "insufficient-samples", "every batch and group requires at least two samples")
    per_feature = [{"feature": name, "batch": _anova(row, batch_partition), "group": _anova(row, group_partition)}
                   for name, row in retained]
    # One common scale preserves Euclidean geometry while avoiding overflow/underflow.
    scale = max(abs(value) for _, row in retained for value in row)
    scaled = [[value / scale for value in row] for _, row in retained]
    points = list(map(list, zip(*scaled)))
    observed = _pseudo(scaled, batch_partition)
    generator = random.Random(rules["permutations"]["seed"])
    count = rules["permutations"]["count"]
    exceedances = failed = 0
    for _ in range(count):
        permuted = _permutation_labels(batch_labels, group_partition, generator)
        try:
            value = _pseudo(scaled, _partition(permuted), "permutation-degenerate")
        except ValueError as error:
            if not str(error).startswith("permutation-degenerate:"):
                raise
            failed += 1
            continue
        exceedances += value > observed or math.isclose(value, observed, rel_tol=1e-9, abs_tol=0.0)
    _require((count - failed) / count >= rules["permutations"]["minimum_success_fraction"],
             "permutation-success", "too few successful stratified permutations")
    p_value = (1 + exceedances + failed) / (count + 1)
    qc_indices = [i for i, row in enumerate(samples) if row["qc"]]
    distances = [_distance(points[i], points[j]) * scale for offset, i in enumerate(qc_indices)
                 for j in qc_indices[offset + 1:] if batch_labels[i] != batch_labels[j]]
    qc = {"status": "available" if distances else "unavailable", "pairs": len(distances),
          "rms_distance": math.sqrt(math.fsum((value / scale)**2 for value in distances) / len(distances)) * scale if distances else None,
          "distance_sd": statistics.pstdev(distances) if distances else None}
    median_batch = statistics.median(row["batch"]["r_squared"] for row in per_feature)
    batch_silhouette = _silhouette(points, batch_partition)
    thresholds = rules["thresholds"]
    failed_controls = []
    if qc["rms_distance"] is not None and qc["rms_distance"] > thresholds["qc_dispersion"]:
        failed_controls.append("qc-dispersion")
    detected = median_batch >= thresholds["median_batch_r2"] and batch_silhouette >= thresholds["batch_silhouette"] and p_value <= thresholds["permutation_alpha"]
    metrics = {"per_feature": per_feature, "median_batch_r2": median_batch,
               "median_group_r2": statistics.median(row["group"]["r_squared"] for row in per_feature),
               "batch_silhouette": batch_silhouette, "group_silhouette": _silhouette(points, group_partition),
               "batch_permanova": {"pseudo_f": observed, "p_value": p_value, "seed": rules["permutations"]["seed"],
                                    "count": count, "successful": count - failed, "strata": "group"},
               "qc_dispersion": qc}
    status = "unassessable" if failed_controls else "batch-structure-detected" if detected else "not-detected"
    return dict(base, status=status, metrics=metrics, failed_controls=failed_controls)


def _evidence(record):
    _record(record, "batch-effect-evidence-v1", "kind result")
    return _text(record["kind"], "evidence kind"), _text(record["result"], "evidence result")


def _claims(bundle, records, own, confounded):
    records = _items(records, "claims", MAX_CLAIMS, empty=True)
    seen = set()
    for claim in records:
        _fields(claim, "id kind status text support", "claim")
        name = _text(claim["id"], "claim id")
        _require(name not in seen, "duplicate-identity", "duplicate claim id")
        seen.add(name)
        status = _text(claim["status"], "claim status")
        kind = _text(claim["kind"], "claim kind")
        text = _text(claim["text"], "claim text")
        _require(status in STATUSES, "invalid-record", "unknown claim status")
        _require(re.search(r"\bgroup[\s-]+adjust\w*\b", text, re.I) is None,
                 "group-adjustment", "this reference cannot support group-adjusted claims")
        if confounded:
            _require(re.search(r"\b(?:no[\s-]+batch|absen\w*|not[\s-]+detect\w*)\b", text, re.I) is None,
                     "confounded-absence", "confounded design cannot support absent-batch wording")
        _require(kind in {"descriptive", "associational"} and OVERREACH.search(text) is None,
                 "claim-boundary", "only bounded technical descriptive or associational claims are admitted")
        support = _items(claim["support"], "claim support", MAX_SUPPORT, empty=True)
        _require(bool(support) or status == "unavailable", "claim-support", "empty evidence requires unavailable status")
        if status == "unavailable":
            _require(ASSERTION.search(text) is None, "unavailable-positive", "unavailable text cannot assert positive evidence")
        for identity in support:
            _fields(identity, "path sha256 origin", "claim support")
            origin = _text(identity["origin"], "origin")
            _require(origin in {"study", "external", "independent", "preregistered"}, "invalid-record", "unknown evidence origin")
            plain = {key: identity[key] for key in ("path", "sha256")}
            if origin != "study":
                _require(not any(identity["path"] == item["path"] or identity["sha256"] == item["sha256"] for item in own),
                         "evidence-independence", "outside evidence aliases a study input or output")
            evidence = bundle.artifact(plain)
            evidence_kind, result = _evidence(evidence)
            _require("unavailable" not in (evidence_kind, result) or status == "unavailable",
                     "unavailable-evidence", "any unavailable citation requires unavailable claim status")
            if status in POSITIVE:
                _require(NON_EVIDENCE.search(evidence_kind) is None and NON_EVIDENCE.search(result) is None,
                         "non-evidence", "review approval and computed agreement cannot support a positive claim")
                _require(evidence_kind == "observed-technical-record" and result == "batch-structure",
                         "non-evidence", "positive evidence requires an observed technical record")
        _require(status != "replicated", "claim-replication", "a single synthetic table cannot establish independent replication")
    return records


def validate_batch_effect_assessment_pack(path):
    """Read one pack JSON relative to a pinned root; return JSON and write nothing."""
    bundle = None
    try:
        path = Path(os.path.abspath(path))
        bundle = _Bundle(path.parent)
        pack = bundle.load(path.name)
        _record(pack, "batch-effect-pack-v1", "stages inputs frozen_rules_sha256 freeze_before_matrix "
                "frozen_at matrix_read_at study_outputs claims status group_adjusted")
        _require(pack["stages"] == list(STAGES), "stage-order", "exactly five ordered stages required")
        inputs = _fields(pack["inputs"], "rules matrix", "inputs")
        rules = _rules(bundle.artifact(inputs["rules"]))
        _require(_boolean(pack["freeze_before_matrix"], "freeze_before_matrix")
                 and pack["frozen_rules_sha256"] == inputs["rules"]["sha256"]
                 and _time(pack["frozen_at"]) < _time(pack["matrix_read_at"]),
                 "rule-freeze", "rules must be hash-frozen before the matrix is opened")
        result = reference_computation(rules, bundle.artifact(inputs["matrix"]))
        status = _text(pack["status"], "status")
        adjusted = _boolean(pack["group_adjusted"], "group_adjusted")
        if result["confounding"]["confounded"]:
            _require(status == "unassessable", "confounded-absence", "confounded design must remain unassessable")
        _require(not adjusted, "group-adjustment", "one-way metrics and stratification do not establish group-adjusted attribution")
        _require(status == result["status"], "summary-mismatch", "declared summary differs from frozen numerical controls")
        outputs = _items(pack["study_outputs"], "study outputs", MAX_SUPPORT, empty=True)
        for identity in outputs:
            _evidence(bundle.artifact(identity))
        own = [*inputs.values(), *outputs, {"path": path.name, "sha256": bundle.snapshots[path.name][2]}]
        claims = _claims(bundle, pack["claims"], own, result["confounding"]["confounded"])
        bundle.finish()
        return {"schema": "batch-effect-result-v1", "schema_version": 1, "fixture": pack["fixture"],
                "stages": list(STAGES), "evidence_level": "arithmetic-only", "review": "unavailable",
                "input_identities": [{"path": name, "sha256": record[2]} for name, record in sorted(bundle.snapshots.items())],
                "rules_sha256": pack["frozen_rules_sha256"], "assessment": result, "claims": claims,
                "limitations": ["Synthetic fixtures establish software behavior only." if pack["fixture"] else "Supplied matrix; source authenticity is unverified.",
                                "Hash and timestamp declarations cannot prove historical freeze timing or independence.",
                                "One-way metrics are unadjusted; group-restricted permutations do not identify attribution.",
                                "Not-detected is limited to the frozen thresholds, features and finite permutation resolution.",
                                "The conservative English wording gate is incomplete and also refuses negations.",
                                "Unavailable QC samples are not negative controls; independent source, record and method review remains required."]}
    except OSError as error:
        raise ValueError("input-file: unavailable regular file or unsafe bundle ancestor") from error
    except (RecursionError, OverflowError, UnicodeError) as error:
        raise ValueError("invalid-record: bounded finite inputs required") from error
    finally:
        if bundle is not None:
            bundle.close()
