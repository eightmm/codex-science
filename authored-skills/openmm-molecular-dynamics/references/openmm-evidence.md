# Evidence and interpretation for OpenMM simulations

## Claim semantics

Use the shared statuses `supported`, `contradicted`, `inconclusive`, and `unavailable`, tied to claim IDs and prespecified criteria.

- **Model-observable claim:** a value calculated from a particular serialized system and trajectory is supported only for the named atoms, observable definition, units, and time window after input and sampling checks. A simulated value is not an experimental measurement.
- **Model-conditional physical interpretation:** a claim about conformational populations, contacts, or dynamics requires validated parameters, acceptable equilibration, sampling and controls, and robustness to plausible numerical/model settings. Identify it explicitly as conditional on those assumptions.
- **Comparative claim:** compare conditions using matched system preparation, analysis, duration/replicate design, and a declared contrast with uncertainty. A changed platform or integrator setting is a method comparison, not a clean biological-condition contrast.
- **Experimental, causal, or binding-affinity claim:** simulation alone does not establish these. Mark unavailable absent relevant independent experiments and a design that justifies the inference. Force-field potential energy is not an experimental free energy.
- Use `contradicted` only when the prespecified observation conflicts with the claim under the tested model; no event in an under-sampled trajectory is not falsification.

## Source dependencies and independence

Preserve prepared structure and repair history, atom mapping, protonation/tautomer choice, parameter generator and version, ligand charges/parameters, force-field and water files, ion model, topology/system serialization, restraints, box, driver source, OpenMM and plugin versions, platform/device, precision, integrator, thermostat/barostat, timestep, seeds, and artifact hashes. Pin exact release or immutable source revision. A force-field label alone does not identify all parameter files.

Record the Python and binary environment needed to reload serialized objects. Platform-specific kernels, precision and plugin versions can alter numerical trajectories; do not assume bitwise identity across CPU/GPU, devices, or releases. A resumed segment shares the original trajectory ancestry and is not an independent replica. Independent replicas need distinct recorded initialization/seeds; replicas that share preparation and model assumptions still share those sources of uncertainty.

## Uncertainty and convergence

Separate finite-sampling uncertainty, between-replica variation, numerical implementation variation, and force-field/protocol uncertainty. Treat frames as correlated: estimate observable-specific autocorrelation/effective sample size where feasible, inspect block averages at increasing block sizes, and state time windows and confidence/interval method. Material block-size drift or disagreement among replicas means fragile or inconclusive evidence. Report per-replica estimates as well as the aggregate.

Assess equilibration from prespecified observables, energy and thermodynamic time series, stage transitions, and relaxation from the initial state. Compare early/late windows and replicas; do not infer equilibrium from a stable total energy, one global RMSD plateau, or successful minimization. Convergence is observable-specific. A stable density cannot establish sampling of a slow torsion or binding mode. Report when available simulation time cannot resolve the relevant relaxation or transition.

## Controls and sanity checks

- When changing OpenMM release, platform, precision, or force-field setup, run a documented known-system benchmark or validated reference protocol and compare only matching observables and conditions.
- Use independent-seed replicas for stochastic sampling claims; retain the initial-state and seed lineage for every replica.
- Check system particle/atom counts, total charge, topology connectivity, box vectors, units, force coverage, constraints, and finite energies after construction and after minimization.
- Track energy, temperature, pressure, density, volume, constraint violations, NaN/Inf, and target-observable stationarity against declared thresholds through each stage.
- Test checkpoint serialization/reload and a short deterministic continuation where the platform permits; record any expected non-bitwise differences. This validates restart mechanics, not independent science.
- Compare an unrestrained or alternative restraint schedule only when the claim could depend on restraints; preserve the production target ensemble definition.

## Sensitivity analysis

Keep a declared baseline and vary timestep (including a smaller timestep), nonbonded cutoff/treatment, thermostat and coupling constant, barostat and coupling constant, and box size. Also vary precision/platform or integrator when implementation robustness matters, and examine seeds, equilibration discard, production window, and observable definitions. Change one material factor at a time when feasible; otherwise identify the confounding. A result is fragile if qualitative interpretation, sign, rank, claim status, or threshold decision changes beyond the prespecified tolerance, or if a plausible setting violates diagnostics. State untested settings and do not silently retune after observing the result.

## Applicability domain

Claims are conditional on composition and protonation, ligand parameterization, force field, water/ion model, restraints, ensemble, finite periodic box, integrator and sampling timescale. Classical fixed-topology simulations do not capture bond breaking or electronic polarization unless the chosen model explicitly includes it. Parameter sets may not transfer to unusual chemistries, covalent ligands, metals, modified residues, or nonstandard solvents without validation. Short trajectories and one basin cannot support rare-event kinetics or broad conformational populations. A platform-consistent run does not cure model error.

## Common failure modes and detection

| Failure | Detection and response |
| --- | --- |
| Missing or guessed ligand parameters | Check atom mapping, charge balance, force assignment, and parameter provenance; stop until validated. |
| Invalid units or box vectors | Check units, periodic box and geometry before system creation; reject guessed conversions. |
| Checkpoint/configuration mismatch | Compare serialized system, integrator state, platform/config and hashes; do not append incompatible state. |
| NaN energy or constraint instability | Check after construction, minimization and each stage; halt, retain failure artifacts, diagnose timestep/constraints/parameters. |
| False convergence from aggregate traces | Inspect per-observable blocks, replicas, and autocorrelation; downgrade if they disagree or drift. |
| Hardware/version-dependent change | Compare a known-system test and numerical tolerances on pinned platforms; report platform/precision boundary. |
| Apparent robust result depends on setup | Rerun prespecified timestep, cutoff, coupling, box or seed variants; narrow claim if qualitative outcome shifts. |

## Reading the OpenMM run record

- Preserve the serialized `System` and `Topology` with the construction script and input files. A script alone may resolve different defaults or parameter files later.
- Record which forces were added and their parameter sources, including custom forces and nonbonded exceptions. Verify charge and particle counts after construction.
- Distinguish integrator state from system definition and from platform context state. A checkpoint is valid only for a compatible system, integrator and execution setup; compare exact restart metadata before continuing.
- Record actual platform, device, precision, and plugin versions for every chunk. GPU and CPU trajectories can differ numerically even when they implement the same model.
- Inspect per-stage trajectories or energy records at boundaries; restrained equilibration is not evidence that the unrestrained production ensemble has equilibrated.
- Check barostat and thermostat configuration against the intended ensemble. A temperature or pressure target in configuration is not proof that the trajectory sampled the target distribution.
- Record both configured and effective timestep, constraints, cutoffs, and dispersion treatment. If a precision/platform setting changes stability, report the result as a method sensitivity.
- For comparisons, use a common observable implementation and align the analyzed time windows. Different stride or discard choices can create an apparent condition effect.
- Preserve partial chunks and restart attempts with distinct identities. Do not flatten chunk lineage when the restart chain contains a failed or incompatible state.
- When available sampling cannot resolve the observable, report the finite trajectory limitation even if the numerical diagnostics pass.
- Retain the exact serialized system and integrator construction arguments for every platform; human-readable force-field names do not uniquely identify a built system.
- Check that checkpoint and State files are not treated as interchangeable restart artifacts; document which one supplies the integrator or context state.
- Record the random number generator and seed where exposed by the selected integrator/platform, and state when a platform does not guarantee deterministic replay.
- Verify restart behavior with a bounded continuation before relying on a long chunked run; keep the original checkpoint unchanged for recovery.
- Report minimization convergence criteria separately from physical equilibration criteria; minimization finds a local low-energy configuration, not an equilibrium ensemble.
- For positional restraints, record atom selection, reference coordinates, force constants, and release stage so results can be tied to the intended ensemble.
- Do not compare scalar energies across systems with different atom counts or Hamiltonians as if they were directly comparable measures of affinity.
- When temperature or pressure coupling is changed for numerical stability, record the method change and rerun the affected sensitivity check rather than silently substituting settings.
- Distinguish an implementation check on a known system from evidence that the modeled target's chemistry is parameterized correctly.
- Keep analysis discard windows and the actual simulated time range in physical units to expose short or discontinuous production coverage.

## Sources

- Eastman et al. (2017), “OpenMM 7: Rapid development of high performance algorithms for molecular dynamics,” *PLoS Computational Biology* 13(7):e1005659. This describes the OpenMM toolkit, not validity of any particular simulation result.
- Allen and Tildesley (2017), *Computer Simulation of Liquids*, 2nd edition. Use for simulation, ensemble, and sampling principles; it does not certify a specific parameter set.
- Grossfield et al. (2019), “Best Practices for Quantification of Uncertainty and Sampling Quality in Molecular Simulations,” *Living Journal of Computational Molecular Science* 1(1). Use for sampling-quality and uncertainty practice, not as a universal stopping threshold.
