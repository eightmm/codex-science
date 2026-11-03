# Method selection and extension

## Search before selection

The seeds are dated documentation references, not installed executors. At selection time inspect current official methods/docs and record access date, immutable release/code identity, license, input formats, observable support, PBC/units behavior, compute envelope and limitations. Prefer the existing approved reader/analyzer when sufficient. MDAnalysis analyzes existing coordinates; OpenMM and GROMACS produce trajectories under a separately selected force field and protocol. A change of engine, parameterization or analysis is a different dependency and must be named separately.

MDAnalysis documentation describes automatic reader conversion to angstrom and ps; OpenMM theory uses nm and ps. Export unit metadata rather than inferring it from a producer name. GROMACS `gmx analyze` documents autocorrelation and block error estimation. These references support method choices, not a universal block length, equilibration cutoff or convergence claim.

## Additive admission

A new compatible analyzer or observable may be described in a run-local ordinary artifact with method ID, role, dated official sources, pinned code/configuration/hash, formats/topology/atom requirements, units/PBC behavior, statistical assumptions, controls, budget, licensing and evidence state (`discovered`, `documented`, or receipt-backed `pilot`). Hash that descriptor into the frozen plan, independently review interpretation-changing choices, and keep missing execution unavailable. Do not edit the backend registry or treat a descriptor as installation, execution authorization or validated performance. New simulation returns to the existing engine skills and approval boundary.
