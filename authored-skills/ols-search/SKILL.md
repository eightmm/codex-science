---
name: ols-search
description: "Search EMBL-EBI Ontology Lookup Service (OLS) for biomedical ontology terms, definitions, and hierarchies across 250+ ontologies (GO, DOID, HP, UBERON, CL). Use for term search, term details, or navigating parents/children/ancestors; labels alone are not stable identifiers. Public API, no credential needed."
license: Apache-2.0
---

# Ols Search (Codex-native)

Codex-native adaptation of Google DeepMind's `embl-ebi-ols` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the
  source's terms of use and record the notice in provenance.
- **Network / install**: read-only public access; be polite about rate limits.
  Write large responses to a file and parse them; if you write helper code, run
  it via `uv run`, never bare `python3`. Ask before installs or large downloads.

## Endpoints

- OLS4 API `https://www.ebi.ac.uk/ols4/api` (docs at `/ols4/api-docs`)

## Decision contract

State the concept, organism/context if relevant, target ontology or allowed ontology set, term-use purpose, and evidence cutoff. Record ontology namespace and term IRI/CURIE as the canonical identity; labels and synonyms are search strings only. Distinguish term discovery from any biological assertion that uses the term.

## Workflow

Search across ontologies first with `science_search_ols`; use OLS4 directly for
ontology scoping and hierarchy traversal.

1. Search a term with `/ols4/api/search?q=<term>` (optionally scope by `ontology=`).
2. Fetch details and navigate the hierarchy (parents, children, ancestors) via the term IRI endpoints.
3. The bundled `science_search_ols` connector accepts `query` and optional `limit` and returns term identifiers, labels, ontology and IRI; use the direct OLS4 endpoints above for ontology filtering, details and hierarchy. Serialize query, ontology, filters and pagination explicitly; record endpoint, access time, release/update reported, page coverage, result count and hash.
4. Validate response schema, ontology membership, IRI/CURIE and obsolete/replaced status when supplied. Keep exact returned and excluded terms with reasons. Distinguish missing definitions, null metadata, no match, filtered terms and unavailable responses; detect truncation before claiming hierarchy completeness.
5. Retry transient errors a bounded number of times and respect service throttling. Do not substitute similarly labeled terms across ontologies without recording the mapping and rationale.

## Outputs

Return normalized search term, ontology scope, term IDs/IRIs, labels/synonyms, definitions and hierarchy links when returned, exact query/release provenance, returned/excluded terms with reasons, and missingness. Assign claim IDs with `supported`, `contradicted`, `inconclusive`, or `unavailable` status only for term-resolution questions; ontology membership alone does not support a biological claim. Report uncertainty, limitations, and the smallest falsifiable next lookup. Save term records, query ledger and hashes via `$science-provenance`; use `$science-review` when ontology mappings materially affect a scientific conclusion.

## Boundaries

- Always report the ontology and term IRI/CURIE (e.g. `GO:0006915`); labels alone are ambiguous.
- Cite only terms actually returned.
- A parent-child relationship is an ontology assertion, not a causal or experimental relation. Do not treat ontology labels as interchangeable across ontologies, or an absent term as evidence that a biological process is absent. Stop when the required ontology or term identity is unresolved. Preserve the terms notice, read-only network boundary, `uv run`, install and large-download gates above.
