import json
import unittest
from pathlib import Path

from codex_science.evidence_graph_v2 import independent_support_groups, impacted_nodes, validate_graph_payload
from codex_science.review_receipts import build_review_receipt, review_receipt_findings, validate_review_receipt
from codex_science.reviewer_benchmark import load_cases, score_cases


class EvidenceReviewV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]

    def test_graph_types_cycles_dependencies_and_impact_are_explicit(self) -> None:
        graph = {
            "schema_version": 2,
            "nodes": [
                {"id": "study-a", "type": "study"},
                {"id": "study-b", "type": "study"},
                {"id": "claim", "type": "claim"},
                {"id": "artifact", "type": "artifact"},
            ],
            "edges": [
                {"source": "study-a", "target": "claim", "relation": "supports"},
                {"source": "study-b", "target": "claim", "relation": "supports"},
                {"source": "study-a", "target": "study-b", "relation": "shares_samples"},
                {"source": "artifact", "target": "claim", "relation": "depends_on"},
            ],
        }
        nodes, edges, findings = validate_graph_payload(graph)
        self.assertEqual([], findings)
        self.assertEqual(1, len(independent_support_groups("claim", nodes, edges)))
        self.assertEqual(["artifact", "claim"], impacted_nodes(["artifact"], edges))

        cyclic = {
            "schema_version": 2,
            "nodes": [{"id": "a", "type": "artifact"}, {"id": "b", "type": "artifact"}],
            "edges": [{"source": "a", "target": "b", "relation": "derived_from"}, {"source": "b", "target": "a", "relation": "derived_from"}],
        }
        _nodes, _edges, findings = validate_graph_payload(cyclic)
        self.assertIn("evidence-dependency-cycle", {item["code"] for item in findings})

    def test_review_receipts_are_hash_covered_and_stale_after_changes(self) -> None:
        receipt = build_review_receipt(
            review_id="review-1", reviewer="reviewer", independent=True,
            review_modes=["record", "method"], status="passed",
            covered_artifacts=[{"path": "metrics.json", "sha256": "a" * 64}],
            covered_claim_ids=["claim-1"], findings=[], limitations=[],
        )
        validate_review_receipt(receipt)
        self.assertEqual([], review_receipt_findings(receipt, {"metrics.json": "a" * 64}))
        codes = {item["code"] for item in review_receipt_findings(receipt, {"metrics.json": "b" * 64})}
        self.assertIn("stale-review-receipt", codes)

    def test_seeded_reviewer_benchmark_has_zero_unsafe_passes(self) -> None:
        report = score_cases(load_cases(self.root / "benchmarks" / "reviewer"))
        self.assertEqual(0.0, report["unsafe_pass_rate"], json.dumps(report, indent=2))
        self.assertEqual(1.0, report["critical_recall"])
        self.assertEqual(1.0, report["major_recall"])
        self.assertEqual(1.0, report["severity_weighted_precision"])


if __name__ == "__main__":
    unittest.main()
