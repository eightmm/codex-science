---
name: variant-evidence-synthesis
description: "Synthesize population, clinical, functional, regulatory, expression, and cohort evidence for a genomic variant. Use for research interpretation of rsIDs or genomic alleles, not patient-specific diagnosis or treatment."
license: MIT
---

# Variant Evidence Synthesis

## Decision contract
Define assembly, normalized allele, transcript or regulatory context, phenotype, population, evidence cutoff, intended research decision, and non-goals; keep multiallelic records and allele-specific claims separate.
## Workflow
Retrieve population frequency and constraint, clinical assertions, predicted molecular consequences, curated associations, regulatory and expression evidence, and cross-cohort PheWAS only when relevant; preserve effect allele, strand, ancestry, phenotype definition, model, sample size, uncertainty, correction scope, source release, and assertion review status.
Triangulate independent lanes rather than counting portals, test direction and allele alignment, distinguish primary evidence from propagated summaries, and reconcile conflicts with `$cx-biomedical-evidence-reconciliation`.
## Outputs
Return a claim-evidence matrix, allele-alignment audit, cohort comparison, conflicts, missing evidence, confidence by claim, and falsifiable functional or replication follow-ups.
## Boundaries
Do not equate association, in-silico effect, a ClinVar assertion, one cohort, or regulatory overlap with causality or clinical actionability; explicitly mark ancestry, ascertainment, LD, transcript, and tissue limitations.
Store exact queries, normalized records, source snapshots, and evidence tables with `$science-provenance`; run `$science-review` before reporting an interpretation.
