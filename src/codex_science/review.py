"""Record-based scientific review checks that never imply an unperformed rerun."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from codex_science.artifact_store import stream_sha256


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


_MAX_INSPECTED_ARTIFACT_BYTES = 64_000_000


def _error_object_artifact_findings(manifest: dict[str, Any], run_dir: Path | None) -> list[dict[str, str]]:
    if run_dir is None:
        return []
    root = Path(run_dir).resolve()
    found = []
    for item in manifest.get("artifacts", []):
        if not isinstance(item, dict) or item.get("kind") not in {"claim-sufficiency", "citation-trace"} or not isinstance(item.get("path"), str):
            continue
        path = (root / item["path"]).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            continue
        reason, payload = None, None
        try:
            size = path.stat().st_size
            if size > _MAX_INSPECTED_ARTIFACT_BYTES:
                reason = f"is {size} bytes, above the {_MAX_INSPECTED_ARTIFACT_BYTES}-byte inspection limit"
            else:
                payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, RecursionError) as error:
            reason = f"is not readable JSON ({type(error).__name__})"
        if reason:
            found.append({"code": "uninspectable-generated-artifact", "severity": "major", "message": (
                f"Artifact {item['path']} {reason}, so it cannot be checked for an error object. Regenerate it with the producing CLI --output.")})
            continue
        schema = payload.get("schema") if isinstance(payload, dict) else None
        if isinstance(schema, str) and schema.endswith("-error-v1"):
            found.append({"code": "error-object-artifact", "severity": "major", "message": (
                f"Artifact {item['path']} is a {schema} error object, not a result. Rerun the producing CLI with --output {item['path']} "
                "after `package_run.py refresh` (or use `package_run.py prepare-review`); never redirect its stdout into the artifact.")})
    return found


def _execution_record_findings(manifest: dict[str, Any], run_dir: Path | None) -> list[dict[str, str]]:
    if run_dir is None:
        return []
    root = Path(run_dir).resolve()
    records = [*manifest.get("executions", []), *manifest.get("superseded_executions", [])]
    findings = []
    for execution in records:
        relative, expected = execution.get("log_path"), execution.get("log_sha256")
        if relative is None or expected is None:
            continue
        code = None
        try:
            if not isinstance(relative, str) or not relative or not isinstance(expected, str):
                raise ValueError("invalid log metadata")
            path = (root / relative).resolve()
            if not path.is_relative_to(root):
                raise ValueError("log escapes run directory")
            if not path.is_file():
                code = "execution-log-missing"
            elif stream_sha256(path)[0] != expected.lower():
                code = "execution-log-mismatch"
        except (OSError, ValueError, RuntimeError):
            code = "execution-log-mismatch"
        if code:
            findings.append({"code": code, "severity": "major", "message": f"Execution {execution.get('id', '<unknown>')} log is missing, outside the run directory or differs from its recorded digest: {relative}."})
    journal = root / "execution-log.jsonl"
    known_ids = {item.get("id") for item in records}
    try:
        if journal.is_symlink() and not journal.resolve().is_relative_to(root):
            raise ValueError("execution journal escapes run directory")
        if journal.exists():
            with journal.open(encoding="utf-8") as stream:
                for number, line in enumerate(stream, 1):
                    if not line.strip():
                        continue
                    entry = json.loads(line)
                    if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or not entry["id"].strip():
                        raise ValueError(f"invalid execution record at line {number}")
                    if entry["id"] not in known_ids:
                        findings.append({"code": "unincorporated-execution", "severity": "major", "message": f"Execution {entry['id']} is not in the manifest; run package_run.py refresh before reviewing."})
    except (OSError, ValueError, RuntimeError) as error:
        findings.append({"code": "invalid-execution-journal", "severity": "major", "message": f"Cannot verify execution-log.jsonl: {error}. Run package_run.py refresh after repairing the journal."})
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
    elif declared_review.get("status") == "passed":
        findings.extend(item for item in declared_review.get("findings", [])
                        if isinstance(item, dict) and item.get("severity") in {"major", "critical"}
                        and item.get("resolution_status", "open") not in {"resolved", "not-applicable"})
    findings.extend(_execution_record_findings(manifest, run_dir))
    artifacts = {str(item.get("path")) for item in manifest.get("artifacts", [])}
    for execution in manifest.get("executions", []):
        if not _execution_succeeded(execution):
            findings.append({"code": "failed-execution", "severity": "major", "message": f"Execution failed: {execution.get('command', '<unknown>')}. If the nonzero exit was the expected outcome of a negative check, record it as a command that exits 0 only when the expected rejection is observed. A transient source failure clears when the identical command is rerun and succeeds."})
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
                findings.append({"code": "missing-evidence", "severity": "major", "message": f"Claim evidence is not a saved artifact: {path} (claim {claim.get('id', '<unknown>')}; evidence entries must be manifest artifact paths, not identifiers)"})
    if sidecars is None and run_dir is not None:
        from codex_science.artifacts import validate_bundle
        sidecars = validate_bundle(manifest, run_dir)
    if sidecars is not None:
        findings.extend(computed_claim_execution_findings(manifest, sidecars))
        from codex_science.evidence import review_sidecars
        findings.extend(review_sidecars(sidecars))
        findings.extend(sidecars.get("advanced_findings", []))
    findings.extend(_error_object_artifact_findings(manifest, run_dir))
    unique = {(item["code"], item.get("claim_id", ""), item.get("id", ""), item.get("affected_claim_id", ""), item["message"]): item for item in findings}
    ordered = sorted(unique.values(), key=lambda item: (item.get("severity", ""), item["code"], item.get("claim_id", ""), item["message"]))
    return {"status": "findings" if ordered else "passed", "findings": ordered}
