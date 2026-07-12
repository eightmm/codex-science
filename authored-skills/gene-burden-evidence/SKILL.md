---
name: gene-burden-evidence
description: "Assess rare-variant gene burden evidence with explicit cohort, ancestry, mask, frequency threshold, model, phenotype, and multiple-testing semantics. Use for gene-level human genetic support and locus-to-gene follow-up."
license: MIT
---

# Gene Burden Evidence

1. Define gene/transcript, phenotype, cohort, ancestry, case/control unit, qualifying variant mask, frequency threshold, and statistical model.
2. Retrieve a versioned public burden result only from a source whose terms and endpoint are available; otherwise report the source as unavailable instead of fabricating a lookup.
3. Preserve mask, consequence definition, sample size, effect direction, confidence interval, p-value, burden/SKAT model, and correction scope.
4. Compare independent cohorts and coding/constraint evidence; keep discovery and replication separate.
5. Use as one lane in `$cx-locus-to-gene-prioritization`, never as a standalone causal proof.

Do not compare differently defined masks or phenotypes as exact replication. GeneBass and similar portals remain availability-gated until a stable, documented public API is verified.

Record source, release, cohort, mask, model, and result with `$science-provenance`; run `$science-review` before synthesis.
