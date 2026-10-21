---
name: indication-dossier
description: "Build an evidence-traceable indication dossier for a disease, target, mechanism, drug, biomarker, or therapeutic hypothesis. Use for landscape assessment, target-indication rationale, clinical pipeline review, translational gaps, and evidence-backed go/no-go questions; not for patient-specific advice."
license: MIT
---

# Indication Dossier

## Decision contract
Role: conductor. Define the indication, population, stage, geography, intervention/target, decision, evidence cutoff, intended claim strength, and non-goals before searching. Separate scientific, clinical, regulatory, commercial, and operational claims. Assign stable claim IDs and record each claim type, required support, falsifier, dependencies, uncertainty rule, and decision threshold. Ask only if a missing choice could materially change evidence selection or interpretation.

## Workflow
1. Normalize disease, target, and drug identifiers with OLS, UniProt, Open Targets, ChEMBL, PubChem, and FDA sources. Preserve submitted names, synonyms, stable IDs, and ontology identifiers. Use bundled read-only tools where available; use a source's documented public route directly otherwise. No connector does not mean a source is unavailable. For bundled legacy tools, use only verified `query` and optional `limit` arguments (limit 1–10); inspect the contract before generic v2/v3 queries.
2. Search primary literature with PubMed, Europe PMC, bioRxiv, and OpenAlex; search registered studies with ClinicalTrials.gov. Record exact source queries, dates, cutoff, inclusion/exclusion criteria, pagination, response completeness, and release/update values reported. Deduplicate papers, trials, cohorts, and propagated portal records at the underlying evidence level. Keep registry status, publication state, and source availability separate.
3. Build independent evidence lanes for disease biology, genetics, expression/cell context, target validation, mechanism, preclinical models, biomarkers, safety/liability, clinical competitors, trial status/results, regulatory facts, and major gaps. Each lane gets normalized entities, allowed sources, claim IDs, evidence cutoff, inclusion rules, output table, and stop conditions. Preserve trial and regulatory identifiers and distinguish registered, completed, reported, peer-reviewed, approved, terminated, and merely announced states.
4. Validate identifiers, source records, denominators, missingness, release, and truncation. Record returned and excluded evidence with reasons. Grade directness, independence, recency, model relevance, replication, and conflicts; do not collapse these into an unexplained score. Reconcile contradictory lanes and distinguish unavailable, null, stale, and negative evidence. Use bounded retries; do not replace failed structured retrieval with unsupported claims.
5. Synthesize only after dependency deduplication. State evidence-supported, contradicted, inconclusive, and unavailable claims separately, with explicit go/no-go criteria and falsifiable next experiments. Save citations, tables, queries, snapshots, and claim links under `artifacts/<run-id>/indication-dossier/` with `$science-provenance`; run `$science-review` before delivery.

## Outputs
Return an executive summary; normalized inputs and assumptions; a claim register; lane-by-lane evidence table with source, identifier, query, release, inclusion status, evidence type, independence, directness, estimate/uncertainty, and missingness; a pipeline table; included/excluded records and reasons; conflicts and dependency groups; statuses `supported`, `contradicted`, `inconclusive`, or `unavailable`; limitations, rejected alternatives, explicit decision criteria, and the smallest falsifiable next action. Include artifact paths and hashes through `$science-provenance` and the independent review receipt.

## Boundaries
- Do not infer efficacy from mechanism, preclinical evidence, or trial existence.
- Do not provide diagnosis, treatment, dosing, or patient-matching advice.
- Clearly label inference, missing results, stale records, and conflicts of interest.
- Do not equate association with causality, trial registration with a result, approval in one context with another indication, or commercial activity with scientific support. Stop when population, indication identity, endpoint, or material source terms are unresolved; keep high-stakes clinical or regulatory claims inconclusive pending qualified review.

