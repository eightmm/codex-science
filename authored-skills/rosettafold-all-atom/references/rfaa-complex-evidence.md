# RoseTTAFold All-Atom complex evidence protocol

## Claim semantics

Assign stable claim IDs before interpreting output:

- **Predicted arrangement:** the pinned RFAA pipeline emitted coordinates for a declared set of entities. This supports only a claim about the model output after input/output validation.
- **Structural agreement:** the prediction matches a named experimental structure under explicit assembly, chain/atom mapping, alignment, and metric. Keep the observed structure as the experimental evidence and the model as a prediction.
- **Interface plausibility:** chain-pair confidence/PAE, contacts, and chemically plausible geometry justify further testing. Report pairwise outputs such as `pae_inter` at their emitted scope; do not treat them as binding probability.
- **Binding or affinity:** require independent experimental interaction or affinity evidence. Predicted docking, high confidence, and restraint satisfaction cannot establish this class.
- **Ligand/covalent plausibility:** correct atom mapping, stereochemistry, valence, covalent linkage, coordination, and local geometry support chemical plausibility only. PoseBusters-style checks can flag defects but do not establish the native pose.

Use statuses consistently: `planned`, `supported`, `contradicted`, `inconclusive`, `unavailable`. Use inconclusive for mixed, fragile, or underpowered evidence and unavailable for absent required inputs/metrics/evidence. Retain null and failed candidates.

## Source dependencies and independence

Pin the RFAA commit, checkpoint checksum and terms, PDB/template and sequence database snapshots, container, SignalP version/terms, and all other separately licensed dependencies. Record training cutoff and known exact/close complex overlap for the specific checkpoint; unknown remains unknown. Inspect both partners and complexes, including propagated structure records, rather than checking only the target chain.

A structure used to make the MSA/template, restraint, or input cannot independently validate the resulting pose. Record shared experimental preparation, biological assembly, homologous complex, or propagated PDB provenance. Multiple seeds, cycles, and sampled candidates are dependent model outputs. Cross-model concordance is weakened by shared training structures, template sources, and preprocessing.

For benchmark claims, freeze the evaluation split and cluster by sequence/structure relationship and complex source before inference. Record exact cutoff, exclusions, unresolved overlaps, and data dates. Never describe a test as held out when a related complex or derived record may have entered training.

## Uncertainty and confidence

Report raw residue-local and pairwise outputs separately, with chain/atom maps and units. `pae_inter`, pLDDT, and any interface score describe model confidence behavior; none is an experimental assay or calibrated probability by default. Preserve per-chain-pair results instead of averaging away a weak interface.

Carry uncertainty from chemical identity, stereochemistry, protonation, metal coordination, covalent bond mapping, construct/assembly, MSA/template coverage, training overlap, stochastic inference, and reference resolution. Label each input assumption and its provenance. Quantitative bounds require an explicitly comparable validation set and method; otherwise state the uncertainty qualitatively.

### Candidate and chemistry review record

For every chain pair, record the exact chain mapping, emitted `pae_inter` or other pairwise field, units/interpretation from the pinned version, contact definition, and candidate rank. Preserve separate partner-pair results. A global mean can hide a weak or incorrectly mapped interface and must not be the sole quality summary.

For ligand and covalent cases, retain the original SDF/SMILES and a machine-readable atom map into the output. Compare stereocenters, bond orders, charge, aromaticity, tautomer/protonation assumptions, covalent attachment, and metal coordination. Run chemical sanitization and a PoseBusters-style geometry/clash review where applicable; report each check rather than one aggregate pass. Do not silently protonate, remap, or repair a candidate and then call it the original prediction.

For MSA/template provenance, identify the database snapshot, template records, date, and generation procedure. If source data are inaccessible, record that boundary; it prevents a strong independence or leakage claim. For a held-out evaluation, cluster target and partner chains and complex-level source records before assigning splits.

When comparing an experimental structure, record the holo/apo state, resolution and missing segments, biological assembly, symmetry choices, and chemical component mapping. Apply the same atom/residue inclusion rule to all candidates and retain exclusions so the reported agreement is reproducible.

## Controls and sensitivity

Test withheld known complexes for recovery under a declared chain mapping and metric. Use apo forms or unrelated/decoy partners matched for sequence length, available MSA, and compute where possible. Include negative/no-ligand controls where the hypothesis permits. Report whether controls were selected before or after inspecting predictions.

Retain every seed, cycle, sample and failure. Compare interface clusters and ligand poses rather than only the selected top score. Vary MSA/template availability, restraints, seeds, and sampling/cycle budget one factor at a time; use matched compute for baseline comparisons. A claim is fragile when partner, topology, rank, stereochemistry, or status changes under plausible settings. Report the full spread and the selection policy.

### Decision rule

Support a geometry-plausibility claim only after chain and atom maps pass, the relevant covalent/metal/ligand checks pass, and control behavior is not inconsistent with the proposed interface. Otherwise mark it `inconclusive` or `unavailable`, preserve the failure, and name the discriminating evidence still needed. No such outcome establishes binding without independent experimental evidence.

### Confidence, MSA, and sampling interpretation

Use per-chain and per-interface evidence at its actual resolution. A whole-complex average can conceal a weak partner pair or a chemically invalid ligand. If a metric is missing for the pinned release, record it as unavailable and rely on explicit geometry or control checks only within their stated scope.

MSA and template records are evidence dependencies as well as model inputs. Record whether the target, partner, or complex itself is represented. Changing database snapshots changes both information content and possible leakage; do not attribute a result change solely to model behavior without acknowledging that dependency.

Count candidate diversity by unique interface/pose clusters under a stated criterion. More cycles or seeds increase computational opportunity and selection; report requested/completed budgets and all failures. Convergence across seeds is reproducibility under one pipeline, not independent experimental confirmation.

### Reporting boundary

Report prediction, structural agreement, chemical validity, and measured interaction as separate evidence lanes. Include the source or artifact for each, shared dependencies, and the unresolved uncertainty. Missing experimental evidence must remain visible even when structure and geometry checks are favorable.

## Applicability and failure detection

Use only entity and chemistry types represented by the pinned RFAA release and inputs. Metal coordination, covalent chemistry, nucleic acids, membrane context, disordered partners, and unusual cofactors may be poorly represented or unsupported; verify each rather than extrapolating from broad all-atom scope. Do not infer cellular function, binding kinetics, or affinity from one model output.

| Failure mode | Detection and response |
|---|---|
| Atom or chain mapping error | Reconcile normalized input/output sequences, atom IDs, bond indices, and chain IDs; stop affected claims. |
| Wrong ligand stereochemistry or state | Compare canonical chemical identity, stereocenters, charge/protonation, bond order, and atom map; do not silently repair. |
| Metal/covalent geometry defect | Inspect coordination distances, valence, bond geometry, and chemistry-specific constraints; flag or mark unavailable. |
| Template/training overlap | Track database dates and related complex records; label retrospective evaluation contaminated or uncertain. |
| Confident wrong interface | Use pairwise metrics, known-complex controls, apo/decoy partners, and independent structure/assay evidence. |
| Constraint-driven agreement | Keep restraints and their source explicit; treat output as conditional and compare restraint-free run where valid. |
| Best-sample bias | Retain sample count, all candidates, ranking rule, failures, and budget-matched comparisons. |
| License or dependency violation | Verify checkpoint, SignalP, database, and container terms before use; stop if permission or terms are unresolved. |

## Sources

- Krishna et al., **Generalized biomolecular modeling and design with RoseTTAFold All-Atom** (2024, Science): model scope and predicted atom/residue confidence; it does not establish experimental validity for a target.
- Baker Lab, **RoseTTAFold All-Atom** source repository and license (versioned): code/weight conditions and execution requirements; check the exact revision used.
- Jumper et al., **Highly accurate protein structure prediction with AlphaFold** (2021): pLDDT and PAE interpretation as prediction confidence.
- Basu and Wallner, **DockQ: A Quality Measure for Protein-Protein Docking Models** (2016): reference-based interface quality.
- Buttenschoen et al., **PoseBusters: AI-based docking methods fail to generate physically valid poses or generalise to novel sequences** (2024): ligand pose validity tests.
