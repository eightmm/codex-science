# Relativistic Claims, Conventions, and Validity

## Claim semantics

Classify each material result separately from whether it is empirically supported.

- **Exact result:** follows from the stated geometry, field equations, initial/boundary data, and algebra without an approximation. State those premises; a solution of an assumed metric is not evidence that the metric describes a physical source.
- **Controlled approximation:** names the dimensionless expansion parameter, retained order, and regime. Weak-field, slow-motion, and post-Newtonian claims require a justified small potential relative to `c^2`, speed relative to `c`, or other declared ratio. State the first omitted order when known; do not imply precision beyond it.
- **Numerical result:** comes from a specified discretization, integrator, precision, and finite computation. Report constraint/residual behavior, step or mesh refinement, and an independent formulation or invariant check when feasible. Numerical convergence does not establish the physical model.
- **Heuristic estimate:** uses qualitative scaling, analogy, or an uncontrolled approximation without an established error order. Mark it as an estimate and do not present it as a precise prediction.

Use claim status `supported`, `contradicted`, `inconclusive`, or `unavailable`. Separate mathematical consequences, coordinate descriptions, local measurements, and empirical observations.

## Source dependencies and independence

- Record the source title, author, edition/revision, year when known, and exact equation, dataset, or observation. Pin software/library versions and metric/curvature conventions for computations.
- Multiple charts, coordinate transforms, or summaries derived from one metric solution are correlated representations, not independent evidence. Numerical implementations sharing equations, initial data, or code dependencies also do not provide fully independent confirmation.
- Distinguish an independent derivation of a solution from an independent measurement of the gravitational or kinematic system.
- If a measured source catalog or instrument calibration is reused, retain cohort/observation IDs, calibration version, and propagated records so repeated observations are not counted twice.
- A coordinate transformation can test representation invariance but cannot by itself validate the chosen spacetime model or source parameters.

## Uncertainty and reporting

- Separate uncertainty in measured initial data and source parameters, numerical integration/discretization error, approximation truncation, coordinate/parameterization choices, and model discrepancy.
- Propagate input covariance through derived observables when a justified statistical model exists. Otherwise report conditional ranges or scenarios; do not invent a probability law.
- Preserve correlations when several observables share a clock, distance estimate, calibration, or fitted mass. Report independent components and combined uncertainty only under stated assumptions.
- Name the observer and measurement procedure for local quantities such as proper time, locally measured energy, or acceleration. A coordinate component alone is not a measurement invariant.
- State sign convention, units, precision, and uncertainty for every reported quantity. Keep uncertainty in inferred source parameters separate from numerical precision.
- If convention or parameter uncertainty changes causal classification, horizon status, or the sign of an effect, report that conclusion as fragile or inconclusive.

## Domain controls

- **Convention ledger:** keep signature, curvature sign, units for `c` and `G`, and index rules together in the run record. When comparing published equations, translate their conventions before comparing signs.
- **Local measurement ledger:** state the observer frame and measurement operation for each locally reported energy, time, distance, or acceleration; identify whether an instrument model or idealized tetrad is assumed.
- **Metric/sign control:** verify signature, determinant/nondegeneracy in the chart, index contractions, and units of metric terms. Confirm that the interval sign matches the declared convention.
- **Causal control:** classify test vectors and trajectories as timelike, null, or spacelike from invariant norms before assigning physical meaning. Check normalization along integrated trajectories.
- **Transformation control:** transform tensors and observers together and compare scalar invariants or local measurements. A coordinate component is expected to change; invariant predictions should not.
- **Flat/Newtonian limits:** recover Minkowski behavior when curvature or gravitational field is removed, and Newtonian behavior only in a justified weak-field/slow-motion limit.
- **Symmetry/conservation control:** derive conserved quantities from stated Killing symmetries and check their numerical drift. Verify stress-energy conservation and field-equation constraints under the declared convention.
- **Curvature control:** compare curvature scalars or regular coordinates across suspected coordinate singularities; do not label a divergence in one chart a physical singularity without an invariant or regularity test.
- **Positive controls:** a known inertial Lorentz transformation should preserve interval and four-vector norm; a standard symmetric vacuum solution should satisfy its declared vacuum field equations in a regular region.
- **Negative controls:** intentionally flip the metric signature without updating equations, violate a normalization constraint, or perturb a tensor component without transforming indices; unit, norm, or constraint checks should detect the error.
- Record expected behavior, observed value, tolerance, and pass/fail rationale. Failed controls invalidate the affected claim until explained.
- For a collision or decay, check total four-momentum before and after and compare invariant mass in more than one frame when useful. Frame-dependent energy components need not match across observers.
- For a geodesic calculation, monitor normalization and constants of motion at intermediate points, not only at the endpoint; report maximum drift over the trajectory.
- For a field-equation solution, check the stated source-free or matter equations and constraints in a regular chart region, including the stress-energy convention used.

## Sensitivity and fragility

Vary parameters that can materially change the interpretation:

- metric or source parameters, initial data, observer worldline, and coordinate chart;
- signature, curvature convention, units, and gauge/coordinate conditions;
- weak-field or post-Newtonian expansion parameter and retained order;
- integration step, mesh, precision, and constraint-control tolerance;
- boundary conditions and the assumed stress-energy model.

Call a result fragile if defensible changes within the input uncertainty or approximation regime change the causal class, sign, qualitative behavior, or claim status, or exceed the declared truncation/numerical error. Record varied inputs and whether they remain physically admissible.

Test one convention or parameter at a time before joint perturbations so an apparent sign change can be traced to its cause. Compare coordinate-dependent values only after fixing both chart and observer. Record whether changing chart alters only components or also the claimed invariant/local observable.

## Applicability domain and failure modes

- A weak-field or post-Newtonian expansion does not apply near strong fields, relativistic velocities, or where omitted terms are comparable to retained terms. Estimate the expansion ratios before use.
- Coordinate components can diverge or vanish without a local observer measuring a divergence. Check scalars, regular coordinates, and tetrad/local measurements.
- A coordinate singularity can be confused with a curvature singularity. Compare invariants and construct a regular chart where possible.
- Geodesic classification can fail when velocity normalization or metric signature conventions are inconsistent. Check invariant norm and units before using coordinate velocities.
- Conservation drift may indicate integrator error, a missing symmetry, or incorrect field equations. Track invariant drift under step refinement and re-derive the symmetry conditions.
- A vacuum solution may be applied where matter or boundary effects are important. Compare the assumed stress-energy and scale with the problem domain.
- A chart may not cover an entire trajectory or spacetime region. Report excluded domains and switch charts only with explicit transformation checks.
- Purely Riemannian geometry has no inherent spacetime causal cones. Do not assign timelike/null/spacelike semantics unless the problem supplies a Lorentzian spacetime interpretation.
- A coordinate-time interval is not automatically a measured elapsed time. Integrate proper time along the stated observer worldline or identify the clock convention used.
- A perturbative result near a boundary, horizon, or singular chart can be nonuniform even when the nominal expansion parameter is small. Check the expansion across the full domain and report regions where terms cease to be ordered.
- Symbolic identities can hold because of an imposed ansatz while omitted equations or constraints remain unsatisfied. Evaluate the full declared system and constraints, not just the reduced equations.
- A coordinate transformation used as a check must be invertible on the region considered. Report chart overlap and excluded points; do not compare formulas outside their shared domain.

## Sources

- Einstein, “The Foundation of the General Theory of Relativity,” 1916: field equations and the general-relativistic framework.
- Crowell, *General Relativity*, repository-registered author-uploaded text: spacetime conventions, curvature, geodesics, field equations, and invariant checks. Publication year is not recorded in the repository source register; see [the textbook source register](../../../docs/TEXTBOOK_SOURCES.md).
- Crowell, *Modern Physics*, author revision dated 2021 in the repository source register: special relativity and relativistic kinematics. See [the textbook source register](../../../docs/TEXTBOOK_SOURCES.md).
