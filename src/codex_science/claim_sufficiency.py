"""Read-only sufficiency check; support and contradiction counts come only from the study table."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from codex_science.artifacts import validate_bundle
from codex_science.evidence import _persistent_id
from codex_science.evidence_graph_v2 import INDEPENDENCE_RELATIONS, UnionFind


SCHEMA = "claim-sufficiency-v1"
EVIDENCE_BOUNDARY = "counts recorded links only; does not judge whether evidence entails the claim"
TIERS = ("quick", "standard", "full")
EVIDENCE_NODE_TYPES = frozenset({
    "study", "dataset", "artifact", "execution", "model", "portal", "cohort", "sample",
})
SUFFICIENCY_POLICY = {
    "schema": "sufficiency-policy-v1",
    "tiers": {"quick": 1, "standard": 2, "full": 2},
    "full_claim_kinds": {"causal": 3, "confirmatory": 3},
    "replicated_minimum": 2,
}


def _group_id(study: dict[str, Any], edge: dict[str, Any]) -> str:
    explicit = str(edge.get("independence_group") or "").strip()
    if explicit:
        return explicit
    cohort = str(study.get("cohort_id") or "").strip()
    if cohort:
        return cohort
    persistent = _persistent_id(study.get("persistent_id") or "")
    return f"pid:{persistent}" if persistent else str(edge["source"])


def check_sufficiency(run_dir: str | Path, *, tier: str) -> dict[str, Any]:
    """Count distinct included study groups and report claim support sufficiency."""
    if tier not in TIERS:
        raise ValueError(f"tier must be one of {TIERS!r}")
    root = Path(run_dir)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    sidecars = validate_bundle(manifest, root)
    manifest_claims = {
        str(item["id"]).strip(): item
        for item in manifest.get("claims", [])
        if isinstance(item, dict) and item.get("id") is not None
    }
    claims = sidecars.get("claim_by_id") or {
        claim_id: item for claim_id, item in manifest_claims.items()
    }
    studies = sidecars.get("study_by_id", {})
    edges = sidecars.get("edges", [])
    edge_groups = {
        (str(edge.get("source", "")), str(edge.get("target", "")), str(edge.get("relation", ""))): edge
        for edge in edges
    }
    # Claims and queries describe evidence without making it dependent.
    nodes = sidecars.get("node_by_id", {})
    keys = {
        str(node_id) for node_id, node in nodes.items()
        if node.get("type") in EVIDENCE_NODE_TYPES
    }
    keys.update(str(sid) for sid in studies)
    independence_edges = [
        edge for edge in edges
        if str(edge.get("relation", "")) in INDEPENDENCE_RELATIONS
        and str(edge["source"]) in keys and str(edge["target"]) in keys
    ]
    union = UnionFind(keys)
    for edge in independence_edges:
        union.union(str(edge["source"]), str(edge["target"]))

    supporting: dict[str, list[tuple[str, str]]] = {claim_id: [] for claim_id in claims}
    contradicting: dict[str, list[tuple[str, str]]] = {claim_id: [] for claim_id in claims}
    # The study table records which studies were included and which claims they
    # support or contradict; graph edges add optional independence metadata.
    for study_id, study in studies.items():
        if not study.get("included", False):
            continue
        for relation, field, groups in (
            ("supports", "supports_claim_ids", supporting),
            ("contradicts", "contradicts_claim_ids", contradicting),
        ):
            for claim_id in study.get(field, []):
                claim_id = str(claim_id)
                if claim_id in claims:
                    edge = edge_groups.get((study_id, claim_id, relation), {"source": study_id})
                    groups[claim_id].append((str(study_id), _group_id(study, edge)))

    def count_groups(memberships: list[tuple[str, str]]) -> int:
        # Shared labels and graph connectivity merge only within this claim/relation.
        gids = {gid for _, gid in memberships}
        local = UnionFind(gids)
        first_gid: dict[str, str] = {}
        for study_id, gid in memberships:
            study_root = union.find(study_id)
            local.union(gid, first_gid.setdefault(study_root, gid))
        return len({local.find(gid) for gid in gids})

    rows: list[dict[str, Any]] = []
    for claim_id in sorted(claims):
        claim = claims[claim_id]
        status = str(claim.get("status", ""))
        if status not in {"supported", "replicated"}:
            continue
        manifest_claim = manifest_claims.get(claim_id, {})
        kind = claim.get("kind", manifest_claim.get("kind"))
        required = SUFFICIENCY_POLICY["tiers"][tier]
        if status == "replicated":
            required = max(required, SUFFICIENCY_POLICY["replicated_minimum"])
        if tier == "full":
            required = max(required, SUFFICIENCY_POLICY["full_claim_kinds"].get(kind, 0))
        support_count = count_groups(supporting[claim_id])
        contradiction_count = count_groups(contradicting[claim_id])
        unresolved = contradiction_count > 0 and not str(claim.get("contradiction_resolution", "")).strip()
        if unresolved:
            verdict = "contradicted_unresolved"
        elif support_count < required:
            verdict = "insufficient"
        else:
            verdict = "sufficient"
        recommended = status
        if verdict == "insufficient":
            recommended = "suggestive" if support_count else "unsupported"
        elif verdict == "contradicted_unresolved":
            recommended = "conflicting"
        rows.append({
            "id": claim_id,
            "status": status,
            "kind": kind,
            "supporting_groups": support_count,
            "contradicting_groups": contradiction_count,
            "required": required,
            "verdict": verdict,
            "recommended_status": recommended,
        })
    counts = {key: sum(row["verdict"] == key for row in rows)
              for key in ("sufficient", "insufficient", "contradicted_unresolved")}
    return {"schema": SCHEMA, "policy": SUFFICIENCY_POLICY["schema"],
            "tier": tier, "claims": rows, "counts": counts,
            "evidence_boundary": EVIDENCE_BOUNDARY}
