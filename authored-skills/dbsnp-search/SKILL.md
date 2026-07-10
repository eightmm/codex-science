---
name: dbsnp-search
description: "Look up and map short human variants (SNPs, indels) in NCBI dbSNP: resolve between rsIDs, GRCh38 coordinates, and HGVS, and get variant type, gene, clinical significance, and allele frequencies. Public NCBI API, no credential needed."
license: Apache-2.0
---

# Dbsnp Search (Codex-native)

Codex-native adaptation of Google DeepMind's `dbsnp-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the
  source's terms of use and record the notice in provenance.
- **Network / install**: read-only public access; be polite about rate limits.
  Write large responses to a file and parse them; if you write helper code, run
  it via `uv run`, never bare `python3`. Ask before installs or large downloads.

## Endpoints

- NCBI Variation Services `https://api.ncbi.nlm.nih.gov/variation/v0/`
- NCBI E-utilities `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/` (db=snp)

## Workflow

1. Given an rsID, fetch the refsnp record for type, gene, clinical significance, allele frequencies, and GRCh38 coordinates.
2. Map between rsID / VCF coordinates / HGVS with the Variation Services endpoints.
- **Provenance & review**: record queries, endpoints, and cited identifiers with
  `$science-provenance`; check claims with `$science-review` before presenting.

## Boundaries

- Report the assembly (GRCh38) explicitly; coordinates differ across builds.
- Cite only rsIDs actually returned; never invent frequencies.
