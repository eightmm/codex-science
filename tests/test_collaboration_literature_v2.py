import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from codex_science.collaboration import (
    append_resolution_event,
    annotation_resolution_lock,
    diff_runs,
    fold_annotation_resolutions,
    load_resolution_events,
    selective_rerun_plan,
    stale_annotations,
    validate_annotation,
    validate_resolution_event,
)
from codex_science.literature_v2 import UnionFind, normalize_identifier, resolve_study_families, validate_risk_of_bias


class CollaborationAndLiteratureV2Tests(unittest.TestCase):
    def test_cli_malformed_annotation_advice_recovers_after_removal(self) -> None:
        from tests.test_discovery_workbench import annotation_fixture

        for content in (None, b"", b"0", b"{", b"[]", b"{}"):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "run"
                manifest, artifact, cli = annotation_fixture(root)
                sidecar = root / "annotations/A1.json"
                sidecar.parent.mkdir()
                if content is None:
                    sidecar.mkdir()
                else:
                    sidecar.write_bytes(content)
                command = cli + ["add", "--id", "A1", "--author", "reviewer", "--text", "Check the claim",
                                 "--artifact", "result.json", "--json-pointer", "/answer"]
                timeout = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120"))
                before = {path: path.read_bytes() if path.is_file() else None
                          for path in (manifest, artifact, sidecar)}
                for _ in range(2):
                    refused = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
                    self.assertEqual(2, refused.returncode, refused.stderr)
                    self.assertIn("unregistered annotation sidecar exists: annotations/A1.json", refused.stderr)
                    self.assertIn("remove it or repair the file", refused.stderr)
                    self.assertNotIn("identical content", refused.stderr)
                    self.assertEqual(before, {path: path.read_bytes() if path.is_file() else None
                                              for path in (manifest, artifact, sidecar)})
                sidecar.rmdir() if content is None else sidecar.unlink()
                recovered = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
                self.assertEqual(0, recovered.returncode, recovered.stderr)
                self.assertEqual("A1", json.loads(recovered.stdout)[0]["annotation_id"])
                self.assertIn("annotations/A1.json", {row["path"] for row in json.loads(manifest.read_text())["artifacts"]})

    def annotation_run(self, root: Path) -> Path:
        from tests.test_discovery_workbench import add_fixture_annotation, annotation_fixture

        manifest, _, cli = annotation_fixture(root / "run")
        result = add_fixture_annotation(cli, annotation_id="A-1")
        self.assertEqual(0, result.returncode, result.stderr)
        return manifest.parent

    def test_resolution_append_repairs_missing_final_newline(self) -> None:
        script = Path(__file__).resolve().parents[1] / "scripts/annotate_run.py"
        with tempfile.TemporaryDirectory() as temporary:
            root = self.annotation_run(Path(temporary))
            ledger = root / "annotations/resolutions.jsonl"
            ledger.touch()
            for status in ("resolved", "dismissed", "resolved"):
                with self.subTest(status=status):
                    if status == "dismissed":
                        ledger.write_bytes(ledger.read_bytes().removesuffix(b"\n"))
                    result = subprocess.run(
                        [sys.executable, str(script), str(root), "resolve", "--id", "A-1",
                         "--status", status, "--resolver", "reviewer"], capture_output=True, text=True,
                    )
                    self.assertEqual(0, result.returncode, result.stderr)
                    listed = subprocess.run([sys.executable, str(script), str(root), "list"],
                                            capture_output=True, text=True)
                    self.assertEqual(0, listed.returncode, listed.stderr)
                    self.assertEqual(status, json.loads(listed.stdout)[0]["status"])
            self.assertEqual(["resolved", "dismissed", "resolved"],
                             [event["status"] for event in load_resolution_events(root)])
            self.assertTrue(ledger.read_bytes().endswith(b"\n"))

    def test_annotation_enum_types_have_labelled_validation_errors(self) -> None:
        script = Path(__file__).resolve().parents[1] / "scripts/annotate_run.py"
        with tempfile.TemporaryDirectory() as temporary:
            root = self.annotation_run(Path(temporary))
            annotation_path = root / "annotations/A-1.json"
            original = json.loads(annotation_path.read_text())
            manifest_path = root / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            for field in ("type", "status"):
                for value in ([], {}, None, 0, "", "unknown"):
                    with self.subTest(field=field, value=value):
                        invalid = {**original, field: value}
                        with self.assertRaisesRegex(ValueError, f"invalid annotation {field}"):
                            validate_annotation(invalid)
                        annotation_path.write_text(json.dumps(invalid))
                        for entry in manifest["artifacts"]:
                            if entry["path"] == "annotations/A-1.json":
                                entry["sha256"] = hashlib.sha256(annotation_path.read_bytes()).hexdigest()
                        manifest_path.write_text(json.dumps(manifest))
                        result = subprocess.run([sys.executable, str(script), str(root), "list"],
                                                capture_output=True, text=True)
                        self.assertEqual(2, result.returncode, result.stderr)
                        self.assertIn(f"invalid annotation {field}", result.stderr)
                        self.assertNotIn("Traceback", result.stderr)
            for value in ([], {}, None, 0, "", "unknown"):
                with self.subTest(resolution_status=value):
                    with self.assertRaisesRegex(ValueError, "invalid resolution status"):
                        append_resolution_event(root, {**self.resolution_payload(), "status": value})
            self.assertFalse((root / "annotations/resolutions.jsonl").exists())

    def test_input_hash_and_explicit_identity_collisions_remain_distinct(self) -> None:
        unidentified = {"release": "v1", "source": "catalog"}
        digest = hashlib.sha256(json.dumps(unidentified, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        explicit = {"identifier": digest, "release": "v2"}
        empty = {"added": [], "removed": [], "changed": []}
        for inputs in ([unidentified, explicit], [explicit, unidentified]):
            with self.subTest(inputs=inputs):
                report = diff_runs({"inputs": inputs}, {"inputs": [explicit]})
                self.assertEqual({**empty, "removed": [digest]}, report["inputs"])
                self.assertTrue(report["review_invalidated"])
                report = diff_runs({"inputs": [explicit]}, {"inputs": inputs})
                self.assertEqual({**empty, "added": [digest]}, report["inputs"])
                self.assertTrue(report["review_invalidated"])
                report = diff_runs({"inputs": inputs}, {"inputs": list(reversed(inputs))})
                self.assertEqual(empty, report["inputs"])
                self.assertFalse(report["review_invalidated"])
        report = diff_runs({}, {"inputs": [unidentified, explicit]})
        self.assertEqual([digest, digest], report["inputs"]["added"])

    @staticmethod
    def annotation_payload() -> dict:
        return {
            "schema_version": 1, "annotation_id": "A-1", "author": "reviewer", "type": "note",
            "text": "Check this.", "status": "open", "created_at": "2026-07-19T00:00:00Z",
            "anchor": {"artifact_path": "metrics.json", "artifact_sha256": "a" * 64, "claim_id": "C1"},
        }

    @staticmethod
    def resolution_payload() -> dict:
        return {
            "schema_version": 1, "annotation_id": "A-1", "status": "resolved", "resolver": "reviewer",
            "resolved_at": "2026-07-20T00:00:00Z", "artifact_sha256": "a" * 64, "note": "checked",
        }

    def test_annotation_validation_reports_invalid_field_and_preserves_input(self) -> None:
        valid = self.annotation_payload()
        validate_annotation(valid)
        cases = (
            ({"schema_version": 2}, "unsupported annotation schema"),
            ({**valid, "annotation_id": " "}, "annotation annotation_id is required"),
            ({**valid, "author": " "}, "annotation author is required"),
            ({**valid, "text": " "}, "annotation text is required"),
            ({**valid, "created_at": " "}, "annotation created_at is required"),
            ({**valid, "type": "other"}, "invalid annotation type"),
            ({**valid, "status": "other"}, "invalid annotation status"),
            ({**valid, "anchor": []}, "annotation anchor must be an object"),
            ({**valid, "anchor": {**valid["anchor"], "artifact_path": " "}}, "annotation artifact_path is required"),
            ({**valid, "anchor": {**valid["anchor"], "artifact_sha256": "0"}}, "annotation artifact_sha256 must be a SHA-256 digest"),
            ({**valid, "anchor": {"artifact_path": "metrics.json", "artifact_sha256": "a" * 64}},
             "annotation anchor needs json_pointer, claim_id, or line_range"),
        )
        for invalid, message in cases:
            with self.subTest(message=message):
                before = deepcopy(invalid)
                with self.assertRaisesRegex(ValueError, message):
                    validate_annotation(invalid)
                self.assertEqual(before, invalid)

    def test_resolution_validation_rejects_each_invalid_contract_without_mutation(self) -> None:
        valid = self.resolution_payload()
        validate_resolution_event(valid)
        cases = (
            (None, "unsupported resolution event schema"),
            ({**valid, "schema_version": 2}, "unsupported resolution event schema"),
            ({**valid, "annotation_id": " "}, "resolution annotation_id is required"),
            ({**valid, "resolver": " "}, "resolution resolver is required"),
            ({**valid, "resolved_at": " "}, "resolution resolved_at is required"),
            ({**valid, "status": "open"}, "invalid resolution status"),
            ({**valid, "artifact_sha256": "bad"}, "resolution artifact_sha256 must be a SHA-256 digest"),
            ({**valid, "note": 1}, "resolution note must be a string"),
        )
        for invalid, message in cases:
            with self.subTest(message=message):
                before = None if invalid is None else dict(invalid)
                with self.assertRaisesRegex(ValueError, message):
                    validate_resolution_event(invalid)
                self.assertEqual(before, invalid)

    def test_resolution_lock_read_and_write_boundaries_and_refusals(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "fresh"
            root.mkdir()
            with annotation_resolution_lock(root, exclusive=False):
                pass
            self.assertFalse((root / "annotations").exists())
            with annotation_resolution_lock(root):
                self.assertTrue((root / "annotations/.resolutions.lock").is_file())
            self.assertEqual(0o644, (root / "annotations/.resolutions.lock").stat().st_mode & 0o777)

            target = Path(temporary) / "target"
            target.mkdir()
            fifo_root = Path(temporary) / "fifo-run"
            (fifo_root / "annotations").mkdir(parents=True)
            Path(fifo_root / "annotations/.resolutions.lock").symlink_to(target)
            with self.assertRaises(OSError):
                with annotation_resolution_lock(fifo_root, exclusive=False):
                    pass
            (fifo_root / "annotations/.resolutions.lock").unlink()
            os.mkfifo(fifo_root / "annotations/.resolutions.lock")
            with self.assertRaisesRegex(ValueError, "resolution lock must be a regular file"):
                with annotation_resolution_lock(fifo_root):
                    pass

            (root / "annotations").rename(root / "annotations_saved")
            (root / "annotations").symlink_to(target, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "annotation directory must not be a symlink"):
                with annotation_resolution_lock(root):
                    pass
            self.assertEqual([], list(target.iterdir()))

            absent = Path(temporary) / "absent"
            absent.mkdir()
            with annotation_resolution_lock(absent, exclusive=False):
                pass
            self.assertFalse((absent / "annotations").exists())

            unlocked = Path(temporary) / "unlocked"
            (unlocked / "annotations").mkdir(parents=True)
            with annotation_resolution_lock(unlocked, exclusive=False):
                pass
            self.assertEqual([], list((unlocked / "annotations").iterdir()))

    def test_resolution_ledger_read_append_and_refusal_paths(self) -> None:
        event = self.resolution_payload()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run"
            root.mkdir()
            self.assertEqual([], load_resolution_events(root))
            with self.assertRaisesRegex(ValueError, "resolution artifact_sha256"):
                append_resolution_event(root, {**event, "artifact_sha256": "bad"})
            self.assertFalse((root / "annotations").exists())

            with annotation_resolution_lock(root):
                append_resolution_event(root, event, lock_held=True)
                self.assertEqual([event], load_resolution_events(root, lock_held=True))
            ledger = root / "annotations/resolutions.jsonl"
            self.assertEqual([event], load_resolution_events(root))
            self.assertEqual(0o644, ledger.stat().st_mode & 0o777)
            append_resolution_event(root, {**event, "status": "dismissed", "note": "second"})
            self.assertEqual(2, len(load_resolution_events(root)))

            ledger.write_text("not-json\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid resolution event at line 1"):
                load_resolution_events(root)
            ledger.write_text("[]\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "resolution event at line 1 must be an object"):
                load_resolution_events(root)

            ledger.unlink()
            ledger.mkdir()
            with self.assertRaisesRegex(ValueError, "resolution event sidecar must be a regular file"):
                load_resolution_events(root)
            ledger.rmdir()
            outside = Path(temporary) / "outside.jsonl"
            outside.write_text("sentinel", encoding="utf-8")
            ledger.symlink_to(outside)
            with self.assertRaisesRegex(ValueError, "resolution event sidecar must not be a symlink"):
                load_resolution_events(root)
            self.assertEqual("sentinel", outside.read_text(encoding="utf-8"))

            lock_link_root = Path(temporary) / "lock-link"
            (lock_link_root / "annotations").mkdir(parents=True)
            (lock_link_root / "annotations/.resolutions.lock").symlink_to(outside)
            with self.assertRaisesRegex(ValueError, "resolution lock must not be a symlink"):
                load_resolution_events(lock_link_root)

            directory_link_root = Path(temporary) / "directory-link"
            directory_link_root.mkdir()
            (directory_link_root / "annotations").symlink_to(root / "annotations", target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "resolution event directory must not be a symlink"):
                load_resolution_events(directory_link_root)

    def test_resolution_fold_preserves_history_latest_wins_and_stale_anchor(self) -> None:
        annotation = {
            "schema_version": 1, "annotation_id": "A-1", "author": "reviewer", "type": "note",
            "text": "Check this.", "status": "open", "created_at": "2026-07-19T00:00:00Z",
            "anchor": {"artifact_path": "metrics.json", "artifact_sha256": "a" * 64, "claim_id": "C1"},
        }
        first = {"schema_version": 1, "annotation_id": "A-1", "status": "resolved", "resolver": "R",
                 "resolved_at": "2026-07-20T00:00:00Z", "artifact_sha256": "a" * 64, "note": "checked"}
        second = {**first, "status": "dismissed", "resolved_at": "2026-07-21T00:00:00Z", "note": "duplicate"}
        result = fold_annotation_resolutions([annotation], [first, second], {"metrics.json": "a" * 64})[0]
        self.assertEqual("dismissed", result["status"])
        self.assertEqual("duplicate", result["latest_resolution"]["note"])
        stale = fold_annotation_resolutions([annotation], [first, second], {"metrics.json": "b" * 64})[0]
        self.assertEqual("stale-anchor", stale["status"])
        old_anchor_event = fold_annotation_resolutions(
            [annotation], [{**first, "artifact_sha256": "b" * 64}], {"metrics.json": "a" * 64}
        )[0]
        self.assertEqual("stale-anchor", old_anchor_event["status"])
        self.assertEqual("b" * 64, old_anchor_event["latest_resolution"]["artifact_sha256"])
        with self.assertRaisesRegex(ValueError, "invalid resolution status"):
            fold_annotation_resolutions([annotation], [{**first, "status": "open"}], {"metrics.json": "a" * 64})
        self.assertEqual(2, len(fold_annotation_resolutions([annotation, annotation], [], {"metrics.json": "a" * 64})))
        with self.assertRaisesRegex(ValueError, "annotation IDs must be unique"):
            fold_annotation_resolutions([annotation, annotation], [first], {"metrics.json": "a" * 64})

    def test_annotations_diff_and_selective_rerun_are_hash_aware(self) -> None:
        annotation = {
            "schema_version": 1,
            "annotation_id": "A-1",
            "author": "reviewer",
            "type": "question",
            "text": "Check this metric.",
            "status": "open",
            "created_at": "2026-07-19T00:00:00Z",
            "anchor": {"artifact_path": "metrics.json", "artifact_sha256": "a" * 64, "json_pointer": "/metrics/0"},
        }
        self.assertEqual("open", stale_annotations([annotation], {"metrics.json": "a" * 64})[0]["status"])
        self.assertEqual("stale-anchor", stale_annotations([annotation], {"metrics.json": "b" * 64})[0]["status"])
        previous = {"run_id": "old", "artifacts": [{"path": "metrics.json", "sha256": "a" * 64}], "claims": [{"id": "C1", "text": "old"}], "code": [], "environment": {}}
        current = {"run_id": "new", "artifacts": [{"path": "metrics.json", "sha256": "b" * 64}], "claims": [{"id": "C1", "text": "new"}], "code": [], "environment": {}}
        report = diff_runs(previous, current)
        self.assertEqual(["metrics.json"], report["artifacts"]["changed"])
        self.assertTrue(report["review_invalidated"])
        plan = selective_rerun_plan(
            changed_nodes=["metrics"],
            edges=[{"source": "metrics", "target": "claim", "relation": "supports"}],
            steps=[{"id": "compute", "consumes": [], "produces": ["metrics"]}, {"id": "synthesize", "consumes": ["claim"], "produces": ["report"]}],
            review_paths=["review.json"],
        )
        self.assertIn("claim", plan["impacted_nodes"])
        self.assertEqual(["review.json"], plan["invalidated_review_receipts"])

    def test_selective_rerun_closes_step_and_graph_chains_in_input_order(self) -> None:
        steps = [
            {"id": "s4", "consumes": ["claim"], "requires_approval": True},
            {"id": "s3", "consumes": ["Z"], "produces": ["report"]},
            {"id": "s2", "consumes": ["Y"], "produces": ["Z"]},
            {"id": "unrelated", "consumes": ["other"], "produces": ["unused"]},
            {"id": "s1", "consumes": ["D"], "produces": ["Y"]},
            {"id": "empty", "consumes": [], "produces": []},
        ]
        edges = [{"source": "Z", "target": "claim", "relation": "supports"}]
        original = deepcopy(steps)
        for changed in ([], ["0"], ["D", "D"]):
            with self.subTest(changed=changed):
                plan = selective_rerun_plan(
                    changed_nodes=changed, edges=edges, steps=steps,
                    review_paths=iter(["review.json", "review.json"]),
                )
                self.assertEqual(sorted(set(changed)), plan["changed_nodes"])
                if "D" in changed:
                    self.assertEqual(["D", "Y", "Z", "claim", "report"], plan["impacted_nodes"])
                    self.assertEqual(["s4", "s3", "s2", "s1"], [step["id"] for step in plan["rerun_steps"]])
                    self.assertEqual(["report"], plan["rerun_steps"][1]["produces"])
                    self.assertTrue(plan["approval_required"])
                else:
                    self.assertEqual(changed, plan["impacted_nodes"])
                    self.assertEqual([], plan["rerun_steps"])
                    self.assertFalse(plan["approval_required"])
                self.assertEqual(["review.json"] if changed else [], plan["invalidated_review_receipts"])
                self.assertEqual(plan, selective_rerun_plan(
                    changed_nodes=iter(changed), edges=edges, steps=iter(steps),
                    review_paths=iter(["review.json", "review.json"]),
                ))
        self.assertEqual(original, steps)

    def test_selective_rerun_visits_chain_steps_once(self) -> None:
        class CountedStep(dict):
            reads = 0

            def get(self, key, default=None):
                type(self).reads += 1
                return super().get(key, default)

        for size in (0, 1, 256):
            with self.subTest(size=size):
                CountedStep.reads = 0
                steps = [CountedStep(id=i, consumes=[str(i)], produces=[str(i + 1)])
                         for i in reversed(range(size))]
                plan = selective_rerun_plan(changed_nodes=["0"], edges=[], steps=steps)
                self.assertEqual([str(i) for i in sorted(range(size + 1), key=str)], plan["impacted_nodes"])
                self.assertEqual(list(reversed(range(size))), [step["id"] for step in plan["rerun_steps"]])
                self.assertLessEqual(CountedStep.reads, 8 * size)

    def test_selective_rerun_cli_reaches_real_shape_dependencies_and_step_outputs(self) -> None:
        root = Path(__file__).resolve().parents[1]
        graph = {
            "nodes": [
                {"id": node, "type": node}
                for node in ("dataset", "study", "claim", "portal")
            ],
            "edges": [
                {"source": "study", "target": "dataset", "relation": "depends_on"},
                {"source": "study", "target": "claim", "relation": "supports"},
                {"source": "portal", "target": "study", "relation": "propagated_from"},
            ],
        }
        steps = [
            {"id": "publish", "consumes": ["summary"], "produces": ["report"], "requires_approval": True},
            {"id": "summarize", "consumes": ["claim", "portal"], "produces": ["summary"]},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            graph_path = Path(tmp) / "graph.json"
            steps_path = Path(tmp) / "steps.json"
            steps_path.write_text(json.dumps({"steps": steps}), encoding="utf-8")
            for version in (1, 2):
                with self.subTest(schema_version=version):
                    graph_path.write_text(json.dumps({**graph, "schema_version": version}), encoding="utf-8")
                    proc = subprocess.run(
                        [sys.executable, str(root / "scripts" / "plan_selective_rerun.py"),
                         str(graph_path), str(steps_path), "--changed", "dataset", "--review-path", "review.json"],
                        capture_output=True, text=True,
                    )
                    self.assertEqual(0, proc.returncode, proc.stderr)
                    plan = json.loads(proc.stdout)
                    self.assertEqual(["dataset"], plan["changed_nodes"])
                    self.assertEqual(["claim", "dataset", "portal", "report", "study", "summary"], plan["impacted_nodes"])
                    self.assertEqual(["publish", "summarize"], [step["id"] for step in plan["rerun_steps"]])
                    self.assertEqual(["review.json"], plan["invalidated_review_receipts"])
                    self.assertTrue(plan["approval_required"])

    def test_claim_identity_changes_invalidate_review(self) -> None:
        claim = {"id": "C1", "text": "Claim"}
        for previous, current, added, removed in (([], [claim], ["C1"], []), ([claim], [], [], ["C1"])):
            with self.subTest(previous=previous, current=current):
                report = diff_runs({"claims": previous}, {"claims": current})
                self.assertTrue(report["review_invalidated"])
                self.assertEqual({"added": added, "removed": removed, "changed": []}, report["claims"])
        self.assertFalse(diff_runs({"claims": []}, {"claims": []})["review_invalidated"])

    def test_artifact_record_metadata_changes_invalidate_review(self) -> None:
        original = {"path": "metrics.json", "sha256": "a" * 64, "kind": "metrics"}
        for field, value in (("kind", "data"), ("size_bytes", 0), ("description", ""), ("result", False)):
            with self.subTest(field=field):
                updated = {**original, field: value}
                for previous, current in ((original, updated), (updated, original)):
                    report = diff_runs({"artifacts": [previous]}, {"artifacts": [current]})
                    self.assertEqual(["metrics.json"], report["artifacts"]["changed"])
                    self.assertTrue(report["review_invalidated"])
        typed = {**original, "result": 0}
        report = diff_runs({"artifacts": [typed]}, {"artifacts": [{**typed, "result": False}]})
        self.assertTrue(report["review_invalidated"])
        self.assertFalse(diff_runs({"artifacts": [original]}, {"artifacts": [dict(reversed(list(original.items())))]})["review_invalidated"])

    def test_diff_runs_rejects_duplicate_artifact_paths(self) -> None:
        previous = {"artifacts": [
            {"path": "metrics.json", "sha256": "a" * 64},
            {"path": "metrics.json", "sha256": "b" * 64},
        ]}
        current = deepcopy(previous)
        current["artifacts"][0]["sha256"] = "c" * 64
        for old, new in ((previous, current), ({}, current), (previous, {})):
            with self.subTest(previous=old, current=new):
                with self.assertRaisesRegex(ValueError, "duplicate artifact path: metrics.json"):
                    diff_runs(old, new)

    def test_diff_runs_rejects_invalid_and_duplicate_claim_ids(self) -> None:
        cases = [([{"text": "first"}, {"text": "second"}], "claim id must be a non-empty string")]
        for value in (None, "", " ", 0, 7, False, [], {}):
            cases.append(([{"id": value}], "claim id must be a non-empty string"))
        cases.append(([{"id": "C1"}, {"id": "C1", "text": "other"}], "duplicate claim id: C1"))
        for claims, message in cases:
            manifest = {"claims": claims}
            for old, new in ((manifest, {}), ({}, manifest)):
                with self.subTest(claims=claims, previous=old):
                    with self.assertRaisesRegex(ValueError, message):
                        diff_runs(old, new)

    def test_diff_runs_rejects_malformed_manifests(self) -> None:
        cases = [(value, "manifest must be an object") for value in ([], None, 0, "")]
        for section in ("artifacts", "claims", "inputs"):
            for value in (None, {}, "", 0):
                cases.append(({section: value}, f"manifest {section} must be a list"))
            for value in (None, [], 0, ""):
                cases.append(({section: [value]}, f"manifest {section} records must be objects"))
        for field in ("path", "sha256"):
            valid = {"path": "metrics.json", "sha256": "a" * 64}
            missing = dict(valid)
            del missing[field]
            cases.append(({"artifacts": [missing]}, f"artifact {field} must be a non-empty string"))
            for value in (None, "", " ", 0, [], {}):
                cases.append(({"artifacts": [{**valid, field: value}]},
                              f"artifact {field} must be a non-empty string"))
        for invalid, message in cases:
            for old, new in ((invalid, {}), ({}, invalid)):
                with self.subTest(invalid=invalid, previous=old):
                    before = deepcopy((old, new))
                    with self.assertRaisesRegex(ValueError, message):
                        diff_runs(old, new)
                    self.assertEqual(before, (old, new))

    def test_diff_runs_reports_inputs_and_preserves_existing_output(self) -> None:
        empty = {"added": [], "removed": [], "changed": []}
        self.assertEqual({
            "schema_version": 1, "previous_run_id": None, "current_run_id": None,
            "artifacts": empty, "claims": empty, "inputs": empty,
            "code_changed": False, "environment_changed": False, "review_invalidated": False,
        }, diff_runs({}, {}))
        inputs = [
            {"identifier": "dataset", "url": "https://example.org/data", "path": "data.csv", "release": "v1"},
            {"url": "https://example.org/other", "path": "other.csv", "sha256": "a" * 64},
            {"path": "local.csv", "query": "old"},
        ]
        for index, field, value, identity in (
            (0, "release", "v2", "dataset"),
            (0, "url", "https://example.org/new", "dataset"),
            (1, "sha256", "b" * 64, "https://example.org/other"),
            (1, "path", "new.csv", "https://example.org/other"),
            (2, "query", "new", "local.csv"),
        ):
            previous = {"inputs": deepcopy(inputs)}
            current = deepcopy(previous)
            current["inputs"][index][field] = value
            with self.subTest(field=field, identity=identity):
                report = diff_runs(previous, current)
                self.assertEqual({**empty, "changed": [identity]}, report["inputs"])
                self.assertTrue(report["review_invalidated"])
                self.assertEqual(empty, report["artifacts"])
                self.assertEqual(empty, report["claims"])
                self.assertFalse(report["code_changed"])
                self.assertFalse(report["environment_changed"])
                self.assertEqual({**empty, "added": [identity]}, diff_runs({}, {"inputs": [inputs[index]]})["inputs"])
                self.assertTrue(diff_runs({}, {"inputs": [inputs[index]]})["review_invalidated"])
                self.assertEqual({**empty, "removed": [identity]}, diff_runs({"inputs": [inputs[index]]}, {})["inputs"])
                self.assertTrue(diff_runs({"inputs": [inputs[index]]}, {})["review_invalidated"])
        unchanged = {"inputs": list(reversed(inputs)), "claims": [{"id": "C1"}],
                     "artifacts": [{"path": "metrics.json", "sha256": "A" * 64}]}
        report = diff_runs({**unchanged, "inputs": inputs,
                            "artifacts": [{"path": "metrics.json", "sha256": "a" * 64}]}, unchanged)
        self.assertEqual(empty, report["inputs"])
        self.assertFalse(report["review_invalidated"])
        self.assertEqual(sorted(["dataset", "https://example.org/other", "local.csv"]),
                         diff_runs({}, {"inputs": inputs})["inputs"]["added"])
        for record, identity in (({"identifier": "", "url": "source"}, "source"),
                                 ({"identifier": " ", "url": "", "path": "local"}, "local")):
            with self.subTest(fallback=record):
                self.assertEqual([identity], diff_runs({}, {"inputs": [record]})["inputs"]["added"])

    def test_diff_runs_cli_distinguishes_nested_json_types(self) -> None:
        script = Path(__file__).resolve().parents[1] / "scripts" / "diff_runs.py"
        empty = {"added": [], "removed": [], "changed": []}
        cases = [(False, 0, True), (True, 1, True), (1, 1.0, True)]
        cases.extend((value, value, False) for value in (None, False, 0, True, 1, 1.0, "", [], {}))
        with tempfile.TemporaryDirectory() as temporary:
            previous_path = Path(temporary) / "previous.json"
            current_path = Path(temporary) / "current.json"
            for section in ("inputs", "claims", "code", "environment"):
                for before, after, changed in cases:
                    with self.subTest(section=section, before=before, after=after, changed=changed):
                        previous_record = {"id": "record", "parameters": {"values": [before], "source": "caf\u00e9"}}
                        current_record = {"parameters": {"source": "caf\u00e9", "values": [after]}, "id": "record"}
                        previous = {section: previous_record if section == "environment" else [previous_record]}
                        current = {section: current_record if section == "environment" else [current_record]}
                        previous_path.write_text(json.dumps(previous), encoding="utf-8")
                        current_path.write_text(json.dumps(current), encoding="utf-8")
                        result = subprocess.run([sys.executable, str(script), str(previous_path), str(current_path)],
                                                capture_output=True, text=True, check=False)
                        self.assertEqual(0, result.returncode, result.stderr)
                        self.assertEqual("", result.stderr)
                        expected = {
                            "schema_version": 1, "previous_run_id": None, "current_run_id": None,
                            "artifacts": empty, "claims": empty, "inputs": empty,
                            "code_changed": False, "environment_changed": False, "review_invalidated": changed,
                        }
                        if section in ("inputs", "claims"):
                            expected[section] = {**empty, "changed": ["record"] if changed else []}
                        else:
                            expected[f"{section}_changed"] = changed
                        self.assertEqual(expected, json.loads(result.stdout))

    def test_diff_runs_rejects_duplicate_explicit_input_ids(self) -> None:
        cases = []
        for field in ("identifier", "id", "query_id", "url", "path"):
            cases.append(([{field: "data"}, {field: "data", "release": "v2"}], "duplicate input identity: data"))
        cases.append(([{"identifier": "data"}, {"path": "data"}], "duplicate input identity: data"))
        for inputs, message in cases:
            for old, new in (({"inputs": inputs}, {}), ({}, {"inputs": inputs})):
                with self.subTest(inputs=inputs, previous=old):
                    with self.assertRaisesRegex(ValueError, message):
                        diff_runs(old, new)

    def test_diff_runs_accepts_real_input_shapes_and_canonical_fallback(self) -> None:
        import hashlib

        inputs = [
            {"accessed_at": "2026-10-28", "query": "query", "query_id": "Q1",
             "response_sha256": "a" * 64, "source": "catalog", "status": "complete"},
            {"accessed_at": "2026-10-28", "id": "I1", "license": "CC0", "source": "catalog"},
            {"id": "I2", "release": "v1", "sha256": "b" * 64, "snapshot": "snapshot", "source": "catalog"},
            {"query_ledger": "queries.jsonl", "release": "v1", "source": "catalog"},
            {"release": "v1", "source": "catalog"},
        ]
        empty = {"added": [], "removed": [], "changed": []}
        self.assertEqual(empty, diff_runs({"inputs": inputs}, {"inputs": inputs})["inputs"])
        self.assertFalse(diff_runs({"inputs": inputs}, {"inputs": inputs})["review_invalidated"])
        for index in (2, 3, 4):
            current = deepcopy(inputs)
            current[index]["release"] = "v2"
            report = diff_runs({"inputs": inputs}, {"inputs": current})
            with self.subTest(shape=index):
                self.assertTrue(report["review_invalidated"])
                if index == 2:
                    self.assertEqual({**empty, "changed": ["I2"]}, report["inputs"])
                else:
                    old_key = hashlib.sha256(json.dumps(inputs[index], sort_keys=True, separators=(",", ":"),
                                                       ensure_ascii=False).encode("utf-8")).hexdigest()
                    new_key = hashlib.sha256(json.dumps(current[index], sort_keys=True, separators=(",", ":"),
                                                       ensure_ascii=False).encode("utf-8")).hexdigest()
                    self.assertEqual({"added": [new_key], "removed": [old_key], "changed": []}, report["inputs"])
        for record in ({}, {"release": "v1"}, {"identifier": "", "id": " ", "query_id": 0},
                       {"url": [], "path": None}, {"source": "caf\u00e9", "release": "v1"}):
            reordered = dict(reversed(list(record.items())))
            with self.subTest(unidentified=record):
                report = diff_runs({"inputs": [record]}, {"inputs": [record, reordered]})
                self.assertEqual(empty, report["inputs"])
                self.assertFalse(report["review_invalidated"])
                self.assertEqual(1, len(diff_runs({}, {"inputs": [record, reordered]})["inputs"]["added"]))
        identities = {"identifier": "primary", "id": "secondary", "query_id": "query", "url": "url", "path": "path"}
        for field, identity in list(identities.items()):
            with self.subTest(precedence=field):
                self.assertEqual([identity], diff_runs({}, {"inputs": [dict(identities)]})["inputs"]["added"])
                del identities[field]

    def test_diff_runs_cli_clean_error_exit_and_output(self) -> None:
        script = Path(__file__).resolve().parents[1] / "scripts" / "diff_runs.py"
        with tempfile.TemporaryDirectory() as temporary:
            previous = Path(temporary) / "previous.json"
            current = Path(temporary) / "current.json"
            output = Path(temporary) / "diff.json"
            previous.write_text("{}", encoding="utf-8")
            invalid = [
                ([], "manifest must be an object"),
                ({"artifacts": [{"path": "metrics.json"}]}, "artifact sha256 must be a non-empty string"),
                ({"artifacts": [{"path": "metrics.json", "sha256": "a" * 64}] * 2},
                 "duplicate artifact path: metrics.json"),
                ({"claims": [{"text": "claim"}]}, "claim id must be a non-empty string"),
                ({"claims": [{"id": "C1"}] * 2}, "duplicate claim id: C1"),
                ({"inputs": [{"path": "data"}, {"path": "data"}]}, "duplicate input identity: data"),
            ]
            for manifest, message in invalid:
                for bad_path, good_path in ((current, previous), (previous, current)):
                    good_path.write_text("{}", encoding="utf-8")
                    bad_path.write_text(json.dumps(manifest), encoding="utf-8")
                    output.write_text("existing report\n", encoding="utf-8")
                    with self.subTest(manifest=manifest, bad_path=bad_path.name):
                        result = subprocess.run([sys.executable, str(script), str(previous), str(current),
                                                 "--output", str(output)], capture_output=True, text=True, check=False)
                        self.assertEqual(1, result.returncode)
                        self.assertEqual(f"error: {message}\n", result.stderr)
                        self.assertEqual("", result.stdout)
                        self.assertEqual("existing report\n", output.read_text(encoding="utf-8"))
            previous.write_text("{}", encoding="utf-8")
            for malformed in ("", "{", "\xff"):
                current.write_bytes(malformed.encode("latin-1"))
                result = subprocess.run([sys.executable, str(script), str(previous), str(current)],
                                        capture_output=True, text=True, check=False)
                self.assertEqual(1, result.returncode)
                self.assertTrue(result.stderr.startswith("error: "), result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual("", result.stdout)
            current.unlink()
            result = subprocess.run([sys.executable, str(script), str(previous), str(current)],
                                    capture_output=True, text=True, check=False)
            self.assertEqual(1, result.returncode)
            self.assertTrue(result.stderr.startswith("error: "), result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            current.write_text('{"inputs": [{"path": "data", "release": "v2"}]}', encoding="utf-8")
            for options in ([], ["--output", str(output)]):
                result = subprocess.run([sys.executable, str(script), str(previous), str(current), *options],
                                        capture_output=True, text=True, check=False)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual("", result.stderr)
                report = json.loads(output.read_text(encoding="utf-8") if options else result.stdout)
                self.assertEqual(["data"], report["inputs"]["added"])
                self.assertTrue(report["review_invalidated"])
            result = subprocess.run([sys.executable, str(script), str(previous), str(current),
                                     "--output", temporary], capture_output=True, text=True, check=False)
            self.assertEqual(1, result.returncode)
            self.assertTrue(result.stderr.startswith("error: "), result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual("", result.stdout)

    def test_diff_runs_project_store_reports_accepted_legacy_manifest_errors(self) -> None:
        from codex_science.artifacts import write_manifest
        from codex_science.project_store import ProjectStore
        from tests.test_project_store import make_run

        cases = (
            ("claims", [{"id": 7, "text": "legacy"}], "claim id must be a non-empty string"),
            ("inputs", [{"identifier": "data"}, {"identifier": "data"}], "duplicate input identity: data"),
        )
        for field, records, message in cases:
            with self.subTest(field=field, records=records), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                manifest_path, _ = make_run(root, "legacy", "Claim", 0.5)
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest[field] = records
                write_manifest(manifest, manifest_path)
                original = manifest_path.read_bytes()
                store = ProjectStore(root / "project.sqlite")
                store.create_project(project_id="project", title="Legacy", question="Compare?")
                store.import_run(project_id="project", manifest_path=manifest_path)
                store.fork_branch(project_id="project", source_run_id="legacy", branch_name="fork")
                before = store.summary(project_id="project")
                with self.assertRaisesRegex(ValueError, message):
                    store.compare_runs(project_id="project", previous_run_id="legacy", current_run_id="legacy")
                with self.assertRaisesRegex(ValueError, message):
                    store.prepare_merge_plan(project_id="project", source_branch="fork", target_branch="main")
                self.assertEqual(before, store.summary(project_id="project"))
                self.assertEqual(original, manifest_path.read_bytes())

    def test_diff_runs_project_store_accepts_unidentified_inputs(self) -> None:
        from codex_science.artifacts import write_manifest
        from codex_science.project_store import ProjectStore
        from tests.test_project_store import make_run

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path, _ = make_run(root, "legacy", "Claim", 0.5)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["inputs"] = [{"source": "catalog", "release": "v1"}] * 2
            write_manifest(manifest, manifest_path)
            original = manifest_path.read_bytes()
            store = ProjectStore(root / "project.sqlite")
            store.create_project(project_id="project", title="Legacy", question="Compare?")
            store.import_run(project_id="project", manifest_path=manifest_path)
            store.fork_branch(project_id="project", source_run_id="legacy", branch_name="fork")
            report = store.compare_runs(project_id="project", previous_run_id="legacy", current_run_id="legacy")
            self.assertFalse(report["review_invalidated"])
            self.assertEqual({"added": [], "removed": [], "changed": []}, report["inputs"])
            plan = store.prepare_merge_plan(project_id="project", source_branch="fork", target_branch="main")
            self.assertFalse(plan["review_receipts_invalidated"])
            self.assertEqual(original, manifest_path.read_bytes())

    def test_namespace_safe_identifiers_and_union_find_study_families(self) -> None:
        self.assertEqual("doi:10.1000/abc", normalize_identifier("https://doi.org/10.1000/ABC"))
        self.assertEqual("pmid:12345678", normalize_identifier("PMID:12345678"))
        for raw, expected in (
            ("math.GT/0309136", "arxiv:math/0309136"),
            ("cond-mat.stat-mech/0101001", "arxiv:cond-mat/0101001"),
            ("physics.bio-ph/0412001", "arxiv:physics/0412001"),
            ("q-bio.PE/0601001", "arxiv:q-bio/0601001"),
            ("hep-th/9901001", "arxiv:hep-th/9901001"),
        ):
            with self.subTest(identifier=raw):
                self.assertEqual(expected, normalize_identifier("arxiv:" + raw))
        records = [
            {"study_id": "preprint", "persistent_ids": ["arxiv:2607.12345", "doi:10.1000/abc"], "publication_state": "preprint", "relationships": [{"type": "published_as", "target_study_id": "article"}]},
            {"study_id": "article", "persistent_ids": ["doi:10.1000/abc", "pmid:12345678"], "publication_state": "peer-reviewed", "relationships": []},
            {"study_id": "correction", "persistent_ids": ["pmid:87654321"], "publication_state": "corrected-peer-reviewed", "relationships": [{"type": "corrected_by", "target_study_id": "article"}]},
        ]
        families = resolve_study_families(records)
        self.assertEqual(1, len(families))
        self.assertEqual("correction", families[0]["canonical_study_id"])
        self.assertIn("doi:10.1000/abc", families[0]["persistent_ids"])

    def test_study_families_handle_deep_unions_without_recursion(self) -> None:
        size = 1100
        records = [{"study_id": str(i), "doi": "10.1000/shared"} for i in range(size)]
        families = resolve_study_families(records)
        self.assertEqual(1, len(families))
        self.assertEqual(sorted(str(i) for i in range(size)), families[0]["study_ids"])
        self.assertEqual(resolve_study_families(records[:1])[0]["family_id"], families[0]["family_id"])
        balanced = UnionFind(str(i) for i in range(size))
        for i in range(1, size):
            balanced.union(str(i), str(i - 1))
        for value in balanced.parent:
            depth, node = 0, value
            while balanced.parent[node] != node:
                depth, node = depth + 1, balanced.parent[node]
            self.assertLessEqual(depth, size.bit_length())
        union = UnionFind(str(i) for i in range(size))
        for i in range(size - 1):
            union.parent[str(i)] = str(i + 1)
        self.assertEqual(str(size - 1), union.find("0"))
        self.assertTrue(all(parent == str(size - 1) for parent in union.parent.values()))

    def test_study_families_reject_duplicate_ids_without_losing_unique_records(self) -> None:
        first = {"study_id": "S1", "persistent_id": "doi:10.1000/one"}
        second = {"study_id": "S2", "persistent_id": "doi:10.1000/two"}
        expected = [
            {"family_id": "family-21bf2304857a65fa6cc8", "canonical_study_id": "S1",
             "study_ids": ["S1"], "persistent_ids": ["doi:10.1000/one"], "publication_states": ["unknown"]},
            {"family_id": "family-528fa5db9d12b5361c9d", "canonical_study_id": "S2",
             "study_ids": ["S2"], "persistent_ids": ["doi:10.1000/two"], "publication_states": ["unknown"]},
        ]
        self.assertEqual([], resolve_study_families([]))
        self.assertEqual(expected[:1], resolve_study_families([first]))
        records = [first, second]
        original = deepcopy(records)
        self.assertEqual(expected, resolve_study_families(records))
        self.assertEqual(expected, resolve_study_families(list(reversed(records))))
        linked = resolve_study_families([first, {**first, "study_id": "S2"}])
        self.assertEqual(["S1", "S2"], linked[0]["study_ids"])
        for duplicate in (dict(first), {**first, "persistent_id": "doi:10.1000/other"}):
            with self.subTest(duplicate=duplicate):
                with self.assertRaisesRegex(ValueError, r"duplicate study_id.*S1"):
                    resolve_study_families([first, second, duplicate])
        self.assertEqual(original, records)

    def test_study_families_cli_refuses_duplicates_before_writing(self) -> None:
        script = Path(__file__).resolve().parents[1] / "scripts/resolve_study_families.py"
        timeout = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120"))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, output = root / "records.json", root / "families.json"
            command = [sys.executable, str(script), str(source), "--output", str(output)]
            for other in ("doi:10.1000/one", "doi:10.1000/other"):
                records = [{"study_id": "S1", "persistent_id": identifier}
                           for identifier in ("doi:10.1000/one", other)]
                for payload in (records, {"studies": records}):
                    with self.subTest(payload=payload):
                        source.write_text(json.dumps(payload), encoding="utf-8")
                        before = source.read_bytes()
                        output.unlink(missing_ok=True)
                        for existing in (False, True):
                            if existing:
                                output.write_text("preserve existing output", encoding="utf-8")
                            result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
                            self.assertEqual(1, result.returncode, result.stderr)
                            self.assertRegex(result.stderr, r"^error: duplicate study_id.*S1")
                            self.assertNotIn("Traceback", result.stderr)
                            self.assertEqual("", result.stdout)
                            self.assertEqual(before, source.read_bytes())
                            if existing:
                                self.assertEqual("preserve existing output", output.read_text())
                            else:
                                self.assertFalse(output.exists())
            source.write_text("{", encoding="utf-8")
            malformed = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
            self.assertEqual(1, malformed.returncode, malformed.stderr)
            self.assertTrue(malformed.stderr.startswith("error: "))
            self.assertNotIn("Traceback", malformed.stderr)
            self.assertEqual("preserve existing output", output.read_text())
            source.unlink()
            missing = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
            self.assertEqual(1, missing.returncode, missing.stderr)
            self.assertTrue(missing.stderr.startswith("error: "))
            self.assertNotIn("Traceback", missing.stderr)
            self.assertEqual("preserve existing output", output.read_text())
            for records in ([], [{"study_id": "S1"}], [{"study_id": "S1"}, {"study_id": "S2"}]):
                with self.subTest(unique=records):
                    source.write_text(json.dumps(records), encoding="utf-8")
                    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertEqual({"schema_version": 1, "families": resolve_study_families(records)},
                                     json.loads(output.read_text()))

    @staticmethod
    def risk_of_bias_payload() -> dict:
        return {"schema_version": 1, "study_id": "S1", "instrument": "RoB 2",
                "domains": [{"name": "selection", "judgment": "low", "rationale": "Reported."}],
                "overall_judgment": "low"}

    def test_risk_of_bias_required_fields_are_nonempty_strings(self) -> None:
        for field in ("study_id", "instrument", "name", "rationale"):
            for value in (None, 0, 1, False, True, [], {}, "", " \t\n"):
                with self.subTest(field=field, value=value):
                    payload = self.risk_of_bias_payload()
                    target = payload if field in ("study_id", "instrument") else payload["domains"][0]
                    target[field] = value
                    original = deepcopy(payload)
                    with self.assertRaises(ValueError):
                        validate_risk_of_bias(payload)
                    self.assertEqual(original, payload)
            payload = self.risk_of_bias_payload()
            target = payload if field in ("study_id", "instrument") else payload["domains"][0]
            del target[field]
            with self.assertRaises(ValueError):
                validate_risk_of_bias(payload)
            for value in ("x", " padded "):
                target[field] = value
                original = deepcopy(payload)
                validate_risk_of_bias(payload)
                self.assertEqual(original, payload)

    def test_risk_of_bias_cli_rejects_null_required_fields(self) -> None:
        from codex_science.artifacts import add_artifact, new_manifest

        script = Path(__file__).resolve().parents[1] / "scripts/validate_artifact.py"
        timeout = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120"))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact, source, output = root / "bias.json", root / "manifest.json", root / "review.json"
            command = [sys.executable, str(script), str(source), "--review-output", str(output),
                       "--require-passed-review"]
            for field in (None, "study_id", "instrument", "name", "rationale"):
                with self.subTest(field=field):
                    payload = self.risk_of_bias_payload()
                    if field is not None:
                        target = payload if field in ("study_id", "instrument") else payload["domains"][0]
                        target[field] = None
                    artifact.write_text(json.dumps(payload), encoding="utf-8")
                    manifest = new_manifest("bias-test", "Is the record valid?", [])
                    manifest["review"]["status"] = "passed"
                    add_artifact(manifest, "bias.json", kind="risk-of-bias",
                                 sha256=hashlib.sha256(artifact.read_bytes()).hexdigest())
                    source.write_text(json.dumps(manifest), encoding="utf-8")
                    before = source.read_bytes(), artifact.read_bytes()
                    output.unlink(missing_ok=True)
                    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
                    self.assertEqual(before, (source.read_bytes(), artifact.read_bytes()))
                    if field is None:
                        self.assertEqual(0, result.returncode, result.stderr)
                        self.assertIn("artifact review: passed", result.stdout)
                    else:
                        self.assertEqual(1, result.returncode, result.stderr)
                        self.assertTrue(result.stderr.startswith("error: "))
                        self.assertIn("bias.json (risk-of-bias):", result.stderr)
                        self.assertNotIn("Traceback", result.stderr)
                        self.assertNotIn("artifact bundle: valid", result.stdout)
                        self.assertFalse(output.exists())

    def test_risk_of_bias_requires_explicit_domain_rationales(self) -> None:
        payload = {
            "schema_version": 1,
            "study_id": "study-1",
            "instrument": "RoB-like fixture",
            "domains": [{"name": "randomization", "judgment": "low", "rationale": "Sequence generation and concealment were reported."}],
            "overall_judgment": "low",
        }
        validate_risk_of_bias(payload)
        broken = dict(payload)
        broken["domains"] = [{"name": "randomization", "judgment": "low", "rationale": ""}]
        with self.assertRaises(ValueError):
            validate_risk_of_bias(broken)

    def test_risk_of_bias_aggregate_hint_and_artifact_label(self) -> None:
        aggregate = {"schema_version": 1, "records": [{"study_id": "s1"}]}
        with self.assertRaisesRegex(ValueError, r"^risk-of-bias study_id and instrument are required.*one study"):
            validate_risk_of_bias(aggregate)
        with self.assertRaisesRegex(ValueError, r"one study.*`assessments`.*--kind PATH=provenance-record"):
            validate_risk_of_bias({"schema_version": 1, "assessments": [{"study_id": "s1", "instrument": "RoB 2"}]})
        with self.assertRaises(ValueError) as lone:
            validate_risk_of_bias({"schema_version": 1, "domains": [{"name": "d"}], "assessments": []})
        self.assertEqual("risk-of-bias study_id and instrument are required", str(lone.exception))
        with self.assertRaises(ValueError) as plain:
            validate_risk_of_bias({"schema_version": 1})
        self.assertEqual("risk-of-bias study_id and instrument are required", str(plain.exception))

        import json
        import tempfile
        from pathlib import Path

        from codex_science.advanced_sidecars import validate_advanced_sidecars

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "S1.json"
            path.write_text(json.dumps(aggregate), encoding="utf-8")
            manifest = {"artifacts": [{"path": "bias/S1.json", "kind": "risk-of-bias", "sha256": "0" * 64}]}
            with self.assertRaisesRegex(ValueError, r"^bias/S1\.json \(risk-of-bias\): risk-of-bias study_id and instrument"):
                validate_advanced_sidecars(manifest, Path(tmp), {"bias/S1.json": path})


if __name__ == "__main__":
    unittest.main()
