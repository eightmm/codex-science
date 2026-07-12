---
name: locus-to-gene-prioritization
description: "Prioritize candidate genes at human genetic loci using curated association, credible-set/L2G, colocalization, eQTL, coding, burden, expression, and pathway evidence. Use for GWAS follow-up and target prioritization."
license: MIT
---

# Locus-to-Gene Prioritization

1. Define trait/EFO ID, assembly, ancestry, lead variant or credible set, locus boundary, LD reference, and evidence cutoff.
2. Normalize every variant and gene. Retrieve curated trait/locus evidence from GWAS Catalog and Open Targets.
3. Keep independent lanes for proximity/coding, L2G/fine-mapping, colocalization/eQTL, rare-variant burden, tissue/cell expression, and pathway/mechanism.
4. Require allele/build alignment before combining lanes. Record source release and avoid duplicate evidence counted through multiple databases.
5. Rank genes with transparent per-lane evidence, not a hidden aggregate. Use confidence labels only when prespecified criteria are met.
6. Return per-locus candidates, rejected alternatives, conflicts, ancestry/tissue limitations, and the smallest experiment or analysis that could change the ranking.

Proximity alone is weak evidence. Colocalization is not causality; shared LD can mislead. Never seed trait-specific variants from an undocumented hard-coded list.

Save per-lane evidence and rejected genes with `$science-provenance`; run `$science-review` before reporting a ranking.
