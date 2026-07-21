import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from codex_science.artifacts import add_artifact, new_manifest, write_manifest
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


if __name__ == "__main__":
    unittest.main()
