# OpenAlex graph evidence interpretation

## Claim classes

- **Entity-resolution:** a name maps to a returned source ID. Assign only when
  returned attributes distinguish the intended entity; unresolved homonyms stay
  ambiguous.
- **Graph-descriptive:** a work/author/institution/source/topic/funder is in the
  retrieved graph with stated fields. This describes a snapshot, not all
  scholarship.
- **Metric-descriptive:** a returned count or group aggregate at retrieval time.
  State metric definition, date/window and missingness; do not infer quality.
- **Association/trend:** compare graph records under a fixed population and
  period. Confounding, coverage, field and age effects remain; causal claims
  require independent designs.
- **Synthesis:** deduplicate works and underlying studies, preserve dependency
  groups, and report conflicting records rather than averaging incompatible
  entities or outcomes.

## Source dependencies and independence

OpenAlex is a scholarly graph with linked entity types; its records and
aggregates can derive from overlapping upstream metadata. Record endpoint,
entity type, exact query/filter, selected fields, access time, page/cursor,
reported update information, and returned IDs. Preserve the actual response
and nulls. Do not claim a release/version unless the service reports it.
Resolve names before filtering and keep resolution rationale. Citation edges,
versions, duplicated works, and multiple portal records may share one source
study. Count independent studies only when underlying work/cohort identity is
established; graph edge count is not independent evidence.

## Uncertainty and controls

Carry ambiguity in names, null fields, page caps, indexing lag, metric date,
field/year mix, and any sampling or filtering choices. Positive control: resolve
a known work/author ID and check expected returned identity/field. Negative
control: query a deliberately incompatible ID/entity type or impossible filter
and confirm it is rejected or yields no eligible match. Controls check route
and parsing, not global graph completeness. Never treat null as zero.

## Sensitivity and applicability

Vary search terms, entity resolution candidate, publication window, filters,
field selection, and page cap one at a time. Compare IDs, counts and rank order;
report instability when reasonable choices change the conclusion. Citation
counts and works counts are time-dependent and field/age biased; author
disambiguation, source coverage and graph updates limit validity. OpenAlex is
not a quality measure, complete census, or causal dataset. Results apply only
to the retrieved graph and explicit filters.

## Failure detection

- Ambiguous entity: compare returned identifiers and attributes; do not choose
  by name string alone.
- Missing page or truncation: reconcile page counts and continuation metadata;
  mark incomplete.
- Null metric: preserve null as unknown and verify selected fields; never
  impute zero.
- Duplicate works/versions: compare stable IDs, DOI, title and version; group
  only verified same-work records.
- Ranking shift: rerun prespecified sensitivity variants and report rank range
  or withdraw ranking claim.

## Source basis

OpenAlex project description and API documentation define its linked scholarly
entities and query interface. The Leiden Manifesto (Hicks et al., 2015) and
DORA declaration (2012) inform responsible interpretation of bibliometrics;
they caution against using aggregate indicators as stand-alone quality
judgments. These frameworks do not validate a particular ranking or graph
snapshot.

For every comparison retain its entity IDs, metric definition, time window,
retrieval date, and filter. Report the actual denominator and unresolved
entities beside aggregates. Separate uncertainty in entity matching from
sampling or study uncertainty. Preserve the original response snapshot so a
later graph update cannot silently change the basis of a reported trend.
State whether counts refer to returned records, filtered entities, or groups.
Do not compare aggregates with different windows or entity-resolution rules
without labeling the contrast exploratory. If an API omits release identity,
record the omission instead of assigning an inferred version.
