---
name: locus-to-gene-prioritization
description: "Prioritize candidate genes at human genetic loci using curated association, credible-set/L2G, colocalization, eQTL, coding, burden, expression, and pathway evidence. Use for GWAS follow-up and target prioritization."
license: MIT
---

# Locus-to-Gene Prioritization

## Decision contract
Define trait and ontology ID, assembly, ancestry, lead variant or credible set, locus boundary, LD reference, tissues or cell states, evidence cutoff, ranking objective, and criteria that would change the decision.
## Workflow
Normalize variants and genes; keep independent lanes for fine-mapping and L2G, coding consequence, colocalization and eQTL, rare-variant burden, chromatin or contact evidence, expression and cell context, pathway or mechanism, and prior functional validation.
Require allele, build, LD, tissue, and phenotype alignment; record source release and study dependence, prevent the same association from being counted through multiple portals, and score only with transparent prespecified per-lane rules plus sensitivity analyses.
## Outputs
Return per-locus ranked candidates, lane-level evidence and counterevidence, rejected alternatives, score sensitivity, conflicts, ancestry and tissue limitations, and the smallest experiment or analysis that could reorder the candidates.
## Boundaries
Proximity is weak evidence, colocalization is not causality, shared LD and correlated annotations can inflate support, and missing a portal result is not gene-level negative evidence.
Save the credible set, lane tables, deduplication decisions, ranking rule, and rejected genes with `$science-provenance`; run `$science-review` before presenting a target-prioritization claim.
