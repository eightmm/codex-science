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

State whether the target is a database association, a channel-specific evidence
observation, a predicted functional association, or an experimentally measured
physical interaction. Record protein set, taxon, namespace, prespecified
`required_score`, channel fields, release, assay context if known, and whether
the output is partners, network, or enrichment. A combined STRING score is a
confidence score for functional association, not a probability of physical
binding, causality, direction, or condition-specific activity.

## Reference usage

Read [references/string-evidence.md](references/string-evidence.md) before
interpreting scores, networks, or enrichment. Apply its channel-specific claim
classes, dependence audit, controls, sensitivity criteria, and applicability
limits; record the selected threshold and release in the query receipt.

## Workflow

1. **Gates (ask before proceeding).** On first use in a workspace, tell the
   user to review the source's terms of use and record the notice in provenance.
   Keep access public and read-only, respect rate limits, write large responses
   to files for parsing, run helper code via `uv run` (never bare `python3`),
   and ask before installs or large downloads; record the gate outcome.
2. Classify the requested evidence as functional association, channel evidence,
   experimentally measured physical interaction, or enrichment; if a causal or
   direct-binding claim exceeds the returned evidence, narrow it and record why.
3. Resolve proteins with optional `science_search_string` (`query`, `limit`
   1–10, default 5), then, before any network or enrichment query, map identifiers via
   `/json/get_string_ids`; preserve original names, canonical STRING IDs,
   taxon, mapping alternatives, and unresolved ambiguity. Stop if alternatives
   materially change the network.
4. Prespecify taxon, `required_score`, queried channels, and background universe
   for enrichment. Use `network_type=physical` for physical-interaction claims;
   this does not make a STRING score a binding probability. Use
   `https://string-db.org/api` endpoints `/json/network`,
   `/json/interaction_partners`; POST the set to `/json/enrichment` when doing
   enrichment. Record exact serialization, release/version, access time, page
   state, result cap, and returned count.
5. Validate status, response shape, IDs, species, score scale, channels, and
   completeness. Retain missing fields and excluded edges with reasons; bound
   query size, pages, and transient retries. Failed or truncated responses are
   unavailable, with partial records retained as partial evidence.
6. For every edge, report returned experiment, database, text-mining,
   co-expression, and other channel scores separately when supplied. Treat a
   combined score only as STRING's integrated functional-association confidence;
   do not convert it into a binding probability. Record missing channel values.
7. For enrichment, report input/mapped/background counts and returned
   multiple-testing fields. Check a well-characterized expected partner or
   function and a random same-size set from the eligible universe; vary the
   prespecified score threshold and evidence-channel filter, calling results
   fragile if the claim or status changes. Record controls and sensitivity.
8. Report uncertainty and context limits, preserve query/response artifacts via
   `$science-provenance`, and use `$science-review` for material network,
   function, or mechanism conclusions; record handoffs and unresolved findings.

## Outputs

Return one `string-association-evidence-v1` record with required fields: claim
identifier (`claim_id`); claim class (`claim_class`); status (`status`:
supported, contradicted, inconclusive, or unavailable); taxon (`taxon`);
submitted and mapped proteins (`submitted_ids`, `mapped_ids`); mapping
alternatives (`mapping_alternatives`); STRING release (`release`); query and
parameters (`query`, `parameters`); prespecified threshold (`required_score`);
edge IDs and scores by channel (`edges`, `channel_scores`); combined score
semantics (`combined_score_interpretation`); background and enrichment fields
(`background`, `enrichment`); controls and sensitivity (`controls`,
`sensitivity`); uncertainty and applicability (`uncertainty`, `applicability`);
inclusion/exclusion reasons (`record_reasons`); source URLs, access time,
artifact hashes, and smallest falsifiable next query (`source_urls`,
`accessed_at`, `artifact_hashes`, `next_query`). Save query and response
artifacts with `$science-provenance`.

## Boundaries

- STRING integrates predicted and experimental evidence; distinguish channels
  and cite only IDs actually returned. The combined score is not a probability
  that two proteins physically interact.
- An edge does not prove direct binding, direction, causality, or activity in
  the user's tissue or condition. Network proximity is not mechanism.
- Enrichment depends on the submitted universe/background and multiple testing.
  Missing edges do not establish absence; failed or truncated queries are
  unavailable. Respect terms and redistribution limits.
- Stop if species or identifier mapping is materially ambiguous. `$science-review`
  is mandatory for material mechanism claims.
