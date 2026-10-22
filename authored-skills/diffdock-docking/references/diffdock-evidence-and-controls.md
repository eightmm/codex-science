# DiffDock evidence, controls, and limits

## Claim semantics

Assign and report distinct claim classes:

- **Execution:** the pinned code/checkpoint completed the declared inference and produced schema-valid coordinates. Verify run identity, logs, atom count, and output parsing; this does not imply a useful pose.
- **Pose recovery:** one of the generated poses satisfies a prespecified symmetry-aware heavy-atom RMSD or other structural criterion against a legitimate experimental reference. Specify atom mapping, symmetry, top-k, denominator, and reference identity. The result applies to the tested inputs and protocol.
- **Confidence/ranking:** the checkpoint's confidence output orders poses according to its learned objective. Describe the exact output and checkpoint. Unless independently calibrated on a representative, disjoint dataset, it is not a calibrated probability that a pose is correct, a probability of binding, or affinity.
- **Comparative pose performance:** a frozen, leakage-controlled benchmark shows performance against declared baselines and controls. Report per-target and aggregate metrics, uncertainty, exclusions, and all generated samples; retrospective benchmark results do not establish prospective performance.
- **Experimental binding/affinity:** requires independent experimental measurements and assay conditions. DiffDock poses or confidence cannot establish this class.
- **Inconclusive or unavailable:** use unavailable when required structures/provenance are missing and inconclusive when mapping, controls, sampling, or references prevent a decisive interpretation. Preserve failures rather than converting them into negative biological evidence.

Choose top-k, RMSD thresholds, sample count, and aggregation before inspecting held-out results. Revisions after inspection are exploratory and do not replace the frozen primary analysis.

## Source dependencies and independence

Record receptor source and assembly, chain, coordinate preparation, missing residues, cofactors/metals/waters, ligand source, stereochemistry and microstates, coordinate frame, atom mapping, model repository commit, checkpoint hash, environment, inference parameters, and all random seeds. Pin the code and weights separately: a repository commit alone does not identify model behavior. Record any receptor prediction method/checkpoint and its confidence or structural uncertainty.

For benchmark claims, freeze targets, ligands, references, and split before inference. Check target-family/homology overlap, ligand scaffold/similarity overlap, exact PDB/complex reuse, and template or training-record propagation. State which overlap checks are possible and their limits; absent full training data, overlap may remain unknown. A held-out crystal pose must not influence receptor selection, cropping, ligand initialization, or postprocessing while calling the result blind pose prediction. Shared structures or derived records reduce independence; represent that lineage and avoid treating repeated versions of the same complex as independent cases.

## Uncertainty

Track structural uncertainty in predicted or experimental receptors, binding-site completeness, ligand protonation/tautomer/stereochemistry, coordinate transforms, atom mapping, checkpoint/domain mismatch, diffusion sampling, generated-pose diversity, and reference alignment. Preserve all seeds and sampled poses, not just the top-confidence pose. Report per-complex metrics and confidence distributions before pooling; state denominator and every exclusion.

Sampling spread is not automatically a calibrated interval. Confidence-score spread is not binding uncertainty and high confidence is not proof. Report model confidence as a model output and describe any independent calibration dataset, split, metric, and residual uncertainty; if absent, state calibration as unknown. Keep uncertainty from predicted receptor coordinates separate from ligand-pose uncertainty.

## Controls and sanity checks

- **Positive pose control:** run known complexes with a valid experimental reference using a frozen inference and top-k criterion. Use references only for scoring after generation in a blind benchmark; separately label any reference-informed setup as redocking or retrospective analysis.
- **Baseline control:** compare with a declared alternative pose method or a simple geometric/reference baseline on the same cases and split. Do not tune both methods on the test set.
- **Negative/sanity controls:** test atom-order or coordinate-frame corruption detection, ligand identity and stereochemistry round trips, output geometry, severe clashes, and clearly mismatched receptor/ligand inputs where appropriate.
- **Sampling control:** repeat seeds or inference draws and inspect whether top-ranked pose clusters recur; one seed cannot characterize sampling stability.
- **Leakage control:** audit sequence, scaffold, structure, and template overlap; report unknown training membership honestly.

Failure of a positive control blocks validation for the affected protocol. It does not establish that a target cannot bind the ligand.

## Pose comparison record

Define the atom correspondence before computing pose metrics. Record whether hydrogens are excluded, how symmetry-equivalent atoms are matched, which receptor frame is used, and whether receptor alignment precedes ligand comparison. Do not use a post hoc alignment or atom map that makes a failed prediction pass.

Keep the following results separate:

- **Top-1 pose success:** the highest-confidence generated pose passes the frozen criterion.
- **Top-k pose success:** at least one of the first k poses passes; record k and the number of generated samples.
- **Best-of-samples RMSD:** a diagnostic of sampling coverage, not the pose a user would receive from the ranking rule.
- **Confidence ordering:** whether higher model confidence correlates with pose success across the declared evaluation set; estimate only on cases with a valid reference and disclose the sample size.
- **Execution success:** valid outputs were generated; report separately from all pose metrics.

For each complex, retain every sample's rank, confidence value, coordinate artifact, and pose metric when a reference is available. Report the denominator for each metric independently: output-generation failures and missing reference poses may differ. Give per-target results before pooling across targets.

If the selected ligand microstate differs from the experimental reference state, explain how atom mapping and protonation affect comparison. If residues or atoms are missing, define whether they are excluded or make the reference unusable. Never silently count a missing reference as a failed prediction or as a success.

## Checkpoint and inference comparison

Treat each checkpoint, repository commit, weight checksum, and material inference change as a distinct model identity. For a checkpoint comparison, use identical structures, split, atom mapping, sample budget, and scoring criteria where the interfaces permit; record unavoidable differences. Do not choose the checkpoint on held-out test performance and then reuse that same set as independent confirmation.

Report the sample budget per complex and compute conditions. More samples can improve best-of-samples coverage even when the ranking quality is unchanged, so do not compare different budgets without labeling the comparison. Preserve every seed and report the declared selection rule rather than the most favorable run.

When confidence ranks pose correctness, report the relationship only on the cases with valid pose labels and include uncertainty around the estimate. A correlation on a small or narrow set does not calibrate per-pose confidence for other targets. Calibration on one checkpoint or split does not automatically transfer to another checkpoint or out-of-distribution chemistry.

## Sensitivity analysis

Vary random seed and number of samples, plausible ligand microstates, receptor conformations or prediction choices, and justified inference parameters such as cropping or candidate count. Keep checkpoint and primary evaluation split fixed for a configuration sensitivity analysis; evaluate another checkpoint as a separate matched method. Recheck coordinate frame, atom ordering, and symmetry mapping under conversions.

Call a result **fragile** when reasonable seeds, states, receptor conformations, or inference settings change whether the criterion passes, materially alter top-k pose success, or reorder cases at the declared acceptance boundary. Report affected targets and do not select the best seed after the fact.

## Applicability domain and failure modes

Applicability depends on the pinned model's training data, protein and ligand representation, structural quality, and benchmark distribution. Treat targets or ligands with training-set overlap uncertainty, out-of-distribution folds or chemotypes, absent/disordered pockets, large induced fit, covalent binding, unusual metals/cofactors, macrocycles, nonstandard chemistry, membrane/allosteric contexts, or poorly predicted receptor regions as outside the demonstrated domain unless separately validated. Pose prediction alone does not predict binding free energy, activity, selectivity, or experimental success.

| Failure mode | Detection and response |
|---|---|
| Confidence described as probability of binding or affinity | Trace the field to checkpoint semantics; relabel as within-model ranking and require external evidence for binding. |
| Held-out reference leaks through receptor crop or postprocessing | Trace all structure-derived inputs; reclassify as reference-informed or invalidate blind performance. |
| Training or template overlap is unknown | Audit available provenance; mark the uncertainty and restrict generalization claims. |
| Atom order, coordinate frame, or stereochemistry changes during conversion | Round-trip atom identity and coordinates; stop pose scoring until mapping is repaired. |
| Reference or symmetry mapping is invalid | Check chain, ligand identity, atom correspondence, and symmetry handling; mark pose claim unavailable. |
| Only top-confidence sample retained | Compare all generated poses and seeds; restore full sample record and report selection policy. |
| Positive controls or baseline fail | Inspect input quality and protocol; downgrade comparative claims and preserve failed cases. |
| Predicted receptor pocket is uncertain or incomplete | Inspect local structure confidence, missing atoms, clashes, and alternative conformations; qualify or stop the pose claim. |

## Source basis

This guidance is informed by Corso et al. (2023), *DiffDock: Diffusion Steps, Twists, and Turns for Molecular Docking*; Trott and Olson (2010), *AutoDock Vina: improving the speed and accuracy of docking with a new scoring function, efficient optimization, and multithreading*; and Warren et al. (2006), *A Critical Assessment of Docking Programs and Scoring Functions*. The cited methods motivate explicit pose and benchmark definitions; they do not establish validity for a new checkpoint, target, ligand distribution, or experimental affinity.
