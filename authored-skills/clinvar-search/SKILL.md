---
name: clinvar-search
description: "Look up clinical significance and pathogenicity classifications (Pathogenic, Benign, VUS) and supporting evidence for human genomic variants in NCBI ClinVar. Use for variant clinical interpretation or benchmark controls. Public NCBI API, no credential needed."
license: Apache-2.0
---

# Clinvar Search (Codex-native)

Codex-native adaptation of Google DeepMind's `clinvar-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the
  source's terms of use and record the notice in provenance.
- **Network / install**: read-only public access; be polite about rate limits.
  Write large responses to a file and parse them; if you write helper code, run
  it via `uv run`, never bare `python3`. Ask before installs or large downloads.

## Endpoints

- NCBI E-utilities `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/` (esearch/esummary/efetch, db=clinvar)

## Workflow

1. Resolve the variant (rsID, HGVS, or gene) with `esearch` against `db=clinvar`, then `esummary`/`efetch` for the record.
2. Report the clinical significance, review status (star rating), condition, and the supporting evidence.
- **Provenance & review**: record queries, endpoints, and cited identifiers with
  `$science-provenance`; check claims with `$science-review` before presenting.

## Boundaries

- Clinical significance and review status vary in confidence; report the star rating. This is not clinical or diagnostic advice.
- Cite only ClinVar accessions (VCV/RCV) actually returned.
