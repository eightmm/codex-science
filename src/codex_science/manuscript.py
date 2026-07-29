"""Build and validate traceable scientific manuscript packages."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any, Mapping


REQUIRED_FILES = {
    "manuscript-contract.json",
    "manuscript.md",
    "claim-citation-map.json",
    "reporting-checklist.json",
    "submission-package.json",
}
DECLARATION_FIELDS = {
    "authors",
    "contributions",
    "ethics",
    "funding",
    "conflicts",
    "data_availability",
}
DECLARATION_STATUSES = {"user-supplied", "not-applicable", "unknown"}
CLAIM_STATUSES = {
    "supported",
    "contradicted",
    "inconclusive",
    "unresolved",
    "withdrawn",
}
PACKAGE_STATUSES = {"draft", "review-ready", "submission-ready"}
MODES = {"new", "revision", "rebuttal"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _relative_path(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        return None
    return value


def _finding(code: str, message: str, *, severity: str = "major") -> dict[str, str]:
    return {"code": code, "severity": severity, "message": message}


def _load_json(
    root: Path,
    name: str,
    findings: list[dict[str, str]],
) -> dict[str, Any] | None:
    path = root / name
    if not path.is_file():
        findings.append(_finding("required-file-missing", f"Required file is missing: {name}"))
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as error:
        findings.append(_finding("invalid-json", f"Could not read {name}: {error}"))
        return None
    if not isinstance(payload, dict):
        findings.append(_finding("invalid-json-object", f"{name} must contain a JSON object"))
        return None
    return payload


def _check_file_ref(
    root: Path,
    record: object,
    findings: list[dict[str, str]],
    *,
    code: str,
    label: str,
) -> bool:
    if not isinstance(record, Mapping):
        findings.append(_finding(code, f"{label} must be a path and sha256 object"))
        return False
    relative = _relative_path(record.get("path"))
    digest = record.get("sha256")
    if relative is None or not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
        findings.append(_finding(code, f"{label} has an invalid path or sha256"))
        return False
    target = root / relative
    if not target.is_file() or not target.resolve().is_relative_to(root.resolve()):
        findings.append(_finding(code, f"{label} file is unavailable inside the package: {relative}"))
        return False
    if _sha256(target) != digest:
        findings.append(_finding(code, f"{label} digest does not match: {relative}"))
        return False
    return True


def validate_manuscript_package(package: Path) -> dict[str, Any]:
    """Return deterministic findings for one portable manuscript package."""
    root = Path(package).resolve()
    findings: list[dict[str, str]] = []
    if not root.is_dir():
        return {
            "schema_version": 1,
            "status": "failed",
            "findings": [_finding("package-missing", f"Package directory is missing: {root}")],
        }

    for name in sorted(REQUIRED_FILES):
        if not (root / name).is_file():
            findings.append(_finding("required-file-missing", f"Required file is missing: {name}"))

    contract = _load_json(root, "manuscript-contract.json", findings)
    trace = _load_json(root, "claim-citation-map.json", findings)
    checklist = _load_json(root, "reporting-checklist.json", findings)
    submission = _load_json(root, "submission-package.json", findings)
    manuscript_path = root / "manuscript.md"
    try:
        manuscript = manuscript_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        manuscript = ""

    manuscript_id = ""
    mode = ""
    output_formats: set[str] = set()
    if contract is not None:
        if contract.get("schema_version") != 1:
            findings.append(_finding("contract-schema-invalid", "Unsupported manuscript contract schema"))
        manuscript_id = str(contract.get("manuscript_id", "")).strip()
        if not manuscript_id:
            findings.append(_finding("manuscript-id-missing", "manuscript_id is required"))
        mode = str(contract.get("mode", ""))
        if mode not in MODES:
            findings.append(_finding("manuscript-mode-invalid", f"Unsupported manuscript mode: {mode}"))
        formats = contract.get("output_formats")
        if not isinstance(formats, list) or not all(isinstance(item, str) for item in formats):
            findings.append(_finding("output-formats-invalid", "output_formats must be a string list"))
        else:
            output_formats = set(formats)
        if "markdown" not in output_formats:
            findings.append(_finding("markdown-output-required", "Markdown is required for review"))
        if "latex" in output_formats and not (root / "manuscript.tex").is_file():
            findings.append(_finding("latex-output-missing", "LaTeX was requested but manuscript.tex is missing"))
        if "bibtex" in output_formats and not (root / "references.bib").is_file():
            findings.append(_finding("bibtex-output-missing", "BibTeX was requested but references.bib is missing"))

        _check_file_ref(
            root,
            contract.get("source_manifest"),
            findings,
            code="source-manifest-mismatch",
            label="source manifest",
        )
        declarations = contract.get("declarations")
        if not isinstance(declarations, Mapping):
            findings.append(_finding("declarations-invalid", "declarations must be an object"))
        else:
            for field in sorted(DECLARATION_FIELDS):
                record = declarations.get(field)
                status = record.get("status") if isinstance(record, Mapping) else None
                if status not in DECLARATION_STATUSES:
                    findings.append(
                        _finding("declaration-status-invalid", f"Declaration {field} has invalid status")
                    )

        if mode in {"revision", "rebuttal"}:
            if "prior_manuscript" not in contract:
                code = (
                    "rebuttal-prior-manuscript-required"
                    if mode == "rebuttal"
                    else "revision-prior-manuscript-required"
                )
                findings.append(_finding(code, f"{mode} requires the exact prior manuscript identity"))
            else:
                _check_file_ref(
                    root,
                    contract.get("prior_manuscript"),
                    findings,
                    code="prior-manuscript-mismatch",
                    label="prior manuscript",
                )
        if mode == "rebuttal":
            if "reviewer_comments" not in contract:
                findings.append(
                    _finding("rebuttal-comments-required", "Rebuttal requires hashed reviewer comments")
                )
            else:
                _check_file_ref(
                    root,
                    contract.get("reviewer_comments"),
                    findings,
                    code="reviewer-comments-mismatch",
                    label="reviewer comments",
                )
            if not (root / "reviewer-response.md").is_file():
                findings.append(
                    _finding("rebuttal-response-required", "Rebuttal requires reviewer-response.md")
                )

    package_status = ""
    listed_paths: set[str] = set()
    if submission is not None:
        if submission.get("schema_version") != 1:
            findings.append(_finding("submission-schema-invalid", "Unsupported submission schema"))
        if manuscript_id and submission.get("manuscript_id") != manuscript_id:
            findings.append(_finding("manuscript-id-mismatch", "Submission manuscript_id does not match"))
        package_status = str(submission.get("status", ""))
        if package_status not in PACKAGE_STATUSES:
            findings.append(_finding("submission-status-invalid", "Submission status is invalid"))
        files = submission.get("files")
        if not isinstance(files, list):
            findings.append(_finding("submission-files-invalid", "Submission files must be a list"))
        else:
            for record in files:
                if not isinstance(record, Mapping):
                    findings.append(_finding("submission-file-invalid", "Submission file record is invalid"))
                    continue
                relative = _relative_path(record.get("path"))
                if relative is None or relative == "submission-package.json":
                    findings.append(_finding("submission-file-invalid", "Submission path is unsafe or circular"))
                    continue
                if relative in listed_paths:
                    findings.append(_finding("submission-file-duplicate", f"Duplicate file: {relative}"))
                    continue
                listed_paths.add(relative)
                _check_file_ref(
                    root,
                    record,
                    findings,
                    code="submission-file-mismatch",
                    label=f"submission file {relative}",
                )
        review = submission.get("review")
        if not isinstance(review, Mapping):
            findings.append(_finding("submission-review-invalid", "Submission review must be an object"))
        elif package_status == "submission-ready":
            if review.get("status") != "passed":
                findings.append(
                    _finding("passed-review-required", "submission-ready requires a passed review")
                )
            _check_file_ref(
                root,
                review.get("receipt"),
                findings,
                code="review-receipt-mismatch",
                label="review receipt",
            )

    required_listed = REQUIRED_FILES - {"submission-package.json"}
    for name in sorted(required_listed - listed_paths):
        findings.append(_finding("submission-file-unlisted", f"Required file is not listed: {name}"))
    actual_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "submission-package.json"
    }
    for name in sorted(actual_paths - listed_paths):
        findings.append(_finding("submission-file-unlisted", f"Package file is not listed: {name}"))

    if contract is not None and package_status in {"review-ready", "submission-ready"}:
        declarations = contract.get("declarations", {})
        if isinstance(declarations, Mapping):
            for field in sorted(DECLARATION_FIELDS):
                record = declarations.get(field)
                if isinstance(record, Mapping) and record.get("status") == "unknown":
                    findings.append(
                        _finding(
                            "unresolved-declaration-for-review-ready",
                            f"Declaration {field} remains unknown",
                        )
                    )

    citation_by_id: dict[str, Mapping[str, Any]] = {}
    claim_ids: set[str] = set()
    if trace is not None:
        if trace.get("schema_version") != 1:
            findings.append(_finding("trace-schema-invalid", "Unsupported claim-citation schema"))
        if manuscript_id and trace.get("manuscript_id") != manuscript_id:
            findings.append(_finding("manuscript-id-mismatch", "Trace manuscript_id does not match"))
        citations = trace.get("citations")
        if not isinstance(citations, list):
            findings.append(_finding("citations-invalid", "citations must be a list"))
            citations = []
        for citation in citations:
            if not isinstance(citation, Mapping):
                findings.append(_finding("citation-invalid", "Citation record must be an object"))
                continue
            citation_id = str(citation.get("citation_id", "")).strip()
            if not citation_id or citation_id in citation_by_id:
                findings.append(_finding("citation-id-invalid", "Citation IDs must be unique and nonempty"))
                continue
            citation_by_id[citation_id] = citation
            if not str(citation.get("persistent_id", "")).strip():
                findings.append(_finding("citation-persistent-id-missing", f"{citation_id} has no persistent ID"))
            if citation.get("verified") is not True:
                findings.append(_finding("citation-unverified", f"{citation_id} is not verified"))
            if not str(citation.get("verification_source", "")).strip():
                findings.append(
                    _finding(
                        "citation-verification-source-missing",
                        f"{citation_id} has no verification source",
                    )
                )

        claims = trace.get("claims")
        if not isinstance(claims, list):
            findings.append(_finding("claims-invalid", "claims must be a list"))
            claims = []
        for claim in claims:
            if not isinstance(claim, Mapping):
                findings.append(_finding("claim-invalid", "Claim record must be an object"))
                continue
            claim_id = str(claim.get("claim_id", "")).strip()
            if not claim_id or claim_id in claim_ids:
                findings.append(_finding("claim-id-invalid", "Claim IDs must be unique and nonempty"))
                continue
            claim_ids.add(claim_id)
            status = claim.get("status")
            if status not in CLAIM_STATUSES:
                findings.append(_finding("claim-status-invalid", f"{claim_id} has invalid status"))
            evidence_refs = claim.get("evidence_refs")
            citation_ids = claim.get("citation_ids")
            if not isinstance(evidence_refs, list) or not isinstance(citation_ids, list):
                findings.append(_finding("claim-support-invalid", f"{claim_id} support fields must be lists"))
                continue
            if claim.get("material") is True and status == "supported" and not evidence_refs and not citation_ids:
                findings.append(
                    _finding("unsupported-material-claim", f"{claim_id} has no evidence or citation support")
                )
            locator = str(claim.get("manuscript_locator", "")).strip()
            if not locator or f"<!-- {locator} -->" not in manuscript:
                findings.append(
                    _finding("claim-locator-missing", f"{claim_id} locator is absent from manuscript.md")
                )
            for evidence in evidence_refs:
                _check_file_ref(
                    root,
                    evidence,
                    findings,
                    code="claim-evidence-mismatch",
                    label=f"evidence for {claim_id}",
                )
            for citation_id_value in citation_ids:
                citation_id = str(citation_id_value)
                citation = citation_by_id.get(citation_id)
                if citation is None:
                    findings.append(
                        _finding("citation-missing", f"{claim_id} references missing citation {citation_id}")
                    )
                elif claim_id not in citation.get("supports_claim_ids", []):
                    findings.append(
                        _finding(
                            "citation-claim-mismatch",
                            f"{citation_id} is not verified for attributed claim {claim_id}",
                        )
                    )
            values = claim.get("reported_values", [])
            if not isinstance(values, list):
                findings.append(_finding("reported-values-invalid", f"{claim_id} values must be a list"))
                continue
            for value in values:
                if not isinstance(value, Mapping):
                    findings.append(_finding("reported-value-invalid", f"{claim_id} value record is invalid"))
                    continue
                text = str(value.get("text", ""))
                if not text or text not in manuscript:
                    findings.append(
                        _finding(
                            "reported-value-not-in-manuscript",
                            f"Reported value for {claim_id} is not present verbatim in manuscript.md",
                        )
                    )
                _check_file_ref(
                    root,
                    {
                        "path": value.get("artifact_path"),
                        "sha256": value.get("artifact_sha256"),
                    },
                    findings,
                    code="reported-value-evidence-mismatch",
                    label=f"reported value for {claim_id}",
                )

    if "bibtex" in output_formats and (root / "references.bib").is_file():
        bibtex = (root / "references.bib").read_text(encoding="utf-8")
        for citation_id in sorted(citation_by_id):
            pattern = re.compile(r"@\w+\s*\{\s*" + re.escape(citation_id) + r"\s*,")
            if pattern.search(bibtex) is None:
                findings.append(
                    _finding("bibtex-entry-missing", f"BibTeX entry is missing: {citation_id}")
                )

    if checklist is not None:
        if checklist.get("schema_version") != 1:
            findings.append(_finding("checklist-schema-invalid", "Unsupported checklist schema"))
        if manuscript_id and checklist.get("manuscript_id") != manuscript_id:
            findings.append(_finding("manuscript-id-mismatch", "Checklist manuscript_id does not match"))
        items = checklist.get("items")
        if not isinstance(items, list):
            findings.append(_finding("checklist-items-invalid", "Checklist items must be a list"))
        elif package_status in {"review-ready", "submission-ready"}:
            for item in items:
                if isinstance(item, Mapping) and item.get("status") == "unresolved":
                    findings.append(
                        _finding(
                            "reporting-checklist-unresolved",
                            f"Reporting item remains unresolved: {item.get('id')}",
                        )
                    )

    unique = {
        (item["code"], item["message"]): item
        for item in findings
    }
    ordered = sorted(unique.values(), key=lambda item: (item["code"], item["message"]))
    return {
        "schema_version": 1,
        "status": "passed" if not ordered else "findings",
        "findings": ordered,
    }


def build_acceptance_package(specification: Mapping[str, Any], output: Path) -> Path:
    """Create a deterministic review-ready fixture; this is not a prose generator."""
    if specification.get("schema_version") != 1:
        raise ValueError("unsupported manuscript acceptance schema")
    root = Path(output)
    if root.exists() and any(root.iterdir()):
        raise ValueError(f"output directory is not empty: {root}")
    root.mkdir(parents=True, exist_ok=True)
    manuscript_id = str(specification.get("manuscript_id", "")).strip()
    if not manuscript_id:
        raise ValueError("manuscript_id is required")

    source_result = {
        "schema_version": 1,
        "claim_id": "source-effect",
        "estimate": 2.5,
        "unit": "response units",
        "interval": [1.2, 3.8],
        "status": "tested",
        "limitations": ["Deterministic acceptance fixture; not an empirical result."],
    }
    result_path = root / "source" / "result.json"
    _write_json(result_path, source_result)
    source_manifest = {
        "schema_version": 1,
        "run_id": "manuscript-source-fixture",
        "review": {"status": "passed"},
        "artifacts": [
            {
                "path": "result.json",
                "kind": "statistical-analysis",
                "sha256": _sha256(result_path),
            }
        ],
    }
    source_manifest_path = root / "source" / "manifest.json"
    _write_json(source_manifest_path, source_manifest)

    contract = {
        "schema_version": 1,
        "manuscript_id": manuscript_id,
        "mode": "new",
        "document_type": "research-article",
        "target_venue": specification.get("target_venue"),
        "evidence_cutoff": specification.get("evidence_cutoff"),
        "reporting_guideline": specification.get("reporting_guideline", "none"),
        "output_formats": ["markdown", "latex", "bibtex"],
        "source_manifest": {
            "path": "source/manifest.json",
            "sha256": _sha256(source_manifest_path),
        },
        "declarations": {
            "authors": {"status": "user-supplied", "value": ["Acceptance Fixture"]},
            "contributions": {"status": "user-supplied", "value": "Fixture generation only."},
            "ethics": {"status": "not-applicable"},
            "funding": {"status": "not-applicable"},
            "conflicts": {"status": "not-applicable"},
            "data_availability": {
                "status": "user-supplied",
                "value": "All deterministic fixture inputs are included in this package.",
            },
        },
    }
    _write_json(root / "manuscript-contract.json", contract)

    manuscript = (
        "# A traceable manuscript acceptance fixture\n\n"
        "## Abstract\n\n"
        "This deterministic fixture tests whether a manuscript package preserves evidence identity.\n\n"
        "## Methods\n\n"
        "The package validator was applied to a checked, local fixture [@ref-method].\n\n"
        "## Results\n\n"
        "<!-- claim:M-001 -->\n"
        "The recorded effect estimate was 2.5 response units with a fixture interval of "
        "1.2 to 3.8 response units.\n\n"
        "## Discussion\n\n"
        "<!-- claim:M-002 -->\n"
        "This value demonstrates package traceability only and is not an empirical scientific result.\n"
    )
    (root / "manuscript.md").write_text(manuscript, encoding="utf-8")
    (root / "manuscript.tex").write_text(
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\title{A traceable manuscript acceptance fixture}\n"
        "\\maketitle\n"
        "The recorded effect estimate was 2.5 response units.\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    (root / "references.bib").write_text(
        "@misc{ref-method,\n"
        "  title = {Codex Science manuscript package acceptance fixture},\n"
        "  year = {2026},\n"
        "  note = {Repository-local deterministic fixture; not a publication}\n"
        "}\n",
        encoding="utf-8",
    )
    trace = {
        "schema_version": 1,
        "manuscript_id": manuscript_id,
        "claims": [
            {
                "claim_id": "M-001",
                "source_claim_id": "source-effect",
                "material": True,
                "text": "The recorded effect estimate was 2.5 response units.",
                "inference_level": "descriptive",
                "status": "supported",
                "manuscript_locator": "claim:M-001",
                "evidence_refs": [
                    {
                        "path": "source/result.json",
                        "sha256": _sha256(result_path),
                        "locator": "/estimate",
                    }
                ],
                "citation_ids": ["ref-method"],
                "reported_values": [
                    {
                        "text": "2.5 response units",
                        "artifact_path": "source/result.json",
                        "artifact_sha256": _sha256(result_path),
                        "locator": "/estimate",
                    }
                ],
            },
            {
                "claim_id": "M-002",
                "source_claim_id": "source-effect",
                "material": True,
                "text": "This value demonstrates package traceability only.",
                "inference_level": "operational",
                "status": "supported",
                "manuscript_locator": "claim:M-002",
                "evidence_refs": [
                    {
                        "path": "source/manifest.json",
                        "sha256": _sha256(source_manifest_path),
                        "locator": "/review/status",
                    }
                ],
                "citation_ids": [],
                "reported_values": [],
            },
        ],
        "citations": [
            {
                "citation_id": "ref-method",
                "persistent_id": "urn:codex-science:fixture:manuscript-package-v1",
                "title": "Codex Science manuscript package acceptance fixture",
                "source_type": "repository-fixture",
                "verified": True,
                "verification_source": "source/manifest.json",
                "supports_claim_ids": ["M-001"],
            }
        ],
    }
    _write_json(root / "claim-citation-map.json", trace)
    checklist = {
        "schema_version": 1,
        "manuscript_id": manuscript_id,
        "guideline": "repository acceptance fixture",
        "items": [
            {
                "id": "traceability",
                "status": "met",
                "manuscript_locator": "claim:M-001",
                "evidence_refs": ["source/result.json"],
            },
            {"id": "human-participants", "status": "not-applicable", "evidence_refs": []},
        ],
    }
    _write_json(root / "reporting-checklist.json", checklist)

    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "submission-package.json":
            files.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "kind": "manuscript-package-file",
                    "sha256": _sha256(path),
                }
            )
    submission = {
        "schema_version": 1,
        "manuscript_id": manuscript_id,
        "status": "review-ready",
        "files": files,
        "review": {
            "status": "pending",
            "required_modes": ["record", "source", "method"],
        },
    }
    _write_json(root / "submission-package.json", submission)
    return root
