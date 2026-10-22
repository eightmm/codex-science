---
name: ncbi-sequence-fetch
description: "Retrieve protein and nucleotide sequences from NCBI via E-utilities: by accession, CDS translation, gene+organism search, locus lookup, PubMed-linked sequences, or patent proteins. Use to fetch biological sequences. Public NCBI API, no credential needed."
license: Apache-2.0
---

# Ncbi Sequence Fetch (Codex-native)

Codex-native adaptation of Google DeepMind's `ncbi-sequence-fetch` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Decision contract

Record whether the requested sequence is protein or nucleotide, the accession or search terms, organism/taxon, desired molecule/region, output format, and downstream use. Preserve accession version and database because sequence records can change. For gene, locus, publication, or patent routes, specify the exact link/search basis and resolve candidate identity before fetching full sequence. For CDS translation record the genetic code table, frame, and any partial-CDS flags rather than implying a complete canonical protein.

## Reference usage

Read [references/ncbi-sequence-records.md](references/ncbi-sequence-records.md) before choosing a search route, fetching/translation, or interpreting a returned sequence. It covers accession/version identity, record classes, query ambiguity, format checks, NCBI request etiquette, and failure states.

## Workflow

1. **Gates (ask before proceeding).** On first use in a workspace, tell the user to review the source's terms of use and record the notice in provenance. Use read-only public access, be polite about rate limits, ask before installs or large downloads, and write large responses to a file and parse them; if helper code is needed, run it via `uv run`, never bare `python3`.
2. Define molecule type, requested region, organism/taxon, downstream use, output format, and accession or query basis; if identity is not clear enough for a unique record, resolve candidates before fetching full sequence and record the choice.
3. Select database and source class: use protein or nucleotide (`nuccore`) records as appropriate and distinguish RefSeq, GenBank, and patent records; record why that record class fits and preserve the returned database and accession.version.
4. Search/fetch through `https://eutils.ncbi.nlm.nih.gov/entrez/eutils` using `esearch`/`efetch` (`db=protein|nuccore`): accession requests use `efetch` with `rettype=fasta`; gene+organism requests use `esearch` then `efetch`. Follow NCBI's documented request-rate etiquette. Set the E-utilities `tool` value to name this workflow (`ncbi-sequence-fetch`). Send an `email` contact only when the user supplied or approved that contact for this purpose; otherwise omit it. Never fill `email` from the environment or a local profile. Do not add account or access parameters.
5. For gene+organism, locus, publication, or patent searches, inspect candidate identifiers and organism/context, check ambiguity from paralogs or overlapping names, and record returned and excluded accessions with the reason before selecting a sequence.
6. Fetch the smallest requested record set and save large responses to a file rather than stdout; record exact query and endpoint, access date, reported release/update metadata, response hash, saved path, and whether the response is complete or truncated.
7. If translating CDS, verify the annotated CDS boundaries, genetic code table, reading frame, partial-start/stop flags, and translation exceptions; retain nucleotide source and derived protein as linked artifacts, and never silently translate, trim, repair, or substitute a nearby record.
8. Validate output format, sequence length when reported, header/accession, molecule type, alphabet, and FASTA/GenBank parsing; distinguish no result, missing field, null, stale record, partial record, and retrieval failure, and use bounded retries only for transient failures.
9. Report the result and limitations, preserve raw requested output and provenance with `$science-provenance`, and use `$science-review` before material claims about sequence identity or downstream function.

## Outputs

Return one `ncbi-sequence-record-v1` record with required fields: normalized query (`normalized_query`), molecule type (`molecule_type`), database (`database`), record class (`record_class`), organism and taxon (`organism_taxon`), accession version (`accession_version`), region (`region`), genetic code (`genetic_code`), frame and partial flags (`frame_and_partial_flags`), sequence format (`sequence_format`), sequence length (`sequence_length`), retrieval timestamp (`retrieval_timestamp`), query endpoint (`query_endpoint`), source update metadata (`source_update_metadata`), returned records (`returned_records`), excluded records (`excluded_records`), validation status (`validation_status`), uncertainty (`uncertainty`), applicability domain (`applicability_domain`), limitations (`limitations`), next action (`next_action`), raw artifact path and hash (`raw_artifact_path_hash`), and review receipt (`review_receipt`). Preserve the raw FASTA or other requested format as a provenance artifact.

## Boundaries

- Report the accession and database (protein vs nucleotide); respect NCBI rate limits and documented etiquette.
- Cite only accessions actually returned; never fabricate sequences.
- A database sequence is not proof of expression, function, or patient genotype.
- Stop if organism, accession, molecule type, or record completeness is uncertain; do not fetch large payloads until a declared file and compute plan exists.
- Record database record version/update context because records may change; do not treat retrieved sequence as timeless.
