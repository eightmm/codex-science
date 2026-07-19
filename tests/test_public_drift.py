import importlib.util
import sys
import unittest
from pathlib import Path


class PublicDriftTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        scripts = str(cls.root / "scripts")
        sys.path.insert(0, scripts)
        spec = importlib.util.spec_from_file_location("public_drift", cls.root / "scripts" / "public_drift.py")
        if spec is None or spec.loader is None:
            raise RuntimeError("could not load public_drift")
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def test_healthy_and_semantic_drift_are_distinct(self) -> None:
        class Healthy:
            def search(self, query, *, limit):
                return [{"id": "record-1"}]
        class Empty:
            def search(self, query, *, limit):
                return []
        healthy = self.module.probe("source", Healthy(), "query", previous_failures=2)
        empty = self.module.probe("source", Empty(), "query", previous_failures=0)
        self.assertEqual("healthy", healthy["status"])
        self.assertEqual(0, healthy["consecutive_failures"])
        self.assertEqual("semantic-drift", empty["status"])

    def test_repeated_transient_failures_degrade_then_become_unavailable(self) -> None:
        class Timeout:
            def search(self, query, *, limit):
                raise TimeoutError("timeout")
        first = self.module.probe("source", Timeout(), "query", previous_failures=0)
        second = self.module.probe("source", Timeout(), "query", previous_failures=1)
        third = self.module.probe("source", Timeout(), "query", previous_failures=2)
        self.assertEqual("transient-failure", first["status"])
        self.assertEqual("degraded", second["status"])
        self.assertEqual("unavailable", third["status"])

    def test_markdown_report_is_stable_and_human_readable(self) -> None:
        report = {"checked_at": "2026-07-19T00:00:00Z", "status": "healthy", "sources": [{"source": "pubmed", "status": "healthy", "consecutive_failures": 0, "detail": "record=1"}]}
        rendered = self.module.render_markdown(report)
        self.assertIn("| pubmed | healthy | 0 | record=1 |", rendered)
        self.assertIn("Overall: **healthy**", rendered)


if __name__ == "__main__":
    unittest.main()
