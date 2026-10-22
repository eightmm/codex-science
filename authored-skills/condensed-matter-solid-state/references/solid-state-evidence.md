# Solid-state evidence protocol

## Claim classes

Assign a stable ID to each material claim. Use `descriptive` for a reported
computed or measured property under stated conditions; `comparative` for an
ordering or difference between specified states; `predictive` for an observable
in an unmeasured condition; and `mechanistic` for a causal physical explanation
linking a model feature to an observable. A phase or ground-state claim combines
comparative and mechanistic support and must specify its order parameter,
symmetry-breaking assumption, thermodynamic-limit target, and finite-size
criterion. A computed Kohn-Sham band gap is a model quantity, not a
direct experimental gap claim. Assign `supported` only when the declared control,
convergence and applicability requirements pass; `contradicted` when credible
evidence conflicts at the same specificity; `inconclusive` when evidence is
insufficient, unstable or conflicting; `unavailable` when required evidence
cannot be obtained. Record a falsifier and the evidence IDs for every claim.

## Cell and reciprocal-space conventions

Record lattice vectors as an ordered matrix, the basis and its units, cell volume,
and whether the cell is primitive or conventional. For a reciprocal basis, state
the factor convention (with or without (2\pi)) and verify the declared duality
against the direct vectors. Record the basis transformation when converting a
conventional cell to a primitive cell. Name the Brillouin zone and path convention;
labels and high-symmetry paths are not universal across settings or centered
lattices. Check symmetry operations, equivalent k points, and degeneracies against
the chosen cell and magnetic space group. Do not compare band paths from different
cells until they are transformed to a common reciprocal basis.

## Dependencies and independence

For each result, record code and release, pseudopotential or basis-set identity,
exchange-correlation functional, relativistic treatment, structure source and
version, magnetic initialization, cell transformation, k-point generator, and
post-processing revision. Record shared experimental samples, structures,
databases, fitted parameters, functionals, and code when comparing reports.
Different calculations that share the same functional, structure, or data are
not independent confirmation. Pin release identifiers or immutable revisions;
record a date only when a service or source provides it. Note whether a reported
observable was derived from a model output or measured directly.

## Uncertainty and comparison with experiment

Keep separate numerical convergence error, statistical sampling error, structural
uncertainty, parameter uncertainty, model-form uncertainty, and experimental
uncertainty. State units, the reported uncertainty type, and whether it is a
standard uncertainty, interval, spread, or qualitative bound. Do not combine
uncertainties without a justified model. Match the calculated quantity to the
measured observable, temperature, pressure, composition, resolution and sample
state. For a calculated band structure, compare to the relevant spectroscopic
observable with its measurement and analysis assumptions; do not equate a
semilocal Kohn-Sham gap with a measured quasiparticle or optical gap. A scissor
correction or fitted offset is a separate model choice, not a validation result.

## Controls and sensitivity

Use controls appropriate to the claim: verify atom and electron counts, charge
neutrality or declared charging, lattice and magnetic symmetries, expected
degeneracies, sum rules, and limiting cases (atomic, free-electron,
long-wavelength, or high-temperature) where relevant. Compare matched states at
identical numerical precision and settings. For total-energy ordering, converge
the energy difference itself and check that reference states use consistent
cells and corrections. Vary one numerical control at a time until the observable
meets a prespecified tolerance: basis or cutoff, k-point density, smearing,
supercell size, solver tolerance and broadening. Then vary consequential modeling
choices, including functional, spin-orbit coupling, magnetic initialization,
defect concentration and structural relaxation. A conclusion is fragile if a
plausible change reverses ordering, changes the claim class or crosses the
declared decision threshold; report that outcome rather than selecting the
favorable setting.

## Applicability domain and failure detection

State whether the modeled object is a finite cluster, periodic crystal,
continuum, or measured sample, then state dimensionality, phase, composition, temperature and pressure range,
disorder level, defect concentration, magnetic state, and boundary conditions
where the model is intended to apply. A primitive periodic cell does not represent
arbitrary disorder or isolated defects without suitable supercell and correction
analysis. Finite cells can suppress long-wavelength modes and shift phase
boundaries; periodic images can interact. Detect these by cell-size trends,
image-separation checks, shape variation, and comparison with an appropriate
finite-size model. Smearing can blur small gaps, Fermi surfaces and phase changes;
vary smearing and extrapolate only with a stated regime. Different spin starts
converging to different states reveal metastability, not a unique ground state.
Semilocal gap error, missing many-body effects, omitted spin-orbit coupling,
unmodeled disorder, and mismatched measured observables must remain explicit
limitations. Stop or downgrade when controls fail, convergence is nonmonotonic,
the stable ordering changes under plausible settings, or the experiment lies
outside the modeled domain.

## Sources

- N. W. Ashcroft and N. D. Mermin, *Solid State Physics* (1976), for crystal,
  reciprocal-space, band and magnetic foundations.
- R. M. Martin, *Electronic Structure: Basic Theory and Practical Methods*
  (2004), for electronic-structure methods and computational approximations.
- The source titles ground physical conventions and method scope; they do not
  establish a particular calculation's convergence or agreement with experiment.
