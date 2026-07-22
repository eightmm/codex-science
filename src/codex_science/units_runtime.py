"""Dependency-free SI unit parsing, conversion, and equation dimension audits."""
from __future__ import annotations

import ast
import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Mapping

from codex_science.safe_expression import canonical_sha256

BASE_DIMENSIONS = ("length", "mass", "time", "current", "temperature", "amount", "luminous_intensity")
Dimension = tuple[Fraction, Fraction, Fraction, Fraction, Fraction, Fraction, Fraction]
ZERO_DIMENSION: Dimension = tuple(Fraction(0) for _ in BASE_DIMENSIONS)  # type: ignore[assignment]


def _dimension(**values: int) -> Dimension:
    return tuple(Fraction(values.get(name, 0)) for name in BASE_DIMENSIONS)  # type: ignore[return-value]


@dataclass(frozen=True)
class Unit:
    symbol: str
    scale: float
    dimension: Dimension
    offset: float = 0.0

    @property
    def affine(self) -> bool:
        return self.offset != 0.0

    def multiply(self, other: "Unit") -> "Unit":
        if self.affine or other.affine:
            raise ValueError("affine temperature units cannot be multiplied or divided")
        return Unit(
            f"({self.symbol}*{other.symbol})",
            self.scale * other.scale,
            tuple(left + right for left, right in zip(self.dimension, other.dimension)),  # type: ignore[arg-type]
        )

    def divide(self, other: "Unit") -> "Unit":
        if self.affine or other.affine:
            raise ValueError("affine temperature units cannot be multiplied or divided")
        if other.scale == 0:
            raise ValueError("unit scale cannot be zero")
        return Unit(
            f"({self.symbol}/{other.symbol})",
            self.scale / other.scale,
            tuple(left - right for left, right in zip(self.dimension, other.dimension)),  # type: ignore[arg-type]
        )

    def power(self, exponent: Fraction) -> "Unit":
        if self.affine and exponent != 1:
            raise ValueError("affine temperature units cannot be exponentiated")
        if abs(exponent.numerator) > 64 or exponent.denominator > 16:
            raise ValueError("unit exponent exceeds configured limits")
        scale = self.scale ** float(exponent)
        if not math.isfinite(scale):
            raise ValueError("unit exponent produced a non-finite scale")
        return Unit(
            f"({self.symbol}^{exponent})",
            scale,
            tuple(value * exponent for value in self.dimension),  # type: ignore[arg-type]
            self.offset if exponent == 1 else 0.0,
        )


def _unit(symbol: str, scale: float, dimension: Dimension, offset: float = 0.0) -> Unit:
    return Unit(symbol, scale, dimension, offset)


M = _dimension(length=1)
KG = _dimension(mass=1)
S = _dimension(time=1)
A = _dimension(current=1)
K = _dimension(temperature=1)
MOL = _dimension(amount=1)
CD = _dimension(luminous_intensity=1)

UNIT_REGISTRY: dict[str, Unit] = {
    "one": _unit("1", 1.0, ZERO_DIMENSION),
    "m": _unit("m", 1.0, M),
    "cm": _unit("cm", 1e-2, M),
    "mm": _unit("mm", 1e-3, M),
    "um": _unit("um", 1e-6, M),
    "nm": _unit("nm", 1e-9, M),
    "angstrom": _unit("angstrom", 1e-10, M),
    "km": _unit("km", 1e3, M),
    "kg": _unit("kg", 1.0, KG),
    "g": _unit("g", 1e-3, KG),
    "mg": _unit("mg", 1e-6, KG),
    "ug": _unit("ug", 1e-9, KG),
    "s": _unit("s", 1.0, S),
    "ms": _unit("ms", 1e-3, S),
    "us": _unit("us", 1e-6, S),
    "ns": _unit("ns", 1e-9, S),
    "min": _unit("min", 60.0, S),
    "h": _unit("h", 3600.0, S),
    "day": _unit("day", 86400.0, S),
    "A": _unit("A", 1.0, A),
    "K": _unit("K", 1.0, K),
    "degC": _unit("degC", 1.0, K, 273.15),
    "mol": _unit("mol", 1.0, MOL),
    "cd": _unit("cd", 1.0, CD),
    "rad": _unit("rad", 1.0, ZERO_DIMENSION),
    "deg": _unit("deg", math.pi / 180.0, ZERO_DIMENSION),
    "L": _unit("L", 1e-3, tuple(value * 3 for value in M)),
    "mL": _unit("mL", 1e-6, tuple(value * 3 for value in M)),
}


def _register_derived(symbol: str, scale: float, dimension: Dimension) -> None:
    UNIT_REGISTRY[symbol] = _unit(symbol, scale, dimension)


_register_derived("Hz", 1.0, tuple(-value for value in S))
_register_derived("N", 1.0, tuple(mass + length - 2 * time for length, mass, time in zip(M, KG, S)))
_register_derived("Pa", 1.0, tuple(n - 2 * length for n, length in zip(UNIT_REGISTRY["N"].dimension, M)))
_register_derived("J", 1.0, tuple(n + length for n, length in zip(UNIT_REGISTRY["N"].dimension, M)))
_register_derived("W", 1.0, tuple(j - time for j, time in zip(UNIT_REGISTRY["J"].dimension, S)))
_register_derived("C", 1.0, tuple(current + time for current, time in zip(A, S)))
_register_derived("V", 1.0, tuple(w - current for w, current in zip(UNIT_REGISTRY["W"].dimension, A)))
_register_derived("ohm", 1.0, tuple(v - current for v, current in zip(UNIT_REGISTRY["V"].dimension, A)))
_register_derived("S_to_conductance", 1.0, tuple(-value for value in UNIT_REGISTRY["ohm"].dimension))
_register_derived("F", 1.0, tuple(c - v for c, v in zip(UNIT_REGISTRY["C"].dimension, UNIT_REGISTRY["V"].dimension)))
_register_derived("T", 1.0, tuple(v - 2 * length for v, length in zip(UNIT_REGISTRY["V"].dimension, M)))
_register_derived("H", 1.0, tuple(v + time - current for v, time, current in zip(UNIT_REGISTRY["V"].dimension, S, A)))
_register_derived("eV", 1.602176634e-19, UNIT_REGISTRY["J"].dimension)


def _fraction(node: ast.AST) -> Fraction:
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
        return Fraction(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_fraction(node.operand)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        numerator = _fraction(node.left)
        denominator = _fraction(node.right)
        if denominator == 0:
            raise ValueError("unit exponent denominator cannot be zero")
        return numerator / denominator
    raise ValueError("unit powers must be integer or rational constants")


def _eval_unit(node: ast.AST) -> Unit:
    if isinstance(node, ast.Expression):
        return _eval_unit(node.body)
    if isinstance(node, ast.Name):
        try:
            return UNIT_REGISTRY[node.id]
        except KeyError as error:
            raise ValueError(f"unknown unit: {node.id}") from error
    if isinstance(node, ast.Constant) and node.value == 1:
        return UNIT_REGISTRY["one"]
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Mult):
            return _eval_unit(node.left).multiply(_eval_unit(node.right))
        if isinstance(node.op, ast.Div):
            return _eval_unit(node.left).divide(_eval_unit(node.right))
        if isinstance(node.op, ast.Pow):
            return _eval_unit(node.left).power(_fraction(node.right))
    raise ValueError(f"unsupported unit expression element: {type(node).__name__}")


def parse_unit(source: str) -> Unit:
    text = str(source).strip()
    if not text:
        raise ValueError("unit expression is required")
    if len(text) > 256:
        raise ValueError("unit expression exceeds 256 characters")
    normalized = text.replace("^", "**").replace("µ", "u").replace("Å", "angstrom")
    try:
        tree = ast.parse(normalized, mode="eval")
    except SyntaxError as error:
        raise ValueError(f"invalid unit expression: {error.msg}") from error
    if len(list(ast.walk(tree))) > 128:
        raise ValueError("unit expression is too complex")
    return _eval_unit(tree)


def dimension_dict(dimension: Dimension) -> dict[str, str]:
    return {
        name: str(value)
        for name, value in zip(BASE_DIMENSIONS, dimension)
        if value != 0
    }


def convert_value(value: float, source: str, target: str) -> float:
    source_unit = parse_unit(source)
    target_unit = parse_unit(target)
    if source_unit.dimension != target_unit.dimension:
        raise ValueError(f"incompatible dimensions: {source} and {target}")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError("conversion value must be finite")
    si_value = numeric * source_unit.scale + source_unit.offset
    converted = (si_value - target_unit.offset) / target_unit.scale
    if not math.isfinite(converted):
        raise ValueError("unit conversion produced a non-finite value")
    return converted


def _eval_dimension(node: ast.AST, variables: Mapping[str, Unit]) -> Dimension:
    if isinstance(node, ast.Expression):
        return _eval_dimension(node.body, variables)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ValueError("only numeric constants are allowed in dimensional equations")
        return ZERO_DIMENSION
    if isinstance(node, ast.Name):
        if node.id not in variables:
            raise ValueError(f"unknown dimensional variable: {node.id}")
        return variables[node.id].dimension
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        return _eval_dimension(node.operand, variables)
    if isinstance(node, ast.BinOp):
        left = _eval_dimension(node.left, variables)
        if isinstance(node.op, (ast.Add, ast.Sub)):
            right = _eval_dimension(node.right, variables)
            if left != right:
                raise ValueError("addition or subtraction combines incompatible dimensions")
            return left
        if isinstance(node.op, ast.Mult):
            right = _eval_dimension(node.right, variables)
            return tuple(a + b for a, b in zip(left, right))  # type: ignore[return-value]
        if isinstance(node.op, ast.Div):
            right = _eval_dimension(node.right, variables)
            return tuple(a - b for a, b in zip(left, right))  # type: ignore[return-value]
        if isinstance(node.op, ast.Pow):
            exponent = _fraction(node.right)
            return tuple(value * exponent for value in left)  # type: ignore[return-value]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.keywords or len(node.args) != 1:
            raise ValueError("dimensional functions accept exactly one positional argument")
        argument = _eval_dimension(node.args[0], variables)
        if node.func.id == "sqrt":
            return tuple(value / 2 for value in argument)  # type: ignore[return-value]
        if node.func.id == "abs":
            return argument
        if node.func.id in {"exp", "log", "log10", "sin", "cos", "tan"}:
            if argument != ZERO_DIMENSION:
                raise ValueError(f"{node.func.id} requires a dimensionless argument")
            return ZERO_DIMENSION
        raise ValueError(f"unsupported dimensional function: {node.func.id}")
    raise ValueError(f"unsupported dimensional expression element: {type(node).__name__}")


def infer_dimension(expression: str, variables: Mapping[str, Unit]) -> Dimension:
    if not expression.strip() or len(expression) > 4096:
        raise ValueError("dimensional expression is empty or too long")
    try:
        tree = ast.parse(expression.replace("^", "**"), mode="eval")
    except SyntaxError as error:
        raise ValueError(f"invalid dimensional expression: {error.msg}") from error
    if len(list(ast.walk(tree))) > 512:
        raise ValueError("dimensional expression is too complex")
    return _eval_dimension(tree, variables)


def run_dimension_check(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported dimension-check input schema")
    check_id = str(payload.get("check_id", "")).strip()
    claim_id = str(payload.get("claim_id", "")).strip()
    if not check_id or not claim_id:
        raise ValueError("check_id and claim_id are required")
    raw_variables = payload.get("variables")
    if not isinstance(raw_variables, Mapping) or not raw_variables:
        raise ValueError("variables must map names to unit expressions")
    variables: dict[str, Unit] = {}
    for name, unit_source in raw_variables.items():
        identifier = str(name)
        if not identifier.isidentifier():
            raise ValueError(f"invalid variable name: {identifier}")
        variables[identifier] = parse_unit(str(unit_source))
    equations_raw = payload.get("equations", [])
    if not isinstance(equations_raw, list) or not all(isinstance(item, Mapping) for item in equations_raw):
        raise ValueError("equations must be a list of objects")
    conversions_raw = payload.get("conversions", [])
    if not isinstance(conversions_raw, list) or not all(isinstance(item, Mapping) for item in conversions_raw):
        raise ValueError("conversions must be a list of objects")
    findings: list[dict[str, str]] = []
    equations: list[dict[str, Any]] = []
    for index, item in enumerate(equations_raw):
        identifier = str(item.get("id", f"equation-{index}"))
        left_source = str(item.get("left", "")).strip()
        right_source = str(item.get("right", "")).strip()
        if not left_source or not right_source:
            raise ValueError(f"equation {identifier} requires left and right expressions")
        try:
            left = infer_dimension(left_source, variables)
            right = infer_dimension(right_source, variables)
            compatible = left == right
            error = None
        except ValueError as exc:
            left = right = ZERO_DIMENSION
            compatible = False
            error = str(exc)
        equations.append({
            "id": identifier,
            "left": left_source,
            "right": right_source,
            "left_dimension": dimension_dict(left),
            "right_dimension": dimension_dict(right),
            "compatible": compatible,
            "error": error,
        })
        if not compatible:
            findings.append({
                "code": "dimension-mismatch",
                "severity": "critical",
                "message": f"Equation {identifier} is dimensionally inconsistent" + (f": {error}" if error else "."),
            })
    conversions: list[dict[str, Any]] = []
    for index, item in enumerate(conversions_raw):
        value = float(item.get("value"))
        source = str(item.get("from", "")).strip()
        target = str(item.get("to", "")).strip()
        identifier = str(item.get("id", f"conversion-{index}"))
        try:
            converted = convert_value(value, source, target)
            error = None
        except ValueError as exc:
            converted = None
            error = str(exc)
            findings.append({
                "code": "unit-conversion-failed",
                "severity": "major",
                "message": f"Conversion {identifier} failed: {exc}",
            })
        conversions.append({"id": identifier, "value": value, "from": source, "to": target, "converted": converted, "error": error})
    result: dict[str, Any] = {
        "schema_version": 1,
        "check_id": check_id,
        "claim_id": claim_id,
        "status": "passed" if not findings else "findings",
        "variables": {name: {"unit": unit.symbol, "scale": unit.scale, "dimension": dimension_dict(unit.dimension)} for name, unit in variables.items()},
        "equations": equations,
        "conversions": conversions,
        "findings": findings,
        "input_sha256": canonical_sha256(payload),
        "limitations": [
            "Dimensional consistency is necessary but not sufficient for a correct equation.",
            "The built-in registry is intentionally bounded; unrecognized domain-specific units must be normalized explicitly.",
        ],
    }
    result["fingerprint"] = canonical_sha256(result)
    return result


def validate_dimension_check(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported dimension-check receipt schema")
    for field in ("check_id", "claim_id", "status"):
        if not str(payload.get(field, "")).strip():
            raise ValueError(f"{field} is required")
    if payload.get("status") not in {"passed", "findings"}:
        raise ValueError("invalid dimension-check status")
    if not isinstance(payload.get("equations"), list) or not isinstance(payload.get("findings"), list):
        raise ValueError("equations and findings must be lists")
    material = dict(payload)
    fingerprint = str(material.pop("fingerprint", "")).lower()
    if len(fingerprint) != 64 or canonical_sha256(material) != fingerprint:
        raise ValueError("dimension-check fingerprint mismatch")


def review_dimension_check(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    try:
        validate_dimension_check(payload)
    except ValueError as error:
        return [{"code": "invalid-dimension-check", "severity": "critical", "message": str(error)}]
    findings = [dict(item) for item in payload.get("findings", [])]
    if payload.get("status") == "passed" and findings:
        findings.append({"code": "unsafe-dimension-pass", "severity": "critical", "message": "Dimension check is passed despite recorded mismatches."})
    return findings
