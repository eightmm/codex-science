---
name: inverse-problems-regularization
description: "Formulate and solve inverse problems with stable regularization and calibrated uncertainty. Use for parameter or field recovery, deconvolution, tomography, system identification, data assimilation, Bayesian inversion, and learned inverse models."
license: MIT
---

# Inverse Problems and Regularization

## Decision contract

State the forward map, observations, unknown, noise and nuisance model, identifiable target, constraints, units, and evaluation data. Specify regularization and uncertainty procedures without tuning on final evaluation data. Examine Hadamard well-posedness, null spaces, conditioning, nonuniqueness, and model discrepancy before claiming recovery.

## Reference usage

Read [references/inverse-problem-evidence.md](references/inverse-problem-evidence.md) before selecting or tuning a regularizer, interpreting a recovered parameter or field, designing synthetic validation, or reporting uncertainty. It defines well-posedness, regularization choices, inverse-crime controls, resolution and identifiability checks, and failure criteria.

Preserve data lineage, model, code, environment, and failed or null results with `$science-provenance`; use `$science-review` before material or consequential scientific conclusions.

## Workflow

1. **Specify the forward problem.** Write the forward operator, unknown, observations, noise and nuisance models, constraints, units, and target; distinguish latent-field recovery from outcome prediction and record assumptions and whether the target is identifiable.
2. **Assess well-posedness.** Check existence, uniqueness, and continuous dependence in the Hadamard sense; inspect null spaces, conditioning, nonuniqueness, and model discrepancy; record the evidence and unresolved defects.
3. **Choose a method.** Select Tikhonov, total variation, sparsity, truncated SVD, constraints, or a prior with a reason; write the full objective, parameter scaling, noise whitening, and whether the coefficient is `lambda` or `lambda^2`; record the exact method.
4. **Choose parameters without leakage.** Declare discrepancy principle, L-curve, GCV, cross-validation, evidence, or another justified rule and its data split; use grouped/independent acquisitions where needed and do not cross-validate nonexchangeable measurement coordinates; record choices before final evaluation.
5. **Design a discriminating validation.** Test synthetic recovery across noise and model mismatch, using a different discretization or forward implementation from inversion to avoid the inverse crime; include independent or grouped real acquisitions when available; record truth, split, and dependency lineage.
6. **Check resolution and identifiability.** Inspect singular values, resolution kernels, parameter correlations, profile geometry, and distinguishable targets; record which modes or parameters the data can resolve.
7. **Calibrate uncertainty and sensitivity.** Use posterior, bootstrap, or other justified uncertainty and check interval/credible-set calibration; vary initialization, mesh, prior/penalty, regularization strength, nuisance assumptions, and noise model; record uncertainty and fragile conclusions.
8. **Verify and report.** Check forward residuals, convergence, out-of-distribution failure, and recovery metrics; a small residual alone does not establish correct recovery; report limitations, applicability domain, and next falsifiable action with artifacts and hashes.

## Outputs

Produce an `inverse-recovery-evidence-v1` record containing: claim identifier (`claim_id`); claim class and status (`claim_class`, `status`: supported, contradicted, inconclusive, or unavailable); forward model and target (`forward_model`, `target`); data split and source lineage (`data_split`, `source_lineage`); noise and nuisance model (`noise_model`, `nuisance_model`); regularizer, objective, parameter, and selection rule (`regularizer`, `objective`, `regularization_parameter`, `selection_rule`); identifiability and resolution findings (`identifiability`, `resolution`); fit and recovery metrics (`metrics`); uncertainty and sensitivity (`uncertainty`, `sensitivity`); applicability domain and limitations (`applicability_domain`, `limitations`); artifact paths and hashes (`artifacts`). Preserve failed, null, and unavailable results distinctly.

## Boundaries

A small residual does not establish unique or accurate recovery; distinguish regularization bias, noise, model discrepancy, and non-identifiability. Do not describe a reconstructed field or simulated prediction as experimentally observed or proven. Stop recovery claims when the target is not identifiable, the forward/noise model is unspecified, or uncertainty is uncalibrated.

## Source basis

Original synthesis informed by an openly licensed modern text on regularization of nonlinear inverse problems
and numerical-analysis sources recorded in `../../docs/TEXTBOOK_SOURCES.md`.
