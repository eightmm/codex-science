import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codex_science.discovery import attach_cycle
from codex_science.artifacts import new_manifest
from codex_science.collaboration import annotation_resolution_lock
from codex_science.project_store import ProjectStore
from codex_science.research_cycle import apply_cycle_event, load_cycle, new_cycle, save_cycle
from tests.test_discovery_integration import ROOT, prepare
from tests import test_discovery_design as design_fixtures


def annotation_fixture(root):
    root.mkdir(parents=True)
    artifact = root / "result.json"
    artifact.write_text('{"answer": 1}\n', encoding="utf-8")
    manifest = new_manifest("run-annotation", "Check an annotation", [])
    manifest["artifacts"].append({"path": "result.json", "kind": "data",
        "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest()})
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    cli = [sys.executable, str(ROOT / "scripts/annotate_run.py"), str(root)]
    return manifest_path, artifact, cli


def add_fixture_annotation(cli, *, annotation_id="A1", text="Check the claim", artifact="result.json"):
    return subprocess.run(cli + ["add", "--id", annotation_id, "--author", "reviewer", "--text", text,
        "--artifact", artifact, "--json-pointer", "/answer"], capture_output=True, text=True)


class DiscoveryWorkbenchTests(unittest.TestCase):
    def test_annotation_cli_round_trip_history_hash_guard_and_workbench(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run"
            root.mkdir()
            artifact = root / "result.json"
            artifact.write_text('{"answer": 1}\n', encoding="utf-8")
            manifest = new_manifest("run-1", "Check a result", [])
            manifest["artifacts"].append({"path": "result.json", "kind": "data",
                "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest()})
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            cli = [sys.executable, str(ROOT / "scripts/annotate_run.py"), str(root)]
            added = subprocess.run(cli + ["add", "--id", "A1", "--author", "reviewer", "--text", "Check <claim>",
                "--artifact", "result.json", "--json-pointer", "/answer"], capture_output=True, text=True)
            self.assertEqual(0, added.returncode, added.stderr)
            self.assertIn(
                "add changes manifest.json bytes; a ProjectStore that already imported this run will refuse it "
                "('imported run manifest changed on disk'). Annotate runs before importing them.",
                added.stderr,
            )
            manifest_after_add = manifest_path.read_bytes()
            self.assertNotIn("annotations/resolutions.jsonl", {
                item["path"] for item in json.loads(manifest_after_add)["artifacts"]
            })
            first = subprocess.run(cli + ["resolve", "--id", "A1", "--status", "resolved", "--resolver", "owner", "--note", "Verified"], capture_output=True, text=True)
            self.assertEqual(0, first.returncode, first.stderr)
            self.assertEqual(0o644, (root / "annotations/resolutions.jsonl").stat().st_mode & 0o777)
            self.assertEqual(manifest_after_add, manifest_path.read_bytes())
            second = subprocess.run(cli + ["resolve", "--id", "A1", "--status", "dismissed", "--resolver", "owner", "--note", "Duplicate"], capture_output=True, text=True)
            self.assertEqual(0, second.returncode, second.stderr)
            self.assertEqual(manifest_after_add, manifest_path.read_bytes())
            history = (root / "annotations/resolutions.jsonl").read_text().splitlines()
            self.assertEqual(2, len(history))
            listed = subprocess.run(cli + ["list"], capture_output=True, text=True)
            self.assertEqual(0, listed.returncode, listed.stderr)
            item = json.loads(listed.stdout)[0]
            self.assertEqual("dismissed", item["status"])
            self.assertEqual("Duplicate", item["latest_resolution"]["note"])
            from codex_science.workbench import render_workbench
            rendered = render_workbench(json.loads(manifest_path.read_text()), root)
            self.assertIn("result.json", rendered)
            self.assertIn("/answer", rendered)
            self.assertIn("Duplicate", rendered)
            self.assertIn("Check &lt;claim&gt;", rendered)
            (root / "result.json").write_text('{"answer": 2}\n', encoding="utf-8")
            changed_manifest = json.loads(manifest_path.read_text())
            changed_manifest["artifacts"][0]["sha256"] = hashlib.sha256((root / "result.json").read_bytes()).hexdigest()
            manifest_path.write_text(json.dumps(changed_manifest), encoding="utf-8")
            refused = subprocess.run(cli + ["resolve", "--id", "A1", "--status", "resolved", "--resolver", "owner"], capture_output=True, text=True)
            self.assertNotEqual(0, refused.returncode)
            self.assertNotIn("re-anchor", refused.stderr)
            self.assertIn("resolution was not recorded", refused.stderr)
            self.assertEqual(2, len((root / "annotations/resolutions.jsonl").read_text().splitlines()))
            (root / "annotations/resolutions.jsonl").write_text("not-json\n")
            malformed = subprocess.run(cli + ["list"], capture_output=True, text=True)
            self.assertNotEqual(0, malformed.returncode)
            self.assertIn("invalid resolution event", malformed.stderr)

    def test_annotation_cli_refuses_symlink_sidecar_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run"
            root.mkdir()
            artifact = root / "result.json"
            artifact.write_text("{}\n")
            manifest = new_manifest("run-1", "Check a result", [])
            manifest["artifacts"].append({"path": "result.json", "kind": "data",
                "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest()})
            (root / "manifest.json").write_text(json.dumps(manifest))
            outside = Path(temporary) / "outside.json"
            outside.write_text("sentinel")
            (root / "annotations").mkdir()
            (root / "annotations/A1.json").symlink_to(outside)
            result = subprocess.run([sys.executable, str(ROOT / "scripts/annotate_run.py"), str(root), "add",
                "--id", "A1", "--author", "reviewer", "--text", "Check", "--artifact", "result.json",
                "--claim-id", "C1"], capture_output=True, text=True)
            self.assertNotEqual(0, result.returncode)
            self.assertEqual("sentinel", outside.read_text())

    def test_orphan_annotation_sidecar_can_be_idempotently_registered(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run"
            manifest_path, artifact, cli = annotation_fixture(root)
            orphan = root / "annotations/A1.json"
            orphan.parent.mkdir()
            payload = {"schema_version": 1, "annotation_id": "A1", "author": "reviewer", "type": "note",
                "text": "Check the claim", "status": "open", "created_at": "2026-10-22T00:00:00Z",
                "anchor": {"artifact_path": "result.json", "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                    "json_pointer": "/answer"}}
            orphan_bytes = json.dumps(payload, indent=2, sort_keys=True).encode() + b"\n"
            orphan.write_bytes(orphan_bytes)
            result = add_fixture_annotation(cli)
            self.assertEqual(0, result.returncode, result.stderr)
            manifest = json.loads(manifest_path.read_text())
            self.assertIn("annotations/A1.json", {item["path"] for item in manifest["artifacts"]})
            self.assertEqual(orphan_bytes, orphan.read_bytes())
            conflicting = {**payload, "annotation_id": "A2", "text": "different"}
            (root / "annotations/A2.json").write_text(json.dumps(conflicting))
            rejected = add_fixture_annotation(cli, annotation_id="A2", text="requested")
            self.assertNotEqual(0, rejected.returncode)
            self.assertIn("annotations/A2.json", rejected.stderr)
            self.assertIn("remove it or re-run add with identical content to register it", rejected.stderr)

    def test_add_validates_resolution_ledger_before_mutating_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            fresh_root = Path(temporary) / "fresh-run"
            _, _, fresh_cli = annotation_fixture(fresh_root)
            refused_fresh = add_fixture_annotation(fresh_cli, artifact="missing.json")
            self.assertNotEqual(0, refused_fresh.returncode)
            self.assertIn("anchor artifact", refused_fresh.stderr)
            self.assertFalse((fresh_root / "annotations").exists())

            root = Path(temporary) / "run"
            manifest_path, _, cli = annotation_fixture(root)
            ledger = root / "annotations/resolutions.jsonl"
            ledger.parent.mkdir()
            artifact_hash = hashlib.sha256((root / "result.json").read_bytes()).hexdigest()
            sidecar = root / "annotations/A1.json"
            sidecar.write_text(json.dumps({
                "schema_version": 1, "annotation_id": "A1", "author": "reviewer", "type": "note",
                "text": "Check the claim", "status": "open", "created_at": "2026-10-22T00:00:00Z",
                "anchor": {"artifact_path": "result.json", "artifact_sha256": artifact_hash,
                           "json_pointer": "/answer"},
            }, indent=2, sort_keys=True) + "\n")
            sidecar_before = sidecar.read_bytes()
            ledger.write_text(json.dumps({
                "schema_version": 1, "annotation_id": "unknown", "status": "resolved",
                "resolver": "reviewer", "resolved_at": "2026-10-22T00:00:00Z",
                "artifact_sha256": artifact_hash,
            }) + "\n")
            manifest_before = manifest_path.read_bytes()
            rejected = add_fixture_annotation(cli)
            self.assertNotEqual(0, rejected.returncode)
            self.assertIn("unknown annotation", rejected.stderr)
            self.assertEqual(manifest_before, manifest_path.read_bytes())
            self.assertEqual(sidecar_before, sidecar.read_bytes())

    def test_add_preserves_modes_and_concurrent_adds_keep_manifest_entries(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run"
            manifest_path, _, cli = annotation_fixture(root)
            manifest_path.chmod(0o640)
            workers = [subprocess.Popen(cli + ["add", "--id", f"A{index}", "--author", "reviewer",
                "--text", f"Check {index}", "--artifact", "result.json", "--json-pointer", "/answer"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for index in range(6)]
            for worker in workers:
                stdout, stderr = worker.communicate(timeout=10)
                self.assertEqual(0, worker.returncode, stderr or stdout)
            manifest = json.loads(manifest_path.read_text())
            annotation_paths = {item["path"] for item in manifest["artifacts"] if item.get("kind") == "annotation"}
            self.assertEqual({f"annotations/A{index}.json" for index in range(6)}, annotation_paths)
            self.assertEqual(0o640, manifest_path.stat().st_mode & 0o777)
            self.assertEqual(0o644, (root / "annotations/A0.json").stat().st_mode & 0o777)
            lock_path = root / "annotations/.resolutions.lock"
            self.assertEqual(0o644, lock_path.stat().st_mode & 0o777)

    def test_readonly_annotation_views_work_with_readonly_lock_and_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run"
            manifest_path, _, cli = annotation_fixture(root)
            with annotation_resolution_lock(root, exclusive=False):
                pass
            self.assertFalse((root / "annotations/.resolutions.lock").exists())
            self.assertEqual(0, add_fixture_annotation(cli).returncode)
            resolved = subprocess.run(cli + ["resolve", "--id", "A1", "--status", "resolved",
                "--resolver", "reviewer", "--note", "Reviewed"], capture_output=True, text=True)
            self.assertEqual(0, resolved.returncode, resolved.stderr)
            lock_path = root / "annotations/.resolutions.lock"
            lock_path.chmod(0o400)
            try:
                for path in (manifest_path, root / "result.json", root / "annotations/A1.json",
                             root / "annotations/resolutions.jsonl"):
                    path.chmod(0o444)
                (root / "annotations").chmod(0o555)
                root.chmod(0o555)
                listed = subprocess.run(cli + ["list"], capture_output=True, text=True)
                self.assertEqual(0, listed.returncode, listed.stderr)
                self.assertEqual("resolved", json.loads(listed.stdout)[0]["status"])
                from codex_science.workbench import render_workbench
                rendered = render_workbench(json.loads(manifest_path.read_text()), root)
                self.assertIn("Reviewed", rendered)
            finally:
                root.chmod(0o755)
                (root / "annotations").chmod(0o755)
                for path in root.rglob("*"):
                    if path.is_file() and not path.is_symlink():
                        path.chmod(0o644)

    def test_tampered_resolution_is_visibly_operator_recorded_and_unverified(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run"
            manifest_path, _, cli = annotation_fixture(root)
            self.assertEqual(0, add_fixture_annotation(cli).returncode)
            self.assertEqual(0, subprocess.run(cli + ["resolve", "--id", "A1", "--status", "dismissed",
                "--resolver", "reviewer", "--note", "original"], capture_output=True, text=True).returncode)
            ledger = root / "annotations/resolutions.jsonl"
            event = json.loads(ledger.read_text())
            event["note"] = "tampered note"
            ledger.write_text(json.dumps(event) + "\n")
            from codex_science.workbench import render_workbench
            rendered = render_workbench(json.loads(manifest_path.read_text()), root)
            self.assertIn("dismissed", rendered)
            self.assertIn("tampered note", rendered)
            self.assertIn("operator-recorded, not covered by the manifest", rendered)
            self.assertIn("Registered bundle artifacts and sidecars were validated against the manifest", rendered)

    def test_resolution_ledger_concurrent_and_sequential_appends_keep_history(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run"
            _, _, cli = annotation_fixture(root)
            added = add_fixture_annotation(cli)
            self.assertEqual(0, added.returncode, added.stderr)
            workers = [subprocess.Popen(cli + ["resolve", "--id", "A1", "--status", "resolved",
                "--resolver", f"worker-{index}", "--note", f"event-{index}"], stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True) for index in range(6)]
            for worker in workers:
                stdout, stderr = worker.communicate(timeout=10)
                self.assertEqual(0, worker.returncode, stderr or stdout)
            sequential = subprocess.run(cli + ["resolve", "--id", "A1", "--status", "dismissed",
                "--resolver", "owner", "--note", "last"], capture_output=True, text=True)
            self.assertEqual(0, sequential.returncode, sequential.stderr)
            events = [json.loads(line) for line in (root / "annotations/resolutions.jsonl").read_text().splitlines()]
            self.assertEqual(7, len(events))
            self.assertEqual(7, len({event["event_id"] for event in events}))

    def test_reanchored_annotation_keeps_old_resolution_as_history_and_lists_stale(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run"
            manifest_path, artifact, cli = annotation_fixture(root)
            self.assertEqual(0, add_fixture_annotation(cli).returncode)
            self.assertEqual(0, subprocess.run(cli + ["resolve", "--id", "A1", "--status", "resolved",
                "--resolver", "reviewer"], capture_output=True, text=True).returncode)
            artifact.write_text('{"answer": 2}\n', encoding="utf-8")
            manifest = json.loads(manifest_path.read_text())
            artifact_sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
            manifest["artifacts"][0]["sha256"] = artifact_sha
            sidecar = root / "annotations/A1.json"
            annotation = json.loads(sidecar.read_text())
            annotation["anchor"]["artifact_sha256"] = artifact_sha
            sidecar.write_text(json.dumps(annotation, indent=2, sort_keys=True) + "\n")
            manifest["artifacts"][1]["sha256"] = hashlib.sha256(sidecar.read_bytes()).hexdigest()
            manifest_path.write_text(json.dumps(manifest))
            listed = subprocess.run(cli + ["list"], capture_output=True, text=True)
            self.assertEqual(0, listed.returncode, listed.stderr)
            self.assertEqual("stale-anchor", json.loads(listed.stdout)[0]["status"])
            from codex_science.workbench import render_workbench
            rendered = render_workbench(manifest, root)
            self.assertIn("stale-anchor", rendered)
            self.assertIn("operator-recorded, not covered by the manifest", rendered)

    def test_resolve_refuses_outside_root_annotation_anchor(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run"
            manifest_path, _, cli = annotation_fixture(root)
            outside = Path(temporary) / "outside.json"
            outside.write_text("{}\n")
            self.assertEqual(0, add_fixture_annotation(cli).returncode)
            manifest = json.loads(manifest_path.read_text())
            sidecar = root / "annotations/A1.json"
            annotation = json.loads(sidecar.read_text())
            annotation["anchor"]["artifact_path"] = "../outside.json"
            annotation["anchor"]["artifact_sha256"] = hashlib.sha256(outside.read_bytes()).hexdigest()
            sidecar.write_text(json.dumps(annotation, indent=2, sort_keys=True) + "\n")
            manifest["artifacts"][1]["sha256"] = hashlib.sha256(sidecar.read_bytes()).hexdigest()
            manifest_path.write_text(json.dumps(manifest))
            result = subprocess.run(cli + ["resolve", "--id", "A1", "--status", "resolved", "--resolver", "reviewer"],
                capture_output=True, text=True)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("inside the run bundle", result.stderr)

    def test_readonly_cli_views_and_project_memory_preserve_scientific_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run"
            save_cycle(new_cycle(prepare(root)), root)
            attach_cycle(root)
            before = (root / "discovery/revisions/000001.json").read_bytes()
            command = [sys.executable, str(ROOT / "scripts/science_project.py")]
            for action in ("audit", "next", "graph", "assess"):
                with self.subTest(action=action):
                    result = subprocess.run(command + ["discovery", action, "--run-dir", str(root)], capture_output=True, text=True)
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertIsInstance(json.loads(result.stdout), dict)
            database = Path(temporary) / "project.sqlite"
            store = ProjectStore(database)
            store.create_project(project_id="p", title="Discovery", question="Why?")
            store.import_run(project_id="p", manifest_path=root / "manifest.json")
            result = subprocess.run(command + ["--database", str(database), "discovery", "memory", "--project-id", "p"], capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(2, len(json.loads(result.stdout)["comparable_evidence_groups"]))
            self.assertEqual(before, (root / "discovery/revisions/000001.json").read_bytes())

            annotation_root = Path(temporary) / "annotation-run"
            annotation_manifest, _, annotation_cli = annotation_fixture(annotation_root)
            store.import_run(project_id="p", manifest_path=annotation_manifest)
            added = add_fixture_annotation(annotation_cli)
            self.assertEqual(0, added.returncode, added.stderr)
            self.assertIn("Annotate runs before importing them.", added.stderr)
            with self.assertRaisesRegex(ValueError, "imported run manifest changed on disk"):
                store.compare_runs(project_id="p", previous_run_id="run-annotation",
                                   current_run_id="run-annotation")

    def test_strict_revision_appends_new_assumption_and_requires_actual_learning(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cycle = design_fixtures.DiscoveryDesignTests().designed(root)
            cycle["design_policy"] = "required-for-reservation"
            cycle["experiments"] = [{"id": "e1", "method_id": "m1", "cost": 1,
                                      "predictions": {"h1": [0, 1]}, "resolution": .1,
                                      "controls": ["same input"]}]
            save_cycle(new_cycle(cycle), root)
            for event in ({"kind": "reserve", "experiment_id": "e1", "request_id": "r1"},
                          {"kind": "failure", "experiment_id": "e1", "request_id": "r1",
                           "failure_kind": "implementation", "outcome": "nonfinite feature"}):
                save_cycle(apply_cycle_event(load_cycle(root), event, root), root)
            cycle = load_cycle(root)
            event = {"kind": "revise", "source_experiment_id": "e1", "rationale": "Need a finite-feature assumption",
                     "assumptions": [{"id": "finite", "statement": "Inputs are finite", "category": "data", "status": "untested"}]}
            with self.assertRaisesRegex(ValueError, "lesson"):
                apply_cycle_event(cycle, event, root)
            event["lesson"] = {"observation": "The feature computation failed before measurement",
                               "interpretation": "Execution failure does not test h1", "limitation": "No valid metric",
                               "change": "Add explicit finite input assumption", "next_test": "Repair and confirm finite features"}
            changed = apply_cycle_event(cycle, event, root)
            save_cycle(changed, root)
            result = load_cycle(root)
            self.assertEqual(cycle["problem"]["assumptions"], result["problem"]["assumptions"][:-1])
            self.assertEqual("finite", result["problem"]["assumptions"][-1]["id"])
            no_change = copy.deepcopy(event)
            no_change.pop("assumptions")
            with self.assertRaisesRegex(ValueError, "append a changed"):
                apply_cycle_event(result, no_change, root)
            with self.assertRaisesRegex(ValueError, "unique"):
                apply_cycle_event(result, event, root)

    def test_cli_cannot_overwrite_unregistered_review_input(self):
        import hashlib
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run"
            save_cycle(new_cycle(prepare(root)), root)
            attach_cycle(root)
            receipt = root / "review.json"
            receipt.write_text('{"sentinel":"must stay intact"}')
            before = receipt.read_bytes()
            payload = root / "assessment.json"
            payload.write_text(json.dumps({"review_refs": [{"path": receipt.name,
                                                           "sha256": hashlib.sha256(before).hexdigest()}]}))
            result = subprocess.run([sys.executable, str(ROOT / "scripts/science_project.py"), "discovery", "assess",
                                     "--run-dir", str(root), "--input", str(payload), "--output", str(receipt)], capture_output=True, text=True)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("cannot overwrite referenced input evidence", result.stderr)
            self.assertEqual(before, receipt.read_bytes())


if __name__ == "__main__":
    unittest.main()
