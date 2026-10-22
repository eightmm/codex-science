# Reactome evidence interpretation

## Claim classes and assignment

Classify each statement before interpreting a response. A **curated-record**
claim says Reactome records a pathway, reaction, or participant in a named
release; assign it only when the stable record and release are returned. It is
a claim about the database, not necessarily about activity in a sample. An
**orthology-inferred-event** claim says Reactome transfers an event from a
reference species using orthology; use it only when the returned event is
explicitly marked as inferred and retain the reference organism. It is a
prediction for the target species. An **enrichment-association** claim says a
submitted set is over-represented relative to a defined universe under the
reported test and correction; assign it only with input, mapping, universe,
release, and multiple-testing details. A **mechanistic-causation** claim says
an intervention or temporal process causes a biological change; Reactome
membership or enrichment alone cannot support it.

Use status `supported` when the retrieved record supports the narrowly stated
database or statistical claim, `contradicted` when a complete query returns
an incompatible record for that claim, `inconclusive` when evidence or model
choices do not decide it, and `unavailable` when retrieval is failed or
incomplete. No returned row is not a biological negative.

## Source dependence and release identity

Pin the response-reported Reactome release or update date and record the
ContentService or AnalysisService endpoint, query serialization, species,
access time, token, input IDs, and pagination/completion state. A missing
release field remains unknown; do not infer it from the current website.
Analysis tokens and mappings are release-scoped observations, not reusable
proof of a stable biological result.

Reactome pathways organize reactions, so participant and pathway rows can be
propagated or inherited through the hierarchy. Count a gene found at an
ancestor and its descendant once in a set-level claim; they are not independent
observations. Orthology transfer also links records across species and is not
independent support from a second experiment. If another source reuses
Reactome-derived records, record that shared provenance before describing
replication.

## Uncertainty and controls

Carry uncertainty from identifier mapping, unmapped list members, background
choice, pathway hierarchy, inferred status, release, and query completeness.
Report submitted, mapped, and tested counts separately. Do not interpret a
server-reported p-value without naming the test and correction fields actually
returned; if the universe or correction is absent, mark the enrichment claim
inconclusive.

For a positive control, include a well-characterized pathway member expected
to map in the chosen species and confirm that its returned stable ID and
membership are sensible. For a negative sanity control, query a random gene
set of similar size drawn from the same eligible universe; retain its result
and avoid treating a single null set as proof of calibration. Record each
control's source, sampling rule, and result.

## Sensitivity and applicability

Recompute enrichment across defensible background universes (for example,
the assayed genes versus all genes eligible for the experiment), the
prespecified evidence-code/record filters when available, and nearby
predeclared score or inclusion thresholds. Record a result as fragile when
the leading pathway, corrected significance classification, direction of the
reported interpretation, or claim status changes under a defensible choice.
Do not select the most favorable setting after seeing results.

Reactome is a curated knowledgebase, not a complete assay of every organism,
cell type, perturbation, or time point. Enrichment is biased by pathway
coverage, study intensity, gene length/annotation opportunity, identifier
mapping, and the chosen universe. Inferred events may be absent or wrong in a
target taxon. Pathway membership does not establish molecular direction,
flux, activation, or causal effect.

## Failure modes and detection

- **Wrong species or namespace:** inspect returned taxon and mapping table;
  stop if alternatives change the interpretation.
- **Background mismatch:** compare the eligible measured universe with the
  submitted background and rerun defensible alternatives.
- **Hierarchy double-counting:** inspect parent/child relationships and dedupe
  genes before treating hits as independent.
- **Orthology mistaken for observation:** inspect the returned inferred-event
  annotation and reference species; downgrade to prediction.
- **Release drift:** compare release metadata and stable IDs across saved
  receipts; do not merge incompatible snapshots silently.
- **Truncation or token failure:** validate page state and token retrieval;
  mark unavailable and retain partial records without interpreting missing rows.
- **Annotation bias or circular evidence:** compare coverage across the input
  set and trace whether the hypothesis or selection used Reactome itself; label
  the result hypothesis-generating when evidence is reused.

## Sources

- Croft et al. (2014), “The Reactome pathway knowledgebase,” describes the
  curated pathway resource and its computationally inferred human reactions.
- Benjamini and Hochberg (1995), “Controlling the False Discovery Rate,”
  supports false-discovery-rate correction as a multiple-testing procedure.
- Gene Ontology Consortium (2021), “The Gene Ontology resource: enriching a
  GOld mine,” describes ontology annotation and evidence distinctions; it does
  not validate Reactome-specific records.
