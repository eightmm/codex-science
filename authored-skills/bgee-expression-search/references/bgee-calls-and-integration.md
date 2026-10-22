# Bgee calls, conditions, and evidence integration

## Claim classes

Assign claims before interpreting the selected records:

- **Observed present call:** Bgee reports expression evidence for the gene in the named condition. State species, anatomy, developmental stage, evidence type, call quality, and release. This is evidence of measured expression in the represented samples/condition, not a universal statement about all samples.
- **Observed absent call:** Bgee reports an absence call for the named gene-condition under its data and call procedure. It supports absence under that procedure and evidence coverage only; it does not prove biological non-expression.
- **Propagated call:** a call has been transferred along an anatomy or developmental ontology. Identify it as propagated and preserve the target condition and source granularity. It is not a direct observation in the target condition.
- **Rank or score:** a relative or quantitative summary as defined by the source release. Preserve the returned field and comparison domain; do not relabel it as TPM or absolute concentration.
- **Unavailable or inconclusive:** no matching call, missing annotation, insufficient coverage, malformed or truncated response, ambiguous identity, or conflicting evidence. No record is not an absent call.

Use `supported`, `contradicted`, `inconclusive`, and `unavailable` consistently. A positive call can support expression in that condition. A negative/absent call only supports the bounded statement that Bgee assigned an absent call there. It cannot refute expression in another sample, stage, anatomy, species, or assay.

## Units, calls, and condition integration

Bgee integrates expression evidence across experiments and data types to provide gene-condition calls and associated quality/confidence information; release-specific records may also expose ranks, expression scores, or corrected statistical fields. Record only fields actually supplied and their source-defined meaning. Do not map a confidence label to a probability unless the release explicitly defines that scale. Do not treat an expression rank as an abundance unit or compare ranks outside their documented universe.

A condition is a combination of biological context, including anatomy and developmental stage. Preserve the exact condition and source ontology terms. Record evidence type, call quality, directly observed versus propagated state, and supporting/contradicting experiment counts or identifiers when the response exposes them. If counts or identifiers are absent, record unavailable rather than infer them.

## Ontology mapping

Retain original anatomy and stage labels. Map anatomy through UBERON and cell type through CL when the term mapping is supported; retain ontology IDs, ontology release, mapping source, and any one-to-many ambiguity. A propagated call can reflect ontology ancestor/descendant integration and different source granularity. Do not silently equate parent tissue with a specific child region, or anatomical tissue with a purified cell type.

## Source dependence and release

Pin the Bgee release reported in the response or dataset metadata, endpoint, serialized parameters, access time, and response hash. Integrated calls can summarize multiple experiments or data types, and propagated calls can reuse the same underlying observations across related conditions. Record these source experiment and ontology dependencies. Multiple conditions, downloaded tables, API routes, and portal displays derived from the same underlying experiments are not independent replications. Do not count propagated records as new experiments.

## Uncertainty and controls

Carry uncertainty from experiment coverage, heterogeneous assays, call quality, sample design, ontology granularity, propagation, annotation gaps, gene mapping, and release. Preserve positive and negative support where available; do not collapse conflicting evidence to one opaque score. Counts are not independent sample sizes unless the source defines their unit and independence.

For a sanity check, query a known broadly expressed housekeeping gene such as RPLP0 and a known tissue-restricted gene suitable for the selected species and anatomy. Record identifier, condition, release, evidence type, and expected pattern before looking at the target. The expected pattern is a diagnostic aid, not a universal law. If comparable controls are absent, record that limitation.

## Applicability domain

Bgee covers the species, anatomical terms, developmental stages, experiments, and evidence types represented in a given release. It is not a comprehensive census of every gene in every condition. A present call is bounded to its evidence; an absent call depends on assay sensitivity, sampled conditions, and integration rules. It does not establish protein abundance, localization, gene function, disease expression, or causal effect.

## Sources

- Bastian et al. “The Bgee suite: integrated curated expression atlas and comparative transcriptomics in animals.” *Nucleic Acids Research* (2021). Describes integration, present/absent calls, ranks/scores, and ontology-based propagation.
- Bgee expression call and download documentation (accessed with the selected release). Defines release-specific call quality and download fields; consult it rather than assuming a field schema.
