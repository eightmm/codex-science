# Protenix complex evidence protocol

## Claim semantics

Assign a stable claim ID and class before reviewing candidates:

- **Predicted arrangement:** inference produced a defined assembly. Support requires valid normalized inputs and retained output coordinates; this is a process/model-output claim.
- **Structural agreement:** a model matches a named experimental reference under a declared assembly, chain mapping, atom selection, alignment, and metric. Record experimental release and exclusions; predicted coordinates remain predictions.
- **Interface plausibility:** interface confidence, pair-specific PAE/ipTM when emitted, contact geometry, and controls support prioritizing an interface. Keep each metric separate; none establishes binding.
- **Binding or affinity:** requires independent experimental interaction/affinity evidence or a validated assay. A confident predicted complex is insufficient.
- **Ligand-pose plausibility:** chemically correct stereochemistry and reasonable ligand/protein geometry support plausibility only. PoseBusters-style pass/fail checks are filters, not proof of the native pose.

Use one status vocabulary: `planned`, `supported`, `contradicted`, `inconclusive`, `unavailable`. Mark mixed, unstable, or underpowered evidence inconclusive; mark a claim unavailable when its required evidence is absent. Preserve failed and negative cases.

## Source dependencies and independence

Pin the exact Protenix model name/release, code commit, weight checksum and terms, database/MSA/template releases, inference budget, and source dates. Record the selected model's stated training-data cutoff; do not carry a cutoff from another Protenix checkpoint. For complex benchmarks, inspect both-chain homology and exact/propagated complex records, not only target sequence identity.

Separate a reference structure used as template, restraint, or input from independent validation. Record whether control and test structures share an assembly, source experiment, homologous complex, or propagated PDB record. Different seeds, candidate samples, and model checkpoints trained on shared data are dependent predictions, not independent experiments.

Freeze benchmark splits before inference/scoring. Cluster related targets and complexes by sequence/structure similarity and shared source records; report post-cutoff, ambiguous, excluded, and unresolved examples. A newer cutoff can increase practical coverage while weakening a retrospective leakage-free benchmark.

## Uncertainty and confidence

Report emitted global and pair-specific confidence values separately, including interface PAE and ipTM only when actually present. State the chain-pair mapping and preserve raw values. Do not infer calibration, interaction probability, or assay outcome from a confidence score without external calibration on comparable targets, model version, and protocol.

Carry uncertainty from model cutoff, homolog/template overlap, MSA quality, partner stoichiometry, ligand protonation/tautomer/stereo assignment, restraint provenance, stochastic sampling, and reference resolution. Report missing cutoff or unavailable metrics as unknown/unavailable, not zero. Any interval or threshold must name its dataset and method; otherwise use a qualitative rationale.

### Version and candidate review record

Record the complete model identifier, not just "Protenix" or a family label. Distinguish released code from checkpoint identity and terms. If comparing releases with different cutoffs, evaluate them as separate models and state that model, training data, and possibly inference procedure all changed together.

For each interface, retain partner chain IDs and mapping, emitted pairwise confidence fields, interface PAE scope, contact definition, and candidate rank. If the output contains global confidence only, state that pair-specific evidence is missing; do not manufacture a chain-pair score from the global value. Compare confidence to the geometry and controls rather than averaging unlike metrics.

For MSA/template inputs, record database release/date, search or preprocessing version, depth/coverage fields actually emitted, template identifiers, and excluded homologs. In a benchmark, freeze these resources and their cutoff relative to the evaluation set. For a practical prediction with a later database, report that it is not a cutoff-matched benchmark result.

For ligands, preserve the input and predicted atom maps and check stereochemistry, bond orders, formal charge, protonation assumption, internal geometry, and protein clashes. Record failures separately. Physical plausibility filtering can eliminate impossible candidates but cannot determine which valid candidate is biologically occupied.

For reference structures, state whether coordinates are apo/holo, which partners are resolved, whether alternate conformers or symmetry copies were considered, and which residues/atoms were omitted. Freeze mapping and comparison rules before ranking candidates when possible.

## Controls and sensitivity

Use known-complex recovery controls with withheld coordinates and fixed chain mapping. Add apo partners or unrelated decoy partners matched for sequence length, MSA coverage, and inference budget. Report control selection and avoid claiming specificity from a control selected after predictions.

Retain all candidates across paired seeds and report distinct interface clusters, partner orientation, and contact consistency. Compare MSA/template conditions, restraint-on/off, seeds, and sampling budget; keep budgets matched when comparing alternatives. A result is fragile if partner selection, interface topology, ranking, or claim status changes under plausible changes. Record all variants, including failures and nulls, and do not select only the best sample without disclosing the selection rule.

### Decision rule

Support an interface-plausibility claim only when the chain mapping is sound, pair-specific evidence and geometry are reported at the available level, and controls do not reveal a clear nonspecific partner preference. Otherwise use `inconclusive` or `unavailable` and identify the missing discriminator. Binding and affinity claims remain dependent on independent experimental evidence.

### Cutoff and inference-budget interpretation

For any benchmark or retrospective comparison, compare the evaluation deposition dates and close homologs with the selected checkpoint cutoff. A nominal date cutoff does not rule out leakage through propagated assemblies, pre-release records, or related complexes. Report unresolved matches and avoid a clean held-out claim when lineage is unclear.

Record requested and completed sample counts, seeds, recycle/scaling options, early stops, and selection criteria. Compare models using equal or explicitly justified budgets. Report how the result changes as sampling increases; selecting the best of more candidates creates a selection advantage even when the underlying model is unchanged.

### Reporting boundary

Keep predicted arrangement, reference agreement, geometry validity, and experimental interaction evidence in separate result fields. Name the evidence lane and dependency for each conclusion. A high confidence score or a passing ligand filter cannot substitute for the missing experimental lane.

## Applicability and failure detection

Applicability is limited to supported entity types, released model, cutoff, inference configuration, and training/evaluation domain. Antibody-antigen performance claims do not transfer automatically to other complexes. Do not infer cellular binding, affinity, kinetics, clinical utility, or unmodeled conformational effects from one predicted structure.

| Failure mode | Detection and response |
|---|---|
| Wrong chain or ligand mapping | Validate input identifiers, sequence and atom maps against normalized output; stop affected claim. |
| Cutoff leakage or propagated complex | Search exact and homologous partner/complex records; document shared source and downgrade benchmark claim. |
| Metric conflation | Verify model output schema and report global, chain-pair, PAE and ipTM fields separately. |
| Implausible ligand pose | Check stereochemistry, bond/angle geometry, intramolecular strain and protein clashes; fail or qualify plausibility. |
| Apparent gain from more samples | Report candidate budget and selection procedure; compare against budget-matched baseline. |
| Restraint-induced result | Compare without restraints where meaningful; label conditional result and do not count restraint satisfaction as support. |
| Weight/license mismatch | Verify exact model artifact terms before download, use, redistribution, or commercial work; stop when terms are unresolved. |
| Partial or failed inference | Validate files, logs and candidate count; preserve failures and distinguish process failure from scientific contradiction. |

## Sources

- ByteDance AML AI4Science Team et al., **Protenix - Advancing Structure Prediction Through a Comprehensive AlphaFold3 Reproduction** (2025 preprint): model/reproduction claims; verify every version-specific detail against the pinned release.
- Zhang et al., **Protenix-v1: Toward High-Accuracy Open-Source Biomolecular Structure Prediction** (2026 preprint): v1 model, cutoff, and evaluation claims; do not transfer them to another checkpoint without evidence.
- Protenix official model documentation (versioned release notes): supported models, their cutoffs, inputs, and weight terms. Documentation can change; preserve the consulted version/date.
- Jumper et al., **Highly accurate protein structure prediction with AlphaFold** (2021): interpretation boundaries for pLDDT and predicted aligned error.
- Basu and Wallner, **DockQ: A Quality Measure for Protein-Protein Docking Models** (2016): reference-based interface assessment.
- Buttenschoen et al., **PoseBusters: AI-based docking methods fail to generate physically valid poses or generalise to novel sequences** (2024): chemical/physical pose checks and their limitations.
