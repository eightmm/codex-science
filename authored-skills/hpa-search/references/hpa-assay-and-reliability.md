# HPA assay-specific evidence and reliability

## Claim classes

Classify each claim before interpreting a portal result:

- **RNA abundance:** transcript abundance in a named tissue or cell context, using the exact returned metric and release. It supports RNA measurement only; it is not protein abundance.
- **Protein detection:** antibody-based protein staining or other explicitly identified protein evidence in a named context. Report the source's intensity/quantity category and reliability annotation. It supports detection under the reported assay, not protein function or calibrated concentration.
- **Localization:** a reported subcellular or tissue localization pattern for the stated cell/tissue and evidence source. It is an observation/annotation, not proof of biological role.
- **Reliability:** the HPA's reliability assessment for the associated antibody/evidence. It qualifies that evidence; it is not an independent expression measurement.
- **Unavailable or inconclusive:** unresolved identity, missing assay context, absent record, incomplete response, or conflicting evidence. An empty result is not evidence of absent expression.

Use the same status vocabulary as the skill: `supported`, `contradicted`, `inconclusive`, or `unavailable`. `Supported` applies only to the narrowly stated assay-specific claim; `contradicted` requires comparable evidence that opposes it. Missing or unmeasured evidence is `unavailable`, not `contradicted`.

## Assays and normalization

HPA includes RNA and protein evidence derived from different assays and source sets. Preserve whether a returned RNA value is TPM, nTPM, a rank, a categorical call, or another field; only call it by the unit/definition exposed for that record. Do not compare raw or normalized values across atlas releases or assay types as if they shared a scale. Protein evidence may be semi-quantitative and dependent on antibody, tissue preparation, staining, and scoring. Record antibody identifiers and the portal reliability score/category exactly when returned; do not collapse categories or invent a score cutoff.

Record tissue and cell label, assay, release, response field, unit/normalization, and any sample counts that the selected endpoint actually exposes. Do not infer counts from aggregate atlas coverage. Distinguish no match, null, omitted annotation, filtered row, and returned zero/call. A localization annotation may derive from a different evidence stream than abundance; preserve the provenance for each.

## Gene and anatomy identity

Resolve to the returned Ensembl gene identifier and retain the symbol mapping. Keep ambiguous mappings explicit. Preserve the source label and map to UBERON for anatomy or CL for cell type only when unambiguous; record ontology release and mapping source. Do not equate a tissue sample with a purified cell population. If ontology mapping is one-to-many or unresolved, report the original label and limit cross-source comparison.

## Source dependence and release pinning

Pin HPA release/version from the response or downloaded dataset metadata, endpoint and serialized parameters, access date, and response hash. HPA RNA may incorporate measurements or resources overlapping external atlases such as GTEx; HPA protein/localization evidence may share antibodies, samples, or atlas aggregation across pages. Portal visualizations and API routes are not independent confirmations of the underlying record. Track reused data, antibodies, datasets, and releases as dependencies. Do not count RNA and protein from the same integrated page as replicate measurements of one modality.

## Antibody reliability and uncertainty

Report the HPA reliability score/category and relevant antibody identity with the protein result. Reliability is an evidence-quality annotation; it does not mean a protein level is exact or universally valid across tissues. Carry uncertainty from antibody specificity, staining interpretation, tissue coverage, cell mixture, assay sensitivity, RNA normalization, ontology mapping, missing annotations, and cross-atlas dependence. Where antibody validations disagree or reliability is uncertain, report the disagreement and narrow or qualify the claim rather than averaging it away.

## Applicability domain

HPA records describe human samples and assays represented by the cited release. They do not cover every tissue, developmental state, disease context, cell subtype, or condition. IHC and other antibody methods have epitope, specificity, and tissue-preparation limitations; bulk RNA misses cell composition and cannot substitute for protein evidence. Do not transfer protein localization across cell types or infer function, disease effect, or clinical relevance from expression alone.

## Sources

- Uhlén et al. “Tissue-based map of the human proteome.” *Science* (2015). Primary tissue atlas describing RNA-seq and antibody-based protein profiling.
- Thul et al. “A subcellular map of the human proteome.” *Science* (2017). Describes subcellular localization evidence and its reliability scoring.
- Uhlén et al. “A proposal for validation of antibodies.” *Nature Methods* (2016). Describes the antibody validation strategies behind enhanced-validation evidence.
