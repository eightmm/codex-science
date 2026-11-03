"""Read-only validation of pack-local, public variant evidence dossiers."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path, PurePosixPath
from typing import Any

from codex_science.cli_io import load_json_object
from codex_science.connector_contract import replay_snapshot


STAGES = ("01-normalize", "02-retrieve", "03-reconcile", "04-bound-claims", "05-review-handoff")
SOURCES = {"clinvar", "gnomad", "dbsnp", "gwas_catalog", "ensembl"}
BOUNDARIES = (
    "Evidence only; no diagnosis or clinical recommendation.",
    "Association is never causality.",
    "Numerical agreement is never physical or clinical validity.",
    "Absence of a record is unavailable, never negative evidence.",
    "Review approval is never truth; preserve failed controls and negative results.",
)


def _refuse(code: str, detail: str) -> None:
    raise ValueError(f"{code}: {detail}")


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _refuse("malformed-record", f"{label} must be an object")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _refuse("missing-field", f"{label} must be non-empty text")
    return value


def _items(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list) or not value:
        _refuse("malformed-record", f"{label} must be a non-empty list")
    return value


def _load(path: Path, schema: str | None = None) -> dict[str, Any]:
    try:
        value = load_json_object(path)
    except (OSError, ValueError) as error:
        _refuse("invalid-json", str(error))
    if schema is not None and value.get("schema") != schema:
        _refuse("schema-mismatch", f"expected {schema}")
    return value


def _linked(root: Path, reference: Any) -> Path:
    reference = _object(reference, "artifact reference")
    relative = PurePosixPath(_text(reference.get("path"), "artifact path"))
    if relative.is_absolute() or ".." in relative.parts or "\\" in str(relative):
        _refuse("unsafe-artifact-path", "artifact path must stay in the dossier")
    candidate = root / relative
    if any(part.is_symlink() for part in (candidate, *candidate.parents) if part.is_relative_to(root)):
        _refuse("unsafe-artifact-path", "artifact symlinks are refused")
    path = candidate.resolve()
    if not path.is_relative_to(root) or not path.is_file():
        _refuse("unsafe-artifact-path", "artifact must be a regular file inside the dossier")
    digest = reference.get("sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        _refuse("artifact-hash-mismatch", "artifact sha256 must be a lowercase SHA-256")
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        _refuse("artifact-hash-mismatch", f"artifact hash does not match: {relative}")
    return path


def _identity(raw: Any) -> dict[str, Any]:
    identity = _object(raw, "variant identity")
    for key in ("genome_build", "chromosome", "ref", "alt", "strand", "transcript"):
        _text(identity.get(key), f"identity.{key}")
    if type(identity.get("position")) is not int or identity["position"] < 1:
        _refuse("invalid-identity", "position must be a positive integer")
    if identity["strand"] not in ("+", "-"):
        _refuse("invalid-identity", "strand must be + or -")
    if any(not re.fullmatch(r"[ACGT]+", identity[key]) for key in ("ref", "alt")):
        _refuse("invalid-identity", "REF and ALT must be explicit uppercase DNA alleles")
    if identity["ref"] == identity["alt"]:
        _refuse("invalid-identity", "REF and ALT must differ")
    return identity


def _pointer(document: Any, pointer: Any) -> Any:
    pointer = _text(pointer, "identity pointer")
    if not pointer.startswith("/"):
        _refuse("invalid-identity-pointer", "use a JSON pointer into the complete snapshot")
    value = document
    try:
        for component in pointer[1:].split("/"):
            component = component.replace("~1", "/").replace("~0", "~")
            value = value[int(component)] if isinstance(value, list) else value[component]
    except (KeyError, IndexError, TypeError, ValueError):
        _refuse("invalid-identity-pointer", "identity pointer does not resolve")
    return value


def _aligned(canonical: dict[str, Any], observed: dict[str, Any], operation: Any) -> None:
    if observed["genome_build"] != canonical["genome_build"]:
        _refuse("genome-build-mismatch", "source and normalized genome builds differ; do not pool")
    transformed = dict(observed)
    if operation == "reverse-complement":
        for field in ("ref", "alt"):
            transformed[field] = observed[field].translate(str.maketrans("ACGT", "TGCA"))[::-1]
        transformed["strand"] = "+" if observed["strand"] == "-" else "-"
    elif operation != "identity":
        _refuse("unreconciled-allele-strand", "only explicit identity or reverse-complement mappings are accepted")
    if any(transformed[field] != canonical[field] for field in ("chromosome", "position", "ref", "alt", "strand", "transcript")):
        _refuse("unreconciled-allele-strand", "allele, strand, locus or transcript is not reconciled")


def _sources(root: Path, ledger: dict[str, Any]) -> dict[str, Any]:
    canonical = _identity(ledger.get("identity"))
    normalized = _load(_linked(root, ledger.get("normalization_input")), "variant-identity-ledger-v1")
    if _identity(normalized.get("identity")) != canonical:
        _refuse("normalization-ledger-mismatch", "retrieval must retain the frozen normalization identity")
    if canonical["strand"] != "+":
        _refuse("invalid-identity", "normalized identity must use the forward strand")
    result: dict[str, Any] = {}
    for raw in _items(ledger.get("sources"), "identity sources"):
        item = _object(raw, "identity source")
        source = _text(item.get("source"), "source")
        if source not in SOURCES or source in result:
            _refuse("source-coverage", "require each planned public source exactly once")
        snapshot = _load(_linked(root, item.get("snapshot")))
        try:
            replay = replay_snapshot(snapshot)
        except (ValueError, TypeError, KeyError, RecursionError) as error:
            _refuse("invalid-connector-snapshot", str(error))
        if replay.request.source != source:
            _refuse("snapshot-source-mismatch", "snapshot request has a different source")
        if replay.records and item.get("record_id") is not None:
            record_id = _text(item.get("record_id"), "selected record ID")
            if record_id not in replay.receipt.returned_record_ids:
                _refuse("snapshot-record-mismatch", "selected record is absent from the snapshot")
            index = replay.receipt.returned_record_ids.index(record_id)
            pointer = _text(item.get("identity_pointer"), "identity pointer")
            if not pointer.startswith(f"/records/{index}/"):
                _refuse("snapshot-record-mismatch", "identity must come from the selected normalized record")
            observed = _identity(_pointer(snapshot, pointer))
            _aligned(canonical, observed, item.get("reconciliation"))
        elif item.get("record_id") is not None or item.get("identity_pointer") is not None:
            _refuse("snapshot-record-mismatch", "empty snapshots cannot supply an identity")
        result[source] = (item, replay)
    if set(result) != SOURCES:
        _refuse("source-coverage", "all five planned sources must be present, including unavailable ones")
    return result


def _rows(table: dict[str, Any], sources: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    for raw in _items(table.get("rows"), "evidence rows"):
        row = _object(raw, "evidence row")
        source = _text(row.get("source"), "row source")
        if source not in sources or source in result:
            _refuse("source-coverage", "evidence rows must match identity sources exactly once")
        item, replay = sources[source]
        if row.get("record_id") != item.get("record_id"):
            _refuse("snapshot-record-mismatch", "evidence row changed the selected record")
        status = row.get("status")
        if status not in ("observed", "negative", "unavailable"):
            _refuse("invalid-evidence-status", "use observed, negative or unavailable")
        if (not replay.records or replay.receipt.status != "complete") and status != "unavailable":
            _refuse("missing-record-not-negative", "no record or failed retrieval must be unavailable")
        if item.get("record_id") is None and status != "unavailable":
            _refuse("unverified-source-identity", "a source without a verified selected identity must remain unavailable")
        denominator = row.get("denominator")
        if type(denominator) is not int or denominator < 0 or (status != "unavailable" and denominator == 0):
            _refuse("missing-denominator", "require a nonnegative integer denominator; observed/negative require >0")
        _text(row.get("denominator_unit"), "denominator unit")
        controls = row.get("controls")
        if not isinstance(controls, dict) or set(controls) != {"positive", "negative"}:
            _refuse("missing-control", "require positive and negative control outcomes")
        if any(value not in ("passed", "failed", "unavailable") for value in controls.values()):
            _refuse("missing-control", "control outcomes must be passed, failed or unavailable")
        for field in ("cohort_groups", "dependency_groups"):
            groups = _items(row.get(field), field)
            for group in groups:
                _text(group, field)
        if row.get("evidence_type") not in ("identity", "annotation", "association", "population_frequency", "clinical_assertion"):
            _refuse("invalid-evidence-type", "unsupported evidence type")
        for field in ("uncertainty", "limitations", "rationale"):
            _text(row.get(field), field)
        result[source] = row
    if set(result) != set(sources):
        _refuse("source-coverage", "retain unavailable and negative rows")
    return result


def _claims(register: dict[str, Any], rows: dict[str, dict[str, Any]]) -> int:
    claims = _items(register.get("claims"), "bounded claims")
    seen = set()
    for raw in claims:
        claim = _object(raw, "bounded claim")
        claim_id = _text(claim.get("id"), "claim ID")
        if claim_id in seen:
            _refuse("duplicate-claim", "claim IDs must be unique")
        seen.add(claim_id)
        for field in ("text", "rationale", "falsifier", "uncertainty", "applicability"):
            _text(claim.get(field), f"claim {field}")
        if claim.get("kind") not in ("descriptive", "associational"):
            _refuse("claim-strength-exceeds-source", "no causality, clinical classification, diagnosis, recommendation or physical validity")
        if claim.get("basis") not in ("source_observation", "association", "population_frequency", "clinical_assertion"):
            _refuse("claim-strength-exceeds-source", "numerical agreement or review approval cannot establish truth")
        support = _items(claim.get("evidence_sources"), "claim evidence sources")
        if any(not isinstance(source, str) or source not in rows for source in support) or len(set(support)) != len(support):
            _refuse("invalid-claim-support", "support must name distinct retained source rows")
        evidence = [rows[source] for source in support]
        status = claim.get("status")
        if status not in ("supported", "contradicted", "inconclusive", "unavailable", "replicated"):
            _refuse("invalid-claim-status", "unsupported bounded claim status")
        if all(row["status"] == "unavailable" for row in evidence) and status != "unavailable":
            _refuse("missing-record-not-negative", "claims without available evidence must remain unavailable")
        if status in ("supported", "replicated"):
            if any(row["status"] != "observed" or any(value != "passed" for value in row["controls"].values()) for row in evidence):
                _refuse("failed-support-control", "supported claims require observed rows and passed controls")
        if claim["kind"] == "associational" and any(row["evidence_type"] != "association" for row in evidence):
            _refuse("claim-strength-exceeds-source", "association claims require association evidence")
        if claim["basis"] != "source_observation" and any(row["evidence_type"] != claim["basis"] for row in evidence):
            _refuse("claim-strength-exceeds-source", "claim basis must match source evidence type")
        if status == "replicated":
            groups = set()
            if len(evidence) < 2:
                _refuse("dependent-replication", "replication requires at least two independent sources")
            for row in evidence:
                current = {("cohort", group) for group in row["cohort_groups"]}
                current.update(("dependency", group) for group in row["dependency_groups"])
                if current & groups or any(group[1] == "unknown" for group in current):
                    _refuse("dependent-replication", "shared or unknown cohort/dependency groups cannot count as independent replication")
                groups.update(current)
    return len(claims)


def validate_variant_dossier(package: Path) -> dict[str, Any]:
    """Validate declared identities and evidence limits; never attest review or truth.

    No files are written. Callers must hold inputs stable during validation;
    immutable run handoffs belong to the coordinator's existing manifest.
    """
    root = Path(package).resolve()
    dossier = _load(root / "dossier.json", "variant-dossier-v1")
    if dossier.get("stage_ids") != list(STAGES):
        _refuse("stage-order", "require the five fixed ordered stages")
    if dossier.get("review_status") != "unreviewed":
        _refuse("self-reviewed-dossier", "only the independent coordinator can attest review")
    if dossier.get("boundaries") != list(BOUNDARIES):
        _refuse("missing-evidence-boundary", "require the evidence-only boundaries verbatim")
    ledger = _load(_linked(root, dossier.get("identity_ledger")), "variant-identity-ledger-v1")
    table = _load(_linked(root, dossier.get("evidence_table")), "variant-source-evidence-v1")
    claims = _load(_linked(root, dossier.get("bounded_claims")), "variant-bounded-claims-v1")
    sources = _sources(root, ledger)
    rows = _rows(table, sources)
    count = _claims(claims, rows)
    return {"schema": "variant-dossier-validation-v1", "status": "passed", "review_status": "unreviewed",
            "source_count": len(sources), "claim_count": count,
            "limitations": ["Checks declared links and structured claims; independent source and method review remains required."]}
