"""Build the register-derived portion of an evidence graph."""
from __future__ import annotations

import hashlib
import json
from difflib import get_close_matches
from pathlib import Path
from typing import Any

from codex_science.cli_io import write_json_atomic
from codex_science.evidence import NODE_TYPES, RELATIONS, _support_source_path, _validate_claim_register, _validate_evidence_graph, _validate_study_table
from codex_science.screening_pool import _relative_path, _safe_file
from codex_science.study_table import _input_file


def _read_json(path: Path) -> tuple[dict[str, Any], str]:
    data = path.read_bytes()
    payload = json.loads(data)
    if not isinstance(payload, dict):
        raise ValueError(f"input JSON must be an object: {path.name}")
    return payload, hashlib.sha256(data).hexdigest()


def _suggest(value: Any, allowed: set[str]) -> str:
    if isinstance(value, str):
        normalized = value.replace("-", "_")
        for candidate in sorted(allowed):
            if normalized == candidate or normalized.rstrip("s") == candidate.rstrip("s"):
                return f"; did you mean {candidate}?"
        matches = get_close_matches(normalized, sorted(allowed), n=1, cutoff=0.6)
        if matches:
            return f"; did you mean {matches[0]}?"
    return ""


def build_evidence_graph(
    run_dir: str | Path, claims: str | Path = "claims.json", studies: str | Path = "studies.json",
    extra: str | Path | None = None, output: str | Path = "evidence_graph.json",
) -> dict[str, Any]:
    """Derive claim/study/cohort nodes and evidence edges; preserve extra relations."""
    root_arg = Path(run_dir).absolute()
    if root_arg.is_symlink() or not root_arg.is_dir():
        raise ValueError("run directory must be an existing, non-symlink directory")
    root = root_arg.resolve()
    claim_path = _input_file(root, claims, "claims file")
    study_path = _input_file(root, studies, "studies file")
    extra_path = _input_file(root, extra, "extra file") if extra is not None else None
    inputs = [claim_path, study_path] + ([extra_path] if extra_path else [])
    output_arg = Path(output)
    if output_arg.is_absolute():
        try:
            output_arg = output_arg.absolute().relative_to(root)
        except ValueError as error:
            raise ValueError("output file must be inside the run directory") from error
    output_rel = _relative_path(output_arg.as_posix(), "output file")
    output_path = _safe_file(root, output_rel, required=False) or root.joinpath(*output_rel.parts)

    problems: list[str] = []
    payloads: list[dict[str, Any]] = []
    hashes: list[str] = []
    for label, path in (("claims", claim_path), ("studies", study_path)) + ((("extra", extra_path),) if extra_path else ()):
        try:
            data, digest = _read_json(path)
            payloads.append(data)
            hashes.append(digest)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
            problems.append(f"{label}: {error}")
            payloads.append({})
            hashes.append("")
    claim_payload, study_payload = payloads[:2]
    extra_payload = payloads[2] if extra_path else None
    try:
        claim_by_id = _validate_claim_register(claim_payload)
    except (ValueError, TypeError) as error:
        problems.append(str(error))
        claim_by_id = {}
    try:
        study_by_id = _validate_study_table(study_payload, root)
    except (ValueError, TypeError) as error:
        problems.append(str(error))
        study_by_id = {}

    excerpt_source_paths = {
        _support_source_path(root, excerpt["source_artifact"], study_id, excerpt.get("claim_id", ""))
        for study_id, study in study_by_id.items()
        for excerpt in study.get("support_excerpts", [])
    }
    protected_paths = {path.resolve() for path in inputs} | {path.resolve() for path in excerpt_source_paths}
    protected_paths.add((root / "manifest.json").resolve())
    if output_path.resolve() in protected_paths:
        raise ValueError("output file must not replace an input file, an excerpt source, or the manifest")

    nodes: list[dict[str, Any]] = [
        {"id": key, "label": value["text"], "type": "claim"} for key, value in claim_by_id.items()
    ]
    nodes.extend({"id": key, "label": value["title"], "type": "study"} for key, value in study_by_id.items())
    edges: list[dict[str, Any]] = []
    cohorts: dict[str, dict[str, Any]] = {}
    known_ids = set(claim_by_id) | set(study_by_id)
    for study_id, study in study_by_id.items():
        cohort = study.get("cohort_id")
        if cohort:
            if cohort in known_ids:
                problems.append(f"cohort_id {cohort} collides with a claim or study id")
            cohorts.setdefault(cohort, {"id": cohort, "label": cohort, "type": "cohort"})
            edges.append({"source": study_id, "target": cohort, "relation": "depends_on"})
        for field, relation in (("supports_claim_ids", "supports"), ("contradicts_claim_ids", "contradicts")):
            for claim_id in study.get(field, []):
                if claim_id not in claim_by_id:
                    problems.append(f"study {study_id} references unknown claim id {claim_id}")
                edge = {"source": study_id, "target": claim_id, "relation": relation}
                if cohort:
                    edge["independence_group"] = cohort
                edges.append(edge)
    nodes.extend(cohorts.values())

    if extra_payload is not None:
        if extra_payload.get("schema") != "evidence-graph-extra-v1":
            problems.append("extra schema must be evidence-graph-extra-v1")
        extra_nodes, extra_edges = extra_payload.get("nodes"), extra_payload.get("edges")
        if not isinstance(extra_nodes, list):
            problems.append("extra nodes must be a list")
            extra_nodes = []
        if not isinstance(extra_edges, list):
            problems.append("extra edges must be a list")
            extra_edges = []
        by_id = {node["id"]: node for node in nodes}
        for i, node in enumerate(extra_nodes):
            if not isinstance(node, dict):
                problems.append(f"extra node {i} must be an object")
                continue
            node_id, node_type = node.get("id"), node.get("type")
            if not isinstance(node_type, str) or node_type not in NODE_TYPES:
                problems.append(f"invalid extra node type {node_type!r}; allowed: {sorted(NODE_TYPES)}{_suggest(node_type, NODE_TYPES)}")
                continue
            if node_type in {"claim", "study"}:
                problems.append(f"extra node {node_id!r} cannot have type {node_type}; registers own claim and study nodes")
                continue
            if not isinstance(node_id, str) or not node_id.strip():
                problems.append(f"extra node {i} id must be non-empty text")
                continue
            if node_id in cohorts and node_type == "cohort":
                cohorts[node_id].update(node)
                continue
            if node_id in by_id:
                problems.append(f"extra node id duplicates existing node: {node_id}")
                continue
            by_id[node_id] = node
            nodes.append(node)
        for i, edge in enumerate(extra_edges):
            if not isinstance(edge, dict):
                problems.append(f"extra edge {i} must be an object")
                continue
            source, target, relation = edge.get("source"), edge.get("target"), edge.get("relation")
            if not isinstance(relation, str) or relation not in RELATIONS:
                problems.append(f"invalid extra relation {relation!r}; allowed: {sorted(RELATIONS)}{_suggest(relation, RELATIONS)}")
                continue
            if not isinstance(source, str) or not isinstance(target, str) or source not in by_id or target not in by_id:
                problems.append(f"extra edge endpoint is missing: {source} -> {target}")
                continue
            if relation in {"supports", "contradicts"} and by_id[source].get("type") == "study" and by_id[target].get("type") == "claim":
                problems.append(f"extra {relation} edge {source} -> {target} must be declared in studies.json")
                continue
            edges.append(edge)

    if problems:
        raise ValueError("; ".join(problems))
    graph = {"schema_version": 1, "nodes": nodes, "edges": edges}
    graph_nodes, _ = _validate_evidence_graph(graph)
    if {key for key, node in graph_nodes.items() if node["type"] == "claim"} != set(claim_by_id):
        raise ValueError("final graph claim node set differs from claim register")
    if {key for key, node in graph_nodes.items() if node["type"] == "study"} != set(study_by_id):
        raise ValueError("final graph study node set differs from study table")
    write_json_atomic(output_path, graph)
    result: dict[str, Any] = {"schema": "evidence-graph-build-v1", "output": output_path.relative_to(root).as_posix(),
        "counts": {"claims": len(claim_by_id), "studies": len(study_by_id), "cohorts": sum(node["type"] == "cohort" for node in nodes), "nodes": len(nodes), "edges": len(edges)},
        "claims_sha256": hashes[0], "studies_sha256": hashes[1]}
    if extra_path:
        result["extra_sha256"] = hashes[2]
    return result
