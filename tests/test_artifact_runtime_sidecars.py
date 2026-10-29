import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_science import artifact_runtime as runtime
from codex_science.advanced_sidecars import validate_advanced_sidecars
from codex_science.artifact_runtime import build_selection, build_transform_proposal, describe_runtime
from codex_science.artifacts import add_artifact, new_manifest, validate_bundle, write_manifest
from codex_science.review import review_manifest


# Literal stored records emitted by 00f4dc8; current creation remains stricter.
BASE_STORED_COORDINATES = json.loads(r'''
{
  "zero.txt": {
    "descriptor": {
      "schema_version": 1,
      "artifact_path": "zero.txt",
      "artifact_sha256": "2c8b08da5ce60398e1f19af0e5dccc744df274b826abe585eaba68c525434806",
      "artifact_kind": "artifact",
      "artifact_type": "file",
      "media_type": null,
      "size_bytes": 4,
      "viewer": "text",
      "generated_at": "2026-07-21T00:00:00Z",
      "bounds": {
        "max_bytes": 1048576,
        "max_records": 100
      },
      "preview": {
        "encoding": "utf-8",
        "line_count_in_prefix": 1,
        "lines_preview": [
          {
            "line": 1,
            "text": "one"
          }
        ]
      },
      "warnings": [],
      "evidence_boundary": "This is a bounded derived view of hash-validated bytes. It does not prove a scientific claim, execute an edit, or replace format-specific validation.",
      "fingerprint": "6dc80ee176d6f51e55c5e0902c72ccf50d2348acc424d2c664a799a7ccf20538"
    },
    "selection": {
      "schema_version": 1,
      "artifact_path": "zero.txt",
      "artifact_sha256": "2c8b08da5ce60398e1f19af0e5dccc744df274b826abe585eaba68c525434806",
      "viewer": "text",
      "selector_type": "line",
      "selector": {
        "line": 0
      },
      "selected_by": "reviewer",
      "reason": "Inspect an existing stored selector.",
      "label": "",
      "created_at": "2026-07-21T00:01:00Z",
      "status": "active",
      "evidence_boundary": "A selection identifies part of an artifact; it does not validate the selected interpretation.",
      "selection_id": "selection-2fd5f58a0b7ec5c7150f",
      "fingerprint": "2fd5f58a0b7ec5c7150f9a8ba45e195cb08b9498ffc78ac8070eccca8e38cce3"
    }
  },
  "reversed.txt": {
    "descriptor": {
      "schema_version": 1,
      "artifact_path": "reversed.txt",
      "artifact_sha256": "c3f9c8c283a2b1f2f1896f27a01cbe3cddc0c9d93f752e4639035a0f5b36f6e8",
      "artifact_kind": "artifact",
      "artifact_type": "file",
      "media_type": null,
      "size_bytes": 8,
      "viewer": "text",
      "generated_at": "2026-07-21T00:00:00Z",
      "bounds": {
        "max_bytes": 1048576,
        "max_records": 100
      },
      "preview": {
        "encoding": "utf-8",
        "line_count_in_prefix": 2,
        "lines_preview": [
          {
            "line": 1,
            "text": "one"
          },
          {
            "line": 2,
            "text": "two"
          }
        ]
      },
      "warnings": [],
      "evidence_boundary": "This is a bounded derived view of hash-validated bytes. It does not prove a scientific claim, execute an edit, or replace format-specific validation.",
      "fingerprint": "acd60c7928263955d39962ca2b563644ee65daccd6ff2ce9894cae727c418d1a"
    },
    "selection": {
      "schema_version": 1,
      "artifact_path": "reversed.txt",
      "artifact_sha256": "c3f9c8c283a2b1f2f1896f27a01cbe3cddc0c9d93f752e4639035a0f5b36f6e8",
      "viewer": "text",
      "selector_type": "line-range",
      "selector": {
        "start": 2,
        "end": 1
      },
      "selected_by": "reviewer",
      "reason": "Inspect an existing stored selector.",
      "label": "",
      "created_at": "2026-07-21T00:01:00Z",
      "status": "active",
      "evidence_boundary": "A selection identifies part of an artifact; it does not validate the selected interpretation.",
      "selection_id": "selection-cc797d964c023cf08ce1",
      "fingerprint": "cc797d964c023cf08ce12ba5e4fff092736acb939cdd15babea1c8a9572a6417"
    }
  }
}
''')


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ArtifactRuntimeSidecarTests(unittest.TestCase):
    def add_legacy_selections(self, manifest, run_dir, *, refresh=False):
        records = []
        # Fingerprints captured from the actual base 6e4e0507 build_selection producer.
        for name, content, kind, selector, fingerprint in (
            ("locus.bed", b"chr1\t10\t11\n", "locus", {"chrom": "chr1", "start": 10},
             "ccf0417808afc0aef907a4b5d0decd64ba319ee62cdf816c74e3ac4858ec4a01"),
            ("labels.csv", b"name,value\nalpha,7\n", "row", {"row": "alpha"},
             "bf4f97ade2a2e06914a60fa77c19e107ec9ce14bfa8c8d23f5cc1376a021e8ba"),
            ("bytes.bin", b"abc", "byte-range", {"offset": 0, "length": 3},
             "478170bf734772b603937f4eb90646758ee0b5952bc046af180ded3438aa22f7"),
            ("pointer.json", b'{"a":1}', "json-pointer", {"path": "/a"},
             "dafa70af890111aa0d2a60b1c55d0780c43011829c5b1c84a396147dd30fadc7"),
            ("legacy.yaml", b"model:\n  lr: 0.1\n", "json-pointer", {"pointer": "/model/lr"},
             "fd0ccc3597dc181addffd5274fecf7c02aee3f7df90d15f1fc813950084f2647"),
            ("zero.txt", b"one\n", "line", {"line": 0}, BASE_STORED_COORDINATES["zero.txt"]["selection"]["fingerprint"]),
            ("reversed.txt", b"one\ntwo\n", "line-range", {"start": 2, "end": 1},
             BASE_STORED_COORDINATES["reversed.txt"]["selection"]["fingerprint"]),
        ):
            with self.subTest(selector_type=kind, selector=selector, refresh=refresh):
                target = run_dir / name
                target.write_bytes(content)
                descriptor = describe_runtime(target).to_dict()
                if name in BASE_STORED_COORDINATES:
                    selection = BASE_STORED_COORDINATES[name]["selection"]
                    runtime.validate_selection(selection)
                else:
                    selection = build_selection(
                        descriptor, selector_type=kind, selector=selector,
                        selected_by="reviewer", reason="Inspect an existing stored selector.",
                        created_at="2026-07-21T00:01:00Z",
                    )
                self.assertEqual(selector, selection["selector"])
                self.assertEqual(fingerprint, selection["fingerprint"])
                path = run_dir / (name + ".selection.json")
                stored = (json.dumps(selection, sort_keys=True) + "\n").encode()
                path.write_bytes(stored)
                if refresh:
                    target.write_bytes(content + b"\n")
                add_artifact(manifest, name, kind="metrics", sha256=digest(target))
                add_artifact(manifest, path.name, kind="artifact-selection", sha256=digest(path))
                records.append((path, selection, stored))
        return records

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
            records = self.add_legacy_selections(manifest, run_dir)
            sidecars = validate_bundle(manifest, run_dir)
            actual = {item["selection_id"]: item for item in sidecars["artifact_selections"]}
            self.assertEqual(8, len(actual))
            for path, selection, stored in records:
                self.assertEqual(selection, actual[selection["selection_id"]])
                self.assertEqual(stored, path.read_bytes())

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
            records = self.add_legacy_selections(manifest, run_dir, refresh=True)
            with patch("codex_science.artifact_runtime._validate_selection_region",
                       side_effect=AssertionError("stale coordinates must not be inspected")):
                sidecars = validate_bundle(manifest, run_dir)
            actual = {item["selection_id"]: item for item in sidecars["artifact_selections"]}
            for path, selection, stored in records:
                self.assertEqual({**selection, "status": "stale-anchor"}, actual[selection["selection_id"]])
                self.assertEqual("active", selection["status"])
                self.assertEqual(stored, path.read_bytes())

    def test_line_selections_survive_media_type_mismatch(self) -> None:
        for include_descriptor in (False, True):
            with self.subTest(include_descriptor=include_descriptor), tempfile.TemporaryDirectory() as scratch:
                run_dir = Path(scratch)
                target = run_dir / "data.txt"
                target.write_text(json.dumps({"a": "x\u2028y\u0085z"}, ensure_ascii=False))
                descriptor = describe_runtime(target).to_dict()
                self.assertEqual(3, descriptor["preview"]["line_count_in_prefix"])
                selection = build_selection(
                    descriptor, selector_type="line", selector={"line": 3},
                    selected_by="reviewer", reason="Inspect the original line-counting interpretation.",
                )
                path = run_dir / "data.selection.json"
                stored = json.dumps(selection).encode()
                path.write_bytes(stored)
                manifest = new_manifest("media-type-run", "Does the stored line stay valid?", [])
                add_artifact(manifest, target.name, kind="metrics", sha256=digest(target), media_type="application/json")
                add_artifact(manifest, path.name, kind="artifact-selection", sha256=digest(path))
                if include_descriptor:
                    # Descriptor order must not determine the interpretation of earlier selections.
                    context = run_dir / "data.runtime.json"
                    context.write_text(json.dumps(descriptor))
                    add_artifact(manifest, context.name, kind="artifact-runtime-descriptor", sha256=digest(context))
                result = validate_bundle(manifest, run_dir)
                self.assertEqual("active", result["artifact_selections"][0]["status"])
                self.assertEqual(stored, path.read_bytes())

    def test_cli_accepts_stored_coordinates_but_creation_rejects_line_zero(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            for name, fixture in BASE_STORED_COORDINATES.items():
                with self.subTest(name=name):
                    path = Path(scratch) / (name + ".selection.json")
                    stored = json.dumps(fixture["selection"]).encode()
                    path.write_bytes(stored)
                    output = Path(scratch) / (name + ".proposal.json")
                    result = subprocess.run([
                        sys.executable, "scripts/render_artifact_runtime.py", "propose", str(path),
                        "--operation", "inspect", "--parameters", "{}", "--reason", "Review old coordinates.",
                        "--affected-step", "inspect", "--proposed-by", "reviewer", "--output", str(output),
                    ], capture_output=True, text=True, timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "30")))
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertTrue(json.loads(output.read_text())["requires_approval"])
                    self.assertEqual(stored, path.read_bytes())
            with self.assertRaises(ValueError):
                build_selection(BASE_STORED_COORDINATES["zero.txt"]["descriptor"], selector_type="line",
                                selector={"line": 0}, selected_by="reviewer", reason="Create a new selection.")

    def test_missing_verified_sidecar_path_is_labelled(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            with self.assertRaisesRegex(ValueError, r"\(artifact-selection\).*path"):
                validate_advanced_sidecars({"artifacts": [{"kind": "artifact-selection"}]}, Path(scratch), {})
            for fields in ({}, {"path": ""}, {"path": None}, {"path": "missing.json"}):
                with self.subTest(fields=fields), self.assertRaisesRegex(ValueError, r"\(artifact-selection\).*path"):
                    validate_advanced_sidecars({"artifacts": [{"kind": "artifact-selection", "sha256": "0" * 64, **fields}]},
                                              Path(scratch), {})

if __name__ == "__main__":
    unittest.main()
