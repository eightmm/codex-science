"""Bounded exported-series analysis; no trajectory reader or simulation executor."""

import hashlib
import json
import math
import statistics


def _number(value, name):
    try:
        finite = math.isfinite(value)
    except (TypeError, OverflowError):
        finite = False
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not finite:
        raise ValueError(f"{name} must be a finite number")
    return value


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty text")
    return value


def _se(values):
    return statistics.stdev(values) / math.sqrt(len(values)) if len(values) >= 2 else None


def _analyze_trajectory_comparison(record):
    """Compare two conditions using equal-weight independent replica means.

    Identity and processing metadata are declarations, not coordinate validation.
    Block errors assume adequate block length; diagnostics cannot prove convergence.
    """
    if not isinstance(record, dict) or record.get("schema") != "trajectory-comparison-v1":
        raise ValueError("expected trajectory-comparison-v1")
    contract = record["contract"]
    for key in ("observable", "unit", "time_unit", "topology_id", "atom_selection", "pbc", "model_id"):
        _text(contract[key], key)
    if contract["pbc"] not in ("minimum-image", "unwrapped", "not-applicable"):
        raise ValueError("unresolved PBC treatment")
    size = contract["block_frames"]
    if type(size) is not int or size < 2:
        raise ValueError("block_frames must be an integer >= 2")
    threshold = _number(contract["max_half_drift"], "max_half_drift")
    if threshold < 0:
        raise ValueError("max_half_drift must be nonnegative")
    dt = _number(contract["frame_interval"], "frame_interval")
    if dt <= 0:
        raise ValueError("frame_interval must be positive")
    expected_times = contract["times"]
    if not isinstance(expected_times, list) or len(expected_times) < 2:
        raise ValueError("at least two explicit expected frame times required")
    for i, time in enumerate(expected_times):
        _number(time, "time")
        if i and (time <= expected_times[i-1] or not math.isclose(
                time - expected_times[i-1], dt, rel_tol=1e-8, abs_tol=0.0)):
            raise ValueError("frame times must be regular and strictly increasing")
    conditions = record["conditions"]
    if not isinstance(conditions, list) or len(conditions) != 2 or len(set(conditions)) != 2:
        raise ValueError("exactly two distinct ordered conditions required")
    for condition in conditions:
        _text(condition, "condition")
    controls = record["controls"]
    if not isinstance(controls, list) or not controls:
        raise ValueError("explicit essential controls required")
    control_ids = set()
    for control in controls:
        identity = _text(control["id"], "control id")
        if identity in control_ids:
            raise ValueError("duplicate control id")
        control_ids.add(identity)
        if type(control["passed"]) is not bool:
            raise ValueError("control passed must be boolean")
    replicas = record["replicas"]
    if not isinstance(replicas, list) or not replicas:
        raise ValueError("replicas required")
    seen = {key: set() for key in ("replica_id", "independent_run_id", "source_id")}
    results = []
    reasons = []
    for replica in replicas:
        for key in seen:
            identity = _text(replica[key], key)
            if identity in seen[key]:
                raise ValueError(f"duplicated {key}; segments are not independent replicas")
            seen[key].add(identity)
        if replica["condition"] not in conditions:
            raise ValueError("unknown condition")
        for key in ("observable", "unit", "time_unit", "topology_id", "atom_selection", "pbc", "model_id"):
            if replica[key] != contract[key]:
                raise ValueError(f"mismatched {key}")
        times, values = replica["times"], replica["values"]
        if not isinstance(times, list) or not isinstance(values, list):
            raise ValueError("times and values must be lists")
        for time in times:
            _number(time, "replica time")
        if times != expected_times or len(values) != len(times):
            raise ValueError("missing/mismatched frames or analysis window")
        for value in values:
            _number(value, "observable value")
        if len(values) % size:
            raise ValueError("incomplete block; freeze a divisible window, never silently discard frames")
        blocks = [statistics.mean(values[i:i+size]) for i in range(0, len(values), size)]
        half = len(values) // 2
        drift = statistics.mean(values[half:]) - statistics.mean(values[:half])
        enough = len(blocks) >= 4
        if not enough:
            reasons.append("insufficient-blocks:" + replica["replica_id"])
        if abs(drift) > threshold:
            reasons.append("drift:" + replica["replica_id"])
        coarse = ([statistics.mean(blocks[i:i+2]) for i in range(0, len(blocks), 2)]
                  if len(blocks) % 2 == 0 else [])
        results.append({"replica_id": replica["replica_id"], "condition": replica["condition"],
                        "mean": statistics.mean(values), "frame_count": len(values),
                        "block_means": blocks, "block_se": _se(blocks) if enough else None,
                        "double_block_se": _se(coarse) if len(coarse) >= 4 else None,
                        "half_drift": drift, "drift_passed": abs(drift) <= threshold})
    summaries = {}
    for condition in conditions:
        means = [item["mean"] for item in results if item["condition"] == condition]
        if not means:
            raise ValueError("each condition requires at least one replica")
        summaries[condition] = {"replicas": len(means), "mean": statistics.mean(means), "replica_se": _se(means)}
        if len(means) < 2:
            reasons.append("insufficient-replicas:" + condition)
    reasons.extend("failed-control:" + c["id"] for c in controls if not c["passed"])
    left, right = (summaries[c] for c in conditions)
    se = None
    if not reasons:
        se = math.hypot(left["replica_se"], right["replica_se"])
    digest = hashlib.sha256(json.dumps(record, sort_keys=True, allow_nan=False).encode()).hexdigest()
    return {"schema": "trajectory-comparison-result-v1", "input_sha256": digest,
            "status": "exploratory" if reasons else "qualified-descriptive",
            "reasons": reasons, "unit": contract["unit"], "replicas": results,
            "conditions": summaries, "contrast": {"direction": f"{conditions[1]} - {conditions[0]}",
            "mean_difference": right["mean"] - left["mean"], "replica_se": se},
            "limitations": ["No convergence proof or experimental/affinity inference.",
                            "Block SE assumes blocks exceed correlation time; no automatic independence test.",
                            "Replica independence, topology, units and PBC are declared, not verified from coordinates.",
                            "SE is not a confidence interval; model uncertainty is excluded."]}


def analyze_trajectory_comparison(record):
    """Reject numeric overflow and nonfinite input metadata or derived output."""
    try:
        json.dumps(record, allow_nan=False)
        result = _analyze_trajectory_comparison(record)
        json.dumps(result, allow_nan=False)
        return result
    except OverflowError as error:
        raise ValueError("numeric range exceeds finite analysis capacity") from error
