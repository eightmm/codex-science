"""Build and validate traceable scientific manuscript packages."""
from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from codex_science.advanced_sidecars import review_advanced_sidecars
from codex_science.artifacts import validate_bundle
from codex_science.review import review_manifest
from codex_science.review_receipts import review_receipt_findings
from codex_science.reviewer_runtime import (
    build_review_packet,
    finalize_review_response,
    validate_review_packet,
)


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
    "citation-needed",
    "supported",
    "contradicted",
    "inconclusive",
    "unresolved",
    "withdrawn",
}
UNRESOLVED_CLAIM_STATUSES = {"citation-needed", "unresolved"}
PACKAGE_STATUSES = {"draft", "review-ready", "submission-ready"}
MODES = {"new", "revision", "rebuttal"}
REQUIRED_SUBMISSION_REVIEW_MODES = frozenset({"record", "source", "method"})
REVIEW_RECEIPT_KINDS = frozenset({"review-receipt", "review-receipt-v2"})
REVIEW_PACKET_KINDS = frozenset({"review-packet", "review-packet-v1"})
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CLAIM_MARKER_RE = re.compile(r"<!--\s*claim:[^>]+-->")
NUMBER_RE = re.compile(
    r"(?<![0-9A-Za-z_.])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?(?![0-9A-Za-z_]|\.\d)"
)


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


def _claim_segment(manuscript: str, locator: str) -> tuple[str | None, str | None]:
    marker = f"<!-- {locator} -->"
    occurrences = manuscript.count(marker)
    if occurrences != 1:
        return None, "missing" if occurrences == 0 else "ambiguous"
    start = manuscript.index(marker) + len(marker)
    next_marker = CLAIM_MARKER_RE.search(manuscript, start)
    end = len(manuscript) if next_marker is None else next_marker.start()
    return manuscript[start:end], None


def _resolve_json_pointer(payload: Any, pointer: str) -> Any:
    if pointer == "":
        return payload
    if not pointer.startswith("/"):
        raise ValueError("JSON locator must be an RFC 6901 pointer")
    current = payload
    for raw_token in pointer[1:].split("/"):
        if re.search(r"~(?![01])", raw_token):
            raise ValueError("JSON locator contains an invalid escape")
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            if not token.isdigit():
                raise ValueError("JSON array locator must use a numeric index")
            index = int(token)
            if index >= len(current):
                raise ValueError("JSON array locator is out of range")
            current = current[index]
        elif isinstance(current, Mapping):
            if token not in current:
                raise ValueError("JSON locator does not exist")
            current = current[token]
        else:
            raise ValueError("JSON locator descends through a scalar value")
    return current


def _scalar_appears_in_text(value: Any, text: str) -> bool:
    if isinstance(value, str):
        return value in text
    if value is None or isinstance(value, bool):
        return json.dumps(value) in text.lower()
    if isinstance(value, (int, float)):
        expected = Decimal(str(value))
        if not expected.is_finite():
            return False
        normalized_text = text.replace("\N{MINUS SIGN}", "-")
        normalized_text = re.sub(r"(?<=\d),(?=\d{3}(?:\D|$))", "", normalized_text)
        for token in NUMBER_RE.findall(normalized_text):
            try:
                if Decimal(token) == expected:
                    return True
            except InvalidOperation:
                continue
        return False
    return False


def _review_packet_scope(
    packet: Mapping[str, Any],
    review_metadata_paths: set[str],
) -> dict[str, Any]:
    """Return the source semantics that an independent review packet freezes."""
    return {
        "source_run_id": packet.get("source_run_id"),
        "decision_contract": packet.get("decision_contract"),
        "claims": packet.get("claims"),
        "material_claim_ids": packet.get("material_claim_ids"),
        "artifacts": [
            item
            for item in packet.get("artifacts", [])
            if isinstance(item, Mapping) and str(item.get("path")) not in review_metadata_paths
        ],
        "evidence_graph": packet.get("evidence_graph"),
        "study_table": packet.get("study_table"),
        "query_records": packet.get("query_records"),
        "lane_receipts": packet.get("lane_receipts"),
        "model_receipts": packet.get("model_receipts"),
    }


def _review_receipt_contract_findings(
    receipt: Mapping[str, Any],
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    limitations = receipt.get("limitations")
    if not isinstance(limitations, list) or not limitations or not all(
        isinstance(item, str) and item.strip() for item in limitations
    ):
        findings.append(
            {
                "code": "review-receipt-limitations-missing",
                "severity": "major",
                "message": "Independent review receipt must state at least one limitation.",
            }
        )
    for index, item in enumerate(receipt.get("findings", [])):
        if not isinstance(item, Mapping):
            continue
        severity = str(item.get("severity", "")).strip()
        code = str(item.get("code", "")).strip()
        message = str(item.get("message", item.get("rationale", ""))).strip()
        resolution = str(item.get("resolution_status", "open"))
        evidence = item.get("evidence", [])
        if (
            severity not in {"critical", "major", "minor", "suggestion"}
            or not code
            or not message
            or resolution not in {"open", "resolved", "accepted-risk", "not-applicable"}
            or not isinstance(evidence, list)
        ):
            findings.append(
                {
                    "code": "review-receipt-finding-invalid",
                    "severity": "major",
                    "message": f"Independent review receipt finding {index} is malformed.",
                }
            )
    return findings


def _validate_source_bundle(
    root: Path,
    record: object,
    package_status: str,
    findings: list[dict[str, str]],
) -> set[str] | None:
    if not _check_file_ref(
        root,
        record,
        findings,
        code="source-manifest-mismatch",
        label="source manifest",
    ):
        return None
    assert isinstance(record, Mapping)
    relative = str(record["path"])
    manifest_path = root / relative
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError("source manifest must be a JSON object")
        sidecars = validate_bundle(manifest, manifest_path.parent)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError, ValueError) as error:
        findings.append(_finding("source-manifest-invalid", f"Source bundle is invalid: {error}"))
        return None

    source_claim_ids = {
        str(claim.get("id", "")).strip()
        for claim in manifest.get("claims", [])
        if isinstance(claim, Mapping) and str(claim.get("id", "")).strip()
    }
    if package_status not in {"review-ready", "submission-ready"}:
        return source_claim_ids
    declared_review = manifest.get("review", {})
    if declared_review.get("status") != "passed":
        findings.append(
            _finding("source-review-not-passed", "Review-ready manuscript requires a passed source review")
        )
    declared_findings = declared_review.get("findings", [])
    if not isinstance(declared_findings, list) or not all(
        isinstance(item, Mapping) for item in declared_findings
    ):
        findings.append(
            _finding("source-review-findings-invalid", "Source review findings must be a list")
        )
    elif declared_review.get("status") == "passed" and any(
        isinstance(item, Mapping)
        and item.get("severity") in {"critical", "major"}
        and item.get("resolution_status", "open") not in {"resolved", "not-applicable"}
        for item in declared_findings
    ):
        findings.append(
            _finding(
                "source-unsafe-review-pass",
                "Source manifest is passed with an unresolved blocking review finding",
                severity="critical",
            )
        )

    deterministic_sidecars = dict(sidecars)
    deterministic_sidecars["review_receipts"] = []
    deterministic_sidecars["advanced_findings"] = review_advanced_sidecars(
        deterministic_sidecars
    )
    deterministic_review = review_manifest(
        manifest,
        manifest_path.parent,
        sidecars=deterministic_sidecars,
    )
    for item in deterministic_review["findings"]:
        findings.append(
            _finding(
                f"source-{item['code']}",
                item["message"],
                severity=item.get("severity", "major"),
            )
        )

    artifact_records = [
        item for item in manifest.get("artifacts", []) if isinstance(item, Mapping)
    ]
    review_metadata_paths = {
        str(item["path"])
        for item in artifact_records
        if str(item.get("kind")) in REVIEW_RECEIPT_KINDS | REVIEW_PACKET_KINDS
    }
    packets_by_fingerprint: dict[str, dict[str, Any]] = {}
    for item in artifact_records:
        if str(item.get("kind")) not in REVIEW_PACKET_KINDS:
            continue
        packet_path = manifest_path.parent / str(item["path"])
        try:
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
            if not isinstance(packet, dict):
                raise ValueError("review packet must be a JSON object")
            validate_review_packet(packet)
        except (json.JSONDecodeError, OSError, UnicodeDecodeError, ValueError) as error:
            findings.append(
                _finding(
                    "source-review-packet-invalid",
                    f"Source review packet is invalid: {error}",
                )
            )
            continue
        packets_by_fingerprint[str(packet["fingerprint"])] = packet

    receipts = sidecars.get("review_receipts", [])
    eligible = [
        receipt
        for receipt in receipts
        if receipt.get("status") == "passed" and receipt.get("independent") is True
    ]
    if not eligible:
        findings.append(
            _finding(
                "source-review-receipt-missing",
                "Review-ready manuscript requires a passed independent source review receipt",
            )
        )
        return source_claim_ids

    source_hashes = {
        str(item["path"]): str(item["sha256"]).lower()
        for item in manifest.get("artifacts", [])
        if isinstance(item, Mapping)
    }
    required_artifacts = {
        str(item["path"])
        for item in manifest.get("artifacts", [])
        if isinstance(item, Mapping)
        and str(item.get("kind")) not in REVIEW_RECEIPT_KINDS | REVIEW_PACKET_KINDS
    }
    covered = False
    candidate_findings: list[dict[str, str]] = []
    for receipt in eligible:
        receipt_findings = review_receipt_findings(receipt, source_hashes)
        receipt_findings.extend(_review_receipt_contract_findings(receipt))
        missing_modes = sorted(
            REQUIRED_SUBMISSION_REVIEW_MODES
            - set(map(str, receipt.get("review_modes", [])))
        )
        if missing_modes:
            receipt_findings.append(
                {
                    "code": "incomplete-review-mode-coverage",
                    "severity": "major",
                    "message": "Source review receipt omits mandatory modes: "
                    + ", ".join(missing_modes),
                }
            )
        packet = packets_by_fingerprint.get(str(receipt.get("packet_fingerprint", "")))
        if (
            packet is None
            or receipt.get("review_task_id") != packet.get("review_task_id")
        ):
            receipt_findings.append(
                {
                    "code": "review-packet-missing",
                    "severity": "major",
                    "message": "Source review receipt is not linked to a valid review packet.",
                }
            )
        else:
            receipt_modes = set(map(str, receipt.get("review_modes", [])))
            packet_modes = set(map(str, packet.get("review_modes", [])))
            if not receipt_modes <= packet_modes:
                receipt_findings.append(
                    {
                        "code": "review-packet-mode-mismatch",
                        "severity": "major",
                        "message": "Source review receipt claims modes outside its linked packet.",
                    }
                )
            try:
                current_packet = build_review_packet(
                    manifest_path,
                    review_modes=list(packet["review_modes"]),
                    independent_required=bool(packet["independent_required"]),
                    review_questions=list(packet["review_questions"]),
                    created_at=str(packet["created_at"]),
                )
            except (OSError, ValueError) as error:
                receipt_findings.append(
                    {
                        "code": "review-packet-invalid",
                        "severity": "major",
                        "message": f"Could not reconstruct source review scope: {error}",
                    }
                )
            else:
                if _review_packet_scope(packet, review_metadata_paths) != _review_packet_scope(
                    current_packet,
                    review_metadata_paths,
                ):
                    receipt_findings.append(
                        {
                            "code": "review-packet-stale",
                            "severity": "major",
                            "message": "Source manifest semantics changed after independent review.",
                        }
                    )
        covered_artifacts = {str(item["path"]) for item in receipt["covered_artifacts"]}
        covered_claims = set(map(str, receipt.get("covered_claim_ids", [])))
        if (
            not receipt_findings
            and required_artifacts <= covered_artifacts
            and source_claim_ids <= covered_claims
        ):
            covered = True
        candidate_findings.extend(receipt_findings)
    if not covered:
        for item in candidate_findings:
            findings.append(
                _finding(
                    f"source-{item['code']}",
                    item["message"],
                    severity=item.get("severity", "major"),
                )
            )
        findings.append(
            _finding(
                "source-review-coverage-incomplete",
                "Source review receipt does not cover every source artifact and claim",
            )
        )
    return source_claim_ids


def _validate_submission_review(
    root: Path,
    review: object,
    listed_paths: set[str],
    current_hashes: Mapping[str, str],
    material_claim_ids: set[str],
    findings: list[dict[str, str]],
) -> None:
    if not isinstance(review, Mapping):
        findings.append(_finding("submission-review-invalid", "Submission review must be an object"))
        return
    if review.get("status") != "passed":
        findings.append(_finding("passed-review-required", "submission-ready requires a passed review"))
    declared_modes = review.get("required_modes")
    if not isinstance(declared_modes, list) or not declared_modes or not all(
        isinstance(item, str) and item for item in declared_modes
    ):
        findings.append(
            _finding("submission-review-modes-invalid", "submission-ready requires review modes")
        )
        declared_mode_set: set[str] = set()
    else:
        declared_mode_set = set(declared_modes)
    missing_declared_modes = sorted(REQUIRED_SUBMISSION_REVIEW_MODES - declared_mode_set)
    if missing_declared_modes:
        findings.append(
            _finding(
                "incomplete-review-mode-coverage",
                "Submission review declaration omits mandatory modes: "
                + ", ".join(missing_declared_modes),
            )
        )
    receipt_ref = review.get("receipt")
    if not _check_file_ref(
        root,
        receipt_ref,
        findings,
        code="review-receipt-mismatch",
        label="review receipt",
    ):
        return
    assert isinstance(receipt_ref, Mapping)
    receipt_path = str(receipt_ref["path"])
    try:
        receipt = json.loads((root / receipt_path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as error:
        findings.append(_finding("invalid-review-receipt", f"Could not read review receipt: {error}"))
        return
    if not isinstance(receipt, dict):
        findings.append(_finding("invalid-review-receipt", "Review receipt must be a JSON object"))
        return
    receipt_findings = review_receipt_findings(receipt, current_hashes)
    receipt_findings.extend(_review_receipt_contract_findings(receipt))
    for item in receipt_findings:
        findings.append(
            _finding(item["code"], item["message"], severity=item.get("severity", "major"))
        )
    if any(item["code"] == "invalid-review-receipt" for item in receipt_findings):
        return
    if receipt.get("status") != "passed":
        findings.append(_finding("review-receipt-not-passed", "Review receipt is not passed"))
    if receipt.get("independent") is not True:
        findings.append(_finding("review-not-independent", "Submission review is not independent"))
    required_modes = REQUIRED_SUBMISSION_REVIEW_MODES | declared_mode_set
    missing_modes = sorted(required_modes - set(map(str, receipt.get("review_modes", []))))
    if missing_modes:
        findings.append(
            _finding(
                "incomplete-review-mode-coverage",
                f"Review receipt omits required modes: {', '.join(missing_modes)}",
            )
        )
    covered_paths = {str(item["path"]) for item in receipt.get("covered_artifacts", [])}
    missing_paths = sorted((listed_paths - {receipt_path}) - covered_paths)
    if missing_paths:
        findings.append(
            _finding(
                "incomplete-review-artifact-coverage",
                f"Review receipt omits package files: {', '.join(missing_paths)}",
            )
        )
    covered_claims = set(map(str, receipt.get("covered_claim_ids", [])))
    missing_claims = sorted(material_claim_ids - covered_claims)
    if missing_claims:
        findings.append(
            _finding(
                "incomplete-review-claim-coverage",
                f"Review receipt omits material claims: {', '.join(missing_claims)}",
            )
        )


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
    source_manifest_record: object = None
    reporting_guideline = ""
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

        reporting_guideline = str(contract.get("reporting_guideline", "")).strip()
        if not reporting_guideline:
            findings.append(
                _finding(
                    "reporting-guideline-invalid",
                    "manuscript contract requires a reporting guideline or explicit 'none'",
                )
            )

        source_manifest_record = contract.get("source_manifest")
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
    submission_review: object = None
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
        submission_review = submission.get("review")
        if not isinstance(submission_review, Mapping):
            findings.append(_finding("submission-review-invalid", "Submission review must be an object"))

    required_listed = REQUIRED_FILES - {"submission-package.json"}
    for name in sorted(required_listed - listed_paths):
        findings.append(_finding("submission-file-unlisted", f"Required file is not listed: {name}"))
    actual_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
        and path.relative_to(root).as_posix() != "submission-package.json"
    }
    for name in sorted(actual_paths - listed_paths):
        findings.append(_finding("submission-file-unlisted", f"Package file is not listed: {name}"))
    current_hashes = {
        relative: _sha256(root / relative)
        for relative in listed_paths
        if (root / relative).is_file()
        and (root / relative).resolve().is_relative_to(root)
    }

    source_claim_ids = _validate_source_bundle(
        root,
        source_manifest_record,
        package_status,
        findings,
    )

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
    citation_support_by_id: dict[str, set[str]] = {}
    claim_ids: set[str] = set()
    material_claim_ids: set[str] = set()
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
            supports_claim_ids = citation.get("supports_claim_ids")
            if not isinstance(supports_claim_ids, list) or not all(
                isinstance(item, str) and item for item in supports_claim_ids
            ):
                findings.append(
                    _finding(
                        "citation-support-invalid",
                        f"{citation_id} supports_claim_ids must be a string list",
                    )
                )
                citation_support_by_id[citation_id] = set()
            else:
                citation_support_by_id[citation_id] = set(supports_claim_ids)
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
            material = claim.get("material") is True
            if material:
                material_claim_ids.add(claim_id)
                source_claim_id = str(claim.get("source_claim_id", "")).strip()
                if source_claim_ids is not None and source_claim_id not in source_claim_ids:
                    findings.append(
                        _finding(
                            "source-claim-missing",
                            f"{claim_id} references missing source claim {source_claim_id or '<empty>'}",
                        )
                    )
                if (
                    package_status in {"review-ready", "submission-ready"}
                    and status in UNRESOLVED_CLAIM_STATUSES
                ):
                    findings.append(
                        _finding(
                            "unresolved-claim-for-review-ready",
                            f"Material claim {claim_id} remains {status}",
                        )
                    )
            evidence_refs = claim.get("evidence_refs")
            citation_ids = claim.get("citation_ids")
            if (
                not isinstance(evidence_refs, list)
                or not isinstance(citation_ids, list)
                or not all(isinstance(item, str) and item for item in citation_ids)
            ):
                findings.append(_finding("claim-support-invalid", f"{claim_id} support fields must be lists"))
                continue
            if material and status == "supported" and not evidence_refs and not citation_ids:
                findings.append(
                    _finding("unsupported-material-claim", f"{claim_id} has no evidence or citation support")
                )
            locator = str(claim.get("manuscript_locator", "")).strip()
            segment, locator_error = _claim_segment(manuscript, locator) if locator else (None, "missing")
            if locator_error is not None:
                findings.append(
                    _finding(
                        "claim-locator-missing" if locator_error == "missing" else "claim-locator-ambiguous",
                        f"{claim_id} locator is {locator_error} in manuscript.md",
                    )
                )
            claim_text = str(claim.get("text", "")).strip()
            if not claim_text or segment is None or claim_text not in segment:
                findings.append(
                    _finding(
                        "claim-text-mismatch",
                        f"{claim_id} exact text is absent from its manuscript locator",
                    )
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
                elif claim_id not in citation_support_by_id[citation_id]:
                    findings.append(
                        _finding(
                            "citation-claim-mismatch",
                            f"{citation_id} is not verified for attributed claim {claim_id}",
                        )
                    )
                if segment is not None and re.search(
                    r"(?<!\w)@" + re.escape(citation_id) + r"(?![\w.:+/-])",
                    segment,
                ) is None:
                    findings.append(
                        _finding(
                            "citation-marker-missing",
                            f"{claim_id} locator does not contain citation marker @{citation_id}",
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
                if not text or segment is None or text not in segment:
                    findings.append(
                        _finding(
                            "reported-value-not-in-manuscript",
                            f"Reported value for {claim_id} is not present verbatim in manuscript.md",
                        )
                    )
                valid_evidence = _check_file_ref(
                    root,
                    {
                        "path": value.get("artifact_path"),
                        "sha256": value.get("artifact_sha256"),
                    },
                    findings,
                    code="reported-value-evidence-mismatch",
                    label=f"reported value for {claim_id}",
                )
                locator_value = value.get("locator")
                if not isinstance(locator_value, str):
                    findings.append(
                        _finding(
                            "reported-value-locator-invalid",
                            f"Reported value for {claim_id} has no evidence locator",
                        )
                    )
                elif valid_evidence:
                    artifact_path = root / str(value["artifact_path"])
                    if artifact_path.suffix.lower() == ".json":
                        try:
                            artifact_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
                            resolved_value = _resolve_json_pointer(artifact_payload, locator_value)
                        except (
                            json.JSONDecodeError,
                            OSError,
                            UnicodeDecodeError,
                            ValueError,
                        ) as error:
                            findings.append(
                                _finding(
                                    "reported-value-locator-invalid",
                                    f"Reported value for {claim_id} has an invalid JSON locator: {error}",
                                )
                            )
                        else:
                            if not isinstance(resolved_value, (str, int, float, bool, type(None))):
                                findings.append(
                                    _finding(
                                        "reported-value-locator-nonscalar",
                                        f"Reported value for {claim_id} must resolve to a JSON scalar",
                                    )
                                )
                            elif not _scalar_appears_in_text(resolved_value, text):
                                findings.append(
                                    _finding(
                                        "reported-value-content-mismatch",
                                        f"Reported value for {claim_id} does not match its JSON locator",
                                    )
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
        checklist_guideline = str(checklist.get("guideline", "")).strip()
        if reporting_guideline and checklist_guideline != reporting_guideline:
            findings.append(
                _finding(
                    "reporting-guideline-mismatch",
                    "Checklist guideline does not match manuscript contract",
                )
            )
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

    if package_status == "submission-ready":
        _validate_submission_review(
            root,
            submission_review,
            listed_paths,
            current_hashes,
            material_claim_ids,
            findings,
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
        "validation_method": "checked local package validator",
        "status": "tested",
        "limitations": ["This deterministic acceptance fixture is not an empirical scientific result."],
    }
    result_path = root / "source" / "result.json"
    _write_json(result_path, source_result)
    source_manifest = {
        "schema_version": 1,
        "run_id": "manuscript-source-fixture",
        "question": "Does the deterministic fixture preserve manuscript evidence identity?",
        "plan": [
            {
                "id": "fixture-analysis",
                "description": "Record one deterministic value and review its identity.",
                "status": "completed",
            }
        ],
        "inputs": [],
        "code": [],
        "executions": [],
        "environment": {"runtime": "deterministic repository fixture"},
        "artifacts": [
            {
                "path": "result.json",
                "kind": "fixture-result",
                "sha256": _sha256(result_path),
            }
        ],
        "claims": [
            {
                "id": "source-effect",
                "text": "The deterministic fixture records an estimate of 2.5 response units.",
                "evidence": ["result.json"],
            },
            {
                "id": "source-method",
                "text": "The fixture specifies a checked local package validator as its validation method.",
                "evidence": ["result.json"],
            },
            {
                "id": "source-limitation",
                "text": "The fixture is not an empirical scientific result.",
                "evidence": ["result.json"],
            },
        ],
        "review": {"status": "pending", "findings": []},
    }
    source_manifest_path = root / "source" / "manifest.json"
    _write_json(source_manifest_path, source_manifest)
    source_packet = build_review_packet(
        source_manifest_path,
        review_modes=["record", "source", "method"],
        created_at="2026-07-23T00:00:00Z",
    )
    source_packet_path = root / "source" / "review-packet.json"
    _write_json(source_packet_path, source_packet)
    source_review = finalize_review_response(
        source_packet,
        {
            "schema_version": 1,
            "review_task_id": source_packet["review_task_id"],
            "packet_fingerprint": source_packet["fingerprint"],
            "reviewer": "independent-fixture-reviewer",
            "independent": True,
            "review_modes": ["record", "source", "method"],
            "reviewed_claim_ids": list(source_packet["material_claim_ids"]),
            "reviewed_artifacts": [
                {"path": item["path"], "sha256": item["sha256"]}
                for item in source_packet["artifacts"]
            ],
            "findings": [],
            "limitations": ["Deterministic fixture review; not scientific peer review."],
            "status": "passed",
        },
    )
    source_review_path = root / "source" / "review-receipt.json"
    _write_json(source_review_path, source_review)
    source_manifest["artifacts"].extend(
        [
            {
                "path": "review-packet.json",
                "kind": "review-packet-v1",
                "sha256": _sha256(source_packet_path),
            },
            {
                "path": "review-receipt.json",
                "kind": "review-receipt-v2",
                "sha256": _sha256(source_review_path),
            },
        ]
    )
    source_manifest["review"] = {"status": "passed", "findings": []}
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
        "<!-- claim:M-003 -->\n"
        "The deterministic fixture specifies a checked local package validator as its validation "
        "method [@ref-method].\n\n"
        "## Results\n\n"
        "<!-- claim:M-001 -->\n"
        "The recorded effect estimate was 2.5 response units with a fixture interval of "
        "1.2 to 3.8 response units.\n\n"
        "## Discussion\n\n"
        "<!-- claim:M-002 -->\n"
        "This deterministic acceptance fixture is not an empirical scientific result.\n"
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
                "text": (
                    "The recorded effect estimate was 2.5 response units with a fixture interval "
                    "of 1.2 to 3.8 response units."
                ),
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
                "citation_ids": [],
                "reported_values": [
                    {
                        "text": "2.5 response units",
                        "artifact_path": "source/result.json",
                        "artifact_sha256": _sha256(result_path),
                        "locator": "/estimate",
                    },
                    {
                        "text": "1.2",
                        "artifact_path": "source/result.json",
                        "artifact_sha256": _sha256(result_path),
                        "locator": "/interval/0",
                    },
                    {
                        "text": "3.8 response units",
                        "artifact_path": "source/result.json",
                        "artifact_sha256": _sha256(result_path),
                        "locator": "/interval/1",
                    },
                ],
            },
            {
                "claim_id": "M-002",
                "source_claim_id": "source-limitation",
                "material": True,
                "text": "This deterministic acceptance fixture is not an empirical scientific result.",
                "inference_level": "operational",
                "status": "supported",
                "manuscript_locator": "claim:M-002",
                "evidence_refs": [
                    {
                        "path": "source/result.json",
                        "sha256": _sha256(result_path),
                        "locator": "/limitations/0",
                    }
                ],
                "citation_ids": [],
                "reported_values": [],
            },
            {
                "claim_id": "M-003",
                "source_claim_id": "source-method",
                "material": True,
                "text": (
                    "The deterministic fixture specifies a checked local package validator as its "
                    "validation method [@ref-method]."
                ),
                "inference_level": "operational",
                "status": "supported",
                "manuscript_locator": "claim:M-003",
                "evidence_refs": [
                    {
                        "path": "source/result.json",
                        "sha256": _sha256(result_path),
                        "locator": "/validation_method",
                    }
                ],
                "citation_ids": ["ref-method"],
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
                "supports_claim_ids": ["M-003"],
            }
        ],
    }
    _write_json(root / "claim-citation-map.json", trace)
    checklist = {
        "schema_version": 1,
        "manuscript_id": manuscript_id,
        "guideline": contract["reporting_guideline"],
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
        relative = path.relative_to(root).as_posix()
        if path.is_file() and relative != "submission-package.json":
            files.append(
                {
                    "path": relative,
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
