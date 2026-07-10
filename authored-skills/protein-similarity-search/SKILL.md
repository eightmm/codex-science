---
name: protein-similarity-search
description: "Find homologous protein sequences with MMseqs2 (fast, default) or BLAST (comprehensive fallback) from a sequence or FASTA. Use to find sequence homologs or infer function by sequence similarity — not by structural similarity. Public APIs, no credential needed."
license: Apache-2.0
---

# Protein Similarity Search (Codex-native)

Codex-native adaptation of Google DeepMind's `protein-sequence-similarity-search` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the
  source's terms of use and record the notice in provenance.
- **Network / install**: read-only public access; be polite about rate limits.
  Write large responses to a file and parse them; if you write helper code, run
  it via `uv run`, never bare `python3`. Ask before installs or large downloads.

## Endpoints

- ColabFold MMseqs2 `https://api.colabfold.com`
- EBI NCBI BLAST REST `https://www.ebi.ac.uk/Tools/services/rest/ncbiblast`

## Workflow

1. Submit the query sequence to MMseqs2 first; fall back to EBI BLAST if needed.
2. Report top homologs with identity, coverage, and E-value, and the inferred function.
- **Provenance & review**: record queries, endpoints, and cited identifiers with
  `$science-provenance`; check claims with `$science-review` before presenting.

## Boundaries

- Sequence similarity suggests, not proves, homology/function; for structural homologs use `$cx-foldseek-structural-search`.
- Cite only hits actually returned.
