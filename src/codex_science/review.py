"""Record-based scientific review checks that never imply an unperformed rerun."""
from __future__ import annotations

from pathlib import Path
from typing import Any


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
        if execution.get("exit_code") != 0:
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
        from codex_science.evidence import review_sidecars
        findings.extend(review_sidecars(sidecars))
        findings.extend(sidecars.get("advanced_findings", []))
    unique = {(item["code"], item.get("claim_id", ""), item["message"]): item for item in findings}
    ordered = sorted(unique.values(), key=lambda item: (item.get("severity", ""), item["code"], item.get("claim_id", ""), item["message"]))
    return {"status": "findings" if ordered else "passed", "findings": ordered}
