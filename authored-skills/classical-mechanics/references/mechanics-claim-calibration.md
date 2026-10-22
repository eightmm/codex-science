# Classical mechanics claim calibration

Load this reference for claim classification, model reduction, uncertainty, or verification decisions. Record the actual model and conditions; a textbook treatment supplies a method, not evidence that a real system satisfies its assumptions.

## Claim semantics

Assign each material claim exactly one primary class and link dependent claims by stable IDs.

- **Exact result:** algebraic identity, theorem consequence, or closed-form solution derived exactly from stated equations and boundary/initial data. State the premises and domain; exactness is conditional on the model and does not imply empirical truth.
- **Controlled approximation:** a truncated expansion or reduced equation with an explicit small parameter (for example, angle, amplitude, perturbation strength, or ratio of timescales), a justified ordering, and a derived or sourced error order. If the leading omitted term or uniformity domain is unknown, label it heuristic instead.
- **Numerical result:** a computed quantity with algorithm, precision, step/grid, stopping rule, and convergence evidence. Report stable digits only when refinement and independent checks support them; solver termination alone is not convergence evidence.
- **Heuristic estimate:** scaling, order-of-magnitude, or qualitative model judgment without a controlled remainder. State its intended precision and the assumptions that could reverse it.

Do not combine a conditional mathematical result with an empirical observation into one status. Use `supported` only for claims whose stated checks pass, `contradicted` for a check that conflicts under the frozen model, `inconclusive` when evidence cannot decide, and `unavailable` when required input or measurement is absent. A failed model check does not refute a physical hypothesis.

## Source dependencies and independence

For every measured or reused quantity record source, release/date, identifier, units, and transformation. Pin software/library and integrator versions when a numerical trajectory depends on them; preserve code/configuration hashes and floating-point precision.

Record shared initial conditions, calibration data, force laws, parameter fits, trajectory segments, and source datasets in a dependency graph. Reusing a fitted potential, initial state, or trajectory window is propagated evidence, not an independent replication. Analytic and numerical results are partly independent only when their derivations, data, and implementation paths do not share the relevant failure mode.

For constants or textbook-derived formulas record the named source and edition when a convention or approximation depends on it. Keep the reference frame, coordinate parameterization, and force-model version explicit across revisions.

## Uncertainty and claim status

Separate input/measurement uncertainty, parameter uncertainty, model discrepancy, approximation truncation, numerical discretization, iteration, and roundoff. Propagate quantitative input uncertainty through the calculation when the model supports it; otherwise give a qualitative limitation rather than an invented interval.

For a controlled approximation report the small parameter, retained order, estimated omitted order, and whether the estimate is uniform over the reported range. For numerical results report refinement sequence, invariant drift, residual scale, and variation across solver or precision when relevant. Preserve covariance and correlations where they affect the observable.

Attach uncertainty to the claim it qualifies. Report unresolved disagreement and failed runs; do not turn absence of detected drift into zero uncertainty or interpret a narrow numerical error bar as model validation.

## Controls and sanity checks

- **Dimensions and conventions:** reduce each equation to consistent base dimensions; verify coordinate, angle, sign, right-hand rule, and inertial versus rotating frame conventions. Check potential-energy zeros are not mistaken for observable energy differences.
- **Limiting cases:** recover static equilibrium, zero force, free motion, zero damping, small-angle motion, equal-mass exchange, and circular-orbit behavior when the equations imply them.
- **Symmetry and conservation:** derive momentum, angular momentum, and energy conservation from the stated translation, rotation, and time symmetries. A claimed conservation law must match external forces, torques, and explicit time dependence.
- **Constraint controls:** test constraint residuals and reaction forces; compare independent coordinates or formulations for a simple case.
- **Solver controls:** verify a known analytic orbit or oscillator and vary time step; compare a symplectic method when long-time Hamiltonian structure matters.

Record expected value or relation, tolerance rationale, observed result, and pass/fail status for each control. A violated control blocks the dependent claim until explained.

## Sensitivity analysis

Vary initial conditions and measured parameters within their uncertainty, damping/friction/contact laws, boundary conditions, and each approximation's controlling parameter. For simulations vary time step, solver family, precision, and event-handling tolerance. Include near-equilibrium, separatrix, resonance, and long-time cases when the conclusion depends on them.

Call a conclusion **fragile** if an admissible perturbation changes its sign, qualitative class, stability classification, conservation interpretation, or reported decision, or if it changes beyond the prespecified claim tolerance. Report the perturbation and the consequence. In chaotic systems compare distributions or finite-time observables, not pointwise long-horizon trajectories.

## Applicability domain

Classical point-particle and rigid-body models may fail at microscopic scales, relativistic speeds, deformable-body scales, unresolved contact or impact processes, or when forces and constitutive laws are not measured. Newtonian dynamics require speeds small relative to light speed; linear oscillations require a verified equilibrium and perturbations small enough for neglected nonlinear terms; perturbation theory requires the stated parameter to remain small in the domain used.

Ideal constraints, point masses, instantaneous impacts, Coulomb friction, and perfectly rigid bodies can create singular or nonunique dynamics. Long-time trajectories may be sensitive to tiny input or roundoff changes. Report where these limits matter; do not extrapolate a local approximation or finite simulation range without additional evidence.

## Common failure modes and detection

| Failure | Detection |
|---|---|
| Wrong frame or omitted fictitious force | Re-derive acceleration in the declared frame; compare inertial and rotating-frame balances in a simple limit. |
| Inconsistent signs, angles, or units | Dimensional audit and a one-dimensional or static sign check. |
| Hidden overconstraint or missing reaction | Count equations/unknowns and inspect constraint residuals. |
| Energy conservation claimed with explicit time dependence or dissipation | Check symmetry and power balance from external work and damping. |
| Perturbation or small-angle result used outside range | Sweep controlling parameter and compare with an untruncated or exact solution. |
| Impact/friction smoothed away by integrator | Compare event-resolved trajectories and check impulse/momentum balance. |
| Convergence mistaken for correctness | Compare analytic benchmark, step refinement, invariant drift, and a structurally distinct solver. |

## Recording a mechanics result

For an oscillator, record the potential, equilibrium, retained Taylor term, and dimensionless amplitude before calling the small-angle period a controlled approximation. State the first neglected term or identify the period as an estimate if no error order was derived. If integrating the trajectory, retain the initial state, integrator, time step, invariant drift, and event policy; do not merge the trajectory result with the model's analytic period claim.

For an orbit, identify the central-force assumption and conserved angular momentum before using an effective potential. A circular-orbit check applies only to a central potential and does not establish stability; perturb the radius and inspect the second variation or the linearized dynamics. If observations set the force law or initial data, retain their uncertainties and provenance separately from the mathematical derivation.

These examples show how to apply the classes and controls; they do not supply default parameter values or acceptance thresholds.

When reporting a stability conclusion, name the perturbation variable, time horizon, and criterion separating neutral from asymptotic stability. When reporting a trajectory, state whether uncertainty is pointwise, ensemble-based, or bounded over a finite horizon; these descriptions answer different questions.

## Sources

- John R. Taylor, *Classical Mechanics* (2005): Newtonian mechanics, oscillations, central forces, Lagrangian methods, and examples of approximations and conservation laws.
- Herbert Goldstein, Charles Poole, and John Safko, *Classical Mechanics*, 3rd ed. (2002): Lagrangian/Hamiltonian formulations, constraints, canonical structure, and perturbation methods.
- The workflow's open source basis and licensing are recorded in `../../../docs/TEXTBOOK_SOURCES.md`; it is not a parameter dataset or empirical validation source.
