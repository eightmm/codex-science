"""Immutable, non-executing scientific discovery-cycle contracts."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping


TERMINAL = {"improved", "rejected", "inconclusive"}
SHA256 = set("0123456789abcdef")


def _canon(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _hash(value: Any) -> str:
    return hashlib.sha256(_canon(value)).hexdigest()


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be numeric")
    try:
        value = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} must be numeric") from error
    if not math.isfinite(value):
        raise ValueError(f"{field} must be finite")
    return value


def _refs(value: Any, field: str, run_dir: Path | None = None) -> list[dict[str, str]]:
    if not isinstance(value, list): raise ValueError(f"{field} must be a list")
    seen: set[str] = set()
    result = []
    for item in value:
        if not isinstance(item, Mapping): raise ValueError(f"{field} item must be an object")
        path = _text(item.get("path"), f"{field} path")
        if Path(path).is_absolute() or ".." in Path(path).parts:
            raise ValueError(f"{field} path escapes run directory")
        digest = _text(item.get("sha256"), f"{field} sha256").lower()
        if len(digest) != 64 or set(digest) - SHA256:
            raise ValueError(f"{field} sha256 is invalid")
        if path in seen:
            raise ValueError(f"duplicate {field} path: {path}")
        seen.add(path)
        result.append({"path": path, "sha256": digest})
        if run_dir is not None:
            candidate = _confined_file(run_dir, path)
            if _file_hash(candidate) != digest: raise ValueError(f"{field} hash mismatch: {path}")
    return result


def _confined_file(root: Path, relative: str) -> Path:
    root = root.resolve()
    candidate = root / relative
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError("artifact path escapes run directory")
    current = root
    for part in Path(relative).parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise ValueError("artifact path may not traverse symlink")
    if not candidate.is_file() or candidate.is_symlink():
        raise ValueError(f"artifact is missing: {relative}")
    if root not in candidate.resolve().parents:
        raise ValueError("artifact path escapes run directory")
    return candidate


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _pointer(value: Any, pointer: str) -> Any:
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError("observation json_pointer is invalid")
    for part in pointer[1:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(value, Mapping) and part in value:
            value = value[part]
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            raise ValueError("observation json_pointer does not resolve")
    return value


def _observations(value: Any, run_dir: Path | None) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value: raise ValueError("observations are required")
    result = []
    for observation in value:
        if not isinstance(observation, Mapping): raise ValueError("observation must be an object")
        ref = _refs([observation.get("artifact_ref")], "observation artifact_ref", run_dir)[0]
        pointer = observation.get("json_pointer")
        if not isinstance(pointer, str) or not pointer.startswith("/"):
            raise ValueError("observation json_pointer is invalid")
        declared = _number(observation.get("value"), "observation value")
        if run_dir is not None:
            try: actual = _pointer(json.loads(_confined_file(run_dir, ref["path"]).read_text(encoding="utf-8")), pointer)
            except (json.JSONDecodeError, UnicodeDecodeError) as error:
                raise ValueError("observation artifact must be JSON") from error
            if _number(actual, "observed artifact value") != declared:
                raise ValueError("observation value does not match artifact locator")
        result.append({"artifact_ref": ref, "json_pointer": pointer, "value": declared})
    return result


def _execution_refs(
    experiment: Mapping[str, Any],
    method: Mapping[str, Any],
    evaluation: Mapping[str, Any],
    observations: list[dict[str, Any]],
    refs: Any,
    run_dir: Path | None,
) -> list[dict[str, str]]:
    if run_dir is None:
        raise ValueError("successful completion requires a run directory")
    records = _refs(refs, "execution_refs", run_dir)
    if not records:
        raise ValueError("successful completion requires execution_refs")
    expected_measurements = [item["artifact_ref"] for item in observations]
    expected_code = _refs(method["code_refs"], "method code_refs", run_dir)
    expected_evaluation = _refs(evaluation["artifact_refs"], "evaluation artifact_refs", run_dir)
    # Preserve identity advertised by the original measurement, not just the
    # adapter's execution envelope; a copied output must not change producers.
    for observation in observations:
        measurement_path = _confined_file(run_dir, observation["artifact_ref"]["path"])
        measurement = json.loads(measurement_path.read_text(encoding="utf-8"))
        if isinstance(measurement, Mapping):
            candidate_hash = measurement.get("candidate_sha256")
            if candidate_hash is not None and candidate_hash not in {item["sha256"] for item in expected_code}:
                raise ValueError("measurement candidate hash does not match reserved method")
            evaluator_hash = measurement.get("evaluator_sha256")
            if evaluator_hash is not None and evaluator_hash not in {item["sha256"] for item in expected_evaluation}:
                raise ValueError("measurement evaluator hash does not match frozen evaluation")
    for ref in records:
        receipt_path = _confined_file(run_dir, ref["path"])
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ValueError("execution receipt must be JSON") from error
        if not isinstance(receipt, Mapping) or receipt.get("schema_version") != 1:
            raise ValueError("execution receipt schema is invalid")
        if receipt.get("experiment_id") != experiment["id"]:
            raise ValueError("execution receipt experiment ID mismatch")
        if receipt.get("experiment_fingerprint") != experiment["fingerprint"]:
            raise ValueError("execution receipt fingerprint mismatch")
        if receipt.get("method_id") != experiment["method_id"]:
            raise ValueError("execution receipt method ID mismatch")
        if _refs(receipt.get("code_refs"), "execution receipt code_refs", run_dir) != expected_code:
            raise ValueError("execution receipt code refs mismatch")
        if _refs(receipt.get("evaluation_refs"), "execution receipt evaluation_refs", run_dir) != expected_evaluation:
            raise ValueError("execution receipt evaluation refs mismatch")
        measurement_refs = _refs(receipt.get("measurement_refs"), "execution receipt measurement_refs", run_dir)
        if not all(item in measurement_refs for item in expected_measurements):
            raise ValueError("execution receipt measurement refs mismatch")
        exit_code = receipt.get("exit_code")
        if not isinstance(exit_code, int) or isinstance(exit_code, bool) or exit_code != 0:
            raise ValueError("execution receipt exit_code must be integer zero")
        candidate_hash = receipt.get("candidate_sha256")
        if candidate_hash is not None and candidate_hash not in {item["sha256"] for item in expected_code}:
            raise ValueError("execution receipt candidate hash mismatch")
        evaluator_hash = receipt.get("evaluator_sha256")
        if evaluator_hash is not None and evaluator_hash not in {item["sha256"] for item in expected_evaluation}:
            raise ValueError("execution receipt evaluator hash mismatch")
    return records


def _ids(items: Any, field: str) -> set[str]:
    if not isinstance(items, list): raise ValueError(f"{field} must be a list")
    result: set[str] = set()
    for item in items:
        if not isinstance(item, Mapping): raise ValueError(f"{field} item must be an object")
        ident = _text(item.get("id"), f"{field} id")
        if ident in result: raise ValueError(f"duplicate {field} id: {ident}")
        result.add(ident)
    return result


def _experiment_fingerprint(item: Mapping[str, Any]) -> str:
    ignored = {"id", "state", "request_id", "outcome", "evidence_refs", "execution_refs", "observations", "failure_kind", "method_effect", "explanation_support", "verification", "novelty", "fingerprint", "retry_of"}
    return _hash({key: value for key, value in item.items() if key not in ignored})


def _classify(experiment: Mapping[str, Any], evaluation: Mapping[str, Any], observations: list[dict[str, Any]]) -> tuple[str, dict[str, str]]:
    resolution = _number(experiment["resolution"], "experiment resolution")
    intervals = []
    for item in observations:
        low = item["value"] - resolution / 2
        high = item["value"] + resolution / 2
        if not math.isfinite(low) or not math.isfinite(high):
            raise ValueError("observation interval must be finite")
        intervals.append((low, high))
    threshold = evaluation["threshold"]
    cutoff = _number(threshold["value"], "evaluation threshold value")
    op = threshold["op"]
    passes = {
        ">": lambda low, high: low > cutoff,
        ">=": lambda low, high: low >= cutoff,
        "<": lambda low, high: high < cutoff,
        "<=": lambda low, high: high <= cutoff,
    }[op]
    fails = {
        ">": lambda low, high: high <= cutoff,
        ">=": lambda low, high: high < cutoff,
        "<": lambda low, high: low >= cutoff,
        "<=": lambda low, high: low > cutoff,
    }[op]
    effect = "positive" if all(passes(low, high) for low, high in intervals) else "nonpositive" if all(fails(low, high) for low, high in intervals) else "inconclusive"
    support: dict[str, str] = {}
    for hypothesis, interval in experiment["predictions"].items():
        low, high = _number(interval[0], "prediction"), _number(interval[1], "prediction")
        if all(observed_high < low or observed_low > high for observed_low, observed_high in intervals):
            support[hypothesis] = "contradicted"
        elif all(low <= observed_low and observed_high <= high for observed_low, observed_high in intervals):
            support[hypothesis] = "consistent"
        else:
            support[hypothesis] = "inconclusive"
    return effect, support


def validate_cycle(cycle: Mapping[str, Any], run_dir: Path | str | None = None) -> None:
    if not isinstance(cycle, Mapping) or cycle.get("schema_version") != 1:
        raise ValueError("unsupported research cycle schema")
    problem = cycle.get("problem")
    if not isinstance(problem, Mapping):
        raise ValueError("problem must be an object")
    _text(problem.get("observed"), "problem observed")
    _text(problem.get("interpreted"), "problem interpreted")
    evaluation = cycle.get("evaluation")
    if not isinstance(evaluation, Mapping):
        raise ValueError("evaluation must be an object")
    for key in ("evaluator", "baseline", "split", "budget_rule"):
        _text(evaluation.get(key), f"evaluation {key}")
    metric = evaluation.get("primary_metric")
    if not isinstance(metric, Mapping) or metric.get("direction") not in {"maximize", "minimize"}:
        raise ValueError("evaluation primary_metric is invalid")
    _text(metric.get("name"), "evaluation primary_metric name")
    if "json_pointer" in metric:
        pointer = _text(metric["json_pointer"], "evaluation primary_metric json_pointer")
        if not pointer.startswith("/"):
            raise ValueError("evaluation primary_metric json_pointer is invalid")
    threshold = evaluation.get("threshold")
    if not isinstance(threshold, Mapping) or threshold.get("op") not in {">", ">=", "<", "<="}:
        raise ValueError("evaluation threshold is invalid")
    _number(threshold.get("value"), "evaluation threshold value")
    if (metric["direction"] == "maximize" and threshold["op"] not in {">", ">="}) or (metric["direction"] == "minimize" and threshold["op"] not in {"<", "<="}):
        raise ValueError("evaluation threshold direction conflicts with primary metric")
    budget = _number(evaluation.get("budget"), "evaluation budget")
    if budget < 0:
        raise ValueError("evaluation budget must be non-negative")
    root = Path(run_dir) if run_dir is not None else None
    if not evaluation.get("artifact_refs"):
        raise ValueError("evaluation artifact_refs are required")
    _refs(evaluation.get("artifact_refs"), "evaluation artifact_refs", root)
    hypotheses = _ids(cycle.get("hypotheses"), "hypotheses")
    for item in cycle["hypotheses"]:
        _text(item.get("statement"), "hypothesis statement")
        _text(item.get("conditions"), "hypothesis conditions")
        _text(item.get("falsifier"), "hypothesis falsifier")
        revision = item.get("revision", 1)
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
            raise ValueError("hypothesis revision is invalid")
    methods = _ids(cycle.get("methods"), "methods")
    methods_by_id = {item["id"]: item for item in cycle["methods"]}
    for item in cycle["methods"]:
        _text(item.get("definition"), "method definition")
        if not isinstance(item.get("code_refs", []), list):
            raise ValueError("method code_refs must be a list")
        if item.get("code_refs"):
            _refs(item["code_refs"], "method code_refs", root)
        checks = item.get("correctness_checks")
        if not isinstance(checks, list) or not checks or not all(isinstance(x, str) and x.strip() for x in checks):
            raise ValueError("method correctness_checks are required")
    experiment_ids = _ids(cycle.get("experiments"), "experiments")
    reserved = 0.0
    fingerprints: dict[str, Mapping[str, Any]] = {}
    requests: dict[str, str] = {}
    for item in cycle["experiments"]:
        if item.get("method_id") not in methods: raise ValueError("experiment references unknown method")
        cost = _number(item.get("cost"), "experiment cost")
        if cost < 0: raise ValueError("experiment cost must be non-negative")
        predictions = item.get("predictions")
        if not isinstance(predictions, Mapping) or not predictions or not set(predictions) <= hypotheses: raise ValueError("experiment predictions reference unknown hypothesis")
        for interval in predictions.values():
            if not isinstance(interval, list) or len(interval) != 2 or _number(interval[0], "prediction lower") > _number(interval[1], "prediction upper"): raise ValueError("prediction interval is invalid")
        if _number(item.get("resolution"), "experiment resolution") <= 0: raise ValueError("experiment resolution must be positive")
        if not isinstance(item.get("controls"), list) or not item["controls"] or not all(isinstance(x, str) and x.strip() for x in item["controls"]): raise ValueError("experiment controls are required")
        control_cost = _number(item.get("control_cost", 0), "experiment control_cost")
        if control_cost < 0: raise ValueError("experiment control_cost must be non-negative")
        fingerprint = _text(item.get("fingerprint", _experiment_fingerprint(item)), "experiment fingerprint")
        if fingerprint != _experiment_fingerprint(item): raise ValueError("experiment fingerprint mismatch")
        if fingerprint in fingerprints:
            prior = fingerprints[fingerprint]
            if item.get("retry_of") != prior.get("id") or prior.get("state") != "failed":
                raise ValueError("duplicate experiment fingerprint requires retry_of resolved failure")
        fingerprints[fingerprint] = item
        if item.get("state", "planned") not in {"planned", "reserved", "running", "completed", "failed", "ambiguous"}: raise ValueError("experiment state is invalid")
        if item.get("state") in {"reserved", "running", "ambiguous", "completed", "failed"}: reserved += cost + control_cost
        if item.get("request_id"):
            request = _text(item["request_id"], "experiment request_id")
            if request in requests and requests[request] != item["id"]: raise ValueError("request_id is already reserved")
            requests[request] = item["id"]
        if item.get("state") == "completed":
            _refs(item.get("evidence_refs", []), "experiment evidence_refs", root)
            observations = _observations(item.get("observations"), root)
            pointer = evaluation["primary_metric"].get("json_pointer")
            if pointer is not None and any(observation["json_pointer"] != pointer for observation in observations):
                raise ValueError("observation must use frozen primary metric locator")
            effect, support = _classify(item, evaluation, observations)
            if item.get("method_effect") != effect or item.get("explanation_support") != support or item.get("verification") != "pending" or item.get("novelty") != "unassessed":
                raise ValueError("completed experiment classification is not derived from observations")
            _execution_refs(
                item,
                methods_by_id[item["method_id"]],
                evaluation,
                observations,
                item.get("execution_refs"),
                root,
            )
        if item.get("state") == "failed" and item.get("failure_kind") not in {"execution", "implementation", "measurement"}: raise ValueError("failure kind is invalid")
    if reserved > budget: raise ValueError("reserved experiment cost exceeds frozen budget")
    if cycle.get("status", "active") not in {"active", *TERMINAL}: raise ValueError("cycle status is invalid")
    if cycle.get("status") in TERMINAL:
        _text(cycle.get("rationale"), "terminal rationale")
        completed = [x for x in cycle["experiments"] if x.get("state") == "completed"]
        unresolved = [x for x in cycle["experiments"] if x.get("state") in {"reserved", "running", "ambiguous"}]
        if unresolved: raise ValueError("terminal cycle has unresolved experiments")
        if cycle.get("status") == "improved" and not any(x.get("method_effect") == "positive" for x in completed): raise ValueError("improved requires observed positive method effect")
        if cycle.get("status") == "rejected" and not any(x.get("method_effect") == "nonpositive" or "contradicted" in x.get("explanation_support", {}).values() for x in completed): raise ValueError("rejected requires bounded no-improvement or contradiction")
    if not isinstance(cycle.get("events", []), list): raise ValueError("events must be a list")
    if any(not isinstance(event, Mapping) for event in cycle.get("events", [])): raise ValueError("event must be an object")
    revision = cycle.get("revision", 0)
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        raise ValueError("revision is invalid")
    if revision > 1 and (not isinstance(cycle.get("parent_hash"), str) or len(cycle["parent_hash"]) != 64): raise ValueError("revision requires parent_hash")
    from codex_science.discovery_design import validate_design
    validate_design(cycle, run_dir=root)
    if cycle.get("design_policy", "legacy") not in {"legacy", "required-for-reservation"}:
        raise ValueError("unsupported design policy")


def validate_transition(previous: Mapping[str, Any], current: Mapping[str, Any], run_dir: Path | str | None = None) -> None:
    """Rebuild the one allowed event rather than trusting materialized fields."""
    validate_cycle(previous, run_dir)
    if current.get("events", [])[:len(previous.get("events", []))] != previous.get("events", []) or len(current.get("events", [])) != len(previous.get("events", [])) + 1:
        raise ValueError("transition must append exactly one event")
    replayed = apply_cycle_event(previous, current["events"][-1], run_dir)
    ignored = {"cycle_hash", "revision", "parent_hash"}
    if {key: value for key, value in replayed.items() if key not in ignored} != {key: value for key, value in current.items() if key not in ignored}:
        raise ValueError("cycle transition does not match replayed event")


def new_cycle(payload: Mapping[str, Any]) -> dict[str, Any]:
    cycle = copy.deepcopy(dict(payload))
    cycle.setdefault("schema_version", 1)
    cycle.setdefault("status", "active")
    cycle.setdefault("events", [])
    cycle.setdefault("revision", 0)
    cycle.setdefault("parent_hash", None)
    for experiment in cycle.get("experiments", []):
        experiment.setdefault("state", "planned")
        experiment.setdefault("fingerprint", _experiment_fingerprint(experiment))
    _validate_genesis(cycle)
    return cycle


def _validate_genesis(cycle: Mapping[str, Any]) -> None:
    validate_cycle(cycle)
    if cycle.get("revision") != 0 or cycle.get("parent_hash") is not None or cycle.get("cycle_hash") is not None:
        raise ValueError("genesis cycle must be unsigned revision zero")
    if cycle.get("status") != "active" or cycle.get("events") != []:
        raise ValueError("genesis cycle must be active with no events")
    for experiment in cycle["experiments"]:
        if experiment.get("state") != "planned" or any(key in experiment for key in {"request_id", "outcome", "evidence_refs", "observations", "failure_kind", "method_effect", "explanation_support", "verification", "novelty"}):
            raise ValueError("genesis experiments must be planned and unobserved")


def _transition_hint(exp: Mapping[str, Any], request_id: str, prior: str | None) -> str:
    held = exp.get("request_id")
    state = f"experiment {exp['id']} is {exp['state']} ({'request_id ' + repr(held) if held else 'no request_id'})"
    if prior is None:
        return f": {state}; a reserve event is only valid for a planned experiment"
    if held and held != request_id:
        return f": {state}; use that request_id, not {request_id!r}"
    if exp["state"] == {"reserve": "planned", "running": "reserved"}[prior]:
        return f": {state}; record a {prior} event with request_id {request_id!r} first"
    return f": {state}; it accepts no further transitions" if exp["state"] in {"completed", "failed"} else f": {state}"


def apply_cycle_event(cycle: Mapping[str, Any], event: Mapping[str, Any], run_dir: Path | str | None = None) -> dict[str, Any]:
    validate_cycle(cycle, run_dir)
    result = copy.deepcopy(dict(cycle))
    event = copy.deepcopy(dict(event))
    kind = _text(event.get("kind"), "event kind")
    root = Path(run_dir) if run_dir is not None else None
    for field in ("execution_refs", "evidence_refs"):
        if field in event:
            _refs(event[field], f"event {field}", root)
    if kind in {"reserve", "running", "complete", "failure", "ambiguous"} and "request_id" in event:
        identity = (kind, event.get("experiment_id"), event.get("request_id"))
        matching = [record for record in cycle.get("events", []) if (record.get("kind"), record.get("experiment_id"), record.get("request_id")) == identity]
        if matching:
            if matching[0] == event:
                return result
            raise ValueError("conflicting replay for request event")
    if cycle.get("status") != "active":
        raise ValueError("terminal cycle cannot accept events")
    experiments = {x["id"]: x for x in result["experiments"]}
    if kind in {"reserve", "running", "complete", "failure", "ambiguous"}:
        ident = _text(event.get("experiment_id"), "event experiment_id")
        if ident not in experiments: raise ValueError("event references unknown experiment")
        exp = experiments[ident]
        exp.setdefault("state", "planned")
        exp.setdefault("fingerprint", _experiment_fingerprint(exp))
        request_id = _text(event.get("request_id"), "event request_id")
        if kind == "reserve":
            if exp.get("request_id") == request_id:
                return result
            if exp["state"] != "planned": raise ValueError("only planned experiments can be reserved" + _transition_hint(exp, request_id, None))
            method = next(item for item in result["methods"] if item["id"] == exp["method_id"])
            if not method.get("code_refs"):
                raise ValueError("experiment reservation requires code refs")
            if result.get("design_policy") == "required-for-reservation":
                from codex_science.discovery_design import audit_design
                audit = audit_design(result, run_dir=root)
                # The audit is a design completeness gate, not method validation.
                method_audit = next(item for item in audit["methods"] if item["method_id"] == method["id"])
                if not audit["problem_ready"] or not method_audit["implementation_ready"]:
                    raise ValueError("reservation requires a complete problem and computational method design")
            exp["state"] = "reserved"; exp["request_id"] = request_id
        elif kind == "running":
            if exp["state"] != "reserved" or exp.get("request_id") != request_id: raise ValueError("only matching reservations can run" + _transition_hint(exp, request_id, "reserve"))
            exp["state"] = "running"
        elif kind == "ambiguous":
            if exp["state"] not in {"reserved", "running", "ambiguous"} or exp.get("request_id") != request_id: raise ValueError("ambiguous submission requires reservation" + _transition_hint(exp, request_id, "reserve"))
            exp["state"] = "ambiguous"
        elif kind == "complete":
            if exp["state"] not in {"running", "ambiguous"} or exp.get("request_id") != request_id: raise ValueError("only matching running experiments can complete" + _transition_hint(exp, request_id, "running"))
            observations = _observations(event.get("observations"), Path(run_dir) if run_dir else None)
            pointer = result["evaluation"]["primary_metric"].get("json_pointer")
            if pointer is not None and any(item["json_pointer"] != pointer for item in observations):
                raise ValueError("observation must use frozen primary metric locator")
            effect, support = _classify(exp, result["evaluation"], observations)
            method = next(item for item in result["methods"] if item["id"] == exp["method_id"])
            execution_refs = _execution_refs(
                exp,
                method,
                result["evaluation"],
                observations,
                event.get("execution_refs"),
                Path(run_dir) if run_dir else None,
            )
            exp.update({"state": "completed", "outcome": _text(event.get("outcome"), "event outcome"), "evidence_refs": [x["artifact_ref"] for x in observations], "observations": observations, "method_effect": effect, "explanation_support": support, "verification": "pending", "novelty": "unassessed"})
            exp["execution_refs"] = execution_refs
        else:
            if exp["state"] not in {"reserved", "running", "ambiguous"} or exp.get("request_id") != request_id: raise ValueError("failure requires reservation" + _transition_hint(exp, request_id, "reserve"))
            exp["state"] = "failed"; exp["failure_kind"] = event.get("failure_kind"); exp["outcome"] = _text(event.get("outcome"), "event outcome")
            if "evidence_refs" in event:
                exp["evidence_refs"] = _refs(event["evidence_refs"], "failure evidence_refs", Path(run_dir) if run_dir else None)
            exp["verification"] = "pending"
    elif kind in {"propose", "revise"}:
        _text(event.get("rationale"), "revision rationale")
        if kind == "propose" and any(item.get("state") in {"completed", "failed"} for item in result["experiments"]):
            raise ValueError("propose is only available before resolved experiments")
        if kind == "revise":
            source = _text(event.get("source_experiment_id"), "revision source_experiment_id")
            if source not in experiments or experiments[source].get("state") not in {"completed", "failed"}: raise ValueError("revision source experiment is not resolved")
            if result.get("design_policy") == "required-for-reservation" and "lesson" not in event:
                raise ValueError("strict revision requires an observation-linked lesson")
            if "lesson" in event:
                lesson = event["lesson"]
                if not isinstance(lesson, Mapping):
                    raise ValueError("revision lesson must be an object")
                for field in ("observation", "interpretation", "limitation", "change", "next_test"):
                    _text(lesson.get(field), f"revision lesson {field}")
            if result.get("design_policy") == "required-for-reservation" and not any(event.get(name) for name in ("assumptions", "hypotheses", "methods", "experiments")):
                raise ValueError("strict revision must append a changed scientific definition or experiment")
        if "assumptions" in event:
            additions = event["assumptions"]
            if not isinstance(additions, list):
                raise ValueError("assumption additions must be a list")
            assumptions = result["problem"].setdefault("assumptions", [])
            existing = {item["id"] for item in assumptions}
            for addition in additions:
                if not isinstance(addition, Mapping) or _text(addition.get("id"), "assumption id") in existing:
                    raise ValueError("assumptions must append unique definitions")
                assumptions.append(copy.deepcopy(dict(addition)))
                existing.add(addition["id"])
        for name in ("hypotheses", "methods", "experiments"):
            additions = event.get(name, [])
            if not isinstance(additions, list): raise ValueError("revision additions must be lists")
            existing = {item["id"] for item in result[name]}
            for addition in additions:
                if not isinstance(addition, Mapping) or _text(addition.get("id"), "revision id") in existing: raise ValueError("revision must append unique definitions")
                appended = copy.deepcopy(dict(addition))
                if name == "experiments":
                    forbidden = {"request_id", "outcome", "evidence_refs", "observations", "failure_kind", "method_effect", "explanation_support", "verification", "novelty"}
                    if appended.get("state", "planned") != "planned" or forbidden.intersection(appended):
                        raise ValueError("new experiments must be unobserved and planned")
                    appended["state"] = "planned"
                    appended["fingerprint"] = _experiment_fingerprint(appended)
                result[name].append(appended)
    elif kind == "conclude":
        status = event.get("status")
        if status not in TERMINAL: raise ValueError("conclusion status is invalid")
        result["status"] = status; result["rationale"] = _text(event.get("rationale"), "event rationale")
    else: raise ValueError("unsupported cycle event")
    result["events"].append(event)
    result["revision"] = int(cycle.get("revision", 0)) + 1 if cycle.get("cycle_hash") else 0
    result["parent_hash"] = cycle.get("cycle_hash") if cycle.get("cycle_hash") else None
    result.pop("cycle_hash", None)
    validate_cycle(result, run_dir); return result


def _revision_dir(run_dir: Path | str) -> Path:
    root = Path(run_dir).resolve()
    discovery = root / "discovery"
    if discovery.exists() and discovery.is_symlink():
        raise ValueError("discovery directory may not be symlink")
    return discovery / "revisions"


def _stored_hash(cycle: Mapping[str, Any]) -> str:
    value = dict(cycle); value.pop("cycle_hash", None); return _hash(value)


def _validate_cycle_hash(cycle: Mapping[str, Any]) -> None:
    if cycle.get("cycle_hash") != _stored_hash(cycle):
        raise ValueError("research cycle hash mismatch")


def _intent_hash(cycle: Mapping[str, Any]) -> str:
    value = dict(cycle)
    for key in ("revision", "parent_hash", "cycle_hash"): value.pop(key, None)
    return _hash(value)


def save_cycle(cycle: Mapping[str, Any], run_dir: Path | str) -> Path:
    root = Path(run_dir).resolve(); validate_cycle(cycle, root); directory = _revision_dir(root); directory.mkdir(parents=True, exist_ok=True)
    if directory.is_symlink(): raise ValueError("revision directory may not be symlink")
    existing = sorted(directory.glob("*.json"))
    latest = load_cycle(root) if existing else None
    if latest is not None:
        candidate = copy.deepcopy(dict(cycle)); candidate["revision"] = latest["revision"] + 1; candidate["parent_hash"] = latest["cycle_hash"]; candidate["cycle_hash"] = _stored_hash(candidate)
        if _intent_hash(cycle) == _intent_hash(latest): return directory / f"{latest['revision']:06d}.json"
        if cycle.get("parent_hash") != latest["cycle_hash"]: raise ValueError("stale cycle parent hash")
        validate_transition(latest, candidate, root)
    else:
        _validate_genesis(cycle)
        candidate = copy.deepcopy(dict(cycle)); candidate["revision"] = 1; candidate["parent_hash"] = None; candidate["cycle_hash"] = _stored_hash(candidate)
    target = directory / f"{candidate['revision']:06d}.json"
    temporary = directory / f".{target.name}.{os.getpid()}.tmp"
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(_canon(candidate)); handle.flush(); os.fsync(handle.fileno())
    try:
        os.link(temporary, target)  # publish only if no racing writer created the immutable name
    except FileExistsError as error:
        raise ValueError("stale concurrent cycle save; reload before retry") from error
    finally:
        temporary.unlink(missing_ok=True)
    return target


def load_cycle(run_dir: Path | str) -> dict[str, Any]:
    root = Path(run_dir).resolve(); directory = _revision_dir(root)
    if directory.is_symlink():
        raise ValueError("revision directory may not be symlink")
    files = sorted(directory.glob("*.json"))
    if not files:
        raise ValueError("research cycle is missing; create it with `science_project.py discovery init --run-dir RUN --input GENESIS`")
    cycles = []
    for index, path in enumerate(files, 1):
        if path.name != f"{index:06d}.json":
            raise ValueError("research cycle revision filename is noncanonical")
        if path.is_symlink():
            raise ValueError("revision file may not be symlink")
        value = json.loads(path.read_text(encoding="utf-8"))
        cycles.append(value)
    validate_history(cycles, root)
    return cycles[-1]


def validate_history(cycles: list[Mapping[str, Any]], run_dir: Path | str | None = None) -> None:
    """Validate a complete immutable revision prefix, including replayed events."""
    if not isinstance(cycles, list) or not cycles:
        raise ValueError("research cycle history is missing")
    parent = None
    latest: Mapping[str, Any] | None = None
    for index, value in enumerate(cycles, 1):
        if not isinstance(value, dict) or value.get("revision") != index or value.get("parent_hash") != parent: raise ValueError("research cycle lineage is invalid")
        _validate_cycle_hash(value)
        validate_cycle(value, run_dir)
        if index == 1:
            genesis = dict(value); genesis.update({"revision": 0, "parent_hash": None}); genesis.pop("cycle_hash", None)
            _validate_genesis(genesis)
        else:
            validate_transition(latest, value, run_dir)
        parent = value["cycle_hash"]
        latest = value
