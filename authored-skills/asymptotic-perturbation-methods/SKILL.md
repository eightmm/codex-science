---
name: asymptotic-perturbation-methods
description: "Construct and validate asymptotic and perturbative approximations. Use for dominant balance, regular or singular perturbations, boundary layers, matched expansions, multiple scales, WKB, Laplace methods, and stationary phase."
license: MIT
---

# Asymptotic and Perturbation Methods

## Decision contract
State the limiting parameter, fixed quantities, observable, and region of validity. Choose a formal or numerical approximation only after identifying the dominant balance; distinguish a formal expansion from a proved error bound.

## Workflow
1. **Identify the limit.**
   State the small or large parameter, nondimensional variables, fixed quantities, domain, and observable. Rank
   terms by dominant balance and identify points where the ordering changes. An expansion is incomplete unless
   its limiting process and uniformity region are declared.

2. **Construct the approximation.**
   - Use a regular expansion only when the reduced problem preserves the needed order and boundary data.
   - For singular limits, locate boundary, initial, turning-point, or internal layers and introduce stretched scales.
   - Match inner and outer limits in a common overlap region, then form a composite approximation without double counting.
   - Use multiple scales or averaging to remove secular terms in long-time oscillatory problems.
   - For integrals and waves, identify stationary points, endpoints, saddles, and Stokes or branch structure.

3. **Estimate the error.**
   Retain the first neglected order, but do not equate formal order with a rigorous bound. Substitute the
   approximation into the original equation and compute its residual. Track exponentially small terms when they
   control switching, instability, or boundary conditions.

4. **Verify.**
   - Compare against an exact solution or high-accuracy numerical reference across decreasing parameter values.
   - Plot or tabulate scaled error to test the predicted convergence rate.
   - Check matching in the overlap and uniform accuracy near layers or turning points.
   - Test conservation laws, boundary conditions, phase, and long-time drift.
   - Report where the approximation fails and whether the failure is algebraic, exponential, or numerical.

5. **Deliver.**
   Give the distinguished limit, balances, expansion, matching, composite result, residual, observed error order,
   and validity region.

## Outputs
Return normalized inputs and assumptions; a machine-readable evidence or execution table; claim IDs marked supported, contradicted, inconclusive, or unavailable; uncertainty and limitations; and the smallest falsifiable next action. Record commands or derivations and artifact paths and hashes with `$science-provenance`; preserve failures and nulls. Run `$science-review` before material or consequential scientific conclusions.

## Boundaries
A formal series is not a convergence theorem or uniform error bound; stop or qualify the result when no controlled limit, overlap, or validity region is established.

## Source basis

Original synthesis informed by Lebl's differential-equations text and open asymptotic-methods references listed
in `../../docs/TEXTBOOK_SOURCES.md`.
