"""Deterministic defect checks for structured scientific-review inputs."""
from __future__ import annotations

import math
import re
import sys
from typing import Any


SCHEMA = "structured-review-input-v1"
_OBSERVATIONAL_DESIGN_TOKENS = frozenset({"cohort", "ecological"})
_CAUSAL_DESIGN_TOKENS = frozenset({
    "randomized", "randomised", "randomization", "randomisation", "rct",
    "interventional", "mr",
})
_NEGATED_RANDOMIZATION_DESIGN = re.compile(r"\b(?:non|quasi)[\s_-]*randomi[sz]ed\b")
_UNIT_ALIASES = {"ml": "mL", "l": "L"}
_UNIT_ROUNDING_RELATIVE_TOLERANCE = 0.005
_BASE_UNITS = {
    "g": ("mass", 1.0),
    "m": ("length", 1.0),
    "s": ("time", 1.0),
    "A": ("electric current", 1.0),
    "K": ("temperature", 1.0),
    "mol": ("amount of substance", 1.0),
    "cd": ("luminous intensity", 1.0),
    "L": ("volume", 1.0),
    "Hz": ("frequency", 1.0),
    "N": ("force", 1.0),
    "Pa": ("pressure", 1.0),
    "J": ("energy", 1.0),
    "W": ("power", 1.0),
    "C": ("electric charge", 1.0),
    "V": ("voltage", 1.0),
    "F": ("capacitance", 1.0),
    "Ohm": ("resistance", 1.0),
    "S": ("conductance", 1.0),
    "Wb": ("magnetic flux", 1.0),
    "T": ("magnetic flux density", 1.0),
    "H": ("inductance", 1.0),
}
_PREFIXES = {
    "Q": 1e30, "R": 1e27, "Y": 1e24, "Z": 1e21, "E": 1e18,
    "P": 1e15, "T": 1e12, "G": 1e9, "M": 1e6, "k": 1e3,
    "h": 1e2, "da": 1e1, "d": 1e-1, "c": 1e-2, "m": 1e-3,
    "u": 1e-6, "μ": 1e-6, "µ": 1e-6, "n": 1e-9, "p": 1e-12,
    "f": 1e-15, "a": 1e-18, "z": 1e-21, "y": 1e-24,
    "r": 1e-27, "q": 1e-30,
}
_SORTED_PREFIXES = sorted(_PREFIXES, key=len, reverse=True)


def _object(value: Any, label: str, allowed: set[str], required: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    if any(not isinstance(key, str) for key in value):
        raise ValueError(f"{label} field names must be strings")
    unknown = set(value) - allowed
    missing = required - set(value)
    if unknown:
        raise ValueError(f"{label} has unknown field(s): {', '.join(sorted(unknown))}")
    if missing:
        raise ValueError(f"{label} is missing field(s): {', '.join(sorted(missing))}")
    return dict(value)


def _array(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _string_list(value: Any, label: str) -> list[str]:
    return [_text(item, f"{label}[{index}]") for index, item in enumerate(_array(value, label))]


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    try:
        converted = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError(f"{label} must be a finite number") from error
    if not math.isfinite(converted):
        raise ValueError(f"{label} must be a finite number")
    return converted


def _integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    return value


def _unique_id(raw: dict[str, Any], label: str, ids: set[str]) -> str:
    identifier = _text(raw.get("id"), f"{label} id")
    if identifier in ids:
        raise ValueError(f"duplicate {label} id: {identifier}")
    ids.add(identifier)
    return identifier


def _unit(unit: str, label: str) -> tuple[str, float]:
    unit = _UNIT_ALIASES.get(unit, unit)
    if unit in _BASE_UNITS:
        dimension, scale = _BASE_UNITS[unit]
        return dimension, scale
    for prefix in _SORTED_PREFIXES:
        if unit.startswith(prefix):
            base = unit[len(prefix):]
            if base in _BASE_UNITS:
                dimension, scale = _BASE_UNITS[base]
                return dimension, _PREFIXES[prefix] * scale
    raise ValueError(f"{label} has unsupported SI unit: {unit}")


def _is_observational_design(design: str) -> bool:
    normalized = design.casefold()
    negated_randomization = _NEGATED_RANDOMIZATION_DESIGN.search(normalized) is not None
    tokens = set(re.findall(r"[a-z]+", _NEGATED_RANDOMIZATION_DESIGN.sub(" ", normalized)))
    if tokens & _CAUSAL_DESIGN_TOKENS:
        return False
    if negated_randomization:
        return True
    return bool(
        tokens & _OBSERVATIONAL_DESIGN_TOKENS
        or {"case", "control"} <= tokens
        or {"cross", "sectional"} <= tokens
    )


def _power_of_ten_mismatch(source_value: float, reported_value: float) -> int | None:
    if source_value == 0 or reported_value == 0 or (source_value < 0) != (reported_value < 0):
        return None
    log_ratio = math.log10(abs(reported_value)) - math.log10(abs(source_value))
    exponent = round(log_ratio)
    if abs(exponent) < 1:
        return None
    log_tolerance = max(
        abs(math.log10(1 + _UNIT_ROUNDING_RELATIVE_TOLERANCE)),
        abs(math.log10(1 - _UNIT_ROUNDING_RELATIVE_TOLERANCE)),
    )
    return exponent if abs(log_ratio - exponent) <= log_tolerance else None


def _validate(payload: Any) -> dict[str, Any]:
    data = _object(
        payload,
        "structured review input",
        {"schema", "claims", "studies", "analyses", "model_evaluations", "source_records", "reported_quantities"},
        {"schema"},
    )
    if data["schema"] != SCHEMA:
        raise ValueError(f"structured review input schema must be {SCHEMA}")

    claims: list[dict[str, Any]] = []
    claim_ids: set[str] = set()
    for index, raw in enumerate(_array(data.get("claims", []), "claims")):
        label = f"claims[{index}]"
        claim = _object(raw, label, {"id", "kind", "supported_by", "population", "significant"}, {"id", "kind", "supported_by"})
        claim_id = _unique_id(claim, label, claim_ids)
        claim["id"] = claim_id
        claim["kind"] = _text(claim["kind"], f"{label} kind").casefold()
        claim["supported_by"] = _string_list(claim["supported_by"], f"{label} supported_by")
        if "population" in claim:
            claim["population"] = _text(claim["population"], f"{label} population")
        if "significant" in claim and not isinstance(claim["significant"], bool):
            raise ValueError(f"{label} significant must be a boolean")
        claims.append(claim)

    studies: list[dict[str, Any]] = []
    study_ids: set[str] = set()
    for index, raw in enumerate(_array(data.get("studies", []), "studies")):
        label = f"studies[{index}]"
        study = _object(raw, label, {"id", "design", "population"}, {"id", "design"})
        study["id"] = _unique_id(study, label, study_ids)
        study["design"] = _text(study["design"], f"{label} design")
        if "population" in study:
            study["population"] = _text(study["population"], f"{label} population")
        studies.append(study)
    for claim in claims:
        missing = set(claim["supported_by"]) - study_ids
        if missing:
            raise ValueError(f"claim {claim['id']} references unknown supporting study(s): {', '.join(sorted(missing))}")

    analyses: list[dict[str, Any]] = []
    for index, raw in enumerate(_array(data.get("analyses", []), "analyses")):
        label = f"analyses[{index}]"
        analysis = _object(raw, label, {"claim_id", "tests_performed", "alpha", "correction"}, {"claim_id", "tests_performed", "alpha", "correction"})
        analysis["claim_id"] = _text(analysis["claim_id"], f"{label} claim_id")
        if analysis["claim_id"] not in claim_ids:
            raise ValueError(f"{label} references unknown claim: {analysis['claim_id']}")
        analysis["tests_performed"] = _integer(analysis["tests_performed"], f"{label} tests_performed")
        if analysis["tests_performed"] < 1:
            raise ValueError(f"{label} tests_performed must be at least 1")
        if analysis["tests_performed"] > sys.float_info.max:
            raise ValueError(f"{label} tests_performed exceeds the largest finite float")
        analysis["alpha"] = _number(analysis["alpha"], f"{label} alpha")
        if not 0 < analysis["alpha"] < 1:
            raise ValueError(f"{label} alpha must be between 0 and 1")
        if analysis["correction"] is not None:
            analysis["correction"] = _text(analysis["correction"], f"{label} correction")
        analyses.append(analysis)

    evaluations: list[dict[str, Any]] = []
    for index, raw in enumerate(_array(data.get("model_evaluations", []), "model_evaluations")):
        label = f"model_evaluations[{index}]"
        evaluation = _object(raw, label, {"train_ids", "test_ids", "train_groups", "test_groups"}, set())
        has_id_fields = "train_ids" in evaluation
        if has_id_fields != ("test_ids" in evaluation):
            raise ValueError(f"{label} must provide both train_ids and test_ids")
        evaluation["train_ids"] = _string_list(evaluation.get("train_ids", []), f"{label} train_ids")
        evaluation["test_ids"] = _string_list(evaluation.get("test_ids", []), f"{label} test_ids")
        for field in ("train_groups", "test_groups"):
            groups = evaluation.get(field, {})
            if not isinstance(groups, dict):
                raise ValueError(f"{label} {field} must be an object of group names to ID arrays")
            normalized_groups: dict[str, list[str]] = {}
            for group, ids in groups.items():
                name = _text(group, f"{label} {field} group name")
                if name in normalized_groups:
                    raise ValueError(f"{label} {field} has duplicate normalized group name: {name}")
                normalized_groups[name] = _string_list(ids, f"{label} {field}.{name}")
            evaluation[field] = normalized_groups
        if set(evaluation["train_groups"]) != set(evaluation["test_groups"]):
            raise ValueError(f"{label} train_groups and test_groups must use the same group names")
        if not has_id_fields and not evaluation["train_groups"]:
            raise ValueError(f"{label} must provide train/test IDs or group IDs")
        evaluations.append(evaluation)

    source_records: list[dict[str, Any]] = []
    source_ids: set[str] = set()
    for index, raw in enumerate(_array(data.get("source_records", []), "source_records")):
        label = f"source_records[{index}]"
        record = _object(raw, label, {"id", "value", "unit"}, {"id", "value", "unit"})
        record["id"] = _unique_id(record, label, source_ids)
        record["value"] = _number(record["value"], f"{label} value")
        record["unit"] = _text(record["unit"], f"{label} unit")
        record["dimension"], record["scale"] = _unit(record["unit"], f"{label} unit")
        source_records.append(record)

    reported_quantities: list[dict[str, Any]] = []
    for index, raw in enumerate(_array(data.get("reported_quantities", []), "reported_quantities")):
        label = f"reported_quantities[{index}]"
        quantity = _object(raw, label, {"source_id", "value", "unit"}, {"source_id", "value", "unit"})
        quantity["source_id"] = _text(quantity["source_id"], f"{label} source_id")
        if quantity["source_id"] not in source_ids:
            raise ValueError(f"{label} references unknown source record: {quantity['source_id']}")
        quantity["value"] = _number(quantity["value"], f"{label} value")
        quantity["unit"] = _text(quantity["unit"], f"{label} unit")
        quantity["dimension"], quantity["scale"] = _unit(quantity["unit"], f"{label} unit")
        source = next(item for item in source_records if item["id"] == quantity["source_id"])
        if quantity["dimension"] != source["dimension"]:
            raise ValueError(f"{label} unit has a different dimension from source record {quantity['source_id']}")
        reported_quantities.append(quantity)

    return {
        "claims": claims,
        "studies": {item["id"]: item for item in studies},
        "analyses": analyses,
        "model_evaluations": evaluations,
        "source_records": {item["id"]: item for item in source_records},
        "reported_quantities": reported_quantities,
    }


def structured_review_findings(payload: Any) -> list[dict[str, str]]:
    """Find defects provable from a validated structured review input."""
    data = _validate(payload)
    findings: list[dict[str, str]] = []

    for claim in data["claims"]:
        supporting = [data["studies"][study_id] for study_id in claim["supported_by"]]
        observational_designs = sorted(
            study["design"].strip() for study in supporting if _is_observational_design(study["design"])
        )
        if claim["kind"] == "causal" and supporting and len(observational_designs) == len(supporting):
            findings.append({
                "code": "causal-overreach",
                "severity": "major",
                "message": f"Causal claim {claim['id']} is supported only by observational study designs: {', '.join(observational_designs)}.",
            })

        if "population" in claim:
            target = claim["population"].casefold()
            declared_populations = [
                study["population"].casefold()
                for study in supporting
                if "population" in study
            ]
            covered = any(
                target == population
                or target in {item.strip() for item in re.split(r"[,;/]|\band\b", population)}
                or (
                    target.startswith(population)
                    and len(target) > len(population)
                    and not target[len(population)].isalnum()
                )
                for population in declared_populations
            )
            if declared_populations and not covered:
                findings.append({
                    "code": "population-overreach",
                    "severity": "major",
                    "message": f"Claim {claim['id']} targets population {claim['population']!r}, which no supporting study lists.",
                })

    claims_by_id = {claim["id"]: claim for claim in data["claims"]}
    for analysis in data["analyses"]:
        claim = claims_by_id[analysis["claim_id"]]
        correction = analysis["correction"]
        normalized_correction = " ".join(correction.casefold().split()) if correction is not None else None
        if (
            analysis["tests_performed"] > 1
            and normalized_correction in {None, "none", "uncorrected", "no correction", "unadjusted"}
            and claim.get("significant") is True
        ):
            tests = analysis["tests_performed"]
            alpha = analysis["alpha"]
            family_wise_error = 1 - (1 - alpha) ** tests
            findings.append({
                "code": "multiplicity-uncorrected",
                "severity": "major",
                "message": (
                    f"Claim {claim['id']} is marked significant among {tests} uncorrected tests; "
                    f"family-wise error under independence: 1-(1-alpha)^m=1-(1-{alpha:g})^{tests}={family_wise_error:.3f}."
                ),
            })

    for evaluation in data["model_evaluations"]:
        overlap_count = len(set(evaluation["train_ids"]) & set(evaluation["test_ids"]))
        overlap_sources: list[str] = []
        if overlap_count:
            overlap_sources.append(f"sample IDs ({overlap_count})")
        for group in sorted(set(evaluation["train_groups"]) & set(evaluation["test_groups"])):
            count = len(set(evaluation["train_groups"][group]) & set(evaluation["test_groups"][group]))
            overlap_count += count
            if count:
                overlap_sources.append(f"{group} group IDs ({count})")
        if overlap_count:
            findings.append({
                "code": "train-test-leakage",
                "severity": "major",
                "message": f"Train/test overlap count {overlap_count}: {', '.join(overlap_sources)}.",
            })

    for quantity in data["reported_quantities"]:
        source = data["source_records"][quantity["source_id"]]
        if source["scale"] == quantity["scale"]:
            exponent = _power_of_ten_mismatch(source["value"], quantity["value"])
            if exponent is None:
                continue
            findings.append({
                "code": "unit-scale-mismatch",
                "severity": "major",
                "message": (
                    f"Reported {quantity['value']:g} {quantity['unit']} for source {source['value']:g} {source['unit']} "
                    f"differs by a power-of-ten factor (10^{exponent}); "
                    "the detector uses a 0.5% relative tolerance to accept ordinary rounding."
                ),
            })
            continue
        factor = source["scale"] / quantity["scale"]
        converted_value = source["value"] * factor
        if not math.isfinite(converted_value):
            raise ValueError(f"reported_quantities value conversion overflows for source record {source['id']}")
        exponent = _power_of_ten_mismatch(converted_value, quantity["value"])
        equals_unconverted_source = quantity["value"] == source["value"] != 0
        if exponent is not None or equals_unconverted_source:
            reason = (
                f"repeats the unconverted source value {source['value']:g} {source['unit']}"
                if equals_unconverted_source
                else f"differs from the converted value by a power-of-ten factor (10^{exponent})"
            )
            findings.append({
                "code": "unit-scale-mismatch",
                "severity": "major",
                "message": (
                    f"Reported {quantity['value']:g} {quantity['unit']} for source {source['value']:g} {source['unit']} "
                    f"{reason}; converting the source gives {converted_value:g} {quantity['unit']}."
                ),
            })

    unique = {(item["code"], item["message"]): item for item in findings}
    return sorted(unique.values(), key=lambda item: (item["severity"], item["code"], item["message"]))
