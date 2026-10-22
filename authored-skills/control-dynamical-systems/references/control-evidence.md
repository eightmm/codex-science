# Control and dynamical systems evidence

## Claim semantics

- **Rank test:** controllability/observability rank is a finite-precision calculation on a stated realization. A rank result near tolerance is unresolved; report singular values and scaling. Stabilizability/detectability can hold even when full controllability/observability does not, so check that every uncontrollable mode is stable (stabilizability) and every unobservable mode is stable (detectability), for example with the PBH test on the unstable eigenvalues.
- **Stability:** poles/eigenvalues establish model stability only for the declared linear model. Nonlinear local stability is restricted to a neighborhood where linearization is valid. A Lyapunov candidate yields a guarantee only when the required definiteness, derivative/difference inequalities, domain, and invariance conditions are proved.
- **Stability margin:** frequency-domain or disk margins describe the stated loop representation and perturbation convention; they do not cover unmodeled uncertainty outside that set.
- **Robustness:** distinguish a sampled uncertainty sweep from a robust guarantee. A guarantee requires a valid uncertainty set and a method whose theorem covers that set.
- **Simulation:** a simulated response is conditional on model, initial state, input, numerical method, and tested cases. It does not establish hardware safety or a universal bound.
- **Implementation behavior:** a sampled implementation claim requires actual sample/hold, intersample, quantization, delay, saturation, and scheduling assumptions. Continuous-time design alone does not verify embedded behavior.

## Source dependencies and independence

Record plant source and version, identification data and conditions, state coordinates, units, controller code/version, parameter estimates, uncertainty-set construction, discretization method, sample period, numerical library version, and solver tolerances. Pin software releases or commits when calculations depend on them.

Plant identification and controller evaluation are dependent when they reuse the same trajectories or disturbance realizations. Repeated simulation with one fitted model is not independent plant validation. Record shared data, preprocessing, model structure, parameter priors, and code paths. Hardware tests are distinct evidence from simulation, but repeated tests under one operating condition do not cover untested conditions.

## Uncertainty

Separate parameter uncertainty, unmodeled dynamics, disturbance/noise, sensor and actuator limits, numerical conditioning, and measurement uncertainty. State whether the reported envelope is deterministic, probabilistic, sampled, or theorem-backed. Retain the uncertainty set, its source, and failures. Do not describe Monte Carlo extrema as worst-case bounds unless the sampling covers a proven bounded set.

## Controls and sanity checks

- Verify units, sign conventions, equilibrium, open-loop poles, and closed-loop feedback polarity before evaluating response.
- Compare controllability/observability matrices with an independent staircase or PBH-style test when rank is material and conditioning permits; verify expected modes on a canonical low-order model.
- Check a known stable and unstable plant/controller pair for the selected pole or Lyapunov implementation.
- Test zero input, zero disturbance, and equilibrium initialization for unintended drift; test saturation and actuator-rate limits to expose windup or infeasibility.
- Confirm discrete behavior against the declared sample-and-hold model and inspect intersample excursions, not only sampled values.
- For a robustness claim, include uncertainty-set boundary cases and a nominal baseline; state if the set was sampled rather than exhaustively or analytically covered.

## Sensitivity analyses

Vary model parameters over their justified range, plant order and neglected modes, sampling period, computation delay, sensor noise, actuator limits, initial conditions, uncertainty structure, and numerical scaling/tolerance. A result is fragile when rank changes under plausible scaling/tolerance, stability is lost within the stated uncertainty set, constraint violations appear under small perturbations, or continuous and discrete responses change the conclusion. Report worst observed cases and whether the set coverage supports a bound.

## Applicability domain

Linear tests apply to the chosen finite-dimensional realization. Linearized nonlinear conclusions apply only near the operating point and where neglected nonlinearities remain controlled. Robustness conclusions do not extend beyond the uncertainty set. Simulations do not establish hardware safety; physical systems with unmodeled delay, saturation, mode switching, or changing dynamics require staged validation and independent safety controls.

## Common failure modes and detection

- **False rank from poor scaling or tolerance:** inspect singular values, rescale states, and compare a structurally appropriate test.
- **Full rank mistaken for practical controllability:** examine singular-value conditioning and required input magnitude.
- **Pole stability mistaken for nonlinear/global stability:** state the linearization region or verify Lyapunov conditions on a declared domain.
- **Nominal margin mistaken for robustness:** specify perturbation model and evaluate the complete declared set.
- **Monte Carlo mistaken for worst case:** distinguish sampled results from a bound; add boundary/adversarial cases or analytical certification.
- **Continuous model mistaken for implementation:** include sampling, delay, quantization, saturation, and intersample analysis.
- **Simulation mistaken for deployment evidence:** require staged hardware validation, independent safety limits, and failure handling.

## Sources

Khalil, *Nonlinear Systems*, 3rd ed., 2002, supports nonlinear stability, Lyapunov, and robustness analysis. Boyd and Vandenberghe, *Introduction to Applied Linear Algebra: Vectors, Matrices, and Least Squares*, 2018, supports linear algebra and numerical conditioning concepts; it is not a control-safety authority. Interpretations remain conditional on the cited model and theorem assumptions.

## Analysis record

Keep plant, controller, estimator, reference, disturbance, and uncertainty models as separately identified objects. Record state coordinates, units, equilibrium, causal assumptions, transfer-function realization, and whether the model is physical, identified, reduced-order, or linearized. Model reduction can remove weakly observable modes that still matter for internal stability or actuator effort.

For pole and margin calculations, report the loop break convention, closed-loop configuration, numerical precision, and the uncertainty perturbation definition. For Lyapunov arguments, retain the candidate function, derivative or difference expression, positivity domain, and invariance argument; a computed matrix inequality is evidence only if definiteness and rounding tolerances are controlled.

For simulations, declare initial conditions, reference and disturbance profiles, sample timing, integration scheme, tolerances, and scenario-selection rationale before comparing controller performance. Report transient metrics and steady-state error separately. Monte Carlo results should include seed policy, sample count, distribution, and observed failure count; structured uncertainty results should state which combinations were actually tested.

Hardware-facing plans should name independent safety interlocks, hard limits, abort criteria, and staged test conditions. These safeguards are part of the deployment boundary and do not follow from a stable simulation. Missing actuator limits or an unspecified safe operating region makes a deployment recommendation unavailable.

## Guarantee checklist

Before calling a result a guarantee, state the theorem or certification method, all hypotheses, the exact model class and domain, and how numerical rounding or solver tolerances affect the inequalities. A Lyapunov function checked on a grid is a sampled check unless interpolation or interval bounds establish the condition between grid points.

Before interpreting a stability margin, state whether the result covers additive or multiplicative perturbations, structured or unstructured uncertainty, and which feedback channels can vary. A margin computed for one loop break does not automatically guarantee robustness to every plant/controller perturbation.

Before claiming robust performance, report the objective and constraints tested at each uncertainty realization and distinguish parameter extremes from dynamic uncertainty. If only finitely many samples were evaluated, label the result as observed coverage and retain the sampling method and seed.

## Model mismatch record

State which phenomena the model omits, including neglected flexible modes, friction, hysteresis, actuator dynamics, delays, saturation, changing load, and sensor filtering where relevant. Connect each omitted effect to an uncertainty bound, a dedicated test, or an explicit limitation.

When identification is used, report excitation conditions and the operating range represented by the data. A well-fitted model on one trajectory may not identify all internal modes and does not support extrapolation to unexcited regimes. Repeat design checks across plausible parameter fits when fit uncertainty could alter stability or constraints.

Keep nominal performance, robust performance, and safety claims in separate rows. State the metric and horizon for each comparison; do not combine transient quality, stability, and hardware risk into one aggregate score.
