import json
import os
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
from codex_science.literature_v2 import normalize_identifier, resolve_study_families, validate_risk_of_bias


class CollaborationAndLiteratureV2Tests(unittest.TestCase):
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
