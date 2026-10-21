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

State whether the task is pathway/reaction lookup, identifier mapping, or
over-representation analysis; specify organism, input identifier namespace,
gene/protein list, evidence cutoff, and interpretation goal. Keep Reactome
stable identifiers (such as returned `stId` values) distinct from names and
external identifiers. For enrichment, record the submitted list and background
assumptions; p-values depend on the background and tested universe.

## Workflow

1. **Gates (ask before proceeding).** On first use in a workspace, tell the
   user to review the source's terms of use and record the notice in provenance.
   Public read-only access: be polite about rate limits. Write large responses
   to a file and parse them; use `uv run` for helper code, never bare `python3`.
   Ask before installs or large downloads.
2. Normalize identifiers and species. Optionally discover with
   `science_search_reactome` (`query`, `limit` 1–10, default 5); it returns
   stable ID, title, type, and URL. Direct APIs are Reactome ContentService
   `https://reactome.org/ContentService` and AnalysisService
   `https://reactome.org/AnalysisService`. Search uses ContentService
   `/search/query?query=<query>&cluster=true`.
3. For enrichment, POST the identifier list to
   `/AnalysisService/identifiers/` and read results by token. Save the exact
   ordered inputs, endpoint, parameters, token, species, access time, and
   response-reported release/update. For content, query pathways/reactions/
   participants via ContentService endpoints and capture query serialization,
   page state and result cap. Do not conflate submitted IDs with mapped IDs.
4. Validate status, expected response fields, stable identifier formats, and
   completion/truncation. Keep not-found and unmapped identifiers with reasons.
   Bound retries and pagination; report API failures as unavailable. Preserve
   null values rather than filling them from a different entity.
5. Report species and analysis token; state list size, mapped/unmapped counts,
   tested background and multiple-testing fields returned. Distinguish pathway
   membership from causal or mechanistic evidence. Record query and response
   receipts with `$science-provenance`; use `$science-review` for material
   pathway or mechanism claims.

## Outputs

Return normalized inputs and namespace; query/token/release/access-time record;
an evidence table of returned pathway/reaction IDs, type, species, mapping
status, relevant measurements and URLs; excluded/unmapped inputs and reasons;
claim IDs marked supported/contradicted/inconclusive/unavailable; uncertainty,
background limitations, and smallest falsifiable next lookup. Save response
artifacts and hashes through `$science-provenance`.

## Boundaries

- Report species and analysis token; enrichment p-values depend on the
  background. Do not call enrichment causal or proof of pathway activity.
- List not-found/unmapped identifiers honestly; cite only stable IDs returned.
- Stop if species, namespace, or background choice can change interpretation.
  A failed token/query is unavailable, not a null biological result. Respect
  terms and redistribution constraints. `$science-review` is mandatory for
  material pathway or mechanism conclusions.
