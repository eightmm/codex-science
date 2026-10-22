---
name: encode-ccres-search
description: "Query the ENCODE Registry of candidate cis-Regulatory Elements (cCREs) via the SCREEN GraphQL API, and ENCODE experiments/files via the ENCODE Portal REST API, across human cell types. Public APIs, no credential needed. Use for cell-type-specific regulatory annotations, not causal claims."
license: Apache-2.0
---

# Encode Ccres Search (Codex-native)

Codex-native adaptation of Google DeepMind's `encode-ccres-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the
  source's terms of use and record the notice in provenance.
- **Network / install**: read-only public access; be polite about rate limits.
  Write large responses to a file and parse them; if you write helper code, run
  it via `uv run`, never bare `python3`. Ask before installs or large downloads.

## Endpoints

- SCREEN GraphQL `https://factorbook.api.wenglab.org/graphql`
- ENCODE Portal REST `https://www.encodeproject.org/` (append `?format=json`)

## Decision contract

Define the gene or genomic interval, genome assembly, cell type/biosample, evidence question (candidate regulatory annotation or experiment/file), and cutoff. Normalize coordinates to a stated assembly and record conversion provenance if any. Treat cCRE, experiment, and file records as distinct evidence objects.

## Reference usage

Read [references/ccre-evidence.md](references/ccre-evidence.md) before classifying cCRE evidence, interpreting biosample-specific signals, comparing releases, or making any functional regulatory statement. It defines the claim boundary, GRCh38 and release provenance, controls, sensitivity checks, and context limits.

## Workflow

1. **Gates (ask before proceeding).** Before first workspace use, stop and ask the user to review source terms; record the notice in provenance. Keep public network access read-only and rate-limited; use `uv run` for helper code, never bare `python3`; ask before installs or large downloads. Record the gate outcome.
2. Normalize the gene/interval, coordinate convention, assembly, biosample, evidence question, and cutoff; if a material choice is missing, ask before retrieval. Record normalized values and any coordinate conversion provenance.
3. Select the source by evidence object: query cCREs through SCREEN GraphQL, raw experiments/files through ENCODE Portal REST with `?format=json` and restricted fields. Record the selected endpoint and rationale.
4. Use bundled `science_search_encode` only as an additional bounded portal search (`query`, optional `limit`); it does not replace SCREEN GraphQL or a field-restricted direct ENCODE request. Record connector use separately from direct requests.
5. Retrieve the smallest relevant result first, then paginate or expand only as needed. Record the exact GraphQL document or REST path, serialized variables/filters, access time, source release/version, pages/counts, returned accessions, and response hashes.
6. Verify schema, record types, interval assembly, payload completeness, and null versus absent metadata; exclude mismatched or duplicate files with reasons. If checks fail, mark affected evidence unavailable or inconclusive and record the failure.
7. Compare cell-type-agnostic cCRE class with biosample-specific signals; keep cCRE, experiment, and file as separate evidence objects. Evaluate a same-biosample well-characterized promoter/enhancer positive control and a matched shuffled or random-genomic background when interpreting overlap; record control results and dependencies.
8. Vary biosample, interval window, and registry/release where available; record whether class or overlap changes alter the claim. Use a direct fallback only for the same evidence object, bound transient retries, respect throttling, and ask before large downloads.
9. Verify the claim table against `references/ccre-evidence.md`, including status, uncertainty, assembly, release, and applicability; preserve failures, null results, and the smallest falsifiable next query. Record the verification outcome.

## Outputs

Return one `encode-ccre-evidence-v1` record with normalized interval and assembly (`interval`, `assembly`), biosample (`biosample`), query provenance (`query_ledger`), distinct cCRE and experiment/file evidence (`ccres`, `experiments`, `files`), returned and excluded records with reasons (`included`, `excluded`), source release and response extent (`source_release`, `response_extent`), missingness (`missingness`), claim IDs and status (`claims`), dependencies (`dependencies`), uncertainty and applicability (`uncertainty`, `applicability`), limitations (`limitations`), and smallest falsifiable next query (`next_action`). Use only `supported`, `contradicted`, `inconclusive`, or `unavailable` for claim status. Save queries, records, exclusions, and hashes with `$science-provenance`; use `$science-review` before presenting a material regulatory interpretation.

## Boundaries

- Report the genome assembly and biosample/cell type; regulatory calls are cell-type specific.
- Cite only ENCODE accessions actually returned.
- A candidate cCRE is not proof of enhancer function, target-gene assignment, or causal disease mechanism. ChIP-seq and other experiments remain assay-specific. Do not combine coordinates across assemblies without explicit conversion, or count multiple files from one experiment as independent evidence. Preserve terms, network, `uv run`, install and large-download gates above.
