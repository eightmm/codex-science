---
name: asymptotic-perturbation-methods
description: "Construct and validate asymptotic and perturbative approximations. Use for dominant balance, regular or singular perturbations, boundary layers, matched expansions, multiple scales, WKB, Laplace methods, and stationary phase."
license: MIT
---

# Asymptotic and Perturbation Methods

## Decision contract

State the limiting parameter, fixed quantities, nondimensional variables, observable, equation, domain, and region of validity before approximation. Identify the dominant balance before choosing a method. Assign each claim a class: formal expansion, asymptotic approximation, matched approximation, numerically validated approximation, or proved estimate. Record its status separately as supported, contradicted, inconclusive, or unavailable. A formal residual or matching calculation alone is not a convergence theorem or uniform error bound.

## Reference usage

Read [asymptotic-regime-guide.md](references/asymptotic-regime-guide.md) before choosing regular or singular perturbation, boundary-layer matching, multiple scales, WKB, truncation, or comparison across parameter values. It defines the regime tests, error labels, and failure criteria used by this workflow.

Preserve inputs, derivations or commands, environment, artifacts, hashes, failures, and null results with `$science-provenance`; use `$science-review` before material or consequential scientific conclusions.

## Workflow

1. **Define the limit.** Record the small or large parameter, fixed quantities, nondimensionalization, domain, observable, boundary and initial data, and intended parameter range; if these are underspecified, stop and mark the result unavailable.
2. **Test the balance.** Rank terms under the proposed scaling and identify where ordering changes; record distinguished limits and any boundary, initial, internal, or turning-point layers before selecting the expansion.
3. **Select a regime.** Use a regular expansion only if the limiting problem preserves required order and data; otherwise introduce stretched variables and record the singular mechanism and overlap region needed for matching.
4. **Construct and label the approximation.** Record coefficient equations, matching conditions, composite subtraction, multiple scales or averaging used to remove secular terms, and whether the result is formal, asymptotic, or supported by a proof.
5. **Check specialized hypotheses.** For WKB record smoothness, scale separation, turning points, and connection rules; for Laplace or stationary phase record dominant saddles, endpoints, Stokes or branch structure, and omitted exponentially small terms when they affect the observable.
6. **Estimate error.** Substitute into the original equation and record the residual, first neglected order, expected uniformity region, and whether any bound is proved; do not treat formal order as a rigorous bound. Track exponentially small terms when they control switching, instability, or boundary conditions.
7. **Verify.** Compare with an exact solution or a documented high-accuracy numerical reference at multiple decreasing parameter values; record scaled errors, observed trend, matching and boundary checks, invariants, phase, and long-time drift. Report where the approximation fails and whether the failure is algebraic, exponential, or numerical.
8. **Probe sensitivity and report.** Vary truncation order, parameter range, scaling, reference accuracy, and numerical resolution when relevant; record fragile changes, failed or null checks, claim status, limitations, and the smallest falsifiable next action.

## Outputs

Return one `asymptotic-evidence-v1` record with: limiting regime (`limit`); assumptions and domain (`assumptions`, `validity_domain`); claim class (`claim_class`: formal expansion, asymptotic approximation, matched approximation, numerically validated approximation, or proved estimate); claim identifier and status (`claim_id`, `claim_status`: supported, contradicted, inconclusive, or unavailable); method and expansion (`method`, `approximation`); error evidence (`residual`, `error_checks`, `error_bound_status`); reference comparisons (`reference_checks`); uncertainty and limitations (`uncertainty`, `limitations`); provenance and artifact identities (`provenance`, `artifact_paths`, `artifact_hashes`); failures and nulls (`failures`, `null_results`); and next action (`next_action`). Preserve derivations and execution details through `$science-provenance`; use `$science-review` for material claims.

## Boundaries

A formal series can be divergent and does not imply convergence. A small residual does not by itself bound solution error. Matching supports an approximation only in its stated overlap and validity regions. Stop or qualify conclusions when no controlled limit, matching region, error comparison, or parameter range is established; retain failures and null results.

## Source basis

Original synthesis informed by Lebl's differential-equations text and open asymptotic-methods references listed
in `../../docs/TEXTBOOK_SOURCES.md`.
