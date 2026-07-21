import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from codex_science.artifact_runtime import build_selection, build_transform_proposal, describe_runtime
from codex_science.artifacts import add_artifact, new_manifest, validate_bundle, write_manifest
from codex_science.review import review_manifest


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ArtifactRuntimeSidecarTests(unittest.TestCase):
    def test_runtime_descriptor_selection_and_proposal_validate_as_hashed_sidecars(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir)
            data = run_dir / "metrics.csv"
            data.write_text("metric,value\nrmsd,1.2\n", encoding="utf-8")
            descriptor = describe_runtime(
                data,
                artifact_path="metrics.csv",
                kind="metrics",
                media_type="text/csv",
                max_bytes=1024,
                max_records=20,
                generated_at="2026-07-21T00:00:00Z",
            ).to_dict()
            selection = build_selection(
                descriptor,
                selector_type="cell",
                selector={"row": 1, "column": "value"},
                selected_by="reviewer",
                reason="Inspect the RMSD threshold input.",
                created_at="2026-07-21T00:01:00Z",
            )
            proposal = build_transform_proposal(
                selection,
                operation="recalculate-metric",
                parameters={"symmetry_aware": True},
                reason="Use the preregistered symmetry-aware definition.",
                affected_steps=["compute-metrics", "review"],
                expected_outputs=["metrics.csv"],
                proposed_by="reviewer",
                created_at="2026-07-21T00:02:00Z",
            )
            descriptor_path = run_dir / "metrics.runtime.json"
            selection_path = run_dir / "metric.selection.json"
            proposal_path = run_dir / "metric.proposal.json"
            for path, payload in ((descriptor_path, descriptor), (selection_path, selection), (proposal_path, proposal)):
                path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            manifest = new_manifest(
                "runtime-sidecar-run",
                "Does the metric artifact satisfy its declared definition?",
                [{"id": "review", "description": "Inspect metric definition", "status": "completed"}],
            )
            manifest["claims"] = [{"id": "C1", "text": "The metric is recorded.", "evidence": ["metrics.csv"]}]
            manifest["review"] = {"status": "passed", "findings": []}
            add_artifact(manifest, "metrics.csv", kind="metrics", sha256=digest(data))
            add_artifact(manifest, descriptor_path.name, kind="artifact-runtime-descriptor", sha256=digest(descriptor_path))
            add_artifact(manifest, selection_path.name, kind="artifact-selection", sha256=digest(selection_path))
            add_artifact(manifest, proposal_path.name, kind="transform-proposal", sha256=digest(proposal_path))
            write_manifest(manifest, run_dir / "manifest.json")

            sidecars = validate_bundle(manifest, run_dir)
            self.assertEqual(1, len(sidecars["runtime_descriptors"]))
            self.assertEqual(1, len(sidecars["artifact_selections"]))
            self.assertEqual(1, len(sidecars["transform_proposals"]))
            self.assertEqual([], sidecars["advanced_findings"])
            self.assertEqual("passed", review_manifest(manifest, run_dir, sidecars=sidecars)["status"])

    def test_changed_target_bytes_make_runtime_records_stale_without_rewriting_them(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir)
            data = run_dir / "metrics.csv"
            data.write_text("metric,value\nrmsd,1.2\n", encoding="utf-8")
            descriptor = describe_runtime(
                data,
                artifact_path="metrics.csv",
                kind="metrics",
                max_bytes=1024,
                max_records=20,
                generated_at="2026-07-21T00:00:00Z",
            ).to_dict()
            selection = build_selection(
                descriptor,
                selector_type="cell",
                selector={"row": 1, "column": "value"},
                selected_by="reviewer",
                reason="Inspect old bytes.",
                created_at="2026-07-21T00:01:00Z",
            )
            data.write_text("metric,value\nrmsd,2.4\n", encoding="utf-8")
            descriptor_path = run_dir / "metrics.runtime.json"
            selection_path = run_dir / "metric.selection.json"
            descriptor_path.write_text(json.dumps(descriptor, sort_keys=True) + "\n", encoding="utf-8")
            selection_path.write_text(json.dumps(selection, sort_keys=True) + "\n", encoding="utf-8")

            manifest = new_manifest(
                "stale-runtime-run",
                "Did the inspected metric bytes change?",
                [{"id": "inspect", "description": "Inspect stale anchor", "status": "completed"}],
            )
            manifest["claims"] = [{"id": "C1", "text": "The current metric is recorded.", "evidence": ["metrics.csv"]}]
            manifest["review"] = {"status": "findings", "findings": []}
            add_artifact(manifest, "metrics.csv", kind="metrics", sha256=digest(data))
            add_artifact(manifest, descriptor_path.name, kind="artifact-runtime-descriptor", sha256=digest(descriptor_path))
            add_artifact(manifest, selection_path.name, kind="artifact-selection", sha256=digest(selection_path))
            sidecars = validate_bundle(manifest, run_dir)
            codes = {item["code"] for item in sidecars["advanced_findings"]}
            self.assertIn("stale-runtime-descriptor", codes)
            self.assertIn("stale-artifact-selection", codes)


if __name__ == "__main__":
    unittest.main()
