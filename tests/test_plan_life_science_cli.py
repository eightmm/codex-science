import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "plan_life_science_research.py"
sys.path.insert(0, str(ROOT / "src"))

from codex_science.life_science import plan_life_science_research  # noqa: E402

QUESTION = "Is the BRCA1 c.5266dupC variant pathogenic in breast cancer"


def run(*args: str, isolated: bool = False) -> subprocess.CompletedProcess:
    interpreter = [sys.executable, "-I", "-S"] if isolated else [sys.executable]
    return subprocess.run([*interpreter, str(CLI), *args], capture_output=True, text=True, cwd=tempfile.gettempdir(), check=False)


class PlanLifeScienceCliTests(unittest.TestCase):
    def test_output_equals_planner(self) -> None:
        result = run(QUESTION, isolated=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(plan_life_science_research(QUESTION), json.loads(result.stdout))

    def test_words_and_option_join_like_single_question(self) -> None:
        expected = json.loads(run(QUESTION).stdout)
        self.assertEqual(expected, json.loads(run(*QUESTION.split()).stdout))
        self.assertEqual(expected, json.loads(run("--question", QUESTION).stdout))

    def test_internal_whitespace_matches_planner(self) -> None:
        question = "BRCA1 across  ancestries"
        result = run(question)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(plan_life_science_research(question), json.loads(result.stdout))

    def test_empty_question_exits_2_without_traceback(self) -> None:
        for args in ((), ("  ",)):
            result = run(*args)
            self.assertEqual(2, result.returncode)
            self.assertNotIn("Traceback", result.stderr)

    def test_overlong_question_exits_2_without_traceback(self) -> None:
        for question in ("x" * 501, "BRCA1  " * 80, " " * 496 + "BRCA1", "BRCA1" + " " * 496):
            result = run(question)
            self.assertEqual(2, result.returncode)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn("1 to 500", result.stderr)


if __name__ == "__main__":
    unittest.main()
