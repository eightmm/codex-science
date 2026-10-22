---
name: chembl-search
description: "Query the ChEMBL database for bioactive molecules, drug targets, bioactivity measurements (IC50/Ki/EC50), approved drugs, and mechanisms. Use when the user asks about compounds, targets, potency values, or drug mechanisms. Public REST API, no credential needed."
license: Apache-2.0
---

# ChEMBL Database Query (Codex-native)

Codex-native adaptation of Google DeepMind's `chembl-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public ChEMBL REST API directly through Codex's own tools.

## Decision contract

Specify compound/target, question (identity, measured activity, mechanism, or
indication), species, evidence cutoff, and endpoints. Assign claim IDs and classify
each claim as a deposited/curated record, a reported measurement, a validated
property, or a mechanistic/clinical inference. A returned activity is a reported
measurement, not by itself a validated property or mechanism. Before comparing
measurements, fix structure identity, assay/target/organism, activity type, units,
confidence, aggregation rule, and uncertainty; stop if any unresolved choice
changes the conclusion.

## Reference usage

- Read [references/chembl-activity-evidence.md](references/chembl-activity-evidence.md)
  before interpreting activities, pChEMBL, assay confidence, validity comments,
  duplicate records, or aggregating measurements.
- Read [references/chemical-identity-and-sensitivity.md](references/chemical-identity-and-sensitivity.md)
  before matching structures, changing a threshold/unit conversion, or making a
  cross-source or scope claim.

## Workflow

1. **Gates (ask before proceeding).** On first use in a workspace, tell the
   user to review the ChEMBL terms
   (https://chembl.gitbook.io/chembl-interface-documentation/about) and record
   the notice in provenance. Public read-only HTTP: be polite about rate limits.
   Write responses to a file and parse them; run helper code via `uv run`, never
   bare `python3`. Ask before installs or large downloads. Record gate completion.
2. Define claim IDs, compound/target and species; resolve gene/protein to target
   via `$cx-uniprot-search` when needed. Use optional `science_search_chembl`
   (`query`, `limit` 1–10, default 5) or direct API at
   `https://www.ebi.ac.uk/chembl/api/data/` with `?format=json`. Record the exact
   query, candidates, and identity-selection rationale.
3. Retrieve relevant `molecule`, `target`, `activity`, `assay`, `mechanism`, or
   `drug_indication` records. Follow only bounded pagination; retain exact
   URL-encoded query, filters, access time, release/update if reported, pages,
   result count, and response artifacts. Verify response shape and completeness.
4. Resolve structure and target identity before comparison. Keep salts,
   tautomers, stereoisomers, target components, and species distinct unless an
   explicit normalization justifies joining them; record included and excluded
   IDs with reasons and retain unmapped inputs.
5. Classify evidence using [references/chembl-activity-evidence.md](references/chembl-activity-evidence.md):
   preserve `standard_type`, `standard_value`, and `standard_units` together;
   inspect assay type, confidence, validity comments, activity comments, and
   duplicates. Compare pChEMBL only within stated compatible contexts; record
   how assay heterogeneity affects each claim.
6. Run a known reference-compound check and a decoy name-collision check. Vary
   the activity cutoff, unit conversion, and aggregation choice; record changes
   to included records and claim status. Failed or truncated endpoints are
   unavailable, not evidence of no activity.
7. Return the required `chembl-activity-evidence-v1` fields, preserve queries,
   cited IDs, and response artifact hashes with `$science-provenance`, then use
   `$science-review` before material potency, mechanism, or indication claims.
   Record unresolved uncertainty and the smallest falsifiable follow-up.

## Outputs

Return one `chembl-activity-evidence-v1` record with: claim identifier
(`claim_id`); claim class and status (`claim_class`, `status`); normalized
compound/target/species (`entity_ids`); source, release, exact query, access
time, pages, and result count (`source_receipt`); activity ID, assay ID/type,
target confidence, reported type/value/unit, pChEMBL, validity/activity
comments, and duplicate relationship (`measurements`); inclusions and
exclusions with reasons (`record_decisions`); shared-source/cohort/record
dependencies (`dependencies`); control outcomes (`controls`); threshold,
conversion, and aggregation variants (`sensitivity`); uncertainty and
applicability domain (`uncertainty`, `applicability`); limitations, next
falsifiable action, artifact paths and hashes (`limitations`, `next_action`,
`artifacts`). Use status values supported, contradicted, inconclusive,
unavailable, or withdrawn.

## Boundaries

- Cite only ChEMBL IDs and values actually returned; never invent IDs,
  potencies, or units. Keep raw activity IDs and assay provenance for each
  measurement.
- A value without type and unit is uninterpretable. pChEMBL is assay-dependent,
  not a universal cross-assay scale; do not average or compare incompatible
  assays, targets, or organisms as equivalent. Do not treat one low-confidence
  record as strong evidence.
- Bioactivity and mechanism records do not alone validate a property, establish
  mechanism, or support clinical/dosing guidance. Approved-drug and indication
  records describe the database record, not medical advice.
- Stop if identity, species, assay, or unit ambiguity changes interpretation.
  Preserve nulls, failed/truncated retrieval as unavailable, and all exclusions.
  Respect ChEMBL terms and redistribution limits. `$science-review` is mandatory
  for material potency, mechanism, or indication conclusions.
