"""Portable FAIR-oriented exports from a validated Codex Science run.

The exporters produce conservative RO-Crate-, W3C PROV-, and scientific-BOM
records. They do not claim formal certification, regulatory compliance, or
portability of bytes that are not included in the source bundle.
"""

from __future__ import annotations

import errno
import hashlib
import json
import math
import mimetypes
import os
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping
from urllib.parse import quote

from codex_science.artifact_store import describe_directory, stream_sha256
from codex_science.artifacts import validate_bundle


RO_CRATE_CONTEXT = "https://w3id.org/ro/crate/1.1/context"
PROV_CONTEXT = "https://www.w3.org/ns/prov#"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("record contains text that is not valid UTF-8 (lone surrogate)") from None
    except ValueError:
        raise ValueError("record contains NaN or Infinity, which is not valid JSON") from None


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _unencodable(value: Any, pointer: str = "$") -> str | None:
    """Locate the first lone surrogate or non-finite number for error messages."""
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            return f"{pointer} (lone surrogate in {value[:60]!r})"
    elif isinstance(value, float) and not math.isfinite(value):
        return f"{pointer} ({value!r})"
    elif isinstance(value, Mapping):
        for key, item in value.items():
            found = _unencodable(key, f"{pointer}.<key {str(key)[:60]!r}>") or _unencodable(item, f"{pointer}.{key}")
            if found:
                return found
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found = _unencodable(item, f"{pointer}[{index}]")
            if found:
                return found
    return None


def _json_bytes(name: str, payload: Any) -> bytes:
    try:
        return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    except ValueError as error:
        where = _unencodable(payload)
        kind = ("text that is not valid UTF-8" if isinstance(error, UnicodeEncodeError)
                else "NaN or Infinity, which is not valid JSON")
        raise ValueError(f"{name} contains {kind}" + (f" at {where}" if where else "")) from None


def _write_json(path: Path, payload: Any) -> None:
    data = _json_bytes(path.name, payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation also refuses symlinks or aliases introduced after preflight.
    with path.open("xb") as stream:
        stream.write(data)


def _canonical_path(value: str) -> str:
    return PurePosixPath(value).as_posix()


def _quote(value: str, label: str, safe: str = "/") -> str:
    try:
        return quote(value, safe=safe)
    except UnicodeEncodeError:
        raise ValueError(f"{label} is not valid UTF-8: {value[:60]!r}") from None


def _claim_evidence(claim: Mapping[str, Any]) -> list[str]:
    evidence = claim.get("evidence", [])
    label = f"claim {str(claim.get('id'))[:60]!r}"
    if not isinstance(evidence, list):
        raise ValueError(f"{label} evidence must be a list of artifact path strings, not {type(evidence).__name__}")
    for item in evidence:
        if not isinstance(item, str):
            raise ValueError(f"{label} evidence entries must be artifact path strings: {item!r}")
    return evidence


def _resolve(path: Path, label: str) -> Path:
    """Resolve a path, labelling symlink loops on every supported Python version."""
    message = f"{label} has a symlink loop: {str(path)!r}"
    try:
        resolved = path.resolve()
    except RuntimeError:
        raise ValueError(message) from None
    try:
        os.stat(resolved)
    except OSError as error:
        if error.errno == errno.ELOOP:
            raise ValueError(message) from None
    return resolved


def _check_types(manifest: Mapping[str, Any]) -> None:
    artifacts = manifest.get("artifacts")
    if isinstance(artifacts, list):
        for index, item in enumerate(artifacts):
            if not isinstance(item, Mapping):
                continue
            for field in ("path", "kind", "descriptor_path"):
                if field in item and not isinstance(item[field], str) and not (field == "descriptor_path" and item[field] is None):
                    raise ValueError(f"artifact {index} {field} must be a string: {item[field]!r}")
    claims = manifest.get("claims")
    if isinstance(claims, list):
        for claim in claims:
            if isinstance(claim, Mapping):
                _claim_evidence(claim)


def _media_type(path: str, record: Mapping[str, Any]) -> str:
    if record.get("media_type"):
        return str(record["media_type"])
    guessed, _encoding = mimetypes.guess_type(path)
    return guessed or "application/octet-stream"


def _artifact_entity(record: Mapping[str, Any], reference: str) -> dict[str, Any]:
    path = str(record["path"])
    entity = {
        "@id": reference,
        "@type": "Dataset" if record.get("artifact_type") == "directory-tree" else "File",
        "name": path,
        "encodingFormat": _media_type(path, record),
        "sha256": str(record["sha256"]),
        "additionalType": str(record.get("kind", "artifact")),
    }
    for source, target in (("size_bytes", "contentSize"), ("artifact_type", "artifactType"), ("root_sha256", "merkleRoot"), ("entry_count", "entryCount")):
        if record.get(source) is not None:
            entity[target] = record[source]
    return entity


def build_ro_crate(
    manifest: Mapping[str, Any], *, exported_at: str,
    manifest_reference: str = "manifest.json",
    artifact_references: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    run_id = str(manifest["run_id"])
    references = artifact_references if artifact_references is not None else {
        _canonical_path(str(item["path"])): _quote(str(item["path"]), f"artifact path {str(item['path'])[:60]!r}")
        for item in manifest.get("artifacts", []) if isinstance(item, Mapping)
    }
    artifacts = [_artifact_entity(item, references[_canonical_path(str(item["path"]))])
                 for item in manifest.get("artifacts", []) if isinstance(item, Mapping)]
    root = {
        "@id": "./",
        "@type": "Dataset",
        "name": f"Codex Science run {run_id}",
        "description": str(manifest.get("question", "")),
        "dateModified": exported_at,
        "hasPart": [{"@id": item["@id"]} for item in artifacts],
        "mainEntity": {"@id": manifest_reference},
        "conformsTo": [
            {"@id": "https://w3id.org/ro/crate/1.1"},
            {"@id": "https://github.com/eightmm/codex-science"}
        ],
        "reviewStatus": str(manifest.get("review", {}).get("status", "unknown")),
    }
    manifest_entity = {
        "@id": manifest_reference,
        "@type": "File",
        "name": "Codex Science artifact manifest",
        "encodingFormat": "application/json",
        "about": {"@id": "./"},
    }
    claims = []
    for claim in manifest.get("claims", []):
        if not isinstance(claim, Mapping) or not claim.get("id"):
            continue
        claim_id = "#claim-" + _quote(str(claim["id"]), f"claim id {str(claim['id'])[:60]!r}")
        citations = []
        for item in _claim_evidence(claim):
            reference = references.get(_canonical_path(item))
            if reference is None:
                raise ValueError(f"claim {str(claim['id'])[:60]!r} evidence is not a listed artifact path: {item!r} "
                                 "(evidence entries must be manifest artifact paths, not identifiers)")
            citations.append({"@id": reference})
        claims.append({
            "@id": claim_id,
            "@type": "CreativeWork",
            "identifier": str(claim["id"]),
            "text": str(claim.get("text", "")),
            "citation": citations,
        })
    root["about"] = [{"@id": item["@id"]} for item in claims]
    return {
        "@context": RO_CRATE_CONTEXT,
        "@graph": [
            {"@id": "ro-crate-metadata.json", "@type": "CreativeWork", "about": {"@id": "./"}, "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"}},
            root,
            manifest_entity,
            *artifacts,
            *claims,
        ],
        "codexScienceBoundary": "This export is RO-Crate-oriented metadata over a validated local bundle. External or omitted bytes remain external and formal RO-Crate conformance is not certified by this exporter."
    }


def _identified_records(records: list[Any], kind: str) -> list[tuple[str, Mapping[str, Any]]]:
    explicit: set[str] = set()
    for record in records:
        if not isinstance(record, Mapping) or "id" not in record:
            continue
        value = record["id"]
        if (isinstance(value, bool) or not isinstance(value, (str, int))
                or not str(value).strip()):
            raise ValueError(f"invalid explicit {kind} id: {value!r}")
        identifier = str(value)
        if identifier in explicit:
            raise ValueError(f"duplicate explicit {kind} id: {identifier!r}")
        explicit.add(identifier)
    identified = []
    reserved = set(explicit)
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            continue
        if "id" in record:
            identifier = str(record["id"])
        else:
            fallback = (record.get("path") or record.get("identifier")) if kind == "input" else None
            identifier = str(fallback or (f"input-{index}" if kind == "input" else index))
            if identifier in reserved:
                identifier = f"@{kind}-{index}"
                while identifier in reserved:
                    identifier += ":"
        reserved.add(identifier)
        identified.append((identifier, record))
    return identified


def build_prov(manifest: Mapping[str, Any], *, exported_at: str) -> dict[str, Any]:
    run_id = str(manifest["run_id"])
    entities: dict[str, Any] = {}
    activities: dict[str, Any] = {}
    used: dict[str, Any] = {}
    generated: dict[str, Any] = {}
    for identifier, item in _identified_records(manifest.get("inputs", []), "input"):
        entities[f"input:{identifier}"] = {"prov:type": "Input", "codex:record": dict(item)}
    for item in manifest.get("artifacts", []):
        if isinstance(item, Mapping):
            entities[f"artifact:{item['path']}"] = {"prov:type": "Artifact", "prov:label": str(item["path"]), "codex:sha256": str(item["sha256"]), "codex:kind": str(item.get("kind", "artifact"))}
    for identifier, execution in _identified_records(manifest.get("executions", []), "execution"):
        activity_id = f"execution:{identifier}"
        activities[activity_id] = {"prov:type": "Execution", "prov:label": str(execution.get("command", activity_id)), "codex:exitCode": execution.get("exit_code")}
    run_activity = f"run:{run_id}"
    activities[run_activity] = {"prov:type": "ScientificRun", "prov:label": str(manifest.get("question", run_id)), "codex:reviewStatus": str(manifest.get("review", {}).get("status", "unknown"))}
    for entity_id in entities:
        # Manifest inputs establish run-level usage, not bindings to each command.
        if entity_id.startswith("input:"):
            used[f"used:{run_activity}:{entity_id}"] = {"prov:activity": run_activity, "prov:entity": entity_id}
        if entity_id.startswith("artifact:"):
            generated[f"generated:{entity_id}"] = {"prov:entity": entity_id, "prov:activity": run_activity}
    return {
        "prefix": {"prov": PROV_CONTEXT, "codex": "https://github.com/eightmm/codex-science#"},
        "entity": entities,
        "activity": activities,
        "used": used,
        "wasGeneratedBy": generated,
        "codexScienceBoundary": "This is a deterministic W3C-PROV-oriented export of recorded lineage. It does not authenticate agents or reconstruct omitted execution events."
    }


def build_scientific_bom(manifest: Mapping[str, Any], sidecars: Mapping[str, Any], *, exported_at: str) -> dict[str, Any]:
    components: list[dict[str, Any]] = []
    for index, item in enumerate(manifest.get("code", [])):
        if isinstance(item, Mapping):
            components.append({"component_type": "code", "id": str(item.get("path") or item.get("module") or f"code-{index}"), "record": dict(item)})
    environment = manifest.get("environment", {})
    if isinstance(environment, Mapping):
        for key in ("container_digest", "lockfile_sha256", "code_revision", "model_registry_sha256"):
            if environment.get(key) is not None:
                components.append({"component_type": key, "id": str(environment[key]), "record": {"value": environment[key]}})
        packages = environment.get("packages", [])
        if not isinstance(packages, list):
            raise ValueError(f"environment.packages must be a list, not {type(packages).__name__}")
        for index, package in enumerate(packages):
            components.append({"component_type": "package", "id": str(package if not isinstance(package, Mapping) else package.get("name", f"package-{index}")), "record": package})
    for index, item in enumerate(manifest.get("inputs", [])):
        if isinstance(item, Mapping):
            component_type = "dataset" if item.get("source") or item.get("identifier") else "input"
            components.append({"component_type": component_type, "id": str(item.get("id") or item.get("identifier") or item.get("path") or f"input-{index}"), "record": dict(item)})
    for receipt in sidecars.get("model_receipts_v2", []):
        if isinstance(receipt, Mapping):
            components.append({"component_type": "model-receipt", "id": str(receipt.get("model_id", "model")), "record": dict(receipt)})
    for record in manifest.get("artifacts", []):
        if isinstance(record, Mapping) and record.get("kind") in {"database-snapshot", "model-weight", "container", "license-bom"}:
            components.append({"component_type": str(record["kind"]), "id": str(record["path"]), "record": dict(record)})
    normalized = sorted(components, key=lambda item: (item["component_type"], item["id"], _sha(item["record"])))
    return {
        "schema_version": 1,
        "run_id": str(manifest["run_id"]),
        "generated_at": exported_at,
        "components": normalized,
        "component_count": len(normalized),
        "limitations": [
            "Only dependencies recorded in the manifest, environment, and recognized receipts are included.",
            "A missing license record is not evidence that reuse is permitted.",
            "Container, model, weight, database, and dataset identities remain source-specific."
        ],
        "evidence_boundary": "The scientific BOM supports dependency and license review; it is not a legal opinion, software vulnerability scan, or proof of complete transitive dependency capture."
    }


def _same_file(left: Path, right: Path) -> bool:
    return left == right or (left.exists() and right.exists() and os.path.samefile(left, right))


def export_run(
    manifest_path: Path, output_dir: Path, *, exported_at: str | None = None,
    receipt_path: Path | None = None,
) -> dict[str, Any]:
    """Export metadata and optional extra receipt after checking all destinations.

    Destinations must preserve the manifest, listed artifacts and their contents,
    and descriptor files, including symlink and hard-link aliases. The extra
    receipt must be outside the output directory and have no ancestor/descendant
    overlap with any export output. All destinations must be
    absent with no non-directory ancestors; unrelated output-directory files
    are preserved. Recorded local code and saved lane-output digests must match
    the bundle bytes. Preflight rejection creates no files.
    """
    manifest_path = _resolve(manifest_path, "manifest path")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    _check_types(manifest)
    _json_bytes("manifest", manifest)
    sidecars = validate_bundle(manifest, manifest_path.parent)
    if sidecars.get("digest_findings"):
        raise ValueError("Bundle digest mismatch: " + "; ".join(
            finding["message"] for finding in sidecars["digest_findings"]
        ))
    output_dir = _resolve(output_dir, "output directory")
    files = {
        "ro_crate": output_dir / "ro-crate-metadata.json",
        "prov": output_dir / "prov.json",
        "scientific_bom": output_dir / "scientific-bom.json",
    }
    receipt_paths = [output_dir / "export-receipt.json"]
    if receipt_path is not None:
        receipt_paths.append(receipt_path)
    protected_paths = {manifest_path}
    for item in manifest["artifacts"]:
        artifact_path = _resolve(manifest_path.parent / item["path"], f"artifact {item['path']!r}")
        protected_paths.add(artifact_path)
        if item.get("artifact_type") == "directory-tree":
            protected_paths.update(_resolve(path, "artifact tree entry") for path in artifact_path.rglob("*") if path.is_file())
        if item.get("descriptor_path") is not None:
            protected_paths.add(_resolve(manifest_path.parent / str(item["descriptor_path"]), "artifact descriptor"))
    existing_destination = None
    for destination in [*files.values(), *receipt_paths]:
        for ancestor in destination.parents:
            if (ancestor.exists() or ancestor.is_symlink()) and not ancestor.is_dir():
                raise ValueError(f"export destination has non-directory ancestor: {str(ancestor)!r}")
        resolved = _resolve(destination, "export destination")
        if any(path in resolved.parents or _same_file(path, resolved) for path in protected_paths):
            raise ValueError(f"export destination overlaps protected bundle path: {str(destination)!r}")
        if existing_destination is None and (destination.exists() or destination.is_symlink()):
            existing_destination = destination
    if receipt_path is not None:
        resolved_receipt = _resolve(receipt_path, "receipt destination")
        if resolved_receipt.is_dir():
            raise ValueError(f"receipt destination is an existing directory: {str(receipt_path)!r}")
        if any(_same_file(resolved_receipt, _resolve(path, "export destination")) for path in [*files.values(), receipt_paths[0]]):
            raise ValueError(f"receipt destination overlaps export output: {str(receipt_path)!r}")
        if any(resolved_receipt == path or resolved_receipt in path.parents or path in resolved_receipt.parents
               for path in (_resolve(destination, "export destination") for destination in [output_dir, *files.values(), receipt_paths[0]])):
            raise ValueError(f"receipt destination has ancestor/descendant overlap with export output: {str(receipt_path)!r}")
    if existing_destination is not None:
        if existing_destination == receipt_path:
            raise ValueError(f"receipt destination already exists: {str(existing_destination)!r}; "
                             "choose a fresh --receipt path or archive the old receipt explicitly")
        raise ValueError(f"export destination already exists: {str(existing_destination)!r}; "
                         "choose a new versioned output directory or archive the old export explicitly")
    timestamp = exported_at or _now()
    artifact_references = {
        _canonical_path(item["path"]): _quote(
            os.path.relpath(manifest_path.parent / item["path"], output_dir).replace(os.sep, "/"),
            f"artifact path {item['path'][:60]!r}")
        for item in manifest["artifacts"]
    }
    manifest_reference = _quote(os.path.relpath(manifest_path, output_dir).replace(os.sep, "/"),
                                f"manifest path {str(manifest_path)[:60]!r}")
    ro_crate = build_ro_crate(manifest, exported_at=timestamp,
                              manifest_reference=manifest_reference, artifact_references=artifact_references)
    prov = build_prov(manifest, exported_at=timestamp)
    bom = build_scientific_bom(manifest, sidecars, exported_at=timestamp)
    payloads = {"ro_crate": ro_crate, "prov": prov, "scientific_bom": bom}
    exports = []
    for name, path in files.items():
        # Encode every payload before any destination is opened.
        data = _json_bytes(path.name, payloads[name])
        exports.append({"name": name, "path": path.name, "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)})
    manifest_digest, _manifest_size = stream_sha256(manifest_path)
    receipt_material = {
        "schema_version": 1,
        "run_id": manifest["run_id"],
        "source_manifest_path": str(manifest_path),
        "source_manifest_sha256": manifest_digest,
        "generated_at": timestamp,
        "exports": exports,
        "status": "generated",
        "certified": False,
        "regulatory_compliance_claimed": False,
        "evidence_boundary": "The export packages validated recorded metadata. It does not certify RO-Crate, W3C PROV, regulatory, or legal compliance."
    }
    receipt = {**receipt_material, "fingerprint": _sha(receipt_material)}
    _json_bytes("export-receipt.json", receipt)
    for name, path in files.items():
        _write_json(path, payloads[name])
    for path in receipt_paths:
        _write_json(path, receipt)
    return receipt
