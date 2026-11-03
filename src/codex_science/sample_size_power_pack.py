"""Offline frozen-assumption normal reference; arithmetic is never study adequacy."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat


STAGES = ("01-freeze", "02-qc", "03-computation", "04-consistency", "05-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_TOTAL_NODES = 4000000
MAX_ARTIFACTS = 128
MAX_ITEMS = 1024
MAX_TEXT = 4096
MAX_DEPTH = 32
MAX_CLAIMS = 100
MAX_SUPPORT = 32
MAX_GRID = 9
MAX_N = 1000000000
MAX_MULTIPLICITY = 10000
MAX_NUMBER = 1e100
MIN_PROBABILITY = 1e-12
POWER_TOLERANCE = 1e-9
POSITIVE = {"supported", "replicated", "suggestive"}
STATUSES = POSITIVE | {"planned", "conflicting", "unsupported", "withdrawn", "unavailable"}
WORDING_FAMILIES = (
    "caus", "mechanis", "therap", "clinic", "efficac", "effective", "treat", "cure",
    "prevent", "recommend", "prescri", "bind", "affinit", "inhibit", "activat",
    "regulat", "driv", "induc",
)
OVERREACH = re.compile(
    r"\b(?:" + "|".join(word + r"\w*" for word in WORDING_FAMILIES)
    + r"|adequa\w*|benefit\w*|well[\s-]+powered|no[\s-]+effect|truth|physical[\s-]+validity"
    + r"|observed[\s-]+power|post[\s-]*hoc[\s-]+power)\b", re.I,
)
ASSERTION = re.compile(r"\b(?:supported|replicated|suggestive|significan\w*)\b", re.I)
NON_EVIDENCE = re.compile(r"review|approv|comput|numer|agreement|truth|physical|clinic", re.I)
PARAMETERS = ("alpha", "adjusted_alpha", "target_power", "allocation_ratio", "nuisance",
              "effect", "attrition", "multiplicity", "minimum_n", "sensitivity_points", "outcome_range")


def _require(condition, code, message):
    if not condition:
        raise ValueError(f"{code}: {message}")


def _fields(value, fields, label):
    _require(type(value) is dict, "invalid-record", f"{label} must be an object")
    _require(set(value) == set(fields), "invalid-record", f"{label} has missing or unknown fields")
    return value


def _text(value, label, empty=False):
    _require(type(value) is str and len(value) <= MAX_TEXT and (empty or bool(value.strip())),
             "invalid-record", f"{label} must be bounded text")
    return value


def _items(value, label, limit, empty=False):
    _require(type(value) is list and (empty or bool(value)), "invalid-record", f"{label} must be a list")
    _require(len(value) <= limit, "input-limit", f"{label} exceeds {limit}")
    return value


def _number(value, label, low=-MAX_NUMBER, high=MAX_NUMBER, integer=False):
    valid = type(value) is int if integer else type(value) in (int, float)
    _require(valid and -MAX_NUMBER <= value <= MAX_NUMBER and math.isfinite(value) and low <= value <= high,
             "invalid-number", f"{label} must be a finite declared number in [{low}, {high}]")
    return value


def _boolean(value, label):
    _require(type(value) is bool, "invalid-record", f"{label} must be boolean")
    return value


def _record(value, schema, fields):
    _fields(value, ("schema", "schema_version", "fixture", *fields), schema)
    _require(value["schema"] == schema, "invalid-record", f"expected {schema}")
    _number(value["schema_version"], "schema_version", 1, 1, integer=True)
    _boolean(value["fixture"], "fixture")
    return value


def _pairs(pairs):
    _require(len(pairs) <= MAX_ITEMS, "input-limit", "too many object fields")
    result = {}
    for key, value in pairs:
        _require(key not in result, "invalid-json", "duplicate JSON key")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("invalid-json: non-finite JSON number")


def _integer(value):
    _require(len(value.lstrip("-")) <= 101, "invalid-json", "huge JSON integer")
    return _number(int(value), "JSON integer")


def _json(raw, allowance):
    estimate = 1 + raw.count(b",") + sum(1 for _ in re.finditer(rb"[\[{](?=\s*[^\s\]}])", raw))
    _require(estimate <= allowance, "input-limit", "bundle JSON value allowance exceeded before parse")
    try:
        root = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant,
                          parse_int=_integer, parse_float=lambda value: _number(float(value), "JSON number"))
        _require(type(root) is dict, "invalid-json", "JSON root must be an object")
        pending = [(root, 0)]
        nodes = 0
        while pending:
            value, depth = pending.pop()
            nodes += 1
            _require(nodes <= allowance, "input-limit", "bundle JSON value allowance exceeded")
            if type(value) in (list, dict):
                _require(depth <= MAX_DEPTH, "invalid-json", "JSON nesting exceeds MAX_DEPTH")
                _require(len(value) <= MAX_ITEMS, "input-limit", "JSON container exceeds MAX_ITEMS")
                if type(value) is dict:
                    for key in value:
                        _text(key, "JSON key")
                children = value.values() if type(value) is dict else value
                pending.extend((child, depth + 1) for child in children)
            elif type(value) is str:
                _text(value, "JSON string", empty=True)
        # Charge the conservative preparse estimate, including punctuation inside strings.
        return root, max(nodes, estimate)
    except (UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError("invalid-json: bounded finite UTF-8 JSON object required") from error
    except json.JSONDecodeError as error:
        raise ValueError("invalid-json: malformed JSON") from error


def _relative(value):
    value = _text(value, "artifact path")
    path = PurePosixPath(value)
    _require(not path.is_absolute() and path.as_posix() == value and value != "."
             and ".." not in path.parts and "\\" not in value and not re.match(r"^[A-Za-z]:", value)
             and all(ord(char) >= 32 for char in value), "input-path", "canonical bundle-relative path required")
    return path


def _signature(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _open_root(root):
    """Pin the full ancestor chain; a surviving root inode alone is insufficient."""
    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_DIRECTORY
    descriptor = os.open(root.anchor, flags)
    chain = [_signature(os.fstat(descriptor))[:2]]
    try:
        for part in root.parts[1:]:
            before = os.lstat(part, dir_fd=descriptor)
            _require(stat.S_ISDIR(before.st_mode), "input-root", "bundle ancestors must be real directories")
            child = os.open(part, flags, dir_fd=descriptor)
            opened = os.fstat(child)
            if _signature(before)[:2] != _signature(opened)[:2]:
                os.close(child)
                raise ValueError("input-root: ancestor changed while pinning")
            chain.append(_signature(opened)[:2])
            os.close(descriptor)
            descriptor = child
        return descriptor, tuple(chain)
    except BaseException:
        os.close(descriptor)
        raise


class _Bundle:
    def __init__(self, path):
        _require(isinstance(path, (str, Path)) and "\x00" not in str(path), "input-path", "invalid bundle path")
        absolute = Path(os.path.abspath(path))
        self.root, self.entry = absolute.parent, absolute.name
        self.cache, self.artifacts = {}, {}
        self.bytes_read = self.nodes_read = 0
        self.descriptor, self.chain = _open_root(self.root)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        os.close(self.descriptor)

    def read(self, path, checked=None):
        flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
        directory = os.dup(self.descriptor)
        try:
            for part in path.parts[:-1]:
                before = os.lstat(part, dir_fd=directory)
                _require(stat.S_ISDIR(before.st_mode), "input-file", "artifact ancestors must be real directories")
                child = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
                opened = os.fstat(child)
                if _signature(before)[:2] != _signature(opened)[:2]:
                    os.close(child)
                    raise ValueError("input-file: artifact ancestor changed while opening")
                os.close(directory)
                directory = child
            before = os.lstat(path.name, dir_fd=directory)
            _require(stat.S_ISREG(before.st_mode) and before.st_size <= MAX_BYTES,
                     "input-file", "expected a regular artifact within MAX_BYTES")
            descriptor = os.open(path.name, flags, dir_fd=directory)
            with os.fdopen(descriptor, "rb") as handle:
                opened = os.fstat(handle.fileno())
                _require(stat.S_ISREG(opened.st_mode) and opened.st_size <= MAX_BYTES
                         and _signature(before) == _signature(opened), "input-file", "artifact changed at open")
                signature = _signature(opened)
                identity = signature[:2]
                cached = self.artifacts.get(identity)
                if cached is not None:
                    _require(signature == cached[2], "input-changed", "cached artifact changed")
                    if checked is None or identity in checked:
                        return None, signature
                limit = MAX_BYTES if checked is not None else min(MAX_BYTES, MAX_TOTAL_BYTES - self.bytes_read)
                _require(opened.st_size <= limit, "input-limit", "aggregate byte allowance exceeded before read")
                raw = handle.read(limit + 1)
                after = os.fstat(handle.fileno())
            _require(len(raw) <= limit and len(raw) == opened.st_size and signature == _signature(after),
                     "input-file", "artifact grew or changed during bounded read")
            if checked is None:
                self.bytes_read += len(raw)
            return raw, signature
        finally:
            os.close(directory)

    def snapshot(self, path):
        name = path.as_posix()
        if name not in self.cache:
            _require(len(self.cache) < MAX_ARTIFACTS, "input-limit", "too many artifact paths")
            raw, signature = self.read(path)
            identity = signature[:2]
            if raw is not None:
                value, nodes = _json(raw, MAX_TOTAL_NODES - self.nodes_read)
                self.nodes_read += nodes
                self.artifacts[identity] = (value, hashlib.sha256(raw).hexdigest(), signature)
            self.cache[name] = self.artifacts[identity]
        return self.cache[name][:2]

    def load(self, identity):
        _fields(identity, ("path", "sha256"), "artifact identity")
        path = _relative(identity["path"])
        digest = _text(identity["sha256"], "SHA-256")
        _require(re.fullmatch(r"[0-9a-f]{64}", digest) is not None, "input-hash", "invalid SHA-256")
        value, actual = self.snapshot(path)
        _require(actual == digest, "input-hash", "artifact hash mismatch")
        return value

    def _recheck_root(self):
        descriptor, chain = _open_root(self.root)
        try:
            _require(chain == self.chain, "input-changed", "bundle root or ancestor replaced")
        finally:
            os.close(descriptor)

    def recheck(self):
        self._recheck_root()
        checked = set()
        for name, (_, digest, signature) in self.cache.items():
            raw, current = self.read(_relative(name), checked)
            _require(current == signature and (raw is None or hashlib.sha256(raw).hexdigest() == digest),
                     "input-changed", "artifact replaced or modified during validation")
            checked.add(current[:2])
        self._recheck_root()


def _time(value):
    _text(value, "timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("assumption-freeze: invalid timestamp") from error
    _require(parsed.utcoffset() is not None, "assumption-freeze", "timezone-aware timestamp required")
    return parsed


def _source(record):
    _record(record, "sample-size-power-source-v1", ("study_id", "kind", "result", "text"))
    for key in ("study_id", "kind", "result", "text"):
        _text(record[key], key)
    return record


def _assumptions(record):
    _record(record, "sample-size-power-assumptions-v1", (
        "study_id", "setting", "outcome_type", "sidedness", "one_sided_justification", *PARAMETERS))
    _text(record["study_id"], "study_id")
    setting = _text(record["setting"], "setting")
    _require(setting in {"laboratory", "preclinical"}, "domain-boundary", "only laboratory or preclinical planning")
    outcome = _text(record["outcome_type"], "outcome_type")
    _require(outcome in {"continuous", "binary"}, "invalid-record", "unknown outcome type")
    sidedness = _text(record["sidedness"], "sidedness")
    _require(sidedness in {"one-sided", "two-sided"}, "invalid-record", "unknown sidedness")
    rationale = _text(record["one_sided_justification"], "one-sided justification", empty=True)
    _require(sidedness != "one-sided" or bool(rationale.strip()), "one-sided-justification",
             "one-sided test needs a frozen directional justification")
    values = {}
    for key in PARAMETERS:
        fields = ("value", "source", "assumption", "rationale") + (("uncertainty",) if key == "nuisance" else ())
        parameter = _fields(record[key], fields, key)
        _boolean(parameter["assumption"], f"{key} assumption")
        _text(parameter["rationale"], f"{key} rationale")
        _require(parameter["source"] is not None or parameter["assumption"], "missing-source",
                 f"{key} needs a source record or explicit assumption label")
        if parameter["source"] is not None:
            _fields(parameter["source"], ("path", "sha256"), f"{key} source")
        if key == "outcome_range":
            bounds = _items(parameter["value"], key, 2)
            _require(len(bounds) == 2, "invalid-record", "outcome_range needs two bounds")
            values[key] = [_number(item, key) for item in bounds]
        else:
            values[key] = _number(parameter["value"], key,
                                  integer=key in {"multiplicity", "minimum_n", "sensitivity_points"})
    alpha, adjusted, power = (values[key] for key in ("alpha", "adjusted_alpha", "target_power"))
    _require(0 < alpha < 1 and 0 < adjusted < 1 and 0 < power < 1,
             "probability-range", "alpha and power must be in (0,1)")
    count = _number(values["multiplicity"], "multiplicity", 1, MAX_MULTIPLICITY, integer=True)
    _require(math.isclose(adjusted, alpha / count, rel_tol=1e-12, abs_tol=0),
             "multiplicity-correction", "adjusted alpha must equal family alpha divided by frozen count")
    _require(MIN_PROBABILITY <= adjusted and power <= 1 - MIN_PROBABILITY and power > adjusted,
             "numerical-resolution", "power must exceed adjusted alpha within reference precision")
    _number(values["allocation_ratio"], "allocation ratio", 0.001, 1000)
    _number(values["minimum_n"], "minimum_n", 2, MAX_N, integer=True)
    _number(values["sensitivity_points"], "sensitivity_points", 2, MAX_GRID, integer=True)
    _require(0 <= values["attrition"] < 1, "attrition-range", "attrition must be in [0,1)")
    bounds = _items(record["nuisance"]["uncertainty"], "nuisance uncertainty", 2)
    _require(len(bounds) == 2, "invalid-record", "nuisance uncertainty needs two endpoints")
    low, high = [_number(item, "uncertainty") for item in bounds]
    nuisance, effect = values["nuisance"], values["effect"]
    _require(0 < low <= nuisance <= high, "nuisance-range", "positive nuisance within frozen uncertainty required")
    lower, upper = values["outcome_range"]
    _require(lower < upper and 0 < effect <= upper - lower, "effect-range", "effect exceeds plausible outcome range")
    if outcome == "binary":
        _require((lower, upper) == (0, 1) and high < 1 and high + effect < 1,
                 "effect-range", "control and alternative proportions must stay in (0,1) across uncertainty")
    _require(record["effect"]["source"] is not None, "effect-prior", "minimum effect requires a prior source record")
    return values, (low, high)


def normal_quantile(probability):
    """Invert Phi using 100 bisections on erf, without a rounded z lookup table."""
    _number(probability, "quantile probability")
    _require(MIN_PROBABILITY / 2 <= probability <= 1 - MIN_PROBABILITY / 2,
             "numerical-resolution", "quantile probability outside reference precision")
    low, high = -9.0, 9.0
    for _ in range(100):
        midpoint = (low + high) / 2
        if (1 + math.erf(midpoint / math.sqrt(2))) / 2 < probability:
            low = midpoint
        else:
            high = midpoint
    return (low + high) / 2


def _cdf(value):
    return (1 + math.erf(value / math.sqrt(2))) / 2


def _scenario(record, values, nuisance, critical, target_z):
    ratio, effect = values["allocation_ratio"], values["effect"]
    if record["outcome_type"] == "continuous":
        variance = nuisance ** 2 * (1 + 1 / ratio)
    else:
        alternative = nuisance + effect
        variance = math.fsum((nuisance * (1 - nuisance), alternative * (1 - alternative) / ratio))
    scale = math.sqrt(variance) / effect * (critical + target_z)
    _require(math.isfinite(scale) and 0 < scale <= math.sqrt(MAX_N),
             "sample-size-limit", "required size exceeds reference bound")
    first = max(values["minimum_n"], math.ceil(scale ** 2))
    second = max(values["minimum_n"], math.ceil(ratio * first))
    _require(second <= MAX_N, "sample-size-limit", "second arm exceeds reference bound")
    retained = 1 - values["attrition"]
    enrolled = [math.ceil(first / retained), math.ceil(second / retained)]
    _require(max(enrolled) <= MAX_N, "sample-size-limit", "attrition-inflated size exceeds reference bound")
    if record["outcome_type"] == "continuous":
        se = nuisance * math.sqrt(1 / first + 1 / second)
        detectable = (critical + target_z) * se
    else:
        alternative = nuisance + effect
        se = math.sqrt(math.fsum((nuisance * (1 - nuisance) / first,
                                 alternative * (1 - alternative) / second)))
        squared = (critical + target_z) ** 2
        a = 1 + squared / second
        b = -squared * (1 - 2 * nuisance) / second
        c = -squared * nuisance * (1 - nuisance) * (1 / first + 1 / second)
        discriminant = math.sqrt(b ** 2 - 4 * a * c)
        detectable = ((-b + discriminant) / (2 * a) if b <= 0 else -2 * c / (b + discriminant))
        _require(0 < nuisance + detectable < 1, "effect-range", "no feasible binary detectable effect")
    _require(math.isfinite(se) and se > 0, "degenerate-design", "positive finite standard error required")
    displacement = effect / se
    power = _cdf(displacement - critical)
    if record["sidedness"] == "two-sided":
        power = math.fsum((power, _cdf(-displacement - critical)))
    return {"nuisance": nuisance, "analyzable_n": [first, second], "enrolled_n": enrolled,
            "power": power, "minimum_detectable_effect": detectable}


def reference_computation(assumptions):
    """Compute prospective normal arithmetic; source authenticity needs bundle validation."""
    try:
        values, (low, high) = _assumptions(assumptions)
        divisor = 2 if assumptions["sidedness"] == "two-sided" else 1
        critical = normal_quantile(1 - values["adjusted_alpha"] / divisor)
        target_z = normal_quantile(values["target_power"])
        points = values["sensitivity_points"]
        grid = [low + (high - low) * index / (points - 1) for index in range(points)]
        grid[0], grid[-1] = low, high
        result = _scenario(assumptions, values, values["nuisance"], critical, target_z)
        result["sensitivity"] = [_scenario(assumptions, values, item, critical, target_z) for item in grid]
        return result
    except (OverflowError, ZeroDivisionError) as error:
        raise ValueError("degenerate-design: arithmetic outside finite reference range") from error


def _same(actual, expected, code):
    if type(expected) is dict:
        _fields(actual, expected, "calculation")
        for key in expected:
            _same(actual[key], expected[key], code)
    elif type(expected) is list:
        _items(actual, "calculation list", MAX_GRID)
        _require(len(actual) == len(expected), code, "calculation dimensions differ")
        for first, second in zip(actual, expected):
            _same(first, second, code)
    elif type(expected) is int:
        _number(actual, "arm size", 2, MAX_N, integer=True)
        _require(actual == expected, code, "arm sizes must be rounded up and attrition-inflated per arm")
    else:
        _number(actual, "calculation value")
        _require(math.isclose(actual, expected, rel_tol=0, abs_tol=POWER_TOLERANCE), code,
                 "stated number does not reproduce frozen arithmetic within tolerance")


def _independent(identity, record, own, study_id, code):
    _require(record["study_id"] != study_id and not any(
        identity["path"] == item["path"] or identity["sha256"] == item["sha256"] for item in own),
        code, "declared prior or independent source aliases this study")


def _claims(bundle, claims, own, study_id):
    _items(claims, "claims", MAX_CLAIMS, empty=True)
    seen = set()
    for claim in claims:
        _fields(claim, ("id", "kind", "status", "text", "support"), "claim")
        for key in ("id", "kind", "status", "text"):
            _text(claim[key], key)
        _require(claim["id"] not in seen, "invalid-record", "duplicate claim ID")
        seen.add(claim["id"])
        status, text = claim["status"], claim["text"]
        _require(status in STATUSES, "invalid-record", "unknown claim status")
        _require(claim["kind"] in {"descriptive", "associational"} and OVERREACH.search(text) is None,
                 "claim-boundary", "only bounded descriptive prospective arithmetic claims")
        support = _items(claim["support"], "claim support", MAX_SUPPORT, empty=True)
        _require(bool(support) or status == "unavailable", "claim-support", "empty support requires unavailable")
        if status == "unavailable":
            _require(ASSERTION.search(text) is None, "unavailable-positive", "unavailable claim asserts positive evidence")
        for identity in support:
            _fields(identity, ("path", "sha256", "origin"), "support identity")
            origin = _text(identity["origin"], "origin")
            _require(origin in {"study", "external", "independent", "preregistered"}, "invalid-record", "unknown origin")
            plain = {key: identity[key] for key in ("path", "sha256")}
            source = _source(bundle.load(plain))
            if origin != "study":
                _independent(plain, source, own, study_id, "evidence-independence")
            _require("unavailable" not in (source["kind"], source["result"]) or status == "unavailable",
                     "unavailable-evidence", "any unavailable citation requires unavailable claim status")
            if status in POSITIVE:
                _require(NON_EVIDENCE.search(source["kind"]) is None and NON_EVIDENCE.search(source["result"]) is None,
                         "non-evidence", "review approval or computed agreement cannot support positive claims")
        _require(status != "replicated", "claim-replication", "this pack cannot establish independent replication")


def validate_sample_size_power_pack(path):
    """Validate one bundle without writes; every refusal has a stable labelled ValueError."""
    try:
        with _Bundle(path) as bundle:
            pack, digest = bundle.snapshot(_relative(bundle.entry))
            _record(pack, "sample-size-power-pack-v1", (
                "stages", "inputs", "frozen_assumptions_sha256", "frozen_at", "outcomes_available_at",
                "exploratory", "study_outputs", "claims"))
            _require(pack["stages"] == list(STAGES), "stage-order", "five exact ordered stages required")
            inputs = _fields(pack["inputs"], ("assumptions", "calculation"), "inputs")
            assumptions = bundle.load(inputs["assumptions"])
            _assumptions(assumptions)
            frozen = _text(pack["frozen_assumptions_sha256"], "frozen assumptions hash")
            _require(frozen == inputs["assumptions"]["sha256"], "assumption-freeze", "frozen assumption hash changed")
            exploratory = _boolean(pack["exploratory"], "exploratory")
            frozen_at = _time(pack["frozen_at"])
            if pack["outcomes_available_at"] is not None:
                _require(frozen_at < _time(pack["outcomes_available_at"]) or exploratory,
                         "post-outcome-change", "post-outcome assumptions require an exploratory label")
            calculation = bundle.load(inputs["calculation"])
            outputs = _items(pack["study_outputs"], "study outputs", MAX_SUPPORT, empty=True)
            for identity in outputs:
                _source(bundle.load(identity))
            own = [*inputs.values(), *outputs, {"path": bundle.entry, "sha256": digest}]
            for key in PARAMETERS:
                identity = assumptions[key]["source"]
                if identity is None:
                    continue
                source = _source(bundle.load(identity))
                code = "effect-leakage" if key == "effect" else "source-independence"
                _independent(identity, source, own, assumptions["study_id"], code)
                _require("unavailable" not in (source["kind"], source["result"]), "source-unavailable",
                         "unavailable source cannot supply an assumption value")
                _require(not re.search(r"own[\s-]*outcome|observed[\s-]*effect", source["kind"] + " " + source["result"], re.I),
                         code, "own outcome estimates cannot be frozen prior assumptions")
            _record(calculation, "sample-size-power-calculation-v1", ("power_basis", "effect_basis", "result"))
            _require(calculation["power_basis"] == "prospective", "observed-power", "observed power cannot evidence a null result")
            _require(calculation["effect_basis"] == "frozen-prior", "effect-leakage", "effect must come from a frozen prior record")
            expected = reference_computation(assumptions)
            stated = _fields(calculation["result"], expected, "stated result")
            _same(stated["analyzable_n"], expected["analyzable_n"], "rounding-attrition")
            _same(stated["enrolled_n"], expected["enrolled_n"], "rounding-attrition")
            _same(stated, expected, "power-consistency")
            _claims(bundle, pack["claims"], own, assumptions["study_id"])
            bundle.recheck()
            return {"schema": "sample-size-power-result-v1", "schema_version": 1, "fixture": pack["fixture"],
                    "stages": list(STAGES), "status": "exploratory" if exploratory else "computed",
                    "evidence_level": "arithmetic-only", "review": "unavailable", "result": expected,
                    "input_identities": [{"path": name, "sha256": value[1]} for name, value in sorted(bundle.cache.items())],
                    "claims": pack["claims"], "limitations": [
                        "Synthetic fixtures establish software behavior only." if pack["fixture"] else "Supplied assumptions; no source audit.",
                        "Normal approximations ignore small-sample, dependence and variance-estimation error.",
                        "Freeze timing and source authenticity cannot be established from declarations and hashes.",
                        "Conservative English lexical refusals are incomplete; coordinator-owned independent review is required.",
                        "Computed arithmetic establishes neither study adequacy nor benefit nor validity."]}
    except OSError as error:
        raise ValueError("input-file: unavailable regular file or symlinked component") from error
    except (RecursionError, OverflowError, UnicodeError) as error:
        raise ValueError("invalid-record: bounded finite inputs required") from error
