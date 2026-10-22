# Vina evidence, controls, and limits

## Claim semantics

Assign one class to each material claim and keep classes separate in the report:

- **Execution:** the pinned program completed the declared inputs and emitted parseable poses. Require exit status, input/output identity, and retained logs. This says nothing about pose correctness.
- **Pose recovery:** the generated pose meets the prespecified symmetry-aware heavy-atom RMSD or task-specific structural criterion against a legitimate experimental reference. State atom mapping, symmetry handling, atom inclusion, threshold, and denominator. This is retrospective evidence for the tested complex and setup.
- **Comparative ranking:** a frozen score/order separates prespecified actives from decoys or ranks ligands in a defined, leakage-controlled set. Report the full set, metric, uncertainty, exclusions, and baseline. A ranking result is not prospective enrichment unless the test is prospective.
- **Experimental binding or affinity:** requires independent experimental evidence with assay, conditions, and uncertainty. Vina energy or pose recovery cannot assign this class.
- **Unavailable or inconclusive:** use unavailable when required reference or provenance is absent; use inconclusive when attempted evidence is ambiguous, underpowered, or controls fail. A failed run is not a negative biological result.

Do not select RMSD cutoff, top-k, score, or subset after viewing results and then report it as confirmatory. If an exploratory criterion changes, preserve the original and label the new analysis exploratory.

## Source dependencies and independence

Record the PDB accession or coordinate source, chain/assembly, experimental method and resolution when supplied, receptor preparation, protonation/charge choices, retained waters, cofactors and metals, ligand source and stereochemistry, microstates, and all conversion tools. Pin Vina/Meeko releases and record binary or container digest where available. Scores from different versions, scoring functions, preparation pipelines, boxes, or ligand-state enumerations are not interchangeable without a matched comparison.

For benchmark claims, freeze split membership before docking. Group related proteins by target or sequence/homology policy and related ligands by scaffold or other declared chemical-similarity policy when the question is generalization. Detect exact structure/ligand reuse and propagated records from the same source. A redock uses the bound ligand to define the receptor preparation or search only when that use is explicitly part of the redocking protocol; it cannot also serve as independent evidence of blind prospective prediction. Record shared receptor templates, structures, ligand series, and preparation code in the evidence graph.

## Uncertainty

Carry per-case uncertainty from receptor conformation, unresolved residues, protonation and tautomer states, stereochemistry, waters, ligand flexibility, search stochasticity, pose multiplicity, and reference/atom mapping. Report the number of states, seeds, poses, and attempted complexes. Summarize the distribution across prespecified state or seed runs rather than the best-scoring pose alone. Distinguish numerical/search variability from structural and model uncertainty; do not turn score spread into a calibrated probability of binding or affinity.

For small screens, report the full per-ligand table and avoid population-level confidence claims from a tiny or selected set. Preserve failed preparations and docking runs in the denominator or state the exact denominator and reason for exclusion.

## Controls and sanity checks

- **Positive pose control:** redock a known co-crystallized ligand into a prepared receptor, with atom mapping verified and a predeclared symmetry-aware pose criterion. Keep the native reference out of any step described as blind prediction.
- **Cross-docking control:** where relevant, dock a ligand into a different experimentally determined receptor state and report the receptor/ligand pairing; success in self-docking does not establish cross-state robustness.
- **Ranking controls:** include known actives and chemically/property-matched decoys, plus a simple baseline such as random ordering or the declared non-docking comparator. Record provenance and construction rules for decoys; decoys are not confirmed inactives.
- **Sanity checks:** verify box coverage, atom counts and charges, plausible bond geometry, absence of conversion-induced stereochemical changes, pose clashes, and parse consistency between logs and SDF/PDBQT properties.

A failed positive control blocks a claim that this setup is validated for the evaluated cases. It does not prove the target is undruggable or the hypothesis false.

## Result summaries and screening decisions

For pose recovery, state whether the reported pose is top-ranked, any-of-top-k, or selected by a rule fixed before scoring. Report the reference structure and atom-selection policy alongside RMSD; ligand symmetry and alternative binding modes can change the numeric result. A pose passing the criterion does not establish that its score is calibrated.

For a ranking task, predeclare the ligand population, activity labels, ranking direction, primary metric, baseline, and any tie handling. Report per-target and pooled results separately when target composition can change the pooled value. Include attempted, scored, failed, excluded, active, and decoy counts so readers can reconstruct each denominator.

Treat enrichment factors as dependent on the chosen active fraction and decoy construction. Show the screening fraction and report a metric that uses more of the ranked list when the sample size permits. Do not claim prospective enrichment from a retrospective set whose labels or composition influenced preparation or score selection.

Use the following interpretation checks before writing a conclusion:

- A lower Vina energy is only a preferred score under the selected scoring function and configuration.
- Agreement with the crystallographic pose tests pose recovery under the tested preparation and search; it does not validate affinity ranking.
- Stable poses across seeds test search reproducibility, not model correctness or biological persistence.
- A favorable rank against decoys is conditional on that target set, decoy protocol, and split.
- A score difference without a predeclared threshold or calibration should be reported as a difference in model score, not a meaningful free-energy difference.
- Missing failures or denominators make benchmark summaries incomplete; retain the case table or label the summary unavailable.

## Preparation choices that change the question

Receptor protonation, histidine state, terminal treatment, retained waters, alternate conformations, missing side chains, and metal coordination can change pocket geometry and score. Record each choice and its source; do not silently repair an input based on the preferred docked pose.

Enumerate chemically plausible ligand tautomers, protonation states, and stereoisomers when they are uncertain and relevant to the assay conditions. Keep each prepared state linked to its source structure and preparation rule. Do not report the best-scoring state as though it were the experimentally populated state.

If the intended biological target requires a cofactor, metal, conserved water network, oligomer interface, or induced-fit rearrangement that the selected setup omits, mark the applicability boundary explicitly. A technically valid pose can still reflect the wrong chemical or biological state.

## Sensitivity analysis

Before inspection, choose a manageable grid over search seeds and exhaustiveness; vary box center/size within a justified pocket boundary; repeat plausible receptor and ligand protonation/tautomer states; and compare top-k or pose clustering under the declared atom mapping. For ranking claims, also vary the prespecified receptor conformation set and test the agreed score aggregation rule. Keep the primary configuration frozen and label all perturbations.

Call a conclusion **fragile** when plausible state or search choices reverse the pose-success call, materially change the ligand ordering under the prespecified metric, or move the result across its declared acceptance boundary. Report that boundary and the affected cases; do not hide fragility by averaging incompatible states.

## Applicability domain and failure modes

Vina is an approximate scoring/search method for prepared structures and a defined pocket. Results may not transfer to disordered or missing binding sites, major induced fit, covalent binding, unusual metals/cofactors, membrane or allosteric contexts, macrocycles, highly charged or nonstandard chemistry, unresolved alternate states, or protein/ligand conditions outside the chosen preparation and validation set. Treat whole-protein blind search as exploratory unless independently benchmarked.

| Failure mode | Detection and response |
|---|---|
| Wrong receptor assembly, chain, or pocket | Compare structure metadata and box coordinates to the frozen target; stop and repair provenance before docking. |
| Incorrect atom map, stereochemistry, charge, or microstate | Round-trip structures and inspect atom-level identity; mark affected cases unavailable until corrected. |
| Box truncates the pocket or ligand motion | Inspect box bounds and control pose; rerun only under a recorded, justified configuration. |
| Reference pose leaks into a blind test | Trace pocket, receptor, and ligand initialization sources; reclassify as redocking or invalidate the blind claim. |
| Positive control fails or decoys are trivial | Check control composition, preparation, and scoring behavior; downgrade validation/ranking claims and retain results. |
| One seed or top score drives conclusion | Inspect per-seed poses, clusters, and score distribution; report instability and avoid best-of-many selection. |
| Score is described as affinity or calibrated confidence | Compare language and output fields to the claim class; revise to model-score description. |

## Source basis

The procedure is informed by Trott and Olson (2010), *AutoDock Vina: improving the speed and accuracy of docking with a new scoring function, efficient optimization, and multithreading*; Eberhardt et al. (2021), *AutoDock Vina 1.2.0: New Docking Methods, Expanded Force Field, and Python Bindings*; and Warren et al. (2006), *A Critical Assessment of Docking Programs and Scoring Functions*. These sources motivate explicit search/scoring scope and benchmark controls; they do not establish validity for a particular target or ligand set.
