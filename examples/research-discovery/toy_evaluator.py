#!/usr/bin/env python3
"""Deterministic toy evaluation for representation loss versus model capacity.

The protected evaluator owns the paired signed dataset, split, fit, and metric.
Candidate source is trusted local code evaluated through that procedure; this is
not a sandbox or a secrecy boundary for holdout data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any, Sequence


TRAIN_MAGNITUDES = (1, 2, 3, 4)
TEST_MAGNITUDES = (5, 6)


def _samples(split: str, magnitudes: Sequence[int]) -> list[dict[str, Any]]:
    return [
        {"id": f"{split}:{sign * magnitude:+d}", "x": sign * magnitude, "y": sign}
        for magnitude in magnitudes
        for sign in (-1, 1)
    ]


TRAIN = _samples("train", TRAIN_MAGNITUDES)
TEST = _samples("test", TEST_MAGNITUDES)


def render_candidate(mode: str) -> str:
    """Return a small, editable candidate predictor source for *mode*."""
    representations = {
        "baseline": "return (abs(x),)",
        # Extra nonlinear features are capacity, but all discard x's direction.
        "capacity": "return tuple(abs(x) ** power for power in range(1, 5))",
        "directional": "return (x,)",
    }
    try:
        expression = representations[mode]
    except KeyError as exc:
        raise ValueError(f"unknown mode {mode!r}; choose baseline, capacity, or directional") from exc
    return (
        '"""Candidate representation for the protected discovery toy."""\n\n'
        "def represent(x):\n"
        f"    {expression}\n"
    )


def write_candidate(path: str | Path, mode: str) -> Path:
    """Write a rendered candidate source, returning its exact path."""
    candidate_path = Path(path)
    candidate_path.write_text(render_candidate(mode), encoding="utf-8")
    return candidate_path


def _load_candidate(path: Path, source: bytes) -> ModuleType:
    """Execute trusted source directly so a same-path edit cannot reuse a pyc file."""
    module = ModuleType("rdl_toy_candidate")
    module.__file__ = str(path)
    exec(compile(source, str(path), "exec"), module.__dict__)
    if not callable(getattr(module, "represent", None)):
        raise TypeError("candidate must define represent(x)")
    return module


def _feature_vector(candidate: ModuleType, x: int) -> tuple[float, ...]:
    raw = candidate.represent(x)
    if not isinstance(raw, (tuple, list)) or not raw:
        raise TypeError("represent(x) must return a non-empty tuple or list")
    if any(isinstance(value, bool) for value in raw):
        raise TypeError("represent(x) must not use boolean features")
    values = tuple(float(value) for value in raw)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("represent(x) must return finite numeric values")
    return values


def _solve_ridge(features: list[tuple[float, ...]], labels: list[int]) -> list[float]:
    """Fit deterministic least squares with a tiny fixed ridge for singular designs."""
    width = len(features[0])
    if any(len(row) != width for row in features):
        raise ValueError("represent(x) returned inconsistent feature widths")
    matrix = [
        [math.fsum(row[left] * row[right] for row in features) for right in range(width)]
        for left in range(width)
    ]
    target = [math.fsum(row[column] * label for row, label in zip(features, labels)) for column in range(width)]
    for index in range(width):
        matrix[index][index] += 1e-12

    # Gauss-Jordan elimination is adequate for this deliberately tiny finite toy.
    for pivot_index in range(width):
        pivot = max(range(pivot_index, width), key=lambda row: abs(matrix[row][pivot_index]))
        if abs(matrix[pivot][pivot_index]) < 1e-15:
            raise ValueError("candidate design is numerically singular")
        matrix[pivot_index], matrix[pivot] = matrix[pivot], matrix[pivot_index]
        target[pivot_index], target[pivot] = target[pivot], target[pivot_index]
        divisor = matrix[pivot_index][pivot_index]
        matrix[pivot_index] = [value / divisor for value in matrix[pivot_index]]
        target[pivot_index] /= divisor
        for row_index in range(width):
            if row_index == pivot_index:
                continue
            factor = matrix[row_index][pivot_index]
            matrix[row_index] = [
                value - factor * pivot_value
                for value, pivot_value in zip(matrix[row_index], matrix[pivot_index])
            ]
            target[row_index] -= factor * target[pivot_index]
    return target


def _pair_controls(candidate: ModuleType) -> dict[str, Any]:
    pairs = []
    for magnitude in TEST_MAGNITUDES:
        negative = _feature_vector(candidate, -magnitude)
        positive = _feature_vector(candidate, magnitude)
        pairs.append(
            {
                "magnitude": magnitude,
                "negative_representation": list(negative),
                "positive_representation": list(positive),
                "identical_representation": negative == positive,
                "opposite_labels": True,
            }
        )
    identical = all(pair["identical_representation"] for pair in pairs)
    return {
        "held_out_paired_controls": pairs,
        "all_held_out_opposite_label_pairs_identical": identical,
        # With identical features for each balanced opposite-label pair, no
        # deterministic predictor of those features can exceed this accuracy.
        "information_bound_accuracy": 0.5 if identical else None,
    }


def _evaluate_path(path: Path, mode: str | None = None) -> dict[str, Any]:
    source_hash: str | None = None
    try:
        source = path.read_bytes()
        source_hash = hashlib.sha256(source).hexdigest()
        candidate = _load_candidate(path, source)
        train_features = [_feature_vector(candidate, sample["x"]) for sample in TRAIN]
        weights = _solve_ridge(train_features, [sample["y"] for sample in TRAIN])
        controls = _pair_controls(candidate)
        predictions = []
        for sample in TEST:
            representation = _feature_vector(candidate, sample["x"])
            if len(representation) != len(weights):
                raise ValueError("represent(x) returned a different feature width at inference")
            score = math.fsum(weight * value for weight, value in zip(weights, representation))
            predicted_label = 1 if score >= 0.0 else -1
            predictions.append(
                {
                    **sample,
                    "representation": list(representation),
                    "score": score,
                    "predicted_label": predicted_label,
                    "correct": predicted_label == sample["y"],
                }
            )
    except Exception as exc:  # Candidate defects are implementation failures, not evidence.
        return {
            "status": "implementation_failure",
            "science_conclusion": "not_assessed",
            "mode": mode,
            "candidate_path": str(path),
            "candidate_sha256": source_hash,
            "failure": {"type": type(exc).__name__, "message": str(exc)},
            "primary_accuracy": None,
            "predictions": [],
            "train_ids": [sample["id"] for sample in TRAIN],
            "test_ids": [sample["id"] for sample in TEST],
        }
    accuracy = math.fsum(item["correct"] for item in predictions) / len(predictions)
    return {
        "status": "completed",
        "science_conclusion": "evaluation_completed",
        "mode": mode,
        "candidate_path": str(path),
        "candidate_sha256": source_hash,
        "train_ids": [sample["id"] for sample in TRAIN],
        "test_ids": [sample["id"] for sample in TEST],
        "fit": {"method": "ridge_least_squares", "ridge": 1e-12, "weights": weights},
        "primary_metric": {"name": "held_out_accuracy", "value": accuracy},
        "primary_accuracy": accuracy,
        "predictions": predictions,
        "controls": controls,
    }


def evaluate_candidate(path: str | Path, *, mode: str | None = None) -> dict[str, Any]:
    """Evaluate a trusted, local candidate source against the frozen toy contract."""
    return _evaluate_path(Path(path), mode)


def evaluate(mode: str, *, broken: bool = False) -> dict[str, Any]:
    """Render and evaluate one candidate; ``broken`` exercises failure handling."""
    with tempfile.TemporaryDirectory(prefix="rdl-toy-") as temporary_directory:
        path = Path(temporary_directory) / "candidate.py"
        if broken:
            path.write_text("def represent(x):\n    return (float('nan'),)\n", encoding="utf-8")
        else:
            write_candidate(path, mode)
        receipt = _evaluate_path(path, mode)
        if receipt["status"] != "completed":
            return receipt
        baseline_path = Path(temporary_directory) / "baseline.py"
        write_candidate(baseline_path, "baseline")
        baseline = _evaluate_path(baseline_path, "baseline")
        receipt["baseline_accuracy"] = baseline["primary_accuracy"]
        receipt["effect_vs_baseline_accuracy"] = receipt["primary_accuracy"] - baseline["primary_accuracy"]
        return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("baseline", "capacity", "directional"), default="baseline")
    parser.add_argument("--candidate", type=Path, help="trusted local candidate source to evaluate")
    parser.add_argument("--broken", action="store_true", help="inject a malformed candidate outcome")
    parser.add_argument("--output", type=Path, help="write JSON receipt to this path instead of stdout")
    args = parser.parse_args()
    receipt = (
        evaluate_candidate(args.candidate, mode="external")
        if args.candidate is not None
        else evaluate(args.mode, broken=args.broken)
    )
    serialized = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(serialized, end="")
    else:
        args.output.write_text(serialized, encoding="utf-8")
    return 0 if receipt["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
