"""Acceptance-contract validation for structure-based drug-discovery benchmarks."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


SPLIT_POLICIES = {"random", "cold-ligand", "cold-target", "cold-both"}
PARTITIONS = {"train", "validation", "test"}
POCKET_SOURCES = {
    "user-residues",
    "reference-ligand",
    "validated-prediction",
    "heldout-bound-ligand",
}
OVERLAP_STATES = {"none", "possible", "known", "unknown"}
CLAIM_TYPES = {"pose", "ranking", "enrichment", "probability", "affinity", "mechanism"}


def _text(value: Any, label: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{label} is required")
    return text


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    return value


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def validate_benchmark(bundle: dict[str, Any]) -> None:
    if not isinstance(bundle, dict):
        raise ValueError("SBDD benchmark must be an object")
    if bundle.get("schema_version") != 1:
        raise ValueError("Unsupported SBDD benchmark schema version")
    _text(bundle.get("benchmark_id"), "benchmark_id")
    split_policy = _text(bundle.get("split_policy"), "split_policy")
    if split_policy not in SPLIT_POLICIES:
        raise ValueError(f"Unsupported SBDD split policy: {split_policy}")
    if not isinstance(bundle.get("experimental_affinity_validation"), bool):
        raise ValueError("experimental_affinity_validation must be boolean")
    _list(bundle.get("positive_controls"), "positive_controls")
    _list(bundle.get("metrics"), "metrics")
    _list(bundle.get("metric_groups"), "metric_groups")

    record_ids: set[str] = set()
    for index, raw in enumerate(_list(bundle.get("records"), "records")):
        record = _mapping(raw, f"record {index}")
        record_id = _text(record.get("complex_id"), f"record {index} complex_id")
        if record_id in record_ids:
            raise ValueError(f"Duplicate complex_id: {record_id}")
        record_ids.add(record_id)
        partition = _text(record.get("partition"), f"record {record_id} partition")
        if partition not in PARTITIONS:
            raise ValueError(f"Invalid partition for {record_id}: {partition}")
        for field in (
            "target_id",
            "target_family",
            "receptor_state",
            "ligand_id",
            "scaffold_id",
            "analog_series_id",
            "task",
            "role",
        ):
            _text(record.get(field), f"record {record_id} {field}")
        pocket_source = _text(record.get("pocket_source"), f"record {record_id} pocket_source")
        if pocket_source not in POCKET_SOURCES:
            raise ValueError(f"Invalid pocket source for {record_id}: {pocket_source}")
        overlap = _text(
            record.get("model_training_overlap"),
            f"record {record_id} model_training_overlap",
        )
        if overlap not in OVERLAP_STATES:
            raise ValueError(f"Invalid model training overlap for {record_id}: {overlap}")

    claim_ids: set[str] = set()
    for index, raw in enumerate(_list(bundle.get("claims"), "claims")):
        claim = _mapping(raw, f"claim {index}")
        claim_id = _text(claim.get("id"), f"claim {index} id")
        if claim_id in claim_ids:
            raise ValueError(f"Duplicate SBDD claim id: {claim_id}")
        claim_ids.add(claim_id)
        _text(claim.get("text"), f"claim {claim_id} text")
        claim_type = _text(claim.get("type"), f"claim {claim_id} type")
        if claim_type not in CLAIM_TYPES:
            raise ValueError(f"Invalid SBDD claim type for {claim_id}: {claim_type}")
        _list(claim.get("evidence"), f"claim {claim_id} evidence")


def audit_sbdd_benchmark(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Detect leakage, unsupported semantics, and missing acceptance controls."""

    validate_benchmark(bundle)
    findings: list[dict[str, Any]] = []

    def add(
        code: str,
        severity: str,
        message: str,
        record_ids: list[str] | None = None,
        claim_id: str = "",
    ) -> None:
        finding: dict[str, Any] = {
            "code": code,
            "severity": severity,
            "message": message,
        }
        if record_ids:
            finding["record_ids"] = sorted(record_ids)
        if claim_id:
            finding["claim_id"] = claim_id
        findings.append(finding)

    records = bundle["records"]
    by_id = {str(record["complex_id"]): record for record in records}
    controls = [str(item) for item in bundle["positive_controls"]]
    missing_controls = sorted(set(controls) - set(by_id))
    if missing_controls:
        add(
            "missing-positive-control",
            "major",
            f"Positive controls are not present in benchmark records: {', '.join(missing_controls)}",
        )
    if not controls:
        add("missing-positive-control", "major", "No positive control is declared.")

    for record in records:
        record_id = str(record["complex_id"])
        is_test = record["partition"] == "test"
        is_redocking_control = record["task"] == "redocking" and record["role"] == "positive-control"
        self_derived = str(record.get("pocket_derived_from_complex_id", "")).strip() == record_id
        if is_test and not is_redocking_control and (
            record["pocket_source"] == "heldout-bound-ligand" or self_derived
        ):
            add(
                "pocket-leak",
                "critical",
                f"Test pocket for {record_id} uses held-out bound-pose information.",
                [record_id],
            )

        overlap = record["model_training_overlap"]
        if is_test and overlap == "known":
            add(
                "known-training-overlap",
                "critical",
                f"Test record {record_id} is known to overlap model training data.",
                [record_id],
            )
        elif is_test and overlap in {"possible", "unknown"}:
            add(
                "unresolved-training-overlap",
                "minor",
                f"Training-data overlap for test record {record_id} is {overlap}.",
                [record_id],
            )

    split_policy = bundle["split_policy"]
    train = [record for record in records if record["partition"] == "train"]
    test = [record for record in records if record["partition"] == "test"]

    def overlap(field: str) -> dict[str, list[str]]:
        train_values: dict[str, list[str]] = defaultdict(list)
        test_values: dict[str, list[str]] = defaultdict(list)
        for record in train:
            train_values[str(record[field])].append(str(record["complex_id"]))
        for record in test:
            test_values[str(record[field])].append(str(record["complex_id"]))
        return {
            value: train_values[value] + test_values[value]
            for value in sorted(train_values.keys() & test_values.keys())
        }

    if split_policy in {"cold-ligand", "cold-both"}:
        for value, record_ids in overlap("analog_series_id").items():
            add(
                "analog-series-leak",
                "critical",
                f"Analog series {value} appears in both train and test partitions.",
                record_ids,
            )
        for value, record_ids in overlap("scaffold_id").items():
            add(
                "scaffold-leak",
                "critical",
                f"Scaffold {value} appears in both train and test partitions.",
                record_ids,
            )

    if split_policy in {"cold-target", "cold-both"}:
        for value, record_ids in overlap("target_id").items():
            add(
                "target-leak",
                "critical",
                f"Target {value} appears in both train and test partitions.",
                record_ids,
            )
        for value, record_ids in overlap("target_family").items():
            add(
                "target-family-leak",
                "major",
                f"Target family {value} appears in both train and test partitions.",
                record_ids,
            )

    metric_groups = {str(item) for item in bundle["metric_groups"]}
    required_groups = {"target", "scaffold", "receptor_state", "failure_mode"}
    missing_groups = sorted(required_groups - metric_groups)
    if missing_groups:
        add(
            "missing-subgroup-analysis",
            "major",
            f"Benchmark omits required metric groups: {', '.join(missing_groups)}",
        )

    metrics = {str(item) for item in bundle["metrics"]}
    for claim in bundle["claims"]:
        claim_id = str(claim["id"])
        claim_type = str(claim["type"])
        if claim_type in {"affinity", "mechanism"} and not bundle[
            "experimental_affinity_validation"
        ]:
            add(
                "affinity-overclaim" if claim_type == "affinity" else "mechanism-overclaim",
                "critical",
                f"Claim {claim_id} asserts {claim_type} without assay-aware experimental validation.",
                claim_id=claim_id,
            )
        if claim_type == "probability" and not ({"brier_score", "ece"} & metrics):
            add(
                "missing-calibration",
                "major",
                f"Probability claim {claim_id} has no calibration metric.",
                claim_id=claim_id,
            )
        missing_evidence = sorted(set(map(str, claim["evidence"])) - metrics)
        if missing_evidence:
            add(
                "missing-claim-metric",
                "major",
                f"Claim {claim_id} cites unreported metrics: {', '.join(missing_evidence)}",
                claim_id=claim_id,
            )

    findings.sort(
        key=lambda item: (
            item["severity"],
            item["code"],
            item.get("claim_id", ""),
            item.get("record_ids", []),
        )
    )
    return findings


def benchmark_passes(bundle: dict[str, Any]) -> bool:
    return not any(
        finding["severity"] in {"critical", "major"}
        for finding in audit_sbdd_benchmark(bundle)
    )
