"""Validate and score weighted hierarchical rubric trees."""
from __future__ import annotations

import json
import math
import stat
from pathlib import Path
from typing import Any

EVIDENCE_BOUNDARY = (
    "A rubric score records supplied criterion results and review receipts; it does not "
    "establish scientific validity, reproducibility, or correctness of the underlying work."
)
MAX_DEPTH = 8
MAX_NODES = 500
MAX_RECEIPT_BYTES = 1_000_000


def validate_tree(tree: Any) -> dict[str, Any]:
    if not isinstance(tree, dict) or tree.get("schema") != "rubric-tree-v1":
        raise ValueError("rubric must use schema rubric-tree-v1")
    if not isinstance(tree.get("id"), str) or not tree["id"]:
        raise ValueError("rubric id must be a non-empty string")
    seen: set[str] = set()
    count = 0
    active: set[int] = set()

    def visit(node: Any, depth: int) -> None:
        nonlocal count
        if depth > MAX_DEPTH:
            raise ValueError(f"maximum rubric depth is {MAX_DEPTH}")
        if not isinstance(node, dict):
            raise ValueError("each node must be an object")
        ident = node.get("id")
        if not isinstance(ident, str) or not ident:
            raise ValueError("node id must be a non-empty string")
        if ident in seen:
            raise ValueError(f"duplicate node id: {ident}")
        seen.add(ident)
        count += 1
        if count > MAX_NODES:
            raise ValueError(f"maximum rubric nodes is {MAX_NODES}")
        title = node.get("title")
        if not isinstance(title, str):
            raise ValueError(f"node {ident} title must be a string")
        weight = node.get("weight")
        try:
            finite_weight = math.isfinite(weight)
        except (OverflowError, TypeError, ValueError):
            finite_weight = False
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not finite_weight or weight <= 0:
            raise ValueError(f"node {ident} weight must be a positive finite number")
        marker = id(node)
        if marker in active:
            raise ValueError("rubric contains a cycle")
        active.add(marker)
        children = node.get("children")
        if children is not None:
            if not isinstance(children, list) or not children:
                raise ValueError(f"node {ident} children must be a non-empty list")
            if "check" in node:
                raise ValueError(f"node {ident} cannot have both children and check")
            for child in children:
                visit(child, depth + 1)
        else:
            check = node.get("check")
            if not isinstance(check, dict) or check.get("kind") not in {"criterion", "review", "manual"}:
                raise ValueError(f"leaf {ident} has invalid check")
            kind = check["kind"]
            required = {"criterion": "criterion_id", "review": "verdict_path"}.get(kind)
            if required and (not isinstance(check.get(required), str) or not check[required]):
                raise ValueError(f"leaf {ident} requires {required}")
        active.remove(marker)

    visit(tree.get("root"), 1)
    return tree


def _review_passed(run_dir: Path | None, verdict_path: str) -> bool | None:
    if run_dir is None:
        return None
    try:
        root = run_dir.resolve(strict=False)
        resolved = (root / verdict_path).resolve(strict=False)
    except (OSError, RuntimeError) as error:
        raise ValueError(f"cannot resolve review receipt path: {error}") from error
    if not resolved.is_relative_to(root):
        raise ValueError("review receipt escapes run directory")
    try:
        info = resolved.stat()
    except (FileNotFoundError, NotADirectoryError):
        return None
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("review receipt must be a regular file")
    if info.st_size > MAX_RECEIPT_BYTES:
        raise ValueError("review receipt exceeds size limit")
    with resolved.open("rb") as stream:
        data = stream.read(MAX_RECEIPT_BYTES + 1)
    if len(data) > MAX_RECEIPT_BYTES:
        raise ValueError("review receipt exceeds size limit")
    try:
        receipt = json.loads(data)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid review receipt: {error}") from error
    return isinstance(receipt, dict) and receipt.get("verdict") == "passed"


def grade(tree: dict[str, Any], criterion_results: dict[str, bool], run_dir: Path | None = None) -> dict[str, Any]:
    validate_tree(tree)
    if not isinstance(criterion_results, dict) or any(not isinstance(k, str) or not isinstance(v, bool) for k, v in criterion_results.items()):
        raise ValueError("criterion results must map strings to booleans")
    ungraded: list[str] = []
    missing: set[str] = set()
    missing_reviews: list[dict[str, str]] = []
    scores: dict[str, float | None] = {}

    def score(node: dict[str, Any]) -> float | None:
        children = node.get("children")
        if children is not None:
            scored = [(child["weight"], score(child)) for child in children]
            scored = [(weight, value) for weight, value in scored if value is not None]
            if scored:
                weight_sum = sum(weight for weight, _ in scored)
                try:
                    finite_weight_sum = math.isfinite(weight_sum)
                except (OverflowError, TypeError, ValueError):
                    finite_weight_sum = False
                if not finite_weight_sum:
                    raise ValueError(f"node {node['id']} child weight sum must be finite")
                value = sum(weight * child_score for weight, child_score in scored) / weight_sum
            else:
                value = None
        else:
            check = node["check"]
            if check["kind"] == "manual":
                ungraded.append(node["id"])
                value = None
            elif check["kind"] == "criterion":
                criterion = check["criterion_id"]
                if criterion not in criterion_results:
                    missing.add(criterion)
                    value = 0.0
                else:
                    value = float(criterion_results[criterion])
            else:
                passed = _review_passed(run_dir, check["verdict_path"])
                if passed is None:
                    missing_reviews.append({"node_id": node["id"], "path": check["verdict_path"]})
                    value = 0.0
                else:
                    value = float(passed)
        scores[node["id"]] = value
        return value

    root_score = score(tree["root"])
    return {"schema": "rubric-score-v1", "score": root_score, "per_node_scores": scores,
            "ungraded_ids": sorted(ungraded), "missing_criterion_ids": sorted(missing),
            "missing_review_paths": sorted(missing_reviews, key=lambda entry: (entry["node_id"], entry["path"])),
            "evidence_boundary": EVIDENCE_BOUNDARY}
