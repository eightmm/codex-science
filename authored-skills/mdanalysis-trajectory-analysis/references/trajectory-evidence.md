# Evidence and interpretation for MDAnalysis trajectory analysis

## Claim semantics

Use `supported`, `contradicted`, `inconclusive`, or `unavailable` for each frozen claim ID.

- **Trajectory measurement:** a calculated RMSD, contact count, distance, SASA, or other observable is supported only for its exact topology, atom selection, transformations, units, frame window, and trajectory lineage after validation. It is a measurement of the analyzed simulation record, not an experimental fact.
- **Model-conditional interpretation:** a statement about conformational populations, stability, or dynamics additionally depends on the simulation force field, water model, ensemble, equilibration, and sampling. Analysis software cannot establish that these model assumptions are adequate.
- **Comparative claim:** compare conditions only with a declared matched analysis contract and a defensible independent-replica or uncertainty design. Repeated frames or alternate analysis of the same trajectory do not create independent samples.
- **Experimental/binding/causal claim:** trajectory analysis alone cannot establish experimental binding, affinity, biological function, or causality. Mark unavailable unless supported by independent data and a justified inference design.
- `Contradicted` requires a prespecified incompatible result; no observed transition in limited sampling is not evidence that the transition cannot occur.

## Source dependencies and independence

Record topology and trajectory hashes, file formats/readers, atom order, residue and chain mapping, units, time step/frame times, box vectors, trajectory segments, missing frames, and software/library versions. Preserve simulation producer, force-field/water model, ensemble, seed/replica identity, preparation history and exact transformation sequence when known. Pin the MDAnalysis release and analysis code/configuration; retain selection strings, reference structures, fitting atoms, PBC operations, and coordinate transformations.

Trajectory segments concatenated from one run share initialization, model, and sampling ancestry. Replicas initialized with distinct seeds may be independent sampling attempts but still share topology, force field, preparation and protocol. Frames are autocorrelated; counting frames as replicates underestimates uncertainty. Repeated calculations and multiple selections are sensitivity checks, not independent evidence.

## Uncertainty and convergence

Separate analysis/measurement uncertainty, finite-trajectory sampling uncertainty, between-replica variation, and upstream simulation-model uncertainty. For each observable, show a time series, estimate autocorrelation/effective sample size where appropriate, and test block averages over increasing block lengths. State interval method, block definition, trajectory duration, analyzed window and replica count. Strong block-size dependence or replica disagreement makes the result fragile or inconclusive.

Treat equilibration as an observable-specific diagnostic: inspect stage boundaries and early/late distributions or block estimates; compare independent replicas; assess whether the relevant slow motions have been sampled. A stable RMSD or radius of gyration does not prove equilibrium, convergence, stability, or binding. If production time is shorter than relevant relaxation or transition times, report the limitation rather than extrapolating.

## Controls and sanity checks

- Validate a reader/analysis pipeline on a small known trajectory or published example with known atom counts, frame count, units, and expected geometry; this checks software plumbing, not scientific truth.
- Check topology atom count/order against every trajectory, residue/chain identity, masses/charges where needed, coordinate units, frame time spacing, box dimensions, and finite coordinates before analysis.
- Run a PBC sanity check on molecules crossing boundaries; compare raw and correctly reconstructed/centered derived coordinates for the declared observable.
- Verify selections against expected atom/residue counts and inspect representative selected atoms; avoid empty selections and unintended alternate-chain matches.
- For stochastic simulation claims, retain and summarize independent replica results; a second analysis of one trajectory is not a replica control.
- Compare an independently implemented calculation or known-system result when a custom observable or transformation is introduced; disclose shared algorithms and inputs.

## Sensitivity analysis

Prespecify reasonable alternatives for fitted atoms/alignment, atom selection, reference structure, PBC unwrap/center/make-whole sequence, equilibration discard, time window, stride, clustering/fit metric, and observable definition. Report sensitivity to box handling and frame-time interpretation where relevant. A result is fragile when a qualitative conclusion, sign, rank, claim status, or threshold call changes beyond the declared tolerance across plausible choices. Report omitted alternatives; do not select a transformation after seeing which one supports the claim.

Analysis cannot compensate for upstream simulation choices. If conclusions plausibly depend on timestep, nonbonded cutoff, thermostat/barostat, box size, force-field or water model, label this dependency and request simulation-side sensitivity runs; do not imply that changing analysis settings tests those physical-model choices.

## Applicability domain

Results apply to the exact topology, sampled molecules, ensemble, replica set, simulation timescale, selections, and coordinate-processing path. MDAnalysis calculates from supplied frames; it does not validate parameterization, thermodynamic correctness, equilibration, or experimental representativeness. Analyses requiring correct bond information, masses, protonation, periodic boxes, or molecule reconstruction fail when topology metadata is missing or inconsistent. PCA, clustering, and dimensionality reduction depend on atom selection, alignment, feature scaling and sampled states; they cannot establish an exhaustive landscape from an undersampled trajectory.

## Common failure modes and detection

| Failure | Detection and response |
| --- | --- |
| Topology/trajectory atom mismatch | Compare atom counts, order, residue identifiers and representative coordinates; stop rather than truncate/reorder by guess. |
| Unit or time-axis error | Check reader metadata and known distances/frame intervals; document any conversion and preserve original values. |
| PBC artifacts or broken molecules | Inspect box vectors and boundary-crossing molecules; validate transformation order on derived data while retaining raw files. |
| Empty or unintended selection | Record selection expression and selected atom/residue counts; inspect examples and stop on unexpected membership. |
| Alignment hides motion | Report fit atoms and compare unaligned/domain-specific alternatives when the claim concerns domain movement. |
| False convergence or tiny uncertainty | Inspect per-replica traces, autocorrelation and block-size stability; downgrade if the sampled window is insufficient. |
| Analysis choice drives result | Rerun prespecified selection/window/PBC/alignment variants; report fragile claim status if conclusion shifts. |
| Double counting frames or segments | Trace segment and replica ancestry; compute uncertainty at trajectory/replica level, not as independent frame count. |

## Interpreting common observables

- **RMSD:** report fitted atoms, reference frame/structure, alignment method, units, and window. A plateau is a descriptive pattern; it does not prove equilibrium or ligand binding.
- **RMSF:** report residue/atom aggregation and alignment reference. Flexible termini or missing residues can dominate summaries and obscure localized motion.
- **Contacts and hydrogen bonds:** state distance/angle rules, atom typing, periodic-distance treatment, and occupancy denominator. Occupancy is conditional on the sampled frames and definition.
- **Radius of gyration and SASA:** state selected atoms, masses if used, solvent-accessibility method, and periodic reconstruction. These global summaries cannot identify a unique structural mechanism.
- **Clustering and dimensionality reduction:** preserve features, scaling, metric, reference/alignment, algorithm parameters, random seed, and cluster population. Display unsampled-state limits and avoid calling cluster count a count of physical states.
- **Time windows:** report both frame indices and physical time. If frames are irregularly spaced or segments have gaps, do not treat index spacing as constant time.
- Compare raw and transformed coordinate summaries when PBC operations or alignment could alter the scientific interpretation; preserve enough metadata to reproduce the transform order.
- For an observable computed per frame, retain the underlying series or an auditable path to it. An aggregate mean alone cannot diagnose drift, multimodality, or outliers.
- Use uncertainty at the level supported by the data. Block bootstrap does not create independent replicas, and too few long blocks cannot yield a reliable sampling interval.
- If an observable changes with a reasonable atom selection or alignment choice, report the alternatives and narrow the claim to the robust part of the result.
- Preserve coordinate units and time units in every exported table; conversions must be explicit and reversible.
- If topology repair or atom remapping is required, preserve the original inputs and a deterministic mapping table; unresolved correspondence is a stop condition.
- For replica summaries, use the replica as the sampling unit where appropriate and disclose unequal durations or missing intervals.
- Keep selection definitions and transformations in machine-readable configuration when possible, alongside the software version needed to replay them.
- A result for one protonation state or ligand pose applies to that state/pose unless a justified ensemble of alternatives was analyzed.
- Report discarded frames and their reason; exclusions selected after seeing a favorable outcome can bias estimates.
- Store uncertainty intervals with their estimator and data window so readers can distinguish statistical sampling uncertainty from model limitations.

## Sources

- Michaud-Agrawal et al. (2011), “MDAnalysis: A toolkit for the analysis of molecular dynamics simulations,” *Journal of Computational Chemistry* 32, 2319–2327. This describes the analysis toolkit, not correctness of a particular topology or scientific conclusion.
- Gowers et al. (2016), “MDAnalysis: A Python package for the rapid analysis of molecular dynamics simulations,” *Proceedings of the 15th Python in Science Conference*. This describes package capabilities, not validation of a specific analysis.
- Grossfield et al. (2019), “Best Practices for Quantification of Uncertainty and Sampling Quality in Molecular Simulations,” *Living Journal of Computational Molecular Science* 1(1). Use for uncertainty and sampling practice; it does not provide universal convergence thresholds.
- Allen and Tildesley (2017), *Computer Simulation of Liquids*, 2nd edition. Use for ensemble and molecular-simulation foundations; it does not validate a force field or analyzed trajectory.
