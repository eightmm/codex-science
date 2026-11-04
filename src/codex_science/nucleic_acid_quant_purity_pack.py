"""Read-only synthetic nucleic-acid absorbance admission and reference arithmetic."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat


STAGES = ("01-rule-freeze", "02-reading-qc", "03-quant-purity", "04-summary", "05-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_ROWS = 10000
MAX_SAMPLES = 128
MAX_NODES = 4000000
MAX_REPLICATES = 128
RELATIVE_TOLERANCE = 1e-8
EDGE_TOLERANCE = 1e-12


def _inside(value, minimum, maximum):
    return (minimum <= value <= maximum or math.isclose(value, minimum, rel_tol=EDGE_TOLERANCE, abs_tol=0)
            or math.isclose(value, maximum, rel_tol=EDGE_TOLERANCE, abs_tol=0))

RELATIVE_ZERO = 1e-12
CONVERSION_FACTORS = {"dsDNA": 50.0, "RNA": 40.0}
WAVELENGTHS = ("A230", "A260", "A280", "A320")
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
    r"physical[\s-]+validity|patient[\s-]+benefit\w*|quality|suitab\w*|sequenc\w*|"
    r"clon\w*|pcr|downstream|safe\w*)\b", re.I,
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


def _bands(value):
    _fields(value, CONVERSION_FACTORS, "purity bands")
    for analyte in CONVERSION_FACTORS:
        _fields(value[analyte], "a260_a280 a260_a230", "analyte bands")
        for band in value[analyte].values():
            _fields(band, "minimum maximum", "ratio band")
            _number(band["minimum"], "ratio minimum", 0, 100)
            _number(band["maximum"], "ratio maximum", band["minimum"], 100)
    return value


def _rules(value):
    _record(value, "nuc-rules-v1", "samples blank_id wavelengths path_length_cm background_rule "
            "blank_rule linear_a260_range purity_bands minimum_replicates replicate_max_relative_difference")
    samples = _list(value["samples"], "frozen samples", MAX_SAMPLES)
    blank = _text(value["blank_id"], "blank id")
    _require(value["wavelengths"] == list(WAVELENGTHS), "wavelength-rule", "four ordered wavelengths required")
    _number(value["path_length_cm"], "path length cm", 1e-6, 10)
    _require(value["background_rule"] == "subtract-A320", "background-rule", "A320 subtraction is mandatory")
    _require(value["blank_rule"] == "subtract-background-corrected-blank",
             "blank-rule", "matched background-corrected blank subtraction is mandatory")
    _fields(value["linear_a260_range"], "minimum maximum", "linear A260 range")
    low = _number(value["linear_a260_range"]["minimum"], "linear minimum", 0, 100)
    high = _number(value["linear_a260_range"]["maximum"], "linear maximum", low, 100)
    _require(high > low and high - low > RELATIVE_ZERO * high,
             "linear-range", "linear range must have nondegenerate width")
    _bands(value["purity_bands"])
    _number(value["minimum_replicates"], "minimum replicates", 2, MAX_REPLICATES, True)
    _number(value["replicate_max_relative_difference"], "replicate agreement", 0, 1)
    seen = set()
    for sample in samples:
        _fields(sample, "sample_id analyte conversion_factor_ng_ul dilution_factor", "sample rule")
        identity = _text(sample["sample_id"], "sample id")
        _require(identity != blank, "blank-mixed", "blank cannot be a sample")
        _require(identity not in seen, "sample-identity", "sample IDs must be unique")
        seen.add(identity)
        analyte = _text(sample["analyte"], "analyte")
        _require(analyte in CONVERSION_FACTORS, "analyte-rule", "only frozen dsDNA and RNA factors are admitted")
        factor = _number(sample["conversion_factor_ng_ul"], "conversion factor", 1, 100)
        _require(math.isclose(factor, CONVERSION_FACTORS[analyte], rel_tol=RELATIVE_TOLERANCE, abs_tol=0),
                 "conversion-factor", "factor differs from declared analyte")
        _number(sample["dilution_factor"], "dilution factor", 1, 1e12)
    return value


def _reading(value, label):
    _fields(value, "replicate_id availability " + " ".join(WAVELENGTHS), label)
    _text(value["replicate_id"], "replicate id")
    availability = _text(value["availability"], "availability")
    _require(availability in {"observed", "unavailable"}, "invalid-record", "unknown reading availability")
    for key in WAVELENGTHS:
        if availability == "observed":
            _number(value[key], key, -100, 100)
        else:
            _require(value[key] is None, "unavailable-as-zero", "missing readings need null absorbance")
    return value


def compute_quant_purity(readings, rules, purity_bands=None):
    """Recompute synthetic absorbance arithmetic; no sample suitability is inferred."""
    rules = _rules(rules)
    bands = _bands(rules["purity_bands"] if purity_bands is None else purity_bands)
    _require(type(readings) is dict and "blank" in readings, "blank-control", "explicit blank required")
    _record(readings, "nuc-readings-v1", "blank samples")
    blank = _fields(readings["blank"], "sample_id reading", "blank")
    _require(_text(blank["sample_id"], "blank sample id") == rules["blank_id"],
             "blank-control", "blank identity differs from frozen rule")
    blank_reading = _reading(blank["reading"], "blank reading")
    _require(blank_reading["availability"] == "observed", "blank-control", "measured blank required")
    blank_values = {key: blank_reading[key] - blank_reading["A320"] for key in WAVELENGTHS[:-1]}
    _require(all(value >= 0 for value in blank_values.values()), "blank-control", "negative blank control")
    samples = _list(readings["samples"], "reading samples", MAX_SAMPLES)
    total = 0
    for sample in samples:
        _fields(sample, "sample_id replicates", "sample readings")
        replicates = _list(sample["replicates"], "replicate readings", MAX_REPLICATES)
        total += len(replicates)
        _require(total <= MAX_ROWS, "input-limit", "total replicate count exceeds MAX_ROWS")
    sample_rules = {sample["sample_id"]: sample for sample in rules["samples"]}
    grouped = {}
    replicate_ids = {blank_reading["replicate_id"]}
    for sample in samples:
        identity = _text(sample["sample_id"], "sample id")
        _require(identity != rules["blank_id"], "blank-mixed", "blank mixed into samples")
        _require(identity in sample_rules and identity not in grouped,
                 "sample-identity", "unknown or duplicate sample ID")
        rows = sample["replicates"]
        _require(len(rows) >= rules["minimum_replicates"], "insufficient-replicates", "frozen replicate minimum unmet")
        for row in rows:
            _reading(row, "replicate reading")
            identity_r = row["replicate_id"]
            _require(identity_r not in replicate_ids, "replicate-identity", "replicate IDs must be unique")
            replicate_ids.add(identity_r)
        grouped[identity] = rows
    _require(set(grouped) == set(sample_rules), "sample-identity", "missing samples need explicit unavailable readings")
    output = []
    for sample_rule in rules["samples"]:
        identity, analyte = sample_rule["sample_id"], sample_rule["analyte"]
        results = []
        for row in grouped[identity]:
            result = {"replicate_id": row["replicate_id"], "corrected": "unavailable",
                      "concentration_ng_ul": "unavailable", "a260_a280": "unavailable",
                      "a260_a230": "unavailable", "flags": []}
            results.append(result)
            if row["availability"] == "unavailable":
                result["flags"].append("missing-reading")
                continue
            corrected = {key: (row[key] - row["A320"]) - blank_values[key] for key in WAVELENGTHS[:-1]}
            result["corrected"] = corrected
            scale = max(abs(row[key]) for key in WAVELENGTHS)
            scale = max(scale, *(abs(blank_reading[key]) for key in WAVELENGTHS))
            if any(value < 0 for value in corrected.values()):
                result["flags"].append("negative-absorbance")
            if not _inside(corrected["A260"], rules["linear_a260_range"]["minimum"], rules["linear_a260_range"]["maximum"]):
                result["flags"].append("outside-linear-range")
            if any(corrected[key] <= RELATIVE_ZERO * scale for key in ("A230", "A280")):
                result["flags"].append("non-positive-denominator")
            if corrected["A260"] <= RELATIVE_ZERO * scale:
                result["flags"].append("degenerate-signal")
            if result["flags"]:
                continue
            result["concentration_ng_ul"] = (corrected["A260"] * sample_rule["conversion_factor_ng_ul"]
                                             * sample_rule["dilution_factor"] / rules["path_length_cm"])
            result["a260_a280"] = corrected["A260"] / corrected["A280"]
            result["a260_a230"] = corrected["A260"] / corrected["A230"]
            for ratio in ("a260_a280", "a260_a230"):
                band = bands[analyte][ratio]
                if not _inside(result[ratio], band["minimum"], band["maximum"]):
                    result["flags"].append(ratio + "-outside-band")
        sample_result = {"sample_id": identity, "analyte": analyte, "replicates": results,
                         "classification": "unavailable", "concentration_ng_ul": "unavailable",
                         "a260_a280": "unavailable", "a260_a230": "unavailable",
                         "replicate_relative_difference": "unavailable",
                         "flags": sorted({flag for row in results for flag in row["flags"]})}
        concentrations = [row["concentration_ng_ul"] for row in results]
        if all(type(value) in (int, float) for value in concentrations):
            difference = (max(concentrations) - min(concentrations)) / max(concentrations)
            _require(difference <= rules["replicate_max_relative_difference"]
                     or math.isclose(difference, rules["replicate_max_relative_difference"], rel_tol=EDGE_TOLERANCE, abs_tol=0),
                     "replicate-disagreement", "replicates exceed frozen relative agreement bound")
            sample_result["classification"] = "quantified"
            sample_result["replicate_relative_difference"] = difference
            for key in ("concentration_ng_ul", "a260_a280", "a260_a230"):
                sample_result[key] = math.fsum(row[key] for row in results) / len(results)
        output.append(sample_result)
    return {"samples": output,
            "summary": {"n": len(output),
                        "quantified": sum(row["classification"] == "quantified" for row in output),
                        "unavailable": sum(row["classification"] == "unavailable" for row in output),
                        "flagged": sum(bool(row["flags"]) for row in output)}}

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
        _require(len(actual) == len(expected), "sample-identity", "reported replicate or sample count differs")
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


def validate_nucleic_acid_quant_purity_pack(bundle):
    """Validate one immutable offline fixture without creating or changing files."""
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
        pack = _record(store.load(path.name), "nuc-pack-v1",
                       "rules frozen_rules_sha256 frozen_before_readings_read readings report evidence")
        rules = _rules(store.artifact(pack["rules"]))
        _require(_text(pack["frozen_rules_sha256"], "frozen rules hash") == pack["rules"]["sha256"]
                 and _boolean(pack["frozen_before_readings_read"], "frozen before readings read"),
                 "rule-freeze", "rules must be hash-frozen before readings are opened")
        report = _record(store.artifact(pack["report"]), "nuc-report-v1",
                         "rules_sha256 exploratory purity_bands background_rule blank_rule samples summary headline claims")
        _require(_text(report["rules_sha256"], "rules hash") == pack["rules"]["sha256"],
                 "rule-freeze", "report cites a different frozen rule revision")
        exploratory = _boolean(report["exploratory"], "exploratory")
        bands = _bands(report["purity_bands"])
        _require(all(math.isclose(bands[a][r][edge], rules["purity_bands"][a][r][edge],
                                  rel_tol=RELATIVE_TOLERANCE, abs_tol=0)
                     for a in CONVERSION_FACTORS for r in bands[a] for edge in bands[a][r]) or exploratory,
                 "post-hoc-bands", "post-outcome band change requires exploratory label")
        _require(report["background_rule"] == rules["background_rule"],
                 "background-rule", "report omits frozen A320 subtraction")
        _require(report["blank_rule"] == rules["blank_rule"], "blank-rule", "report changes frozen blank rule")
        _require(not OVERREACH.search(_text(report["headline"], "headline")),
                 "claim-overreach", "headline exceeds bounded synthetic arithmetic")
        descriptors = _list(pack["evidence"], "evidence artifacts", MAX_RECORDS, True)
        own_paths = {path.name}
        own_hashes = {store.snapshots[path.name][2]}
        for descriptor in (pack["rules"], pack["readings"], pack["report"], *descriptors):
            _fields(descriptor, "path sha256", "artifact identity")
            own_paths.add(str(_relative(descriptor["path"])))
            own_hashes.add(_text(descriptor["sha256"], "sha256"))
        evidence = {}
        for descriptor in descriptors:
            document = _record(store.artifact(descriptor), "nuc-evidence-v1", "records")
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
        result = compute_quant_purity(store.artifact(pack["readings"]), rules, bands)
        samples = _list(report["samples"], "reported samples", MAX_SAMPLES)
        _require(len(samples) == len(result["samples"]), "sample-identity", "report omits samples")
        for actual, expected in zip(samples, result["samples"]):
            _fields(actual, expected, "reported sample")
            rows = _list(actual["replicates"], "reported replicates", MAX_REPLICATES)
            _require(len(rows) == len(expected["replicates"]), "sample-identity", "report omits replicates")
            for observed, reference in [(actual, expected), *zip(rows, expected["replicates"])]:
                _require(type(observed) is dict, "invalid-record", "reported result must be an object")
                if reference["concentration_ng_ul"] == "unavailable":
                    _require(all(observed.get(key) == "unavailable"
                                 for key in ("concentration_ng_ul", "a260_a280", "a260_a230")),
                             "unavailable-quantification", "invalid readings cannot have numerical ratios or concentration")
            _same(actual, expected, "sample")
        _same(report["summary"], result["summary"], "summary")
        store.finish()
        return {"schema": "nuc-result-v1", "fixture": "synthetic fixture", "status": "arithmetic-only",
                "review": "unavailable", "stages": list(STAGES), "exploratory": exploratory,
                "inputs": [{"path": name, "sha256": item[2]} for name, item in sorted(store.snapshots.items())],
                "computation": result, "claims": report["claims"],
                "limitations": ["Synthetic readings establish software arithmetic only.",
                                "Conversion factors, path length, dilution and blank matching are assumptions.",
                                "Ratio bands and replicate agreement do not establish sample suitability.",
                                "Hash declarations cannot establish historical freeze timing or independence.",
                                "Independent record, source and method review remains unavailable."]}
    finally:
        store.close()
