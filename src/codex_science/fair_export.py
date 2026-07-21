"""Portable FAIR-oriented exports from a validated Codex Science run.

The exporters produce conservative RO-Crate-, W3C PROV-, and scientific-BOM
records. They do not claim formal certification, regulatory compliance, or
portability of bytes that are not included in the source bundle.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from codex_science.artifact_store import describe_directory, stream_sha256
from codex_science.artifacts import validate_bundle


RO_CRATE_CONTEXT = "https://w3id.org/ro/crate/1.1/context"
PROV_CONTEXT = "https://www.w3.org/ns/prov#"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _media_type(path: str, record: Mapping[str, Any]) -> str:
    if record.get("media_type"):
        return str(record["media_type"])
    guessed, _encoding = mimetypes.guess_type(path)
    return guessed or "application/octet-stream"


def _artifact_entity(record: Mapping[str, Any]) -> dict[str, Any]:
    path = str(record["path"])
    entity = {
        "@id": path,
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


def build_ro_crate(manifest: Mapping[str, Any], *, exported_at: str) -> dict[str, Any]:
    run_id = str(manifest["run_id"])
    artifacts = [_artifact_entity(item) for item in manifest.get("artifacts", []) if isinstance(item, Mapping)]
    root = {
        "@id": "./",
        "@type": "Dataset",
        "name": f"Codex Science run {run_id}",
        "description": str(manifest.get("question", "")),
        "dateModified": exported_at,
        "hasPart": [{"@id": item["@id"]} for item in artifacts],
        "mainEntity": {"@id": "manifest.json"},
        "conformsTo": [
            {"@id": "https://w3id.org/ro/crate/1.1"},
            {"@id": "https://github.com/eightmm/codex-science"}
        ],
        "reviewStatus": str(manifest.get("review", {}).get("status", "unknown")),
    }
    manifest_entity = {
        "@id": "manifest.json",
        "@type": "File",
        "name": "Codex Science artifact manifest",
        "encodingFormat": "application/json",
        "about": {"@id": "./"},
    }
    claims = []
    for claim in manifest.get("claims", []):
        if not isinstance(claim, Mapping) or not claim.get("id"):
            continue
        claim_id = f"#claim-{claim['id']}"
        claims.append({
            "@id": claim_id,
            "@type": "CreativeWork",
            "identifier": str(claim["id"]),
            "text": str(claim.get("text", "")),
            "citation": [{"@id": str(item)} for item in claim.get("evidence", [])],
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


def build_prov(manifest: Mapping[str, Any], *, exported_at: str) -> dict[str, Any]:
    run_id = str(manifest["run_id"])
    entities: dict[str, Any] = {}
    activities: dict[str, Any] = {}
    used: dict[str, Any] = {}
    generated: dict[str, Any] = {}
    for index, item in enumerate(manifest.get("inputs", [])):
        if not isinstance(item, Mapping):
            continue
        identifier = str(item.get("id") or item.get("path") or item.get("identifier") or f"input-{index}")
        entities[f"input:{identifier}"] = {"prov:type": "Input", "codex:record": dict(item)}
    for item in manifest.get("artifacts", []):
        if isinstance(item, Mapping):
            entities[f"artifact:{item['path']}"] = {"prov:type": "Artifact", "prov:label": str(item["path"]), "codex:sha256": str(item["sha256"]), "codex:kind": str(item.get("kind", "artifact"))}
    for index, execution in enumerate(manifest.get("executions", [])):
        if not isinstance(execution, Mapping):
            continue
        activity_id = f"execution:{execution.get('id', index)}"
        activities[activity_id] = {"prov:type": "Execution", "prov:label": str(execution.get("command", activity_id)), "codex:exitCode": execution.get("exit_code")}
        for entity_id in entities:
            if entity_id.startswith("input:"):
                used[f"used:{activity_id}:{entity_id}"] = {"prov:activity": activity_id, "prov:entity": entity_id}
    run_activity = f"run:{run_id}"
    activities[run_activity] = {"prov:type": "ScientificRun", "prov:label": str(manifest.get("question", run_id)), "prov:endedAtTime": exported_at, "codex:reviewStatus": str(manifest.get("review", {}).get("status", "unknown"))}
    for entity_id in entities:
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
        if isinstance(packages, list):
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


def export_run(manifest_path: Path, output_dir: Path, *, exported_at: str | None = None) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    sidecars = validate_bundle(manifest, manifest_path.parent)
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = exported_at or _now()
    ro_crate = build_ro_crate(manifest, exported_at=timestamp)
    prov = build_prov(manifest, exported_at=timestamp)
    bom = build_scientific_bom(manifest, sidecars, exported_at=timestamp)
    files = {
        "ro_crate": output_dir / "ro-crate-metadata.json",
        "prov": output_dir / "prov.json",
        "scientific_bom": output_dir / "scientific-bom.json",
    }
    _write_json(files["ro_crate"], ro_crate)
    _write_json(files["prov"], prov)
    _write_json(files["scientific_bom"], bom)
    exports = []
    for name, path in files.items():
        digest, size = stream_sha256(path)
        exports.append({"name": name, "path": path.name, "sha256": digest, "size_bytes": size})
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
    _write_json(output_dir / "export-receipt.json", receipt)
    return receipt
