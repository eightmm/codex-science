"""Exercise the review-integrity contract on a deterministic recorded run."""

import copy
import hashlib
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from codex_science.artifacts import add_artifact
from codex_science.review_receipts import validate_review_receipt
from codex_science.reviewer_runtime import (
    build_review_packet,
    finalize_review_response,
    respond_to_review,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "science-review"
QUALITY = ROOT / "runtime-skills" / "science-review" / "quality.json"
SEEDED_FAILURE_TESTS = {
    "stale-reviewed-artifact": "test_stale_reviewed_artifact_is_refused",
    "open-blocking-finding": "test_open_blocking_finding_cannot_pass",
    "nonindependent-review": "test_nonindependent_review_cannot_pass",
    "response-packet-mismatch": "test_response_packet_mismatch_is_refused",
    "finding-outside-packet": "test_finding_outside_packet_is_refused",
    "finalize-unbound-evidence": "test_finalize_unbound_evidence_is_refused",
    "omitted-material-claim": "test_omitted_material_claim_is_refused",
}


class ScienceReviewAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.run_dir = Path(temporary.name)
        self.manifest_path = self.run_dir / "manifest.json"
        shutil.copyfile(FIXTURE / "input.json", self.manifest_path)
        self.manifest = self.read(self.manifest_path)
        for artifact in self.manifest["artifacts"]:
            shutil.copyfile(FIXTURE / artifact["path"], self.run_dir / artifact["path"])
        self.packet = build_review_packet(
            self.manifest_path,
            review_modes=["record"],
            created_at="2026-07-21T00:00:00Z",
        )
        self.task_path = self.run_dir / "review-task.json"
        self.response_path = self.run_dir / "reviewer-response.json"
        self.write(self.task_path, self.packet)

    @staticmethod
    def read(path):
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def write(path, payload):
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def respond(self, **overrides):
        arguments = {
            "reviewer": "fixture-reviewer",
            "independent": True,
            "status": "passed",
            "limitations": ["Deterministic record review; no empirical reproduction."],
            "reviewed_all": True,
        }
        arguments.update(overrides)
        result = respond_to_review(self.task_path, **arguments)
        return result, self.read(self.response_path)

    def finding(self):
        return {
            "id": "F-denominator",
            "severity": "major",
            "code": "wrong-denominator",
            "message": "The reported denominator disagrees with the saved record.",
            "affected_claim_id": "C1",
            "required_action": "Correct the denominator and review the changed claim.",
            "resolution_status": "open",
            "evidence": [{"artifact_path": "evidence.txt", "line_range": [1, 1]}],
        }

    def validate_receipt(self, receipt):
        """Use the same completion CLI for passed and failing review receipts."""
        path = self.run_dir / "review-receipt-v2.json"
        self.write(path, receipt)
        manifest = copy.deepcopy(self.manifest)
        add_artifact(
            manifest, path.name, kind="review-receipt-v2",
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        self.write(self.manifest_path, manifest)
        spec = importlib.util.spec_from_file_location(
            "science_review_acceptance_validator", ROOT / "scripts" / "validate_artifact.py",
        )
        assert spec is not None and spec.loader is not None
        validator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(validator)
        report = self.run_dir / "deterministic-review.json"
        argv = [str(spec.origin), str(self.manifest_path), "--review-output", str(report),
                "--require-passed-review"]
        stdout, stderr = io.StringIO(), io.StringIO()
        code = 0
        with patch.object(sys, "argv", argv), redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                validator.main()
            except SystemExit as error:
                code = error.code
        return code, stdout.getvalue() + stderr.getvalue(), self.read(report)

    def test_acceptance_fixture_passes_the_public_review_workflow(self) -> None:
        self.assertEqual((FIXTURE / "input.json").read_bytes(), self.manifest_path.read_bytes())
        self.assertEqual("science-review-acceptance", self.packet["source_run_id"])
        self.assertEqual(
            hashlib.sha256(self.manifest_path.read_bytes()).hexdigest(),
            self.packet["source_manifest_sha256"],
        )
        self.assertTrue(self.packet["independent_required"])
        self.assertEqual(["C1"], self.packet["material_claim_ids"])
        self.assertEqual(
            self.packet,
            build_review_packet(self.manifest_path, review_modes=["record"],
                                created_at="2026-07-21T00:00:00Z"),
        )
        result, response = self.respond()
        self.assertEqual("passed", result["effective_status"])
        self.assertEqual(1, result["reviewed_artifacts"])
        self.assertEqual(1, result["reviewed_claims"])
        receipt = finalize_review_response(self.packet, response)
        validate_review_receipt(receipt)
        self.assertEqual("passed", receipt["status"])
        self.assertEqual([], receipt["findings"])
        self.assertTrue(receipt["independent"])
        self.assertEqual(["record"], receipt["review_modes"])
        self.assertEqual(["C1"], receipt["covered_claim_ids"])
        self.assertEqual(self.packet["review_task_id"], receipt["review_task_id"])
        self.assertEqual(self.packet["fingerprint"], receipt["packet_fingerprint"])
        self.assertEqual(self.packet["artifacts"][0]["sha256"],
                         receipt["covered_artifacts"][0]["sha256"])
        self.assertTrue(receipt["limitations"])
        code, output, review = self.validate_receipt(receipt)
        self.assertEqual(0, code, output)
        self.assertIn("artifact review: passed", output)
        self.assertEqual({"status": "passed", "findings": []}, review)

    def test_stale_reviewed_artifact_is_refused(self) -> None:
        evidence = self.run_dir / "evidence.txt"
        for changed in ("Recorded fixture estimate: 0.99\n", "", None):
            with self.subTest(changed=changed):
                if changed is None:
                    evidence.unlink()
                else:
                    evidence.write_text(changed, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "artifact bytes no longer match the packet"):
                    self.respond()
                self.assertFalse(self.response_path.exists())

    def test_open_blocking_finding_cannot_pass(self) -> None:
        findings_path = self.run_dir / "findings.json"
        for severity in ("major", "critical"):
            with self.subTest(severity=severity):
                finding = self.finding()
                finding["severity"] = severity
                self.write(findings_path, [finding])
                result, response = self.respond(findings_path=findings_path)
                self.assertEqual("passed", result["requested_status"])
                self.assertEqual("findings", result["effective_status"])
                receipt = finalize_review_response(self.packet, response)
                self.assertEqual("findings", receipt["status"])
                self.assertEqual("wrong-denominator", receipt["findings"][0]["code"])
                self.assertIn("denominator disagrees", receipt["findings"][0]["message"])
                self.assertEqual(self.packet["artifacts"][0]["sha256"],
                                 receipt["findings"][0]["evidence"][0]["artifact_sha256"])
                code, output, review = self.validate_receipt(receipt)
                self.assertEqual("artifact review has unresolved findings", code)
                self.assertIn("artifact review: findings", output)
                self.assertIn("wrong-denominator", {item["code"] for item in review["findings"]})

    def test_nonindependent_review_cannot_pass(self) -> None:
        result, response = self.respond(independent=False)
        self.assertEqual("findings", result["effective_status"])
        receipt = finalize_review_response(self.packet, response)
        self.assertEqual("findings", receipt["status"])
        finding = receipt["findings"][0]
        self.assertEqual("review-not-independent", finding["code"])
        self.assertIn("required independence", finding["message"])
        self.assertFalse(receipt["independent"])

    def test_response_packet_mismatch_is_refused(self) -> None:
        _, response = self.respond()
        for field in ("review_task_id", "packet_fingerprint"):
            for value in ("", "0" * 64, None):
                with self.subTest(field=field, value=value):
                    changed = copy.deepcopy(response)
                    changed[field] = value
                    with self.assertRaisesRegex(ValueError, "review response covers a different packet"):
                        finalize_review_response(self.packet, changed)

    def test_finding_outside_packet_is_refused(self) -> None:
        findings_path = self.run_dir / "findings.json"
        for path in ("unreviewed.txt", "", "../outside.txt"):
            with self.subTest(path=path):
                finding = self.finding()
                finding["evidence"][0]["artifact_path"] = path
                self.write(findings_path, [finding])
                with self.assertRaisesRegex(ValueError, "evidence 0 path not in packet"):
                    self.respond(findings_path=findings_path)
                self.assertFalse(self.response_path.exists())

    def test_finalize_unbound_evidence_is_refused(self) -> None:
        _, response = self.respond()
        path = self.packet["artifacts"][0]["path"]
        cases = (
            ({"artifact_path": "unreviewed.txt", "artifact_sha256": "0" * 64},
             "path not in packet: unreviewed.txt"),
            ({"artifact_path": path, "artifact_sha256": "0" * 64},
             f"hash differs from packet: {path}"),
            ({"url": "https://example.org/study", "locator": "Table 1"},
             "path not in packet: <missing>"),
            ({}, "path not in packet: <missing>"),
            (None, "must be an object"),
            (0, "must be an object"),
            ("", "must be an object"),
            ([], "must be an object"),
        )
        output = self.run_dir / "review-receipt-v2.json"
        for evidence, message in cases:
            for existing in (False, True):
                with self.subTest(evidence=evidence, existing=existing):
                    if existing:
                        output.write_text("existing receipt\n", encoding="utf-8")
                    finding = self.finding()
                    finding["evidence"] = [evidence]
                    response["findings"] = [finding]
                    self.write(self.response_path, response)
                    result = subprocess.run(
                        [sys.executable, str(ROOT / "scripts" / "science_reviewer.py"), "finalize",
                         str(self.task_path), str(self.response_path), "--output", str(output)],
                        capture_output=True, text=True, check=False,
                    )
                    self.assertEqual(1, result.returncode, result.stdout + result.stderr)
                    self.assertEqual(f"error: finding F-denominator evidence 0 {message}", result.stderr.strip())
                    if existing:
                        self.assertEqual("existing receipt\n", output.read_text(encoding="utf-8"))
                        output.unlink()
                    else:
                        self.assertFalse(output.exists())

    def test_omitted_material_claim_is_refused(self) -> None:
        _, response = self.respond()
        response["reviewed_claim_ids"] = []
        with self.assertRaisesRegex(ValueError, "review omits material claims without blocked_reason: C1"):
            finalize_review_response(self.packet, response)
        response["blocked_reason"] = "The material record could not be assessed."
        receipt = finalize_review_response(self.packet, response)
        self.assertEqual("findings", receipt["status"])
        self.assertEqual("incomplete-review-coverage", receipt["findings"][0]["code"])
        self.assertIn("Material claims were not reviewed: C1", receipt["findings"][0]["message"])

    def test_quality_seeded_failures_have_executable_tests(self) -> None:
        quality = self.read(QUALITY)
        self.assertEqual("L4", quality["declared_maturity"])
        self.assertEqual(set(SEEDED_FAILURE_TESTS), set(quality["seeded_failures"]))
        self.assertEqual(len(SEEDED_FAILURE_TESTS), len(quality["seeded_failures"]))
        self.assertEqual(len(SEEDED_FAILURE_TESTS), len(set(SEEDED_FAILURE_TESTS.values())))
        for name, method in SEEDED_FAILURE_TESTS.items():
            with self.subTest(seeded_failure=name):
                self.assertTrue(method.startswith("test_"))
                self.assertTrue(callable(getattr(type(self), method, None)))
        self.assertIn("examples/science-review/input.json", quality["acceptance_fixtures"])
        self.assertIn("tests/test_science_review_acceptance.py", quality["test_files"])


if __name__ == "__main__":
    unittest.main()
