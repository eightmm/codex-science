---
name: biomedical-evidence-reconciliation
description: "Reconcile conflicting multi-source biomedical evidence with explicit entity, release, cohort, assay, independence, and claim semantics. Use before final conclusions from multiple databases or evidence lanes."
license: MIT
---

# Biomedical Evidence Reconciliation

## Decision contract
Define the exact claim, normalized entity, population or model system, endpoint, time window, and confidence vocabulary before combining evidence; separate observation, association, mechanism, prediction, and actionability.
## Workflow
Build an evidence-dependency graph; verify entity and unit compatibility, classify source type and directness, deduplicate records propagated through portals or reviews, mark shared cohorts and samples, and compare release, assay, ancestry, tissue or state, endpoint, direction, uncertainty, correction, and missingness.
## Outputs
Emit a claim-evidence matrix, dependency graph, contradiction log, sensitivity analysis, confidence rationale, unresolved assumptions, and the smallest observation that would resolve each material conflict; classify claims as supported, replicated, suggestive, conflicting, unsupported, or unavailable.
## Boundaries
Missing, filtered, stale, and unavailable evidence are not negative evidence; do not average incompatible studies or hide disagreement behind an opaque score, and cap confidence at the weakest essential evidence link.
Link every decision to `$science-provenance` and require `$science-review` to challenge source independence, claim semantics, and the final confidence assignment.
