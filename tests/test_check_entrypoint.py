import unittest
from pathlib import Path


class CheckEntrypointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]

    def test_fast_cleanup_does_not_leak_return_traps(self) -> None:
        script = (self.root / "scripts" / "check.sh").read_text(encoding="utf-8")
        self.assertNotIn("trap 'rm -f \"$tmp\"' RETURN", script)
        self.assertNotIn("rm -rf \"$sbdd_dir\"' RETURN", script)

    def test_ci_runs_the_same_complete_fast_entrypoint_as_developers(self) -> None:
        workflow = (self.root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("run: ./scripts/check.sh fast", workflow)


if __name__ == "__main__":
    unittest.main()
