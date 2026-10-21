from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = (
    "classify_rigor",
    "report_completion",
    "run_literature_evaluation",
    "report_literature_evaluation",
    "estimate_saturation",
    "trace_citations",
    "drive_codex_run",
    "grade_rubric",
    "rank_trajectories",
    "check_claim_sufficiency",
    "resolve_citations",
)


class Stage7EntrypointTests(unittest.TestCase):
    def test_scripts_are_executable_and_documented(self) -> None:
        doc = (ROOT / "docs/EVALUATION.md").read_text(encoding="utf-8")
        for name in SCRIPTS:
            with self.subTest(script=name):
                result = subprocess.run(
                    ["bash", "scripts/python_runtime.sh", f"scripts/{name}.py", "--help"],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn(f"scripts/{name}.py", doc)


if __name__ == "__main__":
    unittest.main()
