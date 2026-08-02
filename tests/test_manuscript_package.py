import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.manuscript import (  # noqa: E402
    _scalar_appears_in_text,
    build_acceptance_package,
    validate_manuscript_package,
)
from codex_science.review_receipts import (  # noqa: E402
    build_review_receipt,
    canonical_sha256,
)


class ManuscriptPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.package = Path(self.tempdir.name) / "package"
        specification = json.loads(
            (ROOT / "examples" / "manuscript-writing" / "input.json").read_text(
                encoding="utf-8"
            )
        )
        build_acceptance_package(specification, self.package)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def findings(self) -> set[str]:
        return {
            finding["code"]
            for finding in validate_manuscript_package(self.package)["findings"]
        }

    def rewrite_json(self, name: str, payload: dict) -> None:
        (self.package / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def refresh_submission_hash(self, relative: str) -> None:
        submission_path = self.package / "submission-package.json"
        submission = json.loads(submission_path.read_text(encoding="utf-8"))
        digest = hashlib.sha256((self.package / relative).read_bytes()).hexdigest()
        for record in submission["files"]:
            if record["path"] == relative:
                record["sha256"] = digest
                break
        else:
            self.fail(f"submission package does not list {relative}")
        self.rewrite_json(submission_path.name, submission)

    def make_submission_ready(
        self,
        *,
        covered_paths: set[str] | None = None,
        independent: bool = True,
        review_modes: list[str] | None = None,
    ) -> None:
        submission_path = self.package / "submission-package.json"
        submission = json.loads(submission_path.read_text(encoding="utf-8"))
        available = {
            record["path"]: record["sha256"]
            for record in submission["files"]
        }
        selected = set(available) if covered_paths is None else covered_paths
        trace = json.loads(
            (self.package / "claim-citation-map.json").read_text(encoding="utf-8")
        )
        receipt = build_review_receipt(
            review_id="review-manuscript-fixture",
            reviewer="independent-reviewer",
            independent=independent,
            review_modes=review_modes or ["record", "source", "method"],
            status="passed",
            covered_artifacts=[
                {"path": path, "sha256": available[path]}
                for path in sorted(selected)
            ],
            covered_claim_ids=[
                claim["claim_id"]
                for claim in trace["claims"]
                if claim.get("material") is True
            ],
            findings=[],
            limitations=["Deterministic test review; not scientific peer review."],
        )
        receipt_path = self.package / "review-receipt.json"
        self.rewrite_json(receipt_path.name, receipt)
        receipt_digest = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
        submission["files"].append(
            {
                "path": receipt_path.name,
                "kind": "review-receipt-v2",
                "sha256": receipt_digest,
            }
        )
        submission["status"] = "submission-ready"
        submission["review"] = {
            "status": "passed",
            "required_modes": ["record", "source", "method"],
            "receipt": {"path": receipt_path.name, "sha256": receipt_digest},
        }
        self.rewrite_json(submission_path.name, submission)

    def test_acceptance_fixture_is_review_ready_and_portable(self) -> None:
        result = validate_manuscript_package(self.package)

        self.assertEqual("passed", result["status"], result["findings"])
        for name in (
            "manuscript-contract.json",
            "manuscript.md",
            "manuscript.tex",
            "references.bib",
            "claim-citation-map.json",
            "reporting-checklist.json",
            "submission-package.json",
        ):
            self.assertTrue((self.package / name).is_file(), name)
        submission = json.loads(
            (self.package / "submission-package.json").read_text(encoding="utf-8")
        )
        self.assertEqual("review-ready", submission["status"])
        self.assertEqual("pending", submission["review"]["status"])
        trace = json.loads(
            (self.package / "claim-citation-map.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            {"1.2", "2.5 response units", "3.8 response units"},
            {item["text"] for item in trace["claims"][0]["reported_values"]},
        )

    def test_supported_material_claim_requires_artifact_or_citation_support(self) -> None:
        path = self.package / "claim-citation-map.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["claims"][0]["evidence_refs"] = []
        payload["claims"][0]["citation_ids"] = []
        self.rewrite_json(path.name, payload)

        self.assertIn("unsupported-material-claim", self.findings())

    def test_citation_must_explicitly_support_the_attributed_claim(self) -> None:
        path = self.package / "claim-citation-map.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["citations"][0]["supports_claim_ids"] = []
        self.rewrite_json(path.name, payload)

        self.assertIn("citation-claim-mismatch", self.findings())

    def test_citation_support_ids_must_be_a_string_list(self) -> None:
        path = self.package / "claim-citation-map.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["citations"][0]["supports_claim_ids"] = "M-003"
        self.rewrite_json(path.name, payload)
        self.refresh_submission_hash(path.name)

        self.assertIn("citation-support-invalid", self.findings())

    def test_claim_citation_must_appear_in_its_manuscript_segment(self) -> None:
        manuscript_path = self.package / "manuscript.md"
        manuscript = manuscript_path.read_text(encoding="utf-8").replace(
            " [@ref-method]",
            "",
        )
        manuscript_path.write_text(manuscript, encoding="utf-8")
        self.refresh_submission_hash(manuscript_path.name)

        trace_path = self.package / "claim-citation-map.json"
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        trace["claims"][2]["text"] = trace["claims"][2]["text"].replace(
            " [@ref-method]",
            "",
        )
        self.rewrite_json(trace_path.name, trace)
        self.refresh_submission_hash(trace_path.name)

        self.assertIn("citation-marker-missing", self.findings())

    def test_verified_citation_requires_a_verification_source(self) -> None:
        path = self.package / "claim-citation-map.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["citations"][0]["verification_source"] = ""
        self.rewrite_json(path.name, payload)

        self.assertIn("citation-verification-source-missing", self.findings())

    def test_unlisted_package_file_is_rejected(self) -> None:
        (self.package / "unlisted.txt").write_text("not declared\n", encoding="utf-8")

        self.assertIn("submission-file-unlisted", self.findings())

    def test_nested_file_named_like_root_manifest_is_not_exempt(self) -> None:
        nested = self.package / "nested" / "submission-package.json"
        nested.parent.mkdir()
        nested.write_text("{}\n", encoding="utf-8")

        self.assertIn("submission-file-unlisted", self.findings())

    def test_reported_value_requires_hashed_evidence_and_manuscript_text(self) -> None:
        path = self.package / "claim-citation-map.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["claims"][0]["reported_values"][0]["artifact_sha256"] = "0" * 64
        self.rewrite_json(path.name, payload)

        self.assertIn("reported-value-evidence-mismatch", self.findings())

        payload["claims"][0]["reported_values"][0]["text"] = "fabricated 99.9%"
        self.rewrite_json(path.name, payload)
        self.assertIn("reported-value-not-in-manuscript", self.findings())

    def test_reported_json_value_must_match_locator_content(self) -> None:
        manuscript_path = self.package / "manuscript.md"
        manuscript = manuscript_path.read_text(encoding="utf-8").replace(
            "2.5 response units",
            "99.9 response units",
        )
        manuscript_path.write_text(manuscript, encoding="utf-8")
        self.refresh_submission_hash(manuscript_path.name)

        trace_path = self.package / "claim-citation-map.json"
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        trace["claims"][0]["text"] = trace["claims"][0]["text"].replace(
            "2.5 response units",
            "99.9 response units",
        )
        trace["claims"][0]["reported_values"][0]["text"] = "99.9 response units"
        self.rewrite_json(trace_path.name, trace)
        self.refresh_submission_hash(trace_path.name)

        self.assertIn("reported-value-content-mismatch", self.findings())

    def test_json_root_pointer_is_allowed_for_a_scalar_artifact(self) -> None:
        scalar_path = self.package / "source" / "root-value.json"
        scalar_path.write_text("2.5\n", encoding="utf-8")
        scalar_digest = hashlib.sha256(scalar_path.read_bytes()).hexdigest()

        trace_path = self.package / "claim-citation-map.json"
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        trace["claims"][0]["reported_values"][0].update(
            {
                "artifact_path": "source/root-value.json",
                "artifact_sha256": scalar_digest,
                "locator": "",
            }
        )
        self.rewrite_json(trace_path.name, trace)
        self.refresh_submission_hash(trace_path.name)

        submission_path = self.package / "submission-package.json"
        submission = json.loads(submission_path.read_text(encoding="utf-8"))
        submission["files"].append(
            {
                "path": "source/root-value.json",
                "kind": "manuscript-package-file",
                "sha256": scalar_digest,
            }
        )
        self.rewrite_json(submission_path.name, submission)

        result = validate_manuscript_package(self.package)
        self.assertEqual("passed", result["status"], result["findings"])

    def test_equivalent_numeric_format_at_sentence_end_is_accepted(self) -> None:
        manuscript_path = self.package / "manuscript.md"
        manuscript = manuscript_path.read_text(encoding="utf-8")
        start = manuscript.index("<!-- claim:M-001 -->")
        end = manuscript.index("## Discussion", start)
        replacement = (
            "<!-- claim:M-001 -->\n"
            "The recorded effect estimate was 2.50. The fixture interval was "
            "1.2 to 3.8 response units.\n\n"
        )
        manuscript_path.write_text(
            manuscript[:start] + replacement + manuscript[end:],
            encoding="utf-8",
        )
        self.refresh_submission_hash(manuscript_path.name)

        trace_path = self.package / "claim-citation-map.json"
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        trace["claims"][0]["text"] = (
            "The recorded effect estimate was 2.50. The fixture interval was "
            "1.2 to 3.8 response units."
        )
        trace["claims"][0]["reported_values"][0]["text"] = "2.50."
        self.rewrite_json(trace_path.name, trace)
        self.refresh_submission_hash(trace_path.name)

        result = validate_manuscript_package(self.package)
        self.assertEqual("passed", result["status"], result["findings"])

    def test_numeric_matching_preserves_sign_and_grouping(self) -> None:
        self.assertFalse(_scalar_appears_in_text(2.5, "−2.5 response units"))
        self.assertTrue(_scalar_appears_in_text(1000, "1,000 observations"))

    def test_claim_text_must_match_its_manuscript_locator(self) -> None:
        path = self.package / "claim-citation-map.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["claims"][0]["text"] = "A materially different claim."
        self.rewrite_json(path.name, payload)
        self.refresh_submission_hash(path.name)

        self.assertIn("claim-text-mismatch", self.findings())

    def test_unresolved_claim_status_cannot_be_review_ready(self) -> None:
        path = self.package / "claim-citation-map.json"
        for status in ("citation-needed", "unresolved"):
            with self.subTest(status=status):
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload["claims"][0]["status"] = status
                payload["claims"][0]["evidence_refs"] = []
                payload["claims"][0]["citation_ids"] = []
                self.rewrite_json(path.name, payload)
                self.refresh_submission_hash(path.name)

                codes = self.findings()
                self.assertIn("unresolved-claim-for-review-ready", codes)
                self.assertNotIn("claim-status-invalid", codes)

    def test_submission_ready_requires_exact_independent_review_coverage(self) -> None:
        self.make_submission_ready()
        self.assertEqual(
            "passed",
            validate_manuscript_package(self.package)["status"],
        )

        manuscript = self.package / "manuscript.md"
        manuscript.write_text(
            manuscript.read_text(encoding="utf-8") + "\nChanged after review.\n",
            encoding="utf-8",
        )
        self.refresh_submission_hash(manuscript.name)
        self.assertIn("stale-review-receipt", self.findings())

    def test_submission_ready_rejects_incomplete_or_nonindependent_review(self) -> None:
        self.make_submission_ready(
            covered_paths={"manuscript.md"},
            independent=False,
            review_modes=["record"],
        )

        codes = self.findings()
        self.assertIn("incomplete-review-artifact-coverage", codes)
        self.assertIn("incomplete-review-mode-coverage", codes)
        self.assertIn("review-not-independent", codes)

    def test_submission_cannot_lower_required_review_modes(self) -> None:
        self.make_submission_ready(review_modes=["record"])
        submission_path = self.package / "submission-package.json"
        submission = json.loads(submission_path.read_text(encoding="utf-8"))
        submission["review"]["required_modes"] = ["record"]
        self.rewrite_json(submission_path.name, submission)

        self.assertIn("incomplete-review-mode-coverage", self.findings())

    def test_submission_review_receipt_requires_a_stated_limitation(self) -> None:
        self.make_submission_ready()
        receipt_path = self.package / "review-receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["limitations"] = []
        receipt.pop("fingerprint")
        receipt["fingerprint"] = canonical_sha256(receipt)
        self.rewrite_json(receipt_path.name, receipt)
        receipt_digest = hashlib.sha256(receipt_path.read_bytes()).hexdigest()

        submission_path = self.package / "submission-package.json"
        submission = json.loads(submission_path.read_text(encoding="utf-8"))
        submission["review"]["receipt"]["sha256"] = receipt_digest
        for item in submission["files"]:
            if item["path"] == receipt_path.name:
                item["sha256"] = receipt_digest
        self.rewrite_json(submission_path.name, submission)

        self.assertIn("review-receipt-limitations-missing", self.findings())

    def test_unresolved_declarations_keep_package_in_draft(self) -> None:
        contract_path = self.package / "manuscript-contract.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["declarations"]["funding"] = {"status": "unknown"}
        self.rewrite_json(contract_path.name, contract)

        self.assertIn("unresolved-declaration-for-review-ready", self.findings())

    def test_reporting_checklist_must_match_the_contract_guideline(self) -> None:
        checklist_path = self.package / "reporting-checklist.json"
        checklist = json.loads(checklist_path.read_text(encoding="utf-8"))
        checklist["guideline"] = "a different reporting guideline"
        self.rewrite_json(checklist_path.name, checklist)
        self.refresh_submission_hash(checklist_path.name)

        self.assertIn("reporting-guideline-mismatch", self.findings())

    def test_review_ready_requires_a_valid_passed_source_bundle(self) -> None:
        manifest_path = self.package / "source" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["review"]["status"] = "pending"
        self.rewrite_json("source/manifest.json", manifest)

        contract_path = self.package / "manuscript-contract.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        manifest_digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        contract["source_manifest"]["sha256"] = manifest_digest
        self.rewrite_json(contract_path.name, contract)

        self.refresh_submission_hash("source/manifest.json")
        self.refresh_submission_hash(contract_path.name)

        self.assertIn("source-review-not-passed", self.findings())

    def test_source_manifest_semantics_are_bound_to_the_review_packet(self) -> None:
        manifest_path = self.package / "source" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["claims"][0]["text"] = "A different claim with the same identifier."
        self.rewrite_json("source/manifest.json", manifest)

        contract_path = self.package / "manuscript-contract.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["source_manifest"]["sha256"] = hashlib.sha256(
            manifest_path.read_bytes()
        ).hexdigest()
        self.rewrite_json(contract_path.name, contract)
        self.refresh_submission_hash("source/manifest.json")
        self.refresh_submission_hash(contract_path.name)

        self.assertIn("source-review-packet-stale", self.findings())

    def test_failed_source_execution_blocks_review_ready(self) -> None:
        manifest_path = self.package / "source" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["executions"] = [{"command": "fixture-check", "exit_code": 1}]
        self.rewrite_json("source/manifest.json", manifest)

        contract_path = self.package / "manuscript-contract.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["source_manifest"]["sha256"] = hashlib.sha256(
            manifest_path.read_bytes()
        ).hexdigest()
        self.rewrite_json(contract_path.name, contract)
        self.refresh_submission_hash("source/manifest.json")
        self.refresh_submission_hash(contract_path.name)

        self.assertIn("source-failed-execution", self.findings())

    def test_source_review_requires_record_source_and_method_modes(self) -> None:
        receipt_path = self.package / "source" / "review-receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["review_modes"] = ["record"]
        receipt.pop("fingerprint")
        receipt["fingerprint"] = canonical_sha256(receipt)
        self.rewrite_json("source/review-receipt.json", receipt)

        manifest_path = self.package / "source" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        receipt_digest = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
        for artifact in manifest["artifacts"]:
            if artifact["path"] == "review-receipt.json":
                artifact["sha256"] = receipt_digest
        self.rewrite_json("source/manifest.json", manifest)

        contract_path = self.package / "manuscript-contract.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["source_manifest"]["sha256"] = hashlib.sha256(
            manifest_path.read_bytes()
        ).hexdigest()
        self.rewrite_json(contract_path.name, contract)
        self.refresh_submission_hash("source/review-receipt.json")
        self.refresh_submission_hash("source/manifest.json")
        self.refresh_submission_hash(contract_path.name)

        self.assertIn("source-incomplete-review-mode-coverage", self.findings())

    def test_source_review_receipt_requires_a_stated_limitation(self) -> None:
        receipt_path = self.package / "source" / "review-receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["limitations"] = []
        receipt.pop("fingerprint")
        receipt["fingerprint"] = canonical_sha256(receipt)
        self.rewrite_json("source/review-receipt.json", receipt)

        manifest_path = self.package / "source" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        receipt_digest = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
        for artifact in manifest["artifacts"]:
            if artifact["path"] == "review-receipt.json":
                artifact["sha256"] = receipt_digest
        self.rewrite_json("source/manifest.json", manifest)

        contract_path = self.package / "manuscript-contract.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["source_manifest"]["sha256"] = hashlib.sha256(
            manifest_path.read_bytes()
        ).hexdigest()
        self.rewrite_json(contract_path.name, contract)
        self.refresh_submission_hash("source/review-receipt.json")
        self.refresh_submission_hash("source/manifest.json")
        self.refresh_submission_hash(contract_path.name)

        self.assertIn("source-review-receipt-limitations-missing", self.findings())

    def test_source_review_receipt_finding_shape_matches_the_runtime(self) -> None:
        receipt_path = self.package / "source" / "review-receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["findings"] = [{}]
        receipt.pop("fingerprint")
        receipt["fingerprint"] = canonical_sha256(receipt)
        self.rewrite_json("source/review-receipt.json", receipt)

        manifest_path = self.package / "source" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        receipt_digest = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
        for artifact in manifest["artifacts"]:
            if artifact["path"] == "review-receipt.json":
                artifact["sha256"] = receipt_digest
        self.rewrite_json("source/manifest.json", manifest)

        contract_path = self.package / "manuscript-contract.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["source_manifest"]["sha256"] = hashlib.sha256(
            manifest_path.read_bytes()
        ).hexdigest()
        self.rewrite_json(contract_path.name, contract)
        self.refresh_submission_hash("source/review-receipt.json")
        self.refresh_submission_hash("source/manifest.json")
        self.refresh_submission_hash(contract_path.name)

        self.assertIn("source-review-receipt-finding-invalid", self.findings())

    def test_source_review_cannot_pass_with_an_open_blocking_finding(self) -> None:
        manifest_path = self.package / "source" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["review"]["findings"] = [
            {
                "code": "known-critical-gap",
                "severity": "critical",
                "message": "The source review still has an open critical finding.",
                "resolution_status": "open",
            }
        ]
        self.rewrite_json("source/manifest.json", manifest)

        contract_path = self.package / "manuscript-contract.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["source_manifest"]["sha256"] = hashlib.sha256(
            manifest_path.read_bytes()
        ).hexdigest()
        self.rewrite_json(contract_path.name, contract)
        self.refresh_submission_hash("source/manifest.json")
        self.refresh_submission_hash(contract_path.name)

        self.assertIn("source-unsafe-review-pass", self.findings())

    def test_source_manifest_review_findings_must_be_objects(self) -> None:
        manifest_path = self.package / "source" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["review"]["findings"] = ["not-an-object"]
        self.rewrite_json("source/manifest.json", manifest)

        contract_path = self.package / "manuscript-contract.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["source_manifest"]["sha256"] = hashlib.sha256(
            manifest_path.read_bytes()
        ).hexdigest()
        self.rewrite_json(contract_path.name, contract)
        self.refresh_submission_hash("source/manifest.json")
        self.refresh_submission_hash(contract_path.name)

        self.assertIn("source-review-findings-invalid", self.findings())

    def test_source_receipt_modes_must_be_within_the_linked_packet(self) -> None:
        packet_path = self.package / "source" / "review-packet.json"
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        packet["review_modes"] = ["record"]
        packet.pop("review_task_id")
        packet.pop("fingerprint")
        packet_fingerprint = canonical_sha256(packet)
        packet["review_task_id"] = f"review-task-{packet_fingerprint[:20]}"
        packet["fingerprint"] = packet_fingerprint
        self.rewrite_json("source/review-packet.json", packet)

        receipt_path = self.package / "source" / "review-receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["review_task_id"] = packet["review_task_id"]
        receipt["packet_fingerprint"] = packet_fingerprint
        receipt.pop("fingerprint")
        receipt["fingerprint"] = canonical_sha256(receipt)
        self.rewrite_json("source/review-receipt.json", receipt)

        manifest_path = self.package / "source" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        updated_hashes = {
            "review-packet.json": hashlib.sha256(packet_path.read_bytes()).hexdigest(),
            "review-receipt.json": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
        }
        for artifact in manifest["artifacts"]:
            if artifact["path"] in updated_hashes:
                artifact["sha256"] = updated_hashes[artifact["path"]]
        self.rewrite_json("source/manifest.json", manifest)

        contract_path = self.package / "manuscript-contract.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["source_manifest"]["sha256"] = hashlib.sha256(
            manifest_path.read_bytes()
        ).hexdigest()
        self.rewrite_json(contract_path.name, contract)
        self.refresh_submission_hash("source/review-packet.json")
        self.refresh_submission_hash("source/review-receipt.json")
        self.refresh_submission_hash("source/manifest.json")
        self.refresh_submission_hash(contract_path.name)

        self.assertIn("source-review-packet-mode-mismatch", self.findings())

    def test_superseded_source_receipt_does_not_invalidate_current_review(self) -> None:
        current_receipt_path = self.package / "source" / "review-receipt.json"
        old_receipt = json.loads(current_receipt_path.read_text(encoding="utf-8"))
        old_receipt["review_id"] = "superseded-source-review"
        old_receipt["status"] = "superseded"
        old_receipt["covered_artifacts"][0]["sha256"] = "0" * 64
        old_receipt.pop("fingerprint")
        old_receipt["fingerprint"] = canonical_sha256(old_receipt)
        old_path = self.package / "source" / "old-review-receipt.json"
        self.rewrite_json("source/old-review-receipt.json", old_receipt)
        old_digest = hashlib.sha256(old_path.read_bytes()).hexdigest()

        manifest_path = self.package / "source" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["artifacts"].append(
            {
                "path": "old-review-receipt.json",
                "kind": "review-receipt-v2",
                "sha256": old_digest,
            }
        )
        self.rewrite_json("source/manifest.json", manifest)

        contract_path = self.package / "manuscript-contract.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["source_manifest"]["sha256"] = hashlib.sha256(
            manifest_path.read_bytes()
        ).hexdigest()
        self.rewrite_json(contract_path.name, contract)
        self.refresh_submission_hash("source/manifest.json")
        self.refresh_submission_hash(contract_path.name)

        submission_path = self.package / "submission-package.json"
        submission = json.loads(submission_path.read_text(encoding="utf-8"))
        submission["files"].append(
            {
                "path": "source/old-review-receipt.json",
                "kind": "manuscript-package-file",
                "sha256": old_digest,
            }
        )
        self.rewrite_json(submission_path.name, submission)

        result = validate_manuscript_package(self.package)
        self.assertEqual("passed", result["status"], result["findings"])

    def test_material_claim_must_reference_a_source_manifest_claim(self) -> None:
        path = self.package / "claim-citation-map.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["claims"][0]["source_claim_id"] = "missing-source-claim"
        self.rewrite_json(path.name, payload)
        self.refresh_submission_hash(path.name)

        self.assertIn("source-claim-missing", self.findings())

    def test_rebuttal_requires_exact_prior_manuscript_comments_and_response(self) -> None:
        contract_path = self.package / "manuscript-contract.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["mode"] = "rebuttal"
        contract.pop("prior_manuscript", None)
        contract.pop("reviewer_comments", None)
        self.rewrite_json(contract_path.name, contract)

        codes = self.findings()
        self.assertIn("rebuttal-prior-manuscript-required", codes)
        self.assertIn("rebuttal-comments-required", codes)
        self.assertIn("rebuttal-response-required", codes)

    def test_cli_rejects_seeded_unsupported_claim(self) -> None:
        path = self.package / "claim-citation-map.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["claims"][0]["evidence_refs"] = []
        payload["claims"][0]["citation_ids"] = []
        self.rewrite_json(path.name, payload)

        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "validate_manuscript_package.py"),
                str(self.package),
                "--require-clean",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("unsupported-material-claim", result.stdout)


if __name__ == "__main__":
    unittest.main()
