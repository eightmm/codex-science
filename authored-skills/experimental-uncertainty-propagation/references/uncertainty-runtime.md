# Uncertainty propagation runtime

## Input

```bash
uv run python scripts/propagate_uncertainty.py uncertainty.json \
  --output artifacts/run/uncertainty-propagation.json \
  --require-clean
```

```json
{
  "schema_version": 1,
  "propagation_id": "U1",
  "claim_id": "C1",
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

The expression uses the same bounded mathematical language as counterexample search. It cannot access files, attributes, imports, or user-defined functions.

## Linear propagation

The runtime evaluates the nominal expression, estimates a central finite-difference gradient, and computes

```text
u_y^2 = g^T C g
```

using the full covariance matrix. It reports each diagonal sensitivity contribution, but correlated cross-terms remain part of the total variance and must be interpreted from the matrix.

Finite-difference scale is chosen from input magnitude and uncertainty. Review the result when the model is nonsmooth, near a boundary, or has severe cancellation.

## Monte Carlo

`monte-carlo` and `both` require an explicit integer seed and 100–1,000,000 requested samples. The covariance matrix is checked for a valid positive-semidefinite factorization. The built-in sampler uses a correlated Gaussian input model.

The receipt records requested, accepted, and failed samples, output mean, standard uncertainty, percentile interval, seed, and expression hash. Too many invalid or non-finite samples fail the run.

When `both` is selected, the runtime compares linear and Monte Carlo uncertainty plus nominal-to-Monte-Carlo mean shift. Material disagreement produces a nonlinearity finding.

## Covariance rules

- Diagonal entries are fixed by `standard_uncertainty^2`.
- Off-diagonal covariance must reflect a scientific shared source, not an arbitrary tuning parameter.
- The matrix must be symmetric and positive semidefinite.
- Shared calibration, environmental exposure, batch correction, common preprocessing, and reused parameters can induce covariance.
- Independence is an assumption that must be justified, not the default because no covariance was reported.

## Reporting boundary

Report:

- measurand estimate and unit;
- standard uncertainty and interval convention;
- all input means, standard uncertainties, units, and distributions;
- covariance and its provenance;
- dominant sensitivities;
- calibration and traceability records;
- seed, sample count, and failed samples;
- linear/Monte-Carlo disagreement and sensitivity alternatives.

The runtime assumes Gaussian input sampling for Monte Carlo and does not validate calibration, traceability, distribution choice, or model discrepancy. A passed receipt means the declared propagation contract passed, not that the total uncertainty is complete.
