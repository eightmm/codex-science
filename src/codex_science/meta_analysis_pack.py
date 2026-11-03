"""Offline, read-only evidence-synthesis checks and a stdlib reference estimator.

Numerical agreement establishes statistical record consistency only. It cannot
establish source truth, chronology of preregistration, or clinical validity.
"""
from __future__ import annotations

import errno
import hashlib
import json
import math
import os
import re
import stat
from pathlib import Path, PurePosixPath

from codex_science.checkpoints import validate_checkpoint
from codex_science.evidence import CLAIM_STATUSES

MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_TOTAL_NODES = 4000000
MAX_NUMBER = 1e100
MAX_JSON_DEPTH = 64
MAX_STUDIES = 200
STAGES = tuple(f"stage-{i:02d}" for i in range(1, 6))
POSITIVE = {"supported", "replicated", "suggestive"}
# Deliberately conservative: even negated wording requires independent review.
FORBIDDEN_WORDING = (
    r"\b(?:caus\w*|therap\w*|clinic\w*|treat\w*|prescri\w*|recommend\w*|"
    r"efficac\w*|effective\w*|mechanis\w*|cure\w*|prevent\w*|dose\w*|dosing|"
    r"bind\w*|affinit(?:y|ies)|activat\w*|inhibit\w*|administ\w*|induces?|drives?|leads?\s+to|"
    r"physical\s+(?:valid\w*|correct\w*)|scientific\s+truth|proves?\s+true)\b"
)
UNAVAILABLE_POSITIVE_WORDING = r"\b(?:supported|replicated|suggestive|significan\w*|pooled\s+estimate)\b"


def _require(condition, code, detail):
    if not condition:
        raise ValueError(f"{code}: {detail}")


def _object(value, label):
    _require(isinstance(value, dict), "MA_FORMAT", f"{label} must be an object")
    return value


def _list(value, label):
    _require(isinstance(value, list), "MA_FORMAT", f"{label} must be a list")
    return value


def _studies(value):
    rows = _list(value, "studies")
    _require(len(rows) <= MAX_STUDIES, "MA_STUDY_LIMIT", "study table exceeds 200 studies")
    return rows


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _strings(value):
    return (isinstance(value, list) and all(_text(x) for x in value)
            and len(set(value)) == len(value))


def _number(value):
    return type(value) in (int, float) and abs(value) <= MAX_NUMBER and math.isfinite(value)


def _schema(value, name):
    _object(value, name)
    _require(value.get("schema") == name, "MA_FORMAT", f"expected {name}")
    _require("synthetic" not in value or type(value["synthetic"]) is bool,
             "MA_FORMAT", "synthetic label must be boolean")


def _pairs(items):
    result = {}
    for key, value in items:
        _require(key not in result, "MA_JSON", "duplicate JSON key")
        result[key] = value
    return result


def _json_nodes(raw):
    # Upper bound before parsing: root, commas, and each non-empty container's first value.
    return 1 + raw.count(b",") + sum(1 for _ in re.finditer(rb"[\[{](?=\s*[^\s\]}])", raw))


def _json(raw):
    try:
        value = json.loads(raw, object_pairs_hook=_pairs,
                           parse_constant=lambda _: _require(False, "MA_JSON", "non-finite JSON"))
        _object(value, "JSON root")
        pending = [(value, 0)]
        while pending:
            item, depth = pending.pop()
            _require(depth <= MAX_JSON_DEPTH, "MA_JSON", "JSON nesting exceeds 64 levels")
            if isinstance(item, dict):
                pending.extend((child, depth + 1) for child in item.values())
            elif isinstance(item, list):
                pending.extend((child, depth + 1) for child in item)
            elif type(item) in (int, float):
                _require(_number(item), "MA_JSON", "number outside finite supported range")
        return value
    except (ValueError, UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError("MA_JSON: invalid, duplicate, deep or non-finite JSON") from error


class _Bundle:
    def __init__(self, directory):
        self.path = Path(directory).absolute()
        self.descriptor = self._open_root()
        try:
            # Capture identity before inspecting paths that can change underneath us.
            info = os.fstat(self.descriptor)
            self.root_identity = (info.st_dev, info.st_ino)
            self._check_root()
            self.root = self.path.resolve(strict=True)
            resolved = self.root.stat()
            _require((resolved.st_dev, resolved.st_ino) == self.root_identity,
                     "MA_CHANGED", "bundle directory replaced while resolving")
            self._check_root()
        except BaseException:
            os.close(self.descriptor)
            raise
        self.cache = {}
        self.identities = {}
        self.signatures = {}
        self.artifacts = {}
        self.bytes_read = 0
        self.nodes_read = 0
        self.rechecked = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        os.close(self.descriptor)

    def _open_root(self):
        """Pin every ancestor so a pathname swap cannot redirect bundle reads."""
        flags = os.O_RDONLY | os.O_NONBLOCK | os.O_DIRECTORY | os.O_NOFOLLOW
        descriptor = os.open(self.path.anchor, flags)
        try:
            os.fstat(descriptor)
            for part in self.path.parts[1:]:
                before = os.lstat(part, dir_fd=descriptor)
                _require(stat.S_ISDIR(before.st_mode), "MA_PATH", "symlinked or non-directory bundle component")
                child = os.open(part, flags, dir_fd=descriptor)
                try:
                    opened = os.fstat(child)
                    _require((before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino),
                             "MA_CHANGED", "bundle component replaced while opening")
                except BaseException:
                    os.close(child)
                    raise
                os.close(descriptor)
                descriptor = child
            return descriptor
        except BaseException as error:
            os.close(descriptor)
            if isinstance(error, OSError) and error.errno in (errno.ELOOP, errno.ENOTDIR):
                raise ValueError("MA_PATH: symlinked or non-directory bundle component") from error
            raise

    def _check_root(self):
        fd = self._open_root()
        try:
            info = os.fstat(fd)
            _require((info.st_dev, info.st_ino) == self.root_identity,
                     "MA_CHANGED", "bundle directory replaced during validation")
        finally:
            os.close(fd)

    def _read_bytes(self, relative):
        path = PurePosixPath(relative)
        _require(_text(relative) and str(path) == relative and relative != "."
                 and not path.is_absolute() and ".." not in path.parts
                 and "\\" not in relative and "\x00" not in relative,
                 "MA_PATH", "artifact path must be canonical and bundle-relative")
        flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
        directory_flags = flags | os.O_DIRECTORY
        descriptors = []
        try:
            parent = os.dup(self.descriptor)
            descriptors.append(parent)
            info = os.fstat(parent)
            _require((info.st_dev, info.st_ino) == self.root_identity,
                     "MA_CHANGED", "bundle directory replaced during validation")
            for part in path.parts[:-1]:
                parent = os.open(part, directory_flags, dir_fd=parent)
                descriptors.append(parent)
            before = os.lstat(path.name, dir_fd=parent)
            _require(stat.S_ISREG(before.st_mode), "MA_INPUT", "artifact must be a regular file")
            fd = os.open(path.name, flags, dir_fd=parent)
            descriptors.append(fd)
            info = os.fstat(fd)
            _require(stat.S_ISREG(info.st_mode), "MA_INPUT", "artifact must be a regular file")
            _require((before.st_dev, before.st_ino) == (info.st_dev, info.st_ino),
                     "MA_CHANGED", "artifact replaced while opening")
            identity = (info.st_dev, info.st_ino)
            _require(relative not in self.identities or self.identities[relative] == identity,
                     "MA_CHANGED", "artifact replaced during validation")
            self.identities.setdefault(relative, identity)
            _require(info.st_size <= MAX_ARTIFACT_BYTES, "MA_INPUT", "artifact exceeds 64 MiB")
            signature = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
            self.signatures[relative] = signature
            cached = self.artifacts.get(identity)
            if cached is not None:
                _require(signature == cached[2], "MA_CHANGED", "cached artifact changed during validation")
                if self.rechecked is None or identity in self.rechecked:
                    return None
            limit = MAX_ARTIFACT_BYTES
            if self.rechecked is None:
                limit = min(limit, MAX_TOTAL_BYTES - self.bytes_read)
                _require(info.st_size <= limit, "MA_LIMIT", "total input byte budget exceeded")
            # The descriptor is verified before any read, including a FIFO race.
            with os.fdopen(os.dup(fd), "rb") as stream:
                raw = stream.read(min(limit, info.st_size) + 1)
            after = os.fstat(fd)
            _require(len(raw) <= MAX_ARTIFACT_BYTES, "MA_INPUT", "artifact exceeds 64 MiB")
            _require(len(raw) == info.st_size == after.st_size
                     and info.st_mtime_ns == after.st_mtime_ns and info.st_ctime_ns == after.st_ctime_ns,
                     "MA_CHANGED", "artifact grew or changed while reading")
            if self.rechecked is None:
                self.bytes_read += len(raw)
            return raw
        except OSError as error:
            raise ValueError("MA_INPUT: cannot open regular bundle artifact") from error
        finally:
            for fd in reversed(descriptors):
                os.close(fd)

    def read(self, ref, *, root=False):
        _object(ref, "artifact reference")
        _require(set(ref) == {"path", "sha256"} and _text(ref["path"]),
                 "MA_FORMAT", "reference requires path and sha256")
        relative = ref["path"]
        if relative not in self.cache:
            raw = self._read_bytes(relative)
            identity = self.identities[relative]
            if raw is not None:
                nodes = _json_nodes(raw)
                _require(nodes <= MAX_TOTAL_NODES - self.nodes_read,
                         "MA_LIMIT", "total JSON value budget exceeded")
                signature = self.signatures[relative]
                self.artifacts[identity] = (hashlib.sha256(raw).hexdigest(), _json(raw), signature)
                self.nodes_read += nodes
            self.cache[relative] = self.artifacts[identity][:2]
        digest, value = self.cache[relative]
        _require((root and relative == "pack.json" and ref["sha256"] is None)
                 or ref["sha256"] == digest, "MA_HASH", "artifact hash mismatch")
        return value

    def unchanged(self):
        self._check_root()
        self.rechecked = set()
        try:
            for relative, (digest, _) in self.cache.items():
                raw = self._read_bytes(relative)
                _require(raw is None or hashlib.sha256(raw).hexdigest() == digest,
                         "MA_CHANGED", "input changed during validation")
                self.rechecked.add(self.identities[relative])
            self._check_root()
        finally:
            self.rechecked = None


def _variance(row):
    values = [name for name in ("variance", "standard_error") if name in row]
    _require(bool(values), "MA_VARIANCE", "variance or standard error is required")
    for name in values:
        _require(_number(row[name]) and row[name] > 0,
                 "MA_VARIANCE", "variance and standard error must be finite and positive")
    variance = row.get("variance", row.get("standard_error", 0) ** 2)
    _require(_number(variance) and variance > 0, "MA_VARIANCE", "invalid squared standard error")
    if len(values) == 2:
        _require(math.isclose(variance, row["standard_error"] ** 2, rel_tol=1e-12),
                 "MA_VARIANCE", "variance and standard error disagree")
    return variance


def _pool(effects, variances):
    weights = [1 / v for v in variances]
    total = math.fsum(weights)
    mean = math.fsum(w * y for w, y in zip(weights, effects)) / total
    q = math.fsum(w * (y - mean) ** 2 for w, y in zip(weights, effects))
    c = total - math.fsum(w * w for w in weights) / total
    tau = max(0.0, (q - (len(effects) - 1)) / c) if len(effects) > 1 else 0.0
    _require(len(effects) == 1 or c > 0, "MA_NUMERIC", "degenerate weight denominator")

    def estimate(ws):
        weight_sum = math.fsum(ws)
        value = math.fsum(w * y for w, y in zip(ws, effects)) / weight_sum
        se = math.sqrt(1 / weight_sum)
        # Normal 95% Wald interval, not a small-sample or prediction interval.
        z = 1.959963984540054
        return {"estimate": value, "standard_error": se, "ci_low": value - z * se,
                "ci_high": value + z * se}

    return {"fixed": estimate(weights), "random": estimate([1 / (v + tau) for v in variances]),
            "q": q, "tau_squared": tau,
            "i_squared": max(0.0, (q - len(effects) + 1) / q) * 100 if q > 0 else 0.0}


def _small_study(effects, variances):
    precisions = [1 / math.sqrt(v) for v in variances]
    standardized = [y * x for y, x in zip(effects, precisions)]
    x_mean = math.fsum(precisions) / len(effects)
    y_mean = math.fsum(standardized) / len(effects)
    denominator = math.fsum((x - x_mean) ** 2 for x in precisions)
    estimate = None
    if len(effects) >= 3 and denominator > 0:
        slope = math.fsum((x - x_mean) * (y - y_mean)
                          for x, y in zip(precisions, standardized)) / denominator
        estimate = y_mean - slope * x_mean
    return {"status": "exploratory", "method": "Egger intercept (descriptive only)",
            "estimate": estimate, "availability": "computed" if estimate is not None else "unavailable",
            "reason": "Uncalibrated diagnostic; no significance or publication-bias inference."
            if estimate is not None else "Requires at least three studies and varying precision."}


def compute_meta_analysis(studies, min_studies=2):
    """Inverse-variance FE and DerSimonian-Laird RE; no source-validity claim.

    Call the pack validator for identity, scale, units and independence checks.
    This numerical entry point accepts already harmonized independent effects.
    Tables are limited to MAX_STUDIES to bound quadratic leave-one-out work.
    """
    try:
        _require(type(min_studies) is int and 2 <= min_studies <= MAX_NUMBER,
                 "MA_MIN_STUDIES", "minimum independent studies must be an integer at least two")
        studies = _studies(studies)
        _require(len(studies) >= min_studies, "MA_MIN_STUDIES", "too few independent studies to pool")
        effects, variances, identifiers = [], [], []
        for row in studies:
            _object(row, "study")
            _require(_text(row.get("study_id")) and row["study_id"] not in identifiers,
                     "MA_INDEPENDENCE", "study IDs must be unique")
            _require(_number(row.get("effect")), "MA_NUMERIC", "effect must be finite")
            identifiers.append(row["study_id"])
            effects.append(row["effect"])
            variances.append(_variance(row))
        result = _pool(effects, variances)
        sensitivity = []
        for i, identifier in enumerate(identifiers):
            dropped = _pool(effects[:i] + effects[i + 1:], variances[:i] + variances[i + 1:])
            reversal = any((result[m]["estimate"] > 0 > dropped[m]["estimate"]) or (result[m]["estimate"] < 0 < dropped[m]["estimate"])
                           for m in ("fixed", "random"))
            sensitivity.append({"omitted_study": identifier, **dropped, "reversal": reversal})
        result["leave_one_out"] = sensitivity
        result["small_study"] = _small_study(effects, variances)
        _json(json.dumps(result, allow_nan=False))
        return result
    except ValueError as error:
        if str(error).startswith("MA_"):
            raise
        raise ValueError("MA_NUMERIC: non-finite computation") from error
    except ArithmeticError as error:
        raise ValueError("MA_NUMERIC: degenerate or overflowing computation") from error


def _protocol(protocol):
    _schema(protocol, "meta-analysis-protocol-v1")
    for field in ("question", "eligibility", "effect_measure", "direction", "unit"):
        _require(_text(protocol.get(field)), "MA_PROTOCOL", f"missing frozen {field}")
    _require(protocol.get("frozen_before_extraction") is True,
             "MA_PROTOCOL", "freeze protocol before reading extraction")
    _require(protocol.get("model") in ("fixed", "random"), "MA_PROTOCOL", "unsupported frozen model")
    _require(type(protocol.get("min_studies")) is int and 2 <= protocol["min_studies"] <= MAX_NUMBER,
             "MA_MIN_STUDIES", "minimum independent studies must be at least two")
    for key, maximum in (("i_squared_threshold", 100), ("tau_squared_threshold", MAX_NUMBER)):
        _require(_number(protocol.get(key)) and 0 <= protocol[key] <= maximum,
                 "MA_PROTOCOL", f"invalid frozen {key}")
    _require(_strings(protocol.get("subgroups")), "MA_PROTOCOL", "subgroup list required")


def _gate(protocol, extraction, gate):
    _schema(extraction, "meta-analysis-extraction-v1")
    _schema(gate, "meta-analysis-gate-v1")
    rows = _studies(extraction.get("studies"))
    ids = []
    for row in rows:
        _object(row, "study")
        _require(_text(row.get("study_id")) and row["study_id"] not in ids,
                 "MA_INDEPENDENCE", "duplicate or empty study ID")
        ids.append(row["study_id"])
        _variance(row)
        _require(_number(row.get("effect")), "MA_NUMERIC", "effect must be finite")
        for key in ("n_exposed", "n_comparator"):
            _require(type(row.get(key)) is int and 0 < row[key] <= MAX_NUMBER,
                     "MA_SAMPLE", "positive integer sample sizes required")
        for key in ("cohort_id", "independence_group", "effect_measure", "direction", "unit"):
            _require(_text(row.get(key)), "MA_FORMAT", f"missing study {key}")
        _require(_strings(row.get("participant_ids")) and bool(row["participant_ids"]),
                 "MA_INDEPENDENCE", "participant identities must be recorded")
        _require(len(row["participant_ids"]) == row["n_exposed"] + row["n_comparator"],
                 "MA_SAMPLE", "participant identities must cover both sample sizes")
        _require(row.get("result") in ("recorded", "negative", "failed-control", "unavailable"),
                 "MA_PRESERVATION", "absence is unavailable, never negative evidence")
    included = gate.get("included_studies")
    _require(_strings(included), "MA_FORMAT", "included_studies must be unique IDs")
    excluded = []
    for item in _list(gate.get("exclusions"), "exclusions"):
        _object(item, "exclusion")
        _require(_text(item.get("reason")), "MA_POSTHOC", "exclusion rationale required")
        _timing(item)
        excluded.append(item.get("study_id"))
    _require(len(set(excluded)) == len(excluded) and set(included).isdisjoint(excluded)
             and set(included) | set(excluded) == set(ids),
             "MA_PRESERVATION", "retain every included or excluded study exactly once")
    for item in _list(gate.get("subgroups"), "subgroups"):
        _object(item, "subgroup")
        _require(_text(item.get("name")), "MA_POSTHOC", "subgroup name required")
        _timing(item)
        _require(item["name"] in protocol["subgroups"] or item.get("exploratory") is True,
                 "MA_POSTHOC", "added subgroup must be exploratory")
    selected = [row for row in rows if row["study_id"] in included]
    seen = {key: set() for key in ("cohort_id", "independence_group", "participant_ids")}
    conversions = {}
    for item in _list(gate.get("conversions"), "conversions"):
        _object(item, "conversion")
        identifier = item.get("study_id")
        _require(_text(identifier) and identifier in included and identifier not in conversions,
                 "MA_UNITS", "conversion must identify one included study")
        _require(_number(item.get("factor")) and item["factor"] > 0 and _text(item.get("reason")),
                 "MA_UNITS", "conversion requires a positive factor and rationale")
        conversions[identifier] = item
    normalized = []
    for row in selected:
        for key in seen:
            values = row[key] if key == "participant_ids" else [row[key]]
            _require(seen[key].isdisjoint(values), "MA_INDEPENDENCE", "overlapping cohorts or participants counted twice")
            seen[key].update(values)
        _require(row["effect_measure"] == protocol["effect_measure"] and row["direction"] == protocol["direction"],
                 "MA_COMPARABILITY", "mixed effect scales or sign conventions")
        _require(row["result"] not in ("unavailable", "failed-control"),
                 "MA_PRESERVATION", "unavailable effects or failed controls cannot be pooled")
        factor = 1.0
        conversion = conversions.get(row["study_id"])
        if row["unit"] != protocol["unit"] or conversion is not None:
            _require(conversion is not None and conversion.get("from_unit") == row["unit"]
                     and conversion.get("to_unit") == protocol["unit"],
                     "MA_UNITS", "different units require a recorded conversion")
            factor = conversion["factor"]
        normalized.append({"study_id": row["study_id"], "effect": row["effect"] * factor,
                           "variance": _variance(row) * factor * factor})
    return normalized


def _timing(item):
    _require(item.get("timing") in ("before-results", "after-results")
             and type(item.get("exploratory")) is bool,
             "MA_POSTHOC", "decision timing and exploratory label required")
    _require(item["timing"] != "after-results" or item["exploratory"],
             "MA_POSTHOC", "post-result exclusion or subgroup must be exploratory")


def _same_numbers(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and set(actual) == set(expected) and all(
            _same_numbers(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            _same_numbers(a, b) for a, b in zip(actual, expected))
    if type(expected) in (int, float):
        return _number(actual) and math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-12)
    return type(actual) is type(expected) and actual == expected


def _claims(bundle, handoff, too_few, outputs):
    register = bundle.read(handoff.get("claims"))
    _require(type(register.get("schema_version")) is int and register["schema_version"] == 1,
             "MA_FORMAT", "existing claim-register schema_version required")
    evidence = bundle.read(handoff.get("evidence"))
    _schema(evidence, "meta-analysis-evidence-v1")
    records = {}
    for record in _list(evidence.get("records"), "evidence records"):
        _object(record, "evidence record")
        identifier = record.get("id")
        _require(_text(identifier) and identifier not in records, "MA_FORMAT", "unique evidence ID required")
        for field in ("kind", "result", "text", "provenance"):
            _require(_text(record.get(field)), "MA_FORMAT", f"missing evidence {field}")
        ref = record.get("artifact")
        source = bundle.read(ref)
        if record["provenance"] in ("external", "independent", "preregistered"):
            _require(not any(ref["path"] == x["path"] or ref["sha256"] == x["sha256"] for x in outputs),
                     "MA_EXTERNAL", "external evidence aliases the run's own output")
        _schema(source, "meta-analysis-source-v1")
        _require(_text(source.get("study_id")), "MA_FORMAT", "source study identity required")
        records[identifier] = (record, source)
    links = _object(handoff.get("claim_evidence"), "claim evidence mapping")
    identifiers = set()
    for claim in _list(register.get("claims"), "claims"):
        _object(claim, "claim")
        identifier = claim.get("id")
        _require(_text(identifier) and identifier not in identifiers, "MA_CLAIM", "unique claim ID required")
        identifiers.add(identifier)
        _require(_text(claim.get("text")) and claim.get("status") in CLAIM_STATUSES
                 and claim.get("permitted_inference") in ("descriptive", "associational", "causal", "confirmatory"),
                 "MA_CLAIM", "invalid existing claim-register fields")
        refs = links.get(identifier)
        _require(_strings(refs) and all(r in records for r in refs), "MA_CLAIM", "claim evidence must resolve")
        _require(bool(refs) or claim["status"] == "unavailable",
                 "MA_CLAIM", "claim without evidence must be unavailable")
        positive = claim["status"] in POSITIVE
        _require(claim["status"] == "unavailable" or not any(
                     "unavailable" in (item.get(field) for field in ("kind", "result"))
                     for ref in refs for item in records[ref]),
                 "MA_CLAIM_EVIDENCE", "unavailable evidence requires an unavailable claim")
        if too_few:
            _require(not re.search(r"pooled\s+estimate|significan\w*|\bp\s*[<=>]", claim["text"], re.I),
                     "MA_MIN_STUDIES", "no pooled estimate or significance claim below frozen minimum")
        if claim["status"] == "unavailable":
            _require(not re.search(FORBIDDEN_WORDING + "|" + UNAVAILABLE_POSITIVE_WORDING,
                                   claim["text"], re.IGNORECASE),
                     "MA_CLAIM_BOUNDARY", "unavailable claim cannot assert positive evidence")
        if positive:
            _require(not too_few, "MA_MIN_STUDIES", "too few independent studies for a positive synthesis claim")
            _require(claim["permitted_inference"] in ("descriptive", "associational")
                     and not re.search(FORBIDDEN_WORDING, claim["text"], re.IGNORECASE),
                     "MA_CLAIM_BOUNDARY", "only bounded statistical evidence may be claimed")
            for ref in refs:
                record, source = records[ref]
                prohibited = re.compile(r"review|approv|comput|numerical|simulat", re.I)
                _require(all(_text(item.get(field)) and not prohibited.search(item[field])
                             for item in (record, source) for field in ("kind", "result")),
                         "MA_CLAIM_EVIDENCE", "approval or computed record cannot support a positive claim")
                _require(record["result"] not in ("unavailable", "failed-control"),
                         "MA_CLAIM_EVIDENCE", "missing evidence or failed controls cannot support a positive claim")
                _require(claim["text"] == record["text"], "MA_CLAIM", "claim must preserve literal source attribution")
                _require(all(source.get(field) == record[field] for field in ("kind", "result", "text")),
                         "MA_CLAIM", "record must preserve source kind, result and text")
    _require(set(links) == identifiers, "MA_CLAIM", "claim evidence mapping must match claim register")


def _validate(bundle):
    pack = bundle.read({"path": "pack.json", "sha256": None}, root=True)
    _schema(pack, "meta-analysis-pack-v1")
    _require(type(pack.get("synthetic")) is bool, "MA_FORMAT", "synthetic fixture label required")
    stages = _list(pack.get("stages"), "stages")
    _require(len(stages) == 5, "MA_STAGES", "five ordered stages required")
    outputs, data = [], []
    for index, stage in enumerate(stages):
        _schema(stage, "meta-analysis-stage-v1")
        _require(stage.get("id") == STAGES[index] and stage.get("inputs") == outputs,
                 "MA_STAGES", "ordered immutable input path-plus-hash handoffs required")
        output = stage.get("output")
        _object(output, "stage output")
        _require(all(output.get("path") != x["path"] for x in outputs),
                 "MA_STAGES", "stage outputs must have distinct paths")
        value = bundle.read(output)
        if index == 0:
            _protocol(value)  # Freeze is inspected before extraction is opened.
        outputs.append(output)
        data.append(value)
    protocol, extraction, gate, pooling, handoff = data
    checkpoint = bundle.read(pack.get("checkpoint"))
    try:
        for record, fields in (
            (checkpoint, ("schema_version", "continuation_count", "idle_continuations", "continuation_budget", "revision")),
            (checkpoint.get("wait"), ("poll_interval_seconds",)),
            (checkpoint.get("run_budget"), ("policy_version", "max_failed_attempts_per_class", "max_review_rounds")),
        ):
            if isinstance(record, dict):
                for field in fields:
                    _require(field not in record or type(record[field]) is int,
                             "MA_CHECKPOINT", f"checkpoint {field} must be an integer")
        validate_checkpoint(checkpoint)
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        raise ValueError("MA_CHECKPOINT: invalid coordinator checkpoint") from error
    _require([step["id"] for step in checkpoint["steps"]] == list(STAGES),
             "MA_CHECKPOINT", "one coordinator checkpoint must cover the five ordered stages")
    _require(extraction.get("protocol_sha256") == outputs[0]["sha256"],
             "MA_PROTOCOL", "extraction must bind the frozen protocol hash")
    studies = _gate(protocol, extraction, gate)
    _schema(pooling, "meta-analysis-pooling-v1")
    _schema(handoff, "meta-analysis-handoff-v1")
    _require(handoff.get("review_status") == "pending", "MA_REVIEW", "independent review stays pending")
    _require(_strings(handoff.get("limitations")) and bool(handoff["limitations"]),
             "MA_FORMAT", "limitations must be retained")
    too_few = len(studies) < protocol["min_studies"]
    if too_few:
        _require(pooling.get("status") == "unavailable" and pooling.get("results") is None,
                 "MA_MIN_STUDIES", "too few independent studies: no pooled estimate or significance claim")
        result = None
    else:
        result = compute_meta_analysis(studies, protocol["min_studies"])
        headline = pooling.get("headline_model")
        _require(headline in ("fixed", "random"), "MA_MODEL", "headline model required")
        heterogeneous = (result["i_squared"] > protocol["i_squared_threshold"]
                         or result["tau_squared"] > protocol["tau_squared_threshold"])
        _require(not heterogeneous or headline != "fixed", "MA_HETEROGENEITY", "fixed-effect headline exceeds frozen heterogeneity threshold")
        _require(headline == protocol["model"], "MA_MODEL", "headline must match frozen model")
        _require(pooling.get("status") == "computed" and _same_numbers(pooling.get("results"), result),
                 "MA_NUMERIC", "reported pooling or sensitivity differs from reference computation")
    reversals = [row["omitted_study"] for row in result["leave_one_out"] if row["reversal"]] if result else []
    _require(handoff.get("loo_reversals") == reversals, "MA_LOO", "disclose every leave-one-out sign reversal")
    own_outputs = list(outputs)
    for row in extraction["studies"]:
        for ref in _list(row.get("outputs"), "study outputs"):
            bundle.read(ref)
            own_outputs.append(ref)
    _claims(bundle, handoff, too_few, own_outputs)
    for _, value in bundle.cache.values():
        _require("synthetic" not in value or value["synthetic"] is pack["synthetic"],
                 "MA_FORMAT", "synthetic fixture labels must agree across the bundle")
    bundle.unchanged()
    return {"schema": "meta-analysis-validation-v1", "status": "passed", "synthetic": pack["synthetic"],
            "evidence": "statistical only", "review_status": "pending", "independent_studies": len(studies),
            "headline_model": pooling.get("headline_model") if result else None,
            "results": result}


def validate_meta_analysis_pack(directory):
    """Validate an offline bundle without writing files; refusals are ValueError."""
    try:
        with _Bundle(directory) as bundle:
            return _validate(bundle)
    except ValueError as error:
        if str(error).startswith("MA_"):
            raise
        raise ValueError("MA_INPUT: malformed bundle value") from error
    except (OSError, RecursionError, OverflowError, TypeError, KeyError, ArithmeticError) as error:
        raise ValueError("MA_INPUT: malformed, unreadable or numerically degenerate bundle") from error
