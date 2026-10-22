---
name: chai1-structure-prediction
description: "Run pinned Chai-1 inference for proteins, complexes, nucleic acids, ligands, covalent bonds, templates, or restraints. Use when multimolecular structure prediction needs Chai-1-specific inputs and confidence outputs."
license: MIT
---

# Chai-1 Structure Prediction

## Decision contract

Role: executor, with structure and confidence analysis of model outputs.

Before execution, record the structural question, intended use, claim IDs, permitted inference, model alternatives, and the observation that would change the conclusion. Define every entity and state: protein/RNA/DNA sequence, ligand SMILES/CCD, modifications, stoichiometry, covalent bonds, restraints, and templates. Label the run exploratory or decision-bearing.

## Reference usage

- Read [references/chai1-complex-evidence.md](references/chai1-complex-evidence.md) before interpreting a complex, chain-pair confidence, ligand pose, MSA mode, training overlap, or control comparison.
- Record the reference revision and its use with `$science-provenance`; a method reference is not evidence that a predicted structure is experimentally correct.

## Workflow

1. **Gates (ask before proceeding).** Ask once before installing a pinned `chai_lab` release, downloading weights, using GPU compute, or contacting public MSA/template servers. Name each remote host; never upload private sequences or structures without approval. Follow `$cx-compute-environment`. Record approvals, declined gates, or the reason execution stopped.
2. Define the prediction unit, biological assembly, target and partner chain identities, ligand/chemical state, permitted claim, and a falsifier. Decide whether the question concerns a predicted arrangement, structural agreement, or experimentally supported interaction; record the distinction and claim IDs.
3. Validate input schema and entity, residue, atom, bond, restraint, and template mappings. Preserve original and normalized inputs with hashes; record unsupported fields rather than silently dropping them. Stop if chemistry or mapping is unresolved and record `inconclusive` or `unavailable`.
4. Pin Chai-1 code/release, weight checksum and terms, input schema, MSA/template mode, sample count, seeds, hardware, precision, and restraints. Record actual versions and any training-data cutoff or overlap information available for that exact release; label unknown cutoff or overlap as unknown.
5. Smoke-test `chai-lab fold --help` and an upstream example. Verify expected files and structural content before full inference. Run validated FASTA/context into `artifacts/<run-id>/chai1/`; retain inputs, MSAs, templates, restraint files, structures, scores, logs, environment, and failures. Record the smoke-test result and run decision.
6. For each candidate, inspect chain-pair interface confidence, interface PAE and available ipTM-like outputs, chain mapping, contacts, geometry, clashes, ligand stereochemistry/state, and restraint satisfaction. Apply ligand-pose validity checks (PoseBusters-style where applicable) as filters, not proof of binding; record per-chain-pair and per-ligand findings.
7. Compare multiple seeds/samples and report diversity, not just the selected candidate. Where relevant compare MSA and single-sequence modes, restraint-on/off runs, and a justified baseline under declared budgets. Use known-complex recovery and apo or decoy partners as controls when data permit; record control identities, outcomes, dependencies, and failed controls.
8. Classify input, configuration, resource, and infrastructure failures; do not retry invalid inputs, bound transient retries, and preserve cancellation and failure logs. Report uncertainty and sensitivity to MSA, restraints, seeds, and sampling; downgrade claims when conclusions change materially.
9. Record execution and artifact hashes with `$science-provenance`; use `$science-review` before material conclusions. Verify that the output schema is complete, every claim has a status and support boundary, and no predicted-complex result is called experimental evidence.

## Outputs

Return one `chai1-complex-evidence-v1` record with required fields: `claim_id`, `status` (`planned`, `supported`, `contradicted`, `inconclusive`, or `unavailable`), `claim_class`, `prediction_unit`, `normalized_input_hash`, `model_release`, `weight_checksum`, `license_terms`, `training_cutoff_or_unknown`, `MSA_template_provenance`, `restraints`, `command_settings`, `hardware_precision`, `candidate_paths_hashes`, `chain_pair_metrics`, `ligand_validity`, `controls`, `sample_diversity`, `failures_nulls`, `uncertainty_sensitivity`, `dependencies`, `applicability_domain`, `interpretation`, `limitations`, and `next_action`. Include metrics actually returned, alternatives, and a falsifiable next action. Distinguish completed inference from scientific validation.

## Boundaries

Restraint satisfaction is not independent evidence when restraints were input. A plausible predicted complex or ligand pose is not proof of binding or affinity, and confidence is not a calibrated probability or experimental measurement. Public MSA/template results must be reported separately from local MSA runs. Use a justified baseline for decision-critical claims. Do not upload private sequences or structures without approval. Keep the pinned release's code, weight, database, and service terms distinct; do not assume an MIT code license grants weight or database rights. Stop when chemistry or mapping is unresolved, an approval gate is unmet, or the pinned release cannot represent an entity; retain an `inconclusive` or `unavailable` status and the failure record.
