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

Record species, input identifier, genome assembly, reference and alternate
alleles when supplied, and desired mapping or annotation. Accept rsIDs, VCF
coordinates, or HGVS as queries, but do not assume coordinate equivalence
across assemblies. A mapping is resolved only when returned records agree on
allele and locus. An rsID is a database cluster identifier, not a unique
clinical or functional conclusion.

## Reference usage

- Read [references/dbsnp-identity.md](references/dbsnp-identity.md) before
  mapping rsIDs, resolving merged identifiers, or reconciling alleles, builds,
  VCF, and HGVS representations.
- Read [references/dbsnp-identity.md](references/dbsnp-identity.md) before
  assigning mapping status, claiming a record is absent, or interpreting linked
  clinical/frequency annotations.

## Workflow

1. **Gates (ask before proceeding).** On first use in a workspace, ask the user
   to review the source's terms of use and wait for confirmation; record the
   notice in provenance. Ask before installs or large downloads. Write large
   responses to a file and parse them; run helper code via `uv run`, never bare
   `python3`. Continue only after required notice and approvals; record them.
   Access remains read-only and rate-limit polite.
2. Record species, identifier type/value, assembly, supplied REF/ALT, desired
   annotation, and evidence cutoff; if identity or build is unknown, keep the
   mapping unresolved and record what is missing.
3. Read the reference rules; choose whether the claim concerns identifier
   mapping, allele representation, or a linked annotation, and record its
   claim ID and matching criteria.
4. Query NCBI Variation Services at
   `https://api.ncbi.nlm.nih.gov/variation/v0/` for mapping and variant context.
   NCBI E-utilities at `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`
   (`db=snp`) is an additional retrieval route. Given an rsID, retrieve the
   refsnp record for type, gene, clinical significance, frequencies, and
   returned GRCh38 coordinates; use Variation Services to map rsID/VCF/HGVS.
   If using optional Codex Science MCP, use `science_query_source_v2` with
   `source="dbsnp"`. `science_query_source_v2` requires `source` and
   `parameters`; optional top-level fields are `operation`, `page_size`,
   `max_pages`, and `include_snapshot`. Current v2 legacy sources accept
   required `parameters.query` (a non-empty string) and optional
   `parameters.limit` (an integer from 1 to 10).
   `science_list_source_contracts` lists available sources and operations; it
   does not return a parameter schema. Current v2 routes refuse
   `evidence_cutoff`; record the cutoff in your protocol and apply it to
   returned record dates yourself, treating missing dates as unresolved.
   Record exact request, endpoint/tool, access time, and release/version when
   reported.
5. Verify returned identifier, allele, assembly, and locus before accepting a
   mapping; retain merged-from and current rsIDs as separate facts and record
   representation conversions and failed or truncated pages.
6. Compare allele-level annotations only after identity resolution; preserve
   clinical assertions and frequencies with their source, population, and
   dependencies, and record included/excluded records, counts, and reasons.
7. When feasible within rate limits (at least once per run, not per lookup), check known pathogenic and benign retrieval controls plus a nonexistent
   identifier; vary build/representation/release where relevant and record
   outcomes and any status changes.
8. **Verify** that status is supported, contradicted, inconclusive, or
   unavailable, and that missing fields, explicit nulls, no match, incomplete
   response, and service failure remain distinct; save response/hash and query
   metadata, then hand queries/endpoints/IDs to `$science-provenance` and claims
   to `$science-review` before presenting.

## Outputs

Produce `dbsnp-identity-evidence-v1` with required fields: normalized
input and allele representation; species and assembly; returned and merged
rsIDs; variant type; gene links; allele-level mapping; claim IDs and claim
class; status (`supported`, `contradicted`, `inconclusive`, or `unavailable`);
clinical assertions and frequencies with population/source context when
available; exact requests and endpoints/tools; retrieval time and release;
included/excluded counts and reasons; mapping conflicts and dependencies;
uncertainty and limitations; smallest follow-up; response artifact/hash; and
provenance/review references.

## Boundaries

Report the assembly explicitly (GRCh38 when that is the returned reference);
coordinates differ across builds. Cite only rsIDs actually returned; never
invent frequencies. A dbSNP record or linked clinical assertion is not proof of
pathogenicity, and population frequency is not clinical classification. Stop if
alleles or assembly cannot be reconciled. Distinguish no match, explicit null,
missing fields, incomplete response, and service failure. Bound pages and
transient retries; never convert a failed query into a negative result.
