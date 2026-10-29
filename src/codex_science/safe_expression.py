"""Bounded expression evaluation and finite-domain counterexample search.

The evaluator deliberately supports a small mathematical language. It does not
execute Python code, import modules, access attributes, index objects, or call
user-defined functions.
"""
from __future__ import annotations

import ast
import hashlib
import itertools
import json
import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Iterable, Mapping

MAX_EXPRESSION_CHARS = 4096
MAX_AST_NODES = 512
MAX_INTEGER_BITS = 4096
MAX_POWER_ABS = 64
MAX_DOMAIN_VALUES = 10_000
MAX_SEARCH_EVALUATIONS = 1_000_000


class ExpressionError(ValueError):
    """Raised when an expression exceeds the safe mathematical language."""


class _UnsupportedExpressionError(ExpressionError):
    """Raised for syntax or constructs outside the supported grammar."""


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _finite_number(value: Any, label: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ExpressionError(f"{label} must be a real number")
    if isinstance(value, float) and not math.isfinite(value):
        raise ExpressionError(f"{label} must be finite")
    if isinstance(value, int) and value.bit_length() > MAX_INTEGER_BITS:
        raise ExpressionError(f"{label} exceeds the integer-size limit")
    return value


def _checked(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, Fraction):
        if max(value.numerator.bit_length(), value.denominator.bit_length()) > MAX_INTEGER_BITS:
            raise ExpressionError("rational result exceeds the size limit")
        return value
    if isinstance(value, int):
        if value.bit_length() > MAX_INTEGER_BITS:
            raise ExpressionError("integer result exceeds the size limit")
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ExpressionError("expression produced a non-finite result")
        return value
    raise ExpressionError(f"unsupported result type: {type(value).__name__}")


_ALLOWED_FUNCTIONS = {
    "abs": abs,
    "min": min,
    "max": max,
    "sqrt": math.sqrt,
    "exp": math.exp,
    "log": math.log,
    "log10": math.log10,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "floor": math.floor,
    "ceil": math.ceil,
    "isclose": math.isclose,
}

_ALLOWED_CONSTANTS = {"pi": math.pi, "e": math.e, "tau": math.tau, "True": True, "False": False}


@dataclass(frozen=True)
class ParsedExpression:
    source: str
    tree: ast.Expression
    names: tuple[str, ...]
    sha256: str


@dataclass
class _SearchArithmetic:
    rationalize_floats: bool = False
    inexact: bool = False

    def number(self, value: Any, label: str) -> Any:
        value = _finite_number(value, label)
        if isinstance(value, float) and not self.rationalize_floats:
            self.inexact = True
            return value
        return _checked(Fraction(value))

    def checked(self, value: Any) -> Any:
        value = _checked(value)
        if isinstance(value, float):
            self.inexact = True
        elif isinstance(value, int) and not isinstance(value, bool):
            value = Fraction(value)
        return value


def parse_expression(source: str, *, allowed_names: Iterable[str] = ()) -> ParsedExpression:
    return _parse_expression(source, allowed_names=allowed_names)


def _parse_statement_expression(source: str) -> ParsedExpression | None:
    """Classify grammar without receipt names; limits remain errors."""
    try:
        return _parse_expression(source, allowed_names=(), allow_unknown_names=True)
    except _UnsupportedExpressionError:
        return None


def _parse_expression(source: str, *, allowed_names: Iterable[str], allow_unknown_names: bool = False) -> ParsedExpression:
    if not isinstance(source, str) or not source.strip():
        raise ExpressionError("expression is required")
    if len(source) > MAX_EXPRESSION_CHARS:
        raise ExpressionError("expression exceeds the character limit")
    try:
        tree = ast.parse(source, mode="eval")
    except SyntaxError as error:
        raise _UnsupportedExpressionError(f"invalid expression syntax: {error.msg}") from error
    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_AST_NODES:
        raise ExpressionError("expression exceeds the AST node limit")
    allowed = set(allowed_names) | set(_ALLOWED_CONSTANTS)
    referenced: set[str] = set()
    for node in nodes:
        if isinstance(node, ast.Name):
            if isinstance(getattr(node, "ctx", None), ast.Load):
                referenced.add(node.id)
        elif isinstance(node, ast.Constant):
            if isinstance(node.value, bool):
                continue
            if not isinstance(node.value, (int, float)):
                raise _UnsupportedExpressionError("numeric literal must be a real number")
            _finite_number(node.value, "numeric literal")
        elif isinstance(
            node,
            (
                ast.Expression,
                ast.Load,
                ast.UnaryOp,
                ast.UAdd,
                ast.USub,
                ast.Not,
                ast.BinOp,
                ast.Add,
                ast.Sub,
                ast.Mult,
                ast.Div,
                ast.FloorDiv,
                ast.Mod,
                ast.Pow,
                ast.BoolOp,
                ast.And,
                ast.Or,
                ast.Compare,
                ast.Eq,
                ast.NotEq,
                ast.Lt,
                ast.LtE,
                ast.Gt,
                ast.GtE,
                ast.Call,
                ast.IfExp,
            ),
        ):
            continue
        else:
            raise _UnsupportedExpressionError(f"unsupported expression element: {type(node).__name__}")
    unknown = sorted(referenced - allowed - set(_ALLOWED_FUNCTIONS))
    if unknown and not allow_unknown_names:
        raise ExpressionError(f"unknown expression names: {', '.join(unknown)}")
    for node in nodes:
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_FUNCTIONS:
                raise _UnsupportedExpressionError("only approved mathematical functions may be called")
            if node.keywords:
                raise _UnsupportedExpressionError("keyword arguments are not supported")
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow) and isinstance(node.right, ast.Constant):
            exponent = _finite_number(node.right.value, "power exponent")
            if abs(float(exponent)) > MAX_POWER_ABS:
                raise ExpressionError("power exponent exceeds the configured bound")
    return ParsedExpression(
        source=source,
        tree=tree,
        names=tuple(sorted(referenced - set(_ALLOWED_CONSTANTS) - set(_ALLOWED_FUNCTIONS))),
        sha256=hashlib.sha256(source.encode("utf-8")).hexdigest(),
    )


def _eval(node: ast.AST, variables: Mapping[str, Any], arithmetic: _SearchArithmetic | None = None) -> Any:
    def evaluate(child: ast.AST) -> Any:
        return _eval(child, variables, arithmetic)

    number = _finite_number if arithmetic is None else arithmetic.number
    checked = _checked if arithmetic is None else arithmetic.checked
    if isinstance(node, ast.Expression):
        return evaluate(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return node.value
        return number(node.value, "numeric literal")
    if isinstance(node, ast.Name):
        if node.id in variables:
            value = variables[node.id]
            if isinstance(value, bool):
                return value
            return number(value, f"variable {node.id}")
        if node.id in _ALLOWED_CONSTANTS:
            value = _ALLOWED_CONSTANTS[node.id]
            if isinstance(value, bool):
                return value
            if arithmetic is not None:
                arithmetic.inexact = True
            return number(value, "mathematical constant")
        raise ExpressionError(f"missing variable: {node.id}")
    if isinstance(node, ast.UnaryOp):
        value = evaluate(node.operand)
        if isinstance(node.op, ast.Not):
            return not bool(value)
        if isinstance(value, bool):
            raise ExpressionError("boolean values cannot be used as signed numbers")
        if isinstance(node.op, ast.UAdd):
            return checked(+value)
        if isinstance(node.op, ast.USub):
            return checked(-value)
    if isinstance(node, ast.BinOp):
        left = evaluate(node.left)
        right = evaluate(node.right)
        if isinstance(left, bool) or isinstance(right, bool):
            raise ExpressionError("boolean values cannot be used in arithmetic")
        if isinstance(node.op, ast.Add):
            return checked(left + right)
        if isinstance(node.op, ast.Sub):
            return checked(left - right)
        if isinstance(node.op, ast.Mult):
            return checked(left * right)
        if isinstance(node.op, ast.Div):
            if right == 0:
                raise ExpressionError("division by zero")
            return checked(left / right)
        if isinstance(node.op, ast.FloorDiv):
            if right == 0:
                raise ExpressionError("division by zero")
            return checked(left // right)
        if isinstance(node.op, ast.Mod):
            if right == 0:
                raise ExpressionError("modulo by zero")
            return checked(left % right)
        if isinstance(node.op, ast.Pow):
            if abs(right) > MAX_POWER_ABS:
                raise ExpressionError("power exponent exceeds the configured bound")
            try:
                return checked(left ** right)
            except (OverflowError, ValueError, ZeroDivisionError) as error:
                raise ExpressionError(f"invalid power operation: {error}") from error
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            for item in node.values:
                if not bool(evaluate(item)):
                    return False
            return True
        if isinstance(node.op, ast.Or):
            for item in node.values:
                if bool(evaluate(item)):
                    return True
            return False
    if isinstance(node, ast.Compare):
        left = evaluate(node.left)
        for operator, comparator in zip(node.ops, node.comparators):
            right = evaluate(comparator)
            if isinstance(operator, ast.Eq):
                passed = left == right
            elif isinstance(operator, ast.NotEq):
                passed = left != right
            elif isinstance(operator, ast.Lt):
                passed = left < right
            elif isinstance(operator, ast.LtE):
                passed = left <= right
            elif isinstance(operator, ast.Gt):
                passed = left > right
            elif isinstance(operator, ast.GtE):
                passed = left >= right
            else:  # pragma: no cover - parser rejects other comparison operators
                raise ExpressionError("unsupported comparison")
            if not passed:
                return False
            left = right
        return True
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_FUNCTIONS:
            raise ExpressionError("unsupported function call")
        arguments = [evaluate(argument) for argument in node.args]
        if any(isinstance(argument, bool) for argument in arguments):
            raise ExpressionError("boolean values cannot be used in numeric functions")
        if arithmetic is not None and node.func.id == "isclose":
            arithmetic.inexact = True
        try:
            return checked(_ALLOWED_FUNCTIONS[node.func.id](*arguments))
        except (TypeError, ValueError, OverflowError, ZeroDivisionError) as error:
            raise ExpressionError(f"function {node.func.id} failed: {error}") from error
    if isinstance(node, ast.IfExp):
        return evaluate(node.body if bool(evaluate(node.test)) else node.orelse)
    raise ExpressionError(f"unsupported expression element: {type(node).__name__}")


def evaluate_expression(source: str | ParsedExpression, variables: Mapping[str, Any] | None = None) -> Any:
    values = dict(variables or {})
    parsed = source if isinstance(source, ParsedExpression) else parse_expression(source, allowed_names=values)
    missing = sorted(set(parsed.names) - set(values))
    if missing:
        raise ExpressionError(f"missing variables: {', '.join(missing)}")
    return _eval(parsed.tree, values)


def _evaluate_exact_expression(source: str | ParsedExpression, variables: Mapping[str, Any]) -> Any:
    """Use witness-confirmation arithmetic, refusing any inexact operation."""
    parsed = source if isinstance(source, ParsedExpression) else parse_expression(source, allowed_names=variables)
    arithmetic = _SearchArithmetic(rationalize_floats=True)
    result = _eval(parsed.tree, variables, arithmetic)
    if arithmetic.inexact:
        raise ExpressionError("expression cannot be confirmed with exact rational arithmetic")
    return result


def _domain_values(payload: Mapping[str, Any], *, index: int) -> tuple[str, tuple[Any, ...], bool]:
    name = str(payload.get("name", "")).strip()
    if not name.isidentifier() or name in _ALLOWED_FUNCTIONS or name in _ALLOWED_CONSTANTS:
        raise ValueError(f"variables[{index}].name must be a safe unique identifier")
    modes = sum(key in payload for key in ("values", "integer_range", "float_grid"))
    if modes != 1:
        raise ValueError(f"variable {name} requires exactly one domain declaration")
    exact = True
    if "values" in payload:
        raw = payload["values"]
        if not isinstance(raw, list) or not raw:
            raise ValueError(f"variable {name} values must be a non-empty list")
        if len(raw) > MAX_DOMAIN_VALUES:
            raise ValueError(f"variable {name} domain exceeds {MAX_DOMAIN_VALUES} values")
        values: list[Any] = []
        for value in raw:
            if isinstance(value, bool):
                values.append(value)
            else:
                values.append(_finite_number(value, f"variable {name} value"))
    elif "integer_range" in payload:
        spec = payload["integer_range"]
        if not isinstance(spec, Mapping):
            raise ValueError(f"variable {name} integer_range must be an object")
        start, stop, step = spec.get("start"), spec.get("stop"), spec.get("step", 1)
        for value in (start, stop, step):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"variable {name} integer_range bounds and step must be integers")
            _finite_number(value, f"variable {name} integer_range parameter")
        if step == 0 or (stop - start) * step < 0:
            raise ValueError(f"variable {name} integer range is empty or misdirected")
        if abs(stop - start) // abs(step) + 1 > MAX_DOMAIN_VALUES:
            raise ValueError(f"variable {name} domain exceeds {MAX_DOMAIN_VALUES} values")
        terminal = stop + (1 if step > 0 else -1)
        values = list(range(start, terminal, step))
    else:
        spec = payload["float_grid"]
        if not isinstance(spec, Mapping):
            raise ValueError(f"variable {name} float_grid must be an object")
        start = float(_finite_number(spec.get("start"), f"variable {name} grid start"))
        stop = float(_finite_number(spec.get("stop"), f"variable {name} grid stop"))
        count = spec.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 2:
            raise ValueError(f"variable {name} float_grid count must be an integer at least 2")
        if count > MAX_DOMAIN_VALUES:
            raise ValueError(f"variable {name} domain exceeds {MAX_DOMAIN_VALUES} values")
        values = [start]
        for offset in range(1, count - 1):
            fraction = offset / (count - 1)
            values.append(start * (1.0 - fraction) + stop * fraction)
        values.append(stop)
        if not all(math.isfinite(value) and min(start, stop) <= value <= max(start, stop) for value in values):
            raise ValueError(f"variable {name} float_grid coordinates must be finite and within its bounds")
        exact = False
    if len(values) > MAX_DOMAIN_VALUES:
        raise ValueError(f"variable {name} domain exceeds {MAX_DOMAIN_VALUES} values")
    if len(set((type(value).__name__, repr(value)) for value in values)) != len(values):
        raise ValueError(f"variable {name} domain contains duplicate values")
    return name, tuple(values), exact


def search_counterexample(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported counterexample-search schema")
    claim_id = str(payload.get("claim_id", "")).strip()
    statement = str(payload.get("statement", "")).strip()
    scope = str(payload.get("scope", "general")).strip()
    if not claim_id or not statement:
        raise ValueError("claim_id and statement are required")
    if scope not in {"finite", "general"}:
        raise ValueError("scope must be finite or general")
    raw_variables = payload.get("variables")
    if not isinstance(raw_variables, list) or not raw_variables:
        raise ValueError("variables must be a non-empty list")
    domains = [_domain_values(item, index=index) for index, item in enumerate(raw_variables) if isinstance(item, Mapping)]
    if len(domains) != len(raw_variables):
        raise ValueError("each variable domain must be an object")
    names = [item[0] for item in domains]
    if len(names) != len(set(names)):
        raise ValueError("variable names must be unique")
    assumptions = payload.get("assumptions", [])
    if not isinstance(assumptions, list) or not all(isinstance(item, str) and item.strip() for item in assumptions):
        raise ValueError("assumptions must be a list of expressions")
    conclusion = str(payload.get("conclusion", "")).strip()
    if not conclusion:
        raise ValueError("conclusion expression is required")
    parsed_assumptions = [parse_expression(item, allowed_names=names) for item in assumptions]
    parsed_conclusion = parse_expression(conclusion, allowed_names=names)
    max_evaluations = int(payload.get("max_evaluations", 100_000))
    if isinstance(payload.get("max_evaluations"), bool) or not 1 <= max_evaluations <= MAX_SEARCH_EVALUATIONS:
        raise ValueError(f"max_evaluations must be between 1 and {MAX_SEARCH_EVALUATIONS}")

    total_combinations = math.prod(len(item[1]) for item in domains)
    evaluations = 0
    satisfying_assignments = 0
    skipped_assumptions = 0
    counterexample: dict[str, Any] | None = None
    exhausted = True
    used_inexact = False
    unconfirmed_failure = False
    for values in itertools.product(*(item[1] for item in domains)):
        if evaluations >= max_evaluations:
            exhausted = False
            break
        assignment = dict(zip(names, values))
        evaluations += 1
        arithmetic = _SearchArithmetic(inexact=any(isinstance(value, float) for value in values))
        assumptions_hold = all(bool(_eval(item.tree, assignment, arithmetic)) for item in parsed_assumptions)
        used_inexact = used_inexact or arithmetic.inexact
        if not assumptions_hold:
            skipped_assumptions += 1
            continue
        satisfying_assignments += 1
        conclusion_holds = bool(_eval(parsed_conclusion.tree, assignment, arithmetic))
        used_inexact = used_inexact or arithmetic.inexact
        if not conclusion_holds:
            confirmed = not arithmetic.inexact
            if not confirmed:
                # Floats are confirmed as their exact encoded binary values;
                # transcendental functions and approximate predicates stay inexact.
                try:
                    confirmed = (
                        all(bool(_evaluate_exact_expression(item, assignment)) for item in parsed_assumptions)
                        and not bool(_evaluate_exact_expression(parsed_conclusion, assignment))
                    )
                except (ValueError, OverflowError, ZeroDivisionError):
                    confirmed = False
            if confirmed:
                counterexample = assignment
                exhausted = False
                break
            unconfirmed_failure = True

    exact_domains = all(item[2] for item in domains)
    if counterexample is not None:
        status = "disproved"
    elif exhausted and scope == "finite" and exact_domains and not used_inexact and evaluations == total_combinations:
        status = "proved-by-exhaustion"
    elif exhausted and evaluations == total_combinations:
        status = "tested-no-counterexample"
    else:
        status = "bounded-no-counterexample"
    result = {
        "schema_version": 1,
        "claim_id": claim_id,
        "statement": statement,
        "statement_sha256": hashlib.sha256(statement.encode("utf-8")).hexdigest(),
        "scope": scope,
        "assumptions": list(assumptions),
        "conclusion": conclusion,
        "variables": [dict(item) for item in raw_variables],
        "status": status,
        "counterexample": counterexample,
        "exhaustive": bool(status == "proved-by-exhaustion"),
        "general_proof": False,
        "exact_domains": exact_domains,
        "total_combinations": total_combinations,
        "evaluations": evaluations,
        "satisfying_assignments": satisfying_assignments,
        "skipped_assumptions": skipped_assumptions,
        "max_evaluations": max_evaluations,
        "limitations": [
            "Failure to find a counterexample is not a proof of a general statement.",
            "Floating-point grids test only the sampled values.",
        ],
    }
    if unconfirmed_failure:
        result["limitations"].append(
            "Floating-point failures without exact confirmation are not certified counterexamples; the search status records only its tested or bounded coverage."
        )
    result["fingerprint"] = canonical_sha256(result)
    return result


def validate_counterexample_receipt(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported counterexample receipt schema")
    status = str(payload.get("status", ""))
    if status not in {"disproved", "proved-by-exhaustion", "tested-no-counterexample", "bounded-no-counterexample"}:
        raise ValueError(f"invalid counterexample receipt status: {status}")
    if status == "disproved" and not isinstance(payload.get("counterexample"), Mapping):
        raise ValueError("disproved receipt requires a counterexample assignment")
    if status == "proved-by-exhaustion":
        if payload.get("scope") != "finite" or payload.get("exhaustive") is not True or payload.get("exact_domains") is not True:
            raise ValueError("proved-by-exhaustion requires an exact finite exhaustive domain")
    material = dict(payload)
    fingerprint = str(material.pop("fingerprint", "")).lower()
    if len(fingerprint) != 64 or canonical_sha256(material) != fingerprint:
        raise ValueError("counterexample receipt fingerprint mismatch")
    for field in ("evaluations", "satisfying_assignments", "skipped_assumptions", "total_combinations", "max_evaluations"):
        value = payload.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"counterexample receipt {field} must be a non-negative integer")
    expected = search_counterexample(payload)
    # The unchanged producer is deterministic. Canonical comparison also keeps
    # JSON booleans distinct from numbers when checking counts and assignments.
    for field, value in expected.items():
        if field != "fingerprint" and (field not in payload or canonical_sha256(payload[field]) != canonical_sha256(value)):
            raise ValueError(f"counterexample receipt {field} disagrees with replayed search")
