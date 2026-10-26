import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CLI = Path(__file__).resolve().parents[1] / "scripts" / "search_skills.py"


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(CLI), *args], capture_output=True, text=True, cwd=tempfile.gettempdir(), check=False)


class SearchSkillsCliTests(unittest.TestCase):
    def test_unquoted_words_match_single_quoted_query(self) -> None:
        multi = run("literature", "review")
        self.assertEqual(0, multi.returncode, multi.stderr)
        single = run("literature review")
        self.assertEqual(json.loads(single.stdout), json.loads(multi.stdout))
        self.assertIsInstance(json.loads(multi.stdout), list)

    def test_query_option(self) -> None:
        result = run("--query", "literature review")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(json.loads(run("literature", "review").stdout), json.loads(result.stdout))

    def test_missing_query_fails(self) -> None:
        self.assertEqual(2, run().returncode)

    def test_name_prints_record_and_source(self) -> None:
        result = run("--name", "cx-alphafold-structure-analysis")
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("cx-alphafold-structure-analysis", payload["record"]["name"])
        self.assertEqual(payload["record"]["source"], payload["source"]["key"])
        self.assertEqual("", payload["source"]["commit"])

    def test_name_missing_fails_naming_skill(self) -> None:
        result = run("--name", "no-such-skill")
        self.assertEqual(1, result.returncode)
        self.assertIn("no-such-skill", result.stderr)
        self.assertEqual("", result.stdout)

    def test_name_with_query_is_usage_error(self) -> None:
        self.assertEqual(2, run("--name", "x", "literature").returncode)
        self.assertEqual(2, run("--name", "x", "--query", "literature").returncode)

    def test_name_honours_inventory(self) -> None:
        inventory = {
            "schema_version": 2,
            "skills": [{"name": "demo", "source": "s1", "status": "active", "reasons": []}],
            "sources": [{"key": "s1", "commit": "abc123"}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "inv.json"
            path.write_text(json.dumps(inventory), encoding="utf-8")
            found = run("--name", "demo", "--inventory", str(path))
            self.assertEqual(0, found.returncode, found.stderr)
            self.assertEqual("abc123", json.loads(found.stdout)["source"]["commit"])
            self.assertEqual(1, run("--name", "cx-alphafold-structure-analysis", "--inventory", str(path)).returncode)

    def test_help_documents_every_option(self) -> None:
        result = run("--help")
        self.assertEqual(0, result.returncode, result.stderr)
        for text in ("joined with single spaces", "--query TEXT", "catalog/inventory.json", "maximum number of results", "inactive", "--name NAME"):
            self.assertIn(text, result.stdout)


if __name__ == "__main__":
    unittest.main()
