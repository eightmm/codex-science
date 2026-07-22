# Numerical verification, dimensions, and uncertainty

Read the relevant section before invoking a numerical, dimensional, or uncertainty command.

## Numerical verification

```bash
uv run python scripts/verify_numerical_result.py numerical.input.json \
  --output artifacts/run/numerical-verification.json \
  --require-clean
```

Input:

```json
{
  "schema_version": 1,
  "verification_id": "V1",
  "claim_id": "C1",
  "method": "finite-volume solver",
  "reference_value": 1.0,
  "thresholds": {
    "minimum_order": 1.8,
    "max_residual": 1e-6,
    "max_invariant_deviation": 1e-5,
    "max_cross_method_z": 3.0
  },
  "solver": {
    "precision": "IEEE-754 binary64",
    "relative_tolerance": 1e-10,
    "absolute_tolerance": 1e-12
  },
  "refinements": [
    {
      "resolution": 0.2,
      "estimate": 1.02,
      "residual": 1e-7,
      "invariants": {"mass": 2e-6}
    },
    {
      "resolution": 0.1,
      "estimate": 1.005,
      "residual": 1e-8,
      "invariants": {"mass": 5e-7}
    },
    {
      "resolution": 0.05,
      "estimate": 1.00125,
      "residual": 1e-9,
      "invariants": {"mass": 1e-7}
    }
  ],
  "cross_method": [
    {"method": "solver-A", "estimate": 1.0000, "uncertainty": 0.001},
    {"method": "solver-B", "estimate": 1.0004, "uncertainty": 0.001}
  ]
}
```

Resolution must strictly decrease from coarse to fine. If `error` is absent and `reference_value` is present, absolute error is computed. Without a reference, observed order is estimated from successive solution differences only when adjacent refinement ratios are approximately equal.

The receipt detects:

- non-refining sequences;
- incomplete or nonmonotone error series;
- fewer than three levels for an order claim;
- observed order below threshold;
- residual or invariant failure;
- unstated precision or solver tolerance;
- cross-method disagreement relative to declared uncertainties.

Observed convergence on a finite range does not prove asymptotic convergence or model validity.

## Dimensional analysis

```bash
uv run python scripts/check_dimensions.py dimensions.input.json \
  --output artifacts/run/dimension-check.json \
  --require-clean
```

```json
{
  "schema_version": 1,
  "check_id": "units-1",
  "claim_id": "C-unit",
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

Unit expressions use `*`, `/`, integer powers, rational powers, and the bounded built-in SI registry. Supported elementary dimensional functions include `sqrt` and `abs`; `exp`, logarithms, and trigonometric functions require dimensionless arguments.

The runtime rejects addition of unlike dimensions, incompatible conversion, affine-temperature multiplication, path-like code, function attributes, and arbitrary execution.

Dimensional consistency is only a necessary check. A dimensionally valid equation may still have the wrong coefficient, sign, constitutive law, boundary condition, or physical model.

## Uncertainty propagation

```bash
uv run python scripts/propagate_uncertainty.py uncertainty.input.json \
  --output artifacts/run/uncertainty-propagation.json \
  --require-clean
```

```json
{
  "schema_version": 1,
  "propagation_id": "U1",
  "claim_id": "C-U",
  "expression": "x*y",
  "inputs": [
    {"name": "x", "mean": 2.0, "standard_uncertainty": 0.1, "unit": "m"},
    {"name": "y", "mean": 3.0, "standard_uncertainty": 0.2, "unit": "N"}
  ],
  "covariance": [
    {"left": "x", "right": "y", "value": 0.005}
  ],
  "method": "both",
  "confidence_level": 0.95,
  "seed": 20260722,
  "samples": 20000,
  "nonlinearity_threshold": 0.25
}
```

Methods:

- `linear`: central finite-difference gradient and full covariance propagation;
- `monte-carlo`: seeded correlated Gaussian sampling using a checked covariance factorization;
- `both`: run both and report disagreement.

The receipt reports nominal value, gradient, covariance, variance contributions, standard uncertainty, Monte Carlo interval, accepted and failed samples, and linear-versus-Monte-Carlo discrepancy.

A covariance matrix must be positive semidefinite. Monte Carlo requires an explicit seed. The Gaussian model, standard uncertainties, and covariance are scientific assumptions, not facts established by the runtime.

## Interpretation boundary

- A low residual can coexist with a wrong equation or wrong boundary conditions.
- Two implementations can agree because they share the same defect.
- A dimension check cannot validate an empirical coefficient.
- A Monte Carlo interval is conditional on its input distributions and correlation model.
- Solver tolerance is not discretization error.
- Numerical error, parameter uncertainty, model discrepancy, and measurement uncertainty must remain separate where they arise from different mechanisms.
- Preserve failed refinements, non-finite samples, and disagreement; do not discard them only to make a receipt pass.
