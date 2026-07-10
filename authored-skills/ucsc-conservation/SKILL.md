---
name: ucsc-conservation
description: Fetch evolutionary conservation scores (phyloP, phastCons) and transcription-factor binding sites (ENCODE, JASPAR, ReMap) from the UCSC Genome Browser. Use to assess whether variants/regions are conserved or TF-bound. Public API, no credential needed.
license: Apache-2.0
---

# Ucsc Conservation (Codex-native)

Codex-native adaptation of Google DeepMind's `ucsc-conservation-and-tfbs` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the
  source's terms of use and record the notice in provenance.
- **Network / install**: read-only public access; be polite about rate limits.
  Write large responses to a file and parse them; if you write helper code, run
  it via `uv run`, never bare `python3`. Ask before installs or large downloads.

## Endpoints

- UCSC Genome Browser API `https://api.genome.ucsc.edu` (`/getData/track`, `/list/tracks`)

## Workflow

1. List available tracks for the assembly (`/list/tracks?genome=hg38`), then fetch track data for a region (`/getData/track`).
2. Report conservation scores and any overlapping TFBS for the region.
- **Provenance & review**: record queries, endpoints, and cited identifiers with
  `$science-provenance`; check claims with `$science-review` before presenting.

## Boundaries

- State the assembly (hg38/hg19); coordinates and tracks are assembly-specific.
- Cite the track and source; conservation is a signal, not proof of function.
