# Complex-variable and Fourier conventions guide

## Claim semantics

Classify claims by the operation that supports them:

- **Formal derivation:** algebraic manipulations are recorded under declared conventions, but required analytic hypotheses have not all been established.
- **Analytic result:** a theorem applies on the stated domain with its continuity, analyticity, integrability, or decay assumptions checked. State whether the result is pointwise, almost everywhere, distributional, or in a norm.
- **Numerically checked result:** an analytic expression is compared with quadrature, a symbolic identity, or an inverse/reconstruction check under stated precision and domain. This does not establish a general theorem.
- **Sampled-spectrum observation:** a property is observed in a finite, windowed data record. It supports only that record and acquisition setup, not a unique continuous signal or physical cause.

Mark claims supported, contradicted, inconclusive, or unavailable. Keep an integral evaluation, a Fourier identity, and a physical interpretation as distinct claims.

## Source dependencies and independence

Record the source function or data, parameter units, contour and branch convention, transform normalization/sign, time/frequency units, sample spacing, window, and algorithm/library version. A symbolic algebra check that shares the same expression or transform convention is not independent validation. If analytic and numerical calculations share a discretization, sampled input, or code, state that dependency. Pin releases and preserve input arrays or hashes when software behavior or sampled data affects the result.

## Uncertainty and error reporting

Separate analytic assumptions, truncation error, quadrature error, floating-point error, finite-record effects, measurement uncertainty, and model ambiguity. Report units and normalization for coefficients and spectra. A computed residue or transform may be exact under assumptions but input parameters may remain uncertain. A frequency-bin estimate has finite resolution; report that resolution and avoid unsupported precision. Retain uncertainty sources rather than collapsing them into a confidence label.

## Contour and branch controls

- Establish analyticity in the region swept by a contour deformation and identify excluded poles, cuts, and essential singularities.
- State positive orientation and any indentation convention; compute residues with pole order and sign explicitly.
- For a semicircle closure, inspect the exponential factor and arc length in the selected half-plane. Jordan's lemma requires the appropriate decay; it cannot be inferred from oscillation alone.
- For branch points, choose and draw or describe the cut, state the principal argument interval when used, and calculate upper/lower boundary values. Check small-circle and large-circle contributions before dropping them.
- Check a simple contour orientation or a known elementary integral to catch missing factors of `2 pi i` or sign reversals.

## Fourier and sampling controls

- State whether the object is a Fourier series, continuous transform, or finite DFT, with the sign, normalization, inverse, and frequency units. Do not transfer a Parseval or convolution factor across conventions without deriving it.
- For a Fourier series, state periodic extension and regularity. At a jump, the usual symmetric partial sums approach the midpoint under standard hypotheses and exhibit Gibbs overshoot; do not describe pointwise convergence as uniform convergence.
- For sampled data, compare the band of interest with the Nyquist frequency implied by sample spacing. If out-of-band content is uncontrolled, aliasing cannot be ruled out.
- Record the window and its coherent-gain or energy correction where amplitude or power is compared. Windowing reduces some leakage while changing resolution and amplitude response.
- Distinguish bin spacing from true resolving power; test synthetic tones or known signals and reconstruct the time series when possible.

## Sensitivity analysis

Vary contour radius/indentation or branch representation when mathematically equivalent; compare alternate residue bookkeeping or direct quadrature where applicable. For spectra, vary record length, window family, sample rate, truncation, and normalization. A result is fragile if its sign, residue, coefficient scale, spectral peak, or physical interpretation changes under a reasonable choice, or if a claimed feature lies below resolution or within leakage/aliasing uncertainty. Report the affected claim and downgrade it as needed.

## Applicability domain and failure detection

These methods require the stated analyticity, decay, integrability, periodicity, or sampling assumptions. Distributional identities do not automatically apply to pointwise functions. A finite DFT cannot establish a unique continuous transform or remove aliasing already present in acquisition. Detect common failures through a contour-boundary check, inverse transform, conjugate symmetry, Parseval consistency, direct quadrature, and synthetic sampled controls. Failure to close a contour, unresolved branch boundary, convention mismatch, or unstable peak interpretation requires an inconclusive or unavailable result.

## Sources

- Ablowitz, Mark J., and Athanassios S. Fokas. *Complex Variables: Introduction and Applications*. 2nd ed., 2003.
- Stein, Elias M., and Rami Shakarchi. *Fourier Analysis: An Introduction*. 2003.
- Stein, Elias M., and Rami Shakarchi. *Complex Analysis*. 2003.

## Calculation record and discriminating checks

For a residue calculation, keep a ledger with each singularity, whether it is inside the oriented contour, its residue contribution, any cut-bank integral, and each arc or indentation limit. Reversing orientation changes the contour integral sign. A missing contribution at infinity or at a branch endpoint is a common source of a plausible but incorrect closed form.

For a branch-sensitive function, record the principal argument interval and the selected branch of every logarithm or root. Equivalent contours must not cross a cut without accounting for the jump. Check boundary values from both sides; if they differ, include the jump contribution instead of treating the cut as an ordinary interior line.

For transforms, write the forward and inverse formulas next to the result. Verify a Gaussian or another known transform under the same convention before interpreting scale factors. Differentiate or integrate the result when this reduces it to a simpler known transform or integral. This check is useful only when boundary terms and interchange of operations are justified.

For DFT output, record whether the frequency array is shifted, one-sided, or two-sided and whether amplitudes are normalized by sample count, window gain, or energy. A peak's bin index alone does not give physical frequency without the sample interval. Reconstruct known synthetic tones, including one near a bin boundary, to expose leakage and scaling errors.

A failure table should identify the violated hypothesis, observed diagnostic, affected claim, and whether a revised convention or acquisition is required. Preserve original results when a corrected normalization or window is applied so readers can distinguish correction from source data.

When a Fourier series is used at a discontinuity, report the value assigned to the function there separately from the partial-sum limit. When a distribution is used, state the test-function space or operational setting. These distinctions prevent a valid generalized identity from being misreported as pointwise convergence.

If two conventions are compared, convert the full formula, including inverse factors and units, and verify one known function or signal in both. Agreement after a conversion is a consistency check; it does not establish assumptions omitted from either derivation.
