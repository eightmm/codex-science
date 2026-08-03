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

    def test_ci_runs_one_full_history_release_gate_before_required_checks(self) -> None:
        workflow = (self.root / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        self.assertEqual(1, workflow.count("validate_release.py --base-ref"))
        self.assertIn("fetch-depth: 0", workflow)
        self.assertIn("github.event.pull_request.base.sha", workflow)
        self.assertIn("github.event.before", workflow)
        self.assertIn("needs: release-gate", workflow)
        self.assertIn("if: always()", workflow)
        self.assertIn("RELEASE_GATE_RESULT: ${{ needs.release-gate.result }}", workflow)
        self.assertIn('test "$RELEASE_GATE_RESULT" = success', workflow)
        self.assertNotIn("needs.release-gate.result == 'success'", workflow)


if __name__ == "__main__":
    unittest.main()
