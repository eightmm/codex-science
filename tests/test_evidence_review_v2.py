import copy
import json
import subprocess
import sys
import tempfile
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

    def test_reviewer_benchmark_requires_directory_and_nonempty_safety_gate(self) -> None:
        script = self.root / "scripts" / "run_reviewer_benchmark.py"
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            regular = directory / "regular.txt"
            regular.write_text("not a directory", encoding="utf-8")
            for path in (directory / "missing", regular):
                with self.subTest(path=path):
                    with self.assertRaisesRegex(ValueError, "cases.*directory"):
                        load_cases(path)
                    result = subprocess.run([sys.executable, str(script), "--cases", str(path), "--require-safe"],
                                            capture_output=True, text=True)
                    self.assertNotEqual(0, result.returncode)
                    self.assertIn("error:", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
            self.assertEqual([], load_cases(directory))
            empty = score_cases([])
            for metric in ("severity_weighted_precision", "severity_weighted_recall", "severity_weighted_f1",
                           "critical_recall", "major_recall"):
                self.assertEqual(0.0, empty[metric], metric)
            result = subprocess.run([sys.executable, str(script), "--cases", str(directory), "--require-safe"],
                                    capture_output=True, text=True)
            self.assertNotEqual(0, result.returncode)
            self.assertEqual(0, json.loads(result.stdout)["case_count"])
            case = directory / "case.json"
            case.write_text("{}", encoding="utf-8")
            result = subprocess.run([sys.executable, str(script), "--cases", str(directory), "--require-safe"],
                                    capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(1, json.loads(result.stdout)["case_count"])

    def test_reviewer_benchmark_cli_reports_invalid_cases_without_traceback(self) -> None:
        script = self.root / "scripts" / "run_reviewer_benchmark.py"
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            case = directory / "case.json"
            invalid = [
                ('{"structured_review_input":{"schema":"wrong"}}', "structured_review_input"),
                ('{', None), ('[]', None),
                ('{"expected_findings": [{}]}', "expected_findings[0].code"),
                ('{"expected_findings": null}', "expected_findings"),
                ('{"expected_findings": [{"code": 1}]}', "expected_findings[0].code"),
                ('{"expected_findings": [null]}', "expected_findings[0]"),
                ('{"expected_findings": {}}', "expected_findings"),
                ('{"expected_findings": [{"code": ""}]}', "expected_findings[0].code"),
                ('{"additional_findings": null}', "additional_findings"),
                ('{"additional_findings": 42}', "additional_findings"),
            ]
            receipt = build_review_receipt(
                review_id="shape-check", reviewer="fixture-reviewer", independent=True,
                review_modes=["record"], status="passed",
                covered_artifacts=[{"path": "metrics.json", "sha256": "a" * 64}],
                covered_claim_ids=["C"], covered_registry_sha256="b" * 64,
                findings=[{"id": "F", "code": "fixture", "message": "fixture finding",
                           "severity": "minor", "resolution_status": "open", "evidence": [
                               {"artifact_path": "metrics.json", "artifact_sha256": "a" * 64}]}],
                limitations=["fixture limitation"],
            )
            receipt_case = {"review_receipt": receipt, "artifact_hashes": {"metrics.json": "a" * 64},
                            "registry_sha256": "b" * 64}
            graph_case = {"evidence_graph_v2": {"schema_version": 2,
                "nodes": [{"id": "S", "type": "study"}, {"id": "C", "type": "claim"}],
                "edges": [{"source": "S", "target": "C", "relation": "supports"}]},
                "replicated_claim_id": "C"}
            structured_case = json.loads((self.root / "benchmarks" / "reviewer" / "67-clean-control.json").read_text())
            finding_case = {"case_id": "shape-check", "expected_findings": [{"code": "fixture", "severity": "minor"}],
                            "additional_findings": [{"code": "fixture", "severity": "minor", "message": "fixture"}]}
            mutations = [
                (finding_case, [
                    (("case_id",), 0),
                    (("expected_findings", 0, "severity"), []),
                    (("expected_findings", 0, "severity"), "urgent"),
                    (("additional_findings",), {}),
                    (("additional_findings", 0), None),
                    (("additional_findings", 0, "code"), 0),
                    (("additional_findings", 0, "severity"), None),
                    (("additional_findings", 0, "message"), []),
                ]),
                (graph_case, [
                    (("replicated_claim_id",), 0),
                    (("evidence_graph_v2", "nodes"), None),
                    (("evidence_graph_v2", "nodes", 0), []),
                    (("evidence_graph_v2", "nodes", 0, "id"), []),
                    (("evidence_graph_v2", "nodes", 0, "id"), True),
                    (("evidence_graph_v2", "edges"), None),
                    (("evidence_graph_v2", "edges", 0), []),
                    (("evidence_graph_v2", "edges", 0, "source"), []),
                    (("evidence_graph_v2", "edges", 0, "target"), []),
                    (("evidence_graph_v2", "edges", 0, "relation"), []),
                ]),
                (receipt_case, [(("artifact_hashes",), None), (("artifact_hashes",), 42)]),
                (structured_case, [
                    (("structured_review_input",), None),
                    (("structured_review_input", "claims"), None),
                    (("structured_review_input", "claims", 0), []),
                    (("structured_review_input", "claims", 0, "id"), []),
                    (("structured_review_input", "claims", 0, "kind"), []),
                    (("structured_review_input", "claims", 0, "population"), []),
                    (("structured_review_input", "claims", 0, "supported_by"), None),
                    (("structured_review_input", "claims", 0, "supported_by", 0), []),
                    (("structured_review_input", "claims", 0, "significant"), 1),
                    (("structured_review_input", "studies"), None),
                    (("structured_review_input", "studies", 0), []),
                    (("structured_review_input", "studies", 0, "id"), []),
                    (("structured_review_input", "studies", 0, "design"), []),
                    (("structured_review_input", "studies", 0, "population"), []),
                    (("structured_review_input", "analyses"), None),
                    (("structured_review_input", "analyses", 0), []),
                    (("structured_review_input", "analyses", 0, "claim_id"), []),
                    (("structured_review_input", "analyses", 0, "tests_performed"), 0),
                    (("structured_review_input", "analyses", 0, "tests_performed"), int(sys.float_info.max) + 1),
                    (("structured_review_input", "analyses", 0, "alpha"), True),
                    (("structured_review_input", "analyses", 0, "correction"), []),
                    (("structured_review_input", "model_evaluations"), None),
                    (("structured_review_input", "model_evaluations", 0), []),
                    (("structured_review_input", "model_evaluations", 0, "train_ids"), None),
                    (("structured_review_input", "model_evaluations", 0, "test_ids"), None),
                    (("structured_review_input", "model_evaluations", 0, "train_ids", 0), None),
                    (("structured_review_input", "model_evaluations", 0, "test_ids", 0), None),
                    (("structured_review_input", "model_evaluations", 0, "train_groups"), None),
                    (("structured_review_input", "model_evaluations", 0, "test_groups"), None),
                    (("structured_review_input", "model_evaluations", 0, "train_groups", "patient"), None),
                    (("structured_review_input", "model_evaluations", 0, "test_groups", "patient"), None),
                    (("structured_review_input", "model_evaluations", 0, "train_groups", "patient", 0), None),
                    (("structured_review_input", "model_evaluations", 0, "test_groups", "patient", 0), None),
                    (("structured_review_input", "model_evaluations", 0, "train_groups"), {" ": []}),
                    (("structured_review_input", "source_records"), None),
                    (("structured_review_input", "source_records", 0), []),
                    (("structured_review_input", "source_records", 0, "id"), []),
                    (("structured_review_input", "source_records", 0, "value"), True),
                    (("structured_review_input", "source_records", 0, "value"), float("inf")),
                    (("structured_review_input", "source_records", 0, "unit"), []),
                    (("structured_review_input", "reported_quantities"), None),
                    (("structured_review_input", "reported_quantities", 0), []),
                    (("structured_review_input", "reported_quantities", 0, "source_id"), []),
                    (("structured_review_input", "reported_quantities", 0, "value"), True),
                    (("structured_review_input", "reported_quantities", 0, "unit"), []),
                ]),
            ]
            for base, changes in mutations:
                for path, value in changes:
                    payload = copy.deepcopy(base)
                    parent = payload
                    for part in path[:-1]:
                        parent = parent[part]
                    parent[path[-1]] = value
                    field = "".join(f"[{part}]" if isinstance(part, int) else ("." if index else "") + part
                                    for index, part in enumerate(path))
                    invalid.append((json.dumps(payload), field))
            for contents, field in invalid:
                with self.subTest(contents=contents):
                    case.write_text(contents, encoding="utf-8")
                    result = subprocess.run([sys.executable, str(script), "--cases", str(directory)],
                                            capture_output=True, text=True)
                    self.assertEqual(2, result.returncode, result.stderr)
                    self.assertIn("error:", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertEqual("", result.stdout)
                    if field is not None:
                        self.assertIn(case.name, result.stderr)
                        if field.startswith("evidence_graph_v2."):
                            self.assertIn("evidence_graph_v2", result.stderr)
                        elif field.startswith("structured_review_input."):
                            self.assertIn("structured_review_input", result.stderr)
                            self.assertIn(field.rsplit(".", 1)[-1], result.stderr)
                        else:
                            self.assertIn(field, result.stderr)
                        with self.assertRaises(ValueError) as raised:
                            load_cases(directory)
                        self.assertIn(case.name, str(raised.exception))
            numeric_graph = copy.deepcopy(graph_case)
            numeric_graph["evidence_graph_v2"]["nodes"][0]["id"] = 0
            numeric_graph["evidence_graph_v2"]["edges"][0]["source"] = 0
            empty_message = copy.deepcopy(finding_case)
            empty_message["additional_findings"][0]["message"] = ""
            extreme_count = copy.deepcopy(structured_case)
            extreme_count["structured_review_input"]["analyses"][0]["tests_performed"] = int(sys.float_info.max)
            compatible = []
            for evidence in (None, 0, "", {}):
                valid = copy.deepcopy(receipt_case)
                valid["review_receipt"]["findings"][0]["evidence"] = evidence
                valid["review_receipt"].pop("fingerprint")
                valid["review_receipt"]["fingerprint"] = canonical_sha256(valid["review_receipt"])
                compatible.append(valid)
            for field, value in (("id", 3), ("covered_claim_ids", [" "])):
                valid = copy.deepcopy(receipt_case)
                if field == "id":
                    valid["review_receipt"]["findings"][0][field] = value
                else:
                    valid["review_receipt"][field] = value
                valid["review_receipt"].pop("fingerprint")
                valid["review_receipt"]["fingerprint"] = canonical_sha256(valid["review_receipt"])
                compatible.append(valid)
            for graph_value in (None, 0, []):
                compatible.append({"evidence_graph_v2": graph_value})
            float_graph = copy.deepcopy(graph_case)
            float_graph["evidence_graph_v2"]["nodes"][0]["id"] = 0.5
            float_graph["evidence_graph_v2"]["edges"][0]["source"] = 0.5
            compatible.append(float_graph)
            coerced_type = copy.deepcopy(graph_case)
            coerced_type["evidence_graph_v2"]["nodes"][0]["type"] = 3
            compatible.append(coerced_type)
            float_version = copy.deepcopy(graph_case)
            float_version["evidence_graph_v2"]["schema_version"] = 2.0
            compatible.append(float_version)
            for receipt_value in ({"schema_version": 2}, {**receipt, "status": "unknown"}):
                compatible.append({"review_receipt": receipt_value, "expected_findings": [
                    {"code": "invalid-review-receipt", "severity": "critical"}]})
            for valid in ({"expected_findings": [], "additional_findings": []}, finding_case, graph_case,
                          receipt_case, structured_case, numeric_graph, empty_message, extreme_count,
                          {"review_packet": {"unused_metadata": 42}, "registry_sha256": None}, *compatible):
                with self.subTest(valid=valid):
                    original = copy.deepcopy(valid)
                    case.write_text(json.dumps(valid), encoding="utf-8")
                    self.assertEqual([original], load_cases(directory))
                    report = score_cases(load_cases(directory))
                    self.assertEqual(score_cases([original]), report)
                    self.assertEqual(1, report["case_count"])
                    if original.get("expected_findings") == [{"code": "invalid-review-receipt", "severity": "critical"}]:
                        self.assertTrue(report["details"][0]["passed"])

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
