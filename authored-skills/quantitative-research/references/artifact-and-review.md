# Quantitative artifacts and review handoff

Read this file before packaging or reviewing a claim-bearing quantitative run.

## Artifact kinds

The artifact manifest recognizes these quantitative sidecars:

| Kind | Purpose |
| --- | --- |
| `research-design` | preregistration, experimental unit, estimand, stopping, multiplicity, missingness, exclusions |
| `statistical-analysis` | effect, interval, randomization test, unit counts, multiplicity output, seed |
| `mathematical-claim` | exact statement hash, domain, assumptions, quantifiers, status, permitted inference |
| `counterexample-search` | bounded domain, assumptions, evaluations, counterexample or exhaustion status |
| `proof-obligation-graph` | dependency-complete proof decomposition |
| `proof-receipt` | deductive, finite-exhaustion, formal-kernel, or computational-test receipt |
| `formal-proof-check` | bounded Lean preview/execution plus nested proof receipt |
| `numerical-verification` | refinement, order, residual, invariant, tolerance, precision, cross-method audit |
| `dimension-check` | variable units, equation dimensions, conversions, mismatches |
| `uncertainty-propagation` | input distributions, covariance, linear and Monte Carlo uncertainty |

Every file is included in the manifest with an exact SHA-256. Editing any sidecar invalidates the bundle until the manifest and affected reviews are regenerated.

## Cross-sidecar rules

Artifact review enforces:

- every statistical analysis references an included `research-design` by `design_id`;
- quantitative checks reference an included mathematical claim when mathematical claims are present;
- proof and counterexample receipts match the exact mathematical statement SHA-256;
- `proved-formal` requires a passed formal-kernel receipt;
- `proved-deductive` requires a passed deductive receipt and no unresolved obligations;
- `proved-finite` requires a passed finite-exhaustion receipt with `checker.exhaustive: true`;
- `disproved` requires a linked verified counterexample;
- computation-only receipts cannot promote a claim to `proved-*`;
- deterministic findings cannot coexist with an unsafe passed design or verification status;
- seeds, sample counts, solver settings, limitations, and hashes remain visible.

The manifest claim table remains a navigation layer. Mathematical truth status is controlled by `mathematical-claim` and linked receipts, not by prose in a report.

## Acceptance run

Run the deterministic end-to-end fixture:

```bash
uv run python scripts/run_quantitative_acceptance.py \
  examples/quantitative-research/input.json \
  /tmp/quantitative-run

uv run python scripts/validate_artifact.py \
  /tmp/quantitative-run/manifest.json \
  --review-output /tmp/quantitative-review.json \
  --require-passed-review
```

The fixture exercises:

- a clean preregistered two-group design;
- exact randomization inference and bootstrap interval;
- second-order manufactured convergence with residual and invariant thresholds;
- force and work dimensional equations plus unit conversion;
- covariance-aware linear and Monte Carlo uncertainty;
- a real counterexample to a false universal statement;
- exact finite exhaustion and a finite-proof receipt;
- statement hashes, proof obligations, artifact hashes, and cross-review.

It is a software and contract acceptance fixture. It is not an empirical scientific conclusion, general theorem benchmark, or validation of a domain-specific statistical model.

## Review procedure

1. Validate every artifact hash and sidecar schema with `scripts/validate_artifact.py`.
2. Confirm that research-design fields were fixed before outcome inspection.
3. Recompute experimental-unit counts from raw rows or source data.
4. Inspect effect sizes, intervals, missingness, multiplicity family, and alternative analyses before p-values.
5. Verify refinement sequence, errors, residuals, invariants, solver precision, and tolerances.
6. Recheck unit assignments and affine temperature conversions.
7. Verify covariance assumptions and Monte Carlo seed.
8. For a counterexample, confirm all hypotheses and the failed conclusion at the returned assignment.
9. For finite exhaustion, confirm the domain is exact, finite, complete, and identical to the claim.
10. For formal proof, compare the informal statement and the exact kernel-checked theorem.
11. Run an independent review packet when the result supports a material external decision.

## Completion rule

A quantitative run is complete only when:

- planned computations reached a terminal status;
- failures and exclusions are preserved;
- material claims have the narrowest supported status;
- artifact and reference hashes validate;
- blocking deterministic findings are resolved or the run is explicitly `findings` or `blocked`;
- `$science-review` passes for the declared scope;
- limitations identify what was not proved, measured, randomized, calibrated, or reproduced.

Do not hide a failed numerical level, missing unit, violated assumption, unsuccessful counterexample search, or formal proof failure merely to obtain a passing review.
