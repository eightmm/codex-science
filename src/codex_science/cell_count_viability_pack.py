"""Read-only synthetic cell-count admission and exact binomial reference arithmetic."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat


STAGES = ("01-rule-freeze", "02-count-qc", "03-concentration-viability", "04-summary", "05-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_ROWS = 10000
MAX_SAMPLES = 128
MAX_NODES = 4000000
MAX_CELLS = 100000
MAX_CHAMBERS = 256
MAX_SQUARES = 64
MAX_ARTIFACTS = 256
REL_TOL = 1e-8
EDGE_TOL = 1e-12
MAX_ITERATIONS = 1000
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
    r"culture[\s-]+health|releas\w*|health\w*|physical[\s-]+validity|patient[\s-]+benefit\w*|steril\w*|safe\w*|poten\w*)\b", re.I,
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
    _require(len(pairs) <= MAX_ROWS, "input-limit", "JSON object exceeds entry limit")
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


def _denominator(value, scale):
    _require(math.isfinite(value) and abs(value) > 1e-14 * scale,
             "binomial-convergence", "relatively singular beta continued fraction")
    return value


def _beta_fraction(a, b, x):
    total = a + b
    c = 1.0
    term = total * x / (a + 1)
    d = 1 / _denominator(1 - term, max(1, abs(term)))
    result = d
    for step in range(1, MAX_ITERATIONS + 1):
        twice = 2 * step
        coefficients = (step * (b - step) * x / ((a + twice - 1) * (a + twice)),
                        -(a + step) * (total + step) * x / ((a + twice) * (a + twice + 1)))
        for coefficient in coefficients:
            term = coefficient * d
            d = 1 / _denominator(1 + term, max(1, abs(term)))
            term = coefficient / c
            c = _denominator(1 + term, max(1, abs(term)))
            delta = d * c
            result *= delta
        if math.isclose(delta, 1, rel_tol=1e-14, abs_tol=0):
            return result
    raise ValueError("binomial-convergence: beta continued fraction did not converge")


def _beta_cdf(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    scale = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                     + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1) / (a + b + 2):
        return scale * _beta_fraction(a, b, x) / a
    return 1 - scale * _beta_fraction(b, a, 1 - x) / b


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


def binomial_interval(live, total, level=0.95):
    """Equal-tail Clopper-Pearson interval; no Wald or normal approximation."""
    _number(total, "total cells", 1, MAX_CELLS, True)
    _number(live, "live cells", 0, total, True)
    _number(level, "interval level", 0.5, 0.999)
    tail = (1 - level) / 2
    lower = _beta_quantile(live, total - live + 1, tail) if live else 0.0
    upper = _beta_quantile(live + 1, total - live, 1 - tail) if live < total else 1.0
    return {"method": "clopper-pearson-exact", "level": level, "lower": lower, "upper": upper}


def _mixing(value):
    _fields(value, "sample_parts dye_parts", "mixing ratio")
    for key in value:
        _number(value[key], key, 1, 1000, True)
    return value


def _squares(value):
    return _names(value, "square identities", MAX_SQUARES)


def _rules(value):
    _record(value, "cell-rules-v1", "sample_ids chambers square_ids volume_ml dilution_factor mixing_ratio "
            "minimum_per_square maximum_per_square minimum_total_cells maximum_disagreement "
            "viability_definition interval_method interval_level")
    samples = _names(value["sample_ids"], "sample identities", MAX_SAMPLES)
    chambers = _list(value["chambers"], "chamber rules", MAX_CHAMBERS)
    squares = _squares(value["square_ids"])
    _require(len(chambers) * len(squares) <= MAX_ROWS, "input-limit", "frozen square grid exceeds row limit")
    _number(value["volume_ml"], "volume per square mL", 1e-12, 1)
    _number(value["dilution_factor"], "dilution factor", 1, 1e6)
    _mixing(value["mixing_ratio"])
    _number(value["minimum_per_square"], "countable minimum", 1, MAX_CELLS, True)
    _number(value["maximum_per_square"], "countable maximum", value["minimum_per_square"], MAX_CELLS, True)
    _number(value["minimum_total_cells"], "minimum cells", 1, MAX_CELLS, True)
    _number(value["maximum_disagreement"], "maximum disagreement", 0, 2)
    _require(value["viability_definition"] == "live/(live+dead)", "viability-definition", "frozen live fraction required")
    _require(value["interval_method"] == "clopper-pearson-exact", "binomial-interval", "exact binomial method required")
    _number(value["interval_level"], "interval level", 0.5, 0.999)
    seen, counters = set(), set()
    by_sample = {sample: 0 for sample in samples}
    for row in chambers:
        _fields(row, "chamber_id counter_id sample_id", "chamber rule")
        chamber = _text(row["chamber_id"], "chamber id")
        counter = _text(row["counter_id"], "counter id")
        sample = _text(row["sample_id"], "sample id")
        _require(chamber not in seen and counter not in counters,
                 "duplicate-chamber", "chamber and counter identities must be unique")
        seen.add(chamber)
        counters.add(counter)
        _require(sample in by_sample, "sample-identity", "chamber is outside frozen samples")
        by_sample[sample] += 1
    _require(all(count >= 2 for count in by_sample.values()),
             "replicate-minimum", "each sample needs at least two frozen chambers")
    return value


def compute_cell_count_viability(counts, rules, square_ids=None):
    """Compute recorded synthetic counts; square and chamber replicates never increase sample n."""
    rules = _rules(rules)
    _record(counts, "cell-counts-v1", "rows")
    rows = _list(counts["rows"], "square counts", MAX_ROWS)
    squares = _squares(rules["square_ids"] if square_ids is None else square_ids)
    chambers = {row["chamber_id"]: row for row in rules["chambers"]}
    _require(len(chambers) * len(squares) <= MAX_ROWS, "input-limit", "applied square grid exceeds row limit")
    square_set = set(squares)
    frozen_set = set(rules["square_ids"])
    _require(square_set <= frozen_set, "square-identity", "applied squares must come from the frozen recorded set")
    seen = set()
    grouped = {sample: [] for sample in rules["sample_ids"]}
    chamber_counts = dict.fromkeys(grouped, 0)
    for chamber in chambers.values():
        chamber_counts[chamber["sample_id"]] += 1
    for row in rows:
        _require(type(row) is dict and all(key in row for key in ("volume_ml", "dilution_factor", "mixing_ratio")),
                 "chamber-exposure", "every count needs chamber volume, dilution and mixing ratio")
        _fields(row, "chamber_id counter_id sample_id square_id volume_ml dilution_factor mixing_ratio live dead clumped",
                "square count")
        chamber = _text(row["chamber_id"], "chamber id")
        sample = _text(row["sample_id"], "sample id")
        counter = _text(row["counter_id"], "counter id")
        square = _text(row["square_id"], "square id")
        _require(chamber in chambers and sample == chambers[chamber]["sample_id"]
                 and counter == chambers[chamber]["counter_id"], "sample-identity", "count identities differ from frozen rule")
        _require(square in frozen_set and (chamber, square) not in seen,
                 "square-identity", "square is outside frozen set or repeated")
        seen.add((chamber, square))
        for key in ("volume_ml", "dilution_factor"):
            _number(row[key], key, 1e-12, 1e6)
            _require(math.isclose(row[key], rules[key], rel_tol=REL_TOL, abs_tol=0),
                     "chamber-exposure", "count exposure differs from frozen rule")
        _mixing(row["mixing_ratio"])
        _require(row["mixing_ratio"] == rules["mixing_ratio"], "chamber-exposure", "mixing ratio changed")
        _boolean(row["clumped"], "clumping flag")
        if row["live"] is None or row["dead"] is None:
            _require(row["live"] is None and row["dead"] is None,
                     "missing-count", "unavailable square requires both counts null")
        else:
            _number(row["live"], "live count", 0, MAX_CELLS, True)
            _number(row["dead"], "dead count", 0, MAX_CELLS, True)
        grouped[sample].append(row)
    _require(len(seen) == len(chambers) * len(frozen_set),
             "missing-square", "every frozen square needs an explicit row, including unavailable counts")
    mixing = rules["mixing_ratio"]
    factor = rules["dilution_factor"] * (mixing["sample_parts"] + mixing["dye_parts"]) / mixing["sample_parts"] / rules["volume_ml"]
    output = []
    for sample, sample_rows in grouped.items():
        recorded = [row for row in sample_rows if row["live"] is not None]
        total = sum(row["live"] + row["dead"] for row in recorded)
        _require(total <= MAX_CELLS, "input-limit", "pooled cell count exceeds reference limit")
        eligible = [row for row in recorded if row["square_id"] in square_set and not row["clumped"] and
                    rules["minimum_per_square"] <= row["live"] + row["dead"] <= rules["maximum_per_square"]]
        included = [[row["chamber_id"], row["square_id"]] for row in eligible]
        included_set = {tuple(identity) for identity in included}
        complete = len(eligible) == chamber_counts[sample] * len(squares)
        usable = sum(row["live"] + row["dead"] for row in eligible)
        means = {}
        for row in eligible:
            means.setdefault(row["chamber_id"], []).append(row["live"] + row["dead"])
        disagreement = "unavailable"
        if complete:
            chamber_means = [math.fsum(values) / len(values) for values in means.values()]
            mean = math.fsum(chamber_means) / len(chamber_means)
            _require(mean > 0, "degenerate-counts", "zero mean cannot define replicate disagreement")
            disagreement = (max(chamber_means) - min(chamber_means)) / mean
            bound = rules["maximum_disagreement"]
            _require(disagreement <= bound or math.isclose(disagreement, bound, rel_tol=EDGE_TOL, abs_tol=0),
                     "replicate-disagreement", "replicate chambers exceed frozen relative disagreement")
        available = complete and usable >= rules["minimum_total_cells"]
        live = sum(row["live"] for row in recorded)
        result = {"sample_id": sample, "classification": "quantified" if available else "unavailable",
                  "included_squares": included,
                  "excluded_squares": [[row["chamber_id"], row["square_id"]] for row in sample_rows
                                       if (row["chamber_id"], row["square_id"]) not in included_set],
                  "recorded_squares": len(recorded), "recorded_live": live if recorded else "unavailable",
                  "recorded_dead": total - live if recorded else "unavailable", "usable_total": usable,
                  "cells_per_ml": "unavailable", "count_uncertainty": "unavailable",
                  "replicate_disagreement": disagreement, "viability": "unavailable", "viability_interval": "unavailable"}
        if available:
            result["cells_per_ml"] = usable / len(eligible) * factor
            result["count_uncertainty"] = {"method": "poisson-standard-error",
                                            "standard_error_per_ml": math.sqrt(usable) / len(eligible) * factor,
                                            "relative_standard_error": 1 / math.sqrt(usable)}
            usable_live = sum(row["live"] for row in eligible)
            result["viability"] = usable_live / usable
            result["viability_interval"] = binomial_interval(usable_live, usable, rules["interval_level"])
        output.append(result)
    quantified = sum(row["classification"] == "quantified" for row in output)
    return {"samples": output, "summary": {"n": len(output), "quantified": quantified,
                                             "unavailable": len(output) - quantified}}


def _same(actual, expected, label):
    if type(expected) in (int, float):
        _number(actual, label, -MAX_NUMBER, integer=type(expected) is int)
        _require(math.isclose(actual, expected, rel_tol=REL_TOL, abs_tol=0),
                 "reported-number", f"reported {label} disagrees with reference")
    elif type(expected) is dict:
        _fields(actual, expected, label)
        for key in expected:
            _same(actual[key], expected[key], key)
    elif type(expected) is list:
        _list(actual, label, MAX_ROWS, True)
        _require(len(actual) == len(expected), "countable-selection", "reported square or sample count differs")
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


def validate_cell_count_viability_pack(bundle):
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
        pack = _record(store.load(path.name), "cell-pack-v1",
                       "rules frozen_rules_sha256 frozen_before_counts_read counts report evidence")
        rules = _rules(store.artifact(pack["rules"]))
        _require(_text(pack["frozen_rules_sha256"], "frozen rules hash") == pack["rules"]["sha256"]
                 and _boolean(pack["frozen_before_counts_read"], "frozen before counts read"),
                 "rule-freeze", "rules must be hash-frozen before counts are opened")
        report = store.artifact(pack["report"])
        _require("interval_method" in report and "interval_level" in report,
                 "binomial-interval", "report must retain exact interval method and level")
        _record(report, "cell-report-v1", "rules_sha256 exploratory square_ids viability_definition "
                "interval_method interval_level samples summary headline claims")
        _require(_text(report["rules_sha256"], "rules hash") == pack["rules"]["sha256"],
                 "rule-freeze", "report cites a different frozen rule revision")
        exploratory = _boolean(report["exploratory"], "exploratory")
        squares = _squares(report["square_ids"])
        _require(squares == rules["square_ids"] or exploratory,
                 "post-hoc-squares", "post-outcome square change requires exploratory label")
        _require(report["viability_definition"] == rules["viability_definition"],
                 "viability-definition", "reported viability definition changed")
        _require(report["interval_method"] == rules["interval_method"],
                 "binomial-interval", "Wald or other approximate interval is refused")
        _number(report["interval_level"], "reported interval level", 0.5, 0.999)
        _require(math.isclose(report["interval_level"], rules["interval_level"], rel_tol=REL_TOL, abs_tol=0),
                 "binomial-interval", "reported interval level changed")
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
            document = _record(store.artifact(descriptor), "cell-evidence-v1", "records")
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
        counts = store.artifact(pack["counts"])
        result = compute_cell_count_viability(counts, rules, squares)
        samples = _list(report["samples"], "reported samples", MAX_SAMPLES)
        _require(len(samples) == len(result["samples"]), "sample-identity", "report omits samples")
        clumped = {(row["chamber_id"], row["square_id"]) for row in counts["rows"] if row["clumped"]}
        for actual, expected in zip(samples, result["samples"]):
            _require(type(actual) is dict and "viability_interval" in actual,
                     "binomial-interval", "per-sample exact interval or unavailable required")
            identities = _list(actual.get("included_squares"), "reported square identities", MAX_ROWS, True)
            for identity in identities:
                _require(type(identity) is list and len(identity) == 2,
                         "invalid-record", "square identity requires chamber and square")
                for item in identity:
                    _text(item, "square identity")
                _require(tuple(identity) not in clumped, "clumped-selection", "clumped counts cannot be retained")
            _require(identities == expected["included_squares"],
                     "countable-selection", "only countable unclumped squares may enter the estimate")
            if expected["viability"] == "unavailable":
                _require(actual.get("viability") == "unavailable" and actual["viability_interval"] == "unavailable",
                         "minimum-viability", "incomplete or insufficient counts cannot give viability or intervals")
            if expected["classification"] == "unavailable":
                _require(actual.get("cells_per_ml") == "unavailable", "unavailable-as-zero",
                         "unquantified concentration must be unavailable, never zero")
            if not expected["recorded_squares"]:
                _require(actual.get("recorded_live") == "unavailable" and actual.get("recorded_dead") == "unavailable",
                         "unavailable-as-zero", "absent recorded counts must be unavailable, never zero")
            if type(actual["viability_interval"]) is dict:
                _require(actual["viability_interval"].get("method") == "clopper-pearson-exact",
                         "binomial-interval", "per-sample interval must be exact")
            _same(actual, expected, "sample")
        _same(report["summary"], result["summary"], "summary")
        store.finish()
        return {"schema": "cell-result-v1", "fixture": "synthetic fixture", "status": "arithmetic-only",
                "review": "unavailable", "stages": list(STAGES), "exploratory": exploratory,
                "inputs": [{"path": name, "sha256": item[2]} for name, item in sorted(store.snapshots.items())],
                "computation": result, "claims": report["claims"],
                "limitations": ["Synthetic counts establish software arithmetic only.",
                                "Poisson independence, binomial sampling and recorded dilution are assumptions.",
                                "Clumping and countability selection may affect interval coverage.",
                                "Hash declarations cannot establish historical freeze timing or independence.",
                                "Independent record, source and method review remains unavailable."]}
    finally:
        store.close()
