from contextlib import redirect_stdout
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

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
        self.assertIn("--allow-unavailable all", workflow)
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
        with self.assertRaisesRegex(SystemExit, "reactome: HTTP 500"):
            run_checks((("reactome", Connector(500), "x"),), {"reactome"})
        with self.assertRaisesRegex(SystemExit, "other: HTTP 403"):
            run_checks((("other", Connector(403), "x"),), {"reactome"})

    def test_public_smoke_retries_one_transient_timeout(self) -> None:
        class Connector:
            calls = 0

            def search(self, _query: str, *, limit: int) -> list[dict[str, str]]:
                self.calls += 1
                if self.calls == 1:
                    raise TimeoutError("temporary timeout")
                return [{"id": "ok"}]

        connector = Connector()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(1, run_checks((("example", connector, "x"),)))
        self.assertEqual(2, connector.calls)

    def test_public_smoke_collects_failures_and_continues(self) -> None:
        class TimeoutConnector:
            calls = 0

            def search(self, _query: str, *, limit: int) -> list[dict[str, str]]:
                self.calls += 1
                raise TimeoutError("temporary timeout")

        class SuccessConnector:
            def search(self, _query: str, *, limit: int) -> list[dict[str, str]]:
                return [{"id": "ok"}]

        timeout = TimeoutConnector()
        stdout = io.StringIO()
        with redirect_stdout(stdout), self.assertRaisesRegex(
            SystemExit, "first: timeout after 2 attempts"
        ):
            run_checks((("first", timeout, "x"), ("second", SuccessConnector(), "x")))

        self.assertEqual(2, timeout.calls)
        self.assertIn("second: ok (ok)", stdout.getvalue())

    def test_public_smoke_allows_only_named_unavailable_sources(self) -> None:
        class Connector:
            def search(self, _query: str, *, limit: int) -> list[dict[str, str]]:
                raise TimeoutError("temporary timeout")

        stdout = io.StringIO()
        with patch.dict("os.environ", {"GITHUB_ACTIONS": "true"}), redirect_stdout(stdout):
            self.assertEqual(
                1,
                run_checks(
                    (("ensembl", Connector(), "x"),),
                    allowed_unavailable={"ensembl"},
                ),
            )
        self.assertIn("::warning title=Public API unavailable::ensembl", stdout.getvalue())

    def test_public_smoke_can_soft_fail_all_unavailable_sources(self) -> None:
        class Connector:
            def __init__(self, failure: Exception) -> None:
                self.failure = failure

            def search(self, _query: str, *, limit: int) -> list[dict[str, str]]:
                raise self.failure

        with redirect_stdout(io.StringIO()):
            processed = run_checks(
                (
                    ("ensembl", Connector(TimeoutError("temporary timeout")), "x"),
                    (
                        "chembl",
                        Connector(
                            urllib.error.HTTPError(
                                "https://example.test", 500, "upstream error", {}, None
                            )
                        ),
                        "x",
                    ),
                ),
                allowed_unavailable={"all"},
            )
        self.assertEqual(2, processed)

    def test_github_automation_is_pinned_and_minimally_privileged(self) -> None:
        ci = (self.root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        public = (self.root / ".github" / "workflows" / "public-smoke.yml").read_text(
            encoding="utf-8"
        )
        codeql = (self.root / ".github" / "workflows" / "codeql.yml").read_text(
            encoding="utf-8"
        )
        codeql_config = (
            self.root / ".github" / "codeql" / "codeql-config.yml"
        ).read_text(encoding="utf-8")
        dependabot = (self.root / ".github" / "dependabot.yml").read_text(encoding="utf-8")

        for workflow in (ci, public, codeql):
            self.assertRegex(workflow, r"actions/checkout@[0-9a-f]{40}")
            self.assertIn("contents: read", workflow)
        for workflow in (ci, public):
            self.assertRegex(workflow, r"astral-sh/setup-uv@[0-9a-f]{40}")
        self.assertRegex(codeql, r"github/codeql-action/init@[0-9a-f]{40}")
        self.assertRegex(codeql, r"github/codeql-action/analyze@[0-9a-f]{40}")
        self.assertIn("security-events: write", codeql)
        self.assertIn('language: "python"', codeql)
        self.assertIn("config-file: ./.github/codeql/codeql-config.yml", codeql)
        self.assertIn("- src/", codeql_config)
        self.assertIn("- scripts/", codeql_config)
        self.assertIn("- examples/", codeql_config)
        self.assertNotIn("vendor/", codeql_config)
        self.assertIn('package-ecosystem: "github-actions"', dependabot)
        self.assertIn('package-ecosystem: "uv"', dependabot)

    def test_uv_build_constraint_accepts_ci_uv_minor(self) -> None:
        pyproject = tomllib.loads((self.root / "pyproject.toml").read_text(encoding="utf-8"))
        uv_build = next(
            requirement
            for requirement in pyproject["build-system"]["requires"]
            if requirement.startswith("uv_build")
        )

        self.assertIn("<0.12.0", uv_build)
        self.assertNotIn("<0.11.0", uv_build)

    def test_local_omc_state_is_ignored(self) -> None:
        ignored = (self.root / ".gitignore").read_text(encoding="utf-8").splitlines()

        self.assertIn(".omc/", ignored)


if __name__ == "__main__":
    unittest.main()
