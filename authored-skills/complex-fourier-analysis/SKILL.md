---
name: complex-fourier-analysis
description: "Solve and verify complex-variable and Fourier-analysis problems. Use for analytic functions, contour integrals, residues, branch cuts, Fourier series and transforms, convolution, spectral methods, sampling, and dispersion relations."
license: MIT
---

# Complex and Fourier Analysis

## Decision contract

State the domain, function assumptions, contour orientation, branch cuts and principal-branch convention, Fourier normalization and sign convention, frequency variable, sampling model, and target quantity before computing. Separate an analytic derivation from a numerical or sampled-data validation claim. Select analytic, distributional, or discrete methods only when their hypotheses match the input.

## Reference usage

Read [complex-fourier-conventions.md](references/complex-fourier-conventions.md) before contour deformation, branch-dependent evaluation, Fourier-series or transform claims, or sampled-spectrum interpretation. It defines claim classes, contour conditions, normalization checks, and sampling controls.

Preserve inputs, conventions, derivations or commands, environment, artifacts, hashes, failures, and null results with `$science-provenance`; use `$science-review` before material or consequential scientific conclusions.

## Workflow

1. **Fix the problem and conventions.** Record domain, regularity/decay assumptions, singularities, branch and argument conventions, contour orientation, transform sign and normalization, units, sampling rate, and endpoint treatment; mark missing conventions unavailable.
2. **Choose the analytic route.** Invoke Cauchy or deformation results only after checking analyticity in the swept region; select a branch cut and record both boundary values when the integrand is multivalued.
3. **Check contour closure.** For residues, record poles and multiplicities, orientation, indentations, and arc contributions; use Jordan's lemma only when its decay and half-plane hypotheses hold for the actual exponential factor.
4. **Bookkeep the result.** Sum residues with orientation and branch contributions, then record the derivation and any independent differentiation or integration to a simpler known expression, limiting-case, or symbolic check.
5. **Choose the Fourier representation.** Distinguish periodic-series coefficients, continuous Fourier transform, and finite-sample DFT; state normalization and inverse convention before applying convolution, Parseval, or energy identities.
6. **Check convergence and sampling.** For series record endpoint behavior and Gibbs effects; for samples record Nyquist limit, aliasing risk, sample spacing, window, spectral leakage, and resolution before interpreting peaks.
7. **Verify.** Reconstruct or invert where defined, check conjugate symmetry for real signals and energy under the declared convention, and compare analytic values with numerical quadrature away from singularities or with controlled synthetic signals.
8. **Probe sensitivity and report.** Vary branch/contour choices where equivalent, truncation, window, record length, sample rate, and normalization as relevant; record fragile changes, failures, claim status, uncertainty, limitations, and next action.

## Outputs

Return one `complex-fourier-evidence-v1` record with: problem and assumptions (`problem`, `assumptions`); conventions (`branch_convention`, `contour_convention`, `fourier_convention`, `sampling_convention`); claim class (`claim_class`: formal derivation, analytic result, numerically checked result, or sampled-spectrum observation); claim identifier and status (`claim_id`, `claim_status`: supported, contradicted, inconclusive, or unavailable); method and derivation (`method`, `derivation`); convergence mode (`convergence_mode`: pointwise, almost everywhere, distributional, or norm); pole/branch or spectrum bookkeeping (`singularity_bookkeeping`, `spectrum_bookkeeping`); validation and sensitivity (`checks`, `sensitivity`); uncertainty and limitations (`uncertainty`, `limitations`); provenance and artifact identities (`provenance`, `artifact_paths`, `artifact_hashes`); failures and nulls (`failures`, `null_results`); and next action (`next_action`). Preserve derivations and execution details through `$science-provenance`; use `$science-review` for material claims.

## Boundaries

Do not change branch, endpoint, distribution, contour, or transform conventions silently. A Fourier peak is not proof of a unique physical mechanism. A finite DFT is not the continuous transform, and convergence or pointwise endpoint behavior requires its own hypotheses. Qualify results when analyticity, decay, convergence, or sampling assumptions fail; preserve failed and null checks.

## Source basis

Original synthesis informed by Lebl's openly licensed analysis and differential-equations texts recorded in
`../../docs/TEXTBOOK_SOURCES.md`.
