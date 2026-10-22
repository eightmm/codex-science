# GWAS Catalog association evidence

## Claim semantics

Use **supported** for a statement that accurately describes a returned curated
association record, including the trait mapping, variant, effect allele,
estimate/significance, study, and ancestry as represented in that record.
Use **contradicted** only when a complete, scope-matched returned record
explicitly conflicts with the claim. Use **inconclusive** when trait mapping,
allele/build harmonization, ancestry, study design, or missing fields permit
materially different interpretations. Use **unavailable** when required records
could not be retrieved or the source response is invalid or incomplete.

These statuses apply to the stated source and scope. A cataloged association is
evidence that a curated record reports an association; it does not by itself
establish causality, replication, clinical utility, or a causal gene. A
non-significant or absent catalog record is not proof of no association.
Preserve the distinction between lead-variant records and full summary
statistics: the former do not expose every tested variant, model, or result.

Keep effect direction tied to the reported effect allele and phenotype coding.
Do not compare effect estimates until alleles, units, trait definitions,
assembly, and model are harmonized. A p-value alone is not an effect size or
clinical importance measure.

## Source dependencies and independence

Use study accession and publication identifiers to group records from the same
study. Multiple catalog rows may reflect correlated lead variants, related
traits, multiple ancestries, or analyses of overlapping participants. A
meta-analysis may reuse component cohorts that also appear as individual
studies. Record known sample overlap and ancestry composition; do not count
portal mirrors or repeated records as independent replication.

Record the GWAS Catalog API v2 endpoint/contract, exact query, access date,
evidence cutoff, and source-reported release or last-updated metadata. Preserve
the reported publication and study accession. If a release/version is not
provided by the response, record it as unavailable rather than inventing one.
Separate retrieval date from publication date and source update date.

## Uncertainty and reporting

Carry uncertainty through explicit fields: trait mapping alternatives, missing
effect estimates, unknown sample size, broad or mixed ancestry labels, uncertain
build, unaligned alleles, unresolved overlap, incomplete pages, and source
release ambiguity. Mark unavailable values as missing; never impute them from a
related record without labeling the derivation and dependency.

Report ancestry and sample size as returned, not as a claim that all relevant
populations are represented. Explain whether the source record is a lead
association and whether a requested summary-statistics-level analysis was
possible. Do not invent confidence intervals, replication status, or causal
probabilities from catalogue metadata.

## Controls and sanity checks

- Positive control: when the user supplies a known study accession or rsID,
  retrieve it and confirm the identifier, mapped trait, and returned study
  fields. If none is supplied, mark this check not run.
- Negative control: query an impossible exact identifier or an explicitly
  unrelated trait as a plumbing check; verify valid no-match versus retrieval
  failure. Do not use this as evidence of absent genetic association.
- Identity checks: verify trait ontology ID against the question; check that
  build and effect/other alleles are present before directional comparison.
- Consistency checks: compare study accession, publication, ancestry, and
  sample size across rows; flag suspicious duplicate rows, incompatible trait
  mappings, implausible allele encodings, and page-count mismatches.
- If a claim concerns a locus, retain the full set of retrieved candidate
  associations and rejected candidates, not only the preferred lead variant.

## Sensitivity analysis

Vary plausible EFO/MONDO trait mappings, exact versus broader trait scope,
ancestry filters, evidence cutoff or source release, build/variant resolution,
and query/pagination limits one at a time. Preserve included and excluded
study accessions and variant IDs for every run. A claim is fragile when a
plausible mapping or population choice changes included studies, effect
direction, or whether an association is present; when build/allele choice
changes the locus; or when the cutoff changes the evidence set materially.
Mark affected claims inconclusive until the scope choice is resolved. Do not
select a mapping because it yields the expected association.

## Applicability domain and failure modes

The GWAS Catalog is a curated resource, not a complete census of genetic
association studies. Its lead-association records do not substitute for
individual-level data or full summary statistics. Trait curation, ancestry
labels, genome builds, and release coverage can constrain interpretation.
Association search alone cannot establish a causal variant, mechanism, target
gene, or clinical actionability.

- **Trait label mismatch:** detect by checking ontology ID and rejected
  alternatives; stop if phenotype scope remains ambiguous.
- **Allele/build mismatch:** detect missing or conflicting assembly/effect
  allele and alignment fields; prohibit directional comparison until resolved.
- **Lead record treated as complete scan:** detect claims about all variants or
  null loci without summary statistics; narrow the claim or mark unavailable.
- **Association treated as causal:** detect causal or gene-mechanism language
  without appropriate fine-mapping, colocalization, and independent evidence;
  retain the association-only claim and hand off to the relevant synthesis skill.
- **Cohort overlap counted as replication:** compare study accessions,
  publications, ancestry and sample descriptions; group shared participants.
- **Missing record treated as null:** check API validity, page caps, query scope,
  source cutoff, and trait synonyms; mark incomplete or unavailable as needed.
- **Cross-ancestry effects pooled unharmonized:** compare ancestry, allele
  coding, and phenotype; keep strata separate until harmonized.

## Sources

- Little J, et al., **Strengthening the Reporting of Genetic Association
  Studies (STREGA)** (2009): reporting domains for genetic association studies;
  it does not certify a catalog record or establish causality.
- Buniello A, et al., **The NHGRI-EBI GWAS Catalog of published genome-wide
  association studies, targeted arrays and summary statistics 2019** (2019):
  catalog scope and curation context; it does not make this search exhaustive.
- NHGRI-EBI, **GWAS Catalog REST API v2 documentation** (retrieved 2026): query
  and response semantics. Record retrieval time because live API documentation
  can change.
