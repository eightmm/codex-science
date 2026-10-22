# Quantum mechanics claim calibration

Load this reference before classifying a quantum result, choosing a truncation, or interpreting an open-system or numerical calculation. Mathematical predictions are conditional on the Hilbert space, Hamiltonian, state preparation, measurement model, and evolution assumptions.

## Claim semantics

Assign every material conclusion a stable ID and one primary class; link predictions to the assumptions and calculations on which they depend.

- **Exact result:** identity, theorem consequence, or exact solution for the stated operator, domain, state, and boundary conditions. State degeneracy and domain assumptions. Exact solution of a model is not evidence that the model describes the experiment.
- **Controlled approximation:** perturbation, variational, semiclassical, adiabatic, rotating-wave, Born-Oppenheimer, or other approximation. State the small parameter or variational space, retained order, justified error order or bound, and spectral/time domain. Variational upper bounds apply only under their theorem's assumptions; an uncontrolled truncation is not a controlled approximation.
- **Numerical result:** basis/grid/cutoff or time-propagation result with algorithm, precision, tolerances, and convergence evidence. An eigenpair or solver residual at one cutoff is insufficient evidence for a physical prediction.
- **Heuristic estimate:** scaling, qualitative argument, or approximate model with no controlled remainder. Name its intended precision and assumptions.

Use `supported`, `contradicted`, `inconclusive`, or `unavailable` for claim status. Distinguish a prediction conditional on a Hamiltonian from a measured outcome or interpretation. An inconsistent state/operator model invalidates dependent conclusions but does not by itself falsify the physical hypothesis.

## Source dependencies and independence

Record Hamiltonian and potential provenance/version, particle/species and parameter values, state-preparation and measurement protocol, basis construction and cutoff, and solver/library release. Pin numerical packages and random seeds for stochastic methods. Record whether constants are SI, dimensionless, or natural units and retain explicit conversion factors.

Build a dependency graph for shared Hamiltonians, fitted parameters, basis truncations, initial states, calibration records, and code. Two spectra using the same truncated basis or potential are dependent checks; agreement between expectation values derived from the same state is not independent replication. Reused experimental shots or common calibration are propagated evidence, not new samples.

For external data or reported constants give source name, edition/release, date, and transformation. Keep theoretical derivations, numerical implementations, and measured observations on separate evidence lanes.

## Uncertainty and claim status

Separate state-preparation and measurement uncertainty, parameter uncertainty, model mismatch, approximation/truncation error, discretization, solver tolerance, stochastic sampling, and roundoff. Propagate uncertainty through probabilities and expectation values where justified, preserving covariance between observables that share state or parameters. Do not infer a confidence interval from solver tolerance alone.

For approximate claims report the small parameter and justified error order/bound, including whether it is uniform over the claimed energy/time range. For numerical claims record cutoff/grid/basis/time refinements, normalization and trace errors, residuals, and variation in the claimed observable. Retain null, failed, and unavailable outcomes and disagreements.

## Controls and sanity checks

- **Units and conventions:** check Hamiltonian terms have energy units, commutator signs match the chosen convention, and constants set to one are restored consistently. Record basis phases and distinguish global from relative phase.
- **State and probability:** verify state normalization; for density operators check Hermiticity, positivity, unit trace, and probability bounds.
- **Operator structure:** test self-adjointness/domain and boundary conditions for observables and generators; verify orthogonality/completeness within the retained subspace and relevant commutators.
- **Evolution:** for a closed system check unitarity, norm, and energy conservation when the Hamiltonian is time-independent. For an open system check trace preservation and the assumptions that ensure complete positivity.
- **Known limits:** recover free-particle and zero-coupling cases, symmetry/degeneracy expectations, short-time behavior, and a classical or semiclassical limit only where its conditions apply.
- **Independent benchmark:** compare an analytic spectrum or soluble model with the numerical method; refine grid/basis/cutoff/time step and compare distinct formulations when feasible.

Record expected relation, tolerance rationale, observed value, and pass/fail for every control. Failed normalization, positivity, boundary, or conservation checks block dependent claims.

## Sensitivity analysis

Vary Hamiltonian parameters and their uncertainty, initial-state preparation, boundary conditions, approximation parameter, basis family and cutoff, grid/time step, solver precision, and open-system generator assumptions. Near degeneracy, level crossings, avoided crossings, resonances, or long evolution, inspect whether small changes reorder levels or qualitatively alter populations and coherence.

Mark a conclusion **fragile** when a reasonable parameter or boundary perturbation within the stated uncertainty changes its sign, qualitative state/phase/transition classification, measurement probability beyond the declared tolerance, or decision. Report the perturbation and changed observable. For variational and perturbative approaches compare independent trial spaces/orders; apparent stability within one restricted family does not establish total error.

## Applicability domain

The skill's default scope is nonrelativistic quantum mechanics with explicitly specified Hilbert space and observables. Relativistic, quantum-field, identical-particle, many-body, and measurement-context questions require the corresponding structure rather than an unexamined single-particle model. Born-Oppenheimer, rotating-wave, Markovian, adiabatic, and weak-coupling assumptions can fail near crossings, strong drive, memory effects, or rapid environmental changes.

Finite bases and cutoffs can omit continuum states, high-energy tails, entanglement, or boundary behavior; convergence of a few eigenvalues does not establish convergence of all observables. A master equation may not be valid for strong coupling or non-Markovian dynamics. State explicitly when the method does not cover these regimes.

## Common failure modes and detection

| Failure | Detection |
|---|---|
| Non-self-adjoint operator or wrong boundary domain | Check integration-by-parts boundary terms and the operator domain before interpreting eigenvalues. |
| Missing normalization, complex conjugation, or operator order | Recompute norms and expectation values from definitions and check probability bounds. |
| Nondegenerate perturbation applied to a degenerate level | Diagonalize the perturbation within the degenerate subspace first. |
| Finite-basis eigenpair treated as a physical state | Vary basis family and cutoff; check residual, normalization, and observable convergence. |
| Density matrix is not positive or evolution is not trace-preserving | Inspect spectrum, trace, and generator conditions at each propagation step. |
| Global phase interpreted as an observable or relative phase discarded | Apply a global phase transformation and compare measurable quantities/interference terms. |
| Approximation used near a crossing or outside small-parameter range | Sweep the parameter and compare higher order, exact model, or independent method. |

## Recording a quantum result

For a perturbative energy shift, retain the unperturbed spectrum, degeneracy treatment, perturbation matrix elements, expansion parameter, and order retained. Compare with exact diagonalization or higher orders over the parameter range used; agreement at one point does not demonstrate a uniform error bound. Keep state-preparation and measurement uncertainties distinct from truncation error.

For a finite-basis open-system simulation, record the basis, cutoff, initial density operator, Hamiltonian, jump operators, solver, and timestep. Check positivity, trace preservation, and convergence of the claimed observable as the basis and time resolution change. A valid numerical evolution of a chosen master equation does not establish that the Markovian generator represents the physical environment.

These examples demonstrate claim boundaries; they do not prescribe a universal cutoff, solver, or error tolerance.

When comparing a prediction with data, define the measurement operator, outcome bins, shot count, and state-preparation protocol. A computed expectation value and a finite-sample frequency are not interchangeable; report sampling uncertainty and model uncertainty separately.
For repeated measurements, identify whether shots are independent under the preparation protocol; shared drift or postselection can invalidate a binomial uncertainty calculation.

## Sources

- David J. Griffiths and Darrell F. Schroeter, *Introduction to Quantum Mechanics*, 3rd ed. (2018): nonrelativistic wave mechanics, angular momentum, perturbation methods, and approximation examples.
- J. J. Sakurai and Jim Napolitano, *Modern Quantum Mechanics*, 2nd ed. (2017): state/operator formulation, symmetries, angular momentum, approximation methods, and measurement foundations.
- Benjamin Crowell, *Modern Physics* (2021 revision): quantum phenomena and introductory quantum-mechanical applications; provenance and license details are in `../../../docs/TEXTBOOK_SOURCES.md`.
