---
name: locus-to-gene-prioritization
description: "Prioritize candidate genes at human genetic loci using curated association, credible-set/L2G, colocalization, eQTL, coding, burden, expression, and pathway evidence. Use for GWAS follow-up and target prioritization."
license: MIT
---

# Locus-to-Gene Prioritization

## Decision contract
Define trait and ontology ID, assembly, ancestry, lead variant or credible set, locus boundary, LD reference, tissues or cell states, evidence cutoff, ranking objective, and criteria that would change the decision.

## Reference usage
- Read [references/locus-to-gene-method.md](references/locus-to-gene-method.md) before assigning lane evidence, dependence, candidate ranking, or score interpretation.
- Read [references/locus-to-gene-method.md](references/locus-to-gene-method.md) before sensitivity analysis or transferring a ranking to another ancestry, tissue, or trait context.

## Workflow
1. Freeze trait and ontology, genome assembly, ancestry, locus definition, credible-set input, LD reference, tissues or cell states, evidence cutoff, ranking objective, and decision-change criteria; record unresolved inputs before analysis.
2. Normalize variants and candidate genes against pinned sources; preserve identifiers, coordinates, transcript context, source release, query, and exact retrieved records.
3. Construct separate lanes for fine-mapping/L2G, coding consequences, colocalization/eQTL, rare-variant burden, chromatin/contact, expression/cell context, pathways/mechanism, and prior functional validation; record each lane's input and output.
4. Check build, allele, LD, trait/phenotype, tissue, and assay alignment; if an input is incompatible or unavailable, mark that lane unavailable instead of imputing support.
5. Classify direct observations, associations, molecular links, predictions, and functional/mechanistic support using the reference; record the directness and uncertainty of each gene link.
6. Trace shared studies, cohorts, variants, LD signals, portals, and correlated annotations; deduplicate propagated records and record dependence so a single signal cannot masquerade as multiple independent lanes.
7. Score only with transparent, prespecified per-lane rules and controls; vary LD reference, credible-set threshold/input, tissue, source release, dependence collapse, and lane inclusion, and record rankings and decision changes.
8. Return ranked candidates with counterevidence, conflicts between lanes or sources, rejected alternatives, confidence by gene-link claim, ancestry/tissue limitations, and the smallest experiment or analysis likely to reorder candidates.
9. Verify ranking reproducibility from saved inputs and rules and confirm proximity or correlated annotations did not become causal proof; record the verification result and review handoff.

## Outputs
Return `locus-to-gene-prioritization-v1` with required fields `locus_contract`, `candidate_rankings`, `lane_evidence`, `counterevidence`, `conflicts`, `dependency_graph`, `rejected_candidates`, `ranking_rule`, `sensitivity_analysis`, `claim_confidence`, `limitations`, `reordering_experiment`, and `provenance`. Report conflicts between lanes or sources separately from per-gene counterevidence.

## Boundaries
Proximity is weak evidence, colocalization is not causality, shared LD and correlated annotations can inflate support, and missing a portal result is not gene-level negative evidence.
Save the credible set, lane tables, deduplication decisions, ranking rule, and rejected genes with `$science-provenance`; run `$science-review` before presenting a target-prioritization claim.
