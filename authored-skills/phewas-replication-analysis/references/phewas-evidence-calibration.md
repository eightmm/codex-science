# PheWAS Replication Analysis: evidence calibration

## Claim semantics

Use four statuses consistently. `supported` means the prespecified claim criterion is met by traceable evidence in the stated scope. `contradicted` means adequate, relevant evidence conflicts with the claim. `inconclusive` means evidence exists but remains insufficient, imprecise, heterogeneous, or unresolved. `unavailable` means the required source or observation could not be accessed or verified. Apply status to a claim and scope, not to an entire study.

Keep claim classes distinct:

- **Cross-phenotype association:** assign when the queried variant is associated with a named phenotype under the source's model and the prespecified evidence cutoff; retain effect allele, effect estimate, uncertainty, and tested phenotype scope.
- **Replication:** assign exact replication only when variant/build/allele, phenotype definition, estimand, analysis direction, and prespecified comparison criteria align in an independent cohort. A mapped or broader phenotype supports only a labeled near-match.
- **Pleiotropy versus linkage:** a set of phenotype associations may be described as a multi-phenotype pattern. Do not label it biological pleiotropy or one shared causal signal from PheWAS associations alone; distinguish correlated phenotypes and linked variants, and require suitable conditional, fine-mapping, or colocalization evidence for stronger shared-signal claims.
- **Multiple-testing context:** assign significance only against the declared scan or prespecified family and its correction/cutoff. Record the tested phenotype count or source-defined testing scope; a nominal p-value or portal highlight alone does not satisfy this class.

Record each criterion and source evidence ID. Association is not causal evidence or clinical guidance. Preserve null and nonsignificant results with denominators and detection limits. Filtered, unavailable, or unqueried records do not establish absence. Do not meta-analyze incompatible phenotypes or unharmonized effects.

## Source dependencies and independence

Pin source name, cohort/study identifier, release or update value as reported, query, access time, and retrieval completeness. Preserve original variant and phenotype identifiers beside normalized forms and record the build and mapping chain.

Trace shared participants, biobanks, control groups, linked studies, reused datasets, and portal records copied from primary studies. Group dependent records and count a cohort or propagated record once when judging independent replication. A portal mirror is a retrieval route, not independent confirmation.

Treat changes in source release, genome build, allele coding, phenotype code, cohort eligibility, ancestry, and covariate model as possible sources of disagreement. Keep records and transformation history so another analyst can reproduce harmonization. If lineage or overlap is unclear, report independence as unknown and do not count it as confirmed independent replication.

## Uncertainty and missing evidence

Carry reported effect uncertainty and sampling precision alongside uncertainty from phenotype mapping, allele harmonization, ancestry, ascertainment, coding, model choice, source coverage, and cohort dependence. State denominators, missing fields, and the query's result coverage.

Do not impute unreported fields, treat null as zero, interpret unavailable as negative, or infer no association from a filtered result set. Separate imprecision from bias, heterogeneity, and transportability. Name the unresolved uncertainty that could change status and the evidence needed to resolve it.

## Controls and sanity checks

- Use an in-scope variant/phenotype positive retrieval control with a known result in the same source and query path when one is available. Confirm expected identity, returned record, effect allele, and phenotype code.
- Use an unrelated or incompatible variant/phenotype negative identity control. It should not resolve to the target record after normalization or mapping.
- Reconcile returned and excluded record counts with source totals where available; inspect pagination, filters, null fields, and denominators.
- Check that the declared multiple-testing family covers the queried phenotype set and that replicated records have the expected cohort identity.

Record each control's selection, expected result, observed result, and limitations. If a defensible control is unavailable, record that gap. Controls test retrieval and interpretation, not biological truth.

## Sensitivity analysis

Keep the primary phenotype family, cutoff, and replication rule frozen before comparison. Vary only documented alternatives that could change interpretation:

- phenotype mapping granularity and inclusion of related codes;
- correction family and evidence threshold;
- ancestry, cohort inclusion, or known overlap handling;
- build, allele normalization, and source release;
- effect model, covariates, or reported endpoint when comparable alternatives exist.

Label post hoc alternatives exploratory. A result is fragile when a reasonable prespecified alternative changes status, effect direction, material magnitude, or applicability. Report the change and qualify or downgrade the claim rather than selecting the favorable mapping or threshold.

## Applicability domain

Apply conclusions only to the source populations, ancestry composition, phenotype coding, variant representation, analysis model, and release actually queried. Phenome-wide sources may omit nonsignificant results, suppress fields, use curated phenotype subsets, or expose different cohort coverage. A result missing from such a source cannot be generalized to absence of association.

Cross-population transport, low-frequency variants, sparse phenotypes, underpowered null results, and claims about causality or clinical use require evidence beyond a cross-source association table. Stop or narrow the claim when identity, cohort eligibility, denominator, phenotype meaning, or source lineage cannot be verified.

For each negative or absent result, retain the source's tested phenotype scope, eligibility criteria, and coverage. Distinguish an explicit null estimate from a phenotype omitted by filtering or unavailable through the interface. Report whether the source could detect effects of the size relevant to the claim; do not treat lack of power as evidence of no association.

For directional comparisons, use the same effect allele and compatible estimand. Record when an effect estimate is unavailable or a phenotype mapping prevents comparison. Do not infer consistent direction from significance labels alone, and do not use a single directional near-match to claim exact replication.

Interpret clusters of correlated phenotype codes as a pattern requiring review, not as independent confirmations. Record whether each phenotype was planned, mapped after retrieval, or selected by a significance filter. When the source exposes only selected associations, state that the evidence set cannot characterize the full phenotype-wide distribution.

Keep nominal and corrected evidence separate in the report. Name the source's correction, threshold, or stated absence of correction; do not substitute a familiar cutoff when the source does not provide one.

## Common failure modes and detection

- **Variant identity error:** compare build, REF/ALT, effect allele, retained source IDs, and mapping chain; leave unresolved mappings unharmonized.
- **Phenotype overmapping:** inspect original codes and definitions against the frozen map; report a near-match instead of exact replication.
- **False replication from overlap or mirrors:** trace cohort/sample lineage and dependency groups; unknown lineage stays unknown.
- **Missing treated as negative:** inspect query scope, completeness, pagination, filters, nulls, and denominators.
- **Selective significance:** compare returned records with source coverage and the full declared testing family; do not read omitted results as null.
- **Pleiotropy overclaim:** distinguish correlated phenotypes and linked loci; require appropriate shared-signal evidence for causal interpretation.
- **Outcome-driven harmonization:** compare the final map, cutoff, and replication rule with the frozen contract; label later alternatives exploratory.

## Reporting comparison outcomes

For each phenotype comparison, retain the source code and human-readable concept, cohort dependency, effect allele, estimate and uncertainty, correction context, and status. Name whether the row is exact replication, a directional near-match, a heterogeneous comparison, or unassessed; keep those labels separate from the four evidence statuses.

## Sources

Denny et al. 2010 describes a phenome-wide scan framework. STREGA (Little et al. 2009) addresses reporting of genetic association studies, and the NCI-NHGRI Working Group on Replication in Association Studies (Chanock et al. 2007) sets out replication criteria for genotype-phenotype associations. These sources support transparent scope and reporting; they do not define a universal PheWAS cutoff or prove pleiotropy.
