import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.catalog import load_inventory, search_inventory  # noqa: E402
from codex_science.mcp_server import TOOL_NAMES  # noqa: E402
from codex_science.life_science import plan_life_science_research  # noqa: E402

SCRIPT = ROOT / "scripts" / "science_tool.py"


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-I", "-S", str(SCRIPT), *args],
        cwd=tempfile.gettempdir(), capture_output=True, text=True, check=False,
    )


class ScienceToolCliTest(unittest.TestCase):
    def test_list_names_match_server_tools(self) -> None:
        result = run("--list")
        self.assertEqual(0, result.returncode, result.stderr)
        names = {line.split("\t")[0] for line in result.stdout.splitlines()}
        self.assertEqual(set(TOOL_NAMES), names)

    def test_search_skills_matches_catalog_for_query_and_json(self) -> None:
        expected = search_inventory(load_inventory(ROOT / "catalog" / "inventory.json"), "sympy", limit=3)
        for args in (
            ("science_search_skills", "--query", "sympy", "--limit", "3"),
            ("science_search_skills", "--json", json.dumps({"query": "sympy", "limit": 3})),
        ):
            with self.subTest(args=args):
                result = run(*args)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual(expected, json.loads(result.stdout))

    def test_plan_matches_library(self) -> None:
        question = "BRCA1 variant"
        result = run("science_plan_life_science_research", "--query", question)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(plan_life_science_research(question), json.loads(result.stdout))

    def test_user_errors_exit_2_without_traceback(self) -> None:
        cases = (
            ("no_such_tool", "--json", "{}"),
            ("science_search_skills", "--query", "x" * 501),
            ("science_search_skills", "--json", "[1]"),
            ("science_search_skills", "--json", "{bad"),
            ("science_search_skills", "--json", '{"query":"sympy","limit":' + "9" * 5000 + "}"),
            ("science_search_skills", "--json", "{}", "--query", "sympy"),
            ("science_search_skills", "--json", '{"query":' + "[" * 10000 + "0" + "]" * 10000 + "}"),
        )
        for args in cases:
            with self.subTest(args=[a[:20] for a in args]):
                result = run(*args)
                self.assertEqual(2, result.returncode, result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual("", result.stdout)

    def test_lone_surrogate_output_is_valid_utf8_json(self) -> None:
        for escape in ("\\ud800", "\\udc80"):
            with self.subTest(escape=escape):
                result = subprocess.run(
                    [sys.executable, "-I", "-S", str(SCRIPT), "science_plan_life_science_research",
                     "--json", '{"query":"' + escape + '"}'],
                    cwd=tempfile.gettempdir(), capture_output=True, check=False,
                )
                self.assertEqual(0, result.returncode, result.stderr)
                value = json.loads(result.stdout.decode("utf-8"))
                self.assertEqual(plan_life_science_research(json.loads('"' + escape + '"')), value)

    def test_closed_pipe_has_no_traceback(self) -> None:
        for args in (("--list",), ("--help",)):
            with self.subTest(args=args):
                read_end, write_end = os.pipe()
                os.close(read_end)
                try:
                    result = subprocess.run(
                        [sys.executable, "-I", "-S", str(SCRIPT), *args],
                        cwd=tempfile.gettempdir(), stdout=write_end, stderr=subprocess.PIPE, check=False,
                    )
                finally:
                    os.close(write_end)
                self.assertEqual(1, result.returncode, result.stderr)
                self.assertNotIn(b"Traceback", result.stderr)
                self.assertNotIn(b"Exception ignored", result.stderr)


if __name__ == "__main__":
    unittest.main()
