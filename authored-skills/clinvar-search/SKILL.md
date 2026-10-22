---
name: clinvar-search
description: "Look up clinical significance and pathogenicity classifications (Pathogenic, Benign, VUS) and supporting evidence for human genomic variants in NCBI ClinVar. Use for variant clinical interpretation or benchmark controls. Public NCBI API, no credential needed."
license: Apache-2.0
---

# Clinvar Search (Codex-native)

Codex-native adaptation of Google DeepMind's `clinvar-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Decision contract

Record the variant query (rsID, HGVS, or gene), species, supplied assembly,
condition or phenotype, evidence cutoff, and whether the task asks for a record
lookup or an interpretation summary. Preserve ambiguous variants as unresolved
until normalized to a returned ClinVar record. Treat every classification as a
submitter assertion about a specified variant-condition pair, not clinical or
functional truth. Do not collapse distinct conditions or submissions into one
label.

## Reference usage

- Read [references/clinvar-assertions.md](references/clinvar-assertions.md)
  before assigning claim status, comparing submitters, or interpreting star
  levels or conflicting classifications.
- Read [references/clinvar-assertions.md](references/clinvar-assertions.md)
  before excluding a record, treating an absent result as evidence, or reporting
  uncertainty and applicability limits.

## Workflow

1. **Gates (ask before proceeding).** On first use in a workspace, ask the user
   to review the source's terms of use and wait for confirmation; record the
   notice in provenance. Ask before installs or large downloads. Write large
   responses to a file and parse them; run helper code via `uv run`, never bare
   `python3`. Continue only after required notice and approvals; record them.
   Access remains read-only and rate-limit polite.
2. Normalize the query and fix species, assembly, condition, evidence cutoff,
   and lookup-versus-summary scope; if allele, build, or condition is ambiguous,
   stop classification and record unresolved identifiers.
3. Read the reference rules and select a supported claim class; distinguish a
   ClinVar database assertion from clinical truth, and record claim IDs, status,
   and support criteria.
4. Search NCBI E-utilities at
   `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/` (`esearch`, `esummary`,
   `efetch`, `db=clinvar`), retain the exact query and returned IDs, then fetch
   selected records; if using Codex Science MCP, use
   `science_query_source_v2(source="clinvar")` with only the top-level
   arguments `source`, `parameters`, optional `operation`, `page_size`,
   `max_pages`, `evidence_cutoff`, and `include_snapshot`, and first consult
   `science_list_source_contracts` for its parameter schema. Record query,
   endpoint/tool, access time, and release/version when reported.
5. Verify variant allele, assembly, condition, accession, and response
   completeness against the request; mismatch or truncation prevents a positive
   mapping, and the record is retained as unresolved with its reason.
6. Compare the returned SCV submissions and VCV/RCV aggregate for the same
   assertion type; account for review status/stars, classification conflicts,
   and submitter/dependency overlap, then record included/excluded records,
   counts, and reasons.
7. When feasible within rate limits (at least once per run, not per lookup), check positive and negative controls and the smallest relevant sensitivity
   changes described in the reference; record control outcomes and whether the
   conclusion changes.
8. **Verify** that status is supported, contradicted, inconclusive, or
   unavailable, that missing/null/no-match/service-failure states remain
   distinct, and that artifact/hash, timestamp, identifiers, and claim
   dependencies are present; retain response or hash-bound artifact and hand
   query, endpoint, and cited IDs to `$science-provenance`, then claims to
   `$science-review` before presentation.

## Outputs

Produce `clinvar-assertion-evidence-v1` with required fields: query and
normalized variant; species and assembly; condition; claim IDs and claim class;
status (`supported`, `contradicted`, `inconclusive`, or `unavailable`);
ClinVar VCV/RCV/SCV accessions actually returned; classification; review status
and star rating; supporting and conflicting evidence; submitters and known
dependencies; evidence cutoff; retrieval timestamp and release/version;
included/excluded counts and reasons; uncertainty and limitations; smallest
next lookup; response artifact path or hash; and provenance/review references.

## Boundaries

Clinical significance and review status vary in confidence; report the star
rating and its underlying review-status text. This is not clinical or diagnostic
advice. Cite only ClinVar accessions (VCV/RCV) actually returned. A missing
record or blank field is not evidence of benignity; a classification is not an
individual diagnosis or functional proof. Stop interpretation when allele,
build, condition, or record identity cannot be resolved. Do not replace a failed
structured query with broad web search. Preserve exact queries, bound retries to
transient failures, honor service responses, and report no match, unavailable
service, omitted field, explicit null, failed page, and truncation separately.
