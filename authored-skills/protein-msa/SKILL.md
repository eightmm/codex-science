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

## Decision contract

Validate a FASTA containing at least two protein sequences; preserve each supplied
identifier and sequence, reject malformed/empty entries, and record sequence
hashes. Define the comparison question and residue/region of interest. This service
aligns the submitted set and does not discover homologs. Capture service-reported
job state/release metadata when present; do not infer an unreported release.

## Endpoints

- EBI Clustal Omega REST `https://www.ebi.ac.uk/Tools/services/rest/clustalo/`

## Workflow

1. Submit the FASTA of >=2 protein sequences (`/run`), poll `/status/<jobId>`, then fetch results (`/result/<jobId>/...`).
2. Report conserved columns/regions and key-residue conservation from the alignment.
- **Provenance & review**: record queries, endpoints, and cited identifiers with
  `$science-provenance`; check claims with `$science-review` before presenting.

Serialize the exact FASTA and request fields supported by the endpoint. Use the
returned job ID for bounded status polling; retry only transient request failures
with a fixed retry cap, and stop on terminal failure. Validate the result format,
returned sequence IDs/count, and alignment dimensions; detect incomplete or
truncated responses before interpreting them. Record submitted, returned, and
excluded IDs with reasons. Distinguish an absent result from an empty alignment
and from an unavailable request. No repository connector is configured for this
source, so use the documented public endpoint directly; do not substitute another
search route after failure.

## Outputs

Return submitted IDs/hashes, endpoint, job ID/status, request and result artifact
paths/hashes, aligned sequences, alignment length and gaps, conserved columns or
regions, claim IDs/statuses, exclusions/failures, limitations, and smallest
falsifiable next analysis. Use supported, contradicted, inconclusive, or unavailable
for each claim status.
Record artifacts with `$science-provenance`; `$science-review` is mandatory before
material conservation claims.

## Boundaries

- This aligns given sequences; it does not find homologs (use `$cx-protein-similarity-search`).
- Respect the size limits and EBI rate limits; cite the job/inputs used.
