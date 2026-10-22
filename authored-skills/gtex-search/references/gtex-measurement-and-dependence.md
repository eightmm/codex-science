# GTEx measurement, claims, and dependence

## Claim classes

Assign each claim to one class before evaluating rows:

- **Measured tissue RNA abundance:** a normalized RNA-seq abundance for a gene in a named GTEx tissue and release. Require a returned gene ID, tissue, metric, units, and release. This supports presence/relative abundance only under that release's processing and sample definition.
- **Within-release tissue comparison:** compare the same gene across named tissues only when metric, processing, release, and tissue labels match. The comparison describes sampled bulk tissues; it is not a calibrated comparison of cell-intrinsic expression.
- **eQTL association:** a reported variant-gene association in a named tissue and release. Require allele/build identity and returned effect/statistical fields. Association supports a regulatory association claim, not causal mediation, colocalization, disease mechanism, or clinical effect.
- **Unavailable or inconclusive:** identity mismatch, absent record, missing required fields, malformed response, unresolved truncation, or incompatible release/metric. No result is not an expression-absence claim.

Use the skill's consistent statuses: `supported` when the returned evidence meets the prespecified claim; `contradicted` when comparable evidence points against it; `inconclusive` when evidence is incomplete, conflicting, or threshold-sensitive; `unavailable` when the source cannot answer it. Do not convert no match to `contradicted`.

## Measurement and normalization

GTEx RNA-seq abundance is bulk-tissue transcript evidence. Record the field and unit exactly as the selected endpoint returns it; TPM is a normalized abundance unit when that endpoint provides TPM. Do not relabel ranks, z-scores, normalized expression, or eQTL statistics as TPM. Preserve zero as an observed returned value and distinguish it from null, omitted field, filtered row, or no record. Values from different releases or processing definitions are not directly interchangeable without an explicit harmonization analysis.

For every queried tissue, record the response's sample count and donor count when exposed and distinguish their meanings. A donor can contribute samples to multiple tissues; tissues and rows from one donor cohort are dependent observations. Report available sample sizes and do not treat them as independent replication. If the response lacks these counts, mark them unavailable and do not infer counts from a portal summary.

## Tissue and sample context

Retain the source tissue label and map it to a versioned anatomy ontology identifier such as UBERON only when the mapping is unambiguous. Record mapping source/version and preserve one-to-many or unresolved mappings. Bulk tissue mixes cell populations; cell composition can explain apparent tissue differences. GTEx uses postmortem donors, so postmortem interval, RNA integrity, ischemic effects, sample handling, age, sex, ancestry, and technical batch can affect measurements or comparisons. Include relevant reported covariates and exclusions; do not imply every API result supplies them.

## Source dependence and release

Pin the release/version returned by the endpoint, exact endpoint and parameters, access time, and response hash. GTEx tissue expression and eQTL analyses derive from overlapping GTEx donors, samples, assays, and processing; different tissues, visualizations, portal pages, and API routes are not independent replications. Record a shared cohort/release dependency in the evidence graph. A release change requires a new record and explicit reconciliation; never silently combine values across releases.

## Controls and sanity checks

When compatible records exist, query a commonly expressed housekeeping gene (for example, RPLP0) and a tissue-restricted marker appropriate to the selected tissue (for example, ALB for liver). Record gene IDs, tissue, release, metric, and expected pattern before inspecting the result. These are technical/context sanity checks, not universal biological truths. A failed control prompts checking gene mapping, tissue mapping, endpoint, normalization, coverage, and release; it does not authorize post hoc filtering or changing the claim threshold.

## Uncertainty and interpretation

Carry uncertainty from cohort size, bulk-cell mixture, tissue mapping, measurement normalization, missing covariates, response coverage, and eQTL statistical uncertainty. Report donor/sample denominators and the endpoint's returned uncertainty or significance fields when available. Distinguish uncertainty in a point estimate from missing information. Do not use expression magnitude alone as evidence of gene function, protein abundance, or causal effect.

## Applicability domain

GTEx is a resource for non-diseased human tissue sampled under its collection and processing protocol. It does not represent all disease states, developmental stages, rare cell populations, every population, or every environmental condition. Bulk tissue cannot resolve cell-specific expression without a suitable cell-resolved assay. A GTEx eQTL is limited to the analyzed genetic and tissue context and does not establish causal direction or trait mediation.

## Sources

- GTEx Consortium. “The GTEx Consortium atlas of genetic regulatory effects across human tissues.” *Science* (2020). Primary v8 atlas describing postmortem tissue samples, donor overlap, RNA-seq, and genetic regulatory analyses.
