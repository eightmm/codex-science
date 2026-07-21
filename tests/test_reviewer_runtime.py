import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from codex_science.artifacts import add_artifact, new_manifest, write_manifest
from codex_science.reviewer_runtime import build_review_packet, finalize_review_response, validate_review_packet
from codex_science.review_receipts import validate_review_receipt


def make_reviewed_run(root: Path) -> Path:
    run = root / "run"
    run.mkdir()
    evidence = run / "evidence.json"
    evidence.write_text('{"estimate": 0.72}\n', encoding="utf-8")
    digest = hashlib.sha256(evidence.read_bytes()).hexdigest()
    manifest = new_manifest(
        "review-source-run",
        "Does the evidence support the bounded association claim?",
        [{"id": "analyze", "description": "Analyze the recorded evidence", "status": "completed"}],
    )
    manifest["inputs"] = [{"id": "study", "identifier": "pmid:12345678", "token": "must-redact"}]
    manifest["code"] = [{"path": "analysis.py", "revision": "abc"}]
    manifest["executions"] = [{"command": "python analysis.py", "exit_code": 0}]
    manifest["environment"] = {"python": "3.12", "API_TOKEN": "must-redact"}
    manifest["claims"] = [{"id": "C1", "text": "The recorded study supports an association.", "evidence": ["evidence.json"], "producer_rationale": "must-exclude"}]
    manifest["review"] = {"status": "passed", "findings": []}
    add_artifact(manifest, "evidence.json", kind="study-evidence", sha256=digest)
    path = run / "manifest.json"
    write_manifest(manifest, path)
    return path


class ReviewerRuntimeTests(unittest.TestCase):
    def test_packet_is_hash_bound_and_excludes_producer_only_context(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest = make_reviewed_run(Path(tempdir))
            packet = build_review_packet(
                manifest,
                review_modes=["record", "method"],
                created_at="2026-07-21T00:00:00Z",
            )
            validate_review_packet(packet)
            serialized = json.dumps(packet)
            self.assertNotIn("must-exclude", serialized)
            self.assertNotIn("must-redact", serialized)
            self.assertIn("[REDACTED]", serialized)
            self.assertEqual(["C1"], packet["material_claim_ids"])
            self.assertEqual(1, len(packet["artifacts"]))
            self.assertTrue(packet["independent_required"])

    def test_complete_independent_response_builds_passed_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest = make_reviewed_run(Path(tempdir))
            packet = build_review_packet(
                manifest,
                review_modes=["record", "method"],
                created_at="2026-07-21T00:00:00Z",
            )
            artifact = packet["artifacts"][0]
            response = {
                "schema_version": 1,
                "review_task_id": packet["review_task_id"],
                "packet_fingerprint": packet["fingerprint"],
                "reviewer": "independent-reviewer-1",
                "independent": True,
                "review_modes": ["record", "method"],
                "reviewed_claim_ids": ["C1"],
                "reviewed_artifacts": [{"path": artifact["path"], "sha256": artifact["sha256"]}],
                "findings": [],
                "limitations": ["The source study is not independently reproduced in this review."],
                "status": "passed"
            }
            receipt = finalize_review_response(packet, response)
            validate_review_receipt(receipt)
            self.assertEqual("passed", receipt["status"])
            self.assertTrue(receipt["independent"])
            self.assertEqual(packet["review_task_id"], receipt["review_task_id"])

    def test_nonindependent_or_incomplete_review_cannot_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest = make_reviewed_run(Path(tempdir))
            packet = build_review_packet(
                manifest,
                review_modes=["record"],
                created_at="2026-07-21T00:00:00Z",
            )
            artifact = packet["artifacts"][0]
            response = {
                "schema_version": 1,
                "review_task_id": packet["review_task_id"],
                "packet_fingerprint": packet["fingerprint"],
                "reviewer": "producer-second-pass",
                "independent": False,
                "review_modes": ["record"],
                "reviewed_claim_ids": [],
                "reviewed_artifacts": [{"path": artifact["path"], "sha256": artifact["sha256"]}],
                "findings": [],
                "limitations": ["Same producer context."],
                "blocked_reason": "No independent reviewer was available.",
                "status": "passed"
            }
            receipt = finalize_review_response(packet, response)
            self.assertEqual("findings", receipt["status"])
            codes = {item["code"] for item in receipt["findings"]}
            self.assertIn("review-not-independent", codes)
            self.assertIn("incomplete-review-coverage", codes)

    def test_response_cannot_substitute_artifact_hash_or_unknown_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest = make_reviewed_run(Path(tempdir))
            packet = build_review_packet(manifest, review_modes=["record"], created_at="2026-07-21T00:00:00Z")
            base = {
                "schema_version": 1,
                "review_task_id": packet["review_task_id"],
                "packet_fingerprint": packet["fingerprint"],
                "reviewer": "reviewer",
                "independent": True,
                "review_modes": ["record"],
                "reviewed_claim_ids": ["C1"],
                "reviewed_artifacts": [{"path": packet["artifacts"][0]["path"], "sha256": "0" * 64}],
                "findings": [],
                "limitations": ["Limited."],
                "status": "passed"
            }
            with self.assertRaisesRegex(ValueError, "does not match"):
                finalize_review_response(packet, base)
            changed = dict(base)
            changed["reviewed_claim_ids"] = ["UNKNOWN"]
            changed["reviewed_artifacts"] = [{"path": packet["artifacts"][0]["path"], "sha256": packet["artifacts"][0]["sha256"]}]
            with self.assertRaisesRegex(ValueError, "unknown claims"):
                finalize_review_response(packet, changed)


if __name__ == "__main__":
    unittest.main()
