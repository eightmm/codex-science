import ast
import math
import unittest

from codex_science.safe_expression import (
    MAX_AST_NODES,
    MAX_EXPRESSION_CHARS,
    ExpressionError,
    ParsedExpression,
    evaluate_expression,
    parse_expression,
)


class ParseRejectionTests(unittest.TestCase):
    def assertRejected(self, source, fragment, **kwargs):
        with self.assertRaises(ExpressionError) as caught:
            parse_expression(source, **kwargs)
        self.assertIn(fragment, str(caught.exception))

    def test_empty_or_non_string_expression(self):
        for source in ("", "   \t", None, 3):
            with self.subTest(source=source):
                self.assertRejected(source, "expression is required")

    def test_character_limit_edge(self):
        parse_expression("1" + " " * (MAX_EXPRESSION_CHARS - 1))
        self.assertRejected("1" + " " * MAX_EXPRESSION_CHARS, "character limit")

    def test_ast_node_limit_edge(self):
        def build(count):
            return "+".join(["1"] * count)

        count = 1
        while len(list(ast.walk(ast.parse(build(count + 1), mode="eval")))) <= MAX_AST_NODES:
            count += 1
        parse_expression(build(count))
        self.assertRejected(build(count + 1), "AST node limit")

    def test_syntax_error(self):
        self.assertRejected("1 +", "invalid expression syntax")

    def test_disallowed_function_call(self):
        for source in ("__import__('os')", "foo(1)", "(abs if x else abs)(1)"):
            with self.subTest(source=source):
                self.assertRejected(source, "", allowed_names=("x", "foo"))

    def test_disallowed_call_message(self):
        self.assertRejected("foo(1)", "only approved mathematical functions", allowed_names=("foo",))
        self.assertRejected("(abs if x else abs)(1)", "only approved mathematical functions", allowed_names=("x",))

    def test_keyword_arguments_rejected(self):
        # The generic node walk rejects ast.keyword before the dedicated keyword check.
        self.assertRejected("abs(x=1)", "unsupported expression element: keyword", allowed_names=("x",))

    def test_unknown_name(self):
        self.assertRejected("x + y", "unknown expression names: y", allowed_names=("x",))
        self.assertRejected("a + b", "unknown expression names: a, b")

    def test_unsupported_elements(self):
        for source in ("x.real", "x[0]", "[1]", "1 in x", "x is x", "lambda: 1", "-x if x else ~x"):
            with self.subTest(source=source):
                self.assertRejected(source, "unsupported expression element", allowed_names=("x",))

    def test_power_exponent_literal_bound(self):
        parse_expression("2 ** 64")
        parse_expression("2 ** -64")
        self.assertRejected("2 ** 65", "power exponent exceeds")

    def test_numeric_literal_limits(self):
        self.assertRejected("1" + "0" * 1300, "integer-size limit")
        self.assertRejected("1e999", "must be finite")
        for source in ("1j", "'s'", "None"):
            with self.subTest(source=source):
                self.assertRejected(source, "numeric literal must be a real number")


class EvaluateTests(unittest.TestCase):
    def assertEvalRejected(self, source, fragment, variables=None):
        with self.assertRaises(ExpressionError) as caught:
            evaluate_expression(source, variables)
        self.assertIn(fragment, str(caught.exception))

    def test_arithmetic_operators(self):
        cases = {
            "1 + 2": 3,
            "5 - 7": -2,
            "3 * 4": 12,
            "7 / 2": 3.5,
            "7 // 2": 3,
            "7 % 3": 1,
            "2 ** 10": 1024,
            "-3 + +4": 1,
            "x * 2": 8,
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(evaluate_expression(source, {"x": 4}), expected)

    def test_division_by_zero(self):
        self.assertEvalRejected("1 / 0", "division by zero")
        self.assertEvalRejected("1 // 0", "division by zero")
        self.assertEvalRejected("1 % 0", "modulo by zero")
        self.assertEvalRejected("1 / x", "division by zero", {"x": 0})
        self.assertEqual(evaluate_expression("1 / x", {"x": 0.5}), 2.0)

    def test_pow_variable_exponent_bound_and_errors(self):
        self.assertEqual(evaluate_expression("2 ** x", {"x": 64}), 2**64)
        self.assertEvalRejected("2 ** x", "power exponent exceeds", {"x": 65})
        self.assertEvalRejected("2 ** -x", "power exponent exceeds", {"x": 65})
        self.assertEvalRejected("0 ** x", "invalid power operation", {"x": -1})

    def test_integer_result_size_limit(self):
        self.assertEvalRejected("x * x", "integer result exceeds", {"x": 2**3000})

    def test_boolean_not_numeric(self):
        for source in ("True + 1", "1 * False", "x - 1", "x ** 2"):
            with self.subTest(source=source):
                self.assertEvalRejected(source, "boolean values cannot be used in arithmetic", {"x": True})
        self.assertEvalRejected("-True", "boolean values cannot be used as signed numbers")
        self.assertEvalRejected("+x", "boolean values cannot be used as signed numbers", {"x": False})

    def test_not_and_boolean_logic(self):
        self.assertIs(evaluate_expression("not 0"), True)
        self.assertIs(evaluate_expression("not 1"), False)
        self.assertIs(evaluate_expression("True and 1"), True)
        self.assertIs(evaluate_expression("1 and 0"), False)
        self.assertIs(evaluate_expression("0 or 0"), False)
        self.assertIs(evaluate_expression("0 or 2"), True)
        self.assertIs(evaluate_expression("False or False or True"), True)

    def test_and_or_short_circuit(self):
        self.assertIs(evaluate_expression("False and 1 / 0"), False)
        self.assertIs(evaluate_expression("True or 1 / 0"), True)
        self.assertEvalRejected("True and 1 / 0", "division by zero")
        self.assertEvalRejected("False or 1 / 0", "division by zero")

    def test_comparison_operators(self):
        cases = {
            "1 == 1": True,
            "1 == 2": False,
            "1 != 2": True,
            "1 != 1": False,
            "1 < 2": True,
            "2 < 2": False,
            "2 <= 2": True,
            "3 <= 2": False,
            "3 > 2": True,
            "2 > 2": False,
            "2 >= 2": True,
            "1 >= 2": False,
            "1 < 2 < 3": True,
            "1 < 3 < 2": False,
            "3 > 2 > 2": False,
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertIs(evaluate_expression(source), expected)

    def test_chained_comparison_does_not_evaluate_past_failure_only_for_values(self):
        # Chained comparators are all evaluated eagerly up to the first failing link.
        self.assertIs(evaluate_expression("1 > 2 > x", {"x": 0}), False)
        self.assertEvalRejected("2 > 1 > 1 / 0", "division by zero")

    def test_ifexp(self):
        self.assertEqual(evaluate_expression("1 if x else 2", {"x": 0}), 2)
        self.assertEqual(evaluate_expression("1 if x else 1 / 0", {"x": 3}), 1)

    def test_allowed_function_calls(self):
        self.assertEqual(evaluate_expression("abs(-3)"), 3)
        self.assertEqual(evaluate_expression("min(3, 1, 2)"), 1)
        self.assertEqual(evaluate_expression("max(3, 1, 2)"), 3)
        self.assertEqual(evaluate_expression("sqrt(9)"), 3.0)
        self.assertEqual(evaluate_expression("floor(2.7) + ceil(2.1)"), 5)
        self.assertAlmostEqual(evaluate_expression("log(e)"), 1.0)
        self.assertAlmostEqual(evaluate_expression("sin(pi / 2)"), 1.0)
        self.assertAlmostEqual(evaluate_expression("tau / pi"), 2.0)
        self.assertIs(evaluate_expression("isclose(0.1 + 0.2, 0.3)"), True)

    def test_function_failures_are_wrapped(self):
        for source, fragment in (
            ("sqrt(-1)", "function sqrt failed"),
            ("log(0)", "function log failed"),
            ("abs()", "function abs failed"),
            ("min()", "function min failed"),
            ("exp(1000)", "function exp failed"),
            ("sqrt(1, 2)", "function sqrt failed"),
        ):
            with self.subTest(source=source):
                self.assertEvalRejected(source, fragment)

    def test_call_in_hand_built_tree_is_rejected_at_evaluation(self):
        tree = ast.parse("__import__('os')", mode="eval")
        parsed = ParsedExpression(source="__import__('os')", tree=tree, names=(), sha256="0" * 64)
        with self.assertRaises(ExpressionError) as caught:
            evaluate_expression(parsed)
        self.assertIn("unsupported function call", str(caught.exception))

    def test_unsupported_node_in_hand_built_tree_is_rejected_at_evaluation(self):
        tree = ast.parse("[1]", mode="eval")
        parsed = ParsedExpression(source="[1]", tree=tree, names=(), sha256="0" * 64)
        with self.assertRaises(ExpressionError) as caught:
            evaluate_expression(parsed)
        self.assertIn("unsupported expression element: List", str(caught.exception))

    def test_unary_invert_in_hand_built_tree_is_rejected(self):
        parsed = parse_expression("1")
        tree = ast.parse("~1", mode="eval")
        forged = ParsedExpression(source="~1", tree=tree, names=(), sha256=parsed.sha256)
        with self.assertRaises(ExpressionError):
            evaluate_expression(forged)

    def test_missing_variables(self):
        parsed = parse_expression("x + y", allowed_names=("x", "y"))
        self.assertEqual(parsed.names, ("x", "y"))
        self.assertEvalRejected(parsed, "missing variables: x, y")
        self.assertEqual(evaluate_expression(parsed, {"x": 1, "y": 2}), 3)

    def test_variable_values_are_validated(self):
        self.assertEvalRejected("x", "variable x must be a real number", {"x": "1"})
        self.assertEvalRejected("x", "variable x must be a real number", {"x": None})
        self.assertEvalRejected("x", "variable x must be finite", {"x": math.inf})
        self.assertEvalRejected("x", "variable x must be finite", {"x": math.nan})
        self.assertEvalRejected("x", "integer-size limit", {"x": 2**4097})
        self.assertIs(evaluate_expression("x", {"x": True}), True)

    def test_parsed_expression_metadata(self):
        parsed = parse_expression("max(x, pi) + 1", allowed_names=("x",))
        self.assertEqual(parsed.names, ("x",))
        self.assertEqual(len(parsed.sha256), 64)
        self.assertEqual(parsed.source, "max(x, pi) + 1")


if __name__ == "__main__":
    unittest.main()
