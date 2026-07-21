"""Local project-level evidence memory over immutable scientific run bundles.

The SQLite store is an index and decision ledger. A run manifest and its hashed
artifacts remain authoritative. Import, fork, compare, and merge-plan operations
never rewrite a run bundle.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterator, Mapping

from codex_science.artifact_store import stream_sha256
from codex_science.artifacts import validate_bundle
from codex_science.collaboration import diff_runs


SCHEMA_VERSION = 1
POLARITIES = {"supports", "contradicts", "qualifies", "neutral", "unavailable"}
BRANCH_STATUSES = {"active", "candidate", "merged", "abandoned"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _text(value: Any, label: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{label} is required")
    return text


def _sha(value: Any, label: str) -> str:
    text = _text(value, label).lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"{label} must be a SHA-256 digest")
    return text


def _relative(value: Any, label: str) -> str:
    text = _text(value, label)
    pure = PurePosixPath(text)
    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"{label} must be a safe relative path")
    return pure.as_posix()


def _json_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    payload = dict(value)
    try:
        json.dumps(payload, ensure_ascii=False)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be JSON-compatible") from error
    return payload


def _manifest_claims(manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item["id"]): dict(item) for item in manifest.get("claims", []) if isinstance(item, Mapping) and item.get("id")}


def _manifest_artifacts(manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item["path"]): dict(item) for item in manifest.get("artifacts", []) if isinstance(item, Mapping) and item.get("path")}


@dataclass(frozen=True)
class ImportedRun:
    project_id: str
    run_id: str
    branch_name: str
    parent_run_id: str | None
    manifest_path: str
    manifest_sha256: str
    review_status: str
    imported_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "run_id": self.run_id,
            "branch_name": self.branch_name,
            "parent_run_id": self.parent_run_id,
            "manifest_path": self.manifest_path,
            "manifest_sha256": self.manifest_sha256,
            "review_status": self.review_status,
            "imported_at": self.imported_at,
        }


class ProjectStore:
    def __init__(self, path: Path) -> None:
        self.path = path.resolve()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    question TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runs (
                    project_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    branch_name TEXT NOT NULL,
                    parent_run_id TEXT,
                    manifest_path TEXT NOT NULL,
                    manifest_sha256 TEXT NOT NULL,
                    question TEXT NOT NULL,
                    review_status TEXT NOT NULL,
                    imported_at TEXT NOT NULL,
                    PRIMARY KEY (project_id, run_id),
                    FOREIGN KEY (project_id) REFERENCES projects(project_id),
                    FOREIGN KEY (project_id, parent_run_id) REFERENCES runs(project_id, run_id)
                );
                CREATE TABLE IF NOT EXISTS run_artifacts (
                    project_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    artifact_path TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    artifact_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (project_id, run_id, artifact_path),
                    FOREIGN KEY (project_id, run_id) REFERENCES runs(project_id, run_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS run_claims (
                    project_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    claim_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (project_id, run_id, claim_id),
                    FOREIGN KEY (project_id, run_id) REFERENCES runs(project_id, run_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS branches (
                    project_id TEXT NOT NULL,
                    branch_name TEXT NOT NULL,
                    base_run_id TEXT NOT NULL,
                    head_run_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (project_id, branch_name),
                    FOREIGN KEY (project_id, base_run_id) REFERENCES runs(project_id, run_id),
                    FOREIGN KEY (project_id, head_run_id) REFERENCES runs(project_id, run_id)
                );
                CREATE TABLE IF NOT EXISTS assertions (
                    project_id TEXT NOT NULL,
                    assertion_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    claim_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    polarity TEXT NOT NULL,
                    effect_measure TEXT,
                    estimate REAL,
                    interval_low REAL,
                    interval_high REAL,
                    unit TEXT,
                    sample_size INTEGER,
                    population TEXT,
                    independence_group TEXT NOT NULL,
                    risk_of_bias_ref TEXT,
                    locator_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    PRIMARY KEY (project_id, assertion_id),
                    FOREIGN KEY (project_id, run_id) REFERENCES runs(project_id, run_id),
                    FOREIGN KEY (project_id, run_id, claim_id) REFERENCES run_claims(project_id, run_id, claim_id)
                );
                CREATE TABLE IF NOT EXISTS merge_plans (
                    project_id TEXT NOT NULL,
                    plan_id TEXT NOT NULL,
                    source_branch TEXT NOT NULL,
                    target_branch TEXT NOT NULL,
                    base_run_id TEXT NOT NULL,
                    source_run_id TEXT NOT NULL,
                    target_run_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    PRIMARY KEY (project_id, plan_id)
                );
                CREATE TABLE IF NOT EXISTS events (
                    project_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    previous_event_sha256 TEXT,
                    event_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (project_id, sequence)
                );
                """
            )
            current = connection.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
            if current is None:
                connection.execute("INSERT INTO metadata(key, value) VALUES('schema_version', ?)", (str(SCHEMA_VERSION),))
            elif int(current["value"]) != SCHEMA_VERSION:
                raise ValueError(f"unsupported project store schema: {current['value']}")

    def _require_project(self, connection: sqlite3.Connection, project_id: str) -> None:
        if connection.execute("SELECT 1 FROM projects WHERE project_id=?", (project_id,)).fetchone() is None:
            raise ValueError(f"unknown project: {project_id}")

    def _require_run(self, connection: sqlite3.Connection, project_id: str, run_id: str) -> sqlite3.Row:
        row = connection.execute("SELECT * FROM runs WHERE project_id=? AND run_id=?", (project_id, run_id)).fetchone()
        if row is None:
            raise ValueError(f"unknown run: {project_id}/{run_id}")
        return row

    def _require_branch(self, connection: sqlite3.Connection, project_id: str, branch_name: str) -> sqlite3.Row:
        row = connection.execute("SELECT * FROM branches WHERE project_id=? AND branch_name=?", (project_id, branch_name)).fetchone()
        if row is None:
            raise ValueError(f"unknown branch: {project_id}/{branch_name}")
        return row

    def _append_event(self, connection: sqlite3.Connection, project_id: str, event_type: str, payload: Mapping[str, Any]) -> str:
        row = connection.execute("SELECT sequence, event_sha256 FROM events WHERE project_id=? ORDER BY sequence DESC LIMIT 1", (project_id,)).fetchone()
        sequence = 1 if row is None else int(row["sequence"]) + 1
        previous = None if row is None else str(row["event_sha256"])
        created_at = _now()
        material = {
            "project_id": project_id,
            "sequence": sequence,
            "event_type": event_type,
            "payload": dict(payload),
            "previous_event_sha256": previous,
            "created_at": created_at,
        }
        digest = _sha256_json(material)
        connection.execute(
            "INSERT INTO events(project_id, sequence, event_type, payload_json, previous_event_sha256, event_sha256, created_at) VALUES(?,?,?,?,?,?,?)",
            (project_id, sequence, event_type, json.dumps(dict(payload), sort_keys=True), previous, digest, created_at),
        )
        return digest

    def create_project(self, *, project_id: str, title: str, question: str) -> dict[str, Any]:
        self.initialize()
        project_id = _text(project_id, "project_id")
        title = _text(title, "title")
        question = _text(question, "question")
        created_at = _now()
        with self.connect() as connection:
            existing = connection.execute("SELECT * FROM projects WHERE project_id=?", (project_id,)).fetchone()
            if existing is not None:
                if existing["title"] == title and existing["question"] == question:
                    return dict(existing)
                raise ValueError(f"project already exists with different metadata: {project_id}")
            connection.execute(
                "INSERT INTO projects(project_id, title, question, created_at, status) VALUES(?,?,?,?,?)",
                (project_id, title, question, created_at, "active"),
            )
            self._append_event(connection, project_id, "project-created", {"title": title, "question": question})
        return {"project_id": project_id, "title": title, "question": question, "created_at": created_at, "status": "active"}

    def import_run(
        self,
        *,
        project_id: str,
        manifest_path: Path,
        branch_name: str = "main",
        parent_run_id: str | None = None,
    ) -> ImportedRun:
        self.initialize()
        project_id = _text(project_id, "project_id")
        branch_name = _text(branch_name, "branch_name")
        manifest_path = manifest_path.resolve()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError("run manifest must be an object")
        validate_bundle(manifest, manifest_path.parent)
        run_id = _text(manifest.get("run_id"), "manifest run_id")
        digest, _size = stream_sha256(manifest_path)
        question = _text(manifest.get("question"), "manifest question")
        review_status = str(manifest.get("review", {}).get("status", "unknown"))
        imported_at = _now()
        with self.connect() as connection:
            self._require_project(connection, project_id)
            if parent_run_id is not None:
                self._require_run(connection, project_id, parent_run_id)
            existing = connection.execute("SELECT * FROM runs WHERE project_id=? AND run_id=?", (project_id, run_id)).fetchone()
            if existing is not None:
                if existing["manifest_sha256"] != digest:
                    raise ValueError(f"run ID already exists with different manifest bytes: {run_id}")
                return ImportedRun(
                    project_id, run_id, str(existing["branch_name"]), existing["parent_run_id"],
                    str(existing["manifest_path"]), digest, str(existing["review_status"]), str(existing["imported_at"]),
                )
            branch = connection.execute("SELECT * FROM branches WHERE project_id=? AND branch_name=?", (project_id, branch_name)).fetchone()
            if branch is not None and parent_run_id is None:
                parent_run_id = str(branch["head_run_id"])
            connection.execute(
                "INSERT INTO runs(project_id, run_id, branch_name, parent_run_id, manifest_path, manifest_sha256, question, review_status, imported_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (project_id, run_id, branch_name, parent_run_id, str(manifest_path), digest, question, review_status, imported_at),
            )
            for artifact_path, artifact in sorted(_manifest_artifacts(manifest).items()):
                connection.execute(
                    "INSERT INTO run_artifacts(project_id, run_id, artifact_path, sha256, kind, artifact_type, payload_json) VALUES(?,?,?,?,?,?,?)",
                    (
                        project_id, run_id, artifact_path, _sha(artifact.get("sha256"), "artifact sha256"),
                        str(artifact.get("kind", "artifact")), str(artifact.get("artifact_type", "file")),
                        json.dumps(artifact, sort_keys=True),
                    ),
                )
            for claim_id, claim in sorted(_manifest_claims(manifest).items()):
                connection.execute(
                    "INSERT INTO run_claims(project_id, run_id, claim_id, payload_json) VALUES(?,?,?,?)",
                    (project_id, run_id, claim_id, json.dumps(claim, sort_keys=True)),
                )
            if branch is None:
                connection.execute(
                    "INSERT INTO branches(project_id, branch_name, base_run_id, head_run_id, status, created_at, updated_at) VALUES(?,?,?,?,?,?,?)",
                    (project_id, branch_name, run_id, run_id, "active", imported_at, imported_at),
                )
            else:
                connection.execute(
                    "UPDATE branches SET head_run_id=?, updated_at=? WHERE project_id=? AND branch_name=?",
                    (run_id, imported_at, project_id, branch_name),
                )
            self._append_event(
                connection,
                project_id,
                "run-imported",
                {"run_id": run_id, "branch_name": branch_name, "parent_run_id": parent_run_id, "manifest_sha256": digest, "review_status": review_status},
            )
        return ImportedRun(project_id, run_id, branch_name, parent_run_id, str(manifest_path), digest, review_status, imported_at)

    def fork_branch(self, *, project_id: str, source_run_id: str, branch_name: str) -> dict[str, Any]:
        self.initialize()
        project_id = _text(project_id, "project_id")
        source_run_id = _text(source_run_id, "source_run_id")
        branch_name = _text(branch_name, "branch_name")
        created_at = _now()
        with self.connect() as connection:
            self._require_project(connection, project_id)
            self._require_run(connection, project_id, source_run_id)
            if connection.execute("SELECT 1 FROM branches WHERE project_id=? AND branch_name=?", (project_id, branch_name)).fetchone() is not None:
                raise ValueError(f"branch already exists: {branch_name}")
            connection.execute(
                "INSERT INTO branches(project_id, branch_name, base_run_id, head_run_id, status, created_at, updated_at) VALUES(?,?,?,?,?,?,?)",
                (project_id, branch_name, source_run_id, source_run_id, "active", created_at, created_at),
            )
            self._append_event(connection, project_id, "branch-forked", {"branch_name": branch_name, "source_run_id": source_run_id})
        return {"project_id": project_id, "branch_name": branch_name, "base_run_id": source_run_id, "head_run_id": source_run_id, "status": "active", "created_at": created_at}

    def add_assertion(
        self,
        *,
        project_id: str,
        run_id: str,
        claim_id: str,
        source_id: str,
        polarity: str,
        locator: Mapping[str, Any],
        independence_group: str,
        effect_measure: str | None = None,
        estimate: float | None = None,
        interval_low: float | None = None,
        interval_high: float | None = None,
        unit: str | None = None,
        sample_size: int | None = None,
        population: str | None = None,
        risk_of_bias_ref: str | None = None,
    ) -> dict[str, Any]:
        self.initialize()
        for value, label in ((project_id, "project_id"), (run_id, "run_id"), (claim_id, "claim_id"), (source_id, "source_id"), (independence_group, "independence_group")):
            _text(value, label)
        if polarity not in POLARITIES:
            raise ValueError(f"invalid assertion polarity: {polarity}")
        locator_payload = _json_object(locator, "locator")
        artifact_path = _relative(locator_payload.get("artifact_path"), "locator artifact_path")
        artifact_sha = _sha(locator_payload.get("artifact_sha256"), "locator artifact_sha256")
        if not any(locator_payload.get(field) not in (None, "") for field in ("page", "table", "figure", "cell", "json_pointer", "line_range", "record_id")):
            raise ValueError("assertion locator needs a page, table, figure, cell, JSON pointer, line range, or record ID")
        locator_payload["artifact_path"] = artifact_path
        locator_payload["artifact_sha256"] = artifact_sha
        if sample_size is not None and (isinstance(sample_size, bool) or sample_size < 0):
            raise ValueError("sample_size must be a non-negative integer")
        if (interval_low is None) != (interval_high is None):
            raise ValueError("both interval bounds must be provided together")
        if interval_low is not None and interval_high is not None and interval_low > interval_high:
            raise ValueError("interval_low cannot exceed interval_high")
        created_at = _now()
        material = {
            "project_id": project_id,
            "run_id": run_id,
            "claim_id": claim_id,
            "source_id": source_id,
            "polarity": polarity,
            "effect_measure": effect_measure,
            "estimate": estimate,
            "interval_low": interval_low,
            "interval_high": interval_high,
            "unit": unit,
            "sample_size": sample_size,
            "population": population,
            "independence_group": independence_group,
            "risk_of_bias_ref": risk_of_bias_ref,
            "locator": locator_payload,
            "created_at": created_at,
        }
        fingerprint = _sha256_json(material)
        assertion_id = f"assertion-{fingerprint[:20]}"
        with self.connect() as connection:
            self._require_run(connection, project_id, run_id)
            if connection.execute("SELECT 1 FROM run_claims WHERE project_id=? AND run_id=? AND claim_id=?", (project_id, run_id, claim_id)).fetchone() is None:
                raise ValueError(f"claim is not present in imported run: {claim_id}")
            artifact = connection.execute(
                "SELECT sha256 FROM run_artifacts WHERE project_id=? AND run_id=? AND artifact_path=?",
                (project_id, run_id, artifact_path),
            ).fetchone()
            if artifact is None or str(artifact["sha256"]) != artifact_sha:
                raise ValueError("assertion locator does not match an imported artifact hash")
            existing = connection.execute("SELECT fingerprint FROM assertions WHERE project_id=? AND assertion_id=?", (project_id, assertion_id)).fetchone()
            if existing is not None:
                return {**material, "assertion_id": assertion_id, "fingerprint": fingerprint}
            connection.execute(
                """INSERT INTO assertions(
                    project_id, assertion_id, run_id, claim_id, source_id, polarity,
                    effect_measure, estimate, interval_low, interval_high, unit,
                    sample_size, population, independence_group, risk_of_bias_ref,
                    locator_json, created_at, fingerprint
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    project_id, assertion_id, run_id, claim_id, source_id, polarity,
                    effect_measure, estimate, interval_low, interval_high, unit,
                    sample_size, population, independence_group, risk_of_bias_ref,
                    json.dumps(locator_payload, sort_keys=True), created_at, fingerprint,
                ),
            )
            self._append_event(connection, project_id, "assertion-added", {"assertion_id": assertion_id, "run_id": run_id, "claim_id": claim_id, "fingerprint": fingerprint})
        return {**material, "assertion_id": assertion_id, "fingerprint": fingerprint}

    def _load_manifest_for_run(self, connection: sqlite3.Connection, project_id: str, run_id: str) -> dict[str, Any]:
        row = self._require_run(connection, project_id, run_id)
        path = Path(str(row["manifest_path"]))
        digest, _size = stream_sha256(path)
        if digest != str(row["manifest_sha256"]):
            raise ValueError(f"imported run manifest changed on disk: {run_id}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"run manifest is not an object: {run_id}")
        return payload

    def compare_runs(self, *, project_id: str, previous_run_id: str, current_run_id: str) -> dict[str, Any]:
        self.initialize()
        with self.connect() as connection:
            self._require_project(connection, project_id)
            previous = self._load_manifest_for_run(connection, project_id, previous_run_id)
            current = self._load_manifest_for_run(connection, project_id, current_run_id)
        result = diff_runs(previous, current)
        result["project_id"] = project_id
        return result

    @staticmethod
    def _three_way_conflicts(base: Mapping[str, Any], source: Mapping[str, Any], target: Mapping[str, Any], key: str) -> list[str]:
        base_items = {str(item.get(key)): item for item in base.values() if isinstance(item, Mapping)} if isinstance(base, Mapping) else {}
        source_items = {str(item.get(key)): item for item in source.values() if isinstance(item, Mapping)} if isinstance(source, Mapping) else {}
        target_items = {str(item.get(key)): item for item in target.values() if isinstance(item, Mapping)} if isinstance(target, Mapping) else {}
        conflicts = []
        for identifier in sorted(source_items.keys() & target_items.keys()):
            source_changed = source_items[identifier] != base_items.get(identifier)
            target_changed = target_items[identifier] != base_items.get(identifier)
            if source_changed and target_changed and source_items[identifier] != target_items[identifier]:
                conflicts.append(identifier)
        return conflicts

    def prepare_merge_plan(self, *, project_id: str, source_branch: str, target_branch: str) -> dict[str, Any]:
        self.initialize()
        project_id = _text(project_id, "project_id")
        created_at = _now()
        with self.connect() as connection:
            source = self._require_branch(connection, project_id, source_branch)
            target = self._require_branch(connection, project_id, target_branch)
            source_run = str(source["head_run_id"])
            target_run = str(target["head_run_id"])
            base_candidates = {str(source["base_run_id"]), str(target["base_run_id"])}
            if str(source["base_run_id"]) == str(target["base_run_id"]):
                base_run = str(source["base_run_id"])
            elif str(source["base_run_id"]) == target_run:
                base_run = target_run
            elif str(target["base_run_id"]) == source_run:
                base_run = source_run
            else:
                # The store does not invent a lowest common ancestor. Choose the
                # source fork point and report the ambiguity explicitly.
                base_run = str(source["base_run_id"])
            base_manifest = self._load_manifest_for_run(connection, project_id, base_run)
            source_manifest = self._load_manifest_for_run(connection, project_id, source_run)
            target_manifest = self._load_manifest_for_run(connection, project_id, target_run)
            source_diff = diff_runs(base_manifest, source_manifest)
            target_diff = diff_runs(base_manifest, target_manifest)
            base_claims, source_claims, target_claims = (_manifest_claims(item) for item in (base_manifest, source_manifest, target_manifest))
            base_artifacts, source_artifacts, target_artifacts = (_manifest_artifacts(item) for item in (base_manifest, source_manifest, target_manifest))
            claim_conflicts = sorted(
                claim_id for claim_id in source_claims.keys() & target_claims.keys()
                if source_claims[claim_id] != base_claims.get(claim_id)
                and target_claims[claim_id] != base_claims.get(claim_id)
                and source_claims[claim_id] != target_claims[claim_id]
            )
            artifact_conflicts = sorted(
                artifact_path for artifact_path in source_artifacts.keys() & target_artifacts.keys()
                if source_artifacts[artifact_path] != base_artifacts.get(artifact_path)
                and target_artifacts[artifact_path] != base_artifacts.get(artifact_path)
                and source_artifacts[artifact_path] != target_artifacts[artifact_path]
            )
            payload = {
                "schema_version": 1,
                "project_id": project_id,
                "source_branch": source_branch,
                "target_branch": target_branch,
                "base_run_id": base_run,
                "source_run_id": source_run,
                "target_run_id": target_run,
                "source_diff": source_diff,
                "target_diff": target_diff,
                "claim_conflicts": claim_conflicts,
                "artifact_conflicts": artifact_conflicts,
                "base_ambiguity": len(base_candidates) > 1 and base_run not in {source_run, target_run},
                "review_receipts_invalidated": bool(
                    source_diff.get("review_invalidated") or target_diff.get("review_invalidated")
                ),
                "requires_scientific_review": True,
                "status": "blocked-conflicts" if claim_conflicts or artifact_conflicts else "candidate",
                "executed": False,
                "created_at": created_at,
                "evidence_boundary": "A merge plan compares immutable run records. It does not combine artifact bytes, resolve scientific disagreements, or mark a branch merged.",
            }
            fingerprint = _sha256_json(payload)
            plan_id = f"merge-{fingerprint[:20]}"
            connection.execute(
                "INSERT OR IGNORE INTO merge_plans(project_id, plan_id, source_branch, target_branch, base_run_id, source_run_id, target_run_id, status, payload_json, created_at, fingerprint) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (project_id, plan_id, source_branch, target_branch, base_run, source_run, target_run, payload["status"], json.dumps(payload, sort_keys=True), created_at, fingerprint),
            )
            self._append_event(connection, project_id, "merge-plan-created", {"plan_id": plan_id, "source_branch": source_branch, "target_branch": target_branch, "fingerprint": fingerprint})
        return {**payload, "plan_id": plan_id, "fingerprint": fingerprint}

    def summary(self, *, project_id: str) -> dict[str, Any]:
        self.initialize()
        with self.connect() as connection:
            project = connection.execute("SELECT * FROM projects WHERE project_id=?", (project_id,)).fetchone()
            if project is None:
                raise ValueError(f"unknown project: {project_id}")
            branches = [dict(row) for row in connection.execute("SELECT * FROM branches WHERE project_id=? ORDER BY branch_name", (project_id,))]
            runs = [dict(row) for row in connection.execute("SELECT run_id, branch_name, parent_run_id, manifest_sha256, review_status, imported_at FROM runs WHERE project_id=? ORDER BY imported_at, run_id", (project_id,))]
            assertion_count = int(connection.execute("SELECT COUNT(*) AS n FROM assertions WHERE project_id=?", (project_id,)).fetchone()["n"])
            merge_count = int(connection.execute("SELECT COUNT(*) AS n FROM merge_plans WHERE project_id=?", (project_id,)).fetchone()["n"])
            last_event = connection.execute("SELECT sequence, event_sha256, created_at FROM events WHERE project_id=? ORDER BY sequence DESC LIMIT 1", (project_id,)).fetchone()
        return {
            "schema_version": 1,
            "project": dict(project),
            "branches": branches,
            "runs": runs,
            "assertion_count": assertion_count,
            "merge_plan_count": merge_count,
            "event_chain_head": None if last_event is None else dict(last_event),
            "evidence_boundary": "The project store indexes imported immutable run bundles; it is not a substitute for their manifests, reviews, or scientific evidence.",
        }
