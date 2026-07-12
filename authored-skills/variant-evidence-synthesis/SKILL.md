---
name: variant-evidence-synthesis
description: "Synthesize population, clinical, functional, regulatory, expression, and cohort evidence for a genomic variant. Use for research interpretation of rsIDs or genomic alleles, not patient-specific diagnosis or treatment."
license: MIT
---

# Variant Evidence Synthesis

1. Normalize assembly and allele with `$cx-biomedical-entity-normalization`; keep multi-allelic records separate.
2. Retrieve frequency/constraint from `$cx-gnomad-search`, clinical assertions from `$cx-clinvar-search`, annotation from `$cx-ensembl-search`, and curated associations from `$cx-gwas-catalog-search`.
3. Add tissue/regulatory evidence only where relevant using GTEx, ENCODE, HPA/Bgee, or AlphaGenome/Borzoi workflows.
4. Run `$cx-phewas-replication-analysis` for cross-cohort phenotype evidence.
5. Compare effect allele, direction, ancestry, phenotype definition, model, sample size, p-value, multiple-testing context, and release.
6. Produce an evidence matrix, conflicts, missing evidence, and testable follow-ups; record artifacts and run `$science-review`.

Do not equate association, in-silico effect, ClinVar assertion, or one cohort with causality or clinical actionability.

Store the evidence matrix and exact source queries with `$science-provenance` before `$science-review`.
