import ast
import math
import unittest
from unittest.mock import patch

from codex_science.safe_expression import (
    MAX_AST_NODES,
    MAX_EXPRESSION_CHARS,
    MAX_DOMAIN_VALUES,
    ExpressionError,
    ParsedExpression,
    canonical_sha256,
    evaluate_expression,
    parse_expression,
    search_counterexample,
    validate_counterexample_receipt,
    _domain_values,
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
        parse_expression("2 ** 0")
        parse_expression("2 ** 64.0")
        for exponent in ("65", "65.0", str(10**400), "9" * 400):
            with self.subTest(exponent=exponent):
                self.assertRejected("2 ** " + exponent, "power exponent exceeds the configured bound")

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

    def test_mixed_numeric_overflow_is_labelled(self):
        huge = 10**400
        for operation in ("+", "-", "*", "/", "//", "%"):
            with self.subTest(operation=operation):
                expression = f"x {operation} 0.5"
                self.assertEvalRejected(expression, "numeric evaluation overflow", {"x": huge})
                with self.assertRaisesRegex(ExpressionError, "numeric evaluation overflow"):
                    search_counterexample({
                        "schema_version": 1, "claim_id": "C", "statement": expression,
                        "variables": [{"name": "x", "values": [huge]}], "conclusion": expression,
                    })
        self.assertEvalRejected("sqrt(x)", "function sqrt failed", {"x": huge})
        self.assertEvalRejected("2 ** x", "power exponent exceeds", {"x": huge})

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

    def test_numeric_functions_refuse_boolean_arguments(self):
        functions = ("abs", "min", "max", "sqrt", "exp", "log", "log10", "sin", "cos",
                     "tan", "asin", "acos", "atan", "floor", "ceil", "isclose")
        for function in functions:
            for argument in ("True", "False", "x > 0"):
                arguments = f"1, {argument}" if function in {"min", "max", "isclose"} else argument
                with self.subTest(function=function, argument=argument):
                    self.assertEvalRejected(f"{function}({arguments})", "boolean", {"x": 1})
        self.assertEqual(2, evaluate_expression("abs(-1)+1"))

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


class CounterexampleNumericValidityTests(unittest.TestCase):
    def search(self, domain, expression, **overrides):
        payload = {
            "schema_version": 1, "claim_id": "c", "statement": expression, "scope": "finite",
            "variables": [{"name": "x", **domain}], "conclusion": expression,
        }
        payload.update(overrides)
        result = search_counterexample(payload)
        validate_counterexample_receipt(result)
        return result

    def test_receipt_replays_search_and_refuses_forged_results(self):
        honest = self.search({"integer_range": {"start": 0, "stop": 1}}, "x*x >= 0")
        mutations = (
            {"status": "disproved", "counterexample": {"x": 0}, "exhaustive": False},
            {"status": "bounded-no-counterexample", "exhaustive": False},
            {"evaluations": 0},
            {"satisfying_assignments": 0},
            {"skipped_assumptions": 1},
            {"total_combinations": 0},
            {"exact_domains": False},
            {"general_proof": True},
            {"statement_sha256": "a" * 64},
            {"variables": []},
            {"variables": [None]},
            {"variables": [{"name": "x", "float_grid": {"start": 10**400, "stop": 0, "count": 2}}]},
            {"variables": [{"name": "x", "values": [10**400]}], "conclusion": "x + 0.5 > 0"},
            {"conclusion": ""},
            {"conclusion": "x <"},
            {"conclusion": "x < 0"},
            {"assumptions": ["x < 0"]},
        )
        for changes in mutations:
            with self.subTest(changes=changes):
                forged = {**honest, **changes}
                forged.pop("fingerprint")
                forged["fingerprint"] = canonical_sha256(forged)
                with self.assertRaises(ValueError):
                    validate_counterexample_receipt(forged)

    def test_receipt_witness_obeys_domain_assumptions_and_exact_semantics(self):
        honest = self.search({"values": [0, 1]}, "x < 0", assumptions=["x > 0"])
        for assignment in ({}, {"x": 0}, {"x": -1}, {"x": 2}, {"x": True}, {"x": "1"}, {"x": math.nan}, {"x": math.inf}):
            with self.subTest(assignment=assignment):
                forged = {**honest, "counterexample": assignment}
                forged.pop("fingerprint")
                forged["fingerprint"] = canonical_sha256(forged)
                with self.assertRaises(ValueError):
                    validate_counterexample_receipt(forged)
        for domain, expression in (({"values": [1]}, "x/49*49 != x"), ({"values": [False]}, "x")):
            self.search(domain, expression)

    def test_receipt_counters_require_producer_types_and_limits(self):
        honest = self.search({"values": [0]}, "True", max_evaluations=1)
        fields = ("evaluations", "satisfying_assignments", "skipped_assumptions", "total_combinations", "max_evaluations")
        for field in fields:
            for value in (True, False, "1", 1.0, -1, None, math.nan, math.inf):
                with self.subTest(field=field, value=value):
                    forged = {**honest, field: value}
                    forged.pop("fingerprint")
                    forged["fingerprint"] = canonical_sha256(forged)
                    with self.assertRaises(ValueError):
                        validate_counterexample_receipt(forged)
        for field in ("exhaustive", "exact_domains", "general_proof"):
            forged = dict(honest)
            forged[field] = int(honest[field])
            forged.pop("fingerprint")
            forged["fingerprint"] = canonical_sha256(forged)
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_counterexample_receipt(forged)
        for value in (0, 1_000_001):
            forged = {**honest, "max_evaluations": value}
            forged.pop("fingerprint")
            forged["fingerprint"] = canonical_sha256(forged)
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_counterexample_receipt(forged)
        self.search({"values": [0]}, "True", max_evaluations=1_000_000)

    def test_exact_arithmetic_and_inexact_search_statuses(self):
        cases = (
            ({"values": [1]}, "x / 49 * 49 != x", "disproved"),
            ({"values": [1]}, "x / 49 * 49 == x", "proved-by-exhaustion"),
            ({"values": [1]}, "-x/49 + +x/49 == 0 and (x/49)**-2 == 2401", "proved-by-exhaustion"),
            ({"values": [1]}, "abs(-x/49)*49 == x and min(x/49, x) < max(x/49, x)", "proved-by-exhaustion"),
            ({"values": [1]}, "floor(x/49) == 0 and ceil(x/49) == 1", "proved-by-exhaustion"),
            ({"values": [1]}, "(x/49)//(1/49) == 1 and (x/49)%(1/49) == 0", "proved-by-exhaustion"),
            ({"values": [1.0]}, "x > 0", "tested-no-counterexample"),
            ({"values": [1]}, "x + 0.0 > 0", "tested-no-counterexample"),
            ({"values": [1]}, "sqrt(x) > 0", "tested-no-counterexample"),
            ({"values": [1]}, "x**(1/2) > 0", "tested-no-counterexample"),
            ({"values": [1]}, "isclose(x, x)", "tested-no-counterexample"),
            ({"values": [1]}, "pi > x", "tested-no-counterexample"),
            ({"values": [1]}, "sqrt(x) < 0", "tested-no-counterexample"),
            ({"values": [1]}, "pi < 0", "tested-no-counterexample"),
            ({"values": [1.0]}, "x/49*49 == x", "tested-no-counterexample"),
            ({"values": [1.0]}, "1/(x/49*49-x) > 0", "tested-no-counterexample"),
            ({"values": [1.0]}, "x < 0", "disproved"),
            ({"values": [1, 2]}, "sqrt(x) < 0 if x == 1 else x < 0", "disproved"),
            ({"values": [True, False]}, "x or not x", "proved-by-exhaustion"),
            ({"values": [0]}, "x == 0 or sqrt(x) > 0", "proved-by-exhaustion"),
            ({"values": [2**4095]}, "1/x > 0", "proved-by-exhaustion"),
        )
        for domain, expression, expected in cases:
            with self.subTest(domain=domain, expression=expression):
                result = self.search(domain, expression)
                self.assertEqual(expected, result["status"])
                self.assertEqual(expected == "disproved", result["counterexample"] is not None)
                if expression in {"sqrt(x) < 0", "x/49*49 == x", "1/(x/49*49-x) > 0"} and expected == "tested-no-counterexample":
                    self.assertIn("without exact confirmation", result["limitations"][-1])
        result = self.search({"values": [1]}, "x > 0", assumptions=["sqrt(x) > 0"])
        self.assertEqual("tested-no-counterexample", result["status"])
        result = self.search({"values": [1]}, "x < 0", assumptions=["sqrt(x) < 0"])
        self.assertEqual("tested-no-counterexample", result["status"])
        result = self.search({"values": [1.0]}, "x < 0", assumptions=["x/49*49 != x"])
        self.assertEqual("tested-no-counterexample", result["status"])
        result = self.search({"values": [1, 2]}, "sqrt(x) < 0", max_evaluations=1)
        self.assertEqual("bounded-no-counterexample", result["status"])
        with self.assertRaisesRegex(ExpressionError, "size limit"):
            self.search({"values": [2**3000]}, "x*x > 0")
        with self.assertRaisesRegex(ExpressionError, "size limit"):
            self.search({"values": [2**3000]}, "(1/x)*(1/x) > 0")

    def test_float_grid_preserves_endpoints_and_stays_in_bounds(self):
        result = self.search({"float_grid": {"start": 1.0, "stop": 1e-17, "count": 2}}, "x > 0")
        self.assertEqual("tested-no-counterexample", result["status"])
        for start, stop in ((1.0, 1e-17), (1e-17, 1.0), (-1e308, 1e308), (1e308, -1e308)):
            for count in (2, 3, 7):
                with self.subTest(start=start, stop=stop, count=count):
                    _, values, exact = _domain_values(
                        {"name": "x", "float_grid": {"start": start, "stop": stop, "count": count}}, index=0,
                    )
                    self.assertEqual((start, stop), (values[0], values[-1]))
                    self.assertTrue(all(min(start, stop) <= value <= max(start, stop) for value in values))
                    self.assertFalse(exact)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.search({"float_grid": {"start": 0, "stop": 0, "count": 2}}, "True")
        with self.assertRaisesRegex(ValueError, "within its bounds"):
            self.search({"float_grid": {"start": 1e-17, "stop": 1e-17, "count": 7}}, "True")
        for field in ("start", "stop"):
            for sign in (-1, 1):
                with self.subTest(field=field, sign=sign):
                    spec = {"start": 0, "stop": 1, "count": 2, field: sign * 10**400}
                    with self.assertRaisesRegex(ExpressionError, "variable x grid"):
                        self.search({"float_grid": spec}, "True")
                    spec[field] = sign * int(float.fromhex("0x1.fffffffffffffp+1023"))
                    result = self.search({"float_grid": spec}, "True")
                    self.assertEqual("tested-no-counterexample", result["status"])

    def test_integer_range_requires_non_boolean_integers(self):
        for field in ("start", "stop", "step"):
            for value in (0.5, True, False, "1", None):
                spec = {"start": 0, "stop": 0, "step": 1, field: value}
                with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, "integer"):
                    self.search({"integer_range": spec}, "True")
        for start, stop, step, count in ((0, 0, 1, 1), (2, -2, -2, 3), (-2, 2, 2, 3)):
            result = self.search({"integer_range": {"start": start, "stop": stop, "step": step}}, "True")
            self.assertEqual(count, result["evaluations"])
        for spec in ({}, {"start": 0, "stop": 1, "step": 0}, {"start": 1, "stop": 0}):
            with self.subTest(spec=spec), self.assertRaises(ValueError):
                self.search({"integer_range": spec}, "True")

    def test_domain_limits_are_checked_before_materialization(self):
        for domain in (
            {"integer_range": {"start": 0, "stop": MAX_DOMAIN_VALUES}},
            {"integer_range": {"start": MAX_DOMAIN_VALUES, "stop": 0, "step": -1}},
            {"integer_range": {"start": 0, "stop": 2**100}},
            {"float_grid": {"start": 0, "stop": 1, "count": MAX_DOMAIN_VALUES + 1}},
        ):
            with self.subTest(domain=domain), patch(
                "codex_science.safe_expression.range", side_effect=AssertionError("materialized"), create=True,
            ), self.assertRaisesRegex(ValueError, "domain exceeds"):
                self.search(domain, "True")
        for domain in (
            {"integer_range": {"start": 0, "stop": MAX_DOMAIN_VALUES - 1}},
            {"float_grid": {"start": 0, "stop": 1, "count": MAX_DOMAIN_VALUES}},
            {"values": list(range(MAX_DOMAIN_VALUES))},
        ):
            result = self.search(domain, "True")
            self.assertEqual(MAX_DOMAIN_VALUES, result["evaluations"])
        with self.assertRaisesRegex(ValueError, "domain exceeds"):
            self.search({"values": list(range(MAX_DOMAIN_VALUES + 1))}, "True")
        for domain in ({"values": []}, {"float_grid": {}}, {"integer_range": {}}):
            with self.subTest(domain=domain), self.assertRaises(ValueError):
                self.search(domain, "True")
        for count in (0, 1, -1, True, 2.5, "2", None):
            with self.subTest(count=count), self.assertRaises(ValueError):
                self.search({"float_grid": {"start": 0, "stop": 1, "count": count}}, "True")


if __name__ == "__main__":
    unittest.main()
