---
name: ensembl-search
description: "Resolve gene/transcript/protein IDs, fetch genomic or protein sequences, retrieve gene structure (exons), and predict variant consequences (VEP) via the Ensembl REST API. Use as an ID translator, sequence source, and variant-effect tool. Public API, no credential needed."
license: Apache-2.0
---

# Ensembl Search (Codex-native)

Codex-native adaptation of Google DeepMind's `ensembl-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Decision contract
Record species, input symbol or stable identifier, requested operation (lookup, cross-reference, sequence, gene structure, or VEP), genome assembly, and evidence cutoff. Keep gene, transcript, and protein identifiers distinct. For variant consequences, retain exact HGVS or region/allele representation and do not infer equivalence from a name alone.

## Workflow
**Gates (ask before proceeding):** on first use in a workspace, tell the user to review the source's terms of use and record the notice in provenance. Read-only public access; be polite about rate limits. Write large responses to a file and parse them; if you write helper code, run it via `uv run`, never bare `python3`. Ask before installs or large downloads.

Use Ensembl REST `https://rest.ensembl.org` (GRCh37 at `https://grch37.rest.ensembl.org`). Resolve IDs with `/lookup/id/<id>` or `/xrefs/symbol/<species>/<symbol>`; fetch sequence with `/sequence/id/<id>`. Predict variant consequences with `/vep/<species>/hgvs/<hgvs>` or `/vep/<species>/region`. The optional MCP tool `science_search_ensembl` accepts `query` and optional `limit` (1–10); use it for supported gene search, not as a substitute for the direct REST operations above.

Record exact request, endpoint/tool, species, assembly, release/version or update metadata when reported, access time, returned identifiers and counts, exclusions with reasons, and response hash/artifact. Validate response identity and flag truncation, missing fields, nulls, and service errors separately. Retry only bounded transient failures; a missing lookup is not a biological negative. Record queries, endpoints, and cited identifiers with `$science-provenance`; check claims with `$science-review` before presenting.

## Outputs
Return normalized input, resolved Ensembl stable IDs and object type, species, assembly, source release, exact sequence/feature/variant consequence returned, and an evidence table. Include query and response provenance, exclusions, uncertainty, ID ambiguity, limitations, and the smallest confirmatory lookup. State whether the output is an annotation, sequence record, or computational prediction.

## Boundaries
State the species and assembly (GRCh38 vs GRCh37) explicitly. Cite only Ensembl IDs actually returned; VEP predictions are computational. A consequence prediction is not an observed molecular effect, pathogenicity determination, or clinical diagnosis. Stop if species, assembly, allele, or identifier mapping cannot be resolved.
