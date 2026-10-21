---
name: inverse-problems-regularization
description: "Formulate and solve inverse problems with stable regularization and calibrated uncertainty. Use for parameter or field recovery, deconvolution, tomography, system identification, data assimilation, Bayesian inversion, and learned inverse models."
license: MIT
---

# Inverse Problems and Regularization

## Decision contract
State the forward map, observations, unknown, noise and nuisance model, identifiable target, and evaluation data. Choose regularization and uncertainty procedures without tuning on final evaluation data.

## Workflow
1. **Specify the inverse problem.**
   State the forward operator, unknown, observation process, noise model, nuisance parameters, constraints, units,
   and quantity actually identifiable from the data. Examine null spaces, conditioning, nonuniqueness, and model
   discrepancy before selecting a solver. Distinguish recovering a latent field from predicting an outcome.
   Write the complete objective and resolve whether a reported Tikhonov parameter enters as `lambda` or
   `lambda^2`; include noise whitening and parameter scaling rather than relying on a method name alone.

2. **Regularize.**
   - Use scaling, truncated decompositions, Tikhonov penalties, sparsity, total variation, constraints, or priors only with a stated rationale.
   - Choose regularization strength by a declared rule such as discrepancy, cross-validation, evidence, or an L-curve diagnostic.
     For a discrepancy rule, use a whitened residual and calibrate its target to the noise law and effective degrees of freedom.
   - Preserve a validation set or independent experiment; do not tune the prior or regularizer on the final evaluation data.
   - Distinguish the observation being reconstructed from an external benchmark. Do not cross-validate across measurement
     coordinates unless they are genuinely exchangeable; use independent or grouped acquisitions when available.
   - For learned inverses, split by acquisition source, subject, time, or structure to prevent leakage through near duplicates.

3. **Verify.**
   - Perform synthetic recovery with known truth across noise and model-mismatch levels.
   - Check forward residuals, but do not treat small residual as proof of correct recovery.
   - Inspect singular values, posterior or profile geometry, resolution kernels, and parameter correlations.
   - Test sensitivity to initialization, mesh, prior or penalty, regularization strength, and nuisance assumptions.
   - Calibrate intervals or posterior predictive coverage and evaluate out-of-distribution failure.

4. **Deliver.**
   Report forward model, identifiability, data split, noise, regularizer or prior, selection rule, convergence,
   recovery and forward-fit metrics, uncertainty, applicability domain, and unresolved nonuniqueness.

## Outputs
Return normalized inputs and assumptions; a machine-readable evidence or execution table; claim IDs marked supported, contradicted, inconclusive, or unavailable; uncertainty and limitations; and the smallest falsifiable next action. Record commands or derivations and artifact paths and hashes with `$science-provenance`; preserve failures and nulls. Run `$science-review` before material or consequential scientific conclusions.

## Boundaries
A small residual does not establish unique or accurate recovery; distinguish regularization bias, noise, model discrepancy, and non-identifiability. Stop claims of recovery when the target is not identifiable or uncertainty is uncalibrated.

## Source basis

Original synthesis informed by an openly licensed modern text on regularization of nonlinear inverse problems
and numerical-analysis sources recorded in `../../docs/TEXTBOOK_SOURCES.md`.
