---
name: dbsnp-search
description: "Look up and map short human variants (SNPs, indels) in NCBI dbSNP: resolve between rsIDs, GRCh38 coordinates, and HGVS, and get variant type, gene, clinical significance, and allele frequencies. Public NCBI API, no credential needed."
license: Apache-2.0
---

# Dbsnp Search (Codex-native)

Codex-native adaptation of Google DeepMind's `dbsnp-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Decision contract
Record species, input identifier, genome assembly, reference and alternate alleles when supplied, and desired mapping or annotation. Accept rsIDs, VCF coordinates, or HGVS as queries, but do not assume coordinate equivalence across assemblies. A mapping is resolved only when the returned record agrees on allele and locus.

## Workflow
**Gates (ask before proceeding):** on first use in a workspace, tell the user to review the source's terms of use and record the notice in provenance. Read-only public access; be polite about rate limits. Write large responses to a file and parse them; if you write helper code, run it via `uv run`, never bare `python3`. Ask before installs or large downloads.

Use NCBI Variation Services `https://api.ncbi.nlm.nih.gov/variation/v0/` to map identifiers and obtain variant context. NCBI E-utilities `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/` (`db=snp`) is an additional retrieval route. Given an rsID, fetch the refsnp record for type, gene, clinical significance, allele frequencies, and GRCh38 coordinates; map between rsID / VCF coordinates / HGVS with the Variation Services endpoints. Validate returned alleles, assembly, and identifier before accepting a mapping. The optional Codex Science MCP route is `science_query_source_v2` with `source="dbsnp"`; pass `source`, `parameters`, optional `operation`, `page_size`, `max_pages`, `evidence_cutoff`, and `include_snapshot`. Check `science_list_source_contracts` before setting source-specific `parameters`.

Record exact request, endpoint/tool, access time, returned and excluded records with reasons, response hash, and source release/version when reported. Report missing fields as missing; distinguish no match, explicit null, incomplete response, and service failure. Limit retries to transient failures, bound pages, and never convert a failed query into a negative result. Record queries, endpoints, and cited identifiers with `$science-provenance`; check claims with `$science-review` before presenting.

## Outputs
Return normalized input, assembly (GRCh38 when that is the returned reference), allele-level mapping, returned rsIDs, variant type, gene links, clinical assertions, and frequencies with population/source context where available. Include an evidence table with included/excluded counts, uncertainty, mapping conflicts, limitations, and the smallest follow-up needed. Preserve response artifact/hash and query metadata.

## Boundaries
Report the assembly (GRCh38) explicitly; coordinates differ across builds. Cite only rsIDs actually returned; never invent frequencies. A dbSNP record or linked clinical assertion is not proof of pathogenicity, and population frequency is not a clinical classification. Stop if alleles or assembly cannot be reconciled.
