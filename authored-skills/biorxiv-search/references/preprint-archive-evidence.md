# bioRxiv and medRxiv archive evidence

## Claim classes

- **Archive-metadata:** DOI, title, author, date, category, version or abstract
  appears in the returned API record. Missing fields remain unknown.
- **Search-process:** a DOI route or bounded date/category pages returned saved
  records. State the exact range, cursor and completion; this is not keyword
  coverage.
- **Preprint-result:** an abstract or paper reports an observation. Verify its
  version and text; label abstract-only support and preserve study design and
  uncertainty.
- **Publication-status:** a returned published-DOI link establishes a possible
  relation only after checking identity; it does not make the preprint and
  article independent evidence.
- **Synthesis:** connect versions and shared cohorts; do not count repeated
  reports as replication. Preprints remain unreviewed unless separate review
  evidence is established.

## Source dependencies and independence

Record bioRxiv versus medRxiv route, exact DOI/date/category URL, access time,
cursor, response counts, source-reported version/date, and page completion.
Retain raw responses and source metadata as returned; do not invent API release
or update values. DOI identifies a versioned scholarly record but related
preprint versions and journal articles can represent one study. Link records
only when returned metadata or paper text supports identity. Distinct records
can share cohorts; record this dependency and avoid counting portal copies as
independent observations.

## Uncertainty and controls

Carry uncertainty from bounded date range, category selection, cursor/page
completion, null metadata, version changes, abstract-only text, and reported
study uncertainty. Positive control: fetch a known DOI or known date/category
record and verify its ID and fields. Negative control: query a nonmatching
date/category window or unrelated DOI and confirm no eligible record. Controls
test route, not archive-wide coverage. Preserve rate-limit, malformed-body and
transient errors; retries do not convert a failed range into complete search.

## Sensitivity and applicability

Vary DOI route versus date/category route where applicable, date bounds,
category, cursor/page cap, and version handling one at a time. Compare unique
studies, not just records. Mark conclusions fragile when a reasonable boundary
or category change alters the eligible set or when completion is uncertain.
The archive is unsuitable for open-ended keyword discovery and broad local
scans; its date/category scope, submission practices, version history, and
preprint-only status limit applicability. Metadata/abstracts cannot support
full-text claims or clinical conclusions.

## Failure detection

- Wrong route: require DOI or bounded date/category; redirect topic-only
  requests to a keyword-capable source.
- Truncated/malformed response: validate body and required fields, reconcile
  cursors and counts, retain error and mark incomplete.
- Version confusion: compare DOI/version/date and linked publication; preserve
  separate entries when identity is uncertain.
- Missing DOI or page: mark unavailable; do not infer no study or effect.
- Overbroad scan: inspect date span and request count before paging; stop and
  narrow if outside the allowed short window.

## Source basis

bioRxiv API documentation and server policies describe archive endpoints,
record versions, and preprint scope; medRxiv policies describe its separate
medical preprint context. PRISMA 2020 statement (Page et al., 2021) informs
transparent search reporting. These sources do not establish peer review,
exhaustive coverage, or clinical validity.

For each claim retain the DOI/version, text locator, publication-state evidence,
and whether support came from metadata, abstract, or full text. Report date
bounds, pages and observed record denominator. Separate archive uncertainty
from study uncertainty. Preserve the initial response receipt when a later
version or published link changes the record.
State whether the requested range reached its completion marker or only a
declared cap. Do not compare record totals across different category/range
denominators without qualification. If the service does not report an update or
release identifier, retain that as unknown rather than infer one.
