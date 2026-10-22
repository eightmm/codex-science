---
name: jaspar-search
description: "Retrieve transcription-factor binding profiles (PFMs/PWMs) from JASPAR, resolve gene symbols to JASPAR matrix IDs, and get TF metadata in multiple formats (MEME, TRANSFAC, PFM, JASPAR). Public API, no credential needed. Use for motif resources, not binding claims."
license: Apache-2.0
---

# Jaspar Search (Codex-native)

Codex-native adaptation of Google DeepMind's `jaspar-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the
  source's terms of use and record the notice in provenance.
- **Network / install**: read-only public access; be polite about rate limits.
  Write large responses to a file and parse them; if you write helper code, run
  it via `uv run`, never bare `python3`. Ask before installs or large downloads.

## Endpoints

- JASPAR API `https://jaspar.elixir.no/api/v1/`

## Decision contract

Specify the transcription factor, organism, desired collection and matrix format, and use case (motif retrieval or a downstream prediction). Resolve symbols to an explicit TF identity and returned matrix ID; retain aliases and ambiguity. A motif matrix is a binding-profile representation, not evidence that binding occurs in a particular sample.

## Reference usage

Read [references/motif-evidence.md](references/motif-evidence.md) before selecting or comparing JASPAR profiles, scanning sequences, interpreting PWM scores or p-values, or reporting motif matches as evidence. It defines matrix-version and collection pinning, scanning controls, sensitivity, and prediction limits.

## Workflow

1. **Gates (ask before proceeding).** Before first workspace use, stop and ask the user to review source terms; record the notice in provenance. Keep public network access read-only and rate-limited; use `uv run` for helper code, never bare `python3`; ask before installs or large downloads. Record the gate outcome.
2. Normalize TF symbol, organism, collection, requested format, downstream use, and cutoff; resolve aliases without choosing among materially ambiguous identities. Record normalized identity and unresolved alternatives.
3. Search `/matrix/?search=<TF>` for candidate matrix IDs and metadata; record exact query, filters, pagination, and why a profile matches the TF and organism.
4. Use bundled `science_search_jaspar` only as an additional bounded matrix search (`query`, optional `limit`); use its returned matrix ID to identify the record and retrieve the selected format directly when needed. Record connector results separately.
5. Fetch `/matrix/<MA_ID>/` in the requested format and verify ID, TF, collection, organism, matrix values, and response completeness. Record JASPAR release, collection, matrix version, format, access time, and response hash; preserve missing metadata and excluded IDs with reasons.
6. If scanning is requested, define sequence assembly/context, score threshold, background nucleotide model, and p-value or other significance rule before scanning; compare with a well-characterized promoter/enhancer positive control and shuffled sequences or matched random genomic background. Record scan parameters, control outcomes, and all tested sequences.
7. Keep motif match, ChIP-seq peak, and demonstrated binding/function as separate claims. Link motifs in the same TF family or complex as dependent candidates; do not count similar profiles as independent evidence. Record shared profile provenance and any overlapping experimental evidence.
8. Vary score threshold, background model, window size, and relevant cell context; record whether hit count, ranking, or conclusion changes. Treat a conclusion that depends on a narrow setting as fragile and mark it inconclusive.
9. Verify claim status, uncertainty, release pinning, and applicability against `references/motif-evidence.md`; preserve no-match, failed, null, and truncated outcomes, then identify the smallest falsifiable next query or assay. Record the verification outcome.

## Outputs

Return one `jaspar-motif-evidence-v1` record with normalized TF identity and aliases (`tf_identity`, `aliases`, `organism`), exact query and endpoint (`query_ledger`), pinned release and collection (`release`, `collection`), matrix ID/version/format (`matrix_id`, `matrix_version`, `format`), matrix data or artifact reference (`matrix`), returned and excluded records with reasons (`included`, `excluded`), missingness (`missingness`), scan parameters and results when used (`scan`, `controls`), claim IDs and status (`claims`), dependencies (`dependencies`), uncertainty and applicability (`uncertainty`, `applicability`), limitations (`limitations`), and smallest falsifiable next action (`next_action`). Use only `supported`, `contradicted`, `inconclusive`, or `unavailable` for claim status. Save matrices, query ledger, and hashes via `$science-provenance`; use `$science-review` before claims based on downstream motif analysis.

## Boundaries

- Report the JASPAR release/collection (e.g. CORE) and matrix version.
- Cite only matrix IDs actually returned.
- A PFM/PWM or motif match does not establish occupancy, regulatory effect, or phenotype. Do not interpret scores as calibrated probabilities absent calibration. Stop on unresolved TF identity, missing matrix values, or assembly/species mismatch; retain unresolved results as inconclusive/unavailable. Preserve all terms, network, `uv run`, install and large-download gates above.
