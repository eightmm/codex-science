# Boltz structure and affinity evidence

## Claim classes and status

- **Execution:** `supported` means the pinned command completed with parseable artifacts. It is separate from scientific acceptance.
- **Local structure:** pLDDT reports model-estimated local residue confidence. It does not establish experimental accuracy or a calibrated probability that the target is correct.
- **Global topology:** pTM is a model confidence measure for global structure/topology; it does not validate a particular biological state, ligand pose, or experimental structure.
- **Interface:** ipTM is a model confidence measure for predicted inter-chain/interface arrangement. It does not prove that chains bind, that the interface exists in vivo, or that the complex is experimentally stable.
- **Docking score / pose:** treat as model-derived ranking evidence. A favorable score is not binding confirmation and depends on ligand representation, protonation, input constraints, and model calibration.
- **Predicted affinity:** a model estimate that may support prioritization only within a validated scope. It is not measured affinity, a calibrated experimental value, or proof of binding. Require independent measurements and domain-matched validation for stronger claims.
- **Biological or experimental validity:** only support with suitable external structural/biophysical evidence; otherwise `inconclusive`. Use `contradicted` only against a relevant, mapped independent observation. Missing fields yield `unavailable`, never an inferred score.

Use the shared statuses `supported`, `contradicted`, `inconclusive`, and `unavailable` per claim. Do not merge structure, interface, affinity, and process claims into one status.

## Source identity and dependence

Pin Boltz code/package version, model family, weights revision/checksum when available, entity and chain identities, ligand source and representation (SMILES or CCD), protonation/tautomer assumptions when provided, stoichiometry, MSA content and source, server-use decision, seed/sampling settings, hardware, and hashes. Retain the exact input and command. Boltz predictions, confidence heads, docking scores, and predicted-affinity outputs from one run are dependent outputs, not separate confirmations. An MSA server may contribute homolog evidence that overlaps public databases or training data; log MSA provenance. Redocking the known ligand into its own known structure is a pipeline control, not an independent target validation. Different model versions or methods may share training structures and benchmark leakage; check benchmark split and target-family overlap.

## Carrying uncertainty

Report only metrics present in validated output, with units, chain/entity mapping, and model version. Carry uncertainty from sequence/ligand identity, protonation, conformational state, MSA source, stochastic sampling, model-version changes, and benchmark scope. For affinity, report the model's stated output and scale exactly; do not convert a ranking score to experimental units. Record seed and sample count, between-sample spread when repeated sampling is available, and missing/null outputs. Distinguish model confidence from empirical error estimates and process completion from scientific acceptance.

## Controls and sanity checks

- **Positive structural control:** a known complex from a documented benchmark, with the same ligand chemistry and a compatible input protocol; check chain/ligand mapping and structural recovery. Report target overlap and benchmark split.
- **Redocking control:** where a native complex is available, remove and re-predict the ligand under a declared protocol; compare pose to the known coordinates with the stated metric. This validates a pipeline on that control only.
- **Negative/decoy control:** use chemically plausible decoy ligands or nonbinding pairs with documented labels to check whether scores separate controls in the tested set. Do not claim biological specificity from synthetic decoys alone.
- **Input sanity:** confirm atom/residue mapping, bond orders, stereochemistry, chain stoichiometry, finite coordinates, clashes, and expected output schema. Verify affinity head applicability to this entity type and assay domain.
- **Independent validation:** compare predicted affinity with experimentally measured binding data for matched targets and assay conditions; keep calibration, assay noise, and train/test overlap explicit.

## Sensitivity and fragility

Vary seed/sampling count, MSA supplied versus absent (only when permitted), alternative valid protonation/tautomer or ligand representations, model/weight version, and justified input-state assumptions. Compare pose, interface, and affinity separately on mapped entities. A conclusion is **fragile** if reasonable variants reverse binder ranking, change pose beyond the prespecified acceptance threshold, or materially alter the interface/claim. Prespecify metrics and thresholds from benchmark protocol where available; otherwise label criteria exploratory. Sampling spread is not a confidence interval for experimental affinity.

## Applicability and failure modes

Applicability is bounded by training-set overlap, target and ligand distribution, supported entity types, chemistry, complex size, input representation, and the model version. Out-of-distribution proteins, unusual covalent chemistry, uncommon modifications, ambiguous tautomers/protonation, flexible ligands, membrane/assembly context, alternate conformations, and complexes or ligands outside the validated benchmark scope can invalidate interpretation. A plausible pose does not resolve these limits. Public MSA transmission is inappropriate for proprietary or sensitive sequences without explicit approval; use a supplied MSA where authorized.

Detect common failures: wrong entity/chain map via input/output audit; ligand chemistry loss via canonical identity and atom mapping; false interface certainty via ipTM/pose versus known complexes or decoys; affinity overclaim via absent matched assay validation; MSA leakage via provenance and split audit; version drift via code/weights manifest; instability via seed/sampling and MSA sensitivity; and false success via exit code plus output schema/hash verification. Classify input, configuration, resource, and infrastructure failures separately, bound transient retries, and retain cancellations and failed outputs.

## Interpreting structure and interface outputs

Keep residue-local pLDDT, global pTM, and interface ipTM as separate columns and claims. Explain the entity scope for each score and do not compare values across versions unless their definitions and calibration are known to match. A high ipTM can prioritize an interface for testing; it cannot establish binding, stoichiometry, cellular context, or energetic stability.

Inspect coordinates for chain completeness, ligand placement, atom mapping, bond geometry, clashes, and consistency with supplied constraints. State any minimization or postprocessing applied after prediction; those operations create a derived structure and must be versioned separately. Do not hide an invalid ligand pose by silently repairing chemistry.

If a field is absent, preserve it as missing. Do not reconstruct affinity from docking score or infer confidence from coordinate appearance. Record score direction and units exactly as documented by the installed model version.

## Affinity and assay evidence

Before interpreting predicted affinity, identify the target/ligand scope, output scale, and intended use (ranking, classification, or quantitative estimate). Compare only to assays with compatible endpoints, units, temperature/conditions, and target constructs. A model trained for one assay/domain may not transfer to another.

For a calibration set, freeze the split before analysis and cluster by target family and ligand series to reduce leakage. Keep near-duplicate complexes and propagated measurements in one partition. Report sample size, missing/failed predictions, metric definition, calibration procedure, and uncertainty. A high correlation on a small or overlapping benchmark does not provide calibrated affinity for a new target.

If only ranking has been evaluated, report rank agreement rather than a measured value. If benchmark performance is unavailable, treat affinity as exploratory. Do not infer a binding free energy or convert predicted scores to experimental units without a validated transformation and independent calibration.

## Redocking, decoys, and positive controls

For redocking, preserve the native complex identity, ligand atom mapping, receptor preparation, protonation, search settings, and pose metric. Compare predicted and reference poses after an explicitly defined alignment. Recovery on the native ligand tests whether the pipeline can reproduce that case; it does not estimate prospective success for other targets.

Choose decoys that preserve relevant chemical properties when evaluating discrimination, and retain how decoys were constructed. Easy decoys can make a model appear selective without demonstrating binding specificity. Include known nonbinders or orthogonal experimental negatives when available. Keep positive/negative labels and assay provenance auditable.

## Decision thresholds and downgrade rules

Predeclare what pose, interface, or affinity change matters for the intended decision. Use benchmark-derived thresholds where they match the target domain; otherwise identify thresholds as exploratory and report the underlying values. A confidence score threshold is not a universal binder classifier.

Downgrade pose claims when ligand identity, atom mapping, or chain assignment is uncertain. Downgrade interface claims when the complex is outside tested scope or only one sample supports the pose. Mark affinity inconclusive without matched measured validation. Mark applicability uncertain when training overlap, MSA provenance, or benchmark composition cannot be checked. Keep process success separate from each downgraded scientific claim.

Before handoff, check that:

- each confidence metric is attached to the correct claim class;
- ligand and chain mappings match both input and output;
- the model and weight versions are retained with the artifact;
- MSA use and any server approval are recorded;
- predicted scores retain their documented scale and direction;
- controls include their identity, purpose, and benchmark split;
- all seeds and failed samples remain represented;
- affinity results name the assay scope or state that validation is absent.

## Source basis

- Wohlwend et al. (2024), *Boltz-1: Democratizing Biomolecular Interaction Modeling*, describes open biomolecular interaction modeling and its benchmark framing; benchmark performance is not per-target experimental validation.
- Boltz model and CLI documentation (Boltz project, version used) defines supported inputs and output fields; verify the installed release rather than assuming a metric exists.
- Jumper et al. (2021), *Highly accurate protein structure prediction with AlphaFold*, and Lin et al. (2023), *Evolutionary-scale prediction of atomic-level protein structure with a language model*, provide context for model-confidence methods, not validation of Boltz-specific affinity estimates.
