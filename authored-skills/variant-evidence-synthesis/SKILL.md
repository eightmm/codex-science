---
name: variant-evidence-synthesis
description: "Synthesize population, clinical, functional, regulatory, expression, and cohort evidence for a genomic variant. Use for research interpretation of rsIDs or genomic alleles, not patient-specific diagnosis or treatment."
license: MIT
---

# Variant Evidence Synthesis

## Decision contract
Define assembly, normalized allele, transcript or regulatory context, phenotype, population, evidence cutoff, intended research decision, and non-goals; keep multiallelic records and allele-specific claims separate.

## Reference usage
- Read [references/variant-interpretation.md](references/variant-interpretation.md) before allele harmonization, claim classification, or combining clinical, population, functional, and regulatory evidence.
- Read [references/variant-interpretation.md](references/variant-interpretation.md) when choosing controls or sensitivity analyses and defining the interpretation domain.

## Workflow
1. Freeze genome assembly, normalized allele, transcript or regulatory context, phenotype definition, population, evidence cutoff, intended research decision, and non-goals; unresolved identity blocks allele-level synthesis.
2. Retrieve population frequency and constraint, clinical assertions, predicted molecular consequences, curated associations, regulatory and expression evidence, and cross-cohort PheWAS only when relevant; preserve query, exact source release, record ID, snapshot or hash, and whether each source is primary evidence or an index.
3. Verify build, reference and alternate alleles, strand, effect allele, normalization, transcript, and liftover; if any mapping is ambiguous, keep records separate and record the ambiguity.
4. Classify each claim as direct observation, population frequency or constraint, association (including cross-cohort PheWAS), clinical assertion, functional evidence, prediction, or regulatory overlap under the reference criteria; retain its original evidence and review status.
5. Align phenotype, ancestry, ascertainment, LD context, model, tissue, effect direction, sample size, uncertainty, and correction scope; record incompatibilities rather than pooling them.
6. Trace source dependencies and shared cohorts, distinguish primary results from propagated summaries, and reconcile independent evidence lanes with `$cx-biomedical-evidence-reconciliation`; record the dependency decision.
7. Apply the specified positive/negative controls and vary allele harmonization, ancestry, source release, cohort inclusion, and evidence-lane inclusion; record any status or direction change as fragility.
8. Assign claim-specific confidence and state the inference boundary; document missing evidence, conflicts, and a falsifiable functional or replication follow-up.
9. Verify every interpretation against the normalized allele and retained records, and check that association, predicted effect, ClinVar assertion, or regulatory overlap was not upgraded to causality or clinical actionability; record the result and review handoff.

## Outputs
Return `variant-evidence-synthesis-v1` with required fields `variant_identity`, `claim_register`, `evidence_matrix`, `allele_alignment_audit`, `cohort_comparison`, `dependency_graph`, `conflicts`, `missing_evidence`, `confidence_by_claim`, `sensitivity_analysis`, `follow_ups`, and `provenance`.

## Boundaries
Do not equate association, in-silico effect, a ClinVar assertion, one cohort, or regulatory overlap with causality or clinical actionability; explicitly mark ancestry, ascertainment, LD, transcript, and tissue limitations.
Store exact queries, normalized records, source snapshots, and evidence tables with `$science-provenance`; run `$science-review` before reporting an interpretation.
