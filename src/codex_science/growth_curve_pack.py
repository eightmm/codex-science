"""Read-only synthetic OD admission and bounded model-free growth arithmetic."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import statistics


STAGES = ("01-rule-freeze", "02-data-qc", "03-per-well", "04-group-summary", "05-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_JSON_VALUES = 4_000_000
MAX_WELLS = 384
MAX_POINTS = 4096
MAX_WINDOW_WORK = 2_000_000
MAX_RECORDS = 128
MAX_ITEMS = 8192
MAX_STRING = 4096
MAX_DEPTH = 32
MAX_NUMBER = 1e100
POSITIVE = {"supported", "replicated", "suggestive"}
STATUSES = POSITIVE | {"planned", "conflicting", "unsupported", "withdrawn", "unavailable"}
PARAMETERS = ("maximum_specific_growth_rate", "lag_time", "carrying_capacity", "area_under_curve", "doubling_time")
WORDING_FAMILIES = (
    "caus*, mechanis*, therap*, clinic*, efficac*, effective*, treat*, cure*, prevent*, "
    "recommend*, prescri*, bind*, affinit*, inhibit*, activat*, regulat*, "
    "drive/drives/driv*, induc*"
)
OVERREACH = re.compile(
    r"\b(?:caus\w*|mechanis\w*|therap\w*|clinic\w*|efficac\w*|effective\w*|"
    r"treat\w*|cure\w*|prevent\w*|recommend\w*|prescri\w*|bind\w*|affinit\w*|"
    r"inhibit\w*|activat\w*|regulat\w*|driv\w*|induc\w*|fitness|resistan\w*|"
    r"drug[\s-]+effect\w*|truth|physical[\s-]+validity|patient[\s-]+benefit\w*)\b", re.I,
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


def _protocol(value):
    _record(value, "growth-protocol-v1", "strains conditions assignments blank_wells background "
            "blank_stability linear_range_upper model fit_method start_values tolerance window_rule "
            "window_points minimum_points maximum_contamination_flags time_grid time_unit minimum_wells")
    strains = _names(value["strains"], "strains", MAX_WELLS)
    conditions = _names(value["conditions"], "conditions", MAX_WELLS)
    blanks = _names(value["blank_wells"], "blank wells", MAX_WELLS)
    assignments = _list(value["assignments"], "assignments", MAX_WELLS)
    seen = set(blanks)
    for item in assignments:
        _fields(item, "well strain condition biological_unit replicate_type", "assignment")
        well = _text(item["well"], "well")
        strain = _text(item["strain"], "strain")
        condition = _text(item["condition"], "condition")
        _text(item["biological_unit"], "biological unit")
        replicate = _text(item["replicate_type"], "replicate type")
        _require(well not in seen, "well-identity", "blank and replicate well identities must be unique")
        seen.add(well)
        _require(strain in strains and condition in conditions and replicate in {"technical", "biological"},
                 "invalid-record", "assignment outside the frozen design")
    background = _text(value["background"], "background")
    _require(background in {"subtract-pointwise-blank-mean", "none"}, "invalid-record", "unsupported background rule")
    _number(value["blank_stability"], "blank stability", 0, 100)
    _number(value["linear_range_upper"], "linear range upper", 1e-12, 100)
    _require(value["model"] == "model-free-maximum-slope" and value["fit_method"] == "closed-form-ols"
             and value["window_rule"] == "largest-log-od-slope-first-tie",
             "unsupported-method", "freeze the model-free window and closed-form OLS method")
    _require(type(value["start_values"]) is list and not value["start_values"],
             "unsupported-method", "closed-form OLS has no iterative start values")
    _number(value["tolerance"], "tolerance", 1e-15, 1e-3)
    _number(value["window_points"], "window points", 2, MAX_POINTS, True)
    _number(value["minimum_points"], "minimum points", value["window_points"], MAX_POINTS, True)
    _number(value["maximum_contamination_flags"], "maximum contamination flags", 0, MAX_WELLS, True)
    _require(value["time_grid"] == "equal-no-interpolation", "time-grid", "only frozen equal grids are implemented")
    _text(value["time_unit"], "time unit")
    _number(value["minimum_wells"], "minimum wells", 2, MAX_WELLS, True)
    return value


def _slope(times, values):
    # Centering avoids cancellation for measurements with large absolute time origins.
    center = statistics.fmean(times)
    mean = statistics.fmean(values)
    denominator = math.fsum((time - center) ** 2 for time in times)
    _require(denominator > 0, "degenerate-window", "time variance must be positive")
    slope = math.fsum((time - center) * (value - mean) for time, value in zip(times, values)) / denominator
    _number(slope, "slope", -MAX_NUMBER)
    return slope, center, mean


def _parameter(value="unavailable", reason="unavailable"):
    return {"value": value, "status": "reliable" if reason == "none" else "unreliable", "reason": reason}


def _well_parameters(times, corrected, raw, protocol, well):
    reasons = []
    if max(raw) > protocol["linear_range_upper"]:
        reasons.append("saturation")
    if len(times) < protocol["minimum_points"]:
        reasons.append("too-few-points")
    if not well["fit_converged"]:
        reasons.append("non-converged")
    if well["contamination"] or well["edge"] or well["evaporation"]:
        reasons.append("declared-qc-flag")
    if reasons:
        return {name: _parameter(reason=",".join(reasons)) for name in PARAMETERS}, []
    # Zero and negative subtracted OD are refused before any logarithm, not clipped.
    _require(all(value > 0 for value in corrected), "nonpositive-log-od", "log OD requires strictly positive corrected values")
    logs = [math.log(value) for value in corrected]
    width = protocol["window_points"]
    best = None
    for start in range(len(times) - width + 1):
        slope, center, mean = _slope(times[start:start + width], logs[start:start + width])
        if best is None or (slope > best[0] and not math.isclose(slope, best[0], rel_tol=protocol["tolerance"], abs_tol=0)):
            best = slope, start, center, mean
    rate, start, center, mean = best
    result = {name: _parameter(reason="nonpositive-growth") for name in PARAMETERS}
    result["carrying_capacity"] = _parameter(max(corrected), "none")
    auc = math.fsum((times[index + 1] - time) * (corrected[index + 1] + corrected[index]) / 2
                    for index, time in enumerate(times[:-1]))
    result["area_under_curve"] = _parameter(auc, "none")
    if rate > 0:
        result["maximum_specific_growth_rate"] = _parameter(rate, "none")
        result["doubling_time"] = _parameter(math.log(2) / rate, "none")
        # OD-space tangent at the same frozen log-OD window; negative lag is retained.
        raw_slope, raw_center, raw_mean = _slope(times[start:start + width], corrected[start:start + width])
        if raw_slope > 0:
            result["lag_time"] = _parameter(raw_center - raw_mean / raw_slope, "none")
    for item in result.values():
        if item["status"] == "reliable":
            _number(item["value"], "parameter", -MAX_NUMBER)
    return result, list(range(start, start + width))


def compute_growth_curve(data, protocol):
    """Check in-memory synthetic records and compute descriptive per-well quantities."""
    protocol = _protocol(protocol)
    _record(data, "growth-data-v1", "time_unit background_applied wells")
    _require(_text(data["time_unit"], "time unit") == protocol["time_unit"], "time-grid", "mixed time units refused")
    _require(_text(data["background_applied"], "background applied") == protocol["background"],
             "blank-subtraction", "declared subtraction must match the frozen rule")
    wells = _list(data["wells"], "wells", MAX_WELLS)
    by_well = {}
    grid = None
    contamination = 0
    for well in wells:
        _fields(well, "well times od contamination edge evaporation fit_converged", "well")
        identity = _text(well["well"], "well")
        _require(identity not in by_well, "well-identity", "duplicate well")
        times = _list(well["times"], "times", MAX_POINTS)
        od = _list(well["od"], "OD", MAX_POINTS)
        _require(len(times) == len(od), "time-grid", "time and OD lengths must agree")
        for time in times:
            _number(time, "time", 0, 1e9)
        for value in od:
            _number(value, "OD", 0, 100)
        _require(all(later > earlier for earlier, later in zip(times, times[1:])),
                 "time-grid", "times must be strictly increasing")
        _require(grid is None or times == grid, "time-grid", "well time grid mismatch cannot be ignored")
        grid = times
        for name in ("contamination", "edge", "evaporation", "fit_converged"):
            _boolean(well[name], name)
        contamination += well["contamination"]
        by_well[identity] = well
    assignments = protocol["assignments"]
    _require(set(by_well) == set(protocol["blank_wells"]) | {item["well"] for item in assignments},
             "well-identity", "well set must equal frozen blank and replicate identities")
    _require(contamination <= protocol["maximum_contamination_flags"],
             "contamination-limit", "contamination exceeds the frozen maximum")
    blanks = [by_well[identity] for identity in protocol["blank_wells"]]
    for blank in blanks:
        _require(max(blank["od"]) - min(blank["od"]) <= protocol["blank_stability"]
                 and not any(blank[name] for name in ("contamination", "edge", "evaporation")),
                 "unstable-blank", "blank stability or blank QC control failed")
    background = [statistics.fmean(blank["od"][index] for blank in blanks) for index in range(len(grid))]
    _require(len(assignments) * max(0, len(grid) - protocol["window_points"] + 1) * protocol["window_points"] <= MAX_WINDOW_WORK,
             "input-limit", "aggregate window arithmetic budget exceeded")
    results = []
    grouped = {}
    for assignment in assignments:
        well = by_well[assignment["well"]]
        corrected = ([value - background[index] for index, value in enumerate(well["od"])]
                     if protocol["background"] == "subtract-pointwise-blank-mean" else list(well["od"]))
        parameters, window = _well_parameters(grid, corrected, well["od"], protocol, well)
        row = {**assignment, "parameters": parameters, "window_indices": window}
        results.append(row)
        grouped.setdefault((assignment["strain"], assignment["condition"]), []).append(row)
    summaries = []
    for (strain, condition), rows in grouped.items():
        metrics = {}
        for name in PARAMETERS:
            reliable = [row for row in rows if row["parameters"][name]["status"] == "reliable"]
            values = [row["parameters"][name]["value"] for row in reliable]
            count = len(values)
            summary = {"n": count, "well_ids": [row["well"] for row in reliable],
                       "n_biological_units": len({row["biological_unit"] for row in reliable}),
                       "replicate_unit": "well", "mean": "unavailable", "standard_error": "unavailable",
                       "status": "unavailable", "reason": "too-few-reliable-wells"}
            if count >= protocol["minimum_wells"]:
                mean = statistics.fmean(values)
                deviation = statistics.stdev(values)
                summary.update(mean=mean, status="descriptive", reason="none")
                if not math.isclose(min(values), max(values), rel_tol=protocol["tolerance"], abs_tol=0):
                    summary["standard_error"] = deviation / math.sqrt(count)
                else:
                    summary["reason"] = "zero-variance-uncertainty-unavailable"
            metrics[name] = summary
        summaries.append({"strain": strain, "condition": condition, "parameters": metrics})
    return {"wells": results, "groups": summaries, "carrying_capacity_definition": "observed-maximum-proxy"}


def _compare(actual, expected, code="reported-number"):
    if type(expected) is dict:
        _fields(actual, expected, "reported result")
        for name in expected:
            _compare(actual[name], expected[name], code)
    elif type(expected) is list:
        _list(actual, "reported rows", max(MAX_WELLS, MAX_POINTS), True)
        _require(len(actual) == len(expected), code, "reported list length differs")
        for left, right in zip(actual, expected):
            _compare(left, right, code)
    elif type(expected) in (int, float):
        _number(actual, "reported number", -MAX_NUMBER, integer=type(expected) is int)
        _require(math.isclose(actual, expected, rel_tol=1e-9, abs_tol=0), code, "reported number differs from reference")
    else:
        _require(type(actual) is type(expected) and actual == expected, code, "reported value differs from reference")


def _claims(claims, evidence):
    claims = _list(claims, "claims", MAX_RECORDS, True)
    seen = set()
    for claim in claims:
        _fields(claim, "id kind status text evidence", "claim")
        identity = _text(claim["id"], "claim id")
        kind = _text(claim["kind"], "claim kind")
        status = _text(claim["status"], "claim status")
        text = _text(claim["text"], "claim text")
        _require(identity not in seen, "invalid-record", "duplicate claim id")
        seen.add(identity)
        _require(kind in {"descriptive", "associational"} and not OVERREACH.search(text),
                 "claim-overreach", "growth arithmetic cannot establish biological or medical conclusions")
        _require(status in STATUSES, "invalid-record", "unknown claim status")
        ids = _names(claim["evidence"], "claim evidence", MAX_RECORDS, True)
        _require(ids or status == "unavailable", "missing-evidence", "empty evidence requires unavailable")
        _require(status != "unavailable" or not ASSERTION.search(text),
                 "unavailable-positive", "unavailable claim asserts positive evidence")
        for identity in ids:
            _require(identity in evidence, "missing-evidence", "unknown evidence identity")
            record = evidence[identity]
            _require("unavailable" not in (record["kind"], record["result"]) or status == "unavailable",
                     "unavailable-evidence", "unavailable evidence requires an unavailable claim")
            _require(status not in POSITIVE or not any(NON_EVIDENCE.search(record[name]) for name in ("kind", "result")),
                     "non-evidence-support", "computed records and review approval cannot support positive claims")
        _require(status != "replicated", "claim-replication", "synthetic fixtures cannot establish independent replication")


def validate_growth_curve_pack(bundle):
    """Validate immutable fixture inputs and a supplied report; write nothing."""
    try:
        value = _text(os.fspath(bundle), "bundle path")
        _require(all(ord(char) >= 32 for char in value), "input-path", "control character in bundle path")
        path = Path(os.path.abspath(value))
    except (TypeError, ValueError) as error:
        raise ValueError("input-path: invalid bundle path") from error
    store = _Bundle(path.parent)
    try:
        pack = _record(store.load(path.name), "growth-pack-v1",
                       "protocol frozen_protocol_sha256 frozen_before_od_read data report evidence")
        protocol = _protocol(store.artifact(pack["protocol"]))
        _require(_text(pack["frozen_protocol_sha256"], "frozen protocol hash") == pack["protocol"]["sha256"]
                 and _boolean(pack["frozen_before_od_read"], "frozen before OD read"),
                 "protocol-freeze", "protocol hash must be frozen before reading OD values")
        report = _record(store.artifact(pack["report"]), "growth-report-v1",
                         "protocol_sha256 exploratory window_points computation headline claims")
        _require(_text(report["protocol_sha256"], "protocol hash") == pack["protocol"]["sha256"],
                 "protocol-freeze", "report protocol identity differs")
        exploratory = _boolean(report["exploratory"], "exploratory")
        width = _number(report["window_points"], "reported window points", 2, MAX_POINTS, True)
        _require(width == protocol["window_points"] or exploratory,
                 "post-outcome-window", "changed exponential window requires an exploratory label")
        used = dict(protocol, window_points=width, minimum_points=max(width, protocol["minimum_points"]))
        result = compute_growth_curve(store.artifact(pack["data"]), used)
        _require(not OVERREACH.search(_text(report["headline"], "headline")),
                 "claim-overreach", "headline exceeds offline growth arithmetic")
        descriptors = _list(pack["evidence"], "evidence artifacts", MAX_RECORDS, True)
        own_paths = {path.name}
        own_hashes = {store.snapshots[path.name][2]}
        for descriptor in (pack["protocol"], pack["data"], pack["report"], *descriptors):
            _fields(descriptor, "path sha256", "artifact identity")
            own_paths.add(str(_relative(descriptor["path"])))
            own_hashes.add(_text(descriptor["sha256"], "sha256"))
        evidence = {}
        for descriptor in descriptors:
            document = _record(store.artifact(descriptor), "growth-evidence-v1", "records")
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
                             "external-alias", "external label aliases the study's own artifact")
                evidence[identity] = record
        # Evidence boundaries take precedence over report arithmetic discrepancies.
        _claims(report["claims"], evidence)
        _fields(report["computation"], result, "computation")
        reported_wells = _list(report["computation"]["wells"], "reported wells", MAX_WELLS)
        _require(len(reported_wells) == len(result["wells"]), "reported-number", "well count differs")
        for actual, expected in zip(reported_wells, result["wells"]):
            _fields(actual, expected, "reported well")
            _fields(actual["parameters"], PARAMETERS, "parameters")
            for name in PARAMETERS:
                if expected["parameters"][name]["reason"] != "none":
                    code = "saturation-capacity" if name == "carrying_capacity" and "saturation" in expected["parameters"][name]["reason"] else "unreliable-parameter"
                    _compare(actual["parameters"][name], expected["parameters"][name], code)
        groups = _list(report["computation"]["groups"], "reported groups", MAX_WELLS)
        _require(len(groups) == len(result["groups"]), "reported-number", "group count differs")
        for actual, expected in zip(groups, result["groups"]):
            _fields(actual, expected, "reported group")
            _fields(actual["parameters"], PARAMETERS, "group parameters")
            for name in PARAMETERS:
                metric = _fields(actual["parameters"][name], expected["parameters"][name], "group summary")
                _compare(metric["n_biological_units"], expected["parameters"][name]["n_biological_units"], "technical-replication")
                _compare(metric["replicate_unit"], "well", "technical-replication")
                _compare(metric["well_ids"], expected["parameters"][name]["well_ids"], "unreliable-summary")
        _compare(report["computation"], result)
        store.finish()
        return {"schema": "growth-result-v1", "fixture": "synthetic fixture", "status": "offline-arithmetic-only",
                "review": "unavailable", "stages": list(STAGES), "exploratory": exploratory,
                "inputs": [{"path": name, "sha256": item[2]} for name, item in sorted(store.snapshots.items())],
                "computation": result, "claims": report["claims"],
                "limitations": ["Synthetic fixtures establish arithmetic behavior only.",
                                "Observed maximum OD is a carrying-capacity proxy, not an asymptotic fit.",
                                "Well-level standard errors do not establish biological replication.",
                                "Hashes cannot establish historical freeze timing or real independence.",
                                "Independent source, record and method review remains unavailable."]}
    except (OSError, OverflowError, RecursionError) as error:
        raise ValueError("invalid-input: bounded readable finite inputs required") from error
    finally:
        store.close()


def _pairs(pairs):
    _require(len(pairs) <= MAX_ITEMS, "input-limit", "JSON object too large")
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
    upper = 1 + raw.count(b",") + sum(1 for _ in re.finditer(rb"[\[{](?=\s*[^\s\]}])", raw))
    _require(upper <= allowance, "input-limit", "bundle JSON value allowance exceeded")
    try:
        root = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=_constant, parse_int=_int, parse_float=_float)
        _require(type(root) is dict, "invalid-json", "JSON root must be an object")
        pending = [(root, 0)]
        while pending:
            value, depth = pending.pop()
            _require(depth <= MAX_DEPTH, "invalid-json", "JSON nesting limit exceeded")
            if type(value) is dict:
                _require(len(value) <= MAX_ITEMS, "input-limit", "JSON object too large")
                children = list(value.keys()) + list(value.values())
            elif type(value) is list:
                _require(len(value) <= MAX_ITEMS, "input-limit", "JSON list too large")
                children = value
            else:
                if type(value) is str:
                    _text(value, "JSON string")
                continue
            pending.extend((child, depth + 1) for child in children)
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
        self.rechecked = None
        self.parsed = {}
        self.json_values = 0
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
            _require(len(self.snapshots) < MAX_RECORDS, "input-limit", "too many artifact paths")
            raw, signature = self._read(name)
            identity = signature[:2]
            if identity not in self.cache:
                self.cache[identity] = (raw, signature, hashlib.sha256(raw).hexdigest())
                self.total_bytes += len(raw)
            self.snapshots[name] = self.cache[identity]
        raw, signature, actual = self.snapshots[name]
        if digest is not None:
            _text(digest, "sha256")
            _require(re.fullmatch(r"[0-9a-f]{64}", digest) is not None and digest == actual,
                     "input-hash", "artifact hash differs from parsed bytes")
        if not parse:
            return actual
        identity = signature[:2]
        if identity not in self.parsed:
            record, count = _json(raw, MAX_JSON_VALUES - self.json_values)
            self.json_values += count
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
