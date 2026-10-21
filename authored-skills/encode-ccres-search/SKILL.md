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

## Workflow

1. For regulatory annotations, query cCREs by region/cell type via the SCREEN GraphQL endpoint.
2. For raw experimental data (ChIP-seq peaks, etc.), query the ENCODE Portal REST search with `?format=json` and restrict fields.
3. The bundled `science_search_encode` tool is an additional bounded portal search; it accepts `query` and optional `limit` and does not replace SCREEN GraphQL or a field-restricted direct ENCODE request. Preserve both documented direct endpoints above.
4. Record exact GraphQL document or REST path, serialized variables/filters, assembly, biosample, access time, source release/version, returned accessions, pages/counts and response hashes. Validate schema, interval assembly and record types; flag truncated pages or payloads. Preserve null and absent metadata separately and list returned and excluded records with reasons.
5. Retry transient errors only a bounded number of times and respect throttling. On failure, use a direct route only for the same evidence object; otherwise mark unavailable. Ask before large data downloads as required by the gate.

## Outputs

Return normalized interval/assembly and biosample, query ledger, cCRE and experiment/file evidence tables, returned/excluded records, source identifiers/release, response extent, and missingness. Assign claim IDs and status `supported`, `contradicted`, `inconclusive`, or `unavailable`; explain uncertainty, dependencies, limitations, and the smallest falsifiable next experiment or query. Save query, records, exclusions and hashes with `$science-provenance`; use `$science-review` before presenting a material regulatory interpretation.

## Boundaries

- Report the genome assembly and biosample/cell type; regulatory calls are cell-type specific.
- Cite only ENCODE accessions actually returned.
- A candidate cCRE is not proof of enhancer function, target-gene assignment, or causal disease mechanism. ChIP-seq and other experiments remain assay-specific. Do not combine coordinates across assemblies without explicit conversion, or count multiple files from one experiment as independent evidence. Preserve terms, network, `uv run`, install and large-download gates above.
