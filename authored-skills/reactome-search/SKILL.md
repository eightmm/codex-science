---
name: reactome-search
description: "Query Reactome Content and Analysis Services: pathway enrichment of a gene list, identifier mapping, reaction participants, pathway hierarchy, and knowledgebase search. Use for pathway analysis and enrichment. Public API, no credential needed."
license: Apache-2.0
---

# Reactome Search (Codex-native)

Codex-native adaptation of Google DeepMind's `reactome-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Decision contract

Before querying, classify the requested claim as a curated pathway/reaction
record, a Reactome orthology-inferred event, an over-representation
association, or a proposed mechanism. Record organism, input namespace, list,
analysis options (projection, interactors), release, and intended use. A
Reactome stable ID (such as a returned `stId`) is distinct from a display name
or external identifier. Keep submitted IDs distinct from mapped IDs. A curated
record supports database membership; an orthology-inferred event is
predicted transfer; enrichment is a set-level statistical association. None
alone establishes causal mechanism or pathway activity.

## Reference usage

Read [references/reactome-evidence.md](references/reactome-evidence.md) before
enrichment, interpreting inferred events, or making pathway/mechanism claims.
Use its claim classes, dependence checks, controls, sensitivity rules, and
applicability limits; record the selected rules and source release with the
query receipt.

## Workflow

1. **Gates (ask before proceeding).** On first use in a workspace, tell the
   user to review the source's terms of use and record the notice in provenance.
   Keep access public and read-only, respect rate limits, write large responses
   to files for parsing, use `uv run` for helper code (never bare `python3`),
   and ask before installs or large downloads; record the gate outcome.
2. Choose the claim class and analysis settings for lookup, mapping,
   enrichment, or interpretation; identify the evidence class and narrow
   causal requests to association, recording the claim boundary.
3. Normalize organism, namespace, and identifiers; resolve ambiguity before
   analysis and retain each original ID and mapping alternative, or stop and
   record unresolved inputs.
4. Pin the available Reactome release/update. AnalysisService uses all
   Reactome-annotated entities for the species as its background; test any
   alternative universe offline with downloaded Reactome gene sets.
5. Query optionally with `science_search_reactome` (`query`, `limit` 1–10,
   default 5), or use ContentService
   `https://reactome.org/ContentService` and AnalysisService
   `https://reactome.org/AnalysisService`. Search ContentService at
   `/search/query?query=<query>&cluster=true`; POST lists to
   `/AnalysisService/identifiers/` and read by token. Record serialized query,
   release, access time, token, species, result cap, and page state.
6. Validate status, required fields, IDs, completeness, and mapping; retain
   exact ordered inputs, nulls, and excluded/unmapped IDs with reasons; do not
   fill nulls from a different entity, and bound retries and pages.
   On malformed, failed, or truncated responses, mark unavailable and preserve
   the response receipt rather than interpreting absence as a negative.
7. For enrichment, record input and background sizes, mapped counts, returned
   test and multiple-testing fields, and pathway IDs. Sensitivity checks vary
   `/projection` to human, the interactors option, species, and identifier
   mapping; assess alternative universes offline with downloaded gene sets.
8. Report claims with uncertainty and applicability limits, retain query and
   response artifacts through `$science-provenance`, and route material pathway
   or mechanism interpretation to `$science-review`; record each handoff.

## Outputs

Return one `reactome-evidence-reconciliation-v1` record with required fields:
claim identifier (`claim_id`); claim class (`claim_class`); status
(`status`: supported, contradicted, inconclusive, or unavailable); organism
(`organism`); input namespace (`input_namespace`); submitted and mapped inputs
(`submitted_ids`, `mapped_ids`); excluded inputs and reasons
(`excluded_inputs`); Reactome release (`release`); query and analysis token
(`query`, `analysis_token`); API background and tested universe (`background`,
`tested_universe`); pathway/reaction stable IDs and evidence class
(`records`, `evidence_class`); measurements and multiple-testing fields
(`measurements`); controls and sensitivity results (`controls`, `sensitivity`);
uncertainty and applicability (`uncertainty`, `applicability`); source URLs,
access time, artifact hashes, and smallest falsifiable next lookup (`source_urls`,
`accessed_at`, `artifact_hashes`, `next_lookup`). Preserve query/response
artifacts with `$science-provenance` and obtain `$science-review` for material
conclusions.

## Boundaries

- Report species and analysis token. Enrichment p-values depend on background,
  tested universe, mapping, and multiple testing; pathway membership does not
  establish activity or causation.
- Keep submitted IDs distinct from mapped IDs; report not-found identifiers
  and cite only stable IDs actually returned.
- Stop when species, namespace, or background ambiguity changes interpretation.
  A failed token/query is unavailable, not a null biological result. Respect
  terms and redistribution constraints. `$science-review` is mandatory for
  material pathway or mechanism conclusions.
- Reactome-curated reactions and orthology-inferred events have different
  evidence status; neither by itself demonstrates the event in the queried
  organism or condition.
