# Quantitative research review

Read this reference before passing a statistical, mathematical, numerical, dimensional, or uncertainty claim.

## Research design

Verify the exact question, experimental and observational units, outcome measurement, estimand, assignment, primary family, stopping, exclusions, missing-data strategy, sample-size rationale, sensitivity analyses, and whether the design was locked before outcomes.

Blocking examples:

- cells, wells, images, time points, or technical repeats counted as independent subjects;
- repeated outcome looks without a prespecified decision rule or alpha spending;
- multiple primary endpoints with no family or multiplicity strategy;
- post-hoc exclusions or transformations presented as confirmatory;
- observational causal claim without identification assumptions and confounding strategy;
- subjective outcome assessed without declared blinding;
- missingness assumptions incompatible with the analysis.

A deterministic design audit checks completeness and internal consistency. Review the scientific plausibility separately.

## Statistics

Reconstruct the independent-unit count. Confirm that the contrast direction and analysis population match the estimand. Check missing values, exclusions, paired completeness, duplicate aggregation, seed, interval method, exact versus Monte Carlo randomization, multiplicity family, effect size, standardized measure, and sensitivity analyses.

Do not pass a conclusion based only on a p-value. Check whether the effect and interval support the practical claim and whether randomization or exchangeability assumptions justify the test. `status: completed` is a computation status, not a scientific pass.

## Mathematics and proof

Check the exact statement hash, domain, quantifiers, assumptions, equality notion, and permitted inference.

- `tested` may use bounded symbolic or numerical checks.
- `proved-finite` needs exact finite exhaustive evidence.
- `proved-deductive` needs a passed deductive receipt and closed proof obligations.
- `proved-formal` needs a passed kernel receipt for the exact statement plus informal/formal correspondence review.
- `disproved` needs a verified counterexample satisfying every hypothesis.

Critical defects include computation presented as general proof, statement-hash mismatch, unresolved obligation behind a passed proof, admitted formal proof, unreviewed axiom, or a counterexample outside the domain.

## Numerical, units, and uncertainty

For numerical verification, check refinement order, at least three levels for convergence order, reference independence, error monotonicity, residual and invariant definitions, solver precision and tolerance, stable digits, and cross-method dependencies.

For dimensional checks, verify variable meanings and unit conventions before trusting algebra. A passed dimension receipt cannot validate coefficients, frames, boundary conditions, or constitutive laws.

For uncertainty propagation, check measurand, equation, input distributions, covariance provenance, positive semidefiniteness, seed, accepted and failed samples, linear/Monte-Carlo disagreement, calibration, and model discrepancy. Correlated inputs must not be declared independent merely for convenience.

## Reproduction

A record review verifies hashes and internal semantics. Reproduction requires an independent execution from recorded inputs and environment. For deterministic quantitative work, compare reproduced artifact hashes or documented numerical tolerances. For random work, reuse the declared seed first, then assess seed sensitivity separately.

## Pass rule

Pass only when:

- artifact hashes and schemas validate;
- the design supports the analysis and claim type;
- all blocking deterministic findings are resolved;
- evidence status is no stronger than the receipts;
- failed cases and exclusions are preserved;
- units, uncertainty, and validity boundaries are explicit;
- every material claim maps to the correct design, computation, proof, or counterexample receipt;
- the requested review mode was actually performed.

A passing review reduces unsupported inference; it does not itself prove the theorem, validate the model, or establish empirical truth.
