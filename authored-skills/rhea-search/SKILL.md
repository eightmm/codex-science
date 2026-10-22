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

Separate claims about a curated reaction record, a database cross-reference, organism-specific enzyme evidence, and measured reaction flux. A record or propagated annotation is not experimental demonstration. Use claim statuses `supported`, `contradicted`, `inconclusive`, or `unavailable`.

## Reference usage

Read [Rhea claim and dependency semantics](references/rhea-claim-semantics.md) before assigning reaction identity, direction, enzyme, or pathway claims. Read [Rhea retrieval and validation](references/rhea-retrieval-validation.md) before direct retrieval, quartet comparison, controls, or sensitivity analysis.

## Workflow

1. Define whether the target claim concerns record identity, direction, enzyme/protein assignment, pathway context, or measured flux; stop if participant identity cannot be specified. Record question, organism/context and cutoff.
2. Normalize participants with ChEBI while retaining original names, identifiers, charge, stereochemistry and state. Record all mappings and unresolved alternatives.
3. Search with optional `science_search_rhea` (`query`, `limit` 1–10, default 5; records include Rhea ID, equation title, status and URL) or use public Rhea REST documented at [Rhea REST access](https://www.rhea-db.org/help/download). Record query and route.
4. For direct search, call `https://www.rhea-db.org/rhea/` with URL-encoded `query`, `format=json` and bounded `limit`; retain exact parameters, endpoint, access time, reported release/update, count and pagination. The MCP search remains available; missing repository detail operations do not preclude the public API. Record retrieval provenance.
5. Verify response status/schema, Rhea ID, equation, ChEBI participants, stoichiometry, direction and curation status; exclude mismatches with reasons. Preserve nulls; retry transient failures a bounded number of times. Failed or truncated response means `unavailable`, not no reaction. Record validation and exclusions.
6. Inspect the four-reaction quartet and corresponding direction-specific cross-references; choose the member matching the question and never infer forward direction from left/right placement alone. Record master and selected directional IDs.
7. Cross-check enzyme/protein claims with UniProt and pathway claims with Reactome when material; trace EC/UniProt links to their originating reaction and treat propagated records as dependent. Record shared provenance.
8. Test one known reaction/participant as a positive control and a valid negative query; vary direction member, taxonomy/context filters and linked database selection. Record outcomes and settings; mark claims fragile if identity, direction, status, or cross-reference changes.
9. Distinguish no match, missing/null fields, filtering and API failure; report uncertainty and applicability. Assign status `supported`, `contradicted`, `inconclusive` or `unavailable` and preserve query, responses and hashes through `$science-provenance`.
10. Use `$science-review` before material enzyme, pathway or mechanism interpretation; record the evidence table, limitations and smallest next cross-check.

## Outputs

Return `rhea-reaction-evidence-v1` with required fields: question and context; normalized participants and assumptions; claim ID, claim class and status (`supported`, `contradicted`, `inconclusive`, `unavailable`); Rhea master and directional IDs; equation, ChEBI participant IDs, stoichiometry and direction; curation status; quartet members; EC/UniProt/Reactome links and dependency notes; release/access time; source URL; included/excluded records and reasons; query/endpoint provenance; control and sensitivity settings/results; uncertainty and applicability limits; smallest next cross-check; artifact hashes and review handoff. Preserve response artifacts and hashes through `$science-provenance`.

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
- Treat EC and UniProt cross-references as propagated annotations, not independent experimental demonstrations; reaction identity and direction must be checked in Rhea.

Source basis: [Rhea REST access](https://www.rhea-db.org/help/download).
