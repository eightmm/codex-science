---
name: computational-physics-validation
description: "Verify computational physics software, quantify numerical uncertainty, and validate models against experiments. Use for convergence studies, manufactured solutions, conservation audits, code-to-code comparisons, calibration, uncertainty quantification, and simulation credibility."
license: MIT
---

# Computational Physics Validation

## Separate the questions

- Code verification: is the discretized algorithm implemented correctly?
- Solution verification: how large is numerical error for this run?
- Validation: how well does the mathematical model represent the physical experiment for its intended use?
- Uncertainty quantification: how do input, numerical, and model uncertainties affect outputs?

Never use agreement with one experiment to replace code verification, or grid convergence to claim physical validity.

## Build the evidence ladder

1. Define quantities of interest, intended-use domain, acceptance criteria, and failure consequences.
2. Test pure components, invariants, exact solutions, and method of manufactured solutions where possible.
3. Vary mesh, time step, solver tolerance, precision, and stochastic sample count independently.
4. Estimate observed order and numerical uncertainty; investigate non-asymptotic refinement behavior.
5. Calibrate only designated parameters, then validate against separate measurements with uncertainty.
6. Record code revision, inputs, environment, seeds, raw outputs, and post-processing.

## Verify

- Audit conservation, symmetries, positivity, boundary conditions, and dimensional consistency.
- Compare with a simpler analytic limit and an independent implementation or formulation.
- Check sensitivity to uncertain inputs and numerical controls; identify dominant contributors.
- Compare residual patterns and quantities of interest with experimental uncertainty, not point values alone.
- Define the validated domain; treat extrapolation outside it as a new claim.

## Deliver

Provide a credibility matrix separating implementation, numerical, input, experimental, and model-form evidence,
with pass/fail criteria, unresolved discrepancies, provenance, and intended-use limits.

## Source basis

Original synthesis informed by NASA verification, validation, and uncertainty-quantification guidance and open
numerical-analysis sources recorded in `../../docs/TEXTBOOK_SOURCES.md`.
