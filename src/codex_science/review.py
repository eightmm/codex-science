"""Record-based review checks that never claim to re-run an analysis."""

from __future__ import annotations

from typing import Any


def review_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    artifacts = {str(item.get("path")) for item in manifest.get("artifacts", [])}

    for execution in manifest.get("executions", []):
        if execution.get("exit_code") != 0:
            findings.append(
                {
                    "code": "failed-execution",
                    "message": f"Execution failed: {execution.get('command', '<unknown>')}",
                }
            )
    for step in manifest.get("plan", []):
        if step.get("status") != "completed":
            findings.append(
                {
                    "code": "incomplete-plan",
                    "message": f"Plan step is not complete: {step.get('id', '<unknown>')}",
                }
            )
    for claim in manifest.get("claims", []):
        evidence = claim.get("evidence", [])
        if not evidence:
            findings.append(
                {
                    "code": "unsupported-claim",
                    "message": f"Claim has no evidence: {claim.get('id', '<unknown>')}",
                }
            )
            continue
        for path in evidence:
            if path not in artifacts:
                findings.append(
                    {
                        "code": "missing-evidence",
                        "message": f"Claim evidence is not a saved artifact: {path}",
                    }
                )

    findings.sort(key=lambda item: (item["code"], item["message"]))
    return {"status": "findings" if findings else "passed", "findings": findings}
