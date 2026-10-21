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
Record whether the requested sequence is protein or nucleotide, the accession or search terms, organism/taxon, desired molecule/region, output format, and downstream use. Preserve accession version and database because sequence records can change. For gene, locus, publication, or patent routes, specify the exact link/search basis and resolve candidate identity before fetching full sequence.

## Workflow
**Gates (ask before proceeding):** on first use in a workspace, tell the user to review the source's terms of use and record the notice in provenance. Read-only public access; be polite about rate limits. Write large responses to a file and parse them; if you write helper code, run it via `uv run`, never bare `python3`. Ask before installs or large downloads.

Use NCBI E-utilities `https://eutils.ncbi.nlm.nih.gov/entrez/eutils` (`esearch`/`efetch`, `db=protein|nuccore`). For an accession, `efetch` with `rettype=fasta`; for a gene+organism, `esearch` then `efetch`. Resolve and record the actual database, accession and version returned. Write large sequence output to a file; do not dump long FASTA to stdout. Validate format, sequence length when reported, header/accession and molecule type; never silently translate, trim, repair, or substitute a nearby record.

Record exact query and endpoint, access date, source release/update metadata when reported, returned and excluded accessions with reasons, response hash and saved artifact path. Detect partial/truncated output and distinguish no result, missing field, null, and retrieval failure. Use bounded retries only for transient failures; respect NCBI usage/rate limits. Record queries, endpoints, and cited identifiers with `$science-provenance`; check material claims with `$science-review` before presenting.

## Outputs
Return normalized query, molecule/database, organism, accession and version, sequence format and length, retrieval timestamp, and artifact path/hash. Include returned/excluded records and reasons, sequence validation status, uncertainty, limitations, and the smallest next retrieval or identity check. Preserve the raw FASTA or other requested output as a provenance artifact.

## Boundaries
Report the accession and database (protein vs nucleotide); respect NCBI rate limits. Cite only accessions actually returned; never fabricate sequences. A database sequence is not proof of expression, function, or patient genotype. Stop if organism, accession, molecule type, or record completeness is uncertain; do not fetch large payloads until a declared file and compute plan exists.
