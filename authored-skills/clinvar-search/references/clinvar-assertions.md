# ClinVar assertion reconciliation

## Claim semantics

Treat the source statement as a database assertion, never as clinical or
functional truth. Keep claim ID, variant representation, condition, assertion
type, submitter, accession, date/release, and status together.

- **Record identity:** supported only when returned alleles, assembly, and
  condition match the request; otherwise unresolved and unavailable.
- **Submitter classification:** supported as a report of what that submitter
  asserted, not as independent validation. Preserve the exact submitted term,
  assertion criteria, evidence citation, and date.
- **Aggregate classification:** supported only as a report of the ClinVar
  aggregate for the same assertion type and variant-condition scope. Do not
  merge separate RCV conditions or germline, oncogenicity, and somatic impact.
- **Agreement or conflict:** agreement means included returned submissions
  assert compatible terms for the same scope. Conflicting terms remain
  contradicted at the aggregate-concordance claim level; do not vote them away.
- **Absence:** no returned record means unavailable, not benign, reference, or
  evidence of no clinical effect. A service error or truncated response is
  inconclusive, not a no-match.

Use one status vocabulary throughout: `supported`, `contradicted`,
`inconclusive`, or `unavailable`. `Supported` means the stated database claim
matches the retrieved records and scope; it does not establish biological,
clinical, causal, or functional truth.

## Review status and star interpretation

Report the review-status text and star count together. For germline aggregate
records, four stars denotes practice guideline, three expert panel, two
criteria-provided multiple submitters with no conflicts, one may indicate
criteria-provided conflicts or a single submitter, and zero may mean criteria
were not provided or no classification was provided. The one- and zero-star
counts are not unambiguous without the text. Review status describes level and
transparency of review; it does not guarantee correctness. Somatic clinical
impact aggregates use different conflict semantics, so do not transfer the
germline star interpretation to them.

Inspect each SCV when conflicts, conditions, or review status matter. Record
submitter organization and any cited shared publications, laboratories,
expert panels, or evidence sources. Multiple submitters are not necessarily
independent; do not call them replication without evidence of independent
assessment and underlying data.

## Source dependencies and release

Pin the access date and the ClinVar release, record version, or last-updated
metadata returned by the selected interface. Preserve VCV, RCV, and SCV
accessions as distinct identifiers; VCV can aggregate across conditions, while
RCV is condition-specific. Keep exact query, endpoint, retrieved records,
response hash, and exclusions. If version metadata is absent, say so rather
than inferring a release from the current website.

Treat records that cite the same study, submitter group, patient series, or
expert panel as potentially dependent. A submission count is not a count of
independent cohorts or evidence sources. Retain source relationships and
distinguish direct variant assertions from haplotype/genotype-only records.

## Uncertainty and controls

Carry uncertainty as explicit unresolved identity, condition mismatch,
review-status ambiguity, conflicting assertions, missing criteria, stale
record, coverage gap, or service/response limitation. Report which uncertainty
changes the classification claim and what additional record would resolve it.
Do not invent a probability or confidence interval from star count.

For a domain control set, select a known pathogenic and a known benign ClinVar
record with matching condition, allele, build, and release; verify their exact
accessions and classifications before use. Include a deliberately nonexistent
query as a negative retrieval control. Record expected and observed outcomes;
an unexpected control result triggers query, release, and normalization review,
not forced relabeling. Never use a control result to diagnose an individual.

## Sensitivity and applicability

Recheck the claim after varying evidence cutoff or release, using SCV versus
VCV/RCV scope, separating conditions, and excluding potentially dependent
submitters or shared studies. A change in identity, classification, conflict
state, or whether the status is supported is material fragility; report both
results and downgrade the synthesis to inconclusive if the choice is unresolved.

ClinVar is a submission archive and its contents depend on what submitters
provide. It may be stale, incomplete, condition-specific, or based on different
classification criteria. Variant normalization, genome-build mismatches,
complex alleles, and haplotypes can defeat direct matching. The archive does
not establish penetrance, functional effect, individual risk, or diagnosis.

## Common failure modes and detection

- **Build or allele mismatch:** compare assembly, reference/alternate alleles,
  and normalized record before accepting; mismatch stays unresolved.
- **Condition collapse:** compare condition and assertion type at each RCV/SCV;
  different conditions remain separate claims.
- **Star overclaim:** inspect review-status text and contributing submissions;
  never treat stars as a truth score.
- **False submitter independence:** compare submitter identity and cited
  evidence; mark shared evidence as a dependency.
- **Conflict hidden by aggregate:** inspect submitted records and retain
  incompatible classifications with their scopes.
- **Absence read as benign:** test a nonexistent-query control and distinguish
  no match from unavailable service, null, omitted data, and truncation.
- **Stale or partial retrieval:** verify release/access date, pagination, and
  response completeness; preserve failed pages and retry only bounded
  transient failures.

## Sources

- Landrum et al., “ClinVar: improving access to variant interpretations and
  supporting evidence,” 2018.
- NCBI ClinVar, “Review Status” and “Representation of classifications in
  ClinVar,” current documentation consulted 2026.
- Richards et al., ACMG/AMP standards for interpretation of sequence variants,
  2015. This framework informs clinical variant-classification terminology;
  this lookup skill does not apply it to diagnose or classify a person.
