import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from codex_science.formal_proof import run_formal_proof_check
from codex_science.math_contracts import (
    build_mathematical_claim,
    build_proof_receipt,
    math_review_findings,
    validate_proof_obligation_graph,
)
from codex_science.safe_expression import ExpressionError, evaluate_expression, search_counterexample


class MathResearchRuntimeTests(unittest.TestCase):
    def test_safe_expression_rejects_python_escape_hatches(self) -> None:
        self.assertEqual(7, evaluate_expression("x*2 + 1", {"x": 3}))
        for expression in (
            "().__class__",
            "__import__('os')",
            "[x for x in [1,2,3]]",
            "open('secret')",
            "2**1000",
        ):
            with self.subTest(expression=expression), self.assertRaises(ExpressionError):
                evaluate_expression(expression, {"x": 1})

    def test_counterexample_and_finite_exhaustion_have_distinct_semantics(self) -> None:
        false_result = search_counterexample(
            {
                "schema_version": 1,
                "claim_id": "C-false",
                "statement": "For all real x, x^2 >= x",
                "scope": "general",
                "variables": [{"name": "x", "float_grid": {"start": 0.0, "stop": 1.0, "count": 5}}],
                "assumptions": ["True"],
                "conclusion": "x*x >= x",
                "max_evaluations": 100,
            }
        )
        self.assertEqual("disproved", false_result["status"])
        self.assertEqual({"x": 0.25}, false_result["counterexample"])
        self.assertFalse(false_result["general_proof"])

        finite_result = search_counterexample(
            {
                "schema_version": 1,
                "claim_id": "C-finite",
                "statement": "x^2 >= 0 on {-2,-1,0,1,2}",
                "scope": "finite",
                "variables": [{"name": "x", "integer_range": {"start": -2, "stop": 2, "step": 1}}],
                "assumptions": ["True"],
                "conclusion": "x*x >= 0",
                "max_evaluations": 100,
            }
        )
        self.assertEqual("proved-by-exhaustion", finite_result["status"])
        self.assertTrue(finite_result["exhaustive"])
        self.assertFalse(finite_result["general_proof"])

    def test_proof_review_rejects_computation_promoted_to_deductive_proof(self) -> None:
        statement = "For every integer x, x*x >= 0."
        test_receipt = build_proof_receipt(
            receipt_id="R-test",
            claim_id="C1",
            statement=statement,
            kind="computational-test",
            status="passed",
            assumptions=["x was sampled from a bounded range"],
            checker={"general_proof": False},
        )
        claim = build_mathematical_claim(
            claim_id="C1",
            statement=statement,
            domain="integers",
            assumptions=[],
            quantifiers=["for every integer x"],
            status="proved-deductive",
            permitted_inference="A general theorem over the integers.",
            proof_receipt_ids=["R-test"],
        )
        codes = {item["code"] for item in math_review_findings([claim], [test_receipt], [], [])}
        self.assertIn("test-presented-as-proof", codes)
        self.assertIn("deductive-proof-missing", codes)

    def test_proof_obligation_cycles_and_unresolved_dependencies_are_found(self) -> None:
        graph = {
            "schema_version": 1,
            "graph_id": "G1",
            "claim_id": "C1",
            "obligations": [
                {"id": "A", "statement": "A", "status": "passed", "dependencies": ["B"], "assumptions": []},
                {"id": "B", "statement": "B", "status": "open", "dependencies": ["A"], "assumptions": []},
            ],
        }
        codes = {item["code"] for item in validate_proof_obligation_graph(graph)}
        self.assertIn("proof-obligation-cycle", codes)
        self.assertIn("unresolved-proof-dependency", codes)

    def test_formal_proof_preview_and_fake_kernel_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            theorem = root / "Main.lean"
            theorem.write_text("theorem two_plus_two : 2 + 2 = 4 := by norm_num\n", encoding="utf-8")
            payload = {
                "schema_version": 1,
                "check_id": "check-1",
                "receipt_id": "proof-1",
                "claim_id": "claim-1",
                "statement": "2 + 2 = 4",
                "theorem_file": "Main.lean",
                "command_mode": "lean",
                "timeout_seconds": 30,
                "assumptions": [],
            }
            preview = run_formal_proof_check(payload, workspace=root, execute=False)
            self.assertEqual("preview", preview["status"])
            self.assertFalse(preview["execute_requested"])

            def fake_runner(command: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
                if command[-1] == "--version":
                    return subprocess.CompletedProcess(command, 0, "Lean (version 4.20.0)\n", "")
                return subprocess.CompletedProcess(command, 0, "", "")

            with mock.patch("codex_science.formal_proof.shutil.which", return_value="/usr/bin/lean"):
                checked = run_formal_proof_check(payload, workspace=root, execute=True, runner=fake_runner)
            self.assertEqual("passed", checked["status"])
            receipt = checked["proof_receipt"]
            self.assertTrue(receipt["checker"]["kernel_checked"])
            self.assertEqual("formal-kernel", receipt["kind"])

    def test_formal_proof_rejects_sorry_even_if_process_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            (root / "Main.lean").write_text("theorem bad : False := by sorry\n", encoding="utf-8")
            payload = {
                "schema_version": 1,
                "check_id": "check-bad",
                "receipt_id": "proof-bad",
                "claim_id": "claim-bad",
                "statement": "False",
                "theorem_file": "Main.lean",
                "command_mode": "lean",
                "timeout_seconds": 30,
                "assumptions": [],
            }

            def fake_runner(command: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
                if command[-1] == "--version":
                    return subprocess.CompletedProcess(command, 0, "Lean 4\n", "")
                return subprocess.CompletedProcess(command, 0, "", "")

            with mock.patch("codex_science.formal_proof.shutil.which", return_value="/usr/bin/lean"):
                checked = run_formal_proof_check(payload, workspace=root, execute=True, runner=fake_runner)
            self.assertEqual("failed", checked["status"])
            self.assertIn("sorry", checked["proof_receipt"]["admitted_constructs"])


if __name__ == "__main__":
    unittest.main()
