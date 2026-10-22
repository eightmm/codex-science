---
name: plip-interaction-analysis
description: "Profile noncovalent protein-ligand interactions with a pinned PLIP release and compare interaction fingerprints across experimental structures, docking poses, or trajectory representatives. Use after structure preparation or pose generation."
license: MIT
---

# PLIP Interaction Analysis

## Decision contract

Define whether the task describes a complex, compares structures, or estimates trajectory occupancy; identify the structure/pose set, ligand and receptor states, evidence cutoff, and observation that would change the interpretation. Assign claim IDs and prespecify fingerprint fields and any sampling rule. Classify each conclusion as a geometric annotation, a structural comparison, or a sampled occupancy estimate. A contact or interaction fingerprint is not an energetic, affinity, binding, or mechanism measurement.

## Reference usage

Read [references/plip-geometry-and-evidence.md](references/plip-geometry-and-evidence.md) before running PLIP, comparing interaction fingerprints, interpreting trajectory occupancy, or making a claim that depends on interaction type or geometry. It defines interaction classes, dependence checks, controls, sensitivity analyses, and the boundary between a detected contact and a binding claim.

## Workflow

1. **Gate:** Follow `$cx-compute-environment`; ask once before installing pinned PLIP/Open Babel dependencies or processing many structures. Record approval or the decision to stop before proceeding.
2. Define the claim class and comparison rule; proceed only if the target question, claim IDs, evidence cutoff, fingerprint fields, and any frame-sampling rule are specified. Record them in the run contract.
3. Identify inputs and biological context; proceed only when source, release, experimental or predicted provenance, assembly/chains, ligand identity and atom mapping, protonation, retained waters/metals, and coordinate validity are known or explicitly unresolved. Preserve and hash raw inputs; record exclusions.
4. Validate a single representative complex; proceed only if ligand selection and atom mapping resolve to the intended molecule. Record the smoke-test result and exact PLIP/Open Babel versions and commands.
5. Run PLIP into `artifacts/<run-id>/plip/`; retain machine-readable output and failures. Record output paths, hashes, parser status, and reasons for every excluded structure.
6. Classify hydrogen bonds, hydrophobic contacts, salt bridges, pi-stacking, halogen bonds, water bridges, and metal coordination using the pinned PLIP definitions and geometry. Report atom/residue identifiers and measured geometry; label ambiguous or unsupported cases unavailable rather than forcing a type.
7. Compare only consistently prepared structures; for trajectories use the prespecified frame rule and report occupancy with sampling and autocorrelation-aware uncertainty. Vary protonation, hydrogen placement, alternate locations, water handling, and relevant thresholds; downgrade a claim if its direction or key contacts change. Record control and sensitivity outcomes.
8. Report geometry annotations separately from energetic or binding interpretations; preserve scripts, configuration, dependencies, failures, exclusions, and limitations with `$science-provenance`, then obtain `$science-review` before material interpretation. Record supported, contradicted, inconclusive, or unavailable claim status and the smallest falsifiable next action.

## Outputs

Return `plip-interaction-evidence-v1` with required fields: claim identifier (`claim_id`); claim class (`claim_class`); normalized structure and source identity (`structure_id`, `source`, `release`, `structure_provenance`); ligand and receptor state (`ligand_id`, `atom_mapping`, `preparation`); tool identity and command (`plip_version`, `command`); interaction records (`interactions`, each with `type`, `atoms`, `residues`, `geometry`, and optional `frame`/`replica`); sampling and uncertainty (`sampling_rule`, `uncertainty`); control and sensitivity results (`controls`, `sensitivity`); input and output hashes (`input_hashes`, `output_hashes`); exclusions and reasons (`exclusions`); claim status (`status`: supported, contradicted, inconclusive, or unavailable); limitations (`limitations`); and smallest falsifiable next action (`next_action`). Keep raw inputs and derived artifacts distinct.

## Boundaries

A detected contact is a geometry-based annotation, not proof of energetic importance or binding. Protonation, missing hydrogens, alternate locations, and water handling can change the fingerprint; state them. Do not infer affinity from interaction counts. Incompatible preparation, missing atoms, or inadequate trajectory sampling requires an inconclusive result.

## Source basis

PLIP's interaction definitions and detection workflow are grounded in Salentin et al. (2015), “PLIP: fully automated protein-ligand interaction profiler.” Structural provenance and coordinate identity follow wwPDB/PDBx/mmCIF conventions; a deposited or predicted coordinate model does not itself establish binding energetics.
