# Continuum Model Evidence and Verification

## Claim semantics

Assign a class to each material claim and report its evidence status separately.

- **Exact result:** follows from the stated balance laws, kinematics, constitutive assumptions, and boundary/initial data without approximation. State those assumptions; a solution is exact for the model, not necessarily for the material.
- **Controlled approximation:** names the small parameter, retained order, and regime, such as small strain, low Mach number, or a perturbative constitutive term. Give the error order or a defensible bound when available and state the loading/deformation range where it applies.
- **Numerical result:** comes from a specified spatial and temporal discretization, solver, constitutive update, and precision. Report mesh/time refinement, residuals, conservation drift, and iteration tolerances separately. Convergence to a discrete solution does not show continuum-model adequacy.
- **Heuristic estimate:** uses scaling, an unvalidated closure, or an informal analogy without a demonstrated error order. Label it as an estimate and retain the assumptions.

Use status `supported`, `contradicted`, `inconclusive`, or `unavailable`. Distinguish mathematical solution, numerical verification, material characterization, and empirical validation.

## Source dependencies and independence

- Record source title, author, edition/revision, year where known, and exact constitutive data, table, or equation used. Pin solver/library versions, material-data versions, mesh generator settings, and input hashes.
- Measurements from one specimen, batch, imaging session, or calibration remain dependent when converted into multiple material parameters or boundary fields. Preserve specimen/cohort IDs and propagation history.
- Reusing a fitted constitutive law, training data, or calibration curve across simulations does not create independent material evidence. A second solver sharing the same law and mesh does not independently validate that law.
- Separate parameter fitting from validation data. Record which observations fit the law, which assess it, and any shared specimen, loading path, or preprocessing.
- In multi-physics or coupled models, mark shared source fields and parameters so errors are not treated as independent when combining outputs.

## Uncertainty and reporting

- Separate measurement and load uncertainty, uncertain material parameters, spatial/temporal discretization error, nonlinear/linear iteration error, constitutive-update error, and model discrepancy.
- Propagate parameter covariance through predicted fields when justified. For uncertain boundaries, contact states, or model class, report scenario envelopes or sensitivity ranges instead of a fabricated distribution.
- Preserve correlations among elastic constants, fitted rates, and spatially correlated loads. Do not sum uncertainties as independent without evidence.
- Report stress and strain measures with their configuration, units, sign convention, coordinate frame, and averaging method. State whether a reported peak is pointwise, elementwise, or spatially averaged.
- Report mesh quality, refinement sequence, time-step policy, solver tolerance, and conservation error so numerical uncertainty can be distinguished from material uncertainty.
- When observed rates are outside the expected asymptotic range, report non-asymptotic refinement; do not extrapolate a convergence order from an insufficient or irregular sequence.

## Domain controls

- **Configuration control:** state reference/current coordinates and whether stress, strain, and divergence are material or spatial. Verify transformations before combining terms from different configurations.
- **Constitutive control:** document the material class, calibrated state range, objectivity, symmetry, and dissipation assumptions before testing admissibility. A constitutive law is part of the model contract.
- **Dimensional/sign control:** verify units of every balance, traction, stress, strain, and energy term; check traction orientation and stress sign convention.
- **Objectivity and symmetry:** superpose a rigid translation/rotation and verify predicted objective quantities transform correctly; check stress symmetry when angular-momentum assumptions require it.
- **Conservation control:** integrate mass, linear/angular momentum, and energy over the domain and compare boundary fluxes, body forces, and sources. Record residual imbalance and tolerance.
- **Limiting controls:** test rigid motion, hydrostatic state, uniaxial loading, inviscid behavior, and small-strain reduction where the constitutive model supports each limit.
- **Boundary/interface control:** verify essential conditions are compatible, natural tractions have the correct sign, and interface jumps satisfy balance laws.
- **Positive controls:** a rigid-body motion should produce zero strain under an objective kinematics; a uniform equilibrium state should satisfy the declared balances with matching boundary data.
- **Negative controls:** perturb a traction sign, omit a boundary flux, violate a displacement constraint, or use a non-objective constitutive update in a rigid rotation test; the corresponding balance, compatibility, or objectivity check should fail.
- Check constitutive admissibility under the declared model, including symmetry, dissipation, and stability assumptions. Do not impose a universal positivity rule without identifying the material law and state range.
- Record expected behavior, observed result, tolerance, and pass/fail rationale. An unresolved failed control makes the affected claim inconclusive.
- For a closed body with no external load, integrated internal forces should not create net linear momentum; verify action/reaction and boundary accounting.
- For a static solution, check that inertial terms vanish consistently and that the remaining stress divergence, body force, and boundary traction balance.
- For transient calculations, record conservation and constitutive admissibility over time, including extrema rather than only the final state.

## Sensitivity and fragility

Vary choices that can change the solution or its interpretation:

- mesh resolution, element family/order, mesh quality, time step, stabilization, solver tolerance, and constitutive update;
- boundary and interface conditions, contact/friction assumptions, loads, and initial state;
- small-strain versus finite-strain kinematics and material versus spatial formulation;
- constitutive model, material symmetry, rate/thermal/compressibility assumptions, and fitted parameter values;
- spatial heterogeneity, specimen-to-specimen variation, and governing nondimensional ratios.

Call a claim fragile if admissible changes within parameter uncertainty or the stated modeling regime reverse its sign/classification, change the governing failure mode, or exceed the numerical/model error budget. For numerical claims, require mesh and time-step refinement independently when both affect the result; a change larger than the declared tolerance or lack of a stable trend blocks a convergence claim.

Use separate perturbations to attribute sensitivity to boundary data, material parameters, and discretization. Joint scenarios can follow when interactions are plausible. Report the tested mesh/time range and whether observed changes decrease consistently; a single fine mesh is not refinement evidence.

## Applicability domain and failure modes

- Small-strain linear elasticity fails when rotations or strains are not small, geometry changes materially, or nonlinear response matters. Compare strain/rotation scales with the declared approximation and test a finite-strain alternative when needed.
- A constitutive law is valid only over its calibrated material, temperature, rate, pressure, and loading-history range. Detect extrapolation by comparing state variables with the calibration domain and report out-of-domain use.
- A mesh can be refined while retaining locking, poor element quality, or an inconsistent formulation. Inspect deformation modes, mesh quality, and element behavior; compare formulations or element families.
- Contact, shocks, incompressibility, and sharp interfaces can defeat smooth-solution assumptions or default stabilization. Monitor jumps, oscillation, constraint residuals, and conservation across interfaces.
- Boundary data may overconstrain or underconstrain a model. Check compatibility, rigid-body modes, and integrated force/moment balance before interpreting a solution.
- Time-step refinement alone cannot detect spatial error, and mesh refinement alone cannot detect temporal error. Refine each active discretization axis and retain failed levels.
- Solver residuals can be small while the discretization or model is wrong. Compare balances, limiting cases, independent formulations, and available measurements.
- Continuum modeling fails when the modeled scale is not large relative to microstructure or when localization/fracture invalidates the assumed smooth field. State scale separation and the omitted microphysical mechanisms.
- A finite-strain stress/strain pair may be incompatible with the chosen energy or constitutive update. Check conjugacy and configuration consistency before interpreting work or energy.
- An apparent conservation failure can originate in omitted boundary fluxes or inconsistent quadrature. Compare integrated terms and refine numerical integration before attributing it to the material law.
- Calibration and validation on the same loading paths can make an out-of-sample constitutive claim circular. Hold back independent paths or specimens when available and disclose shared data otherwise.
- Boundary-condition sensitivity can dominate constitutive uncertainty in underconstrained geometries. Perturb plausible boundary values and compare the resulting fields and integrated reactions.

## Sources

- Gurtin, *An Introduction to Continuum Mechanics*, 1981: kinematics, balance laws, and constitutive foundations.
- Truesdell and Noll, *The Non-Linear Field Theories of Mechanics*, 1965: nonlinear continuum kinematics and constitutive framework.
- The workflow also draws on the open continuum-mechanics materials and Schnick text recorded in [the textbook source register](../../../docs/TEXTBOOK_SOURCES.md); the register gives provenance rather than a complete scholarly bibliography.
