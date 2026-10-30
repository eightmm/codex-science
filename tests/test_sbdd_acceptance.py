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


    def test_execution_cli_refuses_output_symlink_loop(self) -> None:
        import tempfile
        from loader_cases import assert_refused
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "loop"
            output.symlink_to(output.name)
            for path in (output, output / "child"):
                with self.subTest(path=path):
                    assert_refused(self, "run_sbdd_acceptance.py",
                                   [root / "examples/sbdd-executable/input.json", path], 1)
            self.assertEqual(output.name, output.readlink().name)
            self.assertEqual([output], list(Path(directory).iterdir()))

    def test_execution_cli_refuses_malformed_registry_without_writing(self) -> None:
        import tempfile
        from loader_cases import assert_refused, malformed_json
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            output = Path(directory) / "output"
            for contents in malformed_json():
                path.write_bytes(contents)
                for existing in (False, True):
                    if existing:
                        output.mkdir(exist_ok=True)
                        (output / "keep").write_bytes(b"preserve")
                    with self.subTest(contents=contents, existing=existing):
                        assert_refused(self, "run_sbdd_acceptance.py", [root / "examples/sbdd-executable/input.json", output, "--registry", path], 1, output)
                (output / "keep").unlink()
                output.rmdir()
            path.unlink()
            for candidate in (path, Path(directory)):
                assert_refused(self, "run_sbdd_acceptance.py", [root / "examples/sbdd-executable/input.json", output, "--registry", candidate], 1, output)


if __name__ == "__main__":
    unittest.main()
