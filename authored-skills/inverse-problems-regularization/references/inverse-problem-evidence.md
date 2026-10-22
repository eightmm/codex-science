# Inverse problem evidence guide

## Claim classes and Hadamard status

Classify each material result as a **mathematical property** of a specified operator, a **computed reconstruction** for stated data/model/discretization, a **simulated recovery** against known synthetic truth, a **prediction** on held-out observations, or an **experimentally supported** conclusion backed by measurement. Report a reconstruction as conditional on its model and regularizer. Neither solver convergence nor a small residual proves the recovered unknown is true.

State the Hadamard status of the problem: existence of a solution, uniqueness, and continuous dependence of the solution on the data. Ill-posedness may be addressed by restricting the target, adding prior information, or regularizing, but these choices add assumptions. Record which defect is addressed and which remains. Separate existence of a minimizer from identifiability of the physical unknown.

## Forward model, data, and dependencies

Write the observation model, for example `y = F(x, eta) + epsilon`, with the forward map `F`, unknown `x`, nuisance variables `eta`, noise `epsilon`, units, boundary conditions, and discretization. State the noise law or covariance and any whitening. Record data acquisition, cohort/subject, instrument, preprocessing, exclusions, release/version, and links from raw observations to derived inputs.

Repeated views, neighboring pixels, time points, or samples from one subject/acquisition may share errors and are not automatically independent. Pin dataset and software releases. Record shared forward code, calibration data, mesh, training data, or propagated labels across inversion and validation. Group splits at the source of dependence (subject, acquisition, time, structure, or site); do not split coordinate measurements as if exchangeable without justification.

## Regularization and parameter choice

Name the regularization family and exact objective. For Tikhonov, state penalty operator and whether the scalar is `lambda` or `lambda^2`; for total variation, define the discrete gradient and boundary convention; for sparsity, state the transform/basis and norm; for truncated SVD, give the truncation rule. Explain scaling, constraints, prior, and how each choice changes the solution.

Declare the parameter selection rule: discrepancy principle tied to whitened residual and noise/effective degrees of freedom; L-curve with its selected corner rule; GCV formula and search range; cross-validation split and metric; or another stated procedure. Record the complete path/curve and selected parameter. Do not select a rule or metric after seeing the final evaluation result and present it as preregistered.

Avoid the inverse crime: generate synthetic observations with a different grid, mesh, or sufficiently independent forward implementation than the inverse solver. Disclose any shared discretization or code. Synthetic truth checks implementation under the simulation assumptions only; vary mismatch and avoid treating the generating model as reality.

## Identifiability, resolution, and uncertainty

Probe the null space and singular spectrum, parameter correlations, resolution kernels, profile likelihood, or posterior geometry as appropriate. State which combinations are identifiable at the observed noise level and which are prior-dominated. For nonlinear or learned inverses, test multiple initializations and distinct plausible parameter values that produce similar observations.

Carry measurement, calibration, model, discretization, and regularization uncertainty separately where possible. Choose posterior intervals, bootstrap, profile intervals, or another method that matches the assumptions; report the resampling unit and whether intervals have coverage validation. An interval conditional on one model does not account for model misspecification unless that uncertainty is represented.

## Controls and sensitivity

- Positive controls: recover known simple parameters or fields under a matched forward model and verify the expected limiting/noiseless behavior.
- Negative controls: use non-identifiable parameter combinations, shuffled or zeroed observations, a deliberately mismatched forward model, or held-out conditions where the target is expected to fail; make the expected outcome explicit.
- Check forward residuals in whitened units and inspect structured residuals. A low residual can coexist with severe bias or nonuniqueness.
- Vary noise level/law, regularization family and strength, discretization, initialization, nuisance assumptions, and data split. Include plausible model mismatch and out-of-distribution conditions.
- Treat a conclusion as fragile when the target estimate, sign/rank, selected model, or decision changes beyond a prespecified scientific tolerance under plausible perturbations. Report the perturbation range and all changes.

Common failures and detection: non-identifiability is exposed by null-space or resolution analysis; leakage by source-grouped splits and lineage review; inverse crime by comparing forward/inverse discretizations; parameter tuning leakage by frozen evaluation records; noise misspecification by residual structure and calibration checks; solver-local minima by initialization sweeps; overconfident uncertainty by coverage tests; and discretization artifacts by mesh refinement or an independent forward model.

## Applicability domain

Recovery applies only to the declared observation process, forward model, noise, constraints, regularizer, and data domain. Synthetic tests do not establish real-world validity, cross-site prediction does not establish transport to unrepresented sites, and learned inverse models may fail outside training distributions. If model discrepancy dominates noise or target resolution, report prediction/reconstruction only at the supported scale and abstain from finer recovery claims.

## Claim assignment examples

- A minimizer of the stated penalized objective is a computed reconstruction. It supports optimality for that objective and solver tolerance, not recovery of the true unknown.
- Synthetic recovery against known truth supports a test of the implemented pipeline under that data-generating model. It is not experimental evidence unless the assumptions are independently validated.
- A held-out prediction supports performance only for the declared split, metric, acquisition population, and model version. Shared subjects or acquisitions between training and evaluation invalidate the independence claim.
- A posterior interval is conditional on its likelihood, prior, and forward model. Report calibration checks separately; posterior concentration does not by itself prove identifiability.
- A uniqueness theorem applies only under its operator and parameter assumptions. Numerically similar solutions can still reflect instability or unresolved modes.

## Minimum recovery record

For each result, retain:

1. Raw-data identity, preprocessing, exclusions, acquisition grouping, and release/version.
2. Forward operator, unknown, nuisance variables, noise law/covariance, and units.
3. Full objective, parameter scaling, selected regularization family, and parameter-choice rule.
4. The data split and any shared information across reconstruction, tuning, and evaluation.
5. Solver, discretization, initialization, stopping rule, and convergence diagnostics.
6. Resolution/identifiability evidence, residual structure, and uncertainty method.
7. Synthetic truth and mismatch conditions or independent experimental evidence.
8. Plausible perturbations, failed runs, fragile metrics, and the domain where conclusions apply.

If a discrepancy principle is used, specify the noise model, whitening, and effective degrees of freedom used to set its target. If cross-validation is used, freeze the grouping and metric before tuning and retain the full search path. If an L-curve is used, record the candidate parameter range and corner rule rather than selecting a visually preferred point after viewing final performance. These rules make parameter choice auditable and expose ambiguity when multiple choices are defensible.

When regularization choices produce materially different fields but similar forward fits, report the range as unresolved model/regularization sensitivity. Do not average the reconstructions unless an independently justified model defines that average. If the target is not resolved at the observation scale, report only the supported coarse quantity or abstain from a parameter-level claim.

## Split and benchmark interpretation

Keep the observations used to construct the inverse input distinct from an external benchmark used to evaluate recovery. A benchmark derived from the same acquisition may share calibration, preprocessing, labels, or selection and is not automatically independent. Trace each record to its original subject, instrument, acquisition, and release before declaring a validation split independent.

For learned inverses, group by the source of near duplicates, such as subject, acquisition, time, site, or molecular structure. For tomographic or imaging data, neighboring coordinates may be strongly dependent; random coordinate holdout tests interpolation within an acquisition, not generalization to a new acquisition. State which estimand each split measures.

Do not use the reconstruction observations as an external accuracy target unless an independent truth measurement or justified reference exists; otherwise report forward fit and its limitations rather than recovery error.

Report recovery and forward-fit metrics together with units, denominators, and the evaluation population. A good forward fit with poor truth error can indicate non-identifiability or model flexibility; good synthetic truth error under a matched simulator can conceal inverse crime. Preserve both positive and failed synthetic cases and explain which conclusion each supports.

## Sources

- Per Christian Hansen, *Discrete Inverse Problems: Insight and Algorithms*, Society for Industrial and Applied Mathematics, 2010: discrete ill-posedness, regularization, and parameter-choice methods.
- Heinz W. Engl, Martin Hanke, and Andreas Neubauer, *Regularization of Inverse Problems*, Kluwer Academic Publishers, 1996: regularization theory and stability of inverse problems.
