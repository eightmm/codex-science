# PubMed evidence interpretation

## Claim classes

- **Record-descriptive:** the retrieved record has a title, author, date, or
  publication type. Assign only after the field appears in the source record;
  missing fields remain unknown.
- **Search-process:** a query returned a stated set/count. Assign only for the
  exact query, endpoint, time, bounded result and completeness actually saved.
  It says nothing about all eligible studies.
- **Study-result:** a paper reports an estimate or observation. Verify the
  cited abstract/full-text passage, population, design, comparator, outcome,
  denominator and uncertainty before assigning supported/contradicted.
- **Synthesis:** multiple studies support a common conclusion. Reconcile design,
  population and outcome differences and group shared cohorts/publications;
  otherwise report mixed or inconclusive evidence.
- **Causal/clinical:** requires design-appropriate causal evidence and explicit
  applicability. A PubMed result, abstract, or association alone cannot warrant
  treatment advice or individual clinical action.

## Source dependencies and independence

PubMed is an NLM bibliographic database; indexing does not guarantee peer
review, full-text availability, or complete retrieval. Record database and
interface (MCP discovery versus E-utilities), exact query, retrieval time,
parameters, returned IDs and any source-reported update value. Pin API/format
and release only when actually reported; never manufacture a release number.
PMID is a record identifier, not a study identifier. Link duplicate reports,
corrections, trial registrations, shared cohorts, and companion analyses at the
study level when the source establishes the relationship. Multiple records or
portals for one cohort are dependent evidence, not replication. Preserve
publication type/status and version distinctions.

## Uncertainty and controls

Carry uncertainty at both retrieval and study levels: bounded limit, missing
pages/fields, unavailable abstracts, selection decisions, measurement error,
confidence/credible intervals, and risk of bias. Do not convert absent records,
missing abstracts, or failed fetches into zero evidence. Preserve included and
excluded records with reasons. Positive control: a known eligible PMID should
be found or explicitly explained. Negative control: a clearly unrelated term
should not produce an apparently eligible match under the stated criteria.
Controls diagnose the query and screening path, not database-wide recall.

## Sensitivity and applicability

Vary synonyms/MeSH phrasing, field restriction, date limit and publication
filter one at a time; compare eligible PMID sets and claim direction. Treat a
materially changing set, denominator, or claim classification as fragile and
report variants. This workflow is bounded discovery and retrieval, not a
registered systematic review. It can miss non-indexed work, records outside
the chosen terms, delayed indexing, non-English or inaccessible text, and
unpublished evidence. Generalizability depends on each study's population,
setting, design and outcome.

## Failure detection

- ID mismatch or malformed detail: compare requested and returned PMIDs and
  validate response structure; mark unavailable and retain the error.
- Empty/limited result: inspect query, filters, limit, and positive control;
  report bounded non-retrieval, never absence of evidence.
- Duplicate publications: compare PMID, DOI, title, cohort and registration;
  retain separate records linked to one study where justified.
- Claim exceeds source: require a locator in abstract/full text and downgrade
  abstract-only or unverified claims.
- Changed source fields: retain access time and source-reported date; compare
  snapshots before describing drift.

## Source basis

PRISMA 2020 statement (Page et al., 2021) informs transparent search and
selection reporting. Cochrane Handbook for Systematic Reviews of Interventions
(current edition identified at use) informs study-level synthesis and bias
assessment. National Library of Medicine PubMed documentation informs the
database-versus-record boundary. These frameworks do not validate this bounded
retrieval as a systematic review.

For each claim, preserve its text locator, source ID, design, outcome, and
support status. Report the search cutoff and actual fetched denominator beside
any count. Separate study-reported uncertainty from uncertainty caused by
search coverage or selection. A later search can update the retrieved set; it
does not retroactively make the earlier snapshot complete.
