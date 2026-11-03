"""Join assay outcomes to immutable candidate identities and propose a batch.

The update is an explicit parent-outcome heuristic, not a trained surrogate or
calibrated Bayesian optimization. Held-out outcomes never affect selection.
"""

from __future__ import annotations

import csv
import io
import math
import statistics
from typing import Any, Mapping

from codex_science.experiment_planner import plan_next_experiment


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"{label} must be finite numeric")
    try:
        number = float(value)
    except (ValueError, OverflowError) as error:
        raise ValueError(f"{label} must be finite numeric") from error
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite numeric")
    return number


def import_assay_feedback(contract: Mapping[str, Any], csv_text: str) -> dict[str, Any]:
    if contract.get("schema") != "campaign-feedback-v1":
        raise ValueError("unsupported feedback schema")
    assay = contract.get("assay")
    if not isinstance(assay, dict):
        raise ValueError("assay contract required")
    for field in ("id", "target_construct_id", "unit"):
        _text(assay.get(field), "assay " + field)
    direction = assay.get("direction")
    if direction not in {"maximize", "minimize"}:
        raise ValueError("explicit assay direction required")
    prediction_contract = contract.get("prediction_contract")
    if not isinstance(prediction_contract, dict) or prediction_contract.get("scale") != "assay-value" or prediction_contract.get("unit") != assay["unit"]:
        raise ValueError("predictions must be declared on the same assay-value scale and unit")
    for field in ("source_id", "calibration_reference"):
        _text(prediction_contract.get(field), "prediction " + field)
    candidates = {}
    constructs = set()
    raw_candidates = contract.get("candidates")
    if not isinstance(raw_candidates, list) or not raw_candidates:
        raise ValueError("candidates required")
    for raw in raw_candidates:
        if not isinstance(raw, dict):
            raise ValueError("candidate must be an object")
        key = _text(raw.get("id"), "candidate id")
        if key in candidates:
            raise ValueError("duplicate candidate ID")
        construct = _text(raw.get("construct_id"), "candidate construct_id")
        if construct in constructs:
            raise ValueError("duplicate immutable candidate construct; aliases cannot cross feedback/holdout roles")
        constructs.add(construct)
        if raw.get("role") not in {"feedback", "holdout", "candidate"}:
            raise ValueError("candidate role must be feedback, holdout or candidate")
        item = dict(raw)
        item["prediction"] = _finite(raw.get("prediction"), "prediction")
        item["cost"] = _finite(raw.get("cost", 1), "cost")
        if item["cost"] < 0:
            raise ValueError("cost must be nonnegative")
        if "control" in item and type(item["control"]) is not bool:
            raise ValueError("control must be boolean")
        candidates[key] = item
    reader = csv.DictReader(io.StringIO(csv_text))
    required = {"candidate_id", "assay_id", "target_construct_id", "construct_id", "unit", "replicate_id", "status", "value"}
    if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames) or not required.issubset(reader.fieldnames):
        raise ValueError("CSV requires unique identity, status and value columns")
    if set(reader.fieldnames) - required - {"note"}:
        raise ValueError("unsupported CSV columns")
    seen = set()
    rows = []
    measured: dict[str, list[float]] = {}
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("CSV row width mismatch")
        key = row["candidate_id"]
        if key not in candidates:
            raise ValueError("unknown candidate ID")
        for field, expected in (("assay_id", assay["id"]), ("target_construct_id", assay["target_construct_id"]),
                                ("construct_id", candidates[key]["construct_id"]), ("unit", assay["unit"])):
            if row[field] != expected:
                raise ValueError(f"measurement {field} mismatch")
        replicate = _text(row["replicate_id"], "independent replicate ID")
        identity = (candidates[key]["construct_id"], replicate)
        if identity in seen:
            raise ValueError("duplicate independent replicate")
        seen.add(identity)
        status = row["status"]
        if status not in {"measured", "missing", "failed", "censored"}:
            raise ValueError("unknown measurement status")
        if status == "measured":
            value = _finite(row["value"], "measurement")
            measured.setdefault(key, []).append(value)
        else:
            if row["value"].strip():
                raise ValueError("unquantified outcome must not carry a numeric point estimate")
            value = None
        rows.append({**row, "value": value})
    if not rows:
        raise ValueError("no assay outcomes")
    summaries = {}
    for key, values in measured.items():
        mean = statistics.mean(values)
        se = statistics.stdev(values) / math.sqrt(len(values)) if len(values) > 1 else None
        _finite(mean, "mean")
        if se is not None:
            _finite(se, "standard error")
        summaries[key] = {"n_independent": len(values), "mean": mean, "standard_error": se}
    heldout = [key for key in summaries if candidates[key]["role"] == "holdout"]
    mae = statistics.mean(abs(candidates[key]["prediction"] - summaries[key]["mean"]) for key in heldout) if heldout else None
    if mae is not None:
        _finite(mae, "heldout MAE")
    weight = _finite(contract.get("parent_feedback_weight", 0.5), "parent feedback weight")
    if not 0 <= weight <= 1:
        raise ValueError("parent feedback weight must be in [0,1]")
    controls = contract.get("controls")
    if not isinstance(controls, list) or not controls:
        raise ValueError("explicit controls required")
    control_ids = set()
    for control in controls:
        if not isinstance(control, dict) or type(control.get("passed")) is not bool:
            raise ValueError("controls require boolean outcomes")
        key = _text(control.get("id"), "control ID")
        if key in control_ids:
            raise ValueError("duplicate control ID")
        control_ids.add(key)
    proposed = []
    attempted = {row["candidate_id"] for row in rows}
    for key, item in candidates.items():
        if item["role"] != "candidate" or key in attempted:
            continue
        parent = item.get("parent_id")
        if parent is not None and parent not in candidates:
            raise ValueError("unknown parent candidate")
        if parent == key:
            raise ValueError("candidate cannot be its own parent")
        score = item["prediction"]
        feedback_used = parent in summaries and candidates[parent]["role"] == "feedback"
        if feedback_used:
            score = (1 - weight) * score + weight * summaries[parent]["mean"]
        _finite(score, "updated candidate score")
        proposed.append({"id": key, "properties": {"assay_utility": score}, "cost": item["cost"],
                         "diversity_group": _text(item.get("diversity_group", key), "diversity group"),
                         "control": item.get("control", False),
                         "metadata": {"parent_feedback_used": feedback_used, "parent_id": parent}})
    passed = all(control["passed"] for control in controls)
    proposal = plan_next_experiment({"decision": "Choose next candidates using declared predictions and parent assay feedback",
        "objectives": [{"name": "assay_utility", "direction": direction}], "candidates": proposed,
        "constraints": contract.get("constraints"), "uncertainty_weight": 0}) if passed and proposed else None
    return {"schema": "campaign-feedback-result-v1", "assay": assay, "rows": rows,
            "prediction_contract": prediction_contract,
            "summaries": summaries, "heldout_mae": mae, "heldout_candidates": heldout,
            "controls_passed": passed, "next_batch": proposal,
            "unobserved_candidate_ids": sorted(set(candidates) - {row["candidate_id"] for row in rows}),
            "evidence_boundary": "Supplied assay outcomes and parent-feedback heuristic only; no surrogate training, Bayesian acquisition, assay execution or efficacy claim."}
