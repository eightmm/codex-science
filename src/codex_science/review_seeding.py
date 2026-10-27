"""Plant a known defect into a copy of a reviewed run bundle and score reviewer responses against it."""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from codex_science.run_packaging import REVIEW_KINDS, _is_deterministic_review_file, _is_review_flow_file, refresh

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


def _refuse_symlink_components(root: Path, relative: str, label: str) -> None:
    current = root
    for component in Path(relative).parts:
        current = current / component
        try:
            current.lstat()
        except FileNotFoundError:
            break
        if current.is_symlink():
            raise ValueError(f"{label} traverses a symlink: {relative}")


def load_spec(path: Path) -> dict[str, Any]:
    spec = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(spec, dict) or spec.get("schema_version") != 1:
        raise ValueError("spec must be a JSON object with schema_version 1")
    for key in ("defect_id", "defect_class"):
        if not isinstance(spec.get(key), str) or not spec[key]:
            raise ValueError(f"spec {key} must be a non-empty string")
    if spec["defect_class"] != "control" and spec.get("expected_min_severity") not in MIN_SEVERITIES:
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
    _refuse_symlink_components(root, relative, "spec file")
    if target.is_symlink() or not _is_inside(target.resolve(), root.resolve()):
        raise ValueError(f"spec file escapes the bundle: {relative}")
    if not target.is_file():
        raise ValueError(f"spec file is not a regular file in the bundle: {relative}")
    return target


def _registered_paths(manifest: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(manifest, dict):
        for key, value in manifest.items():
            if key == "path" and isinstance(value, str):
                found.add(PurePosixPath(value).as_posix())
            else:
                found |= _registered_paths(value)
    elif isinstance(manifest, list):
        for item in manifest:
            found |= _registered_paths(item)
    return found


def _drop_target(root: Path, relative: str, registered: set[str], seeded: str | None) -> tuple[str, Path]:
    candidate = Path(relative)
    if not candidate.parts or candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"--drop escapes the bundle: {relative}")
    canonical = PurePosixPath(*candidate.parts)
    target = root / candidate
    _refuse_symlink_components(root, relative, "--drop")
    if target.is_symlink() or not _is_inside(target.resolve(), root.resolve()) or target.resolve() == root.resolve():
        raise ValueError(f"--drop escapes the bundle: {relative}")
    if not target.exists():
        raise ValueError(f"--drop does not exist in the bundle: {relative}")
    overlaps = lambda other: PurePosixPath(other) == canonical or canonical in PurePosixPath(other).parents
    registered_ancestor = any(PurePosixPath(path) in canonical.parents for path in registered)
    if "manifest.json" == canonical.as_posix() or registered_ancestor or any(overlaps(path) for path in registered):
        raise ValueError(f"--drop refused: {relative} is registered in the bundle manifest")
    if seeded is not None and overlaps(seeded):
        raise ValueError(f"--drop refused: {relative} contains the seeded file")
    return canonical.as_posix(), target


def _refuse_managed(root: Path, relative: str, manifest: Any) -> None:
    """Refuse seed targets that refresh() rewrites or archives, so the planted defect cannot be erased."""
    canonical = PurePosixPath(*Path(relative).parts)
    kinds = {}
    if isinstance(manifest, dict) and isinstance(manifest.get("artifacts"), list):
        kinds = {PurePosixPath(item["path"]).as_posix(): item.get("kind") for item in manifest["artifacts"]
                 if isinstance(item, dict) and isinstance(item.get("path"), str)}
    target = root / relative
    if (canonical.as_posix() == "manifest.json" or "review-rounds" in canonical.parts
            or kinds.get(canonical.as_posix()) in REVIEW_KINDS
            or _is_review_flow_file(target) or _is_deterministic_review_file(target)):
        raise ValueError(f"spec file is managed by the review flow and cannot be seeded: {relative}")


def _check_key_parent(key_path: Path) -> None:
    ancestor = key_path.parent
    while not ancestor.exists() and not ancestor.is_symlink():
        ancestor = ancestor.parent
    if not ancestor.is_dir():
        raise ValueError(f"--key parent is not a directory: {ancestor}")


def _read_text(path: Path, relative: str) -> str:
    data = path.read_bytes()
    if b"\0" in data:
        raise ValueError(f"spec file is not a text artifact: {relative}")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"spec file is not a text artifact: {relative}") from error


def seed(bundle: Path, spec_path: Path, out: Path, key_path: Path, drop: Iterable[str] = (),
         strip_review_history: bool = False) -> dict[str, Any]:
    bundle, out, key_path = bundle.resolve(), out.absolute(), key_path.absolute()
    out = out.parent.resolve() / out.name
    key_path = key_path.parent.resolve() / key_path.name
    if not bundle.is_dir():
        raise ValueError(f"bundle is not a directory: {bundle}")
    if out.exists() or out.is_symlink():
        raise ValueError(f"--out already exists: {out}")
    if _is_inside(out, bundle):
        raise ValueError("--out must not be inside --bundle")
    if _is_inside(key_path, bundle):
        raise ValueError("--key must not be inside --bundle; --bundle is never modified")
    if _is_inside(key_path, out):
        raise ValueError("--key must not be inside --out; the answer key must not ship with the bundle")
    if key_path.exists() or key_path.is_symlink():
        raise ValueError(f"--key already exists: {key_path}")
    _check_key_parent(key_path)
    spec = load_spec(spec_path)
    control = spec["defect_class"] == "control"
    before = after = None
    updated = None
    if not control:
        source = _target(bundle, spec["file"])
        manifest_path = bundle / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else None
        _refuse_managed(bundle, spec["file"], manifest)
        text = _read_text(source, spec["file"])
        occurrences = text.count(spec["find"])
        if occurrences != 1:
            raise ValueError(f"spec find must occur exactly once in {spec['file']}; found {occurrences}")
        before = _sha(source)
        updated = text.replace(spec["find"], spec["replace"])
    dropped: list[str] = []
    if drop:
        manifest_path = bundle / "manifest.json"
        if not manifest_path.is_file():
            raise ValueError("--drop needs a bundle manifest.json")
        registered = _registered_paths(json.loads(manifest_path.read_text(encoding="utf-8")))
        for relative in drop:
            canonical, _ = _drop_target(bundle, relative, registered, None if control else PurePosixPath(spec["file"]).as_posix())
            if canonical not in dropped:
                dropped.append(canonical)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        out.mkdir()
    except FileExistsError as error:
        raise ValueError(f"--out already exists: {out}") from error
    temporary = None
    key_created = False
    try:
        shutil.copytree(bundle, out, symlinks=True, dirs_exist_ok=True)
        for relative in dropped:
            _refuse_symlink_components(out, relative, "--drop")
            target = out / relative
            if target.is_dir() and not target.is_symlink():
                shutil.rmtree(target)
            elif target.exists() or target.is_symlink():
                target.unlink()
        if not control:
            target = _target(out, spec["file"])
            target.write_bytes(updated.encode("utf-8"))
            after = _sha(target)
        with contextlib.redirect_stdout(sys.stderr):
            refresh(out, [], invalidate_review=True)
        if not control:
            planted = out / spec["file"]
            if not planted.is_file() or _sha(planted) != after:
                raise ValueError(f"refresh altered the seeded file: {spec['file']}")
        if strip_review_history:
            history = out / "review-rounds"
            if history.is_symlink() or history.is_file():
                history.unlink()
            elif history.exists():
                shutil.rmtree(history)
        key = {
            "schema_version": 1,
            "spec": spec,
            "file_sha256_before": before,
            "file_sha256_after": after,
            "out": str(out),
            "dropped": dropped,
            "stripped_review_history": strip_review_history,
        }
        key_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(dir=key_path.parent, prefix=".key-", suffix=".tmp")
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(key, indent=2, sort_keys=True) + "\n")
        os.link(temporary, key_path)
        key_created = True
        temporary_path = Path(temporary)
        temporary_path.unlink()
        temporary = None
    except BaseException:
        if key_created:
            key_path.unlink(missing_ok=True)
        if temporary is not None:
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
