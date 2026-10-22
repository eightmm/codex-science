# Nonlinear dynamics evidence

## Claim semantics

Assign each claim by its mathematical scope and diagnostic strength:

- **Numerical trajectory:** a solver produced a finite path for specified equations, initial data, parameters, and numerical settings. This does not establish long-time behavior.
- **Fixed point and local linear stability:** a root of the vector field or map is a candidate until its residual and existence assumptions are checked. Eigenvalues classify the linearized system away from marginal cases; nonlinear stability needs additional analysis when linearization is inconclusive.
- **Bifurcation type:** identify a local type only when the critical eigenvalue crossing, nondegeneracy conditions, and local branch/stability pattern match the corresponding normal form. A parameter sweep can locate candidates, not prove a global bifurcation diagram.
- **Lyapunov exponent:** report finite-time estimates separately from a converged asymptotic estimate. A positive estimate supports sensitive dynamics only within the tested model, orbit, duration, tangent method, and numerical resolution; it does not alone prove chaos.
- **Poincare section or return map:** a sampled geometric diagnostic depends on section orientation, crossing direction, event precision, and invariant-set assumptions.
- **Attractor and dimension:** distinguish an observed bounded invariant-looking set from a proven attractor. Dimension estimates are estimator- and data-range-dependent, not intrinsic proof from a finite sample.
- **Shadowing:** state the theorem and hyperbolicity or expansivity assumptions if invoking shadowing. Finite numerical closeness does not show a computed path shadows an exact orbit indefinitely.

## Sources, dependence, and independence

Record the equation/map version, parameter source, units, initial-condition source, solver and library versions, precision, tolerances, step controls, event handling, and analysis code revision. Pin mutable software releases or commits. Preserve random seeds and noise-generation procedure for observed or stochastic data.

Two solvers are not independent checks if they share the same discretization, event interpolation, generated data, or copied implementation. Record common Jacobian code, libraries, parameter fits, preprocessing, and data windows. A parameter sweep reuses one model and is not independent replication. Separate experimental observations from model-generated trajectories and from resampled surrogates.

## Uncertainty

Carry parameter and initial-condition uncertainty separately from solver error, finite-time variability, observation noise, and estimator uncertainty. Report Lyapunov estimates by time window and ensemble where available, with method and uncertainty interval or an explicit reason none is defensible. Retain failed fits, rejected transients, and nonconvergent estimates. Do not collapse uncertainty sources into a single unlabeled error bar.

## Domain-specific controls

- Check a stable fixed point and a known periodic orbit when the implementation permits; compare observed rates or periods with analytic linearization or a high-accuracy reference.
- For a chaos diagnostic, test a regular system expected to have nonpositive largest exponent and verify that finite-time estimates do not spuriously stay positive as duration and precision increase.
- Compare forward/backward integration only where the equations and integrator make reversal meaningful; otherwise use invariant, symmetry, or conserved-quantity checks suited to the model.
- Check event counts and section crossings against a simple periodic reference to detect missed or duplicated events.
- Use shuffled or phase-randomized surrogates only as explicit null controls for data-based claims; preserve the tested statistic and surrogate-generation assumptions.

## Sensitivity analysis

Vary integrator family, maximum step, tolerance, precision, transient cutoff, total integration duration, section location/direction, interpolation rule, initial condition, parameter uncertainty, sampling interval, and Lyapunov renormalization interval. A classification is fragile if the sign or qualitative regime changes across plausible settings, if exponent estimates drift with longer windows, if a bifurcation type depends on an unresolved near-zero eigenvalue, or if the observed set/dimension changes materially with sampling or fit range. Report those changes; do not select only the favorable setting.

## Applicability domain

These diagnostics address deterministic finite-dimensional ODEs/maps or explicitly specified data models. Stochastic forcing, delay equations, hybrid events, partial observations, nonstationary parameters, high-dimensional systems, and noisy finite records require methods whose assumptions match those settings. Bounded trajectories need not be attractors. A numerical attractor does not establish the physical model's adequacy.

## Common failure modes and detection

- **Transient mistaken for asymptotic regime:** repeat with longer transients and windows; compare segment-wise diagnostics.
- **Numerical instability mistaken for chaos:** vary step size, method, precision, and tolerances; check invariants and boundedness.
- **Finite-time exponent mistaken for asymptotic exponent:** report window dependence and convergence; retain sign changes.
- **Nearby-orbit divergence mistaken for chaos:** test tangent-based exponents and regular-system controls; direct trajectories also separate under ordinary numerical error.
- **False bifurcation label:** inspect eigenvalue crossing and nondegeneracy conditions, then verify branch structure on both sides.
- **Aliased or event-biased Poincare structure:** vary step/event tolerances and section definition; audit crossing counts.
- **Overinterpreted dimension:** vary data length, noise treatment, embedding, and scaling interval; report estimator instability.
- **Unjustified shadowing:** identify applicable hyperbolicity conditions or restrict the conclusion to finite-time numerical agreement.

## Sources

Strogatz, *Nonlinear Dynamics and Chaos: With Applications to Physics, Biology, Chemistry, and Engineering*, 2nd ed., 2015, supports qualitative nonlinear dynamics, bifurcations, and chaos concepts. Ott, *Chaos in Dynamical Systems*, 2nd ed., 2002, supports dynamical diagnostics and chaos theory. Neither source makes a finite computation a proof; the claim boundaries above are methodological limits.

## Practical analysis record

For every computed object, retain the equation or map identifier, parameters, units, initial state or ensemble, solver family, step-size control, tolerance, precision, and software release. Record how equilibria were found, how Jacobians were computed, and whether eigenvalue classifications are separated from nonlinear conclusions.

For a continuation or sweep, retain the full parameter grid or branch continuation settings, including direction, initial branch, failed points, and adaptive steps. A coarse sweep can skip narrow branches or folds; refine where branch curvature or stability changes rapidly. If using a local normal form, list nondegeneracy assumptions and the parameter neighborhood where the approximation is expected to apply.

For observed time series, state sampling frequency, observation window, missingness, detrending, filtering, embedding choices, and noise model. Filtering and embedding can create or erase apparent recurrence. A deterministic model fit to finite observations is a hypothesis about the generator, not an observation of deterministic chaos.

The evidence table should distinguish computed object, tested property, supporting diagnostic, control result, sensitivity result, and residual limitation. Include units and scales for residuals, the number of retained samples, the transient exclusion rule, and any selected scaling interval. Preserve alternative interpretations such as stochastic excitation, quasiperiodicity, intermittency, and nonstationarity when the evidence does not discriminate them.

## Classification checks

For continuous-time fixed points, use the Jacobian spectrum only for hyperbolic equilibria; eigenvalues on the imaginary axis leave linearization inconclusive without additional analysis. For maps, use the unit circle as the corresponding boundary. Report the characteristic scale used to call an eigenvalue “near” the boundary instead of silently rounding it into a stable or unstable class.

For time series diagnostics, document the observable and its relation to the full state. A scalar measurement can hide unstable directions or mix multiple modes. When comparing Lyapunov estimates from data and model trajectories, keep the methods and evidential claims separate because data reconstruction adds embedding and noise assumptions.

For dimension estimates, report the estimator, embedding dimension, delay or coordinate choice, sample count, and candidate scaling interval. If no stable scaling interval exists across plausible choices, classify the estimate as inconclusive. Do not use a dimension estimate alone as a chaos test.

For every chaos classification, show which diagnostics agree and which remain ambiguous. Lyapunov behavior, recurrence geometry, spectra, and entropy estimates may share data and preprocessing, so agreement does not make them independent. State whether each diagnostic came from equations, simulated trajectories, or measured observations.

When evidence conflicts, prioritize the failure checks and narrow the claim. A positive finite-time exponent paired with step-size-dependent boundedness, for example, supports numerical fragility rather than a robust chaos classification. Record the unresolved alternative and a concrete observation that could distinguish it.

## Initial-condition sensitivity versus numerical error

Sensitivity to initial conditions is a property of the specified dynamics, assessed through tangent evolution or controlled nearby initial states under a converged numerical method. Numerical error is introduced by finite precision, truncation, interpolation, and solver tolerances. Nearby orbit separation alone cannot distinguish them because numerical perturbations also act as initial perturbations.

Compare tangent-based growth with direct nearby-state runs while independently varying step size, method, precision, and solver tolerance. If the estimated growth rate or qualitative regime tracks numerical settings, report the evidence as unresolved or numerical-sensitive. If direct paths diverge but the tangent estimate and diagnostics remain stable under refinement, report finite-resolution support for sensitivity, not a proof of infinite-time chaos.
