# QuickGO annotation and ontology evidence

## Claim classes and evidence-code assignment

An **annotation-record** claim says a pinned QuickGO/GO release contains a
gene-product-to-term assertion; require the returned annotation and its
accession, taxon, aspect, evidence code, qualifier, reference, and assigned-by
fields when available. A **curated-experimental** claim uses an experimental
evidence code and is still limited to the experiment, gene product, and
assertion recorded. An **IEA-inferred** claim uses Inferred from Electronic
Annotation, corresponding to ECO:0000501 and its descendants, and must be
labeled computationally assigned; do not report it as experimentally validated.
Other non-IEA codes retain their exact code and
source and must not be collapsed into a generic “experimental” label without
checking their defined evidence meaning. A **propagated-ancestor** claim is a
logical consequence of an annotation and ontology relation under the
true-path rule, not a second independent source assertion. A **functional-
association** summarizes annotations or a term-associated gene set. A
**causal-mechanism** or condition-specific phenotype claim needs evidence
beyond ontology membership.

Use `supported` only for the scoped database assertion or association actually
returned; `contradicted` only for a complete, directly incompatible result;
`inconclusive` when evidence class, relation, or context does not decide the
claim; and `unavailable` for failed or incomplete retrieval. A missing
annotation is not a negative biological result.

## Ontology propagation and dependence

Pin the response-reported GO/QuickGO release, ontology relation, taxon,
endpoint, exact filters, page state, access time, and input IDs. Keep the
original annotation accession separate from any derived ancestor term.
For each propagated term, record the source annotation and relation path.
The GO true-path rule propagates annotation along applicable ontology
relations; propagation does not multiply the experimental evidence or create
independent support. Respect relation and aspect semantics rather than
traversing all edges as interchangeable.

Annotations can share a publication, experiment, curator assertion, or
electronic pipeline. Multiple terms on one gene product may be related by
ontology ancestry; multiple genes may come from the same assay or study.
Count unique source assertions and evidence lineages, not annotation rows, as
the units of support. A query filtered to IEA and a query without that filter
are overlapping views, not independent replications.

## Uncertainty and controls

Keep mapping, taxon, evidence code, qualifier, reference, assigned-by source,
ontology release, relation traversal, and page completeness explicit. Missing
fields remain unknown. Separate experimental and IEA counts, each with its
gene-product denominator.

For a positive retrieval control, choose a well-annotated gene product known
to carry the selected term and confirm its accession, taxon, aspect, and evidence
class. For a negative retrieval check, query an obsolete or nonexistent GO ID
and verify that it is reported as such; a failure can expose stale-ID handling
or an incomplete response.

## Sensitivity and applicability

Repeat the summary with IEA excluded and included, with the chosen experimental
evidence-code groups separated, and across predeclared qualifiers or relation
choices where relevant. For enrichment-oriented uses, vary the eligible
background (assayed gene products versus all eligible annotated products) and
report multiple-testing correction and tested universe. Call the conclusion
fragile if term ranking, corrected significance category, claim class, or
status changes under a defensible filter or universe. Do not choose filters
after seeing the preferred result.

GO coverage varies by species, gene product, research attention, and evidence
pipeline. Well-studied genes carry more annotations; annotation frequency is
not function prevalence. IEA coverage can be broad but inherits electronic
mapping assumptions. An annotation may not apply to every tissue, stage,
condition, or isoform. GO terms and ontology relations are not a causal model
or a complete mechanistic pathway.

## Failure modes and detection

- **IEA presented as experimental:** inspect exact evidence code and report
  class; downgrade or correct the claim.
- **Propagated row counted twice:** trace ancestor to source annotation and
  relation path; count the source assertion once.
- **Wrong taxon or identifier:** validate accession mapping and taxon on every
  page; stop when alternatives change interpretation.
- **Qualifier/relation ignored:** inspect qualifier and ontology edge type.
  `NOT` annotations are not positive evidence; their propagation applies to
  descendants, not ancestors.
- **Study/annotation bias:** report well-studied-gene bias and compare evidence
  source coverage across the selected gene products.
- **Circular selection:** determine whether genes or terms were selected from
  the same GO release/query; treat resulting support as descriptive rather
  than independent confirmation.
- **Incomplete pagination or release drift:** validate page completion and
  release; mark unavailable or keep snapshots separate.
- **Filter sensitivity:** repeat the prespecified evidence-code, qualifier, and
  relation alternatives;
  downgrade when claim class or status changes.

## Sources

- Gene Ontology Consortium (2021), “The Gene Ontology resource: enriching a
  GOld mine,” describes GO annotations, evidence codes, ontology structure,
  and annotation propagation; it does not make each annotation causal evidence.
- Gene Ontology Consortium (2004), “The Gene Ontology (GO) database and
  informatics resource,” describes the ontology and annotation framework.
- Benjamini and Hochberg (1995), “Controlling the False Discovery Rate,”
  supports false-discovery-rate correction for enrichment multiple testing.
