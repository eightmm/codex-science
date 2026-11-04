"""Read-only synthetic ddPCR admission and exact binomial/Poisson reference arithmetic."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat


STAGES = ("01-rule-freeze", "02-count-qc", "03-quantification", "04-summary", "05-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_ROWS = 10000
MAX_SAMPLES = 128
MAX_NODES = 4000000
MAX_PARTITIONS = 1000000
MAX_ARTIFACTS = 256
RELATIVE_TOLERANCE = 1e-8
EDGE_TOLERANCE = 1e-12
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
    r"physical[\s-]+validity|patient[\s-]+benefit\w*|copy[\s-]+number\w*|"
    r"gene[\s-]+dosage|disease\w*|sample[\s-]+suitab\w*)\b", re.I,
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
            _require(len(self.snapshots) < MAX_ARTIFACTS, "input-limit", "too many artifact paths")
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
    """Modified Lentz continued fraction for the incomplete beta function."""
    tiny = 1e-300
    c = 1.0
    d = 1 - (a + b) * x / (a + 1)
    if abs(d) < tiny:
        d = math.copysign(tiny, d)
    d = 1 / d
    result = d
    for step in range(1, MAX_ITERATIONS + 1):
        even = 2 * step
        for numerator in (step * (b - step) * x / ((a + even - 1) * (a + even)),
                          -(a + step) * (a + b + step) * x / ((a + even) * (a + even + 1))):
            d = 1 + numerator * d
            c = 1 + numerator / c
            if abs(d) < tiny:
                d = math.copysign(tiny, d)
            if abs(c) < tiny:
                c = math.copysign(tiny, c)
            d = 1 / d
            delta = d * c
            result *= delta
        if abs(delta - 1) <= 1e-14:
            _require(math.isfinite(result) and result > 0,
                     "binomial-convergence", "non-finite beta fraction")
            return result
    raise ValueError("binomial-convergence: exact beta tail did not converge")


def _beta_cdf(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    factor = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                      + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1) / (a + b + 2):
        result = factor * _beta_fraction(a, b, x) / a
    else:
        result = 1 - factor * _beta_fraction(b, a, 1 - x) / b
    _require(math.isfinite(result), "binomial-convergence", "non-finite beta tail")
    return min(1.0, max(0.0, result))


def _beta_quantile(a, b, probability):
    low, high = 0.0, 1.0
    for _ in range(QUANTILE_STEPS):
        middle = (low + high) / 2
        if _beta_cdf(a, b, middle) < probability:
            low = middle
        else:
            high = middle
    _require(high - low <= high * 1e-12,
             "binomial-convergence", "beta quantile bisection did not converge")
    return (low + high) / 2


def exact_binomial_interval(positive, total, level=0.95):
    """Equal-tail Clopper-Pearson bounds; zero events retain a positive upper bound."""
    _number(total, "total partitions", 1, MAX_PARTITIONS, True)
    _number(positive, "positive partitions", 0, MAX_PARTITIONS, True)
    _require(positive <= total, "partition-count", "positive partitions exceed total")
    _number(level, "confidence level", 0.5, 0.999)
    tail = (1 - level) / 2
    lower = (_beta_quantile(positive, total - positive + 1, tail) if 0 < positive < total
             else math.exp(math.log(tail) / total) if positive == total else 0.0)
    upper = (1 - _beta_quantile(total - positive, positive + 1, tail) if 0 < positive < total
             else -math.expm1(math.log(tail) / total) if positive == 0 else 1.0)
    return {"method": "clopper-pearson-exact", "level": level, "lower": lower, "upper": upper}


THRESHOLDS = "minimum_accepted_partitions ntc_maximum_positive saturation_bound agreement_bound"


def _thresholds(value):
    _fields(value, THRESHOLDS, "applied thresholds")
    _number(value["minimum_accepted_partitions"], "minimum accepted partitions", 1, MAX_PARTITIONS, True)
    _number(value["ntc_maximum_positive"], "NTC maximum positive", 0, MAX_PARTITIONS, True)
    _number(value["saturation_bound"], "saturation bound", 1e-9, 1 - 1e-9)
    _number(value["agreement_bound"], "replicate relative range bound", 0, 1)
    return value


def _rules(value):
    _record(value, "ddpcr-rules-v1", "sample_ids wells partition_volume_ul minimum_accepted_partitions "
            "ntc_maximum_positive saturation_bound dilution_factor reaction_to_sample_scaling "
            "confidence_level interval_method replicate_wells_per_sample agreement_bound")
    samples = _names(value["sample_ids"], "sample identities", MAX_SAMPLES)
    wells = _list(value["wells"], "well rules", MAX_ROWS)
    _thresholds({key: value[key] for key in THRESHOLDS.split()})
    _number(value["partition_volume_ul"], "partition volume in uL", 1e-12, 1e6)
    _number(value["dilution_factor"], "dilution correction multiplier", 1e-12, 1e12)
    _number(value["reaction_to_sample_scaling"], "reaction-to-sample multiplier", 1e-12, 1e12)
    _number(value["confidence_level"], "confidence level", 0.5, 0.999)
    _require(value["interval_method"] == "clopper-pearson-exact",
             "binomial-interval", "exact Clopper-Pearson interval required")
    _number(value["replicate_wells_per_sample"], "replicate wells", 1, MAX_ROWS, True)
    seen = set()
    grouped = {sample: 0 for sample in samples}
    ntcs = 0
    for row in wells:
        _fields(row, "well_id sample_id role", "well rule")
        identity = _text(row["well_id"], "well id")
        sample = _text(row["sample_id"], "sample id")
        role = _text(row["role"], "well role")
        _require(identity not in seen, "duplicate-well", "well IDs must be unique")
        seen.add(identity)
        _require(role in {"sample", "ntc"}, "invalid-record", "well role must be sample or ntc")
        if role == "sample":
            _require(sample in grouped, "sample-identity", "well sample is outside frozen identities")
            grouped[sample] += 1
        else:
            _require(sample == "NTC" and sample not in grouped,
                     "sample-identity", "NTC identity must be distinct from samples")
            ntcs += 1
    _require(ntcs > 0, "missing-ntc", "at least one frozen NTC well required")
    _require(all(count == value["replicate_wells_per_sample"] for count in grouped.values()),
             "replicate-identity", "each sample needs its frozen number of replicate wells")
    return value


def _quantities(positive, total, rules):
    _require(total > 0 and positive < total, "singular-positive-fraction", "finite positive fraction required")
    p = positive / total
    interval = exact_binomial_interval(positive, total, rules["confidence_level"])
    _require(interval["upper"] < 1 and 1 - interval["upper"] >= 1e-12,
             "singular-interval", "upper fraction endpoint is numerically singular")
    scale = rules["dilution_factor"] * rules["reaction_to_sample_scaling"] / rules["partition_volume_ul"]
    lam = -math.log1p(-p)
    transformed = {"method": "clopper-pearson-exact-transformed", "level": interval["level"],
                   "lower": -math.log1p(-interval["lower"]) * scale,
                   "upper": -math.log1p(-interval["upper"]) * scale}
    concentration = lam * scale
    _require(all(math.isfinite(number) for number in (lam, concentration, transformed["lower"], transformed["upper"])),
             "degenerate-numerics", "non-finite Poisson quantity")
    return {"positive_fraction": p, "lambda": lam, "concentration_copies_per_ul": concentration,
            "interval": transformed}


def compute_ddpcr(counts, rules, thresholds=None):
    """Quantify admitted synthetic partitions; failed controls never become zeros."""
    rules = _rules(rules)
    thresholds = _thresholds({key: rules[key] for key in THRESHOLDS.split()} if thresholds is None else thresholds)
    _record(counts, "ddpcr-counts-v1", "rows")
    rows = _list(counts["rows"], "partition counts", MAX_ROWS)
    frozen = {row["well_id"]: row for row in rules["wells"]}
    admitted = {}
    for row in rows:
        _fields(row, "well_id sample_id role flag positive total", "partition count")
        identity = _text(row["well_id"], "well id")
        sample = _text(row["sample_id"], "sample id")
        role = _text(row["role"], "well role")
        flag = _text(row["flag"], "count flag")
        _require(identity not in admitted, "duplicate-well", "well IDs must be unique")
        _require(identity in frozen and sample == frozen[identity]["sample_id"] and role == frozen[identity]["role"],
                 "sample-identity", "count identities differ from frozen wells")
        _require(flag in {"observed", "unavailable"}, "invalid-record", "unknown count availability flag")
        if flag == "unavailable":
            _require(row["positive"] is None and row["total"] is None,
                     "unavailable-as-zero", "unavailable counts must be null")
        else:
            _number(row["positive"], "positive partitions", 0, MAX_PARTITIONS, True)
            _number(row["total"], "total partitions", 0, MAX_PARTITIONS, True)
            _require(row["positive"] <= row["total"], "partition-count", "positive partitions exceed total")
        admitted[identity] = row
    _require(all(row["well_id"] in admitted for row in rules["wells"] if row["role"] == "ntc"),
             "missing-ntc", "NTC wells must be explicitly present")
    _require(set(admitted) == set(frozen), "missing-well", "missing wells need explicit unavailable rows")
    output = []
    for identity, rule in frozen.items():
        row = admitted[identity]
        p = row["positive"] / row["total"] if row["flag"] == "observed" and row["total"] else "unavailable"
        reason = "none"
        if row["flag"] == "unavailable":
            reason = "missing-counts"
        elif row["total"] < thresholds["minimum_accepted_partitions"]:
            reason = "insufficient-partitions"
        elif row["role"] == "ntc":
            if row["positive"] > thresholds["ntc_maximum_positive"]:
                reason = "ntc-contamination"
        elif row["positive"] == row["total"]:
            reason = "singular-positive-fraction"
        elif p > thresholds["saturation_bound"]:
            reason = "saturated-well"
        output.append({**rule, "status": "unavailable" if reason != "none" else
                       "control-passed" if row["role"] == "ntc" else "quantified",
                       "reason": reason, "positive": row["positive"], "total": row["total"],
                       "positive_fraction": p, "lambda": "unavailable",
                       "concentration_copies_per_ul": "unavailable", "interval": "unavailable"})
    ntc_failed = any(row["role"] == "ntc" and row["status"] == "unavailable" for row in output)
    grouped = {sample: [] for sample in rules["sample_ids"]}
    for row in output:
        if row["role"] == "sample":
            if ntc_failed:
                row.update(status="unavailable", reason="ntc-failure")
            if row["status"] == "quantified":
                row.update(_quantities(row["positive"], row["total"], rules))
            grouped[row["sample_id"]].append(row)
    samples = []
    for sample, wells in grouped.items():
        observed = all(row["positive"] is not None and row["total"] is not None for row in wells)
        positive = sum(row["positive"] for row in wells) if observed else "unavailable"
        total = sum(row["total"] for row in wells) if observed else "unavailable"
        _require(not observed or total <= MAX_PARTITIONS, "input-limit", "pooled partitions exceed reference limit")
        reason = next((row["reason"] for row in wells if row["status"] == "unavailable"), "none")
        if reason == "none":
            lambdas = [row["lambda"] for row in wells]
            largest = max(lambdas)
            if (largest > 0 and (largest - min(lambdas)) / largest > thresholds["agreement_bound"]
                    and not math.isclose((largest - min(lambdas)) / largest, thresholds["agreement_bound"], rel_tol=EDGE_TOLERANCE, abs_tol=0)):
                reason = "replicate-disagreement"
        result = {"sample_id": sample, "well_ids": [row["well_id"] for row in wells],
                  "status": "quantified" if reason == "none" else "unavailable", "reason": reason,
                  "positive": positive, "total": total,
                  "positive_fraction": positive / total if observed and total else "unavailable",
                  "lambda": "unavailable", "concentration_copies_per_ul": "unavailable", "interval": "unavailable"}
        if reason == "none":
            result.update(_quantities(positive, total, rules))
        samples.append(result)
    values = [row["concentration_copies_per_ul"] for row in samples if row["status"] == "quantified"]
    summary = {"n": len(samples), "quantified": len(values), "unavailable": len(samples) - len(values),
               "ntc_passed": not ntc_failed,
               "mean_concentration_copies_per_ul": math.fsum(values) / len(values) if values else "unavailable"}
    return {"wells": output, "samples": samples, "summary": summary}


def _same(actual, expected, label):
    if type(expected) in (int, float):
        _number(actual, label, -MAX_NUMBER, integer=type(expected) is int)
        _require(math.isclose(actual, expected, rel_tol=RELATIVE_TOLERANCE, abs_tol=0),
                 "reported-number", f"reported {label} disagrees with reference")
    elif type(expected) is dict:
        _fields(actual, expected, label)
        for key in expected:
            _same(actual[key], expected[key], key)
    elif type(expected) is list:
        _list(actual, label, MAX_ROWS, True)
        _require(len(actual) == len(expected), "reported-selection", "reported well or sample count differs")
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


def _reported(actual, expected):
    _fields(actual, expected, "quantification record")
    if expected["status"] == "unavailable":
        code = "ntc-contamination" if expected["reason"] == "ntc-failure" else expected["reason"]
        _require(all(actual[key] == "unavailable" for key in ("lambda", "concentration_copies_per_ul", "interval")),
                 code, "failed QC or missing counts must leave concentration unavailable")
    elif expected["status"] == "quantified":
        _number(actual["lambda"], "reported lambda")
        _require(math.isclose(actual["lambda"], expected["lambda"], rel_tol=RELATIVE_TOLERANCE, abs_tol=0),
                 "poisson-correction", "lambda must use -log1p(-positive/total)")
        _number(actual["concentration_copies_per_ul"], "reported concentration")
        _require(math.isclose(actual["concentration_copies_per_ul"], expected["concentration_copies_per_ul"],
                              rel_tol=RELATIVE_TOLERANCE, abs_tol=0),
                 "concentration-scaling", "concentration must retain volume, dilution and sample scaling")
        _require(type(actual["interval"]) is dict
                 and actual["interval"].get("method") == "clopper-pearson-exact-transformed",
                 "binomial-interval", "exact transformed Clopper-Pearson interval required")
    _same(actual, expected, "quantification")


def validate_ddpcr_absolute_quantification_pack(bundle):
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
        pack = _record(store.load(path.name), "ddpcr-pack-v1",
                       "rules frozen_rules_sha256 frozen_before_counts_read counts report evidence")
        rules = _rules(store.artifact(pack["rules"]))
        _require(_text(pack["frozen_rules_sha256"], "frozen rules hash") == pack["rules"]["sha256"]
                 and _boolean(pack["frozen_before_counts_read"], "frozen before counts read"),
                 "rule-freeze", "rules must be hash-frozen before counts are opened")
        report = store.artifact(pack["report"])
        _require("interval_method" in report and "confidence_level" in report,
                 "binomial-interval", "report must retain exact interval method and confidence level")
        _record(report, "ddpcr-report-v1", "rules_sha256 exploratory thresholds interval_method confidence_level "
                "wells samples summary headline claims")
        _require(_text(report["rules_sha256"], "rules hash") == pack["rules"]["sha256"],
                 "rule-freeze", "report cites a different frozen rule revision")
        exploratory = _boolean(report["exploratory"], "exploratory")
        thresholds = _thresholds(report["thresholds"])
        _require(exploratory or all(math.isclose(thresholds[key], rules[key],
                                                rel_tol=RELATIVE_TOLERANCE, abs_tol=0) for key in thresholds),
                 "post-hoc-threshold", "post-outcome threshold changes require exploratory label")
        _require(report["interval_method"] == rules["interval_method"],
                 "binomial-interval", "normal approximation or omitted exact interval is refused")
        _number(report["confidence_level"], "reported confidence level", 0.5, 0.999)
        _require(math.isclose(report["confidence_level"], rules["confidence_level"],
                              rel_tol=RELATIVE_TOLERANCE, abs_tol=0),
                 "binomial-interval", "confidence level differs from frozen rule")
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
            document = _record(store.artifact(descriptor), "ddpcr-evidence-v1", "records")
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
        result = compute_ddpcr(store.artifact(pack["counts"]), rules, thresholds)
        for key, limit in (("wells", MAX_ROWS), ("samples", MAX_SAMPLES)):
            reported = _list(report[key], "reported " + key, limit)
            _require(len(reported) == len(result[key]), "sample-identity", "report omits wells or samples")
            for actual, expected in zip(reported, result[key]):
                _reported(actual, expected)
        _same(report["summary"], result["summary"], "summary")
        store.finish()
        return {"schema": "ddpcr-result-v1", "fixture": "synthetic fixture", "status": "arithmetic-only",
                "review": "unavailable", "stages": list(STAGES), "exploratory": exploratory,
                "inputs": [{"path": name, "sha256": item[2]} for name, item in sorted(store.snapshots.items())],
                "computation": result, "claims": report["claims"],
                "limitations": ["Synthetic counts establish software arithmetic only.",
                                "Independent equal-volume partitions and valid readout are assumptions, not verified observations.",
                                "Exact binomial intervals omit volume, dilution and scaling uncertainty and post-selection effects.",
                                "Zero positives do not establish absence; failed controls preserve unavailable concentration.",
                                "Hash declarations cannot establish historical freeze timing or independence.",
                                "Independent record, source and method review remains unavailable."]}
    finally:
        store.close()
