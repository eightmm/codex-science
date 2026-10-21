import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LiteratureReviewGuidanceTests(unittest.TestCase):
    def test_citation_trace_and_claim_evidence_guidance(self):
        text = (ROOT / "authored-skills/literature-review/SKILL.md").read_text(encoding="utf-8")
        self.assertIn('"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/trace_citations.py"', text)
        self.assertIn("--require-traced", text)
        self.assertIn("support_excerpts", text)
        self.assertIn("`kind`", text)


if __name__ == "__main__":
    unittest.main()
