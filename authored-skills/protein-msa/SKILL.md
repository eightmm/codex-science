---
name: protein-msa
description: "Align multiple protein sequences with EBI Clustal Omega to assess similarity and residue/domain conservation (up to 4000 sequences, 4 MB). Not for homolog search, non-protein sequences, structural alignment, or a single sequence. Public EBI API, no credential needed."
license: Apache-2.0
---

# Protein Msa (Codex-native)

Codex-native adaptation of Google DeepMind's `protein-sequence-msa` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the
  source's terms of use and record the notice in provenance.
- **Network / install**: read-only public access; be polite about rate limits.
  Write large responses to a file and parse them; if you write helper code, run
  it via `uv run`, never bare `python3`. Ask before installs or large downloads.

## Endpoints

- EBI Clustal Omega REST `https://www.ebi.ac.uk/Tools/services/rest/clustalo/`

## Workflow

1. Submit the FASTA of >=2 protein sequences (`/run`), poll `/status/<jobId>`, then fetch results (`/result/<jobId>/...`).
2. Report conserved columns/regions and key-residue conservation from the alignment.
- **Provenance & review**: record queries, endpoints, and cited identifiers with
  `$science-provenance`; check claims with `$science-review` before presenting.

## Boundaries

- This aligns given sequences; it does not find homologs (use `$cx-protein-similarity-search`).
- Respect the size limits and EBI rate limits; cite the job/inputs used.
