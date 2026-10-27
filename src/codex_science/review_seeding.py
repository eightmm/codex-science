"""Plant a known defect into a copy of a reviewed run bundle and score reviewer responses against it."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterable

from codex_science.run_packaging import refresh

SEVERITY_RANK = {"suggestion": 0, "minor": 1, "major": 2, "critical": 3}
MIN_SEVERITIES = ("major", "critical")
EVIDENCE_BOUNDARY = (
    "One response per variant is a detection record, not a sensitivity estimate; "
    "estimating reviewer sensitivity needs repeated responses over many seeded defects."
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def load_spec(path: Path) -> dict[str, Any]:
    spec = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(spec, dict) or spec.get("schema_version") != 1:
        raise ValueError("spec must be a JSON object with schema_version 1")
    for key in ("defect_id", "defect_class"):
        if not isinstance(spec.get(key), str) or not spec[key]:
            raise ValueError(f"spec {key} must be a non-empty string")
    if spec.get("expected_min_severity") not in MIN_SEVERITIES:
        raise ValueError("spec expected_min_severity must be 'major' or 'critical'")
    claim_id = spec.get("claim_id")
    if claim_id is not None and (not isinstance(claim_id, str) or not claim_id):
        raise ValueError("spec claim_id must be a non-empty string when present")
    if spec["defect_class"] == "control":
        if "find" in spec or "replace" in spec:
            raise ValueError("control spec must not set find/replace")
        return spec
    for key in ("file", "find", "replace"):
        if not isinstance(spec.get(key), str):
            raise ValueError(f"spec {key} must be a string")
    if not spec["file"] or not spec["find"]:
        raise ValueError("spec file and find must be non-empty")
    if spec["find"] == spec["replace"]:
        raise ValueError("spec replace must differ from find")
    return spec


def _target(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"spec file escapes the bundle: {relative}")
    target = root / candidate
    if target.is_symlink() or not _is_inside(target.resolve(), root.resolve()):
        raise ValueError(f"spec file escapes the bundle: {relative}")
    if not target.is_file():
        raise ValueError(f"spec file is not a regular file in the bundle: {relative}")
    return target


def _read_text(path: Path, relative: str) -> str:
    data = path.read_bytes()
    if b"\0" in data:
        raise ValueError(f"spec file is not a text artifact: {relative}")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"spec file is not a text artifact: {relative}") from error


def seed(bundle: Path, spec_path: Path, out: Path, key_path: Path) -> dict[str, Any]:
    bundle, out, key_path = bundle.resolve(), out.absolute(), key_path.absolute()
    out = out.parent.resolve() / out.name
    key_path = key_path.parent.resolve() / key_path.name
    if not bundle.is_dir():
        raise ValueError(f"bundle is not a directory: {bundle}")
    if out.exists() or out.is_symlink():
        raise ValueError(f"--out already exists: {out}")
    if _is_inside(out, bundle):
        raise ValueError("--out must not be inside --bundle")
    if _is_inside(key_path, out):
        raise ValueError("--key must not be inside --out; the answer key must not ship with the bundle")
    if key_path.exists() or key_path.is_symlink():
        raise ValueError(f"--key already exists: {key_path}")
    spec = load_spec(spec_path)
    control = spec["defect_class"] == "control"
    before = after = None
    updated = None
    if not control:
        source = _target(bundle, spec["file"])
        text = _read_text(source, spec["file"])
        occurrences = text.count(spec["find"])
        if occurrences != 1:
            raise ValueError(f"spec find must occur exactly once in {spec['file']}; found {occurrences}")
        before = _sha(source)
        updated = text.replace(spec["find"], spec["replace"])
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copytree(bundle, out, symlinks=True)
        if not control:
            target = _target(out, spec["file"])
            target.write_bytes(updated.encode("utf-8"))
            after = _sha(target)
        refresh(out, [], invalidate_review=True)
    except BaseException:
        shutil.rmtree(out, ignore_errors=True)
        raise
    key = {
        "schema_version": 1,
        "spec": spec,
        "file_sha256_before": before,
        "file_sha256_after": after,
        "out": str(out),
    }
    key_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=key_path.parent, prefix=".key-", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(key, indent=2, sort_keys=True) + "\n")
        os.replace(temporary, key_path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        shutil.rmtree(out, ignore_errors=True)
        raise
    return key


def _findings(response: Any) -> list[dict[str, Any]]:
    findings = response.get("findings") if isinstance(response, dict) else None
    if not isinstance(findings, list) or not all(isinstance(item, dict) for item in findings):
        raise ValueError("response must be a JSON object with a findings list of objects")
    return findings


def _rank(finding: dict[str, Any]) -> int:
    return SEVERITY_RANK.get(str(finding.get("severity", "")).lower(), -1)


def _matches(finding: dict[str, Any], spec: dict[str, Any]) -> bool:
    claim_id = spec.get("claim_id")
    if claim_id is not None and finding.get("affected_claim_id") == claim_id:
        return True
    evidence = finding.get("evidence")
    if isinstance(evidence, list):
        return any(isinstance(item, dict) and item.get("artifact_path") == spec["file"] for item in evidence)
    return False


def score_response(key: dict[str, Any], response: Any) -> dict[str, Any]:
    spec = key["spec"]
    findings = _findings(response)
    ids = lambda items: [str(item.get("id", item.get("code", index))) for index, item in items]
    indexed = list(enumerate(findings))
    if spec["defect_class"] == "control":
        serious = [(i, f) for i, f in indexed if _rank(f) >= SEVERITY_RANK["major"]]
        return {"defect_id": spec["defect_id"], "defect_class": "control",
                "false_positive": bool(serious), "serious_finding_ids": ids(serious)}
    matched = [(i, f) for i, f in indexed if _matches(f, spec)]
    threshold = SEVERITY_RANK[spec["expected_min_severity"]]
    caught = [(i, f) for i, f in matched if _rank(f) >= threshold]
    return {"defect_id": spec["defect_id"], "defect_class": spec["defect_class"],
            "caught": bool(caught), "caught_any_severity": bool(matched),
            "matched_finding_ids": ids(caught), "matched_any_severity_finding_ids": ids(matched)}


def score(key_path: Path, responses: Iterable[Path]) -> dict[str, Any]:
    key = json.loads(key_path.read_text(encoding="utf-8"))
    if not isinstance(key, dict) or not isinstance(key.get("spec"), dict):
        raise ValueError("key must be a seed key JSON object")
    if key["spec"].get("defect_class") != "control" and not isinstance(key["spec"].get("file"), str):
        raise ValueError("key spec is missing file")
    results = []
    for path in responses:
        result = score_response(key, json.loads(path.read_text(encoding="utf-8")))
        results.append({"response": str(path), **result})
    if not results:
        raise ValueError("at least one response is required")
    return {"evidence_boundary": EVIDENCE_BOUNDARY, "results": results}
