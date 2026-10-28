"""Exercise the checked-in provenance bundle through the completion CLI gate."""

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codex_science.artifacts import validate_bundle


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "science-provenance"
QUALITY = ROOT / "runtime-skills" / "science-provenance" / "quality.json"
SEEDED_FAILURE_TESTS = {
    "artifact-digest-mismatch": "test_artifact_digest_mismatch",
    "missing-artifact": "test_missing_artifact",
    "escaping-artifact-path": "test_escaping_artifact_path",
    "unregistered-claim-evidence": "test_unregistered_claim_evidence",
    "unknown-evidence-endpoint": "test_unknown_evidence_endpoint",
    "invalid-reference-digest": "test_invalid_reference_digest",
}


class ScienceProvenanceAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.run_dir = Path(temporary.name) / "run"
        shutil.copytree(FIXTURE, self.run_dir)
        self.manifest_path = self.run_dir / "input.json"
        self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        self.review_path = Path(temporary.name) / "review.json"

    def _write_manifest(self) -> None:
        self.manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")

    def _validate(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable, "-I", "-S", str(ROOT / "scripts" / "validate_artifact.py"),
                str(self.manifest_path), "--review-output", str(self.review_path),
                "--require-passed-review",
            ],
            cwd=self.run_dir,
            capture_output=True,
            text=True,
            check=False,
        )

    def _rewrite_sidecar(self, name: str, payload: dict) -> None:
        path = self.run_dir / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        record = next(item for item in self.manifest["artifacts"] if item["path"] == name)
        record["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        self._write_manifest()

    def _assert_refused(self, fragment: str) -> None:
        result = self._validate()
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn(fragment, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(self.review_path.exists())

    def test_acceptance_fixture_is_valid_and_reviewed(self) -> None:
        original = self.manifest_path.read_bytes()
        result = self._validate()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("artifact bundle: valid\nartifact review: passed\n", result.stdout)
        self.assertEqual("", result.stderr)
        self.assertEqual(
            {"status": "passed", "findings": []},
            json.loads(self.review_path.read_text(encoding="utf-8")),
        )
        self.assertEqual(original, self.manifest_path.read_bytes())
        sidecars = validate_bundle(self.manifest, self.run_dir)
        self.assertEqual({"claim-fixture-values"}, set(sidecars["claim_by_id"]))
        self.assertEqual({"claim-fixture-values", "dataset-fixture"}, set(sidecars["node_by_id"]))
        self.assertEqual(1, len(sidecars["edges"]))
        self.assertEqual(1, len(sidecars["reference_use_ledgers"]))
        self.assertEqual([], sidecars["advanced_findings"])

    def test_artifact_digest_mismatch(self) -> None:
        (self.run_dir / "observations.csv").write_text(
            "sample,value\nfixture-a,999\nfixture-b,2\n", encoding="utf-8",
        )
        self._assert_refused("Artifact digest mismatch: observations.csv")

    def test_missing_artifact(self) -> None:
        (self.run_dir / "observations.csv").unlink()
        self._assert_refused("Artifact file is missing: observations.csv")

    def test_escaping_artifact_path(self) -> None:
        self.manifest["artifacts"][0]["path"] = "../observations.csv"
        self._write_manifest()
        self._assert_refused("Artifact path must stay inside the run bundle: ../observations.csv")

    def test_unregistered_claim_evidence(self) -> None:
        self.manifest["claims"][0]["evidence"] = ["unregistered-observations.csv"]
        self._write_manifest()
        result = self._validate()
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertEqual("artifact bundle: valid\nartifact review: findings\n", result.stdout)
        self.assertIn("artifact review has unresolved findings", result.stderr)
        review = json.loads(self.review_path.read_text(encoding="utf-8"))
        self.assertEqual("findings", review["status"])
        self.assertEqual(["missing-evidence"], [finding["code"] for finding in review["findings"]])
        self.assertIn(
            "Claim evidence is not a saved artifact: unregistered-observations.csv",
            review["findings"][0]["message"],
        )

    def test_unknown_evidence_endpoint(self) -> None:
        graph = json.loads((self.run_dir / "evidence_graph.json").read_text(encoding="utf-8"))
        graph["edges"][0]["source"] = "dataset-not-recorded"
        self._rewrite_sidecar("evidence_graph.json", graph)
        self._assert_refused("Evidence edge endpoint is missing: dataset-not-recorded -> claim-fixture-values")

    def test_invalid_reference_digest(self) -> None:
        ledger = json.loads((self.run_dir / "reference-use-ledger.json").read_text(encoding="utf-8"))
        ledger["uses"][0]["sha256"] = "not-a-sha256"
        self._rewrite_sidecar("reference-use-ledger.json", ledger)
        self._assert_refused("reference use receipt sha256 is invalid")

    def test_quality_names_executable_seeded_failures(self) -> None:
        quality = json.loads(QUALITY.read_text(encoding="utf-8"))
        self.assertEqual("L4", quality["declared_maturity"])
        self.assertEqual(["examples/science-provenance/input.json"], quality["acceptance_fixtures"])
        self.assertCountEqual(SEEDED_FAILURE_TESTS, quality["seeded_failures"])
        self.assertIn("tests/test_science_provenance_acceptance.py", quality["test_files"])
        discovered = unittest.defaultTestLoader.getTestCaseNames(type(self))
        for name in quality["seeded_failures"]:
            with self.subTest(seeded_failure=name):
                method = SEEDED_FAILURE_TESTS[name]
                self.assertIn(method, discovered)
                self.assertTrue(callable(getattr(self, method)))


if __name__ == "__main__":
    unittest.main()
