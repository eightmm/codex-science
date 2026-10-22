---
name: ucsc-conservation
description: "Fetch evolutionary conservation scores (phyloP, phastCons) and transcription-factor binding sites (ENCODE, JASPAR, ReMap) from the UCSC Genome Browser. Use to assess whether variants/regions are conserved or TF-bound. Public API, no credential needed."
license: Apache-2.0
---

# Ucsc Conservation (Codex-native)

Codex-native adaptation of Google DeepMind's `ucsc-conservation-and-tfbs` skill
([science-skills](https://github.com/google-deepmind/science-skills),
Apache-2.0). Uses the public API directly through Codex's own tools.

## Decision contract

Record species/genome, assembly (`hg38` or `hg19` where human), coordinate
convention, chromosome and interval or variant/reference/alternate alleles,
strand where relevant, requested score/track types, evidence cutoff and sought
interpretation. Normalize coordinates before retrieval. Pin exact track IDs and
inspect the source alignment, species count and neutral model when available.
Conservation is an evolutionary score, not evidence of molecular function.

## Reference usage

Read [conservation-and-track-interpretation.md](references/conservation-and-track-interpretation.md)
before choosing phyloP/phastCons tracks, interpreting scores, or claiming
conservation, acceleration or TFBS overlap. Read [coordinates-and-evaluation.md](references/coordinates-and-evaluation.md)
before fetching tracks, choosing controls or comparing intervals/assemblies.

## Workflow

1. **Gates (ask before proceeding).** On first use in a workspace, tell the user
   to review UCSC terms of use and record the notice in provenance. Use the
   read-only public API politely and respect rate limits. Ask before installs or
   large downloads; write large responses to a file and parse them. Any helper
   code runs through `uv run`, never bare `python3`.
2. Normalize species, assembly, interval and coordinate convention; verify the
   chromosome and boundaries against the selected assembly and record the
   normalized query.
3. List available tracks for that assembly and choose exact phyloP, phastCons
   and/or TFBS tracks before interpretation. Record list query, returned IDs,
   release metadata and selected tracks; a listed track is not an observation.
4. Fetch the declared region using UCSC's public Genome Browser API. Retain exact
   endpoint, parameters, access time, raw response or hash, and all returned,
   absent and excluded records with reasons.
5. Verify returned assembly, track, interval, response completeness and score
   type; distinguish no overlap, missing score, null, unavailable track,
   truncation and service failure. Record check results; retrieval failure is
   never a biological negative.
6. Interpret phyloP and phastCons separately and report their alignment/species
   coverage and neutral-model context when exposed. For TFBS, report the exact
   source assay/track; overlap alone is not tissue-specific binding evidence.
7. Compare with predeclared conserved coding-exon and neutral-region controls,
   plus matched random/common variants where suitable; record control matching
   and limitations.
8. Vary track/alignment, assembly, interval width and score summary where data
   permit. Record changes and call the conclusion fragile when classification
   or direction materially changes.
9. **Verify** query/build/track identity, coordinate mapping, response counts,
   score interpretation and artifact hashes; write the versioned result and
   preserve query, endpoint and artifacts with `$science-provenance`. Use
   `$science-review` before material functional claims.

## Outputs

Write one `ucsc-conservation-evidence-v1` record with these required fields:

- Claim identifier (`claim_id`) and status (`claim_status`: `supported`,
  `contradicted`, `inconclusive` or `unavailable`).
- Species (`species`), assembly (`assembly`), coordinate convention
  (`coordinate_convention`), normalized interval (`normalized_interval`) and
  reference/alternate alleles (`reference_and_alternate_alleles`).
- Track listing (`track_listing`), selected IDs (`selected_track_ids`), release
  (`track_release`), alignment set (`alignment_set`), species count
  (`species_count`), neutral model (`neutral_model`) and score type (`score_type`).
- Returned scores and overlaps (`scores_and_overlaps`), endpoint and parameters
  (`query_endpoint_and_parameters`), query time (`query_time`) and returned /
  excluded counts (`returned_and_excluded_counts`).
- Controls (`controls`), sensitivity results (`sensitivity`), uncertainty and
  limits (`uncertainty_and_limits`), artifact paths/hashes (`artifacts`),
  provenance (`provenance`), review disposition (`review`) and smallest
  falsifiable next test (`next_test`).

Use null/unknown explicitly when source metadata is not exposed. Keep raw data or
a hash-bound artifact.

## Boundaries

- State assembly (`hg38`/`hg19); coordinates and tracks are assembly-specific.
  Cite exact track and source. Do not mix builds or silently lift coordinates.
- phyloP measures substitution-rate departure under a neutral model; phastCons
  estimates conserved-element probability. Neither is a functional assay.
- Conservation is a signal, not proof of function. TFBS overlap is not evidence
  of binding in the relevant tissue or condition.
- Do not infer absence of function from absent conservation or track data. Stop
  when assembly or interval cannot be normalized.
- The repository has no UCSC MCP search tool: use Codex's public API access
  directly and do not substitute unrelated connector results.
- Detect response truncation/page limits, bound retries to transient failures,
  and do not interpret retrieval failure as a negative.
