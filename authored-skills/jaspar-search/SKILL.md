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

## Workflow

1. Resolve a TF symbol to a matrix id via `/matrix/?search=<TF>`, then fetch `/matrix/<MA_ID>/` in the desired format.
2. Report the matrix id, TF name, collection, and version.
3. Use the direct JASPAR API path above for metadata and format-specific matrix retrieval. The bundled `science_search_jaspar` connector is an additional bounded matrix search (`query`, optional `limit`); use its returned matrix ID to identify the record, then retrieve the chosen format directly when needed.
4. Serialize query, collection, format, and pagination parameters. Capture access time and release/collection and matrix version reported by the response. Validate matrix ID, TF, collection, and matrix values; preserve missing metadata, no-match results, exclusions and truncated output separately. Record all returned and excluded IDs with reasons.
5. Use bounded retries for transient failures, respect service throttling, and do not silently substitute a motif from another TF or collection. A failed endpoint remains unavailable unless a documented equivalent request returns the same matrix.

## Outputs

Return normalized TF identity and aliases, exact query/endpoint, collection/release, matrix ID/version/format, returned matrix data or artifact reference, records excluded and why, and missingness. Assign claim IDs with `supported`, `contradicted`, `inconclusive`, or `unavailable` status; state uncertainty and applicability, including species and assay limitations. Save matrices, query ledger and hashes via `$science-provenance`; use `$science-review` before claims based on downstream motif analysis.

## Boundaries

- Report the JASPAR release/collection (e.g. CORE) and matrix version.
- Cite only matrix IDs actually returned.
- A PFM/PWM or motif match does not establish occupancy, regulatory effect, or phenotype. Do not interpret scores as calibrated probabilities absent calibration. Stop on unresolved TF identity, missing matrix values, or assembly/species mismatch; retain unresolved results as inconclusive/unavailable. Preserve all terms, network, `uv run`, install and large-download gates above.
