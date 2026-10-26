import unittest
import json
from pathlib import Path

from codex_science.artifacts import add_artifact, new_manifest, validate_bundle
from codex_science.review import review_manifest


def computed_review(manifest: dict, supporting_nodes: list[dict], supporting_edges: list[dict] | None = None) -> dict:
    claim_id = "C1"
    nodes = [{"id": claim_id, "type": "claim"}, *supporting_nodes]
    edges = supporting_edges or [
        {"source": node["id"], "target": claim_id, "relation": "supports"}
        for node in supporting_nodes
    ]
    sidecars = {
        "claim_by_id": {claim_id: {"id": claim_id, "required_evidence": ["computed"]}},
        "graph_v2": {"nodes": nodes, "edges": edges},
    }
    return review_manifest(manifest, sidecars=sidecars)


class ReviewerTests(unittest.TestCase):
    def test_flags_failed_execution_missing_evidence_and_incomplete_plan(self) -> None:
        manifest = new_manifest(
            "run-001",
            "Question",
            [{"id": "step-1", "description": "Run analysis", "status": "pending"}],
        )
        manifest["executions"].append({"command": "python analysis.py", "exit_code": 1})
        manifest["claims"].append(
            {"id": "claim-1", "text": "The analysis improved accuracy.", "evidence": ["missing.json"]}
        )

        review = review_manifest(manifest)

        codes = {finding["code"] for finding in review["findings"]}
        self.assertIn("failed-execution", codes)
        self.assertIn("missing-evidence", codes)
        failed = next(f["message"] for f in review["findings"] if f["code"] == "failed-execution")
        self.assertIn("exits 0 only when the expected rejection is observed", failed)
        message = next(f["message"] for f in review["findings"] if f["code"] == "missing-evidence")
        self.assertIn("missing.json", message)
        self.assertIn("claim-1", message)
        self.assertIn("manifest artifact paths", message)
        self.assertIn("incomplete-plan", codes)
        self.assertEqual("findings", review["status"])

    def test_clean_record_passes(self) -> None:
        manifest = new_manifest(
            "run-001",
            "Question",
            [{"id": "step-1", "description": "Run analysis", "status": "completed"}],
        )
        manifest["executions"].append({"command": "python analysis.py", "exit_code": 0})
        add_artifact(manifest, "result.json", kind="table", sha256="b" * 64)
        manifest["claims"].append(
            {"id": "claim-1", "text": "The analysis completed.", "evidence": ["result.json"]}
        )

        review = review_manifest(manifest)

        self.assertEqual("passed", review["status"])
        self.assertEqual([], review["findings"])

    def test_legacy_computed_claim_without_execution_ids_has_no_new_finding(self) -> None:
        manifest = new_manifest("run-001", "Question", [])
        manifest["executions"] = [{"command": "python analysis.py", "exit_code": 0}]
        manifest["claims"] = [{"id": "C1", "text": "The calculation yielded 4.", "evidence": ["result.json"]}]

        review = computed_review(manifest, [{"id": "execution-1", "type": "execution"}])

        self.assertNotIn("computed-claim-without-execution", {item["code"] for item in review["findings"]})

        manifest["executions"] = []
        review = computed_review(manifest, [{"id": "execution-1", "type": "execution"}])
        self.assertIn("computed-claim-without-execution", {item["code"] for item in review["findings"]})

        review = review_manifest(
            manifest,
            sidecars={
                "claim_by_id": {"C1": {"id": "C1", "required_evidence": []}},
                "graph_v2": {
                    "nodes": [
                        {"id": "C1", "type": "claim"},
                        {"id": "result.json", "type": "artifact", "path": "result.json"},
                    ],
                    "edges": [{"source": "result.json", "target": "C1", "relation": "supports"}],
                },
            },
        )

        self.assertNotIn("computed-claim-without-execution", {item["code"] for item in review["findings"]})

    def test_boolean_exit_code_is_not_a_successful_execution(self) -> None:
        manifest = new_manifest("run-001", "Question", [])
        manifest["executions"] = [{"id": "execution-1", "command": "python analysis.py", "exit_code": False}]
        manifest["claims"] = [{"id": "C1", "text": "The calculation yielded 4.", "evidence": ["result.json"]}]

        review = computed_review(manifest, [{"id": "execution-1", "type": "execution"}])
        codes = {item["code"] for item in review["findings"]}

        self.assertIn("failed-execution", codes)
        self.assertIn("computed-claim-without-execution", codes)

    def test_computed_claim_linked_to_successful_execution_passes(self) -> None:
        manifest = new_manifest("run-001", "Question", [])
        manifest["executions"] = [{"id": "execution-1", "command": "python analysis.py", "exit_code": 0}]
        manifest["claims"] = [{"id": "C1", "text": "The calculation yielded 4.", "evidence": ["result.json"]}]

        review = computed_review(manifest, [{"id": "execution-1", "type": "execution"}])

        self.assertNotIn("computed-claim-without-execution", {item["code"] for item in review["findings"]})

    def test_computed_claim_linked_to_failed_or_unknown_execution_is_reported(self) -> None:
        for execution in (
            {"id": "execution-1", "command": "python analysis.py", "exit_code": 1},
            {"id": "other-execution", "command": "python other.py", "exit_code": 0},
        ):
            with self.subTest(execution=execution):
                manifest = new_manifest("run-001", "Question", [])
                manifest["executions"] = [execution]
                manifest["claims"] = [{"id": "C1", "text": "The calculation yielded 4.", "evidence": ["result.json"]}]

                review = computed_review(manifest, [{"id": "execution-1", "type": "execution"}])

                findings = [item for item in review["findings"] if item["code"] == "computed-claim-without-execution"]
                self.assertEqual(1, len(findings))
                self.assertEqual("major", findings[0]["severity"])
                self.assertIn("C1", findings[0]["message"])

    def test_computed_artifact_with_declared_outputs_requires_a_successful_output_match(self) -> None:
        manifest = new_manifest("run-001", "Question", [])
        manifest["executions"] = [{"id": "execution-1", "exit_code": 0, "outputs": ["other.json"]}]
        manifest["artifacts"] = [{"path": "result.json", "kind": "data", "sha256": "a" * 64}]
        manifest["claims"] = [{"id": "C1", "text": "The calculation yielded 4.", "evidence": ["result.json"]}]

        review = computed_review(manifest, [{"id": "result.json", "type": "artifact", "path": "result.json", "sha256": "a" * 64}])

        self.assertIn("computed-claim-without-execution", {item["code"] for item in review["findings"]})

    def test_computed_claim_is_checked_even_with_study_support_and_literature_claim_is_not(self) -> None:
        manifest = new_manifest("run-001", "Question", [])
        manifest["executions"] = [{"id": "unrelated-execution", "exit_code": 0}]
        manifest["claims"] = [
            {"id": "C1", "text": "The calculation agrees with the cited study.", "evidence": ["study.json"]},
            {"id": "C2", "text": "The study reports an association.", "evidence": ["study.json"]},
        ]
        nodes = [
            {"id": "C1", "type": "claim"}, {"id": "C2", "type": "claim"},
            {"id": "study-1", "type": "study"}, {"id": "execution-1", "type": "execution"},
        ]
        sidecars = {
            "claim_by_id": {
                "C1": {"id": "C1", "required_evidence": ["computed"]},
                "C2": {"id": "C2", "required_evidence": ["primary"]},
            },
            "graph_v2": {
                "nodes": nodes,
                "edges": [
                    {"source": "study-1", "target": "C1", "relation": "supports"},
                    {"source": "execution-1", "target": "C1", "relation": "supports"},
                    {"source": "study-1", "target": "C2", "relation": "supports"},
                ],
            },
        }

        review = review_manifest(manifest, sidecars=sidecars)
        findings = [item for item in review["findings"] if item["code"] == "computed-claim-without-execution"]

        self.assertEqual(["C1"], [item["claim_id"] for item in findings])

    def test_example_bundles_keep_their_existing_review_status(self) -> None:
        root = Path(__file__).resolve().parents[1]
        expected = {
            "life-science-reviewed-run": "passed",
            "literature-review-reviewed-run": "passed",
            "reviewed-run": "passed",
        }
        for name, status in expected.items():
            manifest_path = root / "examples" / name / "manifest.json"
            with self.subTest(example=name):
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                sidecars = validate_bundle(manifest, manifest_path.parent)
                self.assertEqual(status, review_manifest(manifest, manifest_path.parent, sidecars=sidecars)["status"])


if __name__ == "__main__":
    unittest.main()
