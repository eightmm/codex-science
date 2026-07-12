from contextlib import redirect_stdout
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

from codex_science.artifacts import validate_manifest
from codex_science.review import review_manifest
from scripts.public_smoke import run_checks


class LifeScienceAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]
        self.example = self.root / "examples" / "life-science-reviewed-run"

    def test_checked_in_life_science_run_is_hash_complete_and_reviewed(self) -> None:
        manifest = json.loads((self.example / "manifest.json").read_text(encoding="utf-8"))

        validate_manifest(manifest)
        self.assertEqual("passed", review_manifest(manifest)["status"])
        self.assertEqual("passed", manifest["review"]["status"])
        for item in manifest["code"] + manifest["artifacts"]:
            payload = (self.example / item["path"]).read_bytes()
            self.assertEqual(item["sha256"], hashlib.sha256(payload).hexdigest())
        index = (self.example / "index.md").read_text(encoding="utf-8")
        self.assertIn("[evidence.json](evidence.json)", index)
        self.assertIn("[review.json](review.json)", index)

    def test_acceptance_conclusion_preserves_missing_and_incomparable_evidence(self) -> None:
        evidence = json.loads((self.example / "evidence.json").read_text(encoding="utf-8"))
        result = json.loads((self.example / "result.json").read_text(encoding="utf-8"))

        self.assertEqual(
            {"FinnGen", "BioBank Japan", "UKB/TOPMed"},
            {source["source"] for source in evidence["sources"]},
        )
        self.assertEqual(["FinnGen"], result["comparable_significant_sources"])
        self.assertFalse(result["hypothesis_supported"])
        self.assertIn("not established", result["conclusion"])
        self.assertIn("missing evidence is not negative evidence", result["limitations"])

    def test_snapshot_analysis_is_deterministic(self) -> None:
        expected = (self.example / "result.json").read_bytes()
        with tempfile.TemporaryDirectory() as tempdir:
            copied = Path(tempdir) / "run"
            shutil.copytree(self.example, copied)
            completed = subprocess.run(
                [sys.executable, str(copied / "analysis.py")],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertEqual(expected, (copied / "result.json").read_bytes())


class PublicSmokeWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]

    def test_public_smoke_is_scheduled_manual_and_isolated_from_pr_ci(self) -> None:
        workflow = (
            self.root / ".github" / "workflows" / "public-smoke.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("schedule:", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("--allow-http-403 reactome", workflow)
        self.assertIn("timeout-minutes:", workflow)
        self.assertIn("contents: read", workflow)
        self.assertNotIn("pull_request:", workflow)
        self.assertNotIn("push:", workflow)

    def test_environment_block_allowlist_is_source_and_status_specific(self) -> None:
        class Connector:
            def __init__(self, status: int) -> None:
                self.status = status

            def search(self, _query: str, *, limit: int) -> list[dict[str, str]]:
                raise urllib.error.HTTPError("https://example.test", self.status, "blocked", {}, None)

        with redirect_stdout(io.StringIO()):
            self.assertEqual(1, run_checks((("reactome", Connector(403), "x"),), {"reactome"}))
        with self.assertRaises(urllib.error.HTTPError):
            run_checks((("reactome", Connector(500), "x"),), {"reactome"})
        with self.assertRaises(urllib.error.HTTPError):
            run_checks((("other", Connector(403), "x"),), {"reactome"})

    def test_local_omc_state_is_ignored(self) -> None:
        ignored = (self.root / ".gitignore").read_text(encoding="utf-8").splitlines()

        self.assertIn(".omc/", ignored)


if __name__ == "__main__":
    unittest.main()
