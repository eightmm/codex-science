import unittest

from codex_science.artifacts import add_artifact, new_manifest
from codex_science.review import review_manifest


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


if __name__ == "__main__":
    unittest.main()
