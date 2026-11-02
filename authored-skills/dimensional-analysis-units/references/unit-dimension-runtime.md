# Unit and dimension runtime

## Unit grammar

The built-in parser is intentionally bounded. Unit expressions use names, `*`, `/`, integer or rational powers, and the literal `1`. `^` is normalized to exponentiation. The micro sign (U+00B5) and Greek mu (U+03BC) are read as `u`, and `Å` as `angstrom`.

The registry is a fixed list, `UNIT_REGISTRY` in `src/codex_science/units_runtime.py`; there is no general prefix parser. The registered symbols are `one`, `m`, `cm`, `mm`, `um`, `nm`, `angstrom`, `km`, `kg`, `g`, `mg`, `ug`, `s`, `ms`, `us`, `ns`, `min`, `h`, `day`, `A`, `K`, `degC`, `mol`, `cd`, `rad`, `deg`, `L`, `mL`, `Hz`, `N`, `Pa`, `J`, `W`, `C`, `V`, `ohm`, `S_to_conductance` (siemens), `F`, `T`, `H`, and `eV`. Any other prefixed symbol, such as `kJ`, `kPa`, `MHz`, `mA`, `mV`, `kN`, `mmol`, `uL`, or `GPa`, is an unknown unit. Numeric scale factors such as `1000*J` are refused too, because the only numeric literal in a unit expression is `1`; convert the value to a registered unit before the check.

Examples:

```text
kg*m/s^2
J/mol
m^(1/2)/s
1/s
```

Unknown units fail loudly. Normalize domain-specific units explicitly rather than treating them as dimensionless.

Boolean constants and floating-point spellings such as `1.0` are refused as unit literals; the numeric dimensionless literal is `1`. Conversion values cannot be booleans.

Ordinary scale arithmetic preserves binary64 rounding. If a scale operation overflows or underflows, the runtime retries with 80-digit Decimal arithmetic to recover cancellation and representable conversions even when an individual source or target scale exceeds binary64 range. `parse_unit` still requires its final scale to be finite and nonzero in binary64. Unrecoverable scale range failures and nonzero conversions that round to zero raise `ValueError`; conversion failures are recorded as `unit-conversion-failed` findings.

## Equation check

```bash
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/check_dimensions.py" dimensions.json \
  --output artifacts/run/dimension-check.json \
  --require-clean
```

```json
{
  "schema_version": 1,
  "check_id": "units-1",
  "claim_id": "C1",
  "variables": {
    "m": "kg",
    "a": "m/s^2",
    "F": "N",
    "d": "m",
    "E": "J"
  },
  "equations": [
    {"id": "force", "left": "F", "right": "m*a"},
    {"id": "work", "left": "E", "right": "F*d"}
  ],
  "conversions": [
    {"id": "length", "value": 100.0, "from": "cm", "to": "m"}
  ]
}
```

Addition and subtraction require equal dimensions. Multiplication, division, powers, square roots, and absolute values propagate dimensions. Exponential, logarithmic, and trigonometric arguments must be dimensionless.

Equation powers follow these rules:

- The exponent must be dimensionless; a dimensioned exponent such as `2**T` with `T` in K is a `dimension-mismatch`.
- A dimensioned base needs a constant integer or rational exponent: an integer (`x**2`), an integer-valued float (`x**2.0`), or a ratio of such constants (`x**(1/2)`, `x**-(3/2)`). A fractional float such as `x**0.5` and a variable exponent such as `x**n` are refused with `equation powers of a dimensioned base must be integer or rational constants`; write `x**(1/2)` or `sqrt(x)` instead. A zero denominator in a constant exponent is refused.
- A dimensionless base with a dimensionless exponent is dimensionless whatever the exponent's value, so `n**0.5`, `2**n`, and `n**n` pass when `n` is dimensionless.

Unit expressions keep the stricter grammar above: integer or rational constants only, with numerators up to 64 and denominators up to 16.

A check must check something. An input with no equations and no conversions, and an equation whose two sides reference no variable (for example `2 = 3` or `sqrt(4) = 2`; function names do not count), each produce a major `vacuous-dimension-check` finding, so `--require-clean` fails. An identity of a variable with itself, such as `x = x`, is not vacuous. Conversions alone are a non-vacuous check.

In equation expressions, variables declared in affine units such as `degC` cannot be multiplied, divided, raised to a power other than 1, or passed to `sqrt` (a power of 1/2); dimensionless literals count as multiplication.

The receipt records variable dimensions, left and right dimensions for every equation, conversion values, failures, input hash, limitations, and deterministic fingerprint.

Review of a stored receipt re-derives findings from the recorded entries without recomputing dimensions with the current registry: an equation recorded as incompatible or with an error gives `dimension-mismatch`, an equation recorded without an error whose sides name no variable gives `vacuous-dimension-check`, a conversion with an `error` or a null `converted` gives `unit-conversion-failed`, and an empty receipt gives `vacuous-dimension-check`. A receipt whose status is `passed` while any of these hold also gets `unsafe-dimension-pass`. Equation sides that are not strings or do not parse in a record without an error are reported as `invalid-dimension-check`.

## Affine quantities

Celsius is affine relative to Kelvin. Conversion uses the offset, but Celsius cannot be multiplied, divided, or exponentiated as an ordinary absolute unit. A temperature difference must be represented separately from an absolute temperature when the distinction matters.

Known gap: equation checks do not distinguish absolute temperatures from temperature differences in addition and subtraction. `degC` and `K` have the same dimension, so `T1 + T2` with both in `degC`, or an equation setting a `degC` variable equal to a `K` difference, passes the dimension check even though the sum of two absolute Celsius temperatures or a Celsius-versus-Kelvin-difference equality is not physically meaningful. Review such equations by hand.

Gauge pressure, calendar time, pH, decibels, molar fractions, activity, counts, and other convention-dependent quantities also require an explicit semantic contract; base dimensions alone are insufficient.

## Nondimensionalization

The runtime checks dimensions but does not choose characteristic scales. For nondimensionalization:

1. define the reference scales and their physical meaning;
2. substitute each dimensional variable as scale times dimensionless variable;
3. derive every dimensionless group;
4. estimate group magnitudes before dropping terms;
5. state the limiting balance and neglected terms;
6. rescale to verify recovery of the original equation.

## Boundary

- A dimensionally valid equation can have a wrong constant, sign, model, or boundary condition.
- A conversion can be arithmetically correct while the source quantity uses a different convention or reference frame.
- Angles are dimensionless in SI but retain semantic meaning; degree/radian conversion still matters.
- Do not infer physical plausibility from a passed dimension receipt alone.
- Preserve source units and conversion provenance in the artifact bundle.
