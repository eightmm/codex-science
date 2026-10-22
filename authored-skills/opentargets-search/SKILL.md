---
name: opentargets-search
description: "Query the Open Targets Platform for target-disease associations, tractability/safety, genetic/omics evidence, and known drugs, for therapeutic target identification. Public GraphQL API, no credential needed."
license: Apache-2.0
---

# Opentargets Search (Codex-native)

Codex-native adaptation of Google DeepMind's `opentargets-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Decision contract

Define the target-disease question, evidence cutoff, population or disease scope, and intended claim before retrieval. Normalize target to an Ensembl gene ID and disease to an EFO ID where applicable; preserve original symbols, labels, and resolver records. Specify whether the query seeks association, evidence components, tractability/safety context, or known drugs. An aggregate association score is a relative ranking heuristic, not a probability, causal estimate, or decision threshold; any threshold must be prespecified and justified. Separate direct evidence from ontology-propagated and other indirect associations.

## Reference usage

Read [association-score-and-provenance.md](references/association-score-and-provenance.md) before interpreting scores, comparing targets, combining evidence, or making a target-disease claim. It defines score semantics, dependence checks, controls, sensitivity analyses, and the evidence boundary.

## Workflow

1. **Gates (ask before proceeding).** On first use in a workspace, tell the user to review the source's terms of use and record the notice in provenance. Public network access is read-only; be polite about rate limits. Ask before installs or large downloads; write large responses to a file and parse them, and run any helper code with `uv run`, never bare `python3`. Record the notice and any required approval; stop at an unmet gate.
2. Define the target-disease question, scope, cutoff, intended claim, and whether the task needs an aggregate score or component evidence; record these in the query plan.
3. Resolve the gene via `$cx-ensembl-search` and disease via `$cx-ols-search`, normalizing to Ensembl gene ID and EFO ID where applicable; stop if ambiguity could change the result and record resolver evidence and alternatives.
4. Select a bounded retrieval route: POST an explicit GraphQL document and variables to `https://api.platform.opentargets.org/api/v4/graphql`, preserving requested fields; or use `science_search_opentargets` with `query` and optional `limit` for discovery only. For `science_query_source_v2` or `_v3`, inspect the source contract first, do not guess pagination fields, and record source, parameters, page size, page cap, cutoff, and completeness.
5. Validate response status, expected entity IDs, score/evidence fields, nulls, and truncation; distinguish unavailable results from an empty result and retain bounded transient retries. Record exact query, variables, fields, response, access time, and reported release/version; do not infer release from the current date.
6. Classify each returned record as direct or indirect/propagated and trace evidence to source records; identify shared cohorts, publications, databases, and propagated records before treating components as independent. Record dependencies, inclusion/exclusion reasons, and missing evidence.
7. Apply positive and negative query controls, then vary datatype weights, evidence cutoff/release, and propagation handling; if rank or interpretation changes materially, mark the conclusion fragile and record the changed result.
8. Return only entities and evidence actually retrieved, with claim status and uncertainty calibrated to the evidence boundary; save query, response, and cited identifiers with `$science-provenance`, and use `$science-review` for material interpretation before presenting.

## Outputs

Return one `target-association-evidence-v1` record with required fields: `question_and_scope`, `evidence_cutoff`, `query` (document/variables or connector query reference), `endpoint_or_tool`, `requested_fields`, `release_and_access_time`, `target_id`, `disease_id`, `evidence_records`, `score_components_as_reported`, `direct_or_indirect`, `source_dependencies`, `controls`, `sensitivity`, `included_and_excluded_records`, `claim_id_and_status`, `uncertainty_and_limitations`, and `next_action`. Claim status is `supported`, `contradicted`, `inconclusive`, or `unavailable`, and applies only to the stated association/retrieval claim. Record queries, endpoints, responses, and cited identifiers with `$science-provenance`; check claims with `$science-review` before presenting.

## Boundaries

Association scores are aggregated evidence, not proof of causation or clinical validity. Do not interpret missing evidence as a zero score, compare incompatible releases without reconciliation, or claim efficacy, safety, or actionability from a portal association alone. Cite only targets, diseases, or drugs actually returned. Preserve failures, nulls, conflicts, and source dependencies.

Source basis: [Open Targets Platform API](https://api.platform.opentargets.org/).
