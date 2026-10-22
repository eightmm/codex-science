---
name: ols-search
description: "Search EMBL-EBI Ontology Lookup Service (OLS) for biomedical ontology terms, definitions, and hierarchies across 250+ ontologies (GO, DOID, HP, UBERON, CL). Use for term search, term details, or navigating parents/children/ancestors; labels alone are not stable identifiers. Public API, no credential needed."
license: Apache-2.0
---

# Ols Search (Codex-native)

Codex-native adaptation of Google DeepMind's `embl-ebi-ols` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Decision contract

State the concept, organism/context if relevant, target ontology or allowed ontology set, term-use purpose, and evidence cutoff. Record ontology namespace and term IRI/CURIE as the canonical identity; labels and synonyms are search strings only. Distinguish term discovery and ontology membership from any biological assertion that uses the term. Treat obsolete terms and replacements as versioned identity changes, not silent substitutions.

## Reference usage

Read [term-identity-mapping-and-versioning.md](references/term-identity-mapping-and-versioning.md) before selecting a term, accepting an obsolete replacement, mapping across ontologies, traversing hierarchy for a scientific conclusion, or interpreting a match. It defines term identity, mapping confidence, controls, sensitivity, and applicability limits.

## Workflow

1. **Gates (ask before proceeding).** On first use in a workspace, tell the user to review the source's terms of use and record the notice in provenance. Public network access is read-only; be polite about rate limits. Ask before installs or large downloads; write large responses to a file and parse them, and run any helper code with `uv run`, never bare `python3`. Record the notice and any required approval; stop at an unmet gate.
2. Define the concept, organism/context, allowed ontology set, purpose, and evidence cutoff; record the search contract and retain the original wording.
3. Search across ontologies first with `science_search_ols`; call OLS4 API `https://www.ebi.ac.uk/ols4/api` directly (docs at `/ols4/api-docs`; search form `/ols4/api/search?q=<term>` with `ontology=` for scoping) for term details, and traverse parents, children, and ancestors via the term IRI endpoints. Record endpoint, query, ontology filters, access time, and reported release/update.
4. Serialize filters and pagination explicitly; retain result count, page coverage, and response hash. The bundled connector accepts `query` and optional `limit`, and returns term identifiers, labels, ontology, and IRI; use direct OLS4 endpoints for details/hierarchy.
5. Validate response schema, ontology membership, canonical IRI/CURIE, obsolete/replaced status, and returned synonyms/definition; distinguish missing definition, null metadata, no match, filtered term, truncation, and unavailable response. Retry transient errors a bounded number of times, respect service throttling, and retain exact returned and excluded candidates with reasons.
6. Compare candidate definitions, namespace, organism, relationships, and provenance to the intended concept; do not substitute similarly labeled terms across ontologies without a recorded mapping and rationale. Stop if term identity remains ambiguous and record the unresolved alternatives.
7. Check a known term as a positive control and a deliberately unrelated query as a negative control; vary ontology scope, synonym handling, obsolete-term inclusion, and any cross-ontology mapping. If the selected identity or interpretation changes materially, mark the mapping fragile and record the alternatives.
8. Return a term-resolution claim only at the supported identity level; save term records, query ledger, and hashes via `$science-provenance`, and use `$science-review` when mappings materially affect a scientific conclusion.

## Outputs

Return one `ontology-term-resolution-v1` record with required fields: `concept_and_context`, `ontology_scope`, `purpose`, `evidence_cutoff`, `query_and_filters`, `endpoint_or_tool`, `release_and_access_time`, `result_count_and_page_coverage`, `term_candidates`, `canonical_iri_and_curie`, `labels_synonyms_definitions`, `obsolete_and_replacement_status`, `hierarchy_links`, `mapping_basis_and_confidence`, `controls`, `sensitivity`, `included_and_excluded_terms`, `claim_id_and_status`, `uncertainty_and_limitations`, and `next_action`. Claim status `supported`, `contradicted`, `inconclusive`, or `unavailable` applies only to term resolution; ontology membership alone does not support a biological claim. Save term records, query ledger, and hashes via `$science-provenance`; use `$science-review` when ontology mappings materially affect a scientific conclusion.

## Boundaries

- Always report the ontology and term IRI/CURIE (e.g. `GO:0006915`); labels alone are ambiguous.
- Cite only terms actually returned.
- A parent-child relationship is an ontology assertion, not a causal or experimental relation. Do not treat ontology labels as interchangeable across ontologies, or an absent term as evidence that a biological process is absent. Stop when the required ontology or term identity is unresolved.
- Preserve the terms notice, read-only network boundary, `uv run`, install and large-download gates above.
