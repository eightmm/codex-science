# Unit and dimension runtime

## Unit grammar

The built-in parser is intentionally bounded. Unit expressions use names, `*`, `/`, integer or rational powers, and the literal `1`. `^` is normalized to exponentiation. Common SI base and derived units, metric prefixes, litre, degree, radian, electronvolt, and Celsius are included.

Examples:

```text
kg*m/s^2
J/mol
m^(1/2)/s
1/s
```

Unknown units fail loudly. Normalize domain-specific units explicitly rather than treating them as dimensionless.

## Equation check

```bash
uv run python scripts/check_dimensions.py dimensions.json \
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

The receipt records variable dimensions, left and right dimensions for every equation, conversion values, failures, input hash, limitations, and deterministic fingerprint.

## Affine quantities

Celsius is affine relative to Kelvin. Conversion uses the offset, but Celsius cannot be multiplied, divided, or exponentiated as an ordinary absolute unit. A temperature difference must be represented separately from an absolute temperature when the distinction matters.

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
