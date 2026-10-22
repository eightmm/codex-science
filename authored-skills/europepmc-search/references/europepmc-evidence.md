# Europe PMC evidence interpretation

## Claim classes

- **Record-descriptive:** an identifier, title, date, publication type, or
  access flag is present in the returned record. Report only observed fields.
- **Search-process:** the recorded query/pages yielded the saved records. Assign
  only with exact query, endpoint, access time, page parameters, and completion
  evidence; bounded search is not exhaustive evidence.
- **Study-result:** a paper reports a finding. Verify the cited text, study
  design, population, outcome, denominator and uncertainty. Distinguish an
  abstract statement from a full-text checked result.
- **Citation-network:** a returned citation/reference link establishes a source
  relation, not support, quality, or independent replication.
- **Synthesis/causal:** compare compatible studies and group shared cohorts.
  Causal or clinical conclusions require design-appropriate evidence and
  review; records alone cannot support advice.

## Source dependencies and independence

Europe PMC aggregates records from sources including PubMed, PMC, preprints,
and patents. The same underlying work can appear as multiple records or
versions. Keep PMID, PMCID and DOI separate; link records only after identity
verification. Record endpoint, exact serialized query, access time, page size
and continuation token, response counts, and source-reported update/release
metadata if present. The bounded MCP discovery interface does not expose
pagination; direct API retrieval has its own query and page lineage. Pin
observed API/schema versions when provided, never infer a release. Preserve
preprint and published states and shared-cohort dependencies.

## Uncertainty and controls

Record missing abstracts/full text, null metadata, page gaps, truncation,
selection exclusions, and uncertainty reported by each study. A missing PMC
full text is not evidence of a null result. Positive control: retrieve a known
eligible PMID/PMCID/DOI through the chosen route. Negative control: use a
clearly out-of-scope query or known nonmatching ID and inspect accidental
matches. Controls test query and parsing behavior, not source recall. Preserve
all failures and retries; two bounded retries do not establish availability.

## Sensitivity and applicability

Vary synonyms, source-specific filters, date range, publication status, and
page cap one at a time. Compare unique studies as well as records; report
changed inclusion sets and conclusions. A conclusion that depends on one query
variant, unverified identity merge, or capped page set is fragile. Europe PMC
coverage and full-text access differ by source and license. Results are limited
by indexing delay, source scope, language, query vocabulary, missing full text,
and study applicability. This workflow does not establish comprehensive
systematic-review coverage.

## Failure detection

- Invalid JSON/XML or page discontinuity: validate structure, identifiers and
  cursor continuity before parsing; retain response and mark incomplete.
- Duplicate or conflated versions: reconcile PMID/PMCID/DOI plus title/version;
  preserve uncertain merges as separate records.
- Missing text or citation link: mark unavailable; do not infer study result
  from metadata or graph relation.
- Empty result: inspect positive control, query syntax and page completion;
  report only no matches in the searched response.
- License mismatch: inspect item-level license before excerpt or reuse; omit
  reproduction when permission is unclear.

## Source basis

Europe PMC REST API documentation describes source records, search and full-text
routes. PRISMA 2020 statement (Page et al., 2021) informs transparent search
and selection; Cochrane Handbook for Systematic Reviews of Interventions
(current edition identified at use) informs synthesis and study dependence.
These sources do not turn API retrieval into a systematic review.

For each material claim, preserve the identifier, version, text locator, and
whether evidence came from metadata, abstract, or full text. Report counts with
the observed page denominator and cutoff. Keep uncertainty due to selection,
source overlap, and the underlying study distinct. A later API snapshot may
change record metadata and should not overwrite the original receipt.
Where an API provides no explicit release date, report that it was not
reported. A capped page set must include the requested cap and the observed
completion signal or absence of one. Never compare raw record totals across
queries with different source scopes as though the denominators matched.
