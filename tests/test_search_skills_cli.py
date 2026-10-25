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

    def test_help_documents_every_option(self) -> None:
        result = run("--help")
        self.assertEqual(0, result.returncode, result.stderr)
        for text in ("joined with single spaces", "--query TEXT", "catalog/inventory.json", "maximum number of results", "inactive"):
            self.assertIn(text, result.stdout)


if __name__ == "__main__":
    unittest.main()
