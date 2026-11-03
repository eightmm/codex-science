"""Read-only, offline validation of the experiment-design workflow pack.

These records are pack-local artifacts, not new manifest or receipt fields.
Hash agreement proves byte identity, not preregistration time or scientific truth.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import stat
from datetime import datetime
from pathlib import Path, PurePosixPath
from statistics import NormalDist
from typing import Any


STAGES = ("01-question", "02-power", "03-randomisation", "04-analysis-plan", "05-controls", "06-review-handoff")
_MAX_JSON_BYTES = 64 * 1024 * 1024
# Index, six stages, two assumptions, analysis, results and the used plan.
_MAX_TOTAL_BYTES = 12 * _MAX_JSON_BYTES


def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise ValueError(f"{code}: {message}")


def _object(value: Any, label: str) -> dict:
    _require(isinstance(value, dict), "invalid-record", f"{label} must be an object")
    return value


def _text(value: Any, label: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), "invalid-record", f"{label} must be non-empty text")
    return value


def _number(value: Any, label: str, low: float, high: float | None = None) -> float:
    _require(type(value) in (int, float), "invalid-record", f"{label} must be numeric")
    try:
        valid = math.isfinite(value) and value >= low and (high is None or value <= high)
    except OverflowError:
        valid = False
    _require(valid, "invalid-record", f"{label} is outside its finite range")
    return value


def _integer(value: Any, label: str, minimum: int = 0) -> int:
    _require(type(value) is int and value >= minimum, "invalid-record", f"{label} must be an integer >= {minimum}")
    return value


def _list(value: Any, label: str, *, nonempty: bool = False) -> list:
    _require(isinstance(value, list) and (bool(value) or not nonempty), "invalid-record", f"{label} must be a list")
    return value


def _texts(value: Any, label: str, *, nonempty: bool = False) -> list[str]:
    values = _list(value, label, nonempty=nonempty)
    for item in values:
        _text(item, label)
    _require(len(set(values)) == len(values), "invalid-record", f"{label} must be unique")
    return values


def _time(value: Any, label: str) -> datetime:
    try:
        stamp = datetime.fromisoformat(_text(value, label).replace("Z", "+00:00"))
        _require(stamp.utcoffset() is not None, "invalid-record", f"{label} needs a timezone")
        return stamp
    except ValueError as error:
        raise ValueError(f"invalid-record: {label} must be a timezone-aware ISO timestamp") from error


def _read_bytes(path: Path, label: str) -> bytes:
    info = os.lstat(path)
    _require(stat.S_ISREG(info.st_mode), "unavailable-artifact", f"{label} must be a regular file")
    _require(info.st_size <= _MAX_JSON_BYTES, "input-too-large", f"{label} exceeds {_MAX_JSON_BYTES} bytes")
    absolute = Path(os.path.abspath(path))
    with _Bundle(absolute.parent) as reader:
        return reader.read(PurePosixPath(absolute.name), label)


def _pairs(items: list[tuple[str, Any]]) -> dict:
    result = {}
    for name, value in items:
        if name in result:
            raise ValueError(f"duplicate JSON key: {name}")
        result[name] = value
    return result


def _json(raw: bytes, label: str) -> dict:
    try:
        return _object(json.loads(raw, object_pairs_hook=_pairs), label)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise ValueError(f"invalid-record: unreadable JSON: {label}: {error}") from error


def _load(path: Path) -> dict:
    return _json(_read_bytes(path, path.name), path.name)


def _signature(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _open_root(root):
    """Pin every ancestor so a transient pathname swap cannot redirect reads."""
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
    descriptor = os.open(root.anchor, flags)
    try:
        opened = os.fstat(descriptor)
        _require(stat.S_ISDIR(opened.st_mode), "unavailable-artifact", "root must be a directory")
        identities = [(opened.st_dev, opened.st_ino)]
        for part in root.parts[1:]:
            before = os.lstat(part, dir_fd=descriptor)
            _require(stat.S_ISDIR(before.st_mode), "unavailable-artifact", "root ancestors must be real directories")
            child = os.open(part, flags, dir_fd=descriptor)
            try:
                opened = os.fstat(child)
                _require(stat.S_ISDIR(opened.st_mode)
                         and (before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino),
                         "unavailable-artifact", "root ancestor changed during pinning")
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
        self.snapshots = {}
        self.cache = {}
        self.total_bytes = 0
        self.fd, self.identities = _open_root(root)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        os.close(self.fd)

    def _read(self, relative, label, checked=None):
        opened_dirs = []
        try:
            directory = self.fd
            flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
            for part in relative.parts[:-1]:
                before = os.lstat(part, dir_fd=directory)
                _require(stat.S_ISDIR(before.st_mode), "unavailable-artifact", "artifact ancestors must be real directories")
                directory = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
                opened_dirs.append(directory)
                actual = os.fstat(directory)
                _require(stat.S_ISDIR(actual.st_mode)
                         and (before.st_dev, before.st_ino) == (actual.st_dev, actual.st_ino),
                         "unavailable-artifact", "artifact directory replaced")
            before = os.lstat(relative.name, dir_fd=directory)
            _require(stat.S_ISREG(before.st_mode), "unavailable-artifact", f"{label} must be a regular file")
            _require(before.st_size <= _MAX_JSON_BYTES, "input-too-large", f"{label} exceeds 64 MiB")
            descriptor = os.open(relative.name, flags, dir_fd=directory)
            with os.fdopen(descriptor, "rb") as stream:
                actual = os.fstat(stream.fileno())
                _require(stat.S_ISREG(actual.st_mode), "unavailable-artifact", "input must be a regular file")
                _require(before.st_size == actual.st_size, "input-too-large", "input size changed during open")
                _require(_signature(before) == _signature(actual),
                         "unavailable-artifact", "input changed during open")
                signature = _signature(actual)
                identity = signature[:2]
                cached = self.cache.get(identity)
                if cached is not None:
                    _require(signature == cached[1], "unavailable-artifact", "cached input changed")
                    if checked is None or identity in checked:
                        return cached[0], signature
                limit = _MAX_JSON_BYTES if checked is not None else min(_MAX_JSON_BYTES, _MAX_TOTAL_BYTES - self.total_bytes)
                _require(actual.st_size <= limit, "input-too-large", "aggregate input byte budget exceeded")
                raw = stream.read(limit + 1)
                after = os.fstat(stream.fileno())
            _require(len(raw) <= limit, "input-too-large", "input grew beyond its byte budget")
            _require(len(raw) == actual.st_size and _signature(actual) == _signature(after),
                     "unavailable-artifact", "input changed during bounded read")
            return raw, signature
        except OSError as error:
            raise ValueError(f"unavailable-artifact: {label}: unavailable or unsafe input") from error
        finally:
            for descriptor in reversed(opened_dirs):
                os.close(descriptor)

    def read(self, relative, label):
        name = relative.as_posix()
        if name not in self.snapshots:
            raw, signature = self._read(relative, label)
            identity = signature[:2]
            if identity not in self.cache:
                self.cache[identity] = (raw, signature, hashlib.sha256(raw).hexdigest())
                self.total_bytes += len(raw)
            self.snapshots[name] = self.cache[identity]
        return self.snapshots[name][0]

    def _check_root(self):
        descriptor, identities = _open_root(self.root)
        try:
            _require(identities == self.identities, "unavailable-artifact", "bundle root replaced")
        finally:
            os.close(descriptor)

    def finish(self):
        self._check_root()
        checked = set()
        for name, (_, signature, digest) in self.snapshots.items():
            raw, current = self._read(PurePosixPath(name), name, checked)
            _require(current == signature and hashlib.sha256(raw).hexdigest() == digest,
                     "unavailable-artifact", "input replaced during validation")
            checked.add(current[:2])
        self._check_root()


def _artifact(root: Path | _Bundle, identity: Any, label: str) -> dict:
    identity = _object(identity, label)
    relative = PurePosixPath(_text(identity.get("path"), f"{label}.path"))
    _require(not relative.is_absolute() and ".." not in relative.parts and "\\" not in str(relative), "invalid-path", label)
    digest = identity.get("sha256")
    _require(isinstance(digest, str) and len(digest) == 64 and all(c in "0123456789abcdef" for c in digest), "invalid-record", f"{label}.sha256")
    if isinstance(root, _Bundle):
        raw = root.read(relative, label)
    else:
        with _Bundle(Path(os.path.abspath(root))) as reader:
            raw = reader.read(relative, label)
    _require(hashlib.sha256(raw).hexdigest() == digest, "artifact-hash-mismatch", label)
    return _json(raw, label)


def _family(plan: dict) -> dict[str, dict]:
    family = {}
    for item in _list(plan.get("primary_family"), "primary_family", nonempty=True):
        item = _object(item, "comparison")
        identifier = _text(item.get("id"), "comparison.id")
        _require(identifier not in family, "invalid-record", "duplicate comparison")
        _text(item.get("outcome"), "comparison.outcome")
        _number(item.get("threshold"), "comparison.threshold", 0, 1)
        _require(item["threshold"] > 0, "invalid-record", "threshold must be positive")
        family[identifier] = item
    return family


def _analysis_rules(plan: dict) -> None:
    _text(plan.get("method"), "method")
    _text(plan.get("missing_data_rule"), "missing_data_rule")
    _texts(plan.get("exclusion_rules"), "exclusion_rules")
    _require(type(plan.get("sequential")) is bool, "invalid-record", "sequential must be boolean")
    rule = plan.get("stopping_rule")
    _require(isinstance(rule, str) and bool(rule.strip()), "stopping-rule-absent", "a fixed or sequential stopping rule is required")
    if plan["sequential"]:
        _text(plan.get("sequential_error_control"), "sequential_error_control")


def _power(root: _Bundle, power: dict, question: dict, family: dict, bundle: dict) -> dict:
    source = _object(power.get("effect_source"), "effect_source")
    _require(source.get("origin") in ("external", "independent-pilot", "scientific-minimum"), "own-result-effect", "power cannot use this study's own result")
    sources = ((source.get("artifact"), "effect_source.artifact"), (power.get("variance_source"), "variance_source"))
    for name in ("results", "analysis"):
        output = bundle.get(name)
        if output is not None:
            for identity, label in sources:
                identity = _object(identity, label)
                output = _object(output, name)
                _require(identity.get("sha256") != output.get("sha256"), "own-result-effect", f"{label} cannot use this study's {name}")
            _artifact(root, output, name)
    for identity, label in sources:
        _artifact(root, identity, label)
    _require(power.get("count_unit") == question["experimental_unit"], "pseudoreplication", "sample size must count experimental units, not observational repeats")
    _require(power.get("method") == "normal-approximation-two-group", "unsupported-power-method", "supply a two-group normal approximation; complex designs need specialist review")
    effect = _number(power.get("assumed_effect"), "assumed_effect", 0)
    variance = _number(power.get("variance"), "variance", 0)
    _require(effect > 0 and variance > 0, "invalid-record", "effect and variance must be positive")
    target = _number(power.get("target_power"), "target_power", 0, 1)
    _require(0 < target < 1, "invalid-record", "target_power must be inside (0, 1)")
    arms = _list(power.get("arms"), "arms", nonempty=True)
    _require(len(arms) == 2, "invalid-record", "two arms are required")
    names, analyzable, counts, ratios, costs = [], [], [], [], []
    for arm in arms:
        arm = _object(arm, "arm")
        names.append(_text(arm.get("id"), "arm.id"))
        required = _integer(arm.get("required_analyzable"), "required_analyzable", 2)
        planned = _integer(arm.get("planned"), "planned", 2)
        attrition = _number(arm.get("attrition"), "attrition", 0, 1)
        _require(attrition < 1, "invalid-record", "attrition must be below 1")
        _require(planned >= math.ceil(required / (1 - attrition)), "allocation-attrition", "planned arm count does not cover attrition")
        analyzable.append(required)
        counts.append(planned)
        ratios.append(_number(arm.get("allocation"), "allocation", 0))
        _require(ratios[-1] > 0, "invalid-record", "allocation must be positive")
        costs.append(planned * _number(arm.get("cost_per_unit"), "cost_per_unit", 0))
    _require(len(set(names)) == 2, "invalid-record", "arm IDs must be unique")
    _require(math.isclose(counts[0] / counts[1], ratios[0] / ratios[1], rel_tol=1e-12), "allocation-attrition", "planned counts must reflect the declared allocation ratio")
    _text(power.get("cost_unit"), "cost_unit")
    alpha = min(item["threshold"] for item in family.values())
    try:
        z = NormalDist().inv_cdf(1 - alpha / 2)
        signal = effect / math.sqrt(variance * sum(1 / n for n in analyzable))
        achieved = NormalDist().cdf(signal - z) + NormalDist().cdf(-signal - z)
    except (ValueError, OverflowError, ZeroDivisionError) as error:
        raise ValueError("invalid-record: power calculation is not finite") from error
    _require(achieved >= target, "insufficient-power", "analyzable arm counts do not achieve the assumed normal-approximation power")
    _require(math.isfinite(sum(costs)), "invalid-record", "planned cost must be finite")
    return {"achieved_power": achieved, "planned_cost": sum(costs), "planned_units": sum(counts)}


def _claims(claims: Any) -> None:
    for claim in _list(claims, "claims"):
        claim = _object(claim, "claim")
        evidence = claim.get("evidence")
        assertion = claim.get("assertion")
        permitted = {
            "association": {"association"},
            "numerical-agreement": {"numerical-agreement"},
            "unavailable": {"unavailable"},
            "review-approval": {"review-status"},
        }
        _require(isinstance(evidence, str) and evidence in permitted and isinstance(assertion, str) and assertion in permitted[evidence], "inference-boundary", "association, computation, absence and approval cannot establish stronger claims")


def _audit(root: _Bundle, bundle: dict, plan: dict, family: dict, controls: dict) -> list[dict]:
    analysis = _artifact(root, bundle.get("analysis"), "analysis")
    _require(analysis.get("schema") == "experiment-analysis-v1", "invalid-record", "analysis schema")
    used_identity = analysis.get("used_plan")
    _artifact(root, used_identity, "used_plan")
    _require(used_identity["sha256"] == bundle["analysis_plan"]["sha256"], "plan-hash-mismatch", "analysis did not use the frozen plan")
    actual = _family(analysis)
    _analysis_rules(analysis)
    changes = []
    for identifier in sorted(family.keys() - actual.keys()):
        changes.append(("dropped-comparison", identifier))
    for identifier in sorted(actual.keys() - family.keys()):
        changes.append(("added-comparison", identifier))
    for identifier in sorted(family.keys() & actual.keys()):
        for field, kind in (("outcome", "changed-outcome"), ("threshold", "changed-threshold")):
            if family[identifier][field] != actual[identifier][field]:
                changes.append((kind, identifier))
    for rule in set(analysis["exclusion_rules"]) - set(plan["exclusion_rules"]):
        changes.append(("post-hoc-exclusion", rule))
    for rule in set(plan["exclusion_rules"]) - set(analysis["exclusion_rules"]):
        changes.append(("dropped-exclusion", rule))
    for field in ("method", "missing_data_rule", "stopping_rule", "multiplicity", "sequential", "sequential_error_control"):
        if analysis.get(field) != plan.get(field):
            changes.append(("changed-analysis-rule", field))
    labels = {}
    for deviation in _list(analysis.get("deviations"), "deviations"):
        deviation = _object(deviation, "deviation")
        key = (_text(deviation.get("kind"), "deviation.kind"), _text(deviation.get("target"), "deviation.target"))
        _require(key not in labels, "invalid-record", "duplicate deviation")
        _text(deviation.get("reason"), "deviation.reason")
        labels[key] = deviation.get("label")
    _require(set(labels) == set(changes) and all(label == "exploratory" for label in labels.values()), "unlabelled-deviation", "every outcome, comparison, threshold, rule or exclusion deviation must be exploratory")
    results = _artifact(root, bundle.get("results"), "results")
    _require(results.get("schema") == "experiment-results-v1", "invalid-record", "results schema")
    rows = _list(results.get("results"), "results.results", nonempty=True)
    ids = []
    for row in rows:
        row = _object(row, "result")
        ids.append(_text(row.get("id"), "result.id"))
        _require(row.get("status") in ("positive", "negative", "null", "failed", "unavailable"), "invalid-record", "result.status")
        _require(row.get("control_status") in ("passed", "failed", "unavailable"), "invalid-record", "control_status")
    _require(len(set(ids)) == len(ids) and set(family) | set(actual) | set(controls["control_ids"]) <= set(ids), "incomplete-results", "every planned comparison and control needs a result, explicitly unavailable if absent")
    reported = _list(analysis.get("reported_results"), "reported_results")
    _require(sorted(rows, key=lambda row: row["id"]) == sorted(reported, key=lambda row: _text(_object(row, "reported_result").get("id"), "reported_result.id")), "omitted-result", "audit must retain negative, null, failed-control and unavailable results unchanged")
    _claims(analysis.get("claims"))
    return [{"kind": kind, "target": target, "label": "exploratory"} for kind, target in sorted(changes)]


def validate_experiment_design_pack(path: Path, *, mode: str = "preregister") -> dict:
    """Validate immutable artifact identities; return unreviewed findings context."""
    try:
        return _validate_pack(path, mode=mode)
    except (OSError, ArithmeticError, RecursionError, RuntimeError) as error:
        raise ValueError(f"invalid-record: unable to validate pack: {error}") from error


def _validate_pack(path: Path, *, mode: str) -> dict:
    _require(mode in ("preregister", "audit"), "invalid-mode", "choose preregister or audit")
    path = Path(os.path.abspath(path))
    with _Bundle(path.parent) as root:
        result = _validate_snapshot(root, path.name, mode=mode)
        root.finish()
        return result


def _validate_snapshot(root: _Bundle, entry: str, *, mode: str) -> dict:
    bundle = _json(root.read(PurePosixPath(entry), entry), entry)
    _require(bundle.get("schema") == "experiment-design-pack-v1", "invalid-record", "pack schema")
    records = {name: _artifact(root, bundle.get(name), name) for name in ("question", "power", "randomisation", "analysis_plan", "controls", "handoff")}
    for name, record in records.items():
        _require(record.get("schema") == f"experiment-{name.replace('_', '-')}-v1", "invalid-record", f"{name} schema")
    question, plan = records["question"], records["analysis_plan"]
    for field in ("question", "estimand", "population", "experimental_unit", "observational_unit", "assignment_mechanism", "primary_outcome", "observation_window"):
        _text(question.get(field), field)
    _claims(question.get("claims"))
    family = _family(plan)
    _require(question["primary_outcome"] in {item["outcome"] for item in family.values()}, "invalid-record", "primary outcome must be in the frozen family")
    alpha = _number(plan.get("alpha"), "alpha", 0, 1)
    _require(0 < alpha < 1, "invalid-record", "alpha must be inside (0, 1)")
    multiplicity = plan.get("multiplicity")
    _require(isinstance(multiplicity, str) and multiplicity in ("none", "bonferroni"), "multiplicity-ignored", "use an explicit primary-family correction")
    _require((len(family) == 1 or multiplicity == "bonferroni") and all(item["threshold"] <= alpha / len(family) for item in family.values()), "multiplicity-ignored", "thresholds must cover the entire declared primary family")
    _analysis_rules(plan)
    _require(plan.get("outcomes_seen") is False, "outcome-dependent-plan", "frozen plan must precede outcomes")
    power_summary = _power(root, records["power"], question, family, bundle)
    assignment = records["randomisation"]
    for field in ("assignment_seed", "blinding_seed"):
        _integer(assignment.get(field), field)
    for field in ("method", "blinding", "allocation_concealment"):
        _text(assignment.get(field), field)
    _require(assignment.get("assignment_mechanism") == question["assignment_mechanism"], "assignment-mismatch", "randomisation must match the question")
    controls = records["controls"]
    _texts(controls.get("control_ids"), "control_ids", nonempty=True)
    for field in ("failure_rule", "negative_result_handling"):
        _text(controls.get(field), field)
    handoff = records["handoff"]
    _text(handoff.get("producer"), "producer")
    _text(handoff.get("reviewer"), "reviewer")
    _require(handoff["producer"] != handoff["reviewer"] and handoff.get("status") == "pending-independent-review", "independent-review-required", "pack can hand off but cannot mark itself reviewed")
    frozen = _time(plan.get("frozen_at"), "frozen_at")
    handed = _time(handoff.get("handed_off_at"), "handed_off_at")
    _require(frozen <= handed, "stage-order", "review handoff must follow plan freeze")
    _require(handoff.get("analysis_plan") == bundle["analysis_plan"], "plan-hash-mismatch", "handoff must bind the frozen plan")
    for name in ("question", "power", "randomisation", "analysis_plan", "controls"):
        _require(_object(handoff.get("inputs"), "handoff.inputs").get(name) == bundle[name], "handoff-mismatch", f"handoff must bind {name}")
    deviations = []
    if mode == "preregister":
        _require(bundle.get("data_collection_started_at") is None and bundle.get("outcomes_available_at") is None and bundle.get("analysis") is None, "data-already-arrived", "use audit mode after collection or analysis")
    else:
        started = _time(bundle.get("data_collection_started_at"), "data_collection_started_at")
        arrived = _time(bundle.get("outcomes_available_at"), "outcomes_available_at")
        _require(handed < started <= arrived, "stage-order", "independent handoff must precede collection and outcomes")
        deviations = _audit(root, bundle, plan, family, controls)
    return {
        "schema": "experiment-design-validation-v1", "mode": mode,
        "status": "unreviewed-audit" if mode == "audit" else "ready-for-independent-review",
        "stage_ids": list(STAGES), "inputs": {name: bundle[name] for name in records},
        "power": power_summary, "deviations": deviations,
        "limitations": ["Synthetic fixtures do not validate real studies.", "Hashes and declared timestamps do not authenticate preregistration or review.", "Power uses a two-group normal approximation with externally justified effect and variance; sequential operating characteristics need specialist review."],
    }
