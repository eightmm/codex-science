---
name: openfold3-structure-prediction
description: "Run pinned OpenFold3 preview inference for proteins, nucleic acids, noncanonical residues, and small-molecule complexes. Use when an open AlphaFold3-style workflow is wanted and preview-status limitations are acceptable."
license: MIT
---

# OpenFold3 Structure Prediction

## Decision contract

Role: executor, with structure and confidence analysis of model outputs.

Record the structural question, intended use, claim IDs, entity/chemical state, and what would falsify the interpretation. State that OpenFold3 is a preview and define the acceptable inference level. Keep model prediction separate from experimental evidence.

## Reference usage

- Read [references/openfold3-evidence.md](references/openfold3-evidence.md) before assigning claims, interpreting confidence outputs, assessing chemistry, selecting controls, or evaluating MSA/template dependence, possible training/PDB overlap, and sensitivity across preview releases and inference settings.

## Workflow

1. **Gates (ask before proceeding).** Ask once before installing a pinned OpenFold3 preview release, running setup, downloading parameters/databases, contacting an MSA server, or using GPU/remote compute. Never send private sequences to public services without approval. Follow `$cx-compute-environment`; record approval, terms, and any declined or unavailable resource.
2. Define and validate query JSON entities, sequences, ligand states, modifications, stoichiometry, templates, MSAs, and covalent relationships. Validate IDs and atom/residue mappings; preserve and hash input, and record unsupported fields instead of silently dropping them.
3. Pin preview release/commit, parameter checksum, setup version, database snapshots, kernel versions, MSA/template mode, seeds, samples, and hardware. Record actual versions; only state a training-data cutoff when verified for that exact release, otherwise mark it unknown.
4. Assess MSA depth and pairing, template dependence, chemistry/atom mapping, and possible PDB or training-data overlap; record provenance, shared dependencies, and limits on inference caused by preview status or incomplete metadata.
5. Smoke-test the official example and validate expected structure and confidence outputs. Run `run_openfold predict` into `artifacts/<run-id>/openfold3/`; retain query JSON, feature inputs, structures, confidence outputs, environment, exact command, logs, timings, and failures.
6. Classify input, configuration, resource, and infrastructure failures; do not retry invalid inputs, bound transient retries, and preserve cancellation and failure logs. Keep missing metrics, null output, and unavailable chemistry distinct.
7. Evaluate per-atom or per-residue pLDDT, PAE, pTM/ipTM, and `sample_ranking_score` when emitted by the pinned release, plus interfaces, chemistry, clashes, sample diversity, and template/MSA dependence under the reference criteria. Do not infer AlphaFold3 metric equivalence from similar names.
8. Use a positive structural control and a negative/sanity control, and compare an appropriate independent model for decision-critical claims; report shared data and method dependencies. For benchmark claims use post-cutoff targets only when the exact cutoff is documented and audit homolog/template overlap. Vary MSA source/depth, template mode/cutoff, recycle count if supported, and seeds; call the result fragile if plausible settings alter the claim or structure beyond its prespecified criterion.
9. Record with `$science-provenance`; run `$science-review` before material conclusions. Report preview status, claim status, uncertainty, applicability, limitations, and the smallest falsifiable next action. Keep predicted structures separate from experimental evidence.

## Outputs

Return an execution/evidence `openfold3-structure-evidence-v1` record with these required fields: claim identifier (`claim_id`); evidence status (`status`: `supported`, `contradicted`, `inconclusive`, or `unavailable`); normalized entities and chemical input (`input`); input hash (`input_hash`); entity and atom/residue mapping (`entity_mapping`); OpenFold3 preview code revision (`code_version`); parameter release and checksum (`parameter_revision`, `parameter_checksum`); database snapshots (`database_versions`); execution command (`command`); inference configuration (`settings`); hardware and precision (`hardware`); output artifact paths and hashes (`output_paths`, `output_hashes`); emitted metrics and their release-specific interpretation (`metrics`, `metric_interpretations`); MSA, template, PDB, and training-overlap assessment (`msa_template_overlap`); shared data and method dependencies (`dependencies`); controls and their outcomes (`controls`); varied settings, results, and fragility (`sensitivity`); uncertainty (`uncertainty`); execution and validation failures (`failures`); missing and null fields (`missingness`); applicability domain (`applicability`); limitations (`limitations`); preview designation (`preview_status`); process completion (`process_completed`); plausible alternative interpretations (`plausible_alternatives`); concise interpretation (`interpretation`); and smallest falsifiable next action (`next_action`). State process completion separately from scientific validation.

## Boundaries

Label the software and results as OpenFold3 preview; do not claim final-model parity or full AlphaFold3 modality parity. Predicted ligand poses and interfaces do not establish binding or affinity. Do not treat preview output as experimental truth. Stop if required chemistry is unsupported, input mapping is unresolved, or approval is unmet; retain the failure and report the claim as inconclusive or unavailable. Keep OpenFold3's own code, parameter, and database terms; the repository skill license does not grant rights to external assets. Preserve GPU, install, database, and remote-service gates.
