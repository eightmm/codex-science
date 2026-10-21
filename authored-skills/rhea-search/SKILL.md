---
name: rhea-search
description: "Search curated biochemical reactions and participants through Rhea. Use for enzyme, pathway, metabolite, reaction-direction, or mechanism context."
license: MIT
---

# Rhea Search

## Decision contract

Define the reaction, enzyme, or participant question, organism/context if
relevant, evidence cutoff, and intended use. Normalize participant names and
identifiers with ChEBI where needed, retaining ChEBI IDs and stereochemical or
charge state. Treat Rhea reaction IDs and directional reaction records as
source records, not observations of flux in a particular organism.

## Workflow

1. Normalize participant identifiers with ChEBI; preserve the original query
   and each normalized identifier. Search using the optional
   `science_search_rhea` MCP tool (`query`, `limit` 1–10, default 5; records
   include Rhea ID, equation title, status, and URL), or use the public Rhea
   REST access documented at [Rhea REST access](https://www.rhea-db.org/help/download).
2. For direct search, query `https://www.rhea-db.org/rhea/` with URL-encoded
   `query`, `format=json`, and bounded `limit`. Record exact parameters,
   endpoint, access time, response-reported release/update, response count, and
   any pagination state. Keep the MCP search as an additional route; absence of
   repository operations for details does not preclude public API access.
3. Validate response status, JSON structure, returned Rhea ID, equation,
   participant identifiers, direction, stoichiometry, and status where provided.
   Record returned reactions and excluded candidates with reasons. Preserve
   null fields; retry transient failures only a bounded number of times. A
   failed or truncated response is unavailable, not evidence of no reaction.
4. Cross-check enzyme/protein claims with UniProt and pathway claims with
   Reactome when those claims matter. Keep source dependencies explicit; these
   records may share upstream curation and are not automatically independent.
5. Save the query, endpoints, response/page state, selected reaction IDs, and
   artifact hashes with `$science-provenance`. Use `$science-review` before
   presenting material enzyme, pathway, or mechanism conclusions.

## Outputs

Return normalized participants and assumptions; an evidence table with Rhea ID,
equation, direction, participant IDs, stoichiometry, status, release/access
time, source URL, and inclusion/exclusion reason; claim IDs marked
supported/contradicted/inconclusive/unavailable; query provenance; uncertainty,
limitations, and the smallest next cross-check. Preserve response artifacts
and hashes through `$science-provenance`.

## Boundaries

- Do not infer kinetics, cellular flux, thermodynamic favorability, or tissue
  activity from a curated reaction equation.
- Do not merge chemically distinct protonation, stereochemical, charge, or
  compartment states without an explicit mapping rule.
- A reaction record does not prove that an enzyme catalyzes it in the queried
  organism. Stop when participant identity or reaction direction is ambiguous.
  Report missing/null fields and unavailable queries separately. Respect source
  terms and redistribution limits; `$science-review` is mandatory for material
  mechanism claims.

Source basis: [Rhea REST access](https://www.rhea-db.org/help/download).
