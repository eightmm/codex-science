# PLIP geometry and evidence

## Claim classes

- **Detected geometric interaction:** PLIP assigns a contact under its versioned chemical typing and geometric rules. Report the interaction type, participating atom and residue identifiers, distance and any angular measure emitted by the pinned release. This supports only “the supplied coordinates meet this rule.”
- **Cross-structure comparison:** a prespecified interaction feature differs between structures after compatible ligand identity, atom mapping, receptor state, preparation, and software version are established. This supports a structural difference, not a change in affinity.
- **Trajectory occupancy:** a classified interaction is present in a defined fraction of sampled frames under a stated rule. The denominator is analyzed frames; uncertainty must account for temporal dependence or independent replicas. Occupancy does not establish thermodynamic population unless sampling and the estimand justify that interpretation.
- **Energetic, binding, affinity, or mechanism claim:** PLIP alone cannot assign these classes. Such claims require independent, claim-appropriate experimental or validated computational evidence and their own uncertainty and controls.

Set a claim's status to **supported** only when the declared analysis contract passes and its evidence meets the claim class; **contradicted** when valid evidence opposes the prespecified claim; **inconclusive** when relevant evidence cannot discriminate; and **unavailable** when a required input, measurement, or source is absent. Do not use “supported” to mean biologically true.

## Interaction typing and geometric rules

Pin the PLIP release and use its own documented typing rules and cutoffs. Save raw PLIP output so a future release can be compared. Do not silently substitute generic distance cutoffs for PLIP's type-specific criteria.

- **Hydrogen bonds:** donor/acceptor typing, donor-hydrogen-acceptor geometry, and distance depend on atom typing, protonation, and hydrogen placement. Record the reported donor, acceptor, distance, and angle when present.
- **Hydrophobic contacts:** report the atom pairs classified as hydrophobic by the pinned rules and their distances. A close nonpolar pair is not a free-energy contribution.
- **Pi-stacking:** retain the participating aromatic groups and the reported centroid separation, plane angle, and offset or equivalent release-specific geometry. Ring definition and alternate conformations can change assignment.
- **Salt bridges:** report charged atom groups and distance criteria. Protonation and formal charge assignment can change whether a group is eligible.
- **Halogen bonds:** report halogen and acceptor identity, distance, and directionality where available. Element identity alone does not establish a halogen bond.
- **Water bridges:** report the water identity and both legs of the bridge. Waters omitted from a model cannot be treated as absent in the physical system.
- **Metal coordination:** report metal identity, coordinating atoms, distances, and retained ligands/waters. Keep coordination distinct from the six interaction families above and do not infer oxidation state or coordination chemistry from proximity alone.

PLIP's classifications are operational labels for coordinates, not universal physical boundaries. Record numeric geometries and pinned thresholds whenever the release exposes them; if exact criteria are not exposed by a release, state that limitation rather than inventing a cutoff.

For reference, PLIP 3.0.1's configuration lists the following defaults. These values are version-specific, not universal definitions; inspect the configuration bundled with the pinned executable and save it with the run:

| Interaction | Default geometric rule in PLIP 3.0.1 |
| --- | --- |
| Hydrophobic | eligible hydrophobic atom pairs within 4.0 Å, followed by redundant-contact filtering |
| Hydrogen bond | donor-acceptor distance under 4.1 Å and donor angle at least 100° |
| Pi-stacking | ring-center distance up to 5.5 Å, angle within 30° of parallel/perpendicular geometry, offset up to 2.0 Å |
| Salt bridge | opposite charge centers within 5.5 Å |
| Halogen bond | distance under 4.0 Å; donor angle centered at 165° and acceptor angle at 120°, each with 30° deviation |
| Water bridge | water oxygen to polar atom from 2.5 to 4.1 Å; omega 71° to 140° and theta at least 100° |

Treat values as part of the analysis configuration. A PLIP web run may not expose threshold changes available in a local command-line run; state which execution route was used. An interaction just inside a cutoff is not categorically more meaningful than one just outside it.

Pi-cation interactions are separate from pi-stacking. PLIP 3.0.1 uses a charge-center to ring-center distance up to 6.0 Å and a ring offset up to 2.0 Å, with extra angle handling for some tertiary amines. Keep these records separate when counting or comparing interaction classes.

## Reading the interaction records

Retain the PLIP output's donor/acceptor identities, atom indices, interaction centers, geometry, ligand and receptor residue identifiers, and the version metadata. Do not reduce records to counts when atom- or group-level evidence is available. Counts depend on filtering, typing, and ligand selection, so equal counts can describe different contacts and unequal counts do not measure affinity.

PLIP may add polar hydrogens, select models/alternate positions, fix input structures, classify ligands, and remove redundant contacts. Record these transformations and warnings from the output. Where the input workflow already set protonation or alternate locations, inspect whether PLIP changed them again. A correct XML parse does not establish that PLIP selected the biologically intended ligand or assembly.

For each run, store the effective threshold configuration, not only a command-line string: configuration files and defaults can change across releases. If the run used thresholds other than defaults, report both values and the scientific reason for varying them. Keep the default result as the primary analysis unless a different rule was prespecified.

Do not silently compare interaction lists generated by different PLIP releases. First normalize the source and preparation records, then run both versions on the same fixed inputs if a version comparison is needed. Report additions, removals, and changed geometries by interaction identity; a version difference is software sensitivity, not biological evidence.

When comparing experimental and predicted structures, stratify by provenance and coordinate confidence. A predicted pose that meets an interaction cutoff remains a predicted geometric feature. Crystal contacts, unresolved density, model refinement, and predicted confidence have different evidential meanings and must not be collapsed into one category.

## Source dependencies and independence

Record structure accession or file hash, source database/release, experimental versus predicted provenance, model/assembly, chain identifiers, ligand identifiers, atom mapping, and any biological assembly transformation. For crystallographic models include available resolution and model validation context; for predicted models retain the prediction source, model version, and confidence fields with their meaning. Do not treat multiple chains, crystal copies, models from one prediction, docked poses derived from one template, or frames from one trajectory as independent observations.

Interaction records depend on the same coordinate model and often on common preprocessing: protonation and hydrogen placement, alternate-location selection, missing-atom repair, water retention, residue/ligand typing, and PLIP version. Shared parent structures or propagated coordinates must be explicit in the evidence graph. Pin release/version and preserve both the original input and transformed input hashes.

## Uncertainty and controls

For a single structure, report coordinate/model uncertainty and unresolved atom or state ambiguity qualitatively; do not fabricate a statistical interval for one deterministic geometry run. For a comparison, report whether the result survives alternate plausible preparations. For trajectories, define the estimand and frame denominator, retain replica identity, and estimate uncertainty with block/autocorrelation-aware resampling or independent-replica variation. Report exclusions and missing frames.

Use a known co-crystal complex with curated, expected interaction types as a positive workflow control when a suitable system exists. Compare recovered types and atom identities against the stated reference, allowing for release-specific differences. Use a ligand-free or nonbinding-site selection, or a chemically plausible decoy with known limitations, as a negative/sanity control; do not claim a decoy is experimentally nonbinding without evidence. A failed control invalidates the corresponding detection claim until diagnosed.

## Sensitivity and fragility

Repeat the analysis across chemically plausible protonation and tautomer states, hydrogen placement or addition settings, alternate-location choices, and retained/omitted ambiguous waters. Vary the relevant type-specific thresholds only as a declared sensitivity analysis around the pinned default, not as a way to select favorable contacts. For comparisons, apply identical alternatives to both sides.

Call a result **fragile** when a claim's direction, key interaction type, principal residue/atom assignment, or conclusion changes under a plausible alternative. Report which choices cause the change and downgrade the claim to inconclusive when they are unresolved. For trajectory occupancy, vary frame stride/block size and compare replicas; large shifts relative to the stated uncertainty indicate inadequate sampling or fragile occupancy.

## Applicability domain and failure detection

The method describes typed contacts in supplied coordinate structures. It does not estimate binding free energy, rank affinity, identify causal mechanism, or compensate for absent conformational states. Predictions, docked poses, low-resolution models, cryo-EM models, and crystal structures have distinct coordinate uncertainty and experimental context; preserve those labels instead of pooling them as equivalent.

Detect common failures by checking: ligand atom identity/mapping against the source record; duplicate or unexpected ligand copies; missing atoms and alternate locations; protonation and hydrogens for donor/acceptor typing; water/metal retention; parser warnings and empty outputs; chain/assembly choice; PLIP release and command; trajectory coverage, autocorrelation, and replica agreement. Treat unresolved mapping, invalid chemistry, incompatible preparation, or failed positive controls as unavailable or inconclusive, not as zero interactions.

## Sources

- Salentin et al. (2015), “PLIP: fully automated protein-ligand interaction profiler,” *Nucleic Acids Research*.
- Schake, Bolz et al. (2025), “PLIP 2025: introducing protein-protein interactions to the protein-ligand interaction profiler,” *Nucleic Acids Research*; its official PLIP 3.0.1 configuration defines the versioned defaults summarized above.
- wwPDB (2019), PDBx/mmCIF dictionary and archive data model; use it for structure identity and metadata conventions, not for claims of biological activity.
