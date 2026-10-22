# Electromagnetism claim calibration

Load this reference before classifying a field or circuit result, applying a reduced regime, or interpreting numerical agreement. Maxwell-equation consistency is conditional on declared sources, constitutive laws, and boundary data.

## Claim semantics

Give every material claim a stable ID, one primary class, and explicit dependencies.

- **Exact result:** an identity, theorem consequence, or solution of the stated Maxwell/boundary-value equations without truncation. State sources, constitutive model, domain, and boundary/radiation conditions; exactness does not validate those inputs.
- **Controlled approximation:** quasistatic, lumped, multipole, paraxial, perturbative, or other reduced result. Name a dimensionless small parameter (such as size/wavelength, displacement-current ratio, or nonlinear response scale), retain the justified order, and state a derived or sourced error order and domain. Without a controlled remainder, call it heuristic.
- **Numerical result:** a solved discretized or iterated field with mesh, basis, time/frequency resolution, solver, precision, boundary treatment, and convergence evidence. Residual alone does not bound field error near singular or ill-conditioned configurations.
- **Heuristic estimate:** scaling, order-of-magnitude, or qualitative estimate that has no controlled error bound. State intended precision and model dependence.

Use statuses `supported`, `contradicted`, `inconclusive`, and `unavailable` consistently. A failed constitutive or boundary assumption makes the result inapplicable; it does not establish that the underlying physical hypothesis is false.

## Source dependencies and independence

Record charge/current source identity, geometry revision, material composition, constitutive parameter provenance, measurement calibration, boundary data, frequency range, and acquisition or solver release. Pin software and meshing libraries, discretization, tolerances, and unit conventions for numerical comparisons.

Map shared sources and transformations: the same measured permittivity, fitted conductivity, geometry mesh, Green function, or boundary data makes downstream field and derived power estimates dependent. A field and its Poynting flux are not independent observations when the latter is computed from the former. Repeated frequencies or sensor locations from one calibration or specimen do not create independent source evidence.

Name the equation convention source when signs or unit factors depend on it. Record SI or Gaussian units throughout, including the definitions of charge/current and the constitutive parameters; conversion must be explicit and reversible.

## Uncertainty and claim status

Keep source measurement, calibration, geometry, material parameter, boundary condition, model-form, approximation, discretization, iteration, and roundoff uncertainties separate. Propagate correlated uncertainties where fields, energy, force, impedance, or radiation power share parameters. If the model does not support a quantitative propagation, retain the direction and likely scale qualitatively.

For controlled reductions report the controlling parameter and omitted-order estimate at every location or frequency where it changes. For numerics retain refinement sequences, field norms, boundary mismatch, charge-continuity residual, and conservation balance. Report singular-source regularization separately from physical uncertainty.

A claim's status reflects its preregistered checks. Preserve failed controls and conflicting independent estimates; numerical precision cannot compensate for uncertain source geometry or material response.

## Controls and sanity checks

- **Units, signs, and gauge:** dimension-check Maxwell equations, potentials, energy density, impedance, and Poynting vector. Check right-hand orientations and source signs. Under a gauge change, verify gauge-invariant fields and observables remain fixed.
- **Local laws:** check Gauss laws, Faraday/Ampere curl equations, and continuity equation with the same sources and sign convention.
- **Interfaces and global laws:** test normal/tangential field jump conditions and independently integrate flux or circulation over a closed surface/loop.
- **Limits and symmetry:** recover vacuum, conductor, electrostatic, magnetostatic, far-field, long-wavelength, and symmetry-reduced solutions when their assumptions hold.
- **Energy and reciprocity:** verify electrostatic energy positivity for passive media and Poynting/power balance including ohmic, radiative, and stored-energy terms. Test reciprocity only when the material and boundary assumptions support it.
- **Numerical benchmark:** compare a canonical capacitor, coaxial geometry, plane wave, or known boundary-value solution; refine mesh and frequency/time step and check interface resolution.

Record the expected relation, tolerance basis, measured outcome, and dependencies for each check. A control failure blocks claims that rely on it.

## Sensitivity analysis

Perturb source positions and distributions, geometry, boundary/radiation conditions, material parameters, calibration, frequency, and the small parameters used to justify quasistatic, lumped, linear, or multipole approximations. For field solvers vary mesh topology/resolution, domain truncation, basis, frequency/time step, precision, and iterative tolerance. Probe near resonances, interfaces, skin-depth scales, and singular ideal sources when conclusions depend on them.

Mark the conclusion **fragile** if allowed changes within input uncertainty or admissible boundary/model alternatives change its sign, qualitative field pattern, passivity/energy conclusion, resonance classification, or reported decision beyond a prespecified tolerance. State the perturbation and affected observable. For singular idealizations, compare regularized geometry/material models and disclose nonconvergent observables.

## Applicability domain

Electrostatics requires negligible time variation; magnetostatics requires steady sources; quasistatic limits require a justified separation from propagation delay and radiation scales. Lumped circuits require dimensions and delays small relative to relevant wavelengths and switching times. Linear constitutive laws fail for nonlinear, saturated, hysteretic, strongly dispersive, or state-changing media.

Ideal point/line charges and currents may have divergent local fields or energy; numerical mesh refinement near them need not converge to a finite pointwise value. Continuum material models fail below their structural scale. Perfect conductors, infinite domains, radiation conditions, and homogeneous media are idealizations whose boundary/model error must be considered before extrapolation.

## Common failure modes and detection

| Failure | Detection |
|---|---|
| SI/Gaussian factors or source signs mixed | Check one canonical Coulomb, Ampere, or plane-wave result in the declared convention. |
| Symmetry used without symmetric sources and boundaries | Transform sources and boundaries under the proposed symmetry and test field uniqueness conditions. |
| Gauge-dependent quantity reported as observable | Apply a gauge transformation and recompute the claimed observable. |
| Interface condition omitted or wrong component constrained | Independently check normal and tangential jump relations on each interface. |
| Quasistatic or lumped limit used beyond scale separation | Compare propagation, switching, and geometry scales; sweep the controlling dimensionless ratio. |
| Under-resolved interface, skin depth, or wavelength | Inspect local mesh/step ratios and verify systematic refinement of fields and fluxes. |
| Residual or energy agreement hides wrong sources | Check continuity, boundary mismatch, source integration, and an independent canonical benchmark. |

## Recording a field or circuit result

For a lumped circuit, record the device dimensions and relevant wavelength or rise time before treating Kirchhoff equations as a controlled reduction. Identify omitted radiation, propagation, and parasitic effects; if their scale is not bounded, report a circuit estimate rather than a controlled approximation. Keep measured component values, temperature, frequency dependence, and calibration source linked to derived voltage and power claims.

For a boundary-value field solution, record the source distribution, material map, interface conditions, outer boundary or radiation condition, and field norm used for refinement. Compare integral flux with a local residual because either check alone can miss a defect in the other. For idealized point or line sources, report singular local behavior separately from a spatially averaged or regularized observable.

The examples define evidence handling, not universal tolerance values or material models.

When comparing field predictions with measurements, define sensor response, spatial averaging, bandwidth, and calibration before assigning residuals. A pointwise computed field and a finite-aperture measurement are different observables unless the measurement operator is applied to the prediction.

## Sources

- David J. Griffiths, *Introduction to Electrodynamics*, 4th ed. (2013): Maxwell equations, potentials, boundary-value methods, waves, and energy flow in the conventional SI presentation.
- John David Jackson, *Classical Electrodynamics*, 3rd ed. (1998): advanced boundary-value, radiation, wave, and electromagnetic-field methods; equation and unit conventions must be checked against the selected edition and problem.
- The skill's open source basis and licensing are documented in `../../../docs/TEXTBOOK_SOURCES.md`; these references do not establish material parameters or empirical field validity.
