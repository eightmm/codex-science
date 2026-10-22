"""Record-based scientific review checks that never imply an unperformed rerun."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def _execution_succeeded(execution: dict[str, Any]) -> bool:
    # bool is an int subclass, but it is not a recorded process exit status.
    return type(execution.get("exit_code")) is int and execution["exit_code"] == 0


def evidence_node_execution_status(
    manifest: dict[str, Any], node_id: str, node: dict[str, Any]
) -> bool | None:
    """Return linked status, or None when a legacy manifest cannot verify it."""
    executions = [
        item for item in manifest.get("executions", []) if isinstance(item, dict)
    ]
    successful = [item for item in executions if _execution_succeeded(item)]
    if node.get("type") == "execution":
        if not any("id" in item for item in executions):
            return None
        return any(item.get("id") == node_id for item in successful)
    if node.get("type") != "artifact":
        return False

    if not any("outputs" in item for item in executions):
        return None
    path = str(node.get("path", node_id))
    artifact = next(
        (item for item in manifest.get("artifacts", [])
         if isinstance(item, dict) and str(item.get("path", "")) == path),
        None,
    )
    if artifact is None:
        return False
    artifact_hash = str(artifact.get("sha256", "")).lower()
    node_hash = str(node.get("sha256", "")).lower()
    if artifact_hash and node_hash and artifact_hash != node_hash:
        return False
    for execution in successful:
        outputs = execution.get("outputs", [])
        if not isinstance(outputs, list):
            continue
        for output in outputs:
            if isinstance(output, str):
                output_path, output_hash = output, ""
            elif isinstance(output, dict):
                output_path = str(output.get("path", ""))
                output_hash = str(output.get("sha256", "")).lower()
            else:
                continue
            expected_hash = artifact_hash or node_hash
            if output_path == path and (not output_hash or not expected_hash or output_hash == expected_hash):
                return True
    # Artifact manifests do not currently record a producing execution, so an
    # artifact without a matching execution output stays conservatively unlinked.
    return False


def evidence_node_has_successful_execution(
    manifest: dict[str, Any], node_id: str, node: dict[str, Any]
) -> bool:
    status = evidence_node_execution_status(manifest, node_id, node)
    if status is not None:
        return status
    return any(_execution_succeeded(item) for item in manifest.get("executions", []) if isinstance(item, dict))


def computed_claim_execution_findings(
    manifest: dict[str, Any], sidecars: dict[str, Any] | None
) -> list[dict[str, str]]:
    if not isinstance(sidecars, dict):
        return []
    graph = sidecars.get("graph_v2") or sidecars.get("evidence_graph")
    if not isinstance(graph, dict):
        return []
    nodes = {
        str(node.get("id")): node for node in graph.get("nodes", [])
        if isinstance(node, dict) and node.get("id") is not None
    }
    supported: dict[str, set[str]] = {}
    for edge in graph.get("edges", []):
        if isinstance(edge, dict) and edge.get("relation") == "supports":
            supported.setdefault(str(edge.get("target", "")), set()).add(str(edge.get("source", "")))
    claims = {
        str(claim.get("id")): claim for claim in manifest.get("claims", [])
        if isinstance(claim, dict) and claim.get("id")
    }
    claim_records = sidecars.get("claim_by_id", {})
    executions = [item for item in manifest.get("executions", []) if isinstance(item, dict)]
    has_linkage_metadata = any("id" in item or "outputs" in item for item in executions)
    findings = []
    for claim_id, claim in claims.items():
        refs = supported.get(claim_id, set())
        support_nodes = [
            (ref, nodes[ref]) for ref in refs if isinstance(nodes.get(ref), dict)
        ]
        if not support_nodes:
            continue
        data_nodes = [
            (ref, node) for ref, node in support_nodes
            if node.get("type") in {"execution", "artifact"}
        ]
        registered_claim = claim_records.get(claim_id, {}) if isinstance(claim_records, dict) else {}
        required_evidence = (
            registered_claim.get("required_evidence", claim.get("required_evidence", []))
            if isinstance(registered_claim, dict) else claim.get("required_evidence", [])
        )
        is_computed = isinstance(required_evidence, list) and "computed" in required_evidence
        if not is_computed:
            continue
        if data_nodes:
            linked = any(
                evidence_node_has_successful_execution(manifest, ref, node)
                for ref, node in data_nodes
            )
        elif has_linkage_metadata:
            linked = False
        else:
            linked = any(_execution_succeeded(item) for item in executions)
        if not linked:
            findings.append({
                "code": "computed-claim-without-execution",
                "severity": "major",
                "message": f"Computed claim {claim_id} has no linked successful execution.",
                "claim_id": claim_id,
            })
    return findings


def review_manifest(manifest: dict[str, Any], run_dir: Path | None = None, *, sidecars: dict[str, Any] | None = None) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    declared_review = manifest.get("review", {})
    if declared_review.get("status") in {"findings", "blocked"}:
        declared_findings = declared_review.get("findings", [])
        if declared_findings:
            findings.extend(declared_findings)
        else:
            findings.append({"code": "declared-review-not-passed", "severity": "major", "message": f"Manifest review status is {declared_review.get('status', 'unknown')}."})
    artifacts = {str(item.get("path")) for item in manifest.get("artifacts", [])}
    for execution in manifest.get("executions", []):
        if not _execution_succeeded(execution):
            findings.append({"code": "failed-execution", "severity": "major", "message": f"Execution failed: {execution.get('command', '<unknown>')}"})
    for step in manifest.get("plan", []):
        if step.get("status") != "completed":
            findings.append({"code": "incomplete-plan", "severity": "major", "message": f"Plan step is not complete: {step.get('id', '<unknown>')}"})
    for claim in manifest.get("claims", []):
        evidence = claim.get("evidence", [])
        if not evidence:
            findings.append({"code": "unsupported-claim", "severity": "major", "message": f"Claim has no evidence: {claim.get('id', '<unknown>')}"})
            continue
        for path in evidence:
            if path not in artifacts:
                findings.append({"code": "missing-evidence", "severity": "major", "message": f"Claim evidence is not a saved artifact: {path}"})
    if sidecars is None and run_dir is not None:
        from codex_science.artifacts import validate_bundle
        sidecars = validate_bundle(manifest, run_dir)
    if sidecars is not None:
        findings.extend(computed_claim_execution_findings(manifest, sidecars))
        from codex_science.evidence import review_sidecars
        findings.extend(review_sidecars(sidecars))
        findings.extend(sidecars.get("advanced_findings", []))
    unique = {(item["code"], item.get("claim_id", ""), item["message"]): item for item in findings}
    ordered = sorted(unique.values(), key=lambda item: (item.get("severity", ""), item["code"], item.get("claim_id", ""), item["message"]))
    return {"status": "findings" if ordered else "passed", "findings": ordered}
