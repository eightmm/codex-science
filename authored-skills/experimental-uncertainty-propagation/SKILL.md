---
name: experimental-uncertainty-propagation
description: "Quantify and review measurement or model-input uncertainty with explicit measurands, calibration, Type A and B components, covariance, linear sensitivities, seeded Monte Carlo propagation, nonlinear disagreement, and machine-readable uncertainty receipts."
license: MIT
---

# Experimental Uncertainty Propagation

## Decision contract

State the measurand, measurement equation, units, operating conditions, calibration chain, corrections, data reduction, intended coverage statement, and every uncertainty source. Separate repeatability, reproducibility, resolution, drift, calibration, sampling, numerical, and model-form contributions. State all distribution and covariance assumptions.

Do not call every discrepancy “error,” and do not treat a sample standard deviation as the full uncertainty budget.

## Reference usage

Read [the uncertainty propagation runtime](references/uncertainty-runtime.md) before `uncertainty-propagation`, covariance entry, Monte Carlo execution, or a coverage statement. It defines exact input fields, positive-semidefinite covariance rules, linear sensitivities, seeded sampling, output, and interpretation.

Preserve inputs, calibration references, covariance, seed, and receipts with `$science-provenance`, then use `$science-review` for material uncertainty claims.

## Workflow

1. Define the measurand and measurement equation with units.
2. Build Type A and Type B components and convert them to standard uncertainties with explicit distributions.
3. Record covariance caused by shared calibration, environment, preprocessing, or common parameters.
4. Check dimensions, correlation bounds, and covariance positive semidefiniteness.
5. Run `scripts/propagate_uncertainty.py`; use `both` when first-order linearization may be questionable.
6. Verify linear and Monte Carlo means and standard uncertainties, inspect failed samples, and identify dominant sensitivity contributors.
7. Vary plausible Type B distributions, correlations, calibration values, and model forms.
8. Report value, unit, standard uncertainty, interval convention, assumptions, dominant contributors, and limitations.

## Outputs

- `uncertainty-propagation` receipt with expression hash, means, standard uncertainties, covariance, gradient, variance, sensitivities, seed, Monte Carlo interval, findings, and fingerprint;
- calibration and traceability records;
- uncertainty budget and sensitivity alternatives;
- dimension check where quantities carry units;
- manifest and independent review receipt.

## Boundaries

- Linear propagation can fail near discontinuities, boundaries, zero denominators, and strong nonlinearity.
- Monte Carlo output is conditional on the declared distributions and covariance; it does not discover them.
- Covariance from shared sources must not be omitted merely because independence is convenient.
- A coverage interval requires a clear probability or repeated-sampling interpretation.
- Numerical uncertainty, measurement uncertainty, and model discrepancy must remain separate when they have different origins.
- Stop when calibration validity, unit convention, covariance, measurand definition, or input distribution is unresolved.

## Source basis

Original synthesis informed by NIST Technical Note 1297 and the source registry at `../../docs/TEXTBOOK_SOURCES.md`.
