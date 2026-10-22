# arXiv evidence interpretation

## Claim classes

- **Repository metadata:** an ID, title, abstract, subject, version, or date
  appears in the returned record. Do not infer peer review or full-text content.
- **Search-process:** a saved query/page returned specific IDs. Assign only
  within its parameters and completeness; MCP discovery is bounded and
  unpaginated.
- **Paper-result:** a finding stated in the paper. Verify the specific version
  and text locator; abstracts support only abstract-level summaries.
- **Publication-status:** a source-linked journal/published record confirms a
  relation. Verify its identity independently; do not infer it from an arXiv ID.
- **Synthesis:** reconcile versions and studies, group shared data/cohorts, and
  report conflicts. A preprint is not peer-reviewed evidence.

## Source dependencies and independence

Record whether retrieval used built-in MCP or arXiv API, exact query, fields,
access time, page parameters, IDs, version/date, reported update data, and
response counts. Pin observed API/schema metadata when available; do not invent
a release. Version suffixes are versions of a record and are not separate
studies. A published paper and its preprint are usually linked manifestations
of one work, not independent confirmation. Distinct papers may reuse datasets;
record the relationship when stated by the authors or source. Preserve source
links and uncertain identity matches rather than silently merging.

## Uncertainty and controls

Carry uncertainty from query coverage, returned limit, missing pages, abstract
only access, version drift, publication state and study-level intervals or
limitations. Positive control: search a known relevant arXiv ID or paper and
verify the expected record/version. Negative control: search a clearly
off-topic phrase and inspect whether screening excludes it. These controls
test retrieval/screening, not recall or correctness. Failed API requests,
empty results and missing IDs are unavailable/bounded observations, not
evidence that no work exists.

## Sensitivity and applicability

Vary terms, author, subject category, date bounds, result limit and API page
size one at a time. Compare eligible unique works and claim classifications;
report material changes as fragile. arXiv is a preprint repository with
discipline-specific coverage and no guarantee that records are peer-reviewed,
complete, or representative. Applicability depends on the paper's system,
data, methods and version. This workflow is not suitable for peer-reviewed-only
or exhaustive retrieval without complementary sources and screening.

## Failure detection

- Malformed/truncated response: validate XML/JSON and reconcile page count; keep
  failed response and mark incomplete.
- Version conflation: compare base ID, version/date, title and text; preserve
  distinct records until verified.
- Abstract overreach: require full text for specific methods/results claims;
  label claims based on summary alone.
- Peer-review assumption: check source-linked published identity and label
  status unknown if absent.
- Empty retrieval: inspect positive control and query parameters; report only
  no matches in the returned bounded set.

## Source basis

arXiv API documentation and submission policies describe repository metadata,
versions, and moderation scope. PRISMA 2020 statement (Page et al., 2021)
provides transparent search/reporting principles. Neither establishes that a
bounded arXiv query is exhaustive or peer reviewed.

For each paper-level claim, retain the exact version, page/section locator,
publication status evidence, and whether the source read was abstract or full
text. Report query limit and returned-page denominator. Distinguish uncertainty
in retrieval from uncertainty reported by the paper. Preserve the source
snapshot because versions and publication links can change.
Record whether each result set came from bounded MCP discovery or paginated API
retrieval; their denominators are not interchangeable. If release identity is
not reported, say so. Retain failed and excluded records so a later query does
not erase earlier retrieval uncertainty.
