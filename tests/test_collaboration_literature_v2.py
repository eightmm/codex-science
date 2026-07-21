import unittest

from codex_science.collaboration import diff_runs, selective_rerun_plan, stale_annotations
from codex_science.literature_v2 import normalize_identifier, resolve_study_families, validate_risk_of_bias


class CollaborationAndLiteratureV2Tests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
