---
name: rnacentral-search
description: "Resolve non-coding RNA identifiers, sequences, types, and cross-references through RNAcentral. Use for RNA annotation, accession normalization, ncRNA, or sequence-context research; not as experimental function validation."
license: MIT
---

# RNAcentral Search

## Decision contract

Specify RNA name, type, description or accession, target organism, sequence/annotation question, evidence cutoff, and downstream use. Preserve the source accession and stable RNAcentral URS identifier separately from sequence version and external cross-references. Similar labels do not guarantee identical sequences or records.

## Workflow

1. Call `science_search_rnacentral` with an RNA name, type, description, or accession.
2. Verify active status, sequence, molecule type, organism, database cross-references, and release.
3. Preserve strand, alphabet, sequence version, length, and source accession before downstream analysis.
4. Record query, URS identifier, release/access time, and selected cross-references.
5. The bundled connector accepts `query` and optional `limit` for description search. Use the [RNAcentral API](https://rnacentral.org/api) directly for accession, sequence, status and cross-reference details not returned by search. Record exact endpoint and serialized query, access time, source release/update, page coverage, returned count and artifact hash. Validate URS/accession, organism, sequence alphabet and length; detect truncation and preserve null fields.
6. Record included and excluded records with reasons. Distinguish missing sequence, no match, deprecated/inactive record, filtered record, and API failure. Retry transient errors a bounded number of times; use only a direct endpoint that resolves the same RNA record and retain unavailable results otherwise.

## Outputs

Return normalized query and organism, URS/source accession, status, molecule type, sequence version/length/strand/alphabet when available, cross-references, exact query/release provenance, and records returned/excluded with reasons. Assign claim IDs with status `supported`, `contradicted`, `inconclusive`, or `unavailable`; explain annotation uncertainty, dependency and limits, and the smallest falsifiable next check. Store sequence and cross-reference provenance with `$science-provenance`; run `$science-review` for functional claims.

## Boundaries

Do not merge sequences or annotations solely by description. Predicted function is not experimental validation. Similar sequence, shared name, and cross-reference do not prove equivalent biological role; preserve species and sequence version. Stop when identity, sequence integrity, or organism cannot be resolved; keep missing sequence distinct from a negative finding.

Source basis: [RNAcentral API](https://rnacentral.org/api).
