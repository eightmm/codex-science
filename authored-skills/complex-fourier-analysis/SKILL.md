---
name: complex-fourier-analysis
description: "Solve and verify complex-variable and Fourier-analysis problems. Use for analytic functions, contour integrals, residues, branch cuts, Fourier series and transforms, convolution, spectral methods, sampling, and dispersion relations."
license: MIT
---

# Complex and Fourier Analysis

## Decision contract
State the domain, function assumptions, contour and branch conventions, transform normalization, and target quantity. Select analytic, distributional, or sampled-data methods only when their hypotheses match the input.

## Workflow
1. **Fix conventions and domains.**
   State the complex domain, singularities, contour orientation, branch choices, transform normalization, frequency
   variable, and function space or decay assumptions. Mark endpoints and discontinuities. A branch-dependent
   answer without an explicit cut and argument convention is not complete.

2. **Choose the method.**
   - Establish analyticity before invoking Cauchy formulas or deforming a contour.
   - Use residues after classifying poles and confirming arc or indentation contributions.
   - Treat branch points and cuts directly; record values on both sides of the cut.
   - For Fourier series, check periodic extension, symmetry, smoothness, and endpoint convergence.
   - For transforms, verify integrability or use distributions explicitly; apply convolution and Parseval with matching conventions.
   - For sampled data, account for windowing, leakage, resolution, aliasing, and normalization.

3. **Verify.**
   - Parameterize contours and check orientation, residues, and contributions at infinity.
   - Differentiate or integrate the result when that recovers a simpler known expression.
   - Confirm conjugate symmetry for real signals and compare time- and frequency-domain energy.
   - Reconstruct the original signal and inspect error near discontinuities.
   - Check limiting cases and numerical quadrature against the analytic result away from singularities.

4. **Deliver.**
   Report conventions, analytic assumptions, derivation, singularity and branch handling, result, convergence mode,
   and numerical or symbolic checks.

## Outputs
Return normalized inputs and assumptions; a machine-readable evidence or execution table; claim IDs marked supported, contradicted, inconclusive, or unavailable; uncertainty and limitations; and the smallest falsifiable next action. Record commands or derivations and artifact paths and hashes with `$science-provenance`; preserve failures and nulls. Run `$science-review` before material or consequential scientific conclusions.

## Boundaries
Do not change branch, endpoint, distribution, or transform conventions silently; a Fourier peak is not proof of a unique physical mechanism. Qualify results when convergence or sampling assumptions fail.

## Source basis

Original synthesis informed by Lebl's openly licensed analysis and differential-equations texts recorded in
`../../docs/TEXTBOOK_SOURCES.md`.
