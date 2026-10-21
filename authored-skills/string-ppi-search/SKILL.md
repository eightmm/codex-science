---
name: string-ppi-search
description: "Query STRING for protein-protein interactions, interaction confidence/evidence, interaction partners, and functional enrichment. Use for PPI networks and enrichment of a protein set. Public API, no credential needed."
license: Apache-2.0
---

# String Ppi Search (Codex-native)

Codex-native adaptation of Google DeepMind's `string-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Decision contract

State the protein set or interaction question, organism/taxon, evidence cutoff,
identifier namespace, and whether the deliverable is partners, a network, or
functional enrichment. Resolve ambiguous gene/protein names before querying;
preserve canonical identifiers and mapping alternatives. Specify the confidence
threshold before inspecting results and distinguish interaction evidence
channels from a direct physical interaction claim.

## Workflow

1. **Gates (ask before proceeding).** On first use in a workspace, tell the
   user to review the source's terms of use and record the notice in provenance.
   Public read-only access: be polite about rate limits. Write large responses
   to a file and parse them; run helper code via `uv run`, never bare `python3`.
   Ask before installs or large downloads.
2. Resolve proteins with optional `science_search_string` (`query`, `limit`
   1–10, default 5), which returns STRING ID, preferred name, species,
   annotation, and URL. Direct STRING API base is `https://string-db.org/api`.
   Preserve the original identifier, mapping response, taxon ID, and ambiguity.
3. Map identifiers first using `/json/get_string_ids`; then request network or
   partners (`/json/network`, `/json/interaction_partners`) with species and prespecified `required_score`. For enrichment,
   POST the identifier set to `/json/enrichment`. Record exact endpoint,
   serialized parameters, submitted IDs, score scale/threshold, access time,
   response-reported release/version, page state, and returned count. Bound
   query size and pagination.
4. Validate HTTP status, response shape, IDs, species, and completeness. Detect
   truncation; preserve null/missing fields. Use bounded retries for transient
   errors, and report failures as unavailable. Record returned interactions and
   excluded records with reasons. For each edge retain score and channel fields
   actually returned; do not silently turn a combined score into a measured
   binding probability.
5. Report species and confidence threshold. State that STRING combines
   predicted and experimental evidence, and distinguish evidence channels.
   Enrichment depends on the submitted universe/background and multiple-testing
   fields returned. Save query and response artifacts with `$science-provenance`;
   use `$science-review` before material network or mechanism claims.

## Outputs

Return normalized proteins, species and assumptions; mapping table; interaction
or enrichment table with IDs, score, evidence channels, source URL, and
inclusion/exclusion reason; claim IDs marked supported/contradicted/
inconclusive/unavailable; query/version/access-time details; uncertainty,
threshold/background sensitivity, limitations, and smallest falsifiable next
query. Save artifacts and hashes through `$science-provenance`.

## Boundaries

- Interactions include predictions; distinguish evidence channels. Cite only
  identifiers actually returned.
- A STRING edge does not prove direct binding, direction, causality, or activity
  in the user's tissue/condition. Do not treat network proximity as mechanism.
- Stop if species or identifier mapping is materially ambiguous. Missing edges
  are not evidence of no interaction; failed/truncated queries are unavailable.
  Respect terms and redistribution limits. `$science-review` is mandatory for
  material mechanism claims.
