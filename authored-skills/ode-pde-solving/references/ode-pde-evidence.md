# ODE and PDE evidence contract

Use this reference to calibrate claims about differential equations. The equation, solution concept, data, domain, and observable define what a result can establish; a solver output alone is not a theorem.

## Claim semantics

Assign one claim class to each claim ID and keep the status vocabulary `supported`, `contradicted`, `inconclusive`, or `unavailable`.

- **Proven result:** give the exact theorem or derivation, hypotheses, domain, function space, regularity, initial/boundary conditions, and conclusion. Existence, uniqueness, and continuous dependence are separate properties. A formal solution or local theorem does not imply a global solution, uniqueness, or stability outside its hypotheses.
- **Numerically verified result:** give the discretization and solver, conditioning/stability limits, residual norm and scaling, boundary/initial-condition errors, and observed refinement evidence for the stated observable. Require at least two refinements for a comparison; use at least three levels before reporting an observed order. Call it finite numerical verification, not proof of the exact solution or asymptotic convergence.
- **Simulated estimate:** use only for a stochastic quantity computed by simulation; record the probability model, independent sampling unit or dependence structure, estimator, seed, sample size, and Monte Carlo standard error or interval. State separately any model uncertainty. A deterministic numerical trajectory is not a simulated estimate merely because it was computed.
- **Conjecture:** use when an assertion is plausible but its theorem hypotheses or numerical acceptance evidence are incomplete. State the falsifier and the next discriminating calculation; do not upgrade it because plots or solver output look stable.

Do not combine classes to hide the weaker link: if a theorem establishes existence but a numerical run estimates a particular observable, report those as distinct claims.

## Equation, source, and dependency record

For an ODE, specify the independent-variable interval, order, state variables, parameters, initial conditions, and regularity. For a boundary-value problem, specify the interval or domain and every boundary condition. For a PDE, give the spatial domain, time interval if applicable, equation type where meaningful, boundary geometry/data, initial data, compatibility conditions, and solution space (for example, classical or weak) at the level needed by the claim.

For a first-order IVP, distinguish a local existence interval from a global one and record any continuation or blow-up condition used. For a higher-order scalar equation, rewrite as a first-order system only after recording the state definition and transformed initial data. For a boundary-value problem, state whether existence or uniqueness depends on a parameter, eigenvalue, or compatibility condition.

For PDEs, note whether the boundary condition is Dirichlet, Neumann, Robin, periodic, or another declared form; state any corner or interface compatibility needed for the claimed regularity. If using a weak solution, specify the test space or at least the function-space result being invoked. Do not upgrade a weak-solution result to pointwise smoothness without a regularity argument.

Record source provenance for coefficients, forcing, geometry, and boundary/initial data, including release or revision, units, transformations, and missing values. Pin code, solver/library version, precision, tolerances, mesh/time-step rule, and environment. Mark shared code, discretizations, meshes, boundary implementations, coefficient sources, and preprocessing across purportedly independent solutions. Agreement that shares these dependencies is a consistency check, not independent confirmation.

Retain the exact mesh-generation and refinement rule, including how boundaries and singular points are represented. When coefficients or forcing come from measured or fitted data, retain the mapping from source records to solver inputs and report interpolation or extrapolation. A changed source revision or discretization is a changed evidence dependency even if the solver name stays constant.

## Uncertainty and well-posedness

Separate uncertainty in parameters/data, model form, exact-solution derivation, discretization, time integration, iterative solve, floating-point arithmetic, and stochastic sampling. For a numerical result, report the target observable and norm, conditioning or sensitivity where known, residual and scaling, refinement sequence, solver tolerances, and the difference between estimated numerical error and unquantified model error. Do not treat a small residual as a forward-error bound without a conditioning argument.

State the theorem's assumptions before claiming existence, uniqueness, or continuous dependence. For PDEs identify boundary and initial-data compatibility and the solution concept. If the applicable function-space or regularity assumptions are unknown, mark well-posedness unresolved and restrict the computed claim to the tested formulation.

Use one well-posedness claim per property when evidence differs: existence does not imply uniqueness, and uniqueness does not imply stability under perturbation. State whether stability means continuous dependence of the solution, stability of the numerical time-stepping method, or boundedness of a discrete operator; these are different claims.

## Domain-specific controls

- Use a closed-form solution when available and independently substitute it into the operator and all data.
- Use a manufactured solution by selecting a smooth target, deriving its forcing and compatible boundary/initial data, then checking whether the implementation recovers the target at the predicted rate.
- Check small or limiting cases: zero forcing, constant solutions, equilibrium, symmetry, parameter limits, and conservation or positivity invariants when the equation implies them.
- For temporal/spatial coupling, refine each source of error separately at least once; a simultaneous refinement can conceal cancellation.
- Compare a second method only after checking shared code, data, mesh, discretization, and boundary assumptions.

Controls can expose implementation errors but do not establish correctness for untested equations, geometries, or parameter ranges.

Choose controls before interpreting the target result. A manufactured forcing derived from an exact target tests operator and boundary implementation but may not reproduce the target equation's coefficient regularity or singular behavior. Preserve both the manufactured data and the derivation so the control is reproducible.

## Sensitivity and fragility

Vary solver tolerances and precision, time step, spatial mesh, stopping criteria, relevant parameters, and boundary/initial data within justified uncertainty. Predeclare the target observable and a meaningful error budget. Call the conclusion fragile if its claim status changes, the observable moves beyond that budget, the expected convergence regime disappears, or reported digits change under a reasonable perturbation. Report non-asymptotic levels and failed runs instead of selecting only favorable refinements.

For stiff ODEs, test whether stability restrictions or stiffness handling control the step sequence and result. For PDEs, test mesh and time-step refinement separately when practical and check boundary treatment and conservation/invariant behavior. Chaotic systems require horizon- and observable-specific sensitivity; trajectory divergence alone does not identify numerical error versus genuine dynamical sensitivity.

Record the perturbation magnitudes and the observable at each perturbation. If a solver changes its internal step or mesh adaptively, include accepted/rejected step behavior or mesh statistics needed to explain the comparison. When only one resolution or one parameter regime is feasible, label the sensitivity evidence incomplete rather than inferring robustness.

## Applicability and failure detection

Applicability is limited to the declared equation, coefficient/source versions, domain and geometry, data regularity, function space, parameter range, observable, and tested resolution and time horizon. A solver's success message does not widen that domain.

Report extrapolation beyond the tested parameter range or time horizon as an explicit limitation. A control using smooth data does not establish the same accuracy for discontinuous forcing or singular coefficients.

| Failure mode | Detection and response |
|---|---|
| Incompatible or incomplete initial/boundary data | Check compatibility conditions and residuals on each boundary; stop or mark the problem under-specified. |
| Singular point or solution outside assumed regularity | Inspect coefficient/domain singularities and regularity hypotheses; state a weaker solution concept or leave the claim unresolved. |
| Stiffness or unstable time stepping | Compare stability restrictions, step histories, and invariant behavior; use a suitable stiff method or reduce the claim. |
| Spurious convergence or cancellation | Inspect all levels, separate space/time refinement, compare an exact/manufactured/independent control, and report nonmonotonicity. |
| Small residual but inaccurate observable | Assess conditioning and forward sensitivity; report backward and forward evidence separately. |
| Boundary implementation error | Measure boundary error separately from interior residual and test a compatible manufactured solution. |
| Model discrepancy mistaken for solver error | Perturb coefficients, forcing, and boundary data within known uncertainty; keep model and numerical error lanes distinct. |
| Chaotic sensitivity mistaken for instability | Compare finite-horizon observables and perturbations; do not claim trajectory convergence beyond demonstrated sensitivity. |

Retain failed computations and unavailable source/data as evidence states. Do not substitute a different equation or geometry silently.

## Sources

- Jiří Lebl (2026), *Notes on Diffy Qs*, edition 6.11: ODE/PDE classification, solution methods, Fourier methods, and nonlinear dynamics.
- E. Süli and D. F. Mayers (2003), *An Introduction to Numerical Analysis*: error, stability, and convergence concepts for numerical methods.
- J. C. Butcher (2008), *Numerical Methods for Ordinary Differential Equations*, second edition: Runge–Kutta methods and stability considerations.

These sources inform method vocabulary; they do not validate a particular equation, dataset, implementation, or scientific interpretation.
