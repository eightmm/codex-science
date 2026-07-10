---
name: indication-dossier
description: "Build an evidence-traceable indication dossier for a disease, target, mechanism, drug, biomarker, or therapeutic hypothesis. Use for landscape assessment, target-indication rationale, clinical pipeline review, translational gaps, and evidence-backed go/no-go questions; not for patient-specific advice."
license: MIT
---

# Indication Dossier

## Scope

Define the indication, population, stage, geography, intervention/target,
decision, evidence cutoff, and non-goals before searching. Separate scientific,
clinical, regulatory, commercial, and operational claims.

## Workflow

1. Resolve disease/target/drug identifiers with OLS, UniProt, Open Targets,
   ChEMBL, PubChem, and FDA sources. Preserve synonyms and ontology IDs.
2. Search primary literature with PubMed, Europe PMC, bioRxiv, and OpenAlex;
   search registered studies with ClinicalTrials.gov. Record exact queries,
   dates, inclusion/exclusion criteria, and deduplication.
3. Build evidence tables for disease biology, genetics, expression/cell context,
   target validation, mechanism, preclinical models, biomarkers, safety/liability,
   clinical competitors, trial status/results, regulatory facts, and major gaps.
4. Grade each claim by evidence type, independence, directness, recency, model
   relevance, replication, and conflict. Distinguish registered, completed,
   reported, peer-reviewed, approved, terminated, and merely announced states.
5. Produce an executive summary, evidence map, pipeline table, contradictions,
   uncertainties, falsifiable next experiments, and explicit go/no-go criteria.
6. Save citations, tables, queries, snapshots, and claim links under
   `artifacts/<run-id>/indication-dossier/` with `$science-provenance`; run
   `$science-review` before delivery.

## Boundaries

- Do not infer efficacy from mechanism, preclinical evidence, or trial existence.
- Do not provide diagnosis, treatment, dosing, or patient-matching advice.
- Clearly label inference, missing results, stale records, and conflicts of interest.

