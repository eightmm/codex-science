import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.method_landscape import allocate_methods


def topic(identifier, covered=False):
    return {"id": identifier, "name": identifier, "description": "A test topic", "covered_by_baseline": covered}


def paper(identifier, topics):
    return {"paper_id": identifier, "title": identifier, "topics": topics,
            "excerpt": "This is a sufficiently descriptive excerpt for validation."}


def payload(budget=10, topics=None, papers=None):
    return {"schema": "method-landscape-v1", "budget": budget,
            "topics": topics if topics is not None else [topic("a"), topic("b")],
            "papers": papers if papers is not None else [paper("a1", ["a"]), paper("a2", ["a"]), paper("b1", ["b"])]}


class MethodLandscapeTests(unittest.TestCase):
    def test_size_ordered_round_robin_and_tie_order(self):
        result = allocate_methods(payload(5, [topic("a"), topic("b"), topic("c")],
            [paper("a1", ["a"]), paper("b1", ["b"]), paper("a2", ["a"]), paper("b2", ["b"]), paper("c1", ["c"]) ]))
        self.assertEqual([("a1", 1), ("b1", 2), ("c1", 3), ("a2", 4), ("b2", 5)],
                         [(x["paper_id"], x["order"]) for x in result["selected"]])
        self.assertEqual(["a", "b", "c"], [x["topic_id"] for x in result["clusters"]])

    def test_empty_all_covered_and_budget_beyond_clusters(self):
        empty = allocate_methods(payload(papers=[]))
        self.assertEqual([], empty["clusters"])
        covered = allocate_methods(payload(topics=[topic("a", True)], papers=[paper("x", ["a"])]))
        self.assertEqual("all-topics-covered-by-baseline", covered["screened_out"][0]["reason"])
        self.assertEqual(3, len(allocate_methods(payload())["selected"]))

    def test_covered_first_topic_falls_through(self):
        result = allocate_methods(payload(topics=[topic("a", True), topic("b")], papers=[paper("x", ["a", "b"])]))
        self.assertEqual("b", result["selected"][0]["topic_id"])

    def test_rejects_duplicate_ids_unknown_topics_and_invalid_excerpt(self):
        for value in (payload(papers=[paper("x", ["a"]), paper("x", ["b"])]),
                      payload(papers=[paper("x", ["missing"])]),
                      payload(papers=[{**paper("x", ["a"]), "excerpt": "short"}])):
            with self.assertRaises(ValueError):
                allocate_methods(value)

    def test_selected_entries_carry_excerpt_provenance(self):
        digest = "ab" * 32
        result = allocate_methods(payload(papers=[{**paper("a1", ["a"]), "source_sha256": digest}, paper("b1", ["b"])]))
        by_id = {item["paper_id"]: item for item in result["selected"]}
        self.assertEqual(paper("a1", ["a"])["excerpt"], by_id["a1"]["excerpt"])
        self.assertEqual(digest, by_id["a1"]["source_sha256"])
        self.assertEqual(paper("b1", ["b"])["excerpt"], by_id["b1"]["excerpt"])
        self.assertNotIn("source_sha256", by_id["b1"])

    def test_rejects_unhashable_topic_refs(self):
        for ref in (["a"], {"id": "a"}):
            with self.assertRaisesRegex(ValueError, "topic references must be strings"):
                allocate_methods(payload(papers=[paper("x", [ref])]))
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp) / "in.json", Path(tmp) / "out.json"
            source.write_text(json.dumps(payload(papers=[paper("x", [["a"]])])), encoding="utf-8")
            run = subprocess.run([sys.executable, str(ROOT / "scripts/allocate_method_candidates.py"), "--input", str(source), "--output", str(output)], capture_output=True, text=True)
            self.assertEqual(2, run.returncode)
            self.assertIn("topic references must be strings", run.stderr)
            self.assertNotIn("Traceback", run.stderr)

    def test_output_is_deterministic_and_has_expected_topic_count(self):
        value = payload(1)
        self.assertEqual(json.dumps(allocate_methods(value), sort_keys=True), json.dumps(allocate_methods(value), sort_keys=True))
        result = allocate_methods(value)
        self.assertEqual(min(value["budget"], len(result["clusters"])), result["distinct_topics_selected"])

    def test_cli_writes_allocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp) / "in.json", Path(tmp) / "out.json"
            source.write_text(json.dumps(payload()), encoding="utf-8")
            run = subprocess.run([sys.executable, str(ROOT / "scripts/allocate_method_candidates.py"), "--input", str(source), "--output", str(output)], capture_output=True, text=True)
            self.assertEqual(0, run.returncode, run.stderr)
            self.assertIn("selected", json.loads(output.read_text(encoding="utf-8")))
            first = output.read_bytes()
            run = subprocess.run([sys.executable, str(ROOT / "scripts/allocate_method_candidates.py"), "--input", str(source), "--output", str(output)], capture_output=True, text=True)
            self.assertEqual(0, run.returncode, run.stderr)
            self.assertEqual(first, output.read_bytes())

    def test_research_discovery_guidance_mentions_literature_and_paired_gate(self):
        text = (ROOT / "authored-skills/research-discovery/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("allocate_method_candidates.py", text)
        self.assertIn("paired-bootstrap lower bound", text)


if __name__ == "__main__":
    unittest.main()
