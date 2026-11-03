"""Read-only validation of pack-local, public variant evidence dossiers."""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path, PurePosixPath
from typing import Any

from codex_science.connector_contract import replay_snapshot


STAGES = ("01-normalize", "02-retrieve", "03-reconcile", "04-bound-claims", "05-review-handoff")
SOURCES = {"clinvar", "gnomad", "dbsnp", "gwas_catalog", "ensembl"}
MAX_JSON_BYTES = 64 * 1024 * 1024
CLINICAL_WORDING = re.compile(
    r"\b(?:actionab(?:le|ility)|pathogenic(?:ity)?|benign|"
    r"treat(?:ment|ments|ed|ing|s)?|therap(?:y|ies|eutic(?:s|ally)?)|"
    r"recommend(?:ation|ations|ed|ing|s)?|prescri(?:be|bes|bed|bing|ption|ptions)|"
    r"diagnos(?:is|es|e|ed|ing|tic)|(?:start|initiate|use|administer)\s+"
    r"(?:drug|medication|chemotherapy|therapy|treatment))\b",
    re.IGNORECASE,
)
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


def _guard(condition, code, message):
    if not condition:
        raise ValueError(f"{code}: {message}")


def _signature(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _open_root(root):
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
    descriptor = os.open(root.anchor, flags)
    try:
        opened = os.fstat(descriptor)
        identities = [(opened.st_dev, opened.st_ino)]
        for part in root.parts[1:]:
            before = os.lstat(part, dir_fd=descriptor)
            _guard(stat.S_ISDIR(before.st_mode), "unsafe-artifact-path", "root ancestors must be real directories")
            child = os.open(part, flags, dir_fd=descriptor)
            try:
                opened = os.fstat(child)
                _guard(stat.S_ISDIR(opened.st_mode)
                       and (before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino),
                       "unsafe-artifact-path", "root ancestor changed during pinning")
            except BaseException:
                os.close(child)
                raise
            os.close(descriptor)
            descriptor = child
            identities.append((opened.st_dev, opened.st_ino))
        return descriptor, identities
    except BaseException:
        os.close(descriptor)
        raise


class _Bundle:
    def __init__(self, root):
        self.root = Path(os.path.abspath(root))
        self.fd, self.identities = _open_root(self.root)
        self.snapshots = {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        os.close(self.fd)

    def _read_bytes(self, relative):
        path = PurePosixPath(relative)
        opened_dirs = []
        try:
            directory = self.fd
            flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
            for part in path.parts[:-1]:
                before = os.lstat(part, dir_fd=directory)
                _guard(stat.S_ISDIR(before.st_mode), "unsafe-artifact-path", "symlinked artifact directory refused")
                directory = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
                opened_dirs.append(directory)
                opened = os.fstat(directory)
                _guard(stat.S_ISDIR(opened.st_mode)
                       and (before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino),
                       "unsafe-artifact-path", "artifact ancestor changed during open")
            before = os.lstat(path.name, dir_fd=directory)
            _guard(not stat.S_ISLNK(before.st_mode), "unsafe-artifact-path", "artifact symlinks are refused")
            _guard(stat.S_ISREG(before.st_mode), "unsafe-artifact-path", "input must be an available regular JSON file")
            _guard(before.st_size <= MAX_JSON_BYTES, "invalid-json", "input exceeds the inclusive 64 MiB JSON size bound")
            descriptor = os.open(path.name, flags, dir_fd=directory)
            with os.fdopen(descriptor, "rb") as stream:
                opened = os.fstat(stream.fileno())
                _guard(stat.S_ISREG(opened.st_mode), "unsafe-artifact-path", "input must be an available regular JSON file")
                _guard(opened.st_size <= MAX_JSON_BYTES, "invalid-json", "input exceeds the inclusive 64 MiB JSON size bound")
                _guard(_signature(before) == _signature(opened), "input-changed", "input changed during open")
                raw = stream.read(MAX_JSON_BYTES + 1)
                after = os.fstat(stream.fileno())
            _guard(len(raw) <= MAX_JSON_BYTES, "invalid-json", "input exceeds the inclusive 64 MiB JSON size bound")
            _guard(len(raw) == opened.st_size and _signature(opened) == _signature(after),
                   "input-changed", "input changed during bounded read")
            digest = hashlib.sha256(raw).hexdigest()
            snapshot = (_signature(after), digest)
            previous = self.snapshots.setdefault(str(path), snapshot)
            _guard(previous == snapshot, "input-changed", "input replaced or modified during validation")
            return raw
        except OSError as error:
            raise ValueError("unsafe-artifact-path: unavailable input or symlinked component") from error
        finally:
            for descriptor in reversed(opened_dirs):
                os.close(descriptor)

    def _check_root(self):
        descriptor, identities = _open_root(self.root)
        try:
            _guard(identities == self.identities, "input-changed", "bundle root replaced during validation")
        finally:
            os.close(descriptor)

    def unchanged(self):
        self._check_root()


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for name, value in items:
        if name in result:
            raise ValueError(f"duplicate JSON key: {name}")
        result[name] = value
    return result


def _load(raw: bytes, schema: str | None = None) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
        if not isinstance(value, dict):
            raise ValueError("input JSON must be an object")
    except (UnicodeError, ValueError, RecursionError) as error:
        _refuse("invalid-json", str(error))
    if schema is not None and value.get("schema") != schema:
        _refuse("schema-mismatch", f"expected {schema}")
    return value


def _linked(root: _Bundle, reference: Any) -> bytes:
    reference = _object(reference, "artifact reference")
    relative = PurePosixPath(_text(reference.get("path"), "artifact path"))
    if relative.is_absolute() or ".." in relative.parts or "\\" in str(relative):
        _refuse("unsafe-artifact-path", "artifact path must stay in the dossier")
    digest = reference.get("sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        _refuse("artifact-hash-mismatch", "artifact sha256 must be a lowercase SHA-256")
    raw = root._read_bytes(str(relative))
    if root.snapshots[str(relative)][1] != digest:
        _refuse("artifact-hash-mismatch", f"artifact hash does not match: {relative}")
    return raw


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


def _sources(root: _Bundle, ledger: dict[str, Any]) -> dict[str, Any]:
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
        if claim["basis"] == "clinical_assertion":
            quoted = re.fullmatch(r'Source assertion \(quoted only\): "([^"\r\n]+)"\.?', claim["text"])
            if claim["kind"] != "descriptive" or quoted is None or not quoted[1].strip():
                _refuse("claim-strength-exceeds-source", "clinical assertions require a descriptive quote-only statement")
        elif status in ("supported", "replicated") and CLINICAL_WORDING.search(claim["text"]):
            _refuse("claim-strength-exceeds-source", "supported claim text cannot assert clinical actionability, classification or treatment")
        if any(row["status"] == "unavailable" for row in evidence) and status != "unavailable":
            _refuse("missing-record-not-negative", "claims citing any unavailable evidence must remain unavailable")
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
    try:
        with _Bundle(package) as root:
            dossier = _load(root._read_bytes("dossier.json"), "variant-dossier-v1")
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
            root.unchanged()
            return {"schema": "variant-dossier-validation-v1", "status": "passed", "review_status": "unreviewed",
                    "source_count": len(sources), "claim_count": count,
                    "limitations": ["Checks declared links and structured claims; independent source and method review remains required."]}
    except OSError as error:
        _refuse("unsafe-artifact-path", "cannot pin or recheck bundle directory")
