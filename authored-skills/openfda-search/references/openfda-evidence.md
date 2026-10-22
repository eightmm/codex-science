# openFDA record interpretation

## Claim semantics

Assign **supported** only to a statement directly supported by retrieved
records from a matching endpoint, with identity and query scope checked.
Assign **contradicted** only when a complete, applicable record explicitly
conflicts with the stated label, report, or enforcement fact. Assign **inconclusive** when
identity, scope, reporting, missingness, or evidence type leaves multiple
interpretations. Assign **unavailable** when the needed endpoint or records
could not be retrieved or validated. An empty search is not a negative safety
finding.

Keep evidence classes separate: adverse-event reports are spontaneous reports;
label text is regulatory product information; recalls are actions concerning
identified products or lots; approvals, clearances, and listings are distinct
regulatory records. A record may support what was submitted or recorded, not
necessarily an event's causality, population incidence, comparative benefit,
or current clinical safety. Do not combine unlike classes into one score.

An event count is a count of returned reports under a query, not an incidence
rate unless a valid denominator, exposure window, and ascertainment method are
available and justified. A label field supports the wording of that label at
the retrieved snapshot; it is not proof of comparative effectiveness. A 510(k)
clearance does not equal FDA approval or a demonstrated clinical outcome.

## Source dependencies and independence

Use product names to discover candidates only. Resolve identity with the
identifiers actually returned, such as an available application, product,
manufacturer, or ingredient identifier, and preserve the exact fields used.
Do not assume similarly named products, formulations, routes, strengths,
manufacturers, or devices are interchangeable.

Reports can be duplicated, follow-up submissions, or linked to the same
underlying event or product. If the source does not expose enough information
to deduplicate, report raw returned counts and that limitation. Shared
manufacturers, ingredients, product applications, and event sources create
dependencies; group them rather than treating records as independent
confirmations. Distinct records within one dataset are not independent studies.

Pin dataset endpoint, exact query/parameters, requested fields, API version or
documentation identity if reported, access time, source update metadata,
pagination state, and artifact hash. State explicitly when the API does not
return a dataset release or record version. Never infer release identity from
the current date or from a cached response.

## Uncertainty and reporting

Carry uncertainty as explicit identity ambiguity, unknown/null fields, missing
denominator, possible duplicate reports, under-reporting, time-window mismatch,
query sensitivity, and endpoint incompleteness. Do not manufacture uncertainty
intervals or causal probabilities. Separate source-reported values from
analyst-derived summaries and state the derivation.

Report access cutoff and any source update time as different values. If
returned metadata does not establish when the underlying records were last
updated, say so. An unavailable response, a valid zero-result response, and a
response with missing fields are different states.

## Controls and sanity checks

- Positive control: retrieve a known product/application identifier when one is
  supplied and confirm that the endpoint returns the expected identifier and
  record class. If there is no known identifier, mark the control not run.
- Negative control: query an impossible exact identifier and verify that a
  valid no-match response is distinguishable from HTTP, schema, or parse error.
  It does not establish absence of adverse events.
- Identity check: compare the returned identifiers and manufacturer/formulation
  context across candidate endpoints before joining results.
- Count check: compare reported total and retrieved unique record identifiers;
  check offset/page continuity, duplicate IDs, malformed dates, and null versus
  absent values.
- Type check: verify the endpoint and record type match the claim; label or
  clearance records cannot serve as event counts or clinical outcomes.

## Sensitivity analysis

Vary plausible brand/generic or ingredient terms, identifiers, formulation or
manufacturer constraints, endpoint, event/date window, requested fields, and
page limit one at a time. Preserve each exact query and the records added or
removed. A result is fragile when a plausible identity resolution changes the
included product, when endpoint choice changes the evidence class, or when a
reasonable date/query change materially changes a count or conclusion. Mark
claims inconclusive until the sensitivity is resolved. Do not select the query
that gives the preferred safety interpretation.

## Applicability domain and failure modes

openFDA provides access to submitted or regulatory records, with endpoint-
specific coverage, fields, lag, and quality. Spontaneous-report systems are
subject to under-reporting, stimulated reporting, duplicates, missing data, and
no exposed-population denominator. The API does not provide a complete census
of events or a causal safety assessment.

- **Report count called incidence or causation:** detect absence of a justified
  denominator or causal design; report only observed report counts.
- **Product-name collision:** detect conflicting or incomplete identifiers and
  formulation/manufacturer metadata; exclude or mark identity inconclusive.
- **Empty result called no risk:** inspect HTTP/schema validity, endpoint,
  query, aliases, pagination, and cutoff; report bounded coverage only.
- **Evidence classes merged:** compare source endpoint and record type with the
  claim; split incompatible records and claims.
- **Pagination or truncation ignored:** compare counts, offsets, and unique IDs;
  mark incomplete and preserve failed pages.
- **Duplicate reports counted as independent:** inspect available follow-up or
  event linkage; if not resolvable, retain raw count and dependency caveat.

## Sources

- U.S. Food and Drug Administration, **openFDA API documentation** (retrieved
  2026): endpoint and query semantics. Record retrieval time because live
  service documentation can change.
- U.S. Food and Drug Administration, **Good Pharmacovigilance Practices and
  Pharmacoepidemiologic Assessment** (2005): limitations and interpretation of
  postmarketing safety evidence; it does not validate an openFDA query.
- U.S. Food and Drug Administration, **FAERS Public Dashboard** data and
  limitations documentation (retrieved 2026): spontaneous-report context and
  its interpretive limits.
