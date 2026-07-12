---
name: biomedical-evidence-reconciliation
description: "Reconcile conflicting multi-source biomedical evidence with explicit entity, release, cohort, assay, independence, and claim semantics. Use before final conclusions from multiple databases or evidence lanes."
license: MIT
---

# Biomedical Evidence Reconciliation

1. Verify every row refers to the same normalized entity, species, assembly/transcript/chemical form, and scientific claim.
2. Separate direct experiment, curated assertion, association, prediction, portal summary, and secondary citation.
3. Deduplicate evidence propagated across databases or publications; mark shared cohorts, samples, authors, and source records.
4. Compare release dates, population, ancestry, tissue/cell state, assay, endpoint, units, effect direction, uncertainty, and correction.
5. Classify each conclusion as supported, replicated, suggestive, conflicting, unsupported, or unavailable. Missing evidence is not negative evidence.
6. Produce a claim-evidence matrix, contradiction log, sensitivity analysis, and the smallest observation that could resolve each material conflict.
7. Link claims to provenance artifacts and run `$science-review`.

Do not use an opaque score to hide disagreements. The final confidence cannot exceed the weakest essential evidence link.
