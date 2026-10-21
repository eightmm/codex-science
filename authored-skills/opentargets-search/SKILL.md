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
Role: retriever. Define the target-disease question, evidence cutoff, population or disease scope, and intended claim before retrieval. Normalize target to an Ensembl gene ID and disease to an EFO ID where applicable; preserve original symbols, labels, and resolver records. Specify whether the query seeks association, evidence components, tractability/safety context, or known drugs. An aggregate association score is not a decision threshold unless prespecified and justified.

## Workflow
**Gates (ask before proceeding)**
- **Terms notice**: on first use in a workspace, tell the user to review the source's terms of use and record the notice in provenance.
- **Network / install**: read-only public access; be polite about rate limits. Write large responses to a file and parse them; if you write helper code, run it via `uv run`, never bare `python3`. Ask before installs or large downloads.

1. Resolve identifiers first (gene via `$cx-ensembl-search`, disease via `$cx-ols-search`). Record resolution evidence and stop if an ambiguous entity could change the result.
2. POST a GraphQL query to the documented endpoint `https://api.platform.opentargets.org/api/v4/graphql` with an explicit document and variables. Preserve exact query text, variables, requested fields, response, and access time. The bundled read-only `science_search_opentargets` tool accepts `query` and optional `limit`; use it for bounded discovery, not as a substitute for a specific GraphQL field selection. For generic structured retrieval, inspect the source contract before using `science_query_source_v2` or `_v3`; record the source, parameters, page size, page cap, cutoff, and completeness. Do not guess pagination fields.
3. Validate response status, expected entity IDs, score/evidence fields, nulls, and truncation. Preserve each evidence record's source identifiers and dependencies. Record release/version reported by the response; do not infer a release from the current date. Use bounded retries for transient failures and report unavailable results separately from empty results.
4. Include only targets, diseases, drugs, or evidence records actually returned. Keep source terms and citation identifiers with each record.

## Outputs
Return normalized target and disease IDs; the GraphQL query/variables or connector query reference; an evidence table with returned entity IDs, score and component fields as reported, source identifiers, release/access time, and missing values; records included/excluded and reasons; claim IDs with status `supported`, `contradicted`, `inconclusive`, or `unavailable`; dependencies, uncertainty, limitations, and rejected alternatives; and the smallest falsifiable next action. Record queries, endpoints, responses, and cited identifiers with `$science-provenance`; check claims with `$science-review` before presenting.

## Boundaries
Association scores are aggregated evidence, not proof of causation or clinical validity. Do not interpret missing evidence as a zero score, compare incompatible releases without reconciliation, or claim efficacy, safety, or actionability from a portal association alone. Cite only targets, diseases, or drugs actually returned. Preserve failures, nulls, conflicts, and source dependencies.

Source basis: [Open Targets Platform API](https://api.platform.opentargets.org/).
