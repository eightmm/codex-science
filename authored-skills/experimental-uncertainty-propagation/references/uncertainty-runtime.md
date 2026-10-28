# Uncertainty propagation runtime

## Input

```bash
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/propagate_uncertainty.py" uncertainty.json \
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

Finite-difference scale is chosen from input magnitude and uncertainty. All methods report the original linear result; only `linear` and `both` enforce stability against the derivative at half that step. The runtime raises `ValueError` (`unstable numerical derivative for <name>`) if the two estimates differ by more than 0.1% relative to the larger magnitude, allowing the larger of subtraction roundoff (16 output-value ulps divided by the original step) and a central-difference truncation floor (`function_scale * (step / input_scale)^2 / input_scale`, with `function_scale = max(1, absolute sampled function values)` and `input_scale = max(1, absolute input mean, input uncertainty)`). The absolute floor permits truncation-sized discrepancies near stationary points. Monte Carlo-only propagation does not enforce this stability check because it does not use the linear derivative. Stable results retain the original derivative. This bounded check cannot prove derivative accuracy or detect every oscillatory alias. Review nonsmooth models, boundaries, and severe cancellation independently.

Negative propagated variance raises `ValueError` unless its magnitude is within `1e-12` times the sum of absolute covariance contributions, where cancellation roundoff is clamped to zero.

## Monte Carlo

`monte-carlo` and `both` require an explicit integer seed and 100–1,000,000 requested samples. The covariance matrix is checked for a valid positive-semidefinite factorization. The built-in sampler uses a correlated Gaussian input model.

The receipt records requested, accepted, and failed samples, output mean, standard uncertainty, percentile interval, seed, and expression hash. Too many invalid or non-finite samples fail the run. Any failed samples add the `monte-carlo-domain-filtering` review finding: the reported statistics are conditional on the accepted samples. The finding is major when failures are at least 1% of requested samples and minor otherwise. A major finding changes status to `findings`; a minor finding alone leaves status `passed`, so inspect findings even with `--require-clean`.

When `both` is selected, the runtime compares linear and Monte Carlo uncertainty plus nominal-to-Monte-Carlo mean shift. Material disagreement produces a nonlinearity finding.

## Covariance rules

- Diagonal entries are fixed by `standard_uncertainty^2`. A supplied diagonal must agree within relative tolerance `1e-9`, with no absolute floor; the derived value is retained. Zero uncertainty requires an exactly zero diagonal and zero covariance with every other input.
- Off-diagonal covariance must reflect a scientific shared source, not an arbitrary tuning parameter.
- The matrix must be symmetric and positive semidefinite. Correlation bounds and factorization residuals use relative tolerance `1e-12` against the corresponding standard-uncertainty product or diagonal variance. Every positive pivot is used regardless of magnitude, preserving correlations between inputs with very different scales. Invalid correlations, indefinite matrices, and inconsistent singular matrices raise `ValueError`.
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
