"""Typed evidence-dependency validation and independence-component analysis."""

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
INDEPENDENCE_RELATIONS = {
    "duplicates",
    "derived_from",
    "shares_cohort",
    "shares_samples",
    "propagated_from",
    "training_overlap",
}
ACYCLIC_RELATIONS = {"depends_on", "derived_from", "propagated_from"}


class _UnionFind:
    def __init__(self, values: Iterable[str]) -> None:
        self.parent = {value: value for value in values}
        self.rank = {value: 0 for value in values}

    def find(self, value: str) -> str:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        if self.rank[left_root] < self.rank[right_root]:
            left_root, right_root = right_root, left_root
        self.parent[right_root] = left_root
        if self.rank[left_root] == self.rank[right_root]:
            self.rank[left_root] += 1


def validate_typed_graph(
    nodes: dict[str, dict[str, Any]], edges: list[dict[str, Any]]
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for edge in edges:
        relation = str(edge.get("relation", ""))
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        if relation not in RELATION_TYPES or source not in nodes or target not in nodes:
            continue
        allowed_sources, allowed_targets = RELATION_TYPES[relation]
        source_type = str(nodes[source].get("type", ""))
        target_type = str(nodes[target].get("type", ""))
        if source_type not in allowed_sources or target_type not in allowed_targets:
            findings.append(
                {
                    "code": "invalid-evidence-edge-type",
                    "severity": "major",
                    "message": (
                        f"Evidence edge {source} {relation} {target} has invalid types "
                        f"{source_type}->{target_type}."
                    ),
                }
            )

    directed: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        if edge.get("relation") in ACYCLIC_RELATIONS:
            directed[str(edge["source"])].append(str(edge["target"]))
    state: dict[str, int] = {}

    def visit(node: str, stack: list[str]) -> None:
        state[node] = 1
        stack.append(node)
        for neighbour in directed.get(node, []):
            if state.get(neighbour) == 1:
                cycle = stack[stack.index(neighbour) :] + [neighbour]
                findings.append(
                    {
                        "code": "evidence-dependency-cycle",
                        "severity": "major",
                        "message": "Evidence dependency cycle: " + " -> ".join(cycle),
                    }
                )
            elif state.get(neighbour, 0) == 0:
                visit(neighbour, stack)
        stack.pop()
        state[node] = 2

    for node in sorted(nodes):
        if state.get(node, 0) == 0:
            visit(node, [])
    unique = {
        (item["code"], item["message"]): item
        for item in findings
    }
    return sorted(unique.values(), key=lambda item: (item["code"], item["message"]))


def independence_components(
    nodes: dict[str, dict[str, Any]], edges: list[dict[str, Any]]
) -> dict[str, str]:
    evidence_nodes = {
        node_id
        for node_id, node in nodes.items()
        if node.get("type") in {"study", "dataset", "artifact", "execution", "model", "portal"}
    }
    union = _UnionFind(evidence_nodes)
    for edge in edges:
        if edge.get("relation") not in INDEPENDENCE_RELATIONS:
            continue
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        if source in evidence_nodes and target in evidence_nodes:
            union.union(source, target)
    roots = {node: union.find(node) for node in evidence_nodes}
    canonical = {
        root: sorted(node for node, value in roots.items() if value == root)[0]
        for root in set(roots.values())
    }
    return {node: canonical[root] for node, root in roots.items()}


def independent_support_groups(
    claim_id: str,
    nodes: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
) -> set[str]:
    components = independence_components(nodes, edges)
    sources = {
        str(edge["source"])
        for edge in edges
        if edge.get("relation") == "supports" and str(edge.get("target")) == claim_id
    }
    return {components.get(source, source) for source in sources}


def impacted_nodes(
    changed: Iterable[str], edges: list[dict[str, Any]]
) -> list[str]:
    """Traverse support/dependency/derivation edges to find invalidated downstream nodes."""

    forward: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        relation = str(edge.get("relation", ""))
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        if relation in {"supports", "contradicts", "depends_on", "derived_from", "propagated_from", "training_overlap"}:
            forward[source].add(target)
    queue = deque(str(item) for item in changed)
    seen = set(queue)
    while queue:
        current = queue.popleft()
        for neighbour in forward.get(current, set()):
            if neighbour not in seen:
                seen.add(neighbour)
                queue.append(neighbour)
    return sorted(seen)
