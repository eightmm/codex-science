---
name: biomedical-evidence-reconciliation
description: "Reconcile conflicting multi-source biomedical evidence with explicit entity, release, cohort, assay, independence, and claim semantics. Use before final conclusions from multiple databases or evidence lanes."
license: MIT
---

# Biomedical Evidence Reconciliation

## Decision contract
Define the exact claim, normalized entity, population or model system, endpoint, time window, and confidence vocabulary before combining evidence; separate observation, association, mechanism, prediction, and actionability.

## Reference usage
- Read [references/reconciliation-method.md](references/reconciliation-method.md) before assigning claim status, resolving dependence, or comparing heterogeneous evidence.

## Workflow
1. Freeze the claim, entity identifiers, population or model system, endpoint, time window, evidence cutoff, and confidence vocabulary; if any is ambiguous, record it as unresolved and do not aggregate.
2. Retrieve the minimum primary records needed for each claim; retain query, source, release or access date, record identifier, and snapshot hash, and label unavailable sources.
3. Normalize entities, units, assay endpoints, populations, and outcome direction; when mappings or units cannot be reconciled, record the mismatch and keep evidence in separate strata.
4. Classify each statement as observation, association, mechanism, prediction, or actionability using the reference criteria; label source type and directness, and record the exact supporting result and inference step.
5. Build the evidence-dependency graph across studies, cohorts, samples, reviews, portals, and propagated records; merge duplicates and record shared participants and provenance links.
6. Compare compatible evidence on design, assay, ancestry, tissue or state, endpoint, direction, uncertainty, correction, release, and missingness; record agreements and contradictions without averaging incompatible results.
7. Test dependence, inclusion, release, and compatibility choices with the prescribed sensitivity checks; record status changes and cap confidence at the weakest essential evidence link.
8. Assign supported, replicated, suggestive, conflicting, unsupported, or unavailable status only by the stated criteria; record the rationale, unresolved assumptions, and smallest discriminating observation.
9. Verify that each conclusion traces to retained sources and that missing or filtered evidence was not treated as negative; record the check result, then hand off for independent review.

## Outputs
Emit `biomedical-evidence-reconciliation-v1` with required fields `claim_register`, `evidence_matrix`, `dependency_graph`, `contradiction_log`, `sensitivity_analysis`, `confidence_rationale`, `unresolved_assumptions`, `discriminating_observations`, and `provenance`.

## Boundaries
Missing, filtered, stale, and unavailable evidence are not negative evidence; do not average incompatible studies or hide disagreement behind an opaque score, and cap confidence at the weakest essential evidence link.
Link every decision to `$science-provenance` and require `$science-review` to challenge source independence, claim semantics, and the final confidence assignment.
