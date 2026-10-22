# Evidence and interpretation for GROMACS simulations

## Claim semantics

Assign one status to each preregistered claim: `supported`, `contradicted`, `inconclusive`, or `unavailable`.

- **Model-observable claim:** a directly computed quantity (for example, energy, density, distance, or RMSD) is supported only for the stated model, atom selection, trajectory interval, and analysis definition when diagnostics and uncertainty meet the declared criterion. It says what this simulation produced, not what an experiment measured.
- **Model-conditional physical interpretation:** an interpretation about conformational preference, contacts, or dynamics requires adequate parameterization, equilibration, sampling, controls, and robustness to declared settings. If model limitations or sampling dominate, label it inconclusive or exploratory.
- **Comparative claim:** a difference between conditions requires matched analysis, comparable sampling and independent replicas or another justified uncertainty model; report the contrast and its uncertainty, not only two separate means.
- **Experimental or causal claim:** assign unavailable from simulation alone. Requires independent, relevant experimental evidence and a separate design that supports the stated inference.
- `Contradicted` requires a prespecified result incompatible with the claim under the model and analysis; failure to observe an event in a short run is not contradiction.

## Source dependencies and independence

Record source structure, preparation and repair operations, atom mapping, ligand parameter source and version, force-field files, water and ion model, topology includes, `.mdp` files, GROMACS version/build, hardware and precision, commands, seeds, and hashes. Pin exact releases or immutable revisions; a force-field family name alone is insufficient to reproduce the parameter set.

Frames from one trajectory are correlated observations, not independent replicas. Independent replicas need separately initialized velocities/seeds and preserved ancestry; if they share the same starting structure, preparation, force field, and protocol, state those shared dependencies. Repeated analysis of the same trajectory is not replication. A benchmark rerun validates implementation/protocol behavior only to the extent that the benchmark tests that behavior.

## Uncertainty and convergence

Separate within-trajectory sampling uncertainty from between-replica variability and model/protocol uncertainty. Estimate correlation time or effective sample size for each observable when feasible; use blocks longer than the relevant correlation time and report block stability, replica count, interval method, and sampled time window. A block average whose estimate changes materially with block size is fragile. Report each replica as well as pooled summaries; do not let a large frame count conceal disagreement among replicas.

Assess equilibration with declared physical diagnostics and time series, not a visual RMSD plateau alone. Compare early/late blocks for target observables and thermodynamic quantities, inspect drift and stationarity, and repeat with independent seeds. Convergence is claim- and observable-specific: a stable density does not establish convergence of a slow conformational transition. State when the trajectory is too short to distinguish slow relaxation from equilibrium.

## Controls and sanity checks

- Run a documented known-system or published protocol benchmark when the software/build or workflow is unfamiliar; compare only quantities with the benchmark's matching conditions and uncertainty.
- Use independent-seed replicas for stochastic sampling claims; preserve each seed and initialization.
- Inspect energy and temperature behavior, pressure/density/box evolution in NPT, constraint failures, warnings, volume excursions, and periodic-boundary artifacts against prespecified criteria.
- Verify atom counts, charges, topology connectivity, ligand mapping, and component parameters before `grompp`; unresolved warning or parameter gaps are stop conditions.
- Where feasible, compare a short rerun or restart with a clean run under the same immutable inputs to detect restart/append or analysis mistakes. This is a pipeline check, not independent scientific replication.

## Sensitivity analysis

Vary one material choice at a time and preserve a baseline: timestep (including a smaller step), nonbonded cutoff and treatment, thermostat and coupling time, barostat and coupling time, and periodic box size. Also inspect constraint choices, initial velocities/seed, equilibration window, production window, and analysis selection where relevant. A conclusion is fragile if the sign, claim status, rank ordering, qualitative mechanism, or threshold crossing changes beyond the prespecified tolerance, or if diagnostics fail in a plausible alternative setting. Report settings not tested; never tune silently after seeing the target result.

## Applicability domain

A result applies only to the represented chemical composition, protonation/tautomer states, parameter coverage, force field, water/ion model, boundary conditions, thermodynamic ensemble, restraints, and sampled timescale. Classical fixed-topology models do not represent bond breaking or electronic rearrangement. Standard nonpolarizable force fields and water models can misrepresent systems or observables outside their parameterization domain. Finite periodic boxes can couple a solute to its images; inadequate sampling cannot be repaired by more frames from the same trapped basin. Binding, kinetic rates, rare events, and experimental observables need specialized validation beyond routine trajectory completion.

## Common failure modes and detection

| Failure | Detection and response |
| --- | --- |
| Unsupported ligand or protonation parameters | Audit atom mapping, charges, bonded terms, and parameter provenance; stop and resolve before `grompp`. |
| Suppressed topology warning | Inspect full `grompp` output and record each justified exception; reject unexplained `-maxwarn` continuation. |
| Apparent equilibration with drift | Plot energy, density, box, and target observables by stage/block; extend or downgrade if declared stationarity criteria fail. |
| Restart from changed inputs | Compare checkpoint ancestry and hashes of TPR, topology, `.mdp`, and seed/configuration; do not append incompatible segments. |
| False precision from correlated frames | Estimate autocorrelation/effective samples and block-size stability; report replica-level uncertainty. |
| Box/cutoff or coupling sensitivity | Compare planned alternatives and monitor volume, density, and observable shifts; narrow the claim if outcomes change. |
| Periodic jump mistaken for a structural event | Inspect molecules across boundaries and transformation history; analyze a derived corrected trajectory and preserve raw coordinates. |

## Reading the GROMACS run record

- Treat each `.mdp` as part of the model definition. Record resolved values, not only user-supplied overrides, because defaults and preprocessing can affect the generated TPR.
- Check the generated TPR and topology lineage alongside the original topology and include files; a command line without those artifacts is not enough to identify the simulated system.
- Separate minimization, restrained equilibration, unrestrained equilibration, and production. A successful `mdrun` exit establishes process completion only.
- For NVT stages, compare temperature and energy behavior to the chosen ensemble and coupling scheme; for NPT stages, inspect pressure, density, volume, and box dimensions over time. Short pressure fluctuations alone are not an equilibrium failure, but sustained drift or implausible volume changes require diagnosis.
- Examine constraint warnings and integration stability when changing timestep or constraints. A trajectory that runs without crashing may still have unacceptable energy behavior.
- Check that neighbor-list, electrostatics, and cutoff settings match the intended protocol and box geometry. A sensitivity rerun changes the protocol and must be reported as such.
- Confirm that periodic correction, centering, fitting, and analysis run on derived files with documented commands. Never overwrite the source trajectory during preparation.
- Report the actual simulated interval after equilibration discard, not just the production command's nominal duration; missing frames or failed chunks reduce analyzed coverage.
- Preserve cancelled and failed stages with their exit status and diagnostic output. Do not summarize a partial trajectory as a completed intended protocol.
- When a diagnostic has no justified universal threshold, set a system-specific criterion before inspecting the result and record its rationale and uncertainty.
- Retain the complete `grompp` output and the resulting topology/TPR identity so a later audit can distinguish an acknowledged warning from an unrecorded one.
- Verify that continuation files belong to the same run identity; a filename match is not sufficient evidence that a checkpoint matches the input protocol.
- When multiple restraints are released in stages, name the restrained atoms and force constants for each stage; record whether the measured observable was collected before or after release.
- Separate equilibration discard from production duration in the output and preserve the rule used to select the discard interval.
- If an NPT box-size sensitivity changes the effective solute-image separation, interpret the change as a finite-size/model limitation rather than ordinary replicate noise.
- Do not average observables across replicas with different analyzed windows without stating the weighting and explaining why the windows are comparable.
- A correct temperature distribution cannot compensate for an invalid topology, nonphysical density, or inadequate sampling of the target observable.
- Report the ensemble actually generated by the integrator and coupling scheme; do not infer it solely from a requested temperature or pressure value.
- If force-field parameters were regenerated or patched, archive the exact modified files and identify the changes relative to the upstream version.
- Treat a benchmark pass as a bounded software/protocol control; it does not demonstrate that the target molecule is inside the benchmark's applicability domain.

## Sources

- Abraham et al. (2015), “GROMACS: High performance molecular simulations through multi-level parallelism from laptops to supercomputers,” *SoftwareX* 1–2, 19–25. This describes GROMACS implementation and performance, not scientific validity of a particular model.
- Allen and Tildesley (2017), *Computer Simulation of Liquids*, 2nd edition. Use for molecular-simulation ensemble, sampling, and statistical-mechanics principles; it does not validate a specific force field.
- Grossfield et al. (2019), “Best Practices for Quantification of Uncertainty and Sampling Quality in Molecular Simulations,” *Living Journal of Computational Molecular Science* 1(1). Use for uncertainty and sampling-quality practice, not as a universal convergence threshold.
