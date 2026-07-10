---
name: experimental-uncertainty-propagation
description: "Quantify and report experimental measurement uncertainty. Use for measurand definitions, calibration, Type A and Type B components, covariance, nonlinear propagation, Monte Carlo uncertainty, coverage intervals, and traceable result reporting."
license: MIT
---

# Experimental Uncertainty Propagation

## Define the measurement

State the measurand, measurement equation, units, operating conditions, calibration chain, corrections, data
reduction, and intended coverage statement. Separate repeatability, reproducibility, resolution, drift,
calibration, sampling, and model-form contributions. Do not call all variation “error.”

## Build the uncertainty budget

1. Estimate Type A components from an explicit statistical model and effective independent sample size.
2. Estimate Type B components from certificates, specifications, prior data, or bounded assumptions.
3. Convert components to standard uncertainties and document each assumed distribution.
4. Include covariance caused by shared calibrations, environmental effects, or common preprocessing.
5. Propagate through the measurement equation using sensitivities or Monte Carlo for strong nonlinearity.

## Verify

- Check dimensions, signs, correlation bounds, and positive semidefiniteness of covariance matrices.
- Compare linear propagation with Monte Carlo in a regime where both should agree.
- Test sensitivity to plausible Type B distributions and correlation assumptions.
- Confirm calibration validity dates, traceability, resolution effects, and significant digits.
- Distinguish standard, combined, and expanded uncertainty; state the coverage factor and interpretation.

## Deliver

Report the estimate as value, unit, uncertainty, coverage convention, uncertainty budget, degrees of freedom
when used, correlations, calibration provenance, and dominant sensitivity contributors.

## Source basis

Original synthesis informed by NIST Technical Note 1297 and the source registry at
`../../docs/TEXTBOOK_SOURCES.md`.
