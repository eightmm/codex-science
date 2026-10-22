# Thermodynamic Evidence and Validity

## Claim semantics

Assign one class to every material claim; a result can have a mathematical class and a separate empirical status.

- **Exact result:** follows algebraically from stated definitions and assumptions, without an approximation. Show the governing identities and conditions, such as equilibrium state-function differentials. Exactness does not validate the model against a physical system.
- **Controlled approximation:** names its dimensionless small parameter, truncation order, and regime. For example, a low-density expansion is controlled only where the omitted higher-density terms are negligible for the requested accuracy. Report the retained order and a bound or estimate for omitted terms when available.
- **Numerical result:** comes from a specified numerical method and finite precision. Report solver/version, tolerances, residuals or normalization error, and convergence under refinement or an independent method. A converged calculation does not bound model error.
- **Heuristic estimate:** uses a scaling argument, analogy, closure, or uncontrolled simplification without a demonstrated error order. Label it as an estimate and do not state it as a precise prediction.

Record claim status as `supported`, `contradicted`, `inconclusive`, or `unavailable`. A consistency check supports internal coherence only; it does not establish empirical agreement.

## Source dependencies and independence

- Record the source, edition/revision, access date when relevant, and exact table, equation, or dataset used. Preserve the source version and the derivation inputs with the result.
- Treat multiple tables, summaries, or calculations copied from one equation of state, experiment, or source dataset as dependent evidence. Shared measurements, fitted parameters, calibration, or preprocessing also create dependence.
- Distinguish an independent derivation from an independent physical measurement. Recomputing the same partition sum by another script tests implementation but adds no new physical evidence.
- For statistical mechanics, state which microstates and conserved quantities define the ensemble. Do not count a change of ensemble as independent replication of the same underlying system.
- Compare ensembles only with their finite-size and thermodynamic-limit conditions stated. Ensemble equivalence may fail for small systems, long-range interactions, phase coexistence, or constraints that remain consequential.

## Uncertainty and reporting

- Separate uncertainty in measured inputs, uncertain model parameters, numerical error, approximation/truncation error, and structural model discrepancy.
- Propagate input and parameter uncertainty through derived observables when a probability model is justified. Otherwise report bounded scenarios or a sensitivity range rather than inventing a probability distribution.
- Preserve covariance when shared measurements or fitted parameters affect multiple outputs. Do not combine dependent values as if independent.
- State the reference state and convention for energy and entropy where relevant. Report units, sign convention, precision, and the assumptions behind any uncertainty interval.
- For fluctuations, state whether the reported quantity is a variance, standard deviation, or response coefficient and derive it under the same ensemble and normalization convention.
- Keep failed normalization, unstable equilibrium, phase ambiguity, and unavailable parameters explicit; do not replace them with a plausible default.

## Domain controls

Choose controls that can expose algebraic, sign, ensemble, and model mistakes.

Potential selection follows the controlled variables, not convenience:

- Use internal energy when entropy, volume, and composition are the natural fixed variables for an isolated description.
- Use enthalpy when pressure is controlled and the relevant state variables make it the appropriate potential.
- Use Helmholtz free energy for fixed temperature and volume, and Gibbs free energy for fixed temperature and pressure, subject to the declared composition and constraints.
- State any Legendre transform and its independent variables. Do not compare minima of potentials under incompatible constraints.
- For an open system include chemical work and chemical potentials for exchanged species; a closed-system balance cannot silently stand in for it.

- **Units and signs:** check dimensions in every balance and potential; verify heat/work signs against the declared convention. Use absolute temperature in thermodynamic identities.
- **First-law control:** for a closed cycle, the net internal-energy change is zero and net heat plus work follows the chosen sign convention. For open systems include enthalpy transport and other energy fluxes.
- **Second-law control:** calculate entropy generation or the cycle Clausius sum with reservoir temperatures. A reversible cycle gives equality; an irreversible cycle obeys the inequality under the stated convention.
- **Limiting controls:** recover ideal-gas, dilute, noninteracting, zero-coupling, and large-system limits only where the model assumptions make those limits meaningful.
- **Symmetry and normalization:** verify permutation or spatial symmetries that the model claims, and check that the probability measure sums or integrates to one.
- **Stability control:** check convexity/concavity of the relevant potential, positive response functions where required by the declared stable equilibrium, and phase coexistence conditions.
- **Negative controls:** deliberately reverse a heat/work sign, violate normalization, or use an incompatible ensemble in a small known case; the workflow should detect the resulting balance, probability, or limit failure.
- Record each control, expected behavior, observed value, tolerance, and pass/fail rationale. A failed control makes the affected claim inconclusive until resolved.
- For a cycle using heat reservoirs, calculate the signed sum of heat exchanged divided by each reservoir's absolute temperature under the declared heat convention; document how that expression maps to the Clausius inequality used.
- Check an exactly solvable or limiting case before interpreting a complicated model. The chosen control should test the same variables and constraints as the target problem.

## Sensitivity and fragility

Vary the assumptions that can change the selected state function or conclusion:

- equation of state, interaction model, and truncation order;
- ensemble, finite-size treatment, and conserved quantities;
- boundary conditions, reservoir values, and heat/work sign convention;
- parameter values, input uncertainty, and covariance;
- equilibrium assumption, phase selection, and metastable-state treatment.

Call a result fragile if a defensible change within the stated uncertainty or regime reverses its sign, phase/stability classification, ranking, or claim status, or changes the result by more than the declared error budget. Record the varied value, range, result change, and whether the variation remains physically admissible.

Where several assumptions vary together, use one-at-a-time checks to identify drivers, then evaluate joint scenarios for interactions. Report whether the qualitative regime is robust when numerical values shift within uncertainty. Do not treat an alternative ensemble as a sensitivity choice unless the physical constraints permit that ensemble.

## Applicability domain and failure modes

- Equilibrium thermodynamic potentials and Maxwell relations require well-defined equilibrium state functions. For non-equilibrium, driven, or finite-time processes use an explicitly justified extension; do not infer equilibrium solely from a steady-looking measurement.
- A thermodynamic-limit approximation can fail for small systems, interfaces, strong finite-size effects, or long-range interactions. State system size and the limit used.
- Ideal-gas and dilute expansions fail when interactions or density corrections are material. Detect this by estimating expansion terms or comparing with a suitable equation of state.
- A partition function can be mathematically defined yet omit relevant states or constraints. Check state-space coverage, degeneracies, normalization, and known limiting cases.
- A claimed phase equilibrium can be spurious if chemical potentials, pressure, or temperature are compared across inconsistent conventions. Recompute each potential from one consistent model and state.
- A cycle may appear to violate conservation because the system boundary omits matter flow, non-`pV` work, or a reservoir. Reconcile all fluxes before interpreting the discrepancy.
- A negative heat capacity or other unusual response is not automatically an error in every ensemble or finite system. Check the ensemble, constraints, and stability criterion before classifying it.
- A potential minimum is meaningful only under corresponding controlled variables and allowed variations. Detect a mismatch by recording the natural variables and constraints beside the minimization.
- Maxwell relations require differentiable state functions in a single equilibrium region. At phase boundaries or non-smooth transitions, check one-sided derivatives and coexistence conditions instead of applying a smooth identity blindly.
- Thermodynamic and statistical descriptions can disagree at finite size or under non-additive interactions. State the limiting procedure and identify which ensemble is physically realized.
- An equation-of-state fit can reproduce bulk data while leaving microscopic interactions unidentified. Do not infer a mechanism from fit quality alone.

## Sources

- Callen, *Thermodynamics and an Introduction to Thermostatistics*, 2nd edition, 1985: equilibrium thermodynamic potentials, stability, and thermodynamic relations.
- Gibbs, *Elementary Principles in Statistical Mechanics*, 1902: ensemble-based statistical mechanics and statistical foundations.
- Crowell, *Modern Physics*, author revision dated 2021 in the repository source register: thermodynamics and probability topics covered by that text. See [the textbook source register](../../../docs/TEXTBOOK_SOURCES.md) for provenance and license.
