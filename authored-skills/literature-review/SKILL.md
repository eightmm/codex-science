---
name: literature-review
description: "Run a protocol-driven, updateable literature review with exact multi-source queries, study-level deduplication, structured extraction, evidence dependency tracking, bounded synthesis, provenance, and independent review. Use for systematic, scoping, rapid, living, or evidence-landscape reviews where discovery alone is insufficient."
license: MIT
---

# Literature Review

Use this conductor when the deliverable is an auditable body-of-evidence synthesis rather than a citation list or list of papers. Discovery tools retrieve records; this skill owns the protocol, eligibility, study identity, extraction, dependency graph, synthesis boundary, update diff, and review handoff.

## Decision contract

Before retrieval, record:

- the decision or deliverable and the exact scientific question;
- PICO, PECO, PICOT, SPIDER, or another explicit framework;
- population or system, intervention or exposure, comparator, outcomes, study designs, time window, language and publication-state rules;
- permitted inference level and non-goals;
- evidence cutoff, sources, update mode, and stopping rule;
- primary claim IDs, required evidence, uncertainty, and falsifiers.

A material change to eligibility, outcome, cutoff, or permitted inference creates a new protocol revision. Do not rewrite the original protocol after seeing favorable records.

## Workflow

### Source plan

1. Select the smallest complementary source set. For biomedicine, prefer `$cx-pubmed-search` plus `$cx-europepmc-search`; add `$cx-biorxiv-search` for preprints and `$cx-openalex-search` for citation or cross-disciplinary coverage. Use `$cx-arxiv-search` for mathematics, physics, computer science, quantitative biology, and statistics.
2. Translate the question into source-specific exact queries. Record query strings, filters, date ranges, pagination, access times, result counts, source releases or update timestamps, and response hashes in `queries.jsonl`.
3. Preserve source availability separately from scientific evidence. A failed query is `unavailable`, not a negative result.
4. Search references, citations, registries, or related datasets only when the protocol permits snowballing. Label records found outside the prespecified electronic search.

### Study identity and eligibility

1. Normalize DOI, PMID, PMCID, arXiv ID, trial or dataset accession, title, year, authors, and publication version.
2. Deduplicate at the underlying study level, not only the article level. Link preprint, conference abstract, journal article, correction, protocol, registry record, and secondary analysis to one study family where appropriate.
3. Record every inclusion and exclusion decision with reviewer, stage, and reason. Do not silently remove near matches.
4. Keep primary research, preprints, secondary reviews, guidelines, registry entries, datasets, and portal summaries distinct.
5. Detect shared cohorts, samples, sites, authors, databases, and propagated portal records before treating results as independent replication.

### Structured extraction

For each included study save a machine-readable row containing, where applicable:

- identifiers, study family, publication state, funding and conflicts;
- design, population or system, setting, sample unit, sample size, eligibility, intervention or exposure, comparator, endpoint and follow-up;
- assay, model, preprocessing, covariates, missing-data handling, statistical method, multiplicity correction, effect estimate, uncertainty and units;
- prespecified versus post-hoc status, attrition, protocol deviations, limitations, and risk-of-bias judgments;
- claim IDs supported or contradicted, independence group, and exact source locations.

Do not infer an unreported method, denominator, result, or uncertainty from an abstract or portal summary.

### Evidence graph and synthesis

1. Save `claims.json` as a `claim-register`, `evidence_graph.json` as an `evidence-graph`, study extraction as a `study-table`, and each independent search or extraction lane as a `lane-receipt` artifact.
2. Represent support, contradiction, derivation, duplication, shared cohort or samples, source propagation, and model-training dependence explicitly.
3. Grade directness, independence, precision, applicability, risk of bias, publication state, consistency, and missingness. Do not collapse them into an unexplained score.
4. Separate direct evidence, reasonable inference, contradiction, unavailable results, and absence of evidence.
5. A replicated claim requires independent evidence groups. Multiple papers from one cohort, mirrored portal records, or repeated analysis of the same sample do not count as replication.
6. The final confidence cannot exceed the weakest essential evidence link. Withdraw or downgrade a conclusion when its required support is absent.

### Living-update mode

Keep prior snapshots immutable. Save a new snapshot with the revised cutoff and run:

`<plugin-root>/scripts/diff_literature_review.py <previous.json> <current.json> --output <diff.json>`

Report added, removed, and changed queries, studies, eligibility decisions, and claims. Never replace a previous reviewed narrative without a diff and review invalidation.

## Outputs

Return and save:

- protocol and source plan;
- exact query ledger and search-flow counts;
- deduplicated candidate and included-study tables with exclusion reasons;
- structured extraction and risk-of-bias records;
- claim register, evidence graph, lane receipts, contradictions, dependency groups, and unresolved assumptions;
- bounded narrative synthesis and the smallest discriminating next evidence;
- current snapshot, prior-to-current diff when updating, and review receipt.

Record every artifact and hash with `$science-provenance`. Run `$science-review` in `record`, `source`, and `method` modes before delivery; use `reproduction` only when a separate worker actually re-executes the searches and extraction.

## Boundaries

- Stop for an eligibility ambiguity that changes the evidence set, an unavailable full text required for a material claim, unresolved study identity, or a source restriction that prevents traceable use.
- Do not label a review systematic merely because multiple databases were searched.
- Do not count secondary citations as verification of the primary result.
- Do not infer causality, clinical actionability, safety, or generalization beyond the included designs and populations.
- Do not use vote counting by statistical significance as a substitute for effect estimates, uncertainty, heterogeneity, and study quality.
- Preserve negative, null, conflicting, retracted, corrected, and unavailable evidence.

Source basis: independently designed Codex workflow informed by FAIR provenance, reproducible review practice, and the public source contracts used by Codex Science.
