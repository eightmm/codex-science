import unittest
import json
import hashlib
import tempfile
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
    def test_passed_review_keeps_only_unresolved_blocking_declared_findings(self) -> None:
        for severity in ("major", "critical", "minor", "suggestion"):
            for resolution in (None, "open", "", "accepted-risk", "resolved", "not-applicable", "unknown"):
                with self.subTest(severity=severity, resolution=resolution):
                    manifest = new_manifest("run", "Question", [])
                    finding = {"code": "declared", "severity": severity, "message": "Check evidence"}
                    if resolution is not None:
                        finding["resolution_status"] = resolution
                    manifest["review"] = {"status": "passed", "findings": [finding]}
                    blocking = severity in {"major", "critical"} and resolution not in {"resolved", "not-applicable"}
                    result = review_manifest(manifest)
                    self.assertEqual("findings" if blocking else "passed", result["status"])
                    self.assertEqual([finding] if blocking else [], result["findings"])
        manifest["review"] = {"status": "passed", "findings": ["invalid", None, 0]}
        self.assertEqual("passed", review_manifest(manifest)["status"])

    def test_distinct_declared_finding_ids_and_affected_claims_survive_dedup(self) -> None:
        manifest = new_manifest("run", "Question", [])
        critical = {"id": "F1", "affected_claim_id": "C1", "code": "unsupported", "message": "Check evidence", "severity": "critical"}
        minor = {**critical, "id": "F2", "affected_claim_id": "C2", "severity": "minor"}
        same_id = {**minor, "affected_claim_id": "C3"}
        same_claim = {**minor, "id": "F3"}
        manifest["review"] = {"status": "findings", "findings": [critical, minor, same_id, same_claim, minor]}
        findings = review_manifest(manifest)["findings"]
        self.assertEqual(4, len(findings))
        self.assertIn(critical, findings)
        self.assertIn(same_id, findings)
        self.assertIn(same_claim, findings)

    def test_execution_log_integrity_checks_active_and_superseded_records(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = root / "run"
            run.mkdir()
            log = run / "execution.log"
            outside = root / "outside.log"
            outside.write_bytes(b"recorded")
            alias = run / "alias.log"
            alias.symlink_to(outside)
            for field in ("executions", "superseded_executions"):
                for relative, content, expected in (
                    ("execution.log", b"recorded", None),
                    ("execution.log", b"", None),
                    ("execution.log", b"changed", "execution-log-mismatch"),
                    ("execution.log", None, "execution-log-missing"),
                    ("../outside.log", b"recorded", "execution-log-mismatch"),
                    ("alias.log", b"recorded", "execution-log-mismatch"),
                    ("\x00", b"recorded", "execution-log-mismatch"),
                ):
                    with self.subTest(field=field, relative=relative, content=content):
                        log.unlink(missing_ok=True)
                        if content is not None:
                            log.write_bytes(content)
                        manifest = new_manifest("run", "Question", [])
                        digest = hashlib.sha256(b"" if content == b"" else b"recorded").hexdigest()
                        manifest[field] = [{"id": "E1", "exit_code": 0, "log_path": relative, "log_sha256": digest}]
                        findings = review_manifest(manifest, run, sidecars={})["findings"]
                        self.assertEqual([] if expected is None else [expected], [item["code"] for item in findings])
                        if expected:
                            self.assertEqual("major", findings[0]["severity"])
            for entry in ({"log_path": "missing"}, {"log_sha256": "0" * 64}, {}):
                manifest["executions"] = [{"exit_code": 0, **entry}]
                manifest["superseded_executions"] = []
                self.assertEqual("passed", review_manifest(manifest, run, sidecars={})["status"])

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
