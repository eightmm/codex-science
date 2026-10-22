# Asymptotic regime and verification guide

## Claim semantics

Assign one claim class to each claim and retain its basis:

- **Formal expansion:** coefficient equations satisfy the chosen ansatz order by order. This establishes algebraic consistency only; it does not establish convergence or a uniform error estimate.
- **Asymptotic approximation:** a remainder is smaller than the retained scale in a named limit and domain. State the scale relation and evidence; when no proof is available, say the asymptotic behavior was numerically tested rather than proved.
- **Matched approximation:** inner and outer forms agree in a specified common overlap and the composite does not double count the common part. Local agreement alone does not establish uniform accuracy elsewhere.
- **Numerically validated approximation:** an exact or independently computed reference is compared across multiple parameter values and a stated domain, with numerical reference error controlled. This supports only the sampled range and observables.
- **Proved estimate:** a stated theorem or derivation bounds the remainder under explicit hypotheses. Give those hypotheses and bound; never upgrade a residual check into this class.

Record a separate status for each claim: supported when evidence meets the stated criteria, contradicted when a declared check fails, inconclusive when evidence cannot distinguish the predicted regime, and unavailable when required assumptions or references are missing. Preserve separate claims for approximation construction, error behavior, and theorem-level conclusions.

## Source dependencies and independence

Record equation and boundary-data source, parameter definitions, scaling choices, coefficient derivation, numerical solver and precision, and exact/reference solution version. A numerical curve generated from the same truncated expansion is not an independent reference. If the reference and approximation share a discretization, solver, fitted parameter, or code path, record that dependency and do not count agreement as independent confirmation. Pin software releases or source revisions where implementation affects a comparison; retain the full parameter grid and failed points.

## Uncertainty and error reporting

Separate truncation scale, remainder bound, discretization error, solver tolerance, parameter/input uncertainty, roundoff, and model discrepancy. Report units or normalization, observable, parameter values, reference uncertainty, and comparison error. If the series is asymptotic and divergent, identify the least-term or other truncation rule used; describe optimal truncation as a practical estimate unless a bound is proved. Do not combine unlike uncertainties into one score without a justified model.

## Regime-specific controls

- **Regular perturbation:** check the limiting equation has the required order and satisfies the original boundary or initial data. A mismatch signals a singular limit.
- **Boundary/internal layers:** check the stretched coordinate resolves the layer and that inner and outer forms agree in an overlap. Evaluate the composite near both the layer and outer region.
- **Matched asymptotics:** verify the common part is subtracted once and compare composite error across the full claimed domain.
- **Multiple scales:** identify secular terms at each order and confirm the slow modulation removes them over the claimed long-time scale; compare phase and drift at increasing times.
- **WKB:** verify scale separation away from turning points; use a local connection treatment at a turning point and check amplitude/phase against an exact or numerical solution where available.
- **Laplace and stationary phase:** check dominant contributions, endpoint terms, contour accessibility, and saddle/branch assumptions; compare normalized integral values as the parameter varies.
- **General sanity checks:** substitute into the original equation, test boundary data and invariants, and check the zero-parameter limit against the reduced problem.

## Sensitivity analysis

Vary truncation order, matching point or overlap interval, stretched scale, small-parameter range, WKB turning-point distance, solver tolerance, and reference resolution as applicable. A conclusion is fragile if its sign, leading coefficient, claimed order, validity boundary, or interpretation changes under a reasonable variation or if numerical reference error is comparable to the claimed difference. Report the full variation and downgrade the claim when the regime cannot be separated.

## Applicability domain and failure detection

These procedures require an identifiable limiting process and a well-defined observable. They do not by themselves justify extrapolation to parameter values outside the tested or proved range, nonlinear stability, or a physical model's adequacy. Detect common failures by checking: lost boundary conditions in a nominally regular expansion; no overlap or inconsistent matching; unremoved secular growth; WKB use at an unresolved turning point; omitted endpoint or exponentially small contribution; nondecreasing or unexplained error against a reference; and inconsistent nondimensionalization. Stop or state the affected claim as inconclusive when a diagnostic fails.

## Sources

- Bender, Carl M., and Steven A. Orszag. *Advanced Mathematical Methods for Scientists and Engineers: Asymptotic Methods and Perturbation Theory*. 1978.
- Hinch, E. J. *Perturbation Methods*. 1991.

## Decision record for difficult regimes

For a regular-versus-singular decision, explicitly compare the order and boundary data of the limiting equation with the full problem. If the reduced operator loses order or cannot satisfy all boundary conditions, classify the perturbation as singular and identify the missing condition's layer before expanding. When no layer scale balances the dominant terms, keep the regime unresolved instead of forcing a matched construction.

For multiple scales, name the fast and slow variables, the order at which resonance occurs, and the solvability condition that removes secular growth. State the time scale over which the approximation is intended to remain accurate. Averaging or a bounded modulation equation is not evidence of long-time validity beyond that scale.

For divergent asymptotic series, record the coefficient or term behavior used to choose truncation. Compare truncation before and after the least term when possible. If no reliable least term is visible, report order sensitivity and avoid calling the chosen truncation optimal. A convergent power series and an asymptotic series answer different questions; report the evidence for whichever status is claimed.

## Comparison protocol

Use a parameter sequence that enters the claimed asymptotic regime and record the exact values, precision, solver method, and stopping criterion. Prefer a known exact solution where available; otherwise establish reference convergence separately by refinement or an independent method. Compare the same observable, norm, and spatial or temporal domain at every parameter value. Report absolute and scaled errors, since a decreasing raw error can mask a wrong predicted order.

A verification table should retain each parameter value, predicted leading scale, computed error, reference uncertainty, residual, and failed check. A missing reference, insufficient precision, or non-asymptotic parameter range prevents a numerical-validation claim even when a plot appears smooth.

Before stating an observed order, state the predictor for the error scale and compare ratios across at least several parameter values. If error differences are below reference uncertainty or machine precision, mark the order unresolved. Separate error plateau from exponential asymptotics, which may require observables or parameter ranges that expose the beyond-all-orders contribution.

Record the range over which the dominant balance was checked. If a different term ordering appears within the requested domain, split the answer into regimes or narrow the claim; do not present one expansion as uniform across a transition without a separate matched or uniform argument.

When the limiting observable is itself singular or changes scale, normalize it explicitly before comparing errors and state why that normalization is meaningful in each regime.
