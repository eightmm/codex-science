"""Deterministic executable SBDD acceptance with numeric metrics and reviewed artifacts."""
from __future__ import annotations

import hashlib
import json
import math
import random
from itertools import groupby
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

from codex_science.artifacts import add_artifact, new_manifest, write_manifest
from codex_science.model_registry_v2 import build_model_receipt_v2, load_registry_v2, registry_sha256, validate_registry_v2
from codex_science.review_receipts import build_review_receipt
from codex_science.sbdd import audit_sbdd_benchmark


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finite_real(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite real number")
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValueError(f"{label} must be a finite real number") from exc
    if not math.isfinite(result):
        raise ValueError(f"{label} must be a finite real number")
    return result


def _coords(value: Any, label: str) -> list[list[float]]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a non-empty coordinate list")
    result: list[list[float]] = []
    for index, row in enumerate(value):
        if not isinstance(row, list) or len(row) != 3:
            raise ValueError(f"{label}[{index}] must contain x,y,z")
        result.append([_finite_real(item, f"{label}[{index}][{axis}]") for axis, item in enumerate(row)])
    return result


def generate_pose(starting: list[list[float]], delta: list[float]) -> list[list[float]]:
    if not isinstance(delta, list) or len(delta) != 3:
        raise ValueError("pose_delta must contain x,y,z")
    translation = [_finite_real(item, f"pose_delta[{axis}]") for axis, item in enumerate(delta)]
    predicted = [[point[axis] + translation[axis] for axis in range(3)] for point in starting]
    return _coords(predicted, "predicted_coords")


def rmsd(reference: list[list[float]], predicted: list[list[float]], permutation: list[int] | None = None) -> float:
    if len(reference) != len(predicted):
        raise ValueError("reference and predicted atom counts differ")
    if not reference:
        raise ValueError("rmsd needs a non-empty coordinate list")
    order = permutation or list(range(len(predicted)))
    if sorted(order) != list(range(len(predicted))):
        raise ValueError("symmetry permutation must contain every atom index exactly once")
    try:
        squared = 0.0
        for ref, index in zip(reference, order):
            pred = predicted[index]
            squared += sum((ref[axis] - pred[axis]) ** 2 for axis in range(3))
        value = math.sqrt(squared / len(reference))
    except OverflowError:
        value = math.inf
    if not math.isfinite(value):
        # Subtract first to retain nearby-coordinate precision; scale overflowing differences separately.
        try:
            differences = [
                ref[axis] - predicted[index][axis]
                for ref, index in zip(reference, order) for axis in range(3)
            ]
            scale = max(abs(item) for item in differences)
            if math.isfinite(scale):
                normalized = [item / scale for item in differences]
            else:
                scale = max(abs(item) for points in (reference, predicted) for point in points for item in point)
                normalized = []
                for ref, index in zip(reference, order):
                    for axis in range(3):
                        difference = ref[axis] - predicted[index][axis]
                        normalized.append(difference / scale if math.isfinite(difference) else ref[axis] / scale - predicted[index][axis] / scale)
            value = scale * math.sqrt(math.fsum(item * item for item in normalized) / len(reference))
        except OverflowError as exc:
            raise ValueError("rmsd must be a finite real number") from exc
    return _finite_real(value, "rmsd")


def symmetry_rmsd(reference: list[list[float]], predicted: list[list[float]], permutations: Iterable[list[int]]) -> float:
    options = [list(range(len(reference))), *[list(item) for item in permutations]]
    return min(rmsd(reference, predicted, option) for option in options)


def interaction_recovery(reference: Iterable[str], predicted: Iterable[str]) -> float:
    reference_set, predicted_set = set(map(str, reference)), set(map(str, predicted))
    value = 1.0 if not reference_set else len(reference_set & predicted_set) / len(reference_set)
    return _finite_real(value, "interaction_recovery")


def average_precision(labels: list[bool], scores: list[float]) -> float:
    if len(labels) != len(scores) or not labels:
        raise ValueError("labels and scores must be non-empty and aligned")
    for index, score in enumerate(scores):
        _finite_real(score, f"average_precision scores[{index}]")
    positives = sum(labels)
    if positives == 0:
        return 0.0
    ranked = sorted(zip(scores, labels), key=lambda item: -item[0])
    true_positives = 0
    precision_sum = 0.0
    rank = 0
    for _score, items in groupby(ranked, key=lambda item: item[0]):
        group = list(items)
        group_positives = sum(label for _score, label in group)
        rank += len(group)
        true_positives += group_positives
        if group_positives:
            # All tied predictions enter at one threshold, regardless of label order.
            precision_sum += group_positives * (true_positives / rank)
    return _finite_real(precision_sum / positives, "average_precision")


def _mean(values: list[float], label: str) -> float:
    try:
        value = sum(values) / len(values)
    except OverflowError:
        value = math.inf
    if not math.isfinite(value):
        value = mean(values)
    return _finite_real(value, label)


def bootstrap_mean(values: list[float], *, seed: int = 0, replicates: int = 1000) -> tuple[float, float]:
    if not values:
        raise ValueError("cannot bootstrap an empty metric")
    for value in values:
        _finite_real(value, "bootstrap metric")
    randomizer = random.Random(seed)
    means = []
    for _ in range(replicates):
        sample = [values[randomizer.randrange(len(values))] for _ in values]
        means.append(_mean(sample, "bootstrap mean"))
    means.sort()
    lower = means[int(0.025 * (replicates - 1))]
    upper = means[int(0.975 * (replicates - 1))]
    return lower, upper


def _metric(name: str, value: float, unit: str, operator: str, threshold: float, n: int, interval: tuple[float, float] | None = None) -> dict[str, Any]:
    value = _finite_real(value, name)
    if interval is not None:
        interval = tuple(_finite_real(bound, f"{name} confidence_interval") for bound in interval)
    if operator == "<=":
        passed = value <= threshold
    elif operator == ">=":
        passed = value >= threshold
    else:
        raise ValueError(f"unsupported metric operator: {operator}")
    return {
        "name": name,
        "value": value,
        "unit": unit,
        "n": n,
        "threshold": {"operator": operator, "value": threshold},
        "confidence_interval": None if interval is None else list(interval),
        "passed": passed,
    }


def compute_acceptance(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    leakage_findings = audit_sbdd_benchmark(payload)
    blocking = [item for item in leakage_findings if item["severity"] in {"critical", "major"}]
    if blocking:
        raise ValueError("SBDD contract has blocking leakage findings: " + ", ".join(item["code"] for item in blocking))
    thresholds = payload.get("numeric_thresholds", {})
    if not isinstance(thresholds, dict):
        raise ValueError("numeric_thresholds must be an object")
    thresholds = {name: _finite_real(value, f"numeric_thresholds.{name}") for name, value in thresholds.items()}
    poses: list[dict[str, Any]] = []
    control_rmsds: list[float] = []
    interaction_values: list[float] = []
    labels: list[bool] = []
    scores: list[float] = []
    for record in payload["records"]:
        reference = _coords(record["reference_coords"], f"{record['complex_id']} reference_coords")
        starting = _coords(record["starting_coords"], f"{record['complex_id']} starting_coords")
        try:
            predicted = generate_pose(starting, record.get("pose_delta", [0, 0, 0]))
            pose_rmsd = _finite_real(symmetry_rmsd(reference, predicted, record.get("symmetry_permutations", [])), "symmetry_rmsd_angstrom")
            recovery = _finite_real(interaction_recovery(record.get("reference_interactions", []), record.get("predicted_interactions", [])), "interaction_recovery")
        except ValueError as exc:
            raise ValueError(f"{record['complex_id']} {exc}") from exc
        score = _finite_real(record.get("score", 0.0), f"{record['complex_id']} score")
        active = record.get("active", False)
        if not isinstance(active, bool):
            raise ValueError(f"{record['complex_id']} active must be a JSON boolean")
        poses.append({
            "complex_id": record["complex_id"],
            "predicted_coords": predicted,
            "symmetry_rmsd_angstrom": pose_rmsd,
            "interaction_recovery": recovery,
            "score": score,
            "active": active,
            "role": record["role"],
            "task": record["task"],
        })
        if record["role"] == "positive-control" and record["task"] == "redocking":
            control_rmsds.append(pose_rmsd)
            interaction_values.append(recovery)
        if record["task"] == "screening":
            labels.append(active)
            scores.append(score)
    if not control_rmsds or not labels:
        raise ValueError("acceptance input needs redocking controls and screening records")
    rmsd_mean = _mean(control_rmsds, "top1_symmetry_rmsd mean")
    recovery_mean = _mean(interaction_values, "interaction_recovery mean")
    pr_auc = average_precision(labels, scores)
    metrics = [
        _metric("top1_symmetry_rmsd", rmsd_mean, "angstrom", "<=", thresholds.get("top1_symmetry_rmsd", 2.0), len(control_rmsds), bootstrap_mean(control_rmsds)),
        _metric("interaction_recovery", recovery_mean, "fraction", ">=", thresholds.get("interaction_recovery", 0.5), len(interaction_values), bootstrap_mean(interaction_values)),
        _metric("pr_auc", pr_auc, "fraction", ">=", thresholds.get("pr_auc", 0.75), len(labels), None),
    ]
    return poses, metrics, leakage_findings


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def execute_acceptance(input_path: Path, output_dir: Path, *, registry_path: Path) -> Path:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    poses, metrics, leakage_findings = compute_acceptance(payload)
    output_dir.mkdir(parents=True, exist_ok=True)
    poses_path, metrics_path = output_dir / "poses.json", output_dir / "metrics.json"
    _write_json(poses_path, {"schema_version": 1, "poses": poses})
    _write_json(metrics_path, {"schema_version": 1, "metrics": metrics, "all_passed": all(item["passed"] for item in metrics), "leakage_findings": leakage_findings})
    all_passed = all(item["passed"] for item in metrics)
    claim_status = "supported" if all_passed else "unsupported"
    claims = {
        "schema_version": 1,
        "claims": [{
            "id": "claim-sbdd-acceptance",
            "text": "The deterministic workflow supports pose-generation and exploratory ranking only within this checked acceptance fixture.",
            "permitted_inference": "Reproducibility and metric-contract acceptance for the local deterministic baseline; not experimental affinity or mechanism.",
            "status": claim_status,
            "required_support": 1,
            "required_evidence": ["computed"],
            "dependencies": ["execution-sbdd-baseline"],
            "falsifier": "Any required numeric metric fails its preregistered threshold or a blocking leakage finding is present.",
            "uncertainty": "The fixture is small and deterministic and does not establish prospective docking performance.",
            "next_action": "Run the same contract with a pinned external docking implementation and experimental controls before making target-specific claims."
        }]
    }
    claims_path = output_dir / "claims.json"
    _write_json(claims_path, claims)
    graph_v1 = {
        "schema_version": 1,
        "nodes": [{"id": "execution-sbdd-baseline", "type": "execution"}, {"id": "claim-sbdd-acceptance", "type": "claim"}],
        "edges": [{"source": "execution-sbdd-baseline", "target": "claim-sbdd-acceptance", "relation": "supports"}] if all_passed else [{"source": "execution-sbdd-baseline", "target": "claim-sbdd-acceptance", "relation": "contradicts"}],
    }
    graph_v2 = {"schema_version": 2, "nodes": graph_v1["nodes"], "edges": graph_v1["edges"]}
    graph_v1_path, graph_v2_path = output_dir / "evidence_graph.json", output_dir / "evidence_graph_v2.json"
    _write_json(graph_v1_path, graph_v1)
    _write_json(graph_v2_path, graph_v2)
    registry = load_registry_v2(registry_path)
    models = validate_registry_v2(registry)
    model = models["deterministic-translation-baseline"]
    config_hash = canonical_sha256({"thresholds": payload.get("numeric_thresholds", {}), "algorithm": "deterministic-translation-baseline-v1"})
    model_receipt = build_model_receipt_v2(
        model,
        registry_sha256_value=registry_sha256(registry),
        code_revision="deterministic-translation-baseline-v1",
        weight_revision="not-applicable",
        database_revisions={},
        configuration_sha256=config_hash,
        input_sha256=file_sha256(input_path),
    )
    model_path = output_dir / "model_receipt.json"
    _write_json(model_path, model_receipt)
    report_path = output_dir / "report.md"
    report_path.write_text(
        "# Deterministic SBDD acceptance\n\n"
        + "\n".join(f"- {item['name']}: {item['value']:.6g} {item['unit']} — {'PASS' if item['passed'] else 'FAIL'} ({item['threshold']['operator']} {item['threshold']['value']})" for item in metrics)
        + "\n\nThis is a reproducibility and contract fixture. It is not evidence of experimental binding affinity, efficacy, or mechanism.\n",
        encoding="utf-8",
    )
    covered = [{"path": path.name, "sha256": file_sha256(path)} for path in (poses_path, metrics_path, claims_path, graph_v1_path, graph_v2_path, model_path, report_path)]
    review_findings = [
        {
            "code": "acceptance-metric-failed",
            "severity": "major",
            "message": f"Acceptance metric {item['name']} failed its preregistered threshold.",
            "resolution_status": "open",
        }
        for item in metrics
        if not item["passed"]
    ]
    review_receipt = build_review_receipt(
        review_id="review-sbdd-acceptance", reviewer="deterministic-contract-checker", independent=False,
        review_modes=["record", "method"], status="passed" if all_passed else "findings",
        covered_artifacts=covered, covered_claim_ids=["claim-sbdd-acceptance"], findings=review_findings,
        covered_registry_sha256=registry_sha256(registry),
        limitations=["This deterministic check is not an independent scientific review.", "The fixture does not validate experimental affinity."],
    )
    review_path = output_dir / "review_receipt.json"
    _write_json(review_path, review_receipt)
    manifest = new_manifest(str(payload.get("run_id", "sbdd-executable-acceptance")), "Does the deterministic SBDD baseline satisfy prespecified pose and ranking acceptance thresholds?", [
        {"id": "validate-input", "description": "Validate input states and leakage contract", "status": "completed"},
        {"id": "generate-poses", "description": "Generate deterministic poses", "status": "completed"},
        {"id": "compute-metrics", "description": "Compute RMSD, interaction recovery, and PR-AUC", "status": "completed"},
        {"id": "review", "description": "Review hashes, thresholds, inference boundary, and reproducibility", "status": "completed"},
    ])
    manifest["inputs"] = [{"path": str(input_path), "sha256": file_sha256(input_path)}]
    manifest["code"] = [{"module": "codex_science.sbdd_execution", "revision": "deterministic-translation-baseline-v1"}]
    manifest["executions"] = [{
        "id": "execution-sbdd-baseline",
        "command": f"python scripts/run_sbdd_acceptance.py {input_path} {output_dir}",
        "exit_code": 0,
        "outputs": [
            "poses.json", "metrics.json", "claims.json", "evidence_graph.json",
            "evidence_graph_v2.json", "model_receipt.json", "report.md", "review_receipt.json",
        ],
    }]
    manifest["environment"] = {"python": ">=3.11", "random_seed": 0, "model_registry_sha256": registry_sha256(registry)}
    manifest["claims"] = [{"id": "claim-sbdd-acceptance", "text": claims["claims"][0]["text"], "evidence": ["metrics.json", "poses.json", "report.md"]}]
    manifest["review"] = {"status": "passed" if all_passed else "findings", "findings": review_findings}
    for path, kind in (
        (poses_path, "pose-table"), (metrics_path, "metrics"), (claims_path, "claim-register"),
        (graph_v1_path, "evidence-graph"), (graph_v2_path, "evidence-graph-v2"),
        (model_path, "model-receipt-v2"), (report_path, "report"), (review_path, "review-receipt"),
    ):
        add_artifact(manifest, path.name, kind=kind, sha256=file_sha256(path))
    manifest_path = output_dir / "manifest.json"
    write_manifest(manifest, manifest_path)
    return manifest_path
