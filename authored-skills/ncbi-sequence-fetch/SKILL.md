---
name: ncbi-sequence-fetch
description: "Retrieve protein and nucleotide sequences from NCBI via E-utilities: by accession, CDS translation, gene+organism search, locus lookup, PubMed-linked sequences, or patent proteins. Use to fetch biological sequences. Public NCBI API, no credential needed."
license: Apache-2.0
---

# Ncbi Sequence Fetch (Codex-native)

Codex-native adaptation of Google DeepMind's `ncbi-sequence-fetch` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the
  source's terms of use and record the notice in provenance.
- **Network / install**: read-only public access; be polite about rate limits.
  Write large responses to a file and parse them; if you write helper code, run
  it via `uv run`, never bare `python3`. Ask before installs or large downloads.

## Endpoints

- NCBI E-utilities `https://eutils.ncbi.nlm.nih.gov/entrez/eutils` (esearch/efetch, db=protein|nuccore)

## Workflow

1. For an accession, `efetch` with `rettype=fasta`; for a gene+organism, `esearch` then `efetch`.
2. Write large sequence output to a file; do not dump long FASTA to stdout.
- **Provenance & review**: record queries, endpoints, and cited identifiers with
  `$science-provenance`; check claims with `$science-review` before presenting.

## Boundaries

- Report the accession and database (protein vs nucleotide); respect NCBI rate limits.
- Cite only accessions actually returned; never fabricate sequences.
