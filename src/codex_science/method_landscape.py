"""Deterministic, provenance-preserving allocation of literature methods."""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from typing import Any, Mapping


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def allocate_methods(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a method-landscape-v1 input and allocate its paper budget."""
    if not isinstance(payload, Mapping) or payload.get("schema") != "method-landscape-v1":
        raise ValueError("schema must be method-landscape-v1")
    budget = payload.get("budget")
    if type(budget) is not int or budget <= 0:
        raise ValueError("budget must be a positive int")
    topics, papers = payload.get("topics"), payload.get("papers")
    if not isinstance(topics, list) or not isinstance(papers, list):
        raise ValueError("topics and papers must be lists")
    topic_order: dict[str, int] = {}
    covered: dict[str, bool] = {}
    for i, topic in enumerate(topics):
        if not isinstance(topic, Mapping) or not isinstance(topic.get("id"), str):
            raise ValueError("each topic must have a string id")
        identifier = topic["id"]
        if identifier in topic_order:
            raise ValueError(f"duplicate topic id: {identifier}")
        if type(topic.get("covered_by_baseline")) is not bool:
            raise ValueError(f"topic {identifier} covered_by_baseline must be bool")
        topic_order[identifier] = i
        covered[identifier] = topic["covered_by_baseline"]

    paper_ids: set[str] = set()
    clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
    screened_out: list[dict[str, str]] = []
    for paper in papers:
        if not isinstance(paper, Mapping) or not isinstance(paper.get("paper_id"), str):
            raise ValueError("each paper must have a string paper_id")
        paper_id = paper["paper_id"]
        if paper_id in paper_ids:
            raise ValueError(f"duplicate paper id: {paper_id}")
        paper_ids.add(paper_id)
        refs = paper.get("topics")
        if not isinstance(refs, list) or not refs:
            raise ValueError(f"paper {paper_id} topics must be a nonempty list")
        for ref in refs:
            if not isinstance(ref, str):
                raise ValueError(f"paper {paper_id} topic references must be strings")
            if ref not in topic_order:
                raise ValueError(f"paper {paper_id} references unknown topic: {ref}")
        excerpt = paper.get("excerpt")
        if not isinstance(excerpt, str) or not 20 <= len(excerpt) <= 2000:
            raise ValueError(f"paper {paper_id} excerpt length must be 20..2000 characters")
        digest = paper.get("source_sha256")
        if digest is not None and (not isinstance(digest, str) or re.fullmatch(r"[0-9a-fA-F]{64}", digest) is None):
            raise ValueError(f"paper {paper_id} source_sha256 must be 64-hex")
        primary = next((ref for ref in refs if not covered[ref]), None)
        if primary is None:
            screened_out.append({"paper_id": paper_id, "reason": "all-topics-covered-by-baseline"})
        else:
            clusters[primary].append(dict(paper))

    ordered_topics = sorted(clusters, key=lambda item: (-len(clusters[item]), topic_order[item]))
    selected: list[dict[str, Any]] = []
    not_selected: list[dict[str, str]] = []
    positions = {topic: 0 for topic in ordered_topics}
    round_number = 1
    while len(selected) < budget:
        progressed = False
        for topic_id in ordered_topics:
            position = positions[topic_id]
            cluster = clusters[topic_id]
            if position >= len(cluster):
                continue
            progressed = True
            paper = cluster[position]
            entry = {"paper_id": paper["paper_id"], "topic_id": topic_id,
                     "round": round_number, "order": len(selected) + 1, "excerpt": paper["excerpt"]}
            if paper.get("source_sha256") is not None:
                entry["source_sha256"] = paper["source_sha256"]
            selected.append(entry)
            positions[topic_id] += 1
            if len(selected) == budget:
                break
        if not progressed:
            break
        round_number += 1
    for topic_id in ordered_topics:
        for paper in clusters[topic_id][positions[topic_id]:]:
            not_selected.append({"paper_id": paper["paper_id"], "topic_id": topic_id,
                                 "reason": "budget-exhausted"})
    selected_topics = {item["topic_id"] for item in selected}
    return {
        "schema": "method-allocation-v1",
        "input_sha256": _canonical_sha256(payload),
        "budget": budget,
        "selected": selected,
        "not_selected": not_selected,
        "screened_out": screened_out,
        "clusters": [{"topic_id": topic_id, "size": len(clusters[topic_id]),
                      "selected_count": positions[topic_id]} for topic_id in ordered_topics],
        "covered_topics": [item["id"] for item in topics if item["covered_by_baseline"]],
        "distinct_topics_selected": len(selected_topics),
    }
