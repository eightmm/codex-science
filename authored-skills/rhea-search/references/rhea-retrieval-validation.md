# Rhea retrieval and validation

## Retrieval and evidence boundaries

The optional `science_search_rhea` tool accepts `query` and `limit` 1–10 (default 5); returned summaries include Rhea ID, equation title, status, and URL. The public REST route is documented by Rhea. For direct search use the documented endpoint and exact parameters, including URL-encoded query, JSON format, and bounded limit. Preserve serialized request, endpoint, access time, reported release/update, response count, pagination and response hashes.

Classify claims as reaction record, participant/equation, direction, curated enzyme/EC annotation, linked protein/pathway annotation, or experimental catalysis/flux. Database records can support only the database-level claim they explicitly represent. Use `supported`, `contradicted`, `inconclusive`, or `unavailable` consistently.

## Response validation and controls

Check status, JSON shape, returned Rhea ID, equation, ChEBI IDs, coefficients, direction, curation status, and quartet links. Preserve nulls; list included and excluded candidates with reasons. A failed or truncated response is unavailable, not evidence of absence. Retry transient failures only a bounded number of times and respect service limits.

Use one known Rhea reaction and a known ChEBI participant as positive controls. Use a syntactically valid but chemically impossible participant query as a negative control. Confirm that the positive resolves to the expected identity and direction and that the negative yields an explicit no-match. A control failure blocks interpretation pending retrieval diagnosis.

## Dependencies and release controls

Record the selected Rhea release or access date, participant ChEBI IDs and state, quartet/member IDs, and relevant UniProt/EC/Reactome versions or update dates. Follow cross-references to determine whether sources represent separate evidence or propagated mappings. Keep shared source lineage explicit; do not infer independent confirmation from duplicate annotations.

For every comparison, record why each linked database was selected and whether it contributes a new evidence type or only a propagated mapping. This makes source agreement auditable without equating resource count with replication.

## Sensitivity analysis

Check the master and all direction-specific quartet members. Vary relevant organism/taxonomy filters and whether claims rely on Rhea alone, UniProt, EC, or Reactome. Keep the question fixed and document one setting change at a time. Mark fragile any result whose reaction identity, direction, inclusion/status, or annotation support changes. If a linked source or release is inaccessible, state that sensitivity was not evaluated.

## Applicability and failure detection

Database access validates records available from the selected release; it does not prove all biological reactions are cataloged or that a reaction occurs in a particular organism. Stop on unresolved participants, ambiguous direction, invalid/incomplete response, or release differences that affect the conclusion.

- Invalid identifier or wrong candidate: detect by checking ID and participant structure against the response equation.
- Direction confusion: inspect symbol and quartet member rather than equation layout.
- Propagation mistaken for independence: trace cross-reference lineage and shared source curation.
- Truncated/API failure: validate response completeness and distinguish an error from zero results.
- Release drift: record source-reported release/access date and avoid untracked mixtures.

## Sources

- Rhea REST access documentation, EMBL-EBI: endpoint and access methods; use live documentation for current request details.
- Alcántara et al., 2012, “Rhea—a manually curated resource of biochemical reactions”: participant identity and directional representation.
- Bansal et al., 2022, “Rhea, the reaction knowledgebase in 2022”: links to UniProt and other resources.
