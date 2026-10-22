# Chai-1 complex evidence protocol

## Claim semantics

Assign each claim a stable ID and one class before examining candidates:

- **Predicted arrangement:** the pinned model generated a specified chain/ligand arrangement. Support requires valid inputs, successful inference, and retained coordinates; it says nothing by itself about truth.
- **Structural agreement:** a candidate agrees with an experimental reference under a declared chain mapping, atom/residue selection, and metric. Record reference release, exclusions, alignment protocol, and metric; do not call a predicted coordinate set experimental.
- **Interface plausibility:** chain-pair confidence, contacts, geometry, and control behavior make an interface worth testing. Report ipTM or its emitted counterpart, interface PAE, and chain-pair metrics separately; do not convert them to binding probabilities.
- **Binding or affinity:** experimental assay, perturbation, or other independent interaction evidence is required. A Chai prediction, high confidence, or restraint satisfaction alone cannot support this class.
- **Ligand-pose plausibility:** correct chemical identity/stereochemistry, acceptable internal geometry, and absence of severe protein clashes support physical plausibility only. Passing PoseBusters-style checks does not identify the correct pose.

Use consistent statuses: `planned`, `supported`, `contradicted`, `inconclusive`, `unavailable`. A claim is `inconclusive` when evidence is mixed or underpowered; use `unavailable` when required inputs, metrics, controls, or experimental evidence cannot be obtained. Retain negative results.

## Source dependencies and independence

Pin the Chai code/release, weights/checksum and terms, input schema, databases, MSA/template sources, and inference settings. Record model training cutoff and known target/partner/complex overlap for the exact release; unknown is a reported uncertainty, not proof of no leakage. Search for exact complex and close homologs on both chains, not only target sequence identity.

An experimental structure used as template, restraint source, or input cannot independently validate the resulting arrangement. Distinguish the same PDB entry, propagated structure, homologous complex, and genuinely separate experimental preparation. Count samples, seeds, and model variants as dependent predictions, not independent biological evidence. Shared training data, templates, and preprocessing weaken apparent agreement between predictors.

For benchmarks, group related complexes by shared biological assembly, sequence/structure homology, and propagated PDB records before splitting. Freeze the split and cutoff before scoring; report excluded, ambiguous, and post-cutoff records.

## Uncertainty and confidence

Report raw model metrics with their scope: residue-local confidence, interface PAE, global/interface score, and chain-pair score are not interchangeable. Preserve per-chain-pair values and mapping; a multimer-wide mean may hide a weak partner pair. State that scores are model confidence signals unless external calibration on a matching population and protocol supports stronger language.

Carry uncertainty from entity mapping, protonation/tautomer state, oligomeric state, MSA depth/composition, template availability, stochastic sampling, cutoff overlap, and experimental reference resolution. Use qualitative rationale or empirical intervals only when their construction is stated. Do not turn a rank among sampled candidates into calibrated confidence.

### Candidate-level review record

For each chain pair, retain the chain names, direction of mapping, interface metric name/version, interface PAE scope, and residue/contact definition. Record missing metrics explicitly; do not infer an absent chain-pair score from an overall confidence value. Compare confidence with geometry and known-complex controls rather than treating metrics as votes that can be summed without calibration.

For MSA comparisons, preserve source, query date, search parameters, filtering/deduplication policy, sequence count, effective depth if emitted, and whether templates were enabled. A single-sequence run tests a different information condition; it is not a control for every effect of MSA. Report whether a conclusion is stable across modes and whether candidate budgets were equal.

For ligand assessment, verify that the predicted atom map still represents the input chemical graph, including stereocenters, aromaticity, formal charge, and covalent attachment. Record each validity check and its failure. Geometric validity is necessary for a usable candidate but cannot establish biological occupancy, protonation in situ, or binding free energy.

For an experimental comparison, define the assembly and biological state before alignment. Report missing residues, unresolved chains, alternate conformations, ligand occupancy, symmetry handling, and any excluded atoms. Do not select the reference chain or alignment after seeing which choice improves agreement without labeling that analysis exploratory.

### Decision rule

Support a structural-plausibility claim only when input mapping is valid, the reported interface is stable enough for the intended use, and no decisive control or geometry failure contradicts it. Otherwise mark it `inconclusive` or `unavailable` and state what evidence would discriminate the alternatives. This rule does not promote a structure-prediction claim to a binding claim.

### MSA and sampling interpretation

An MSA can add evolutionary information but also carries database, homolog-selection, and leakage dependencies. Report whether close partner homologs or known complex sequences appear in the alignment. A single-sequence result can test robustness to alignment availability, but cannot isolate every modeling difference unless all other inference settings are held fixed.

Candidate diversity should be measured from declared interface or structural clusters, not inferred from the number of output files. Retain per-seed confidence and structural representatives. If all seeds converge, state that convergence is within this model and sampling setup; it is not independent replication.

### Reporting boundary

Present model confidence, geometry, reference agreement, and experimental interaction evidence in separate columns. State the evidence lane supporting each claim and the main dependency shared with any comparison model. If a required lane is absent, do not fill its place with model confidence.

## Controls and sensitivity

Use known complexes with blinded or declared reference coordinates as positive recovery controls. Use plausible apo partners, unrelated decoy partners, or chain-swapped partners as negative controls; keep controls matched for size, MSA availability, and sampling. A control set assembled after seeing predictions is exploratory and must be labeled.

Run paired seeds and retain all candidates. Report distinct interface clusters and whether top-ranked candidates agree on chain orientation and contacts. Compare MSA against single-sequence mode when supported; record MSA source/depth and avoid treating server and local MSAs as equivalent. Vary restraints on/off, seeds, and candidate count under fixed settings. A claim is fragile if rank, partner choice, interface topology, or claim status changes under plausible perturbations; report the range rather than selecting the favorable run.

## Applicability and failure detection

Applicability depends on whether the pinned release represents the entity types, modifications, stoichiometry, and ligand chemistry. Do not extrapolate a good benchmark result to unrepresented chemical states, membrane context, disordered regions, transient interactions, or cellular conditions without separate evidence.

| Failure mode | Detection and response |
|---|---|
| Wrong chain/entity mapping | Compare normalized sequence, residue and atom maps; stop and mark affected claims unavailable. |
| MSA leakage or stale homolog | Record source dates and exact/close complex matches; flag benchmark contamination or cutoff uncertainty. |
| Confident but wrong interface | Check chain-pair metrics, blinded known-complex controls, decoys, and independent structural evidence. |
| Ligand chemistry silently changed | Compare canonicalized identity, stereochemistry, bond orders, protonation and atom map before and after; stop on mismatch. |
| Restraints drive the answer | Compare restraint-free candidate or label support as conditional on restraints; never count satisfaction twice. |
| Candidate selection bias | Retain all samples, seeds, failures, and ranking rule; compare fixed-budget diversity. |
| Incomplete output or interrupted run | Validate expected structures and logs; classify process failure, preserve artifacts, and do not infer scientific failure. |

## Sources

- Chai Discovery, **Chai-1: Decoding the Molecular Interactions of Life** (2024 preprint): model-specific multimolecular prediction, confidence outputs, and MSA versus single-sequence use. Verify details against the pinned release.
  The preprint describes method behavior; the exact installed release determines supported inputs and emitted fields.
- Jumper et al., **Highly accurate protein structure prediction with AlphaFold** (2021): pLDDT and predicted aligned error as model confidence quantities, not experimental assays.
- Basu and Wallner, **DockQ: A Quality Measure for Protein-Protein Docking Models** (2016): interface-quality comparison against a reference structure.
- Buttenschoen et al., **PoseBusters: AI-based docking methods fail to generate physically valid poses or generalise to novel sequences** (2024): chemical and physical pose-validity checks.
