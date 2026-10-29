import copy
import json
import unittest
from pathlib import Path

from codex_science.evidence_graph_v2 import independent_support_groups, impacted_nodes, validate_graph_payload
from codex_science.review_receipts import build_review_receipt, canonical_sha256, review_receipt_findings, validate_review_receipt
from codex_science.reviewer_benchmark import load_cases, score_cases


class EvidenceReviewV2Tests(unittest.TestCase):
    def test_numeric_graph_ids_preserve_dependency_components(self):
        from codex_science.advanced_sidecars import review_advanced_sidecars

        for first, second in ((1, 2), (0, 1), (" 1 ", " 2 ")):
            with self.subTest(first=first):
                graph = {"schema_version": 2, "nodes": [
                    {"id": first, "type": "study"}, {"id": second, "type": "study"},
                    {"id": "C", "type": "claim"}], "edges": [
                    {"source": first, "target": "C", "relation": "supports"},
                    {"source": second, "target": "C", "relation": "supports"},
                    {"source": first, "target": second, "relation": "shares_samples"}]}
                nodes, edges, findings = validate_graph_payload(graph)
                self.assertEqual([], findings)
                self.assertEqual(1, len(independent_support_groups("C", nodes, edges)))
                self.assertTrue(all(node["id"] == key for key, node in nodes.items()))
                reviewed = review_advanced_sidecars({"graph_v2_nodes": nodes, "graph_v2_edges": edges,
                    "base_sidecars": {"claim_by_id": {"C": {"status": "replicated"}}}})
                self.assertIn("dependent-evidence-v2", {item["code"] for item in reviewed})
        nodes, edges, findings = validate_graph_payload({"schema_version": 2, "nodes": [], "edges": []})
        self.assertEqual(set(), independent_support_groups("C", nodes, edges))
        with self.assertRaisesRegex(ValueError, "endpoint missing"):
            validate_graph_payload({"schema_version": 2, "nodes": [], "edges": [
                {"source": 0, "target": "C", "relation": "supports"}]})

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
        self.assertEqual(["artifact"], impacted_nodes(["artifact"], edges))
        self.assertEqual(["artifact", "claim"], impacted_nodes(["claim"], edges))

        cyclic = {
            "schema_version": 2,
            "nodes": [{"id": "a", "type": "artifact"}, {"id": "b", "type": "artifact"}],
            "edges": [{"source": "a", "target": "b", "relation": "derived_from"}, {"source": "b", "target": "a", "relation": "derived_from"}],
        }
        _nodes, _edges, findings = validate_graph_payload(cyclic)
        self.assertIn("evidence-dependency-cycle", {item["code"] for item in findings})

    def test_impact_follows_relation_direction_and_ignores_independence_only_edges(self) -> None:
        cases = (
            ("supports", ["a", "b"], ["b"]),
            ("contradicts", ["a", "b"], ["b"]),
            ("depends_on", ["a"], ["a", "b"]),
            ("derived_from", ["a"], ["a", "b"]),
            ("propagated_from", ["a"], ["a", "b"]),
            ("training_overlap", ["a", "b"], ["a", "b"]),
        )
        for relation, from_source, from_target in cases:
            edges = [{"source": "a", "target": "b", "relation": relation}]
            for changed, expected in (("a", from_source), ("b", from_target)):
                with self.subTest(relation=relation, changed=changed):
                    self.assertEqual(expected, impacted_nodes([changed, changed], edges))

        edges = [
            {"source": "study", "target": "dataset", "relation": "depends_on"},
            {"source": "study", "target": "claim", "relation": "supports"},
            {"source": "portal", "target": "study", "relation": "propagated_from"},
        ]
        for relation in ("duplicates", "shares_cohort", "shares_samples", "unknown"):
            edges.extend([
                {"source": "study", "target": relation + "-out", "relation": relation},
                {"source": relation + "-in", "target": "study", "relation": relation},
            ])
        self.assertEqual(["claim", "dataset", "portal", "study"], impacted_nodes(["dataset"], edges))
        self.assertEqual([], impacted_nodes([], edges))
        self.assertEqual(["0"], impacted_nodes(["0"], []))
        self.assertEqual(["dataset"], impacted_nodes(["dataset"], [{}]))

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

    def test_review_receipt_rejects_non_object_findings_without_crashing(self) -> None:
        receipt = build_review_receipt(
            review_id="review-malformed",
            reviewer="reviewer",
            independent=True,
            review_modes=["record"],
            status="passed",
            covered_artifacts=[{"path": "metrics.json", "sha256": "a" * 64}],
            covered_claim_ids=["claim-1"],
            findings=[],
            limitations=[],
        )
        receipt["findings"] = ["not-an-object"]
        receipt.pop("fingerprint")

        with self.assertRaisesRegex(ValueError, "findings must contain objects"):
            validate_review_receipt(receipt)
        self.assertEqual(
            {"invalid-review-receipt"},
            {
                item["code"]
                for item in review_receipt_findings(
                    receipt,
                    {"metrics.json": "a" * 64},
                )
            },
        )

    def test_blocking_severity_normalization_preserves_honest_receipts(self) -> None:
        for severity in ("major", "critical", "minor", "suggestion"):
            for resolution in ("open", "resolved", "accepted-risk", "not-applicable"):
                with self.subTest(severity=severity, resolution=resolution):
                    receipt = build_review_receipt(
                        review_id="review-normalized", reviewer="reviewer", independent=True,
                        review_modes=["record"], status="passed",
                        covered_artifacts=[{"path": "metrics.json", "sha256": "a" * 64}],
                        covered_claim_ids=[], findings=[{"severity": severity, "resolution_status": resolution}],
                    )
                    codes = {item["code"] for item in review_receipt_findings(receipt, {"metrics.json": "a" * 64})}
                    self.assertEqual(
                        severity in {"major", "critical"} and resolution not in {"resolved", "not-applicable"},
                        "unsafe-review-pass" in codes,
                    )
        for severity in ("", "major ", " critical\t", "MAJOR"):
            with self.subTest(severity=severity):
                with self.assertRaisesRegex(ValueError, "invalid finding severity"):
                    build_review_receipt(
                        review_id="review-invalid-severity", reviewer="reviewer", independent=True,
                        review_modes=["record"], status="passed",
                        covered_artifacts=[{"path": "metrics.json", "sha256": "a" * 64}],
                        covered_claim_ids=[], findings=[{"severity": severity}],
                    )

    def test_receipt_finding_decision_fields_are_validated_with_valid_fingerprint(self) -> None:
        base = build_review_receipt(
            review_id="review-fields", reviewer="reviewer", independent=True,
            review_modes=["record"], status="passed",
            covered_artifacts=[{"path": "metrics.json", "sha256": "a" * 64}],
            covered_claim_ids=[], findings=[],
        )
        invalid = [{}]
        for field in ("severity", "resolution_status"):
            invalid.extend({"severity": "minor", field: value}
                           for value in ("", "  ", "later", "MAJOR", 0, None, [], {}))
        for finding in invalid:
            with self.subTest(finding=finding):
                receipt = {**base, "findings": [finding]}
                receipt.pop("fingerprint")
                receipt["fingerprint"] = canonical_sha256(receipt)
                with self.assertRaises(ValueError):
                    validate_review_receipt(receipt)
                self.assertEqual(["invalid-review-receipt"], [item["code"] for item in
                    review_receipt_findings(receipt, {"metrics.json": "a" * 64})])
        accepted = [{"severity": "minor"}, {"severity": "major", "resolution_status": "resolved"}]
        accepted.extend({"severity": "suggestion", "evidence": value} for value in ([], None, 0, "", {}))
        for finding in accepted:
            with self.subTest(accepted=finding):
                receipt = {**base, "findings": [finding]}
                receipt.pop("fingerprint")
                receipt["fingerprint"] = canonical_sha256(receipt)
                validate_review_receipt(receipt)
                self.assertEqual([], review_receipt_findings(receipt, {"metrics.json": "a" * 64}))

    def test_finding_evidence_freshness_includes_artifacts_outside_coverage(self) -> None:
        receipt = build_review_receipt(
            review_id="review-evidence", reviewer="reviewer", independent=True,
            review_modes=["record"], status="passed",
            covered_artifacts=[{"path": "metrics.json", "sha256": "a" * 64}],
            covered_claim_ids=[], findings=[{
                "severity": "major", "resolution_status": "resolved", "evidence": [
                    {"artifact_path": "counter.json", "artifact_sha256": "b" * 64},
                    {"artifact_path": "manifest.json", "artifact_sha256": "d" * 64},
                    {"artifact_path": "review-task.json", "artifact_sha256": "e" * 64},
                ],
            }],
        )
        original = copy.deepcopy(receipt)
        for digest, stale in (("b" * 64, False), ("c" * 64, True)):
            with self.subTest(digest=digest):
                findings = review_receipt_findings(receipt, {"metrics.json": "a" * 64,
                                                           "counter.json": digest})
                self.assertEqual(stale, bool(findings))
                if stale:
                    self.assertEqual("stale-review-receipt", findings[0]["code"])
                    self.assertEqual("major", findings[0]["severity"])
                    self.assertIn("counter.json", findings[0]["message"])
        self.assertEqual([], review_receipt_findings(receipt, {"metrics.json": "a" * 64}))
        self.assertEqual(original, receipt)

    def test_review_receipt_requires_an_actual_reviewer_string(self) -> None:
        receipt = build_review_receipt(
            review_id="review-without-reviewer",
            reviewer="reviewer",
            independent=True,
            review_modes=["record"],
            status="passed",
            covered_artifacts=[{"path": "metrics.json", "sha256": "a" * 64}],
            covered_claim_ids=["claim-1"],
            findings=[],
            limitations=[],
        )
        receipt["reviewer"] = None
        receipt.pop("fingerprint")

        with self.assertRaisesRegex(ValueError, "reviewer is required"):
            validate_review_receipt(receipt)

    def test_seeded_reviewer_benchmark_has_zero_unsafe_passes(self) -> None:
        cases = load_cases(self.root / "benchmarks" / "reviewer")
        report = score_cases(cases)
        self.assertEqual(12, report["case_count"])
        self.assertEqual(0.0, report["unsafe_pass_rate"], json.dumps(report, indent=2))
        self.assertEqual(1.0, report["critical_recall"])
        self.assertEqual(1.0, report["major_recall"])
        self.assertEqual(1.0, report["severity_weighted_precision"])
        self.assertEqual(1.0, report["severity_weighted_recall"])
        self.assertEqual(0.0, report["false_positive_case_rate"])
        self.assertTrue(all(item["passed"] for item in report["details"]), json.dumps(report, indent=2))

    def test_train_test_case_id_matches_sample_overlap(self) -> None:
        case_ids = {item["case_id"] for item in load_cases(self.root / "benchmarks" / "reviewer")}
        self.assertIn("train-test-sample-id-overlap", case_ids)

    def test_duplicate_shared_cohort_case_is_not_in_corpus(self) -> None:
        case_ids = {item["case_id"] for item in load_cases(self.root / "benchmarks" / "reviewer")}
        self.assertNotIn("same-cohort-counted-as-independent-replication", case_ids)

    def test_structured_case_mutation_removes_finding_without_echoing_seeded_answers(self) -> None:
        cases = load_cases(self.root / "benchmarks" / "reviewer")
        case = copy.deepcopy(next(item for item in cases if item["case_id"] == "train-test-sample-id-overlap"))
        case["structured_review_input"]["model_evaluations"][0]["test_ids"] = ["held-out-only"]
        case["additional_findings"] = [{"code": "train-test-leakage", "severity": "major"}]

        report = score_cases([case])
        detail = report["details"][0]
        self.assertFalse(detail["passed"], json.dumps(detail, indent=2))
        self.assertEqual([], detail["actual"])
        self.assertEqual([("train-test-leakage", "major")], detail["missing"])


if __name__ == "__main__":
    unittest.main()
