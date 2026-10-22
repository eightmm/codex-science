# Verification and validation protocol

## Claim lanes and semantics

Assign separate claim IDs to code verification, solution verification,
experimental validation, and uncertainty statements. A code-verification claim
concerns whether the implementation solves the specified equations; evidence
includes analytic limits, unit tests, MMS, or independent formulations. A
solution-verification claim estimates numerical error for a specified execution;
it requires a refinement or error-estimation argument and retained run settings.
A validation claim concerns agreement of model predictions with independent
observations in a declared intended-use domain, including measurement
uncertainty. An uncertainty claim describes propagation or coverage under named
input, parameter, numerical, sampling and model-form assumptions. Do not transfer
support from one lane to another. Use `supported` only when lane-specific
criteria pass, `contradicted` for same-specificity conflicting evidence,
`inconclusive` for unresolved or inadequate evidence, and `unavailable` when a
required source or measurement cannot be obtained. State each claim's falsifier.

## Dependencies, provenance and independence

Pin source revision, build/compiler and relevant flags, solver and library
versions, hardware where numerically relevant, input files, meshes, boundary and
initial conditions, tolerances, precision, post-processing, and random seeds.
Hash inputs, code, environment records and outputs where available. Record
calibration data, validation data, shared samples, preprocessing and fitted
parameters separately. A second code path is not independent if it shares the
same discretization, library, algorithm, data transformation, or input data.
Calibration observations cannot also count as independent validation unless the
design explicitly accounts for reuse. Record source releases and transformations
so propagated records are not counted again as independent observations.

## Code verification and manufactured solutions

For a method of manufactured solutions (MMS), choose a sufficiently smooth
analytic field compatible with the equation form, substitute it into the
continuous equation to derive forcing and boundary/initial data, and solve that
manufactured problem. Verify the source terms independently, including signs,
units and boundary derivatives. Compare the numerical field to the exact field
using a declared norm, domain, quadrature and mesh. MMS tests implementation
consistency for the manufactured case; it does not validate the physical model
or guarantee accuracy for nonsmooth solutions, different regimes, or untested
code paths. Add conservation, symmetry, positivity, dimensional and analytic
limit checks where applicable.

## Grid and time-step convergence

Prespecify the quantity of interest, norm, expected order, refinement ratio,
acceptance threshold, and tolerable discretization uncertainty. Refine space and
time independently before a combined refinement so their contributions can be
separated. Preserve at least three systematically refined levels for an observed
order estimate. For scalar errors (e_i) at resolutions (h_i), the adjacent
order estimate is

```text
p_i = log(|e_i/e_(i+1)|) / log(h_i/h_(i+1))
```

An error sequence needs a trusted exact/reference solution or an explicitly
justified estimate. With nearly constant ratio (r=h_1/h_2), monotone
asymptotic error and an assumed order (p), Richardson extrapolation estimates
the zero-resolution value as (q_0 \approx q_2 +(q_2-q_1)/(r^p-1)), with
indices ordered coarse then fine. State the refinement ratio and assumptions.
Do not report observed order or extrapolation when errors are zero, nonmonotonic,
dominated by another error, or outside the asymptotic regime. Grid convergence
does not quantify model-form or input error.

## Controls, stability and conservation

Check equations, dimensions, initial and boundary conditions, residual norms,
conservation balances, symmetry, positivity, and stability constraints at every
relevant level. State normalization, sign and scale for each invariant. Include
simple analytic or limiting cases and an independent implementation or
formulation when feasible. A small residual is not a bound on forward error in
an ill-conditioned problem. A conserved quantity can coexist with a wrong
solution; controls are complementary and must not be collapsed into one pass
score. Preserve failures and negative results.

## Validation, uncertainty and sensitivity

Keep calibration and validation evidence separate. Compare predictions with
measurements of the same quantity at matched conditions; record measurement
uncertainty, sampling, instrument resolution, and any transformations. Report
residual structure and interval coverage or another justified metric, not only
point agreement. Carry numerical, input, parameter, sampling, experimental and
model-form uncertainty separately before any justified combination. Sensitivity
analysis varies uncertain inputs, parameters, mesh, time step, solver tolerance,
precision, model form and stochastic seed according to the claim. A result is
fragile when plausible variations cross the predeclared acceptance or decision
threshold, reverse a comparison, or materially widen the uncertainty beyond the
use tolerance. State the validated domain; extrapolation beyond sampled
conditions is a new claim.

## Failure modes and applicability domain

Detect non-asymptotic refinement from inconsistent or changing order; detect
time-step instability from growth or oscillation with reduced step; detect
boundary-condition errors from residual concentration or failed manufactured
boundary checks; detect conservation defects from balance drift; detect
overfitting from calibration success paired with held-out failure; detect
uncertainty undercoverage from residuals outside declared predictive intervals;
and detect false independence from shared code, samples or transformations.
Applicability is limited to tested equations, regimes, geometries, boundary
conditions, parameter ranges, data populations, and numerical configurations.
Stop or downgrade claims when required controls fail, measurement uncertainty is
missing, model discrepancy dominates, or the intended use lies outside this
domain.

## Sources

- P. J. Roache, *Verification and Validation in Computational Science and
  Engineering* (1998), for computational verification and validation practice.
- W. L. Oberkampf and C. J. Roy, *Verification and Validation in Scientific
  Computing* (2010), for evidence, uncertainty and model validation concepts.
- These frameworks organize evidence; they do not establish that a particular
  solver, model or validation dataset is adequate without the recorded study.
