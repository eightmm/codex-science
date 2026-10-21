---
name: ucsc-conservation
description: "Fetch evolutionary conservation scores (phyloP, phastCons) and transcription-factor binding sites (ENCODE, JASPAR, ReMap) from the UCSC Genome Browser. Use to assess whether variants/regions are conserved or TF-bound. Public API, no credential needed."
license: Apache-2.0
---

# Ucsc Conservation (Codex-native)

Codex-native adaptation of Google DeepMind's `ucsc-conservation-and-tfbs` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Decision contract
Record species/genome, assembly, chromosome and interval (or variant plus reference/alternate alleles), strand where relevant, requested score/track types, evidence cutoff, and the biological interpretation sought. Normalize coordinate conventions before retrieval and do not mix assemblies. List tracks to inspect before interpreting the interval.

## Workflow
**Gates (ask before proceeding):** on first use in a workspace, tell the user to review the source's terms of use and record the notice in provenance. Read-only public access; be polite about rate limits. Write large responses to a file and parse them; if you write helper code, run it via `uv run`, never bare `python3`. Ask before installs or large downloads.

Use UCSC Genome Browser API `https://api.genome.ucsc.edu` (`/getData/track`, `/list/tracks`). List available tracks for the assembly (`/list/tracks?genome=hg38`), then fetch track data for a region (`/getData/track`). Report conservation scores and any overlapping TFBS for the region. Record exact genome, interval, track identifiers, query parameters, access time, response/release metadata when reported, and the raw response or hash-bound artifact. Validate chromosome and interval against the selected genome and confirm the returned track and assembly. A listed track is not a returned observation; retain absent tracks as unavailable.

The repository currently catalogs UCSC but has no UCSC MCP search tool. Use Codex's public API access directly; do not substitute unrelated connector results. Detect truncation or page limits and distinguish no overlap, missing score, null, unavailable track, and service failure. Bound retries to transient failures and do not interpret retrieval failure as a negative. Record query, endpoint, track, returned/excluded records and reasons with `$science-provenance`; check material functional claims with `$science-review` before presenting.

## Outputs
Return normalized assembly and interval, track listing and selected track IDs, scores/overlaps actually returned, query timestamp and response artifact/hash, and exact inclusion/exclusion counts. State uncertainty, track/species coverage, coordinate limitations, claim status (supported, contradicted, inconclusive, unavailable), and the smallest orthogonal follow-up that could test the interpretation.

## Boundaries
State the assembly (hg38/hg19); coordinates and tracks are assembly-specific. Cite the track and source; conservation is a signal, not proof of function. TFBS overlap is not evidence of binding in the relevant tissue or condition. Do not infer absence of function from absent conservation or track data; stop when the assembly or interval cannot be normalized.
