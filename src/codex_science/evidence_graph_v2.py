"""Typed evidence graph validation, dependency components, and impact propagation."""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Iterable

RELATION_TYPES: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "supports": (frozenset({"study", "dataset", "artifact", "execution", "model"}), frozenset({"claim"})),
    "contradicts": (frozenset({"study", "dataset", "artifact", "execution", "model"}), frozenset({"claim"})),
    "depends_on": (frozenset({"claim", "study", "dataset", "artifact", "execution", "model"}), frozenset({"claim", "study", "dataset", "artifact", "execution", "model"})),
    "duplicates": (frozenset({"study", "dataset", "artifact", "portal"}), frozenset({"study", "dataset", "artifact", "portal"})),
    "derived_from": (frozenset({"claim", "study", "dataset", "artifact", "execution", "portal"}), frozenset({"study", "dataset", "artifact", "execution", "portal", "query"})),
    "shares_cohort": (frozenset({"study", "dataset"}), frozenset({"study", "dataset"})),
    "shares_samples": (frozenset({"study", "dataset"}), frozenset({"study", "dataset"})),
    "propagated_from": (frozenset({"portal", "study", "dataset", "artifact"}), frozenset({"portal", "study", "dataset", "artifact"})),
    "training_overlap": (frozenset({"model", "dataset", "study", "artifact"}), frozenset({"model", "dataset", "study", "artifact"})),
}
INDEPENDENCE_RELATIONS = {"duplicates", "derived_from", "shares_cohort", "shares_samples", "propagated_from", "training_overlap"}
ACYCLIC_RELATIONS = {"depends_on", "derived_from", "propagated_from"}


class UnionFind:
    def __init__(self, values: Iterable[str]) -> None:
        self.parent = {value: value for value in values}
        self.rank = {value: 0 for value in values}
    def find(self, value: str) -> str:
        if self.parent[value] != value:
            self.parent[value] = self.find(self.parent[value])
        return self.parent[value]
    def union(self, left: str, right: str) -> None:
        a, b = self.find(left), self.find(right)
        if a == b:
            return
        if self.rank[a] < self.rank[b]:
            a, b = b, a
        self.parent[b] = a
        if self.rank[a] == self.rank[b]:
            self.rank[a] += 1


def graph_records(payload: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    if payload.get("schema_version") != 2:
        raise ValueError("unsupported evidence graph v2 schema")
    raw_nodes, raw_edges = payload.get("nodes"), payload.get("edges")
    if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
        raise ValueError("evidence graph nodes and edges must be lists")
    nodes: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(raw_nodes):
        if not isinstance(raw, dict):
            raise ValueError(f"node {index} must be an object")
        node_id = str(raw.get("id", "")).strip()
        node_type = str(raw.get("type", "")).strip()
        if not node_id or not node_type:
            raise ValueError(f"node {index} requires id and type")
        if node_id in nodes:
            raise ValueError(f"duplicate evidence node: {node_id}")
        nodes[node_id] = dict(raw)
    edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for index, raw in enumerate(raw_edges):
        if not isinstance(raw, dict):
            raise ValueError(f"edge {index} must be an object")
        source, target, relation = (str(raw.get(key, "")).strip() for key in ("source", "target", "relation"))
        if source not in nodes or target not in nodes:
            raise ValueError(f"edge endpoint missing: {source} -> {target}")
        if relation not in RELATION_TYPES:
            raise ValueError(f"unknown evidence relation: {relation}")
        key = (source, target, relation)
        if key in seen:
            raise ValueError(f"duplicate evidence edge: {source} {relation} {target}")
        seen.add(key)
        edges.append(dict(raw))
    return nodes, edges


def validate_typed_graph(nodes: dict[str, dict[str, Any]], edges: list[dict[str, Any]]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for edge in edges:
        relation, source, target = str(edge["relation"]), str(edge["source"]), str(edge["target"])
        allowed_sources, allowed_targets = RELATION_TYPES[relation]
        source_type, target_type = str(nodes[source].get("type", "")), str(nodes[target].get("type", ""))
        if source_type not in allowed_sources or target_type not in allowed_targets:
            findings.append({"code": "invalid-evidence-edge-type", "severity": "major", "message": f"Evidence edge {source} {relation} {target} has invalid types {source_type}->{target_type}."})
    directed: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        if edge["relation"] in ACYCLIC_RELATIONS:
            directed[str(edge["source"])].append(str(edge["target"]))
    state: dict[str, int] = {}
    def visit(node: str, stack: list[str]) -> None:
        state[node] = 1
        stack.append(node)
        for neighbour in directed.get(node, []):
            if state.get(neighbour) == 1:
                cycle = stack[stack.index(neighbour):] + [neighbour]
                findings.append({"code": "evidence-dependency-cycle", "severity": "major", "message": "Evidence dependency cycle: " + " -> ".join(cycle)})
            elif state.get(neighbour, 0) == 0:
                visit(neighbour, stack)
        stack.pop()
        state[node] = 2
    for node in sorted(nodes):
        if state.get(node, 0) == 0:
            visit(node, [])
    unique = {(item["code"], item["message"]): item for item in findings}
    return sorted(unique.values(), key=lambda item: (item["code"], item["message"]))


def validate_graph_payload(payload: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[dict[str, str]]]:
    nodes, edges = graph_records(payload)
    return nodes, edges, validate_typed_graph(nodes, edges)


def independence_components(nodes: dict[str, dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, str]:
    evidence = {node_id for node_id, node in nodes.items() if node.get("type") in {"study", "dataset", "artifact", "execution", "model", "portal"}}
    union = UnionFind(evidence)
    for edge in edges:
        if edge.get("relation") in INDEPENDENCE_RELATIONS and edge["source"] in evidence and edge["target"] in evidence:
            union.union(str(edge["source"]), str(edge["target"]))
    groups: dict[str, list[str]] = defaultdict(list)
    for node in evidence:
        groups[union.find(node)].append(node)
    canonical = {root: sorted(values)[0] for root, values in groups.items()}
    return {node: canonical[union.find(node)] for node in evidence}


def independent_support_groups(claim_id: str, nodes: dict[str, dict[str, Any]], edges: list[dict[str, Any]]) -> set[str]:
    components = independence_components(nodes, edges)
    sources = {str(edge["source"]) for edge in edges if edge.get("relation") == "supports" and str(edge.get("target")) == claim_id}
    return {components.get(source, source) for source in sources}


def impacted_nodes(changed: Iterable[str], edges: list[dict[str, Any]]) -> list[str]:
    forward: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        if edge.get("relation") in {"supports", "contradicts", "depends_on", "derived_from", "propagated_from", "training_overlap"}:
            forward[str(edge["source"])].add(str(edge["target"]))
    queue = deque(map(str, changed))
    seen = set(queue)
    while queue:
        node = queue.popleft()
        for neighbour in forward.get(node, set()):
            if neighbour not in seen:
                seen.add(neighbour)
                queue.append(neighbour)
    return sorted(seen)
