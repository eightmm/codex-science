---
name: rosettafold-all-atom
description: "Run RoseTTAFold All-Atom for proteins, nucleic acids, small molecules, metals, covalent modifications, and higher-order assemblies. Use when its Hydra input model and confidence metrics fit the problem and licensed dependencies are available."
license: MIT
---

# RoseTTAFold All-Atom

Use `$cx-modeling-problem-execution` for concrete structures and continue through input preparation, inference, analysis, and review.

## Decision contract

Role: executor, with structure-quality analysis of model outputs.

Record the structural question, intended use, claim IDs, organism/construct, entities, ligand/metal/covalent state, and acceptable inference. Name a falsifier and identify unsupported chemistry or unresolved mappings that would make the result inconclusive. Do not treat model confidence as binding evidence.

## Reference usage

- Read [references/rfaa-complex-evidence.md](references/rfaa-complex-evidence.md) before interpreting complex or ligand claims, chain-pair confidence, training overlap, controls, or sensitivity.
- Record the exact reference revision and use with `$science-provenance`; these procedures do not establish experimental correctness.

## Workflow

1. **Gates (ask before proceeding).** Ask once before cloning a pinned commit, creating the environment/container, downloading large sequence/template databases and weights, installing separately licensed SignalP, and running GPU compute. Verify each dependency's terms before use. Record approvals, declined gates, and the stop reason.
2. Define the prediction unit, assembly, chain partners, structural or interaction claim, falsifier, ligand state, and decision consequence. Distinguish predicted structure from experimentally determined structure and binding evidence; assign claim IDs and record exploratory versus decision-bearing use.
3. Validate protein/nucleic-acid FASTA, ligand SDF/SMILES, metals, covalent bond atom indices/chirality, chain IDs, and Hydra config. Preserve/hash submitted and normalized inputs; record unsupported fields. Stop on unresolved mapping or chemistry and retain an inconclusive/unavailable status.
4. Pin code commit, checkpoint checksum and terms, database snapshots, container digest, SignalP and other dependency versions/licenses, MSA/template mode, cycles, restraints, samples/seeds, hardware, and precision. Record actual revisions and training-data cutoff/overlap or explicitly mark them unknown.
5. Smoke-test an official example and validate structural output/metrics before the full run. Run into `artifacts/<run-id>/rfaa/`; retain inputs/config, MSAs/templates, PDB, pLDDT/PAE/PDE metrics, mappings, logs, environment, and failures. Record smoke-test outcome before proceeding.
6. Inspect chain-pair interface confidence and interface PAE, available ipTM-like evidence, chain mapping, contacts, covalent/metal geometry, ligand stereochemistry/state, clashes, and confidence. Use PoseBusters-style checks for ligand physical plausibility where applicable; they do not show that the pose or interaction is experimentally correct.
7. Use known-complex recovery and apo/decoy partners as controls where available. Compare seed/sample diversity and sensitivity to MSA, restraints, seeds, cycles/sampling, and a justified baseline under matched budgets. Record control identities/results, data and method dependencies, and any conclusion that changes.
8. Classify input, configuration, resource, and infrastructure failures; do not retry invalid inputs, bound transient retries, and preserve cancellation and failure logs. Report uncertainty and applicability; downgrade material claims when MSA, controls, training overlap, or sensitivity checks reveal fragility.
9. Record command, environment, outputs, negative results, and hashes with `$science-provenance`; use `$science-review` before material conclusions. Verify output completeness, license terms, failure retention, and the distinction between prediction and experimental validation.

## Outputs

Return one `rfaa-complex-evidence-v1` record with required fields: `claim_id`, `status` (`planned`, `supported`, `contradicted`, `inconclusive`, or `unavailable`), `claim_class`, `prediction_unit`, `input_mapping_hashes`, `code_checkpoint_database_container`, `license_terms`, `dependency_versions`, `training_cutoff_or_unknown`, `MSA_template_provenance`, `restraints`, `settings`, `hardware_precision`, `artifact_paths_hashes`, `chain_pair_metrics`, `ligand_validity`, `controls`, `sample_diversity`, `failures_nulls`, `uncertainty_sensitivity`, `dependencies`, `applicability_domain`, `interpretation`, `limitations`, and `next_action`. Include observed metrics, geometry findings, alternative interpretations, and a falsifiable next action. State process completion separately from scientific validation.

## Boundaries

SignalP and other dependencies may have separate licenses and cannot be silently downloaded or redistributed. Verify the pinned code, weights, databases, and dependency terms; do not assume one license covers all. Predicted docks and `pae_inter` are prioritization signals, not affinity. A predicted geometry is not experimentally validated, confidence is not calibrated probability, and restraint satisfaction is not independent evidence when restraints were inputs. Stop if licensing, atom mapping, chirality, or input support is unresolved; retain outputs and report affected claims as inconclusive or unavailable.
