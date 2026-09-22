"""Optional, non-executing scientific-design contracts for research cycles.

This sidecar deliberately does not promote an idea or its predictions to a
scientific result.  It only makes the proposed mechanism and computational
contract inspectable when a cycle supplies them.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from codex_science.research_cycle import _refs, _text


ASSUMPTION_CATEGORIES = {
    "representation", "objective", "optimization", "evaluation", "data", "execution",
}
ASSUMPTION_STATUSES = {"tested", "inherited", "untested"}
OPERATORS = {
    "representation", "assumption", "objective", "conditioning", "computation", "transfer",
}


def _object(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def _id_list(value: Any, field: str, available: set[str]) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} must be a non-empty list")
    identifiers: list[str] = []
    for item in value:
        identifier = _text(item, f"{field} item")
        if identifier in identifiers:
            raise ValueError(f"duplicate {field} id: {identifier}")
        if identifier not in available:
            raise ValueError(f"{field} references unknown id: {identifier}")
        identifiers.append(identifier)
    return identifiers


def _text_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} must be a non-empty list")
    return [_text(item, f"{field} item") for item in value]


def _assumptions(problem: Mapping[str, Any], root: Path | None) -> set[str]:
    value = problem.get("assumptions")
    if not isinstance(value, list) or not value:
        raise ValueError("problem assumptions must be a non-empty list")
    identifiers: set[str] = set()
    for item in value:
        item = _object(item, "problem assumption")
        identifier = _text(item.get("id"), "problem assumption id")
        if identifier in identifiers:
            raise ValueError(f"duplicate problem assumption id: {identifier}")
        identifiers.add(identifier)
        _text(item.get("statement"), "problem assumption statement")
        if item.get("category") not in ASSUMPTION_CATEGORIES:
            raise ValueError("problem assumption category is invalid")
        if item.get("status") not in ASSUMPTION_STATUSES:
            raise ValueError("problem assumption status is invalid")
        if item.get("status") == "tested" and "evidence_refs" not in item:
            raise ValueError("tested problem assumption requires evidence_refs")
        if "evidence_refs" in item:
            if not isinstance(item["evidence_refs"], list) or not item["evidence_refs"]:
                raise ValueError("problem assumption evidence_refs must be a non-empty list")
            _refs(item["evidence_refs"], "problem assumption evidence_refs", root)
    return identifiers


def _implementation(
    value: Any, method: Mapping[str, Any], root: Path | None, field: str,
) -> None:
    implementation = _object(value, field)
    if set(implementation) != {"code_refs"}:
        raise ValueError(f"{field} must contain only code_refs")
    if not isinstance(implementation.get("code_refs"), list) or not implementation["code_refs"]:
        raise ValueError(f"{field} code_refs must be a non-empty list")
    design_refs = _refs(implementation.get("code_refs"), f"{field} code_refs", root)
    outer_refs = _refs(method.get("code_refs"), "method code_refs", root)
    if {(ref["path"], ref["sha256"]) for ref in design_refs} != {
        (ref["path"], ref["sha256"]) for ref in outer_refs
    }:
        raise ValueError(f"{field} code_refs must match method code_refs")


def _method_design(
    method: Mapping[str, Any], hypotheses: set[str], assumptions: set[str], root: Path | None,
) -> None:
    design = _object(method.get("design"), "method design")
    if "hypothesis_ids" in design:
        _id_list(design["hypothesis_ids"], "method design hypothesis_ids", hypotheses)
    if "assumption_ids" in design:
        _id_list(design["assumption_ids"], "method design assumption_ids", assumptions)
    if "operator" in design and design["operator"] not in OPERATORS:
        raise ValueError("method design operator is invalid")
    for key in ("inputs", "outputs", "computation", "complexity", "applicability", "predictions", "baseline_difference"):
        if key in design:
            _text(design[key], f"method design {key}")
    for key in ("invariants", "failure_modes"):
        if key in design:
            _text_list(design[key], f"method design {key}")
    if design.get("operator") == "transfer":
        mapping = _object(design.get("mapping"), "method design mapping")
        for key in ("source_variables", "target_variables", "correspondence", "validity_conditions"):
            _text(mapping.get(key), f"method design mapping {key}")
    elif "mapping" in design:
        raise ValueError("method design mapping is only valid for transfer")
    if "implementation" in design:
        _implementation(design["implementation"], method, root, "method design implementation")
    if "correctness_refs" in design:
        if not isinstance(design["correctness_refs"], list) or not design["correctness_refs"]:
            raise ValueError("method design correctness_refs must be a non-empty list")
        _refs(design["correctness_refs"], "method design correctness_refs", root)


def validate_design(cycle: Mapping[str, Any], run_dir: Path | str | None = None) -> None:
    """Validate supplied RDL sidecar values while accepting partial ideas.

    The core cycle validator owns the v1 cycle.  This function intentionally
    validates only design fields that are actually supplied, leaving readiness
    policy to :func:`audit_design` and its caller.
    """
    if not isinstance(cycle, Mapping):
        raise ValueError("cycle must be an object")
    root = Path(run_dir) if run_dir is not None else None
    problem = _object(cycle.get("problem", {}), "problem")
    for key in ("current_method", "unexplained"):
        if key in problem:
            _text(problem[key], f"problem {key}")
    assumptions: set[str] | None = None
    if "assumptions" in problem:
        assumptions = _assumptions(problem, root)
    methods = cycle.get("methods", [])
    if not isinstance(methods, list):
        raise ValueError("methods must be a list")
    if not all(isinstance(method, Mapping) for method in methods):
        raise ValueError("method must be an object")
    has_design = any("design" in method for method in methods)
    if has_design:
        raw_hypotheses = cycle.get("hypotheses", [])
        if not isinstance(raw_hypotheses, list) or not all(isinstance(item, Mapping) for item in raw_hypotheses):
            raise ValueError("hypotheses must be a list of objects")
        hypotheses: set[str] = set()
        for item in raw_hypotheses:
            identifier = item.get("id")
            if not isinstance(identifier, str) or not identifier.strip():
                raise ValueError("hypotheses ids are invalid")
            hypotheses.add(identifier)
        for method in methods:
            if not isinstance(method, Mapping):
                raise ValueError("method must be an object")
            if "design" in method:
                design = _object(method["design"], "method design")
                if "assumption_ids" in design and assumptions is None:
                    raise ValueError("method design assumption_ids require problem assumptions")
                _method_design(method, hypotheses, assumptions or set(), root)


def _missing_text(value: Any) -> bool:
    return not isinstance(value, str) or not value.strip()


def audit_design(cycle: Mapping[str, Any], run_dir: Path | str | None = None) -> dict[str, Any]:
    """Report proposal readiness without claiming an idea is valid or successful."""
    findings: list[dict[str, str]] = []
    try:
        validate_design(cycle, run_dir=run_dir)
    except (KeyError, TypeError, ValueError) as error:
        findings.append({"code": "invalid-supplied-design", "message": str(error)})

    problem = cycle.get("problem") if isinstance(cycle, Mapping) else None
    problem = problem if isinstance(problem, Mapping) else {}
    methods = cycle.get("methods") if isinstance(cycle, Mapping) else None
    methods = methods if isinstance(methods, list) else []
    hypotheses = cycle.get("hypotheses") if isinstance(cycle, Mapping) else None

    problem_missing: list[str] = []
    for field in ("problem.current_method", "problem.unexplained"):
        key = field.split(".", 1)[1]
        if _missing_text(problem.get(key)):
            problem_missing.append(field)
    idea_missing = list(problem_missing)
    if not isinstance(hypotheses, list) or not hypotheses:
        idea_missing.append("hypotheses")

    design_missing = list(idea_missing)
    assumptions = problem.get("assumptions")
    if not isinstance(assumptions, list) or not assumptions:
        design_missing.append("problem.assumptions")
    if not methods:
        design_missing.append("methods")
    method_readiness: list[dict[str, Any]] = []
    required_design = {
        "hypothesis_ids", "assumption_ids", "operator", "inputs", "outputs", "computation",
        "invariants", "complexity", "failure_modes", "applicability", "predictions", "baseline_difference",
    }
    hypothesis_ids: set[str] = set()
    if isinstance(hypotheses, list):
        for item in hypotheses:
            if isinstance(item, Mapping) and isinstance(item.get("id"), str):
                hypothesis_ids.add(item["id"])
    assumption_ids: set[str] = set()
    if isinstance(assumptions, list):
        assumption_ids = {
            item.get("id") for item in assumptions if isinstance(item, Mapping) and isinstance(item.get("id"), str)
        }
    for index, method in enumerate(methods):
        if not isinstance(method, Mapping) or "design" not in method:
            design_missing.append(f"methods[{index}].design")
            method_readiness.append({"method_id": method.get("id") if isinstance(method, Mapping) and isinstance(method.get("id"), str) else None, "design_ready": False, "implementation_ready": False,
                                     "missing": [f"methods[{index}].design"]})
            continue
        design = method["design"]
        missing = []
        if not isinstance(design, Mapping):
            missing.append(f"methods[{index}].design")
        else:
            missing.extend(f"methods[{index}].design.{key}" for key in sorted(required_design - set(design)))
            if design.get("operator") == "transfer" and "mapping" not in design:
                missing.append(f"methods[{index}].design.mapping")
        implementation = design.get("implementation") if isinstance(design, Mapping) else None
        code_refs = method.get("code_refs")
        structurally_valid = False
        if isinstance(design, Mapping):
            try:
                _method_design(method, hypothesis_ids, assumption_ids, Path(run_dir) if run_dir is not None else None)
                structurally_valid = True
            except (TypeError, ValueError) as error:
                findings.append({"code": "invalid-method-design", "message": f"methods[{index}]: {error}"})
        implementation_ready = not missing and structurally_valid and isinstance(implementation, Mapping) and bool(implementation.get("code_refs")) and bool(code_refs)
        if not implementation_ready:
            missing.append(f"methods[{index}].design.implementation.code_refs")
        method_readiness.append({
            "method_id": method.get("id") if isinstance(method.get("id"), str) else None,
            "design_ready": structurally_valid and (not missing or missing == [f"methods[{index}].design.implementation.code_refs"]),
            "implementation_ready": implementation_ready,
            "missing": missing,
        })
        design_missing.extend(item for item in missing if not item.endswith(".implementation.code_refs"))

    implementation_missing = list(design_missing)
    for item in method_readiness:
        if not item["implementation_ready"]:
            implementation_missing.extend(value for value in item["missing"] if value not in implementation_missing)

    readiness = {
        "problem": {"ready": not problem_missing, "missing": problem_missing},
        "idea": {"ready": not idea_missing, "missing": idea_missing},
        "design": {"ready": not design_missing and not findings, "missing": design_missing},
        "implementation": {
            "ready": not implementation_missing and not findings,
            "missing": implementation_missing,
        },
    }
    for stage, result in readiness.items():
        for field in result["missing"]:
            findings.append({"code": f"{stage}-missing", "message": f"{field} is required for {stage} readiness"})
    return {
        "schema_version": 1,
        "problem_ready": not problem_missing,
        "methods": method_readiness,
        "readiness": readiness,
        "findings": findings,
        "evidence_boundary": (
            "Readiness records supplied contracts only. It does not establish scientific validity, "
            "mechanism, novelty, implementation correctness, or experimental success."
        ),
    }
