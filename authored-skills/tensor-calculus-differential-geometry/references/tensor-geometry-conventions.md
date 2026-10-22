# Tensor geometry conventions and verification guide

## Claim semantics

Separate the kinds of result so component arithmetic cannot silently become a geometric theorem:

- **Component computation:** listed components follow from stated coordinates and conventions after index and algebra checks. This supports the calculation in that chart only.
- **Tensor identity:** a coordinate-independent equality is supported by a derivation respecting tensor types and transformation laws, or by a general proof. Checking a component in one chart is insufficient.
- **Curvature or invariant result:** the declared Riemann convention and all contractions are explicit, and the scalar or tensor is checked independently or through a valid identity.
- **Singularity classification:** chart degeneration is distinguished from physical curvature pathology. Invariant blow-up is evidence of curvature pathology; finite invariants alone do not prove extendibility or geodesic completeness.
- **Symbolically checked result:** a symbolic system reproduces selected components or contractions under a stated metric and convention. This is an implementation check, not independent proof unless the derivation is separately justified.

Mark claims supported, contradicted, inconclusive, or unavailable. Keep the component result, invariant interpretation, and physical conclusion as separate claims.

## Source dependencies and independence

Record the metric or geometric source, chart, coordinate ranges, signature, index convention, orientation, connection assumptions, Riemann definition, software and symbolic package versions, simplification rules, and any imported expressions. Two symbolic computations using the same generated Christoffel table are dependent checks. A coordinate transformation derived from the same code path does not independently validate that path. Record shared formulas, packages, and conventions; pin software versions when results depend on symbolic behavior.

## Uncertainty and reporting

Separate input metric/model uncertainty, chart-domain restrictions, algebraic or symbolic uncertainty, numerical evaluation error, and unresolved convention choices. Report units and coordinate range where components are interpreted numerically. A symbolic equality may be exact conditional on the supplied metric and conventions; it does not validate those inputs or physical assumptions. Preserve unevaluated or singular expressions and identify excluded points instead of silently simplifying them away.

## Convention and computation controls

- State whether the metric signature is mostly plus or mostly minus (or explicitly list signs), which indices are raised or lowered, and the summation range.
- Define the Christoffel formula and test symmetry in its lower pair only for a torsion-free connection. Check metric compatibility when Levi-Civita is assumed.
- Write the Riemann tensor definition, derivative order, and sign before computing; record Ricci contraction and scalar-curvature convention. Convert alternate conventions explicitly before comparing signs.
- Distinguish partial derivatives of components from covariant derivatives. Check the connection terms and free-index type in each derivative.
- Validate volume form/orientation and determinant sign on the chart domain. Check flat Cartesian or Euclidean cases and known symmetry identities.
- Independently derive selected Christoffel, curvature, and invariant expressions, preferably with a second symbolic implementation or a hand derivation; compare scalar contractions and transformed components at regular sample points.

## Singularity and chart controls

At a suspect coordinate locus, compute the chart Jacobian or metric determinant and determine whether the coordinate map degenerates. Evaluate curvature scalars or other suitable invariants using the same sign convention. If invariants remain finite, investigate extension in another regular chart and geodesic behavior; do not conclude regularity from one scalar alone. If an invariant diverges, state which invariant and limiting path show it and keep coordinate-domain assumptions explicit. A singular coordinate component by itself does not classify the underlying geometry.

## Sensitivity analysis

Repeat key calculations after explicitly converting to an alternate metric signature or Riemann sign convention, testing regular points in another chart, changing symbolic simplification order, and using an independent derivation for material expressions. A result is fragile if invariant signs or values, tensor symmetries, geodesic properties, or singularity classification change after a consistent convention conversion or independent check. Record discrepancies and downgrade affected claims rather than selecting the favorable output.

## Applicability domain and failure detection

The workflow assumes enough differentiability for the declared connection and curvature operations and a valid chart on the stated domain. A chart cannot support claims at points it excludes. Coordinate and frame components are representation-dependent; only correctly contracted or transformed objects support invariant statements. Detect common failures with free-index checks, lower-pair Christoffel symmetry where applicable, metric-compatibility residuals, Bianchi identities, flat-space controls, transformed invariants, and independent symbolic comparison. Unresolved convention, invalid chart, or inconsistent identities makes dependent claims unavailable or contradicted.

## Sources

- Carroll, Sean M. *Spacetime and Geometry: An Introduction to General Relativity*. 2004.
- Misner, Charles W., Kip S. Thorne, and John A. Wheeler. *Gravitation*. 1973.

## Derivation record and independent checks

For each derived object, retain the input metric, inverse, determinant, nonzero connection components, and declared coordinate ranges. Record symmetry reductions only after stating their geometric or algebraic basis. When using differential forms, define the coframe, exterior derivative, wedge ordering, and orientation so signs can be reconstructed; compare a form-based result with components when the claim depends on that sign.

An independent symbolic check should start from the metric rather than importing the first calculation's connection table. Compare selected Christoffel symbols, curvature components, Ricci contractions, and scalar invariants after converting conventions explicitly. Evaluate identities at generic regular points, not just symmetric points where terms vanish accidentally. Numerical sample agreement is a diagnostic and does not replace a symbolic identity or proof.

When changing signature or curvature convention, document the full conversion and recompute every affected contraction. A global sign flip is not always the only change when index positions or definitions differ. Never repair disagreement by selecting whichever convention matches an expected answer without tracing the definitions.

## Reporting a chart boundary

Name the chart and the exact locus excluded by its coordinate domain. If a second chart is used, provide the transformation and the overlapping regular region. State which invariants were examined and their limiting behavior. A finite set of scalar invariants is not automatically a complete classification for every geometry; if no extension or geodesic analysis was performed, leave regularity or completeness unresolved.

For covariant differentiation, expand at least one representative component to show the connection terms and verify the resulting index type. For geodesics, state the affine parameter and normalization; compare the conserved quantities with the metric symmetries only when those symmetries have been established.

Report whether a connection is assumed or derived and whether torsion is zero. If a non-Levi-Civita connection is used, do not invoke lower-index Christoffel symmetry or metric compatibility unless separately established for that connection.

For coordinate transformations, check that the Jacobian is nonsingular on the overlap and transform every free index with the correct Jacobian or inverse Jacobian factor.
