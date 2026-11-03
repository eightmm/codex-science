"""Read-only synthetic Cq arithmetic, with no biological or clinical admission."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import statistics


STAGES = ("01-freeze", "02-qc", "03-quantification", "04-summary", "05-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_TOTAL_NODES = 4000000
MAX_ARTIFACTS = 256
MAX_DEPTH = 64
MAX_ITEMS = 20000
MAX_TEXT = 4096
MAX_SAMPLES = 256
MAX_GENES = 32
MAX_WELLS = 10000
MAX_DILUTIONS = 64
MAX_TECHNICAL_REPLICATES = 16
MAX_RECORDS = 128
MAX_NUMBER = 1e100
POSITIVE = {"supported", "replicated", "suggestive"}
STATUSES = POSITIVE | {"planned", "conflicting", "unsupported", "withdrawn", "unavailable"}
WORDING_FAMILIES = (
    "caus", "mechanis", "therap", "clinic", "efficac", "effective", "treat", "cure",
    "prevent", "recommend", "prescri", "bind", "affinit", "inhibit", "activat",
    "regulat", "driv", "induc",
)
OVERREACH = re.compile(
    r"\b(?:" + "|".join(word + r"\w*" for word in WORDING_FAMILIES)
    + r"|biomarker\w*|target[\s-]+valid\w*|physical[\s-]+valid\w*|truth)\b", re.I,
)
ASSERTION = re.compile(r"\b(?:supported|replicated|suggestive|significan\w*)\b", re.I)
NON_EVIDENCE = re.compile(r"review|approv|comput|calculat|arithmet|numer|agreement|truth|physical|clinic", re.I)


def _require(condition, code, message):
    if not condition:
        raise ValueError(f"{code}: {message}")


def _text(value, label):
    _require(type(value) is str and bool(value.strip()), "invalid-record", f"{label} must be text")
    _require(len(value) <= MAX_TEXT, "input-limit", f"{label} text exceeds limit")
    return value


def _fields(value, fields, label):
    _require(type(value) is dict, "invalid-record", f"{label} must be an object")
    names = fields.split() if type(fields) is str else fields
    _require(set(value) == set(names), "invalid-record", f"{label} has missing or unknown fields")
    return value


def _items(value, label, limit, empty=False):
    _require(type(value) is list and (empty or bool(value)), "invalid-record", f"{label} must be a list")
    _require(len(value) <= limit, "input-limit", f"{label} exceeds limit {limit}")
    return value


def _names(value, label, limit, empty=False):
    value = _items(value, label, limit, empty)
    for item in value:
        _text(item, label)
    _require(len(set(value)) == len(value), "invalid-record", f"duplicate {label}")
    return value


def _number(value, label, low=-MAX_NUMBER, high=MAX_NUMBER, integer=False):
    valid = type(value) is int if integer else type(value) in (int, float)
    _require(valid and -MAX_NUMBER <= value <= MAX_NUMBER and math.isfinite(value)
             and low <= value <= high, "invalid-record", f"{label} must have a finite bounded numeric type")
    return value


def _boolean(value, label):
    _require(type(value) is bool, "invalid-record", f"{label} must be boolean")
    return value


def _record(value, schema, fields):
    _fields(value, "schema schema_version fixture " + fields, schema)
    _require(_text(value["schema"], "schema") == schema, "invalid-record", "wrong local schema")
    _number(value["schema_version"], "schema_version", 1, 1, integer=True)
    _require(value["fixture"] == "synthetic fixture", "invalid-record", "synthetic fixture label required")
    return value


def _pairs(pairs):
    _require(len(pairs) <= MAX_ITEMS, "input-limit", "JSON object exceeds limit")
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
    _require(math.isfinite(number) and abs(number) <= MAX_NUMBER, "invalid-json", "non-finite or huge number")
    return number


def _json(raw, allowance):
    # This conservative preparse allowance includes commas inside strings too.
    nodes = 1 + raw.count(b",") + sum(1 for _ in re.finditer(rb"[\[{](?=\s*[^\s\]}])", raw))
    _require(nodes <= allowance, "input-limit", "bundle JSON value allowance exceeded")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                           parse_constant=_constant, parse_int=_integer, parse_float=_float)
        _require(type(value) is dict, "invalid-json", "JSON root must be an object")
        pending = [(value, 0)]
        while pending:
            item, depth = pending.pop()
            _require(depth <= MAX_DEPTH, "invalid-json", "JSON nesting exceeds limit")
            if type(item) in (dict, list):
                _require(len(item) <= MAX_ITEMS, "input-limit", "JSON container exceeds limit")
                if type(item) is dict:
                    for key in item:
                        _text(key, "JSON key")
                children = item.values() if type(item) is dict else item
                pending.extend((child, depth + 1) for child in children)
            elif type(item) is str:
                _require(len(item) <= MAX_TEXT, "input-limit", "JSON string exceeds limit")
        return value, nodes
    except (UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError("invalid-json: bounded finite UTF-8 JSON object required") from error
    except json.JSONDecodeError as error:
        raise ValueError("invalid-json: malformed JSON") from error


def _relative(value):
    value = _text(value, "artifact path")
    path = PurePosixPath(value)
    _require(not path.is_absolute() and ".." not in path.parts and "\\" not in value
             and path.as_posix() == value and value != "." and ":" not in value
             and all(ord(char) >= 32 for char in value), "input-path", "canonical bundle-relative path required")
    return path


def _signature(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _artifact_identity(value):
    _fields(value, "path sha256", "artifact identity")
    _relative(value["path"])
    _require(type(value["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", value["sha256"]) is not None,
             "input-hash", "lowercase 64-hex SHA-256 required")
    return value


def _open_root(root):
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
    descriptor = os.open(root.anchor, flags)
    try:
        info = os.fstat(descriptor)
        identities = [(info.st_dev, info.st_ino)]
        for part in root.parts[1:]:
            before = os.lstat(part, dir_fd=descriptor)
            _require(stat.S_ISDIR(before.st_mode), "input-root", "bundle ancestors must be real directories")
            child = os.open(part, flags, dir_fd=descriptor)
            try:
                info = os.fstat(child)
                _require(stat.S_ISDIR(info.st_mode)
                         and (before.st_dev, before.st_ino) == (info.st_dev, info.st_ino),
                         "input-root", "bundle ancestor changed during pinning")
            except BaseException:
                os.close(child)
                raise
            os.close(descriptor)
            descriptor = child
            identities.append((info.st_dev, info.st_ino))
        return descriptor, identities
    except BaseException:
        os.close(descriptor)
        raise


class _Bundle:
    def __init__(self, root):
        self.root = root
        self.fd = None
        self.paths = {}
        self.cache = {}
        self.parsed = {}
        self.total_bytes = self.total_nodes = 0
        try:
            self.fd, self.identities = _open_root(root)
        except OSError as error:
            raise ValueError("input-root: cannot pin bundle directory") from error

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def _read(self, name, rechecked=None):
        path = _relative(name)
        directories = []
        try:
            directory = self.fd
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            for part in path.parts[:-1]:
                before = os.lstat(part, dir_fd=directory)
                _require(stat.S_ISDIR(before.st_mode), "input-file", "artifact directory must be real")
                directory = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
                directories.append(directory)
                info = os.fstat(directory)
                _require((info.st_dev, info.st_ino) == (before.st_dev, before.st_ino),
                         "input-file", "artifact directory changed during open")
            before = os.lstat(path.name, dir_fd=directory)
            _require(stat.S_ISREG(before.st_mode) and before.st_size <= MAX_BYTES,
                     "input-file", "regular input at most 64 MiB required")
            descriptor = os.open(path.name, flags, dir_fd=directory)
            with os.fdopen(descriptor, "rb") as handle:
                info = os.fstat(handle.fileno())
                signature = _signature(info)
                _require(stat.S_ISREG(info.st_mode) and info.st_size <= MAX_BYTES
                         and signature == _signature(before), "input-file", "input changed during open")
                identity = signature[:2]
                cached = self.cache.get(identity)
                if rechecked is not None:
                    _require(signature == self.paths[name][1], "input-changed", "input replaced during validation")
                if cached is not None:
                    _require(signature == cached[1], "input-changed", "cached input changed")
                    if rechecked is None or identity in rechecked:
                        return cached
                _require(rechecked is not None or self.total_bytes + info.st_size <= MAX_TOTAL_BYTES,
                         "input-limit", "aggregate input exceeds 256 MiB")
                raw = handle.read(min(MAX_BYTES, info.st_size) + 1)
                after = os.fstat(handle.fileno())
            _require(len(raw) == info.st_size and len(raw) <= MAX_BYTES and signature == _signature(after),
                     "input-file", "input grew or changed during bounded read")
            return raw, signature, hashlib.sha256(raw).hexdigest()
        except (OSError, UnicodeError) as error:
            raise ValueError("input-file: unavailable input or symlinked component") from error
        finally:
            for descriptor in reversed(directories):
                os.close(descriptor)

    def load(self, name, digest=None, parse=True):
        _relative(name)
        if name not in self.paths:
            _require(len(self.paths) < MAX_ARTIFACTS, "input-limit", "too many artifact paths")
            item = self._read(name)
            identity = item[1][:2]
            if identity not in self.cache:
                self.cache[identity] = item
                self.total_bytes += len(item[0])
            self.paths[name] = self.cache[identity]
        raw, signature, actual = self.paths[name]
        if digest is not None:
            _require(type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
                     and digest == actual, "input-hash", "artifact hash differs from parsed bytes")
        if not parse:
            return actual
        identity = signature[:2]
        if identity not in self.parsed:
            value, nodes = _json(raw, MAX_TOTAL_NODES - self.total_nodes)
            self.total_nodes += nodes
            self.parsed[identity] = value
        return self.parsed[identity]

    def artifact(self, value, parse=True):
        _artifact_identity(value)
        return self.load(value["path"], value["sha256"], parse)

    def _check_root(self):
        descriptor, identities = _open_root(self.root)
        try:
            _require(identities == self.identities, "input-root", "bundle ancestor identity changed")
        finally:
            os.close(descriptor)

    def finish(self):
        try:
            self._check_root()
            checked = set()
            for name, (_, signature, digest) in self.paths.items():
                current = self._read(name, checked)
                _require(current[1] == signature and current[2] == digest,
                         "input-changed", "artifact changed during validation")
                checked.add(signature[:2])
            self._check_root()
        except OSError as error:
            raise ValueError("input-root: bundle ancestor unavailable at final recheck") from error


def _close_number(actual, expected, code, label):
    _number(actual, label)
    _require(math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-10), code, label + " differs")


def _assay(assay, bounds):
    _fields(assay, "gene dilution_series efficiency r_squared", "assay")
    _text(assay["gene"], "assay gene")
    rows = _items(assay["dilution_series"], "dilution series", MAX_DILUTIONS, True)
    _require(len(rows) >= 3, "dilution-series", "efficiency requires at least three dilution points")
    xs, ys = [], []
    for row in rows:
        _fields(row, "log10_input cq", "dilution point")
        xs.append(_number(row["log10_input"], "log10 input", -12, 12))
        ys.append(_number(row["cq"], "dilution Cq", 0, 100))
    _require(len(set(xs)) == len(xs), "dilution-series", "dilution inputs must be distinct")
    mx, my = math.fsum(xs) / len(xs), math.fsum(ys) / len(ys)
    xx = math.fsum((x - mx) ** 2 for x in xs)
    yy = math.fsum((y - my) ** 2 for y in ys)
    _require(xx > 0 and yy > 0, "degenerate-series", "dilution series has zero variance")
    xy = math.fsum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = xy / xx
    _require(slope < 0 and -1 / slope <= math.log10(3), "efficiency-range", "invalid dilution slope")
    efficiency = math.expm1(-math.log(10) / slope)
    _require(bounds[0] <= efficiency <= bounds[1], "efficiency-range", "assay efficiency outside frozen range")
    r_squared = min(1.0, (xy / math.sqrt(xx) / math.sqrt(yy)) ** 2)
    _close_number(assay["efficiency"], efficiency, "efficiency-mismatch", "dilution-derived efficiency")
    _number(assay["r_squared"], "R-squared", 0, 1)
    _close_number(assay["r_squared"], r_squared, "r-squared-mismatch", "reported R-squared")
    return math.log2(1 + efficiency)


def _protocol(value):
    _record(value, "qpcr-protocol-v1", "conditions targets reference_gene reference_rule assays efficiency_range "
            "samples ntc_wells ntc_min_cq max_technical_spread detection_cq undetermined_rule statistic confidence minimum_interval_n")
    conditions = _names(value["conditions"], "conditions", 2)
    _require(len(conditions) == 2, "invalid-record", "two ordered conditions required: calibrator then contrast")
    targets = _names(value["targets"], "targets", MAX_GENES - 1)
    reference = _text(value["reference_gene"], "reference gene")
    _require(reference not in targets and value["reference_rule"] == "fixed-single-reference",
             "reference-rule", "one fixed reference distinct from targets required")
    _require(value["undetermined_rule"] == "censored", "censoring-rule", "undetermined is censored, never zero or 40")
    _require(value["statistic"] == "log2-fold-change-welch-t", "statistic-rule", "frozen biological Welch interval required")
    _number(value["confidence"], "confidence", 0.95, 0.95)
    _number(value["minimum_interval_n"], "minimum interval n", 3, 3, integer=True)
    bounds = _items(value["efficiency_range"], "efficiency range", 2)
    _require(len(bounds) == 2, "invalid-record", "two efficiency bounds required")
    for bound in bounds:
        _number(bound, "efficiency bound", 0.01, 2)
    _require(bounds[0] <= bounds[1], "invalid-record", "ordered efficiency bounds required")
    _number(value["ntc_min_cq"], "NTC threshold", 0, 100)
    _number(value["detection_cq"], "detection cutoff", 0, 100)
    _number(value["max_technical_spread"], "technical spread", 0, 100)
    genes = targets + [reference]
    assays = _items(value["assays"], "assays", MAX_GENES)
    _require(len(assays) == len(genes), "invalid-record", "one dilution series per gene required")
    factors = {}
    for assay in assays:
        factor = _assay(assay, bounds)
        gene = assay["gene"]
        _require(gene in genes and gene not in factors, "invalid-record", "assay gene identity differs")
        factors[gene] = factor
    samples = _items(value["samples"], "samples", MAX_SAMPLES)
    planned, sample_ids, biological_ids = {}, set(), set()
    total_wells = 0
    for sample in samples:
        _fields(sample, "id biological_id condition technical_replicates wells", "sample")
        identity = _text(sample["id"], "sample id")
        biological = _text(sample["biological_id"], "biological id")
        condition = _text(sample["condition"], "condition")
        _require(identity not in sample_ids and biological not in biological_ids,
                 "biological-identity", "one independent biological unit per sample, without repeated units")
        _require(condition in conditions, "invalid-record", "unknown condition")
        sample_ids.add(identity)
        biological_ids.add(biological)
        count = _number(sample["technical_replicates"], "technical replicate count", 1,
                        MAX_TECHNICAL_REPLICATES, integer=True)
        wells = _items(sample["wells"], "sample wells", MAX_WELLS)
        total_wells += len(wells)
        _require(total_wells <= MAX_WELLS, "input-limit", "planned wells exceed limit")
        _require(len(wells) == len(genes) * count, "well-identity", "complete assay by technical replicate grid required")
        seen = set()
        for well in wells:
            _fields(well, "well_id gene technical_replicate", "planned well")
            name = _text(well["well_id"], "well id")
            gene = _text(well["gene"], "well gene")
            tech = _number(well["technical_replicate"], "technical replicate", 1, count, integer=True)
            _require(gene in genes and (gene, tech) not in seen and name not in planned,
                     "well-identity", "duplicate or unknown planned well")
            seen.add((gene, tech))
            planned[name] = (identity, gene)
    ntcs = _items(value["ntc_wells"], "NTC wells", MAX_WELLS)
    _require(total_wells + len(ntcs) <= MAX_WELLS, "input-limit", "planned wells exceed limit")
    ntc_genes = set()
    for well in ntcs:
        _fields(well, "well_id gene", "NTC well")
        name = _text(well["well_id"], "NTC well id")
        gene = _text(well["gene"], "NTC gene")
        _require(name not in planned and gene in genes, "well-identity", "duplicate or unknown NTC well")
        planned[name] = (None, gene)
        ntc_genes.add(gene)
    _require(ntc_genes == set(genes), "ntc-missing", "NTC required for every assay")
    _require({sample["condition"] for sample in samples} == set(conditions),
             "insufficient-biological-n", "both biological conditions required")
    return factors, planned


def _beta_fraction(a, b, x):
    tiny = 1e-300
    c = 1.0
    d = 1 - (a + b) * x / (a + 1)
    d = 1 / (d if abs(d) > tiny else tiny)
    result = d
    for index in range(1, 201):
        for term in (index * (b - index) * x / ((a + 2 * index - 1) * (a + 2 * index)),
                     -(a + index) * (a + b + index) * x / ((a + 2 * index) * (a + 2 * index + 1))):
            d = 1 + term * d
            c = 1 + term / c
            d = 1 / (d if abs(d) > tiny else tiny)
            c = c if abs(c) > tiny else tiny
            delta = d * c
            result *= delta
        if abs(delta - 1) <= 3e-14:
            return result
    raise ValueError("numerical-failure: incomplete beta did not converge")


def _t_tail(t, df):
    x = df / (df + t * t)
    if x == 1:
        return 1.0
    a, b = df / 2, 0.5
    factor = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                      + a * math.log(x) + b * math.log1p(-x))
    return (factor * _beta_fraction(a, b, x) / a if x < (a + 1) / (a + b + 2)
            else 1 - factor * _beta_fraction(b, a, 1 - x) / b)


def _t_critical(df):
    # n >= 3 per group implies df >= 2; the 97.5% quantile is below 8.
    lower, upper = 0.0, 8.0
    for _ in range(64):
        middle = (lower + upper) / 2
        if _t_tail(middle, df) > 0.05:
            lower = middle
        else:
            upper = middle
    return (lower + upper) / 2


def reference_computation(protocol, table):
    """Efficiency-corrected unpaired two-condition contrast; inputs are synthetic."""
    factors, planned = _protocol(protocol)
    return _compute(protocol, table, factors, planned)


def _compute(protocol, table, factors, planned):
    _record(table, "qpcr-cq-table-v1", "rows")
    rows = _items(table["rows"], "Cq rows", MAX_WELLS)
    measured, grouped = {}, {}
    for row in rows:
        _fields(row, "well_id cq", "Cq row")
        well = _text(row["well_id"], "well id")
        _require(well in planned and well not in measured, "well-identity", "unknown or duplicate measured well")
        cq = row["cq"]
        if cq != "undetermined":
            _number(cq, "Cq", 0, 100)
        measured[well] = cq
        sample, gene = planned[well]
        if sample is None:
            _require(cq == "undetermined" or cq > protocol["ntc_min_cq"],
                     "ntc-amplification", "NTC amplified at or below frozen threshold")
        else:
            grouped.setdefault((sample, gene), []).append(cq)
    _require(measured.keys() == planned.keys(), "well-identity", "measured and frozen well identities differ")
    means = {}
    for key, values in grouped.items():
        finite = [cq for cq in values if cq != "undetermined"]
        _require(not finite or max(finite) - min(finite) <= protocol["max_technical_spread"] + 1e-12,
                 "technical-spread", "technical spread exceeds frozen maximum; averaging refused")
        means[key] = (math.fsum(finite) / len(finite) if len(finite) == len(values)
                      and all(cq < protocol["detection_cq"] for cq in finite) else None)
    control, treatment = protocol["conditions"]
    reference = protocol["reference_gene"]
    summaries = []
    for gene in protocol["targets"]:
        groups = {control: [], treatment: []}
        missing = {control: 0, treatment: 0}
        quantities = []
        for sample in protocol["samples"]:
            target_cq = means[(sample["id"], gene)]
            reference_cq = means[(sample["id"], reference)]
            normalized = (None if target_cq is None or reference_cq is None
                          else reference_cq * factors[reference] - target_cq * factors[gene])
            if normalized is None:
                missing[sample["condition"]] += 1
            else:
                groups[sample["condition"]].append(normalized)
            quantities.append((sample, normalized))
        first, second = groups[control], groups[treatment]
        _require(first and second, "insufficient-biological-n", "no detected biological values in a condition")
        calibrator = math.fsum(first) / len(first)
        difference = math.fsum(second) / len(second) - calibrator
        interval = "unavailable"
        if min(len(first), len(second)) >= protocol["minimum_interval_n"]:
            va, vb = statistics.variance(first), statistics.variance(second)
            _require(va > 0 and vb > 0, "degenerate-variance", "zero biological variance cannot yield an interval")
            a, b = va / len(first), vb / len(second)
            scale = max(a, b)
            _require(scale > 0, "degenerate-variance", "biological uncertainty below numeric resolution")
            wa, wb = a / scale, b / scale
            df = (wa + wb) ** 2 / (wa * wa / (len(first) - 1) + wb * wb / (len(second) - 1))
            margin = _t_critical(df) * math.sqrt(a + b)
            interval = {"lower": difference - margin, "upper": difference + margin, "confidence": 0.95, "df": df}
        samples = []
        for sample, normalized in quantities:
            log2_quantity = "unavailable" if normalized is None else normalized - calibrator
            samples.append({"sample_id": sample["id"], "biological_id": sample["biological_id"],
                            "condition": sample["condition"], "censored": normalized is None,
                            "log2_relative_quantity": log2_quantity,
                            "relative_quantity": "unavailable" if normalized is None else 2.0 ** log2_quantity})
        summaries.append({"gene": gene, "reference_gene": reference, "calibrator": control, "contrast": treatment,
                          "n": {group: len(values) for group, values in groups.items()}, "censored_n": missing,
                          "log2_fold_change": difference, "fold_change": 2.0 ** difference,
                          "interval": interval, "samples": samples})
    return summaries


def _same(actual, expected):
    if type(expected) is dict:
        _fields(actual, expected, "summary")
        for key in expected:
            _same(actual[key], expected[key])
    elif type(expected) is list:
        _items(actual, "summary rows", MAX_WELLS, True)
        _require(len(actual) == len(expected), "summary-mismatch", "summary row count differs")
        for a, b in zip(actual, expected):
            _same(a, b)
    elif type(expected) in (int, float):
        _number(actual, "summary number", integer=type(expected) is int)
        _close_number(actual, expected, "summary-mismatch", "summary number")
    else:
        _require(type(actual) is type(expected) and actual == expected,
                 "summary-mismatch", "summary differs, including censored values and unavailable intervals")


def _claims(claims, evidence):
    seen = set()
    for claim in _items(claims, "claims", MAX_RECORDS, True):
        _fields(claim, "id kind status text evidence", "claim")
        identity = _text(claim["id"], "claim id")
        _require(identity not in seen, "invalid-record", "duplicate claim identity")
        seen.add(identity)
        kind = _text(claim["kind"], "claim kind")
        status = _text(claim["status"], "claim status")
        text = _text(claim["text"], "claim text")
        _require(kind in {"descriptive", "associational"} and not OVERREACH.search(text),
                 "claim-overreach", "text exceeds offline arithmetic evidence")
        _require(status in STATUSES, "invalid-record", "unknown claim status")
        ids = _names(claim["evidence"], "claim evidence", MAX_RECORDS, True)
        _require(ids or status == "unavailable", "missing-evidence", "empty evidence requires unavailable")
        _require(status != "unavailable" or not ASSERTION.search(text),
                 "unavailable-positive", "unavailable claim asserts positive evidence")
        for identity in ids:
            _require(identity in evidence, "missing-evidence", "unknown evidence identity")
            source = evidence[identity]
            _require("unavailable" not in (source["kind"], source["result"]) or status == "unavailable",
                     "unavailable-evidence", "unavailable evidence requires an unavailable claim")
            _require(status not in POSITIVE or not any(NON_EVIDENCE.search(source[key]) for key in ("kind", "result")),
                     "non-evidence-support", "computed records and review approval cannot support positive claims")
        _require(status != "replicated", "claim-replication", "one synthetic bundle cannot establish replication")


def validate_qpcr_relative_quantification_pack(bundle):
    """Validate one pack JSON plus pinned relative artifacts, returning JSON data."""
    try:
        value = _text(os.fspath(bundle), "bundle path")
        _require(".." not in Path(value).parts and all(ord(c) >= 32 for c in value),
                 "input-path", "invalid bundle path")
        path = Path(os.path.abspath(value))
    except (TypeError, ValueError) as error:
        raise ValueError("input-path: invalid bundle path") from error
    store = _Bundle(path.parent)
    try:
        pack = _record(store.load(path.name), "qpcr-pack-v1",
                       "protocol frozen_protocol_sha256 frozen_before_cq_read table report evidence")
        protocol = store.artifact(pack["protocol"])
        factors, planned = _protocol(protocol)
        _require(_text(pack["frozen_protocol_sha256"], "frozen protocol hash") == pack["protocol"]["sha256"]
                 and _boolean(pack["frozen_before_cq_read"], "freeze before Cq read"),
                 "protocol-freeze", "rules must be hash-frozen before Cq admission")
        report = _record(store.artifact(pack["report"]), "qpcr-report-v1",
                         "protocol_sha256 reference_gene exploratory undetermined_rule technical_rule efficiency_source n_unit summary headline claims")
        _require(_text(report["protocol_sha256"], "report protocol hash") == pack["protocol"]["sha256"],
                 "protocol-freeze", "report cites a different frozen protocol")
        exploratory = _boolean(report["exploratory"], "exploratory")
        _text(report["reference_gene"], "report reference gene")
        _require(report["reference_gene"] == protocol["reference_gene"] or exploratory,
                 "post-hoc-reference", "changed reference requires an exploratory label and a separate frozen revision")
        _require(report["reference_gene"] == protocol["reference_gene"],
                 "unsupported-reference", "exploratory reference changes require a separate frozen revision")
        _require(report["undetermined_rule"] == "censored", "censoring-rule", "undetermined cannot become 40 or zero")
        _require(report["technical_rule"] == "refuse-spread", "technical-rule", "averaging cannot override failed spread")
        _require(report["efficiency_source"] == "dilution-series", "dilution-series", "100 percent efficiency cannot be assumed")
        _require(report["n_unit"] == "biological", "biological-n", "technical replicates cannot count as biological n")
        headline = _text(report["headline"], "headline")
        _require(not OVERREACH.search(headline), "claim-overreach", "headline exceeds offline arithmetic evidence")
        descriptors = _items(pack["evidence"], "evidence artifacts", MAX_RECORDS, True)
        own_paths, own_hashes = {path.name}, {store.paths[path.name][2]}
        for descriptor in (pack["protocol"], pack["table"], pack["report"], *descriptors):
            _artifact_identity(descriptor)
            own_paths.add(str(_relative(descriptor["path"])))
            own_hashes.add(descriptor["sha256"])
        evidence = {}
        for descriptor in descriptors:
            document = _record(store.artifact(descriptor), "qpcr-evidence-v1", "records")
            records = _items(document["records"], "evidence records", MAX_RECORDS, True)
            _require(len(evidence) + len(records) <= MAX_RECORDS, "input-limit", "aggregate evidence count exceeds limit")
            for record in records:
                _fields(record, "id kind result origin source", "evidence record")
                identity = _text(record["id"], "evidence id")
                _require(identity not in evidence, "invalid-record", "duplicate evidence identity")
                for key in ("kind", "result", "origin"):
                    _text(record[key], key)
                _require(record["origin"] in {"internal", "external", "independent", "preregistered"},
                         "invalid-record", "unknown evidence origin")
                digest = store.artifact(record["source"], False)
                _require(record["origin"] == "internal" or
                         (record["source"]["path"] not in own_paths and digest not in own_hashes),
                         "external-alias", "external label aliases the bundle's own records")
                evidence[identity] = record
        _claims(report["claims"], evidence)
        computation = _compute(protocol, store.artifact(pack["table"]), factors, planned)
        _items(report["summary"], "reported summaries", MAX_GENES)
        _require(type(report["summary"]) is list and all(type(row) is dict and "interval" in row
                 for row in report["summary"]), "interval-required", "every fold change requires an interval field")
        for actual, expected in zip(report["summary"], computation):
            _require(expected["interval"] != "unavailable" or actual["interval"] == "unavailable",
                     "interval-small-n", "fewer than three detected biological units requires unavailable interval")
        _same(report["summary"], computation)
        store.finish()
        return {"schema": "qpcr-result-v1", "schema_version": 1, "fixture": "synthetic fixture",
                "status": "arithmetic-only", "review": "unavailable", "stages": list(STAGES),
                "exploratory": exploratory, "computation": computation, "claims": report["claims"],
                "inputs": [{"path": name, "sha256": item[2]} for name, item in sorted(store.paths.items())],
                "limitations": ["Synthetic fixtures establish arithmetic behavior only.",
                                "Hashes cannot establish historical freezing or independent source authenticity.",
                                "Fixed single reference, unpaired two-condition contrast and 95 percent Welch interval only.",
                                "Censored biological units are counted and omitted from detected-value estimates.",
                                "Independent review is coordinator-owned and unavailable here.",
                                "English lexical claim checks are conservative and incomplete."]}
    finally:
        store.close()
