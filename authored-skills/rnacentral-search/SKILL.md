---
name: rnacentral-search
description: "Resolve non-coding RNA identifiers, sequences, types, and cross-references through RNAcentral. Use for RNA annotation, accession normalization, ncRNA, or sequence-context research; not as experimental function validation."
license: MIT
---

# RNAcentral Search

## Decision contract

Specify RNA name, type, description or accession, target organism, sequence/annotation question, evidence cutoff, and downstream use. Preserve the source accession and stable RNAcentral URS identifier separately from sequence version and external cross-references. Similar labels do not guarantee identical sequences or records.

Separate claims of sequence identity, expert-database provenance, annotation, and experimentally demonstrated function. A URS or member-database annotation is a database record; it does not demonstrate function. Sequence-based evidence and annotation-based evidence are distinct claim classes. Use statuses `supported`, `contradicted`, `inconclusive`, or `unavailable`.

## Reference usage

Read [RNAcentral identity and evidence](references/rnacentral-evidence-semantics.md) before matching sequences, reconciling expert-database annotations, or making function claims. Read [RNAcentral retrieval and sensitivity](references/rnacentral-retrieval-sensitivity.md) before API retrieval, release pinning, controls, or varying member-database selection.

## Workflow

1. Define whether the question concerns sequence identity, accession mapping, annotation, or experimentally tested function; specify organism, cutoff and downstream use. Record the claim class and criteria.
2. Search with `science_search_rnacentral` using RNA name, type, description or accession; retain exact query and returned count. Record route and access time.
3. Resolve URS identifier separately from member-database accession, species-specific taxon suffix, sequence version and external cross-references; stop if records cannot be distinguished. Record mappings and ambiguity.
4. Verify active status, sequence, molecule type, organism, member-database cross-references and release; preserve strand, alphabet, version, length and source accession. Record values and nulls.
5. The bundled connector accepts `query` and optional `limit` for description search; use the [RNAcentral API](https://rnacentral.org/api) for accession, sequence, status and cross-reference details absent from search. Record endpoint, serialized query, access time, release/update, page coverage, count and artifact hash.
6. Validate URS/accession, organism, sequence alphabet and length; check response pagination and truncation. Record included and excluded records with reasons.
7. Use a known URS/accession as a positive control and a valid negative query; confirm expected identity and explicit no-match handling. Vary release and expert-database selection; record whether sequence identity, annotation or status changes.
8. Distinguish missing sequence, no match, deprecated/inactive record, filtered record, and API failure. Retry transient errors a bounded number of times; use only a direct endpoint that resolves the same RNA record and retain unavailable results otherwise.
9. Compare sequence-based evidence (identity/alignment and its limits) separately from annotation-based evidence (member database and provenance). Mark conclusions fragile when plausible database selection or release changes claim status or mapping.
10. Assign claim status `supported`, `contradicted`, `inconclusive` or `unavailable`; state uncertainty and applicability, save records and hashes with `$science-provenance`, and use `$science-review` for functional claims. Record the smallest falsifiable next check.

## Outputs

Return `rnacentral-identity-evidence-v1` with required fields: question and claim class; normalized query and organism; claim ID and status (`supported`, `contradicted`, `inconclusive`, `unavailable`); URS and member-database accession; active status; molecule type; sequence version, length, strand and alphabet when available; sequence-based evidence; annotation-based evidence and expert-database provenance; cross-references and dependency links; release/access time; query, endpoint and page coverage; returned/excluded records with reasons; controls and sensitivity settings/results; missingness; uncertainty and applicability limits; smallest falsifiable next check; artifact hashes and review handoff. Store sequence and cross-reference provenance with `$science-provenance`; run `$science-review` for functional claims.

## Boundaries

Do not merge sequences or annotations solely by description. Predicted function is not experimental validation. Similar sequence, shared name, and cross-reference do not prove equivalent biological role; preserve species and sequence version. Treat member-database links as provenance-bearing annotations and report disagreement rather than choosing silently. Stop when identity, sequence integrity, or organism cannot be resolved; keep missing sequence distinct from a negative finding.

Source basis: [RNAcentral API](https://rnacentral.org/api).
