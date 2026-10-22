---
name: indication-dossier
description: "Build an evidence-traceable indication dossier for a disease, target, mechanism, drug, biomarker, or therapeutic hypothesis. Use for landscape assessment, target-indication rationale, clinical pipeline review, translational gaps, and evidence-backed go/no-go questions; not for patient-specific advice."
license: MIT
---

# Indication Dossier

## Decision contract

Role: conductor. Define the indication, population, stage, geography, intervention/target, decision, evidence cutoff, intended claim strength, and non-goals before searching. Separate scientific, clinical, regulatory, commercial, and operational claims. Assign stable claim IDs and record each claim type, required support, falsifier, dependencies, uncertainty rule, and decision threshold. Ask only if a missing choice could materially change evidence selection or interpretation. A go/no-go framing supports a documented decision; it is not medical advice or a claim of efficacy.

## Reference usage

Read [references/indication-evidence-reconciliation.md](references/indication-evidence-reconciliation.md) before classifying evidence, comparing support across lanes, judging directness or independence, or proposing a go/no-go threshold. It defines evidence classes, dependency handling, uncertainty, controls, sensitivity checks, and the dossier's applicability limits.

## Workflow

1. Define the indication, population, stage, geography, intervention, decision, evidence cutoff, and claim strength; if any missing choice could change retrieval or interpretation, ask before searching and record the resolved contract.
2. Normalize disease, target, and drug identifiers with OLS, UniProt, Open Targets, ChEMBL, PubChem, and FDA sources; preserve submitted terms, synonyms, stable IDs, and ontology identifiers, and record each source/query and ambiguity. Use bundled read-only tools where available and a source's documented public route otherwise; no connector does not mean a source is unavailable. For bundled legacy tools, use only verified `query` and optional `limit` arguments (limit 1–10), and inspect the contract before generic v2/v3 queries.
3. Search primary literature with PubMed, Europe PMC, bioRxiv, and OpenAlex and registered studies with ClinicalTrials.gov; record exact queries, dates, cutoff, inclusion/exclusion rules, pagination, response completeness, and reported release/update values.
4. Build independent evidence lanes for disease biology, genetics, expression/cell context, target validation, mechanism, preclinical models, biomarkers, safety/liability, clinical competitors, trial status/results, regulatory facts, and gaps; for each, record normalized entities, allowed sources, claim IDs, inclusion rules, and stop conditions. Preserve trial and regulatory identifiers and distinguish registered, completed, reported, peer-reviewed, approved, terminated, and merely announced states.
5. Validate identifiers, source records, denominators, missingness, release, and truncation; include and exclude records with reasons, distinguish unavailable/null/stale/negative evidence, and use bounded retries without replacing failed structured retrieval with unsupported claims.
6. Classify each claim as genetic association, expression, preclinical model, clinical-trial, approval, or another explicitly named class; assess directness to the indication, independence, recency, model relevance, replication, and conflicts separately, then record supporting and contradictory evidence and dependencies.
7. Check registry status against published results, target-indication rationale against efficacy, and pipeline age against the evidence cutoff; run the reference's controls and sensitivity checks and record fragile, stale, or bias-sensitive conclusions.
8. Synthesize supported, contradicted, inconclusive, and unavailable claims against explicit go/no-go criteria; if evidence is indirect, dependent, stale, or conflicting, preserve that uncertainty and name the smallest falsifiable next action.
9. Save citations, tables, queries, snapshots, and claim links under `artifacts/<run-id>/indication-dossier/` with `$science-provenance`; run `$science-review` before delivery and record both handoff paths/statuses.

## Outputs

Return one `indication-evidence-dossier-v1` record with required fields: decision contract (`decision_contract`), evidence cutoff (`evidence_cutoff`), normalized inputs (`normalized_inputs`), claim register (`claim_register`), evidence lanes (`evidence_lanes`), pipeline table (`pipeline_table`), included records (`included_records`), excluded records (`excluded_records`), dependency groups (`dependency_groups`), conflicts (`conflicts`), claim statuses (`claim_statuses`), uncertainty (`uncertainty`), applicability domain (`applicability_domain`), limitations (`limitations`), rejected alternatives (`rejected_alternatives`), decision criteria (`decision_criteria`), next action (`next_action`), artifact paths and hashes (`artifact_paths_and_hashes`), and review receipt (`review_receipt`). Include an executive summary; each lane row carries source, identifier, query, release, inclusion status, evidence class, independence, indication directness, estimate/uncertainty, and missingness. Claim statuses are `supported`, `contradicted`, `inconclusive`, or `unavailable`.

## Boundaries

- Do not infer efficacy from mechanism, preclinical evidence, or trial existence.
- Do not provide diagnosis, treatment, dosing, or patient-matching advice.
- Clearly label inference, missing results, stale records, and conflicts of interest.
- Do not equate association with causality, trial registration with a result, approval in one context with another indication, or commercial activity with scientific support.
- Stop when population, indication identity, endpoint, or material source terms are unresolved; keep high-stakes clinical or regulatory claims inconclusive pending qualified review.
- A go/no-go summary is decision support, not a clinical recommendation.
