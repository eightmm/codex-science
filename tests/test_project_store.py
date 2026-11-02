import hashlib
import json
import os
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from contextlib import contextmanager

from codex_science.artifacts import add_artifact, new_manifest, validate_bundle, write_manifest
from codex_science.project_store import ProjectStore


def make_run(root: Path, run_id: str, claim_text: str, metric_value: float) -> tuple[Path, str]:
    run_dir = root / run_id
    run_dir.mkdir(parents=True)
    metrics = run_dir / "metrics.json"
    metrics.write_text(json.dumps({"metric": "effect", "value": metric_value}) + "\n", encoding="utf-8")
    digest = hashlib.sha256(metrics.read_bytes()).hexdigest()
    manifest = new_manifest(
        run_id,
        "Which branch best supports the prespecified hypothesis?",
        [{"id": "analyze", "description": "Compute the prespecified metric", "status": "completed"}],
    )
    manifest["claims"] = [{"id": "C1", "text": claim_text, "evidence": ["metrics.json"]}]
    manifest["executions"] = [{"command": "fixture", "exit_code": 0}]
    manifest["review"] = {"status": "passed", "findings": []}
    add_artifact(manifest, "metrics.json", kind="metrics", sha256=digest)
    manifest_path = run_dir / "manifest.json"
    write_manifest(manifest, manifest_path)
    return manifest_path, digest


class ProjectStoreTests(unittest.TestCase):
    def _race_imports(self, store, first_path, second_path, branch_name="main"):
        timeout = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120"))
        first_at_insert = threading.Event()
        second_ready = threading.Event()
        first_finished = threading.Event()
        caller = threading.local()
        connect = store.connect
        case = self

        class PausingConnection:
            def __init__(self, connection):
                self.connection = connection

            def __getattr__(self, name):
                return getattr(self.connection, name)

            def execute(self, sql, parameters=()):
                if caller.role == "second" and sql == "BEGIN IMMEDIATE":
                    second_ready.set()
                if sql.startswith("INSERT INTO runs("):
                    if caller.role == "first":
                        first_at_insert.set()
                        case.assertTrue(second_ready.wait(timeout), "second import did not arrive")
                    else:
                        # Deferred callers have both read the old head here;
                        # serialized callers announced their lock attempt above.
                        second_ready.set()
                        case.assertTrue(first_finished.wait(timeout), "first import did not finish")
                return self.connection.execute(sql, parameters)

        @contextmanager
        def racing_connect():
            with connect() as connection:
                yield PausingConnection(connection)

        def run(role, path):
            caller.role = role
            try:
                return store.import_run(project_id="p", manifest_path=path, branch_name=branch_name)
            finally:
                if role == "first":
                    first_finished.set()

        # The fixture has initialized the schema; isolate the import transaction.
        with patch.object(store, "initialize"), patch.object(store, "connect", racing_connect):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(run, "first", first_path)
                self.assertTrue(first_at_insert.wait(timeout), "first import did not reach its insert")
                second = pool.submit(run, "second", second_path)
                return first.result(timeout), second.result(timeout)

    def test_concurrent_imports_keep_branch_ancestry_linear(self) -> None:
        for branch in ("main", "new-branch"):
            with self.subTest(branch=branch), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                store = ProjectStore(root / "project.sqlite")
                store.create_project(project_id="p", title="P", question="Q")
                base_path, _ = make_run(root, "base", "Base", 0)
                store.import_run(project_id="p", manifest_path=base_path)
                first_path, _ = make_run(root, "first", "First", 1)
                second_path, _ = make_run(root, "second", "Second", 2)

                first, second = self._race_imports(store, first_path, second_path, branch)

                self.assertEqual("base" if branch == "main" else None, first.parent_run_id)
                self.assertEqual(first.run_id, second.parent_run_id)
                summary = store.summary(project_id="p")
                head = next(row for row in summary["branches"] if row["branch_name"] == branch)
                self.assertEqual(second.run_id, head["head_run_id"])
                with store.connect() as connection:
                    events = connection.execute("SELECT * FROM events ORDER BY sequence").fetchall()
                self.assertEqual(list(range(1, 5)), [row["sequence"] for row in events])
                self.assertEqual([None] + [row["event_sha256"] for row in events[:-1]],
                                 [row["previous_event_sha256"] for row in events])
                self.assertEqual(first.run_id, json.loads(events[-1]["payload_json"])["parent_run_id"])

    def test_concurrent_reimports_preserve_digest_checks_and_idempotence(self) -> None:
        for changed in (False, True):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                store = ProjectStore(root / "project.sqlite")
                store.create_project(project_id="p", title="P", question="Q")
                first_path, _ = make_run(root, "same", "First", 1)
                second_path = first_path
                if changed:
                    second_path, _ = make_run(root / "other", "same", "Changed", 2)
                    with self.assertRaisesRegex(ValueError, "different manifest bytes"):
                        self._race_imports(store, first_path, second_path)
                else:
                    first, second = self._race_imports(store, first_path, second_path)
                    self.assertEqual(first, second)
                summary = store.summary(project_id="p")
                self.assertEqual(1, len(summary["runs"]))
                self.assertEqual("same", summary["branches"][0]["head_run_id"])
                self.assertEqual(2, summary["event_chain_head"]["sequence"])

    def test_import_fork_assert_compare_and_merge_plan_preserve_run_authority(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            database = root / "project" / "evidence.sqlite"
            store = ProjectStore(database)
            project = store.create_project(
                project_id="project-1",
                title="Hypothesis comparison",
                question="Which branch is supported?",
            )
            self.assertEqual("project-1", project["project_id"])

            base_manifest, _base_digest = make_run(root, "run-base", "Baseline claim", 0.5)
            source_manifest, source_digest = make_run(root, "run-source", "Source branch claim", 0.8)
            target_manifest, _target_digest = make_run(root, "run-target", "Target branch claim", 0.2)

            base = store.import_run(project_id="project-1", manifest_path=base_manifest, branch_name="main")
            self.assertEqual("run-base", base.run_id)
            store.fork_branch(project_id="project-1", source_run_id="run-base", branch_name="experiment")
            source = store.import_run(project_id="project-1", manifest_path=source_manifest, branch_name="experiment")
            target = store.import_run(project_id="project-1", manifest_path=target_manifest, branch_name="main")
            self.assertEqual("run-base", source.parent_run_id)
            self.assertEqual("run-base", target.parent_run_id)

            assertion = store.add_assertion(
                project_id="project-1",
                run_id="run-source",
                claim_id="C1",
                source_id="study-1",
                polarity="supports",
                locator={
                    "artifact_path": "metrics.json",
                    "artifact_sha256": source_digest,
                    "json_pointer": "/value",
                },
                independence_group="cohort-A",
                effect_measure="difference",
                estimate=0.8,
                interval_low=0.6,
                interval_high=1.0,
                sample_size=42,
                population="fixture population",
            )
            self.assertTrue(assertion["assertion_id"].startswith("assertion-"))

            comparison = store.compare_runs(
                project_id="project-1",
                previous_run_id="run-base",
                current_run_id="run-source",
            )
            self.assertEqual(["metrics.json"], comparison["artifacts"]["changed"])
            self.assertEqual(["C1"], comparison["claims"]["changed"])
            self.assertTrue(comparison["review_invalidated"])

            plan = store.prepare_merge_plan(
                project_id="project-1",
                source_branch="experiment",
                target_branch="main",
            )
            self.assertEqual("blocked-conflicts", plan["status"])
            self.assertEqual(["C1"], plan["claim_conflicts"])
            self.assertEqual(["metrics.json"], plan["artifact_conflicts"])
            self.assertFalse(plan["executed"])
            self.assertTrue(plan["requires_scientific_review"])

            summary = store.summary(project_id="project-1")
            self.assertEqual(3, len(summary["runs"]))
            self.assertEqual(1, summary["assertion_count"])
            self.assertEqual(1, summary["merge_plan_count"])
            self.assertIsNotNone(summary["event_chain_head"])

    def test_import_hash_and_index_use_the_validated_manifest_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ProjectStore(root / "project.sqlite")
            store.create_project(project_id="p", title="P", question="Q")
            path, _ = make_run(root, "run", "Original claim", 1)
            original = path.read_bytes()
            replacement = json.loads(original)
            replacement["claims"][0]["text"] = "Replacement claim"

            def replace_after_validation(manifest, directory):
                result = validate_bundle(manifest, directory)
                path.write_text(json.dumps(replacement), encoding="utf-8")
                return result

            with patch("codex_science.project_store.validate_bundle", side_effect=replace_after_validation):
                imported = store.import_run(project_id="p", manifest_path=path)
            self.assertEqual(hashlib.sha256(original).hexdigest(), imported.manifest_sha256)
            with store.connect() as connection:
                row = connection.execute("SELECT payload_json FROM run_claims").fetchone()
                self.assertEqual("Original claim", json.loads(row[0])["text"])
            with self.assertRaisesRegex(ValueError, "different manifest bytes"):
                store.import_run(project_id="p", manifest_path=path)
            with self.assertRaisesRegex(ValueError, "changed on disk"):
                store.compare_runs(project_id="p", previous_run_id="run", current_run_id="run")
            path.write_bytes(original)
            self.assertEqual(imported, store.import_run(project_id="p", manifest_path=path))
            before = store.summary(project_id="p")
            next_path, _ = make_run(root, "next", "New claim", 2)
            with patch.object(store, "_append_event", side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    store.import_run(project_id="p", manifest_path=next_path)
            self.assertEqual(before, store.summary(project_id="p"))
            store.import_run(project_id="p", manifest_path=next_path)
            self.assertEqual(2, len(store.summary(project_id="p")["runs"]))

    def test_loaded_manifest_hash_and_payload_share_one_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ProjectStore(root / "project.sqlite")
            store.create_project(project_id="p", title="P", question="Q")
            path, _ = make_run(root, "run", "Original claim", 1)
            store.import_run(project_id="p", manifest_path=path)
            replacement = json.loads(path.read_bytes())
            replacement["claims"][0]["text"] = "Replacement claim"
            original_open = Path.open
            replaced = False

            @contextmanager
            def replace_after_read(candidate, *args, **kwargs):
                nonlocal replaced
                with original_open(candidate, *args, **kwargs) as stream:
                    yield stream
                if candidate == path and not replaced:
                    replaced = True
                    with original_open(path, "w", encoding="utf-8") as stream:
                        json.dump(replacement, stream)

            with store.connect() as connection, patch.object(Path, "open", replace_after_read):
                loaded = store._load_manifest_for_run(connection, "p", "run")
            self.assertTrue(replaced)
            self.assertEqual("Original claim", loaded["claims"][0]["text"])
            with self.assertRaisesRegex(ValueError, "changed on disk"):
                store.compare_runs(project_id="p", previous_run_id="run", current_run_id="run")

    def test_evidence_operations_reverify_all_involved_artifact_bytes(self) -> None:
        for operation, involved in (("compare", "base"), ("compare", "source"),
                                    ("merge", "base"), ("merge", "source"), ("merge", "target"),
                                    ("assertion", "source")):
            for state in ("changed", "missing"):
                with self.subTest(operation=operation, run=involved, state=state), tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    store = ProjectStore(root / "project.sqlite")
                    store.create_project(project_id="p", title="P", question="Q")
                    for run_id, branch in (("base", "main"), ("source", "fork"), ("target", "main")):
                        path, digest = make_run(root, run_id, "Claim", 1)
                        store.import_run(project_id="p", manifest_path=path, branch_name=branch)
                        if run_id == "base":
                            store.fork_branch(project_id="p", source_run_id="base", branch_name="fork")
                    metric = root / involved / "metrics.json"
                    if state == "missing":
                        metric.unlink()
                    else:
                        metric.write_text('{"metric":"effect","value":2}', encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "Artifact (digest mismatch|file is missing)"):
                        if operation == "compare":
                            store.compare_runs(project_id="p", previous_run_id="base", current_run_id="source")
                        elif operation == "merge":
                            store.prepare_merge_plan(project_id="p", source_branch="fork", target_branch="main")
                        else:
                            store.add_assertion(
                                project_id="p", run_id="source", claim_id="C1", source_id="study", polarity="supports",
                                locator={"artifact_path": "metrics.json", "artifact_sha256": digest, "json_pointer": "/value"},
                                independence_group="cohort",
                            )
                    summary = store.summary(project_id="p")
                    self.assertEqual(0, summary["assertion_count"])
                    self.assertEqual(0, summary["merge_plan_count"])

    def test_merge_conflicts_include_deletions_and_json_type_changes(self) -> None:
        cases = [
            ("delete", "edit", True), ("edit", "delete", True),
            ("delete", "delete", False), ("delete", "base", False),
            ("base", "delete", False), ("edit", "edit", False),
            (True, 1, True), (1, 1.0, True), (0, 0, False),
        ]
        for source_value, target_value, conflict in cases:
            with self.subTest(source=source_value, target=target_value), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                store = ProjectStore(root / "project.sqlite")
                store.create_project(project_id="p", title="P", question="Q")
                for run_id, value, branch in (("base", "base", "main"), ("source", source_value, "fork"), ("target", target_value, "main")):
                    path, _ = make_run(root, run_id, "Claim", 1)
                    manifest = json.loads(path.read_bytes())
                    if value == "delete":
                        manifest["claims"] = []
                        manifest["artifacts"] = []
                    else:
                        result = 0 if value == "base" else value
                        manifest["claims"][0]["result"] = result
                        manifest["artifacts"][0]["result"] = result
                    write_manifest(manifest, path)
                    store.import_run(project_id="p", manifest_path=path, branch_name=branch)
                    if run_id == "base":
                        store.fork_branch(project_id="p", source_run_id="base", branch_name="fork")
                plan = store.prepare_merge_plan(project_id="p", source_branch="fork", target_branch="main")
                self.assertEqual(["C1"] if conflict else [], plan["claim_conflicts"])
                self.assertEqual(["metrics.json"] if conflict else [], plan["artifact_conflicts"])
                self.assertEqual("blocked-conflicts" if conflict else "candidate", plan["status"])

    def test_assertion_json_pointer_must_resolve_with_rfc6901_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ProjectStore(root / "project.sqlite")
            store.create_project(project_id="p", title="P", question="Q")
            path, _ = make_run(root, "run", "Claim", 1)
            metric = path.parent / "metrics.json"
            metric.write_text(json.dumps({"value": 0, "": None, "a/b": {"~": [False, 1]}}), encoding="utf-8")
            digest = hashlib.sha256(metric.read_bytes()).hexdigest()
            manifest = json.loads(path.read_bytes())
            manifest["artifacts"][0]["sha256"] = digest
            for name, media_type in (("result.data", "application/example+json; charset=utf-8"),
                                     ("result", "application/json"), ("notes.txt", "text/plain")):
                alternate = path.parent / name
                alternate.write_bytes(metric.read_bytes())
                add_artifact(manifest, name, kind="data", sha256=digest, media_type=media_type)
            write_manifest(manifest, path)
            store.import_run(project_id="p", manifest_path=path)
            valid = ("", "/", "/value", "/a~1b/~0/0", "/a~1b/~0/1")
            invalid = ("/missing", "/value/child", "/a~1b/~0/2", "/a~1b/~0/-", "/a~1b/~0/00",
                       "/a~1b/~0/-1", "/a~1b/~0/١", "/a~2b", "value", None, 0)
            for pointer in (*invalid, *valid):
                with self.subTest(pointer=pointer):
                    arguments = dict(
                        project_id="p", run_id="run", claim_id="C1", source_id="study", polarity="supports",
                        locator={"artifact_path": "metrics.json", "artifact_sha256": digest, "json_pointer": pointer},
                        independence_group="cohort",
                    )
                    if pointer in invalid:
                        with self.assertRaises(ValueError):
                            store.add_assertion(**arguments)
                    else:
                        self.assertEqual(pointer, store.add_assertion(**arguments)["locator"]["json_pointer"])
            for name in ("result.data", "result"):
                arguments["locator"] = {"artifact_path": name, "artifact_sha256": digest, "json_pointer": "/missing"}
                with self.assertRaisesRegex(ValueError, "json_pointer does not resolve"):
                    store.add_assertion(**arguments)
                for pointer in ("/value", ""):
                    arguments["locator"]["json_pointer"] = pointer
                    self.assertEqual(pointer, store.add_assertion(**arguments)["locator"]["json_pointer"])
            arguments["locator"]["artifact_path"] = "notes.txt"
            arguments["locator"]["json_pointer"] = "/value"
            arguments["locator"]["line_range"] = "1"
            self.assertEqual("/value", store.add_assertion(**arguments)["locator"]["json_pointer"])
            for key in ("line_range", "page", "table", "figure", "cell", "record_id"):
                arguments["locator"] = {"artifact_path": "metrics.json", "artifact_sha256": digest, key: "1"}
                self.assertEqual("1", store.add_assertion(**arguments)["locator"][key])
            for bad in (None, "", "/value", "value", 0, False, [], {}):
                with self.subTest(non_json_pointer=bad):
                    with store.connect() as connection:
                        before_counts = tuple(connection.execute(
                            "SELECT (SELECT COUNT(*) FROM assertions), (SELECT COUNT(*) FROM events)"
                        ).fetchone())
                    arguments["locator"] = {"artifact_path": "notes.txt", "artifact_sha256": digest, "json_pointer": bad}
                    with self.assertRaisesRegex(ValueError, "assertion locator needs a page, table, figure, cell, JSON pointer, line range, or record ID"):
                        store.add_assertion(**arguments)
                    with store.connect() as connection:
                        self.assertEqual(before_counts, tuple(connection.execute(
                            "SELECT (SELECT COUNT(*) FROM assertions), (SELECT COUNT(*) FROM events)"
                        ).fetchone()))
            for pointer in (None, "", "/value"):
                arguments["locator"] = {"artifact_path": "notes.txt", "artifact_sha256": digest, "json_pointer": pointer, "page": 0}
                self.assertEqual(0, store.add_assertion(**arguments)["locator"]["page"])
            arguments["locator"] = {"artifact_path": "metrics.json", "artifact_sha256": digest, "json_pointer": ""}
            self.assertEqual("", store.add_assertion(**arguments)["locator"]["json_pointer"])
            before = store.summary(project_id="p")
            original_metric = metric.read_bytes()

            def replace_artifact_after_validation(payload, directory):
                result = validate_bundle(payload, directory)
                metric.write_text('{"value":2}', encoding="utf-8")
                return result

            arguments["locator"] = {"artifact_path": "metrics.json", "artifact_sha256": digest, "json_pointer": "/value"}
            try:
                with patch("codex_science.project_store.validate_bundle", side_effect=replace_artifact_after_validation):
                    with self.assertRaisesRegex(ValueError, "artifact changed during locator validation"):
                        store.add_assertion(**arguments)
            finally:
                metric.write_bytes(original_metric)
            self.assertEqual(before, store.summary(project_id="p"))

    def test_changed_manifest_bytes_cannot_be_reused_under_same_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            store = ProjectStore(root / "project.sqlite")
            store.create_project(project_id="p", title="P", question="Q")
            manifest_path, _digest = make_run(root, "run-1", "Claim", 1.0)
            store.import_run(project_id="p", manifest_path=manifest_path, branch_name="main")
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload["question"] = "Changed question"
            manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "different manifest bytes"):
                store.import_run(project_id="p", manifest_path=manifest_path, branch_name="main")
            with self.assertRaisesRegex(ValueError, "changed on disk"):
                store.compare_runs(project_id="p", previous_run_id="run-1", current_run_id="run-1")

    def test_assertion_requires_exact_imported_artifact_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            store = ProjectStore(root / "project.sqlite")
            store.create_project(project_id="p", title="P", question="Q")
            manifest_path, _digest = make_run(root, "run-1", "Claim", 1.0)
            store.import_run(project_id="p", manifest_path=manifest_path, branch_name="main")
            with self.assertRaisesRegex(ValueError, "does not match"):
                store.add_assertion(
                    project_id="p",
                    run_id="run-1",
                    claim_id="C1",
                    source_id="study",
                    polarity="supports",
                    locator={"artifact_path": "metrics.json", "artifact_sha256": "0" * 64, "json_pointer": "/value"},
                    independence_group="cohort",
                )

    def _counts(self, store):
        with store.connect() as connection:
            return tuple(connection.execute(
                "SELECT (SELECT COUNT(*) FROM runs), (SELECT COUNT(*) FROM assertions),"
                " (SELECT COUNT(*) FROM merge_plans), (SELECT COUNT(*) FROM events)"
            ).fetchone())

    def test_import_refuses_claim_ids_and_artifact_paths_that_are_not_strings(self) -> None:
        cases = [("claims", "id", value, "claim id") for value in (7, 0, None, True, "  ")]
        cases.append(("artifacts", "path", 7, "artifact path"))
        for section, field, value, label in cases:
            with self.subTest(section=section, value=value), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                store = ProjectStore(root / "project.sqlite")
                store.create_project(project_id="p", title="P", question="Q")
                path, _ = make_run(root, "run", "Claim", 1)
                manifest = json.loads(path.read_bytes())
                manifest[section][0][field] = value
                if section == "artifacts":
                    (path.parent / "7").write_bytes((path.parent / "metrics.json").read_bytes())
                path.write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaises(ValueError) as caught:
                    store.import_run(project_id="p", manifest_path=path)
                if value != "  ":
                    self.assertIn(f"{label} must be a non-empty string", str(caught.exception))
                self.assertEqual((0, 0, 0, 1), self._counts(store))

    def test_assertion_refuses_non_finite_or_non_numeric_estimates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ProjectStore(root / "project.sqlite")
            store.create_project(project_id="p", title="P", question="Q")
            path, digest = make_run(root, "run", "Claim", 1)
            store.import_run(project_id="p", manifest_path=path)
            arguments = dict(
                project_id="p", run_id="run", claim_id="C1", source_id="study", polarity="supports",
                locator={"artifact_path": "metrics.json", "artifact_sha256": digest, "json_pointer": "/value"},
                independence_group="cohort",
            )
            before = self._counts(store)
            for field in ("estimate", "interval_low", "interval_high"):
                for bad in (float("nan"), float("inf"), float("-inf"), True, "1"):
                    with self.subTest(field=field, value=bad):
                        values = {"estimate": 0.5} if field == "estimate" else {"interval_low": -1.0, "interval_high": 1.0}
                        values[field] = bad
                        with self.assertRaisesRegex(ValueError, f"{field} must be a finite number"):
                            store.add_assertion(**arguments, **values)
                        self.assertEqual(before, self._counts(store))
            recorded = store.add_assertion(**arguments, estimate=0, interval_low=0.0, interval_high=0.0)
            self.assertEqual((0, 0.0, 0.0), (recorded["estimate"], recorded["interval_low"], recorded["interval_high"]))

    def test_dot_spelled_artifacts_are_citable_and_locators_need_an_artifact_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ProjectStore(root / "project.sqlite")
            store.create_project(project_id="p", title="P", question="Q")
            path, digest = make_run(root, "run", "Claim", 1)
            manifest = json.loads(path.read_bytes())
            manifest["artifacts"][0]["path"] = "./metrics.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            store.import_run(project_id="p", manifest_path=path)
            arguments = dict(project_id="p", run_id="run", claim_id="C1", source_id="study",
                             polarity="supports", independence_group="cohort")
            for spelling in ("./metrics.json", "metrics.json"):
                locator = {"artifact_path": spelling, "artifact_sha256": digest, "json_pointer": "/value"}
                self.assertEqual("metrics.json", store.add_assertion(**arguments, locator=locator)["locator"]["artifact_path"])
            before = self._counts(store)
            for locator in ({"artifact_sha256": digest, "page": 1}, {"artifact_path": None, "artifact_sha256": digest, "page": 1}):
                with self.assertRaisesRegex(ValueError, "locator artifact_path is required"):
                    store.add_assertion(**arguments, locator=locator)
            self.assertEqual(before, self._counts(store))

    def _forked_store(self, root):
        store = ProjectStore(root / "project.sqlite")
        store.create_project(project_id="p", title="P", question="Q")
        for run_id, branch in (("base", "main"), ("a", "main"), ("c", "main"), ("b", "fork")):
            if run_id == "c":
                store.fork_branch(project_id="p", source_run_id="a", branch_name="fork")
            path, _ = make_run(root, run_id, "Claim", 1)
            store.import_run(project_id="p", manifest_path=path, branch_name=branch)
        return store

    def test_summary_and_merge_plan_verify_the_event_chain(self) -> None:
        tampering = (
            ("UPDATE events SET payload_json='{}' WHERE sequence=2", 2),
            ("UPDATE events SET payload_json='not json' WHERE sequence=2", 2),
            ("UPDATE events SET event_sha256=? WHERE sequence=3", 3),
            ("UPDATE events SET previous_event_sha256=? WHERE sequence=4", 4),
            ("DELETE FROM events WHERE sequence=2", 2),
            ("UPDATE events SET sequence=0 WHERE sequence=1", 1),
        )
        for statement, broken in tampering:
            with self.subTest(statement=statement), tempfile.TemporaryDirectory() as temporary:
                store = self._forked_store(Path(temporary))
                with store.connect() as connection:
                    connection.execute(statement, ("f" * 64,) if "?" in statement else ())
                before = self._counts(store)
                with self.assertRaisesRegex(ValueError, f"event chain is broken at event {broken}:"):
                    store.summary(project_id="p")
                with self.assertRaisesRegex(ValueError, f"event chain is broken at event {broken}:"):
                    store.prepare_merge_plan(project_id="p", source_branch="fork", target_branch="main")
                self.assertEqual(before, self._counts(store))

    def test_merge_plan_uses_parent_lineage_and_refuses_one_branch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = self._forked_store(root)
            for source, target in (("fork", "main"), ("main", "fork")):
                plan = store.prepare_merge_plan(project_id="p", source_branch=source, target_branch=target)
                self.assertEqual(("a", False), (plan["base_run_id"], plan["base_ambiguity"]))
            before = self._counts(store)
            with self.assertRaisesRegex(ValueError, "merge plan needs two different branches: main"):
                store.prepare_merge_plan(project_id="p", source_branch="main", target_branch="main")
            self.assertEqual(before, self._counts(store))
            path, _ = make_run(root, "island", "Claim", 1)
            store.import_run(project_id="p", manifest_path=path, branch_name="island")
            plan = store.prepare_merge_plan(project_id="p", source_branch="island", target_branch="main")
            self.assertEqual(("island", False), (plan["base_run_id"], plan["base_ambiguity"]))
            plan = store.prepare_merge_plan(project_id="p", source_branch="fork", target_branch="island")
            self.assertEqual(("a", True), (plan["base_run_id"], plan["base_ambiguity"]))

    def test_import_refuses_oversized_deeply_nested_or_looping_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ProjectStore(root / "project.sqlite")
            store.create_project(project_id="p", title="P", question="Q")
            path, _ = make_run(root, "run", "Claim", 1)
            size = len(path.read_bytes())
            with patch("codex_science.project_store.DEFAULT_MAX_JSON_BYTES", size - 1):
                with self.assertRaisesRegex(ValueError, f"run manifest exceeds {size - 1} bytes"):
                    store.import_run(project_id="p", manifest_path=path)
            self.assertEqual((0, 0, 0, 1), self._counts(store))
            deep = root / "deep.json"
            deep.write_text("[" * 200000 + "]" * 200000, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid JSON in .*deep.json: excessive nesting"):
                store.import_run(project_id="p", manifest_path=deep)
            empty = root / "empty.json"
            empty.write_bytes(b"")
            with self.assertRaisesRegex(ValueError, "invalid JSON in .*empty.json"):
                store.import_run(project_id="p", manifest_path=empty)
            loop = root / "loop.json"
            loop.symlink_to(loop)
            with self.assertRaisesRegex(ValueError, "invalid protected input path"):
                store.import_run(project_id="p", manifest_path=loop)
            self.assertEqual((0, 0, 0, 1), self._counts(store))
            with patch("codex_science.project_store.DEFAULT_MAX_JSON_BYTES", size):
                self.assertEqual("run", store.import_run(project_id="p", manifest_path=path).run_id)

    def test_reimport_refuses_a_different_branch_or_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ProjectStore(root / "project.sqlite")
            store.create_project(project_id="p", title="P", question="Q")
            base_path, _ = make_run(root, "base", "Claim", 1)
            store.import_run(project_id="p", manifest_path=base_path)
            path, _ = make_run(root, "next", "Claim", 2)
            imported = store.import_run(project_id="p", manifest_path=path)
            self.assertEqual(imported, store.import_run(project_id="p", manifest_path=path, branch_name="main", parent_run_id="base"))
            before = self._counts(store)
            with self.assertRaisesRegex(ValueError, "already imported on branch main: next"):
                store.import_run(project_id="p", manifest_path=path, branch_name="other")
            with self.assertRaisesRegex(ValueError, "already imported with parent base: next"):
                store.import_run(project_id="p", manifest_path=path, parent_run_id="next")
            with self.assertRaisesRegex(ValueError, "already imported with parent None: base"):
                store.import_run(project_id="p", manifest_path=base_path, parent_run_id="next")
            self.assertEqual(before, self._counts(store))
            self.assertEqual(["main"], [row["branch_name"] for row in store.summary(project_id="p")["branches"]])

    def test_runs_stored_with_non_string_claim_ids_refuse_reimport_and_review(self) -> None:
        def tolerant_claims(manifest):
            return {str(item["id"]): dict(item) for item in manifest.get("claims", []) if item.get("id")}

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ProjectStore(root / "project.sqlite")
            store.create_project(project_id="p", title="P", question="Q")
            path, _ = make_run(root, "legacy", "Claim", 1)
            manifest = json.loads(path.read_bytes())
            manifest["claims"][0]["id"] = 7
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with patch("codex_science.project_store._manifest_claims", tolerant_claims):
                store.import_run(project_id="p", manifest_path=path)
            store.fork_branch(project_id="p", source_run_id="legacy", branch_name="fork")
            before = self._counts(store)
            with self.assertRaisesRegex(ValueError, "claim id must be a non-empty string"):
                store.import_run(project_id="p", manifest_path=path)
            with self.assertRaisesRegex(ValueError, "claim id must be a non-empty string"):
                store.compare_runs(project_id="p", previous_run_id="legacy", current_run_id="legacy")
            with self.assertRaisesRegex(ValueError, "claim id must be a non-empty string"):
                store.prepare_merge_plan(project_id="p", source_branch="fork", target_branch="main")
            self.assertEqual(before, self._counts(store))

    def test_discovery_history_validates_each_bundle_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ProjectStore(root / "project.sqlite")
            store.create_project(project_id="p", title="P", question="Q")
            path, _ = make_run(root, "run", "Claim", 1)
            store.import_run(project_id="p", manifest_path=path)
            with patch("codex_science.project_store.validate_bundle", side_effect=validate_bundle) as validator:
                store.discovery_history(project_id="p")
            self.assertEqual(1, validator.call_count)


if __name__ == "__main__":
    unittest.main()
