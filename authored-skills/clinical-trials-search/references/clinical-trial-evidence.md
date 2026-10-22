# Clinical trial registry evidence

## Claim semantics

Classify claims about what the registry records separately from claims about
clinical effects. A **supported** registry claim is directly present in a
retrieved record at the stated cutoff and matches the NCT ID and requested
field. A **contradicted** registry claim conflicts with a complete, retrieved
field for that record. A **supported** search-coverage claim requires the
declared query and filters to have completed all available pages; it means only
that the stated records matched that query, not that the search found every
relevant trial. An **inconclusive** claim has conflicting, ambiguous, missing,
or scope-sensitive records. An **unavailable** claim lacks a response or
required data because of access, API, or completeness failure.

Registration status, study design, outcome measures, results-submission state,
and posted summary results are distinct observations. A record marked completed
does not itself establish that results were posted, analyzed as planned, or
valid. A record's absence of a results field is not a null outcome. Do not derive
efficacy, safety, or participant eligibility from registration metadata.

For any count, specify endpoint, query, filters, cutoff, total-count behavior,
and pagination completeness. Counts from different filters or access times are
not interchangeable. Eligibility criteria can support a report of what the
record says; they do not establish that a person qualifies or should enroll.

## Source dependencies and independence

Treat an NCT ID as the registry record identity, not as an independent
experiment. Multiple registry versions, linked publications, secondary reports,
or analyses that reuse the same participant cohort share evidence. Group them
under a study/cohort dependency and identify linked NCT records where reported.
Do not sum repeated registry entries as distinct trials or call several papers
independent replication without checking cohort overlap.

Pin the API v2 endpoint, exact query and field list, retrieval time, returned
NCT IDs, page tokens, source-reported update metadata, and any record version or
history information actually returned. If update/version information is absent,
record it as unavailable; do not infer a version from a locally cached copy.
Keep record-level metadata separate from publication dates and result-posting
dates.

## Uncertainty and reporting

Carry uncertainty as named missingness, ambiguity, conflict, or coverage limits,
not as an invented confidence interval. Preserve unknown fields, unresolved
term mappings, competing NCT candidates, pagination caps, failed pages, and
disagreement between registry and linked publications. State whether each item
is missing from the record, unavailable from retrieval, or not applicable.

Report the evidence cutoff and access time. For evolving records, describe the
claim as applying to the retrieved snapshot. If a source update field is absent
or stale by the question's criteria, lower the claim to inconclusive or
unavailable and state why. Never let the number of records stand in for
certainty or completeness.

## Controls and sanity checks

- Positive control: retrieve a user-supplied known NCT ID and confirm that the
  returned record contains the expected identifier and requested basic fields.
  If no suitable known ID is supplied, label this check not run.
- Negative control: issue an intentionally impossible exact identifier or
  clearly out-of-scope term and confirm that the API response is distinguished
  from a transport or parsing failure. Do not use this as evidence that the
  substantive question has no trials.
- Sanity checks: compare `countTotal=true` with retrieved unique NCT IDs and
  verify page-token continuity; check duplicate IDs, impossible dates, status
  vocabularies as returned, and missing-versus-null fields.
- If a filter is material, compare a small unfiltered or independently stated
  query with the filtered set; record expected exclusions and unexplained
  discrepancies rather than assuming server filters are exhaustive.

## Sensitivity analysis

Vary plausible condition/intervention synonyms, ontology mappings when used,
recruitment status, phase, geography, date cutoff, and page cap one at a time.
Record the candidate NCT IDs added or removed and the reason. Treat a change as
fragile when a plausible alternative changes inclusion of a decision-relevant
record, reverses a count-based comparison, or changes whether retrieval is
complete. Mark affected claims inconclusive until the query scope is resolved.
Do not tune the query after seeing records without retaining the original and
the changed query.

## Applicability domain and failure modes

The registry describes submitted and curated study records. It may be stale,
incomplete, inconsistently coded, or silent about outcomes. It is not a
comprehensive map of all research activity, and public record fields do not
provide adjudicated patient-level eligibility.

- **Empty result treated as no evidence:** detect by checking filters, synonyms,
  API success, count, page tokens, and an alternate query; report scope limits.
- **Count treated as complete:** detect missing token traversal, capped pages,
  duplicate IDs, or a total larger than retrieved unique IDs; label incomplete.
- **Status treated as outcome:** detect claims of benefit or harm without
  posted results and a suitable analysis; downgrade to inconclusive.
- **Registration or publication duplication:** detect repeated cohorts, linked
  NCT IDs, and overlapping publications; represent a shared dependency.
- **Record treated as patient match:** detect individual recommendations;
  stop at record description and refer to qualified study staff.
- **Field absence treated as negative:** compare missing, explicit null, and
  populated values; preserve each separately.

## Sources

- World Health Organization, **WHO Trial Registration Data Set**, version 1.3
  (2017): minimum registration fields and terminology. It supports describing
  registry data elements, not judging trial efficacy.
- Schulz KF, Altman DG, Moher D, **CONSORT 2010 Statement** (2010): reporting
  of randomized trials. It informs completeness questions for reports, not
  registry search coverage or causal validity of an individual record.
- ClinicalTrials.gov, **API v2 Documentation** (retrieved 2026): endpoint,
  query, field, and pagination semantics. Record retrieval time because live
  service documentation can change.
