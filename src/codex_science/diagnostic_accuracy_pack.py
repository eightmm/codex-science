"""Read-only diagnostic accuracy admission and a bounded, offline reference calculation."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import random
import re
import stat
import statistics


STAGES = ("01-protocol", "02-cases", "03-bias", "04-computation", "05-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
MAX_ARTIFACTS = 256
MAX_DEPTH = 64
MAX_ROWS = 10000
MAX_DRAWS = 2000
MAX_CLAIMS = 100
MAX_SUPPORT = 100
MAX_TEXT = 4096
MAX_ITEMS = 20000
MAX_NODES = 200000
MAX_NUMBER = 1e100
POSITIVE = {"supported", "replicated", "suggestive"}
STATUSES = POSITIVE | {"planned", "conflicting", "unsupported", "withdrawn", "unavailable"}
FORBIDDEN_WORDING = (
    r"\b(?:caus\w*|mechanis\w*|therap\w*|clinic\w*|efficac\w*|effective\w*|"
    r"treat\w*|cure\w*|prevent\w*|recommend\w*|prescri\w*|bind\w*|affinit\w*|"
    r"inhibit\w*|activat\w*|regulat\w*|driv\w*|induc\w*|truth|"
    r"screening[\s-]+(?:utility|use)|physical[\s-]+validity|patient[\s-]+benefit\w*)\b"
)
UNAVAILABLE_POSITIVE = r"\b(?:supported|replicated|suggestive|significan\w*)\b"
NON_EVIDENCE = re.compile(r"review|approv|comput|numer|physical|clinic|truth", re.I)


def _require(condition, code, message):
    if not condition:
        raise ValueError(f"{code}: {message}")


def _obj(value, label):
    _require(type(value) is dict, "invalid-record", f"{label} must be an object")
    return value


def _fields(value, names, label):
    value = _obj(value, label)
    _require(set(value) == set(names), "invalid-record", f"{label} fields must be {', '.join(names)}")
    return value


def _text(value, label):
    _require(type(value) is str and 0 < len(value) <= MAX_TEXT and bool(value.strip()),
             "invalid-record", f"{label} must be nonempty text at most {MAX_TEXT} characters")
    return value


def _items(value, label, limit, empty=False):
    _require(type(value) is list and len(value) <= limit and (empty or bool(value)),
             "input-limit", f"{label} must be a list with {'0' if empty else '1'}..{limit} entries")
    return value


def _number(value, label, low=-MAX_NUMBER, high=MAX_NUMBER, integer=False):
    valid = type(value) is int if integer else type(value) in (int, float)
    _require(valid and low <= value <= high and math.isfinite(value),
             "invalid-record", f"{label} must be a finite {'integer' if integer else 'number'} in [{low}, {high}]")
    return value


def _bool(value, label):
    _require(type(value) is bool, "invalid-record", f"{label} must be boolean")
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
    _require(len(value.lstrip("-")) <= 101, "invalid-json", "huge integer")
    return _number(int(value), "JSON integer")


def _json(raw, allowance=None):
    allowance = MAX_NODES if allowance is None else allowance
    # Upper bound on value count before json.loads allocates the tree: the root,
    # one value per comma, and the first value of every non-empty container.
    _require(1 + raw.count(b",") + sum(1 for _ in re.finditer(rb"[\[{](?=\s*[^\s\]}])", raw)) <= allowance,
             "input-limit", "too many JSON values")
    try:
        root = _obj(json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                              parse_constant=_constant, parse_int=_integer,
                              parse_float=lambda value: _number(float(value), "JSON number")), "JSON root")
        pending = [(root, 0)]
        nodes = 0
        while pending:
            value, depth = pending.pop()
            nodes += 1
            _require(nodes <= allowance, "input-limit", "too many JSON values")
            if type(value) in (dict, list):
                _require(depth <= MAX_DEPTH, "invalid-json", "JSON nesting exceeds limit")
                _require(len(value) <= MAX_ITEMS, "input-limit", "too many JSON entries")
                children = value.items() if type(value) is dict else enumerate(value)
                for key, child in children:
                    if type(key) is str:
                        _text(key, "JSON key")
                    pending.append((child, depth + 1))
            elif type(value) is str:
                _require(len(value) <= MAX_TEXT, "input-limit", "JSON string exceeds limit")
        return root, nodes
    except (UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError("invalid-json: bounded finite UTF-8 JSON object required") from error
    except json.JSONDecodeError as error:
        raise ValueError("invalid-json: malformed JSON") from error


def _relative(value):
    value = _text(value, "artifact path")
    path = PurePosixPath(value)
    _require(not path.is_absolute() and path.as_posix() == value and value != "."
             and ".." not in path.parts and "\\" not in value and not re.match(r"^[A-Za-z]:", value)
             and all(ord(char) >= 32 for char in value),
             "input-path", "artifact path must be canonical and bundle-relative")
    return path


def _signature(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _directory(path):
    """Walk from the filesystem root using descriptors; never follow an ancestor link."""
    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_DIRECTORY
    descriptor = os.open(path.anchor, flags)
    try:
        for part in path.parts[1:]:
            before = os.lstat(part, dir_fd=descriptor)
            _require(stat.S_ISDIR(before.st_mode), "input-path", "bundle ancestors must be directories")
            child = os.open(part, flags, dir_fd=descriptor)
            try:
                opened = os.fstat(child)
                _require((before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino),
                         "input-changed", "bundle directory replaced during open")
            except BaseException:
                os.close(child)
                raise
            os.close(descriptor)
            descriptor = child
        resolved = os.stat(path, follow_symlinks=False)
        opened = os.fstat(descriptor)
        _require(stat.S_ISDIR(resolved.st_mode) and
                 (resolved.st_dev, resolved.st_ino) == (opened.st_dev, opened.st_ino),
                 "input-changed", "bundle root no longer identifies pinned directory")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


class _Bundle:
    def __init__(self, path):
        self.path = Path(os.path.abspath(path))
        _require(all(ord(char) >= 32 for char in str(self.path)),
                 "input-path", "bundle path contains control characters")
        self.root = self.path.parent
        self.descriptor = _directory(self.root)
        self.identity = os.fstat(self.descriptor)
        self.cache = {}
        self.bytes_read = 0
        self.nodes = 0

    def _parse(self, raw):
        root, count = _json(raw, MAX_NODES - self.nodes)
        self.nodes += count
        return root

    def close(self):
        os.close(self.descriptor)

    def _read(self, relative):
        flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
        cached = relative.as_posix() in self.cache
        _require(cached or len(self.cache) < MAX_ARTIFACTS, "input-limit", "too many input artifacts")
        limit = MAX_BYTES if cached else min(MAX_BYTES, MAX_TOTAL_BYTES - self.bytes_read)
        directory = os.dup(self.descriptor)
        try:
            for part in relative.parts[:-1]:
                before = os.lstat(part, dir_fd=directory)
                _require(stat.S_ISDIR(before.st_mode), "input-file", "symlinked artifact component")
                child = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
                opened = os.fstat(child)
                if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
                    os.close(child)
                    raise ValueError("input-changed: artifact directory replaced")
                os.close(directory)
                directory = child
            before = os.lstat(relative.name, dir_fd=directory)
            _require(stat.S_ISREG(before.st_mode) and before.st_size <= MAX_BYTES,
                     "input-file", "input must be a regular file at most 64 MiB")
            _require(before.st_size <= limit, "input-limit", "total input byte budget exceeded")
            descriptor = os.open(relative.name, flags, dir_fd=directory)
            with os.fdopen(descriptor, "rb") as handle:
                opened = os.fstat(handle.fileno())
                _require(stat.S_ISREG(opened.st_mode) and opened.st_size <= MAX_BYTES
                         and _signature(before) == _signature(opened),
                         "input-file", "input replaced or exceeds limit")
                raw = handle.read(limit + 1)
                after = os.fstat(handle.fileno())
            _require(len(raw) <= MAX_BYTES and len(raw) == opened.st_size and
                     _signature(opened) == _signature(after), "input-changed", "input grew or changed during read")
            return raw, _signature(after)
        finally:
            os.close(directory)

    def load(self, identity, schema=None):
        identity = _fields(identity, ("path", "sha256"), "artifact identity")
        name = _relative(identity["path"]).as_posix()
        if name not in self.cache:
            raw, signature = self._read(_relative(name))
            self.cache[name] = (self._parse(raw), hashlib.sha256(raw).hexdigest(), signature)
            self.bytes_read += len(raw)
        record, digest, _ = self.cache[name]
        expected = identity["sha256"]
        _require(type(expected) is str and re.fullmatch(r"[0-9a-f]{64}", expected) is not None
                 and expected == digest, "input-hash", "artifact hash mismatch")
        if schema:
            _require(record.get("schema") == schema, "invalid-record", f"expected {schema}")
        return record

    def entry(self):
        raw, signature = self._read(_relative(self.path.name))
        self.cache[self.path.name] = (self._parse(raw), hashlib.sha256(raw).hexdigest(), signature)
        self.bytes_read += len(raw)
        return self.cache[self.path.name][0]

    def recheck(self):
        # Only the parsed snapshot is used; this second read verifies unchanged bytes.
        for name, (_, digest, signature) in self.cache.items():
            raw, current_signature = self._read(_relative(name))
            _require(current_signature == signature and hashlib.sha256(raw).hexdigest() == digest,
                     "input-changed", "input replaced during validation")
        # Check the visible root last, including replacements during the hash reads.
        current = _directory(self.root)
        try:
            info = os.fstat(current)
            _require((info.st_dev, info.st_ino) == (self.identity.st_dev, self.identity.st_ino),
                     "input-changed", "bundle root replaced during validation")
        finally:
            os.close(current)


def _record(record, schema, names):
    _fields(record, ("schema", "schema_version", "fixture", *names), schema)
    _require(record["schema"] == schema, "invalid-record", f"expected {schema}")
    _number(record["schema_version"], "schema_version", 1, 1, integer=True)
    _bool(record["fixture"], "fixture")
    return record


def _time(value):
    try:
        result = datetime.fromisoformat(_text(value, "time").replace("Z", "+00:00"))
        _require(result.tzinfo is not None, "protocol-freeze", "timestamps require a timezone")
        return result
    except (ValueError, OverflowError) as error:
        raise ValueError("protocol-freeze: valid timezone-aware timestamps required") from error


def _protocol(record):
    _record(record, "diagnostic-accuracy-protocol-v1", (
        "index_test", "direction", "reference_standard", "target_condition", "population",
        "threshold", "minimum_cases", "minimum_controls", "intervals", "verification_rule",
        "incorporates_index_test", "unblinded_reference_disclosed"))
    for key in ("index_test", "reference_standard", "target_condition", "population"):
        _text(record[key], key)
    direction = _text(record["direction"], "direction")
    _require(direction in {"higher", "lower"}, "invalid-record", "direction must be higher or lower")
    threshold = _fields(record["threshold"], ("method", "chosen_on", "value"), "threshold")
    method = _text(threshold["method"], "threshold method")
    chosen = _text(threshold["chosen_on"], "threshold chosen_on")
    _require(chosen != "evaluation", "evaluation-threshold", "evaluation outcomes cannot choose the threshold")
    _require((method == "fixed" and chosen == "before-outcomes") or
             (method == "youden-training" and chosen == "training"),
             "evaluation-threshold", "threshold must be fixed or chosen on a separate training split")
    if method == "fixed":
        _number(threshold["value"], "threshold value")
    else:
        _require(threshold["value"] is None, "invalid-record", "training threshold value must be null before selection")
    for key in ("minimum_cases", "minimum_controls"):
        _number(record[key], key, 1, MAX_ROWS, integer=True)
    intervals = _fields(record["intervals"], ("binomial", "auc", "draws", "seed", "minimum_success_fraction"), "intervals")
    _require(intervals["binomial"] == "wilson-95" and intervals["auc"] == "stratified-bootstrap-percentile-95",
             "interval-method", "Wilson and stratified percentile intervals must be frozen")
    _number(intervals["draws"], "draws", 1, MAX_DRAWS, integer=True)
    _number(intervals["seed"], "seed", -2**63, 2**63 - 1, integer=True)
    _number(intervals["minimum_success_fraction"], "minimum_success_fraction", 0.5, 1)
    _require(_text(record["verification_rule"], "verification_rule") == "all-subjects",
             "verification-bias", "reference application must not depend on score or a selected subset")
    _require(not _bool(record["incorporates_index_test"], "incorporates_index_test"),
             "incorporation-bias", "reference standard must not incorporate the index test")
    _bool(record["unblinded_reference_disclosed"], "unblinded_reference_disclosed")
    return record


def _groups(rows, minimum_cases, minimum_controls):
    cases = [row["score"] for row in rows if row["reference_label"] == 1]
    controls = [row["score"] for row in rows if row["reference_label"] == 0]
    _require(bool(cases) and bool(controls), "undefined-class", "both reference classes are required")
    _require(len(cases) >= minimum_cases and len(controls) >= minimum_controls,
             "insufficient-class", "cases and controls must meet the frozen minimum")
    _require(min(cases + controls) != max(cases + controls), "constant-scores", "constant scores cannot establish discrimination")
    return cases, controls


def _cases(record, protocol):
    _record(record, "diagnostic-accuracy-cases-v1", ("rows",))
    rows = _items(record["rows"], "subject rows", MAX_ROWS)
    seen = set()
    evaluation, training = [], []
    unblinded = []
    for row in rows:
        _fields(row, ("subject_id", "score", "reference_label", "reference_applied", "blinded", "split"), "case row")
        subject = _text(row["subject_id"], "subject_id")
        _require(subject not in seen, "subject-leakage", "one subject cannot appear twice, including across splits")
        seen.add(subject)
        _number(row["score"], "score")
        split = _text(row["split"], "split")
        _require(split in {"training", "evaluation"}, "invalid-record", "unknown split")
        _require(_bool(row["reference_applied"], "reference_applied"),
                 "verification-bias", "reference must be applied to every supplied subject")
        _require(row["reference_label"] is not None, "missing-reference", "missing reference is unavailable, never a negative label")
        _number(row["reference_label"], "reference_label", 0, 1, integer=True)
        if not _bool(row["blinded"], "blinded"):
            unblinded.append(subject)
        (evaluation if split == "evaluation" else training).append(row)
    _require(not unblinded or protocol["unblinded_reference_disclosed"],
             "unblinded-reference", "unblinded reference reading must be disclosed")
    _groups(evaluation, protocol["minimum_cases"], protocol["minimum_controls"])
    if protocol["threshold"]["method"] == "youden-training":
        _groups(training, protocol["minimum_cases"], protocol["minimum_controls"])
    return evaluation, training, unblinded


def _auc(cases, controls, direction):
    values = sorted([(value, 1) for value in cases] + [(value, 0) for value in controls], reverse=direction == "lower")
    twice_u = 0
    controls_below = 0
    start = 0
    while start < len(values):
        end = start + 1
        while end < len(values) and values[end][0] == values[start][0]:
            end += 1
        positive = sum(label for _, label in values[start:end])
        negative = end - start - positive
        twice_u += positive * (2 * controls_below + negative)
        controls_below += negative
        start = end
    return twice_u / (2 * len(cases) * len(controls))


def _wilson(successes, total):
    z = statistics.NormalDist().inv_cdf(0.975)
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    half = z * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total)) / denominator
    return [max(0.0, center - half), min(1.0, center + half)]


def _percentile(values, probability):
    position = (len(values) - 1) * probability
    low = math.floor(position)
    fraction = position - low
    return math.fsum((values[low] * (1 - fraction), values[min(low + 1, len(values) - 1)] * fraction))


def _training_threshold(training, direction):
    cases, controls = _groups(training, 1, 1)
    # All attainable decisions, including predict-none, are scanned once after sorting.
    values = sorted([(x, 1) for x in cases] + [(x, 0) for x in controls], reverse=direction == "higher")
    threshold = math.nextafter(values[0][0], math.inf if direction == "higher" else -math.inf)
    best = (0, threshold)
    tp = fp = 0
    start = 0
    while start < len(values):
        end = start
        while end < len(values) and values[end][0] == values[start][0]:
            tp += values[end][1]
            fp += 1 - values[end][1]
            end += 1
        candidate = (tp * len(controls) - fp * len(cases), values[start][0])
        if candidate[0] > best[0] or (candidate[0] == best[0] and candidate[1] < best[1]):
            best = candidate
        start = end
    return best[1]


def reference_computation(protocol, case_table):
    """Compute descriptive held-out discrimination, never clinical validity or utility."""
    protocol = _protocol(protocol)
    evaluation, training, unblinded = _cases(case_table, protocol)
    cases, controls = _groups(evaluation, protocol["minimum_cases"], protocol["minimum_controls"])
    direction = protocol["direction"]
    threshold = protocol["threshold"]["value"] if protocol["threshold"]["method"] == "fixed" else _training_threshold(training, direction)
    positive = (lambda score: score >= threshold) if direction == "higher" else (lambda score: score <= threshold)
    tp = sum(positive(value) for value in cases)
    fp = sum(positive(value) for value in controls)
    tn, fn = len(controls) - fp, len(cases) - tp
    sensitivity, specificity = tp / len(cases), tn / len(controls)
    intervals = protocol["intervals"]
    rng = random.Random(intervals["seed"])
    draws = []
    for _ in range(intervals["draws"]):
        sampled_cases = rng.choices(cases, k=len(cases))
        sampled_controls = rng.choices(controls, k=len(controls))
        try:
            _require(min(sampled_cases + sampled_controls) != max(sampled_cases + sampled_controls),
                     "bootstrap-degenerate", "resampled scores are constant")
        except ValueError as error:
            if str(error).startswith("bootstrap-degenerate:"):
                continue
            raise
        draws.append(_auc(sampled_cases, sampled_controls, direction))
    _require(bool(draws) and len(draws) / intervals["draws"] >= intervals["minimum_success_fraction"],
             "bootstrap-success", "too few successful bootstrap draws")
    draws.sort()
    return {
        "threshold": threshold, "direction": direction,
        "cases": len(cases), "controls": len(controls), "training_subjects": len(training),
        "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "sensitivity": {"estimate": sensitivity, "interval": _wilson(tp, len(cases))},
        "specificity": {"estimate": specificity, "interval": _wilson(tn, len(controls))},
        "auc": {"estimate": _auc(cases, controls, direction),
                "interval": [_percentile(draws, 0.025), _percentile(draws, 0.975)],
                "successful_draws": len(draws), "draws": intervals["draws"], "seed": intervals["seed"]},
        "evaluation_prevalence": len(cases) / len(evaluation), "unblinded_subjects": unblinded,
    }


def _predictive(values, result):
    _items(values, "predictive values", 2)
    _require(len(values) == 2, "predictive-prevalence", "both PPV and NPV must state their assumed prevalence")
    seen = set()
    for record in values:
        _require(type(record) is dict and "assumed_prevalence" in record and "applied_prevalence" in record,
                 "predictive-prevalence", "PPV and NPV require assumed and applied prevalence")
        _fields(record, ("metric", "value", "assumed_prevalence", "applied_prevalence"), "predictive value")
        metric = _text(record["metric"], "predictive metric")
        _require(metric in {"ppv", "npv"} and metric not in seen, "invalid-record", "unique ppv or npv required")
        seen.add(metric)
        prevalence = _number(record["assumed_prevalence"], "assumed_prevalence", 0, 1)
        applied = _number(record["applied_prevalence"], "applied_prevalence", 0, 1)
        _require(prevalence == applied, "predictive-prevalence", "predictive value cannot be transferred to a different prevalence")
        sensitivity = result["sensitivity"]["estimate"]
        specificity = result["specificity"]["estimate"]
        numerator = sensitivity * prevalence if metric == "ppv" else specificity * (1 - prevalence)
        other = (1 - specificity) * (1 - prevalence) if metric == "ppv" else (1 - sensitivity) * prevalence
        denominator = math.fsum((numerator, other))
        _require(denominator > 0, "predictive-undefined", "predictive denominator is zero")
        actual = _number(record["value"], "predictive value", 0, 1)
        _require(math.isclose(actual, numerator / denominator, rel_tol=1e-10, abs_tol=1e-12),
                 "predictive-value", "reported predictive value disagrees with the stated prevalence")
    return values


def _evidence(record):
    _record(record, "diagnostic-accuracy-evidence-v1", ("kind", "result"))
    return _text(record["kind"], "evidence kind"), _text(record["result"], "evidence result")


def _claims(bundle, records, own):
    records = _items(records, "claims", MAX_CLAIMS, empty=True)
    seen = set()
    for claim in records:
        _fields(claim, ("id", "kind", "status", "text", "support"), "claim")
        name = _text(claim["id"], "claim id")
        _require(name not in seen, "invalid-record", "duplicate claim id")
        seen.add(name)
        status = _text(claim["status"], "claim status")
        kind = _text(claim["kind"], "claim kind")
        text = _text(claim["text"], "claim text")
        _require(status in STATUSES, "invalid-record", "unknown claim status")
        _require(kind in {"descriptive", "associational"} and re.search(FORBIDDEN_WORDING, text, re.I) is None,
                 "claim-boundary", "only descriptive or associational statistical wording is allowed")
        support = _items(claim["support"], "claim support", MAX_SUPPORT, empty=True)
        _require(bool(support) or status == "unavailable", "claim-support", "empty evidence requires unavailable status")
        if status == "unavailable":
            _require(re.search(UNAVAILABLE_POSITIVE, text, re.I) is None,
                     "unavailable-positive", "unavailable claim cannot assert positive evidence")
        for identity in support:
            _fields(identity, ("path", "sha256", "origin"), "claim support identity")
            origin = _text(identity["origin"], "evidence origin")
            _require(origin in {"study", "external", "independent", "preregistered"}, "invalid-record", "unknown evidence origin")
            plain = {key: identity[key] for key in ("path", "sha256")}
            evidence = bundle.load(plain, "diagnostic-accuracy-evidence-v1")
            evidence_kind, evidence_result = _evidence(evidence)
            if origin != "study":
                _require(not any(identity["path"] == item["path"] or identity["sha256"] == item["sha256"] for item in own),
                         "evidence-independence", "declared outside evidence aliases a study input or output")
            _require("unavailable" not in (evidence_kind, evidence_result) or status == "unavailable",
                     "unavailable-evidence", "unavailable records cannot support positive or negative evidence")
            if status in POSITIVE:
                _require(NON_EVIDENCE.search(evidence_kind) is None and NON_EVIDENCE.search(evidence_result) is None,
                         "non-evidence", "review approval or computed agreement cannot support a positive claim")
                _require(evidence_kind == "statistical-evidence" and evidence_result == "held-out-discrimination",
                         "non-evidence", "positive support requires a statistical evidence record")
        _require(status != "replicated", "claim-replication", "this single table cannot establish independent replication")
    return records


def validate_diagnostic_accuracy_pack(path):
    """Validate one immutable bundle and return JSON-compatible statistical evidence."""
    bundle = None
    try:
        bundle = _Bundle(path)
        pack = bundle.entry()
        _record(pack, "diagnostic-accuracy-pack-v1", (
            "stages", "inputs", "frozen_protocol_sha256", "freeze_before_labels", "frozen_at",
            "labels_read_at", "study_outputs", "predictive_values", "claims"))
        _require(pack["stages"] == list(STAGES), "stage-order", "exactly five ordered stages required")
        inputs = _fields(pack["inputs"], ("protocol", "cases"), "inputs")
        # Validate and hash the protocol BEFORE opening any case labels.
        protocol = _protocol(bundle.load(inputs["protocol"], "diagnostic-accuracy-protocol-v1"))
        _require(_bool(pack["freeze_before_labels"], "freeze_before_labels") and
                 pack["frozen_protocol_sha256"] == inputs["protocol"]["sha256"] and
                 _time(pack["frozen_at"]) < _time(pack["labels_read_at"]),
                 "protocol-freeze", "protocol must be hash-frozen before reference labels are read")
        cases = bundle.load(inputs["cases"], "diagnostic-accuracy-cases-v1")
        result = reference_computation(protocol, cases)
        outputs = _items(pack["study_outputs"], "study outputs", MAX_SUPPORT, empty=True)
        for identity in outputs:
            _evidence(bundle.load(identity, "diagnostic-accuracy-evidence-v1"))
        own = [*inputs.values(), *outputs, {"path": bundle.path.name, "sha256": bundle.cache[bundle.path.name][1]}]
        claims = _claims(bundle, pack["claims"], own)
        predictive = _predictive(pack["predictive_values"], result)
        bundle.recheck()
        return {
            "schema": "diagnostic-accuracy-result-v1", "schema_version": 1, "fixture": pack["fixture"],
            "stages": list(STAGES), "evidence_level": "statistical-only", "review": "unavailable",
            "protocol_sha256": pack["frozen_protocol_sha256"],
            "input_identities": [{"path": name, "sha256": value[1]} for name, value in sorted(bundle.cache.items())],
            "metrics": result, "predictive_values": predictive, "claims": claims,
            "limitations": ["Synthetic fixtures validate software only." if pack["fixture"] else "Supplied table; no source audit performed.",
                            "Hash and timestamp declarations do not prove historical freeze timing or actual independence.",
                            "No prevalence transportability, calibration, subgroup validity or decision utility is established.",
                            "Unblinded readings are retained and disclosed; residual bias requires independent review.",
                            "The conservative English lexical claim filter is incomplete; independent review is mandatory."],
        }
    except OSError as error:
        raise ValueError("input-file: unavailable regular file or symlinked component") from error
    except (RecursionError, OverflowError, UnicodeError) as error:
        raise ValueError("invalid-record: bounded finite inputs required") from error
    finally:
        if bundle is not None:
            bundle.close()
