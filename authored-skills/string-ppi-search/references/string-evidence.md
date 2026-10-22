# STRING association evidence

## Claim classes and assignment

An **integrated-functional-association** claim states that STRING reports an
edge with a confidence score at a pinned version and threshold. It concerns
functional association, which can include indirect relationships. A
**channel-specific** claim reports only the evidence channel and score actually
returned: experiments, curated databases, text mining, co-expression,
neighborhood, fusion, co-occurrence, or another available channel. A
**predicted-association** claim is an inference based on computational or
transferred evidence, not a direct observation in the target assay. A
**physical-interaction** claim requires an appropriate experimental record and
assay context; an integrated or channel score alone does not establish direct
binding. A **causal-mechanism** claim requires intervention or temporal evidence
outside a STRING edge. An **enrichment-association** is over-representation in
a named input set relative to a defensible universe and reported correction.

Assign `supported` only to the narrow claim matching the returned evidence and
release. Use `contradicted` for an incompatible result from a complete query,
`inconclusive` when channel, context, mapping, or threshold leaves the claim
undecided, and `unavailable` for failed or incomplete retrieval. Absence of an
edge is not evidence of no biological relationship.

## Channel and source dependence

Pin STRING version/release when reported, taxon, endpoint, exact parameters,
input identifiers, access time, threshold, pagination, and completion state.
Keep channel scores separate from the combined score. The integrated score
combines evidence for a functional association; it is neither a calibrated
posterior probability of physical binding nor a measurement in the user's
condition.

Channels are not independent replications. Experimental and database channels
may share underlying publications or curated records; text mining can surface
the same literature that supplied other records; co-expression can reflect
shared datasets. Orthology transfer and other prediction channels reuse
external assumptions and training data. Record known shared sources and avoid
counting the integrated score plus its constituent channels as separate
evidence. Repeated protein pairs from the same source remain one dependency
cluster unless independence is established.

## Uncertainty and controls

Carry uncertainty from protein mapping, taxon, version, threshold, missing
channels, evidence provenance, assay context, network truncation, and
enrichment universe. Distinguish score scale from probability and preserve
returned values without rescaling or inventing missing fields.

For a positive control, query a well-characterized partner in the same taxon
with known evidence relevant to the requested channel; verify its ID, edge, and
channel record. For a negative sanity control, query a random same-size protein
set from the eligible universe and record the sampling rule. Controls check
query behavior and background plausibility; they do not calibrate a universal
false-positive rate. Record failed controls explicitly.

## Enrichment and sensitivity

For functional enrichment, record the submitted and mapped set, eligible
background, counts, test and multiple-testing fields returned, release, and
selected terms. A background of all proteins may be inappropriate when only a
subset was measurable or queryable. Annotation/study bias favors well-studied
proteins, and multiple testing must be reported using the server's fields or
another explicitly justified procedure.

Vary prespecified `required_score` cutoffs and compare channel-specific
filters (for example, experimental/database evidence versus text mining or
co-expression) when available. Also compare defensible enrichment backgrounds.
Call a result fragile when the leading partner/term, corrected significance
classification, evidence class, or claim status changes under a defensible
setting. Do not choose a cutoff after observing which one supports the desired
claim.

## Applicability and failure modes

STRING is a knowledgebase for functional associations, not a complete map of
physical binding in every tissue, cell type, perturbation, or time point. A
network can miss context-specific interactions and overrepresent well-studied
genes. Species transfer and predictions may not hold for the target organism.
Scores do not establish direction, stoichiometry, cellular colocalization, or
causality.

- **Mapping ambiguity:** inspect canonical IDs, taxon, and alternatives; stop
  when they change the network.
- **Combined score read as binding probability:** check the claim wording and
  preserve integrated functional-association semantics.
- **Channel double counting:** inspect source overlap and distinguish evidence
  channels from independent observations.
- **Literature circularity:** check whether the hypothesis or candidate list
  was selected using text mining or the same publications; label reused
  evidence and avoid confirmatory language.
- **Background/study bias:** compare eligible background and random-set
  control; report well-studied-protein bias as a limitation.
- **Threshold fragility:** recompute at prespecified nearby cutoffs and channel
  filters; downgrade if claim class/status changes.
- **Truncated response or version drift:** validate count/page state and release;
  mark unavailable or keep snapshots separate.

## Sources

- Szklarczyk et al. (2023), “The STRING database in 2023: protein-protein
  association networks and functional enrichment analyses for any sequenced
  genome of interest,” describes association channels, integrated confidence,
  and functional enrichment.
- Benjamini and Hochberg (1995), “Controlling the False Discovery Rate,”
  provides a multiple-testing correction framework; it does not validate any
  STRING score or biological interpretation.
- Gene Ontology Consortium (2021), “The Gene Ontology resource: enriching a
  GOld mine,” describes annotation and evidence distinctions relevant to
  functional enrichment, not STRING's channel calibration.
