import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.manuscript import (  # noqa: E402
    build_acceptance_package,
    validate_manuscript_package,
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

    def test_verified_citation_requires_a_verification_source(self) -> None:
        path = self.package / "claim-citation-map.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["citations"][0]["verification_source"] = ""
        self.rewrite_json(path.name, payload)

        self.assertIn("citation-verification-source-missing", self.findings())

    def test_unlisted_package_file_is_rejected(self) -> None:
        (self.package / "unlisted.txt").write_text("not declared\n", encoding="utf-8")

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

    def test_unresolved_declarations_keep_package_in_draft(self) -> None:
        contract_path = self.package / "manuscript-contract.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["declarations"]["funding"] = {"status": "unknown"}
        self.rewrite_json(contract_path.name, contract)

        self.assertIn("unresolved-declaration-for-review-ready", self.findings())

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
