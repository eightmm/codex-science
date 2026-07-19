import json
import unittest
from pathlib import Path

from codex_science.sbdd import audit_sbdd_benchmark, benchmark_passes


class SBDDAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).resolve().parents[1] / "examples" / "sbdd-acceptance"
        self.valid = json.loads((root / "benchmark.json").read_text(encoding="utf-8"))
        self.seeded = json.loads((root / "seeded-leaks.json").read_text(encoding="utf-8"))

    def test_acceptance_fixture_has_no_blocking_findings(self) -> None:
        findings = audit_sbdd_benchmark(self.valid)
        self.assertTrue(benchmark_passes(self.valid), findings)
        self.assertFalse(
            any(item["severity"] in {"critical", "major"} for item in findings), findings
        )

    def test_seeded_leaks_and_affinity_overclaim_are_detected(self) -> None:
        findings = audit_sbdd_benchmark(self.seeded)
        codes = {item["code"] for item in findings}
        for expected in (
            "pocket-leak",
            "known-training-overlap",
            "analog-series-leak",
            "scaffold-leak",
            "target-leak",
            "target-family-leak",
            "missing-subgroup-analysis",
            "affinity-overclaim",
        ):
            self.assertIn(expected, codes)
        self.assertFalse(benchmark_passes(self.seeded))


if __name__ == "__main__":
    unittest.main()
