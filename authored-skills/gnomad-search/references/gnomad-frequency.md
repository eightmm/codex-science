# gnomAD frequency and constraint evidence

## Claim semantics

Use claim IDs and one status vocabulary: `supported`, `contradicted`,
`inconclusive`, or `unavailable`. A supported frequency claim means the
retrieved dataset reports the stated allele count/frequency for the normalized
variant, population, and callset context. It does not mean that the variant is
clinically benign, causal, or present/absent in a particular person.

- **Variant identity:** support only when normalized alleles and assembly match
  the requested locus; unresolved representation is unavailable.
- **Frequency:** state exact population stratum and reported AC, AN, AF, and
  filtering context. A global estimate cannot substitute for a requested
  ancestry group.
- **Constraint:** report pLI, LOEUF, oe, and transcript/gene context as
  database estimates; they do not establish an individual variant's effect.
- **No observation:** absent record is not rare or absent in people. If
  coverage, callability, filters, or query completeness cannot be checked, the
  claim is inconclusive or unavailable.

Keep `supported`, `contradicted`, `inconclusive`, and `unavailable` distinct
from raw query outcomes. A successful zero-result response can support only a
carefully scoped statement that no matching record was returned under that
query; it cannot establish population absence.

## Source dependencies, population, and release

Pin gnomAD dataset/version, genome assembly, exome/genome callset, endpoint,
query, access date, and any returned data release metadata. Preserve the
population label exactly as returned. Genetic ancestry group labels are
discrete summaries of heterogeneous populations; they do not identify every
individual's ancestry or represent all variation within a group.

AC counts observed alternate alleles and AN is the number of called alleles
contributing to the estimate. Report both where returned; low AN means less
information and greater sampling uncertainty, while zero AN makes AF
unavailable. Do not calculate an interval unless the method and assumptions are
explicit. Record quality filters, coverage/callability, flags, and whether
frequencies from exome and genome data are combined or discordant. A frequency
without its denominator and QC context is incomplete evidence.

Samples or callsets shared across population views, exome/genome subsets, or
release versions are dependencies, not independent replications. Do not add
their counts or claim independent confirmation. A release change may alter
variant normalization, sample count, ancestry composition, filters, and
frequency estimates; retain old and new versions separately.

## Uncertainty and controls

Carry uncertainty as exact AC/AN, population stratum, coverage/callability,
filter/flag state, missing fields, release, ancestry composition, and query
completeness. Explain whether small AN, poor coverage, or an excluded/flagged
site can change the conclusion. Do not present AF precision beyond source
values or infer a confidence interval from the point estimate alone.

Use a positive retrieval control: a known pathogenic variant with a verified
ClinVar assertion and matching build that is expected to have a gnomAD record
in the selected dataset, when such a record is available. Use a known benign
variant under the same identity checks as a second positive retrieval control;
these are retrieval checks only, not proof that gnomAD distinguishes clinical
classes. Include a deliberately nonexistent variant query as a negative
retrieval control. Verify each control's exact identity, expected observation,
and actual response; do not hard-code an assumed frequency or call absent
records a passing negative without checking completeness.

## Sensitivity and applicability

When relevant, compare overall and requested ancestry-specific strata; exome
versus genome data; dataset releases; and results with/without relevant quality
flags or coverage cutoffs. Preserve source-reported frequencies and do not
silently recompute after exclusions. A change in variant identity, AF estimate
beyond stated precision, rank/order, or status is material fragility. Report
the alternatives; if there is no prespecified tolerance, call the comparison
qualitative and downgrade a conclusion that depends on the choice.

gnomAD aggregates sequenced cohorts and is not a population census. Rare
variants are especially sensitive to sample size, ancestry composition, and
callability. Genes and sites can have uneven coverage; constraint power depends
on gene length, coverage, and model assumptions. Somatic tumors and individual
patient genomes are outside this workflow's applicability domain. Population
labels and allele frequencies may not transfer to an unrepresented or admixed
population.

## Common failure modes and detection

- **Genome-build mismatch:** compare query and response assembly plus reference
  allele; reject a coordinate-only match on another build.
- **Allele normalization mismatch:** normalize indels against the reference;
  compare REF/ALT and split multiallelic records only when the API representation
  makes the queried allele unambiguous. Record every split and retain original
  representation.
- **Absent-as-rare error:** check response success, pagination, dataset,
  coverage, callability, and filters; otherwise no record is inconclusive, not
  evidence of rarity.
- **Low sample-size overclaim:** report AC and AN by population and avoid
  treating zero observed alleles as zero population frequency.
- **Flag or filter ignored:** inspect returned flags and filtering AF context;
  if unavailable, state that limitation and avoid a quality-qualified claim.
- **Population collapse:** compare exact population labels and do not replace a
  requested stratum with a global estimate.
- **Release mixing:** bind each row to its dataset/version and do not combine
  counts across releases or overlapping callsets.
- **Connector failure or truncation:** validate response errors, page limits,
  and counts; preserve partial results and do not retry indefinitely.

## Sources

- Karczewski et al., “The mutational constraint spectrum quantified from
  variation in 141,456 humans,” 2020. Supports constraint estimates and the
  role of coverage/power; it does not define clinical variant interpretation.
- gnomAD v4 release documentation (gnomAD browser help and release notes).
  Supports release-specific sample and ancestry context; it cannot stand in for
  the exact dataset version returned by a query.
- ACMG/AMP joint consensus standards, Richards et al., *Genetics in Medicine*, 2015, for the distinction
  between population-frequency evidence and clinical classification. This skill
  reports database frequency and does not apply a clinical threshold.
