# Cancer Genomics Evidence: evidence calibration

## Claim semantics

Use four statuses consistently. `supported` means the prespecified claim criterion is met by traceable evidence in the stated scope. `contradicted` means adequate, relevant evidence conflicts with the claim. `inconclusive` means evidence exists but remains insufficient, imprecise, heterogeneous, or unresolved. `unavailable` means the required source or observation could not be accessed or verified. Apply status to a claim and scope, not to an entire cohort or alteration.

Keep claim classes distinct:

- **Prevalence:** assign when the numerator and eligible denominator are defined for the specified cancer, stage, cohort, sample/patient unit, assay, and alteration definition. Report ascertainment and assay coverage.
- **Prognosis:** assign to an association between a biomarker and outcome in a defined population with endpoint, follow-up, treatment context, and relevant covariates reported. Do not treat an unadjusted survival split as a validated prognostic model.
- **Prediction:** assign when evidence tests whether treatment effect or response differs by biomarker status using a defined treatment and comparator or a suitable validated predictive design. A biomarker-outcome association in a treated-only cohort is not by itself predictive evidence.
- **Mechanism:** assign when functional or molecular experiments directly test a proposed biological process and connect it to the alteration. Co-occurrence or pathway annotation alone is insufficient.
- **Resistance:** assign when a defined alteration is linked to reduced response or acquired resistance under a specified therapy and experimental or clinical context; separate baseline resistance from acquired change and record competing explanations.
- **Actionability:** assign to a source-attributed interpretation tier or clinical evidence statement with disease, alteration, therapy, and evidence context specified. A database tier is a reported classification, not a patient-specific treatment recommendation.

Record criterion, directness, and evidence IDs for every claim. Preserve disagreements, missing/null results, and negative evidence with denominators and detection limits. Do not turn a portal label, mechanistic plausibility, or p-value alone into a stronger claim.

## Source dependencies and independence

Pin source name, study/cohort, release or update value as reported, query, access time, and retrieval completeness. Keep source-native gene, variant, sample, endpoint, and evidence identifiers beside normalized forms; retain genome build and every mapping step.

Trace reused samples, overlapping cohorts, linked publications, shared controls, prior versions, and records propagated between portals or review databases. Group dependent records. A CIViC, ClinVar, or other portal entry copied from a paper is a route to that evidence, not a new independent experiment. Distinguish source curation from the primary observation and record evidence lineage where available.

Treat cohort eligibility, cancer subtype/stage, sample unit, platform, assay panel, variant calling, purity, treatment, endpoint, follow-up, and source-release changes as possible explanations for disagreement. Preserve transformation history. If sample overlap or evidence lineage cannot be resolved, report it as unknown and do not count it as independent validation.

## Uncertainty and missing evidence

Carry sampling uncertainty for estimates and intervals with uncertainty from selection, tumor purity, assay sensitivity, subtype composition, stage, treatment exposure, follow-up, endpoint definitions, missing covariates, source coverage, and cohort dependence. Report numerator and denominator for each prevalence estimate and the unit that each count represents.

Keep unavailable, unqueried, filtered, null, and observed-negative evidence distinct. Do not impute absent records or interpret an omitted portal row as absence of an alteration or effect. Separate precision from bias, confounding, and applicability. State which uncertainty could change claim status and the evidence needed to reduce it.

## Controls and sanity checks

- Confirm normalized gene/variant identity, build, alteration class, sample unit, and source-native IDs against the original record.
- Reconcile eligible sample counts, numerator, denominator, exclusions, duplicate samples, and assay-tested populations; check that subgroup denominators do not exceed the source cohort.
- Use a known in-scope alteration or curated record as a positive retrieval control when the source has a documented comparator. Confirm expected cohort, assay, and evidence lineage.
- Use an unrelated gene/variant or incompatible cancer subtype as a negative identity control; it should not resolve to the target record after normalization.
- Check source coverage and expected missingness for assay panels; distinguish untested genes from tested-negative genes.
- For survival or response claims, inspect endpoint, follow-up, treatment exposure, and comparator structure before labeling prognosis or prediction.
- Recalculate simple prevalence proportions from the recorded numerator and denominator when both are available; reconcile any mismatch with the source's unit and exclusions.
- Match each control to the same source path and scope as the target query; a control retrieved from a different assay or cohort tests only that separate path.

Record each control's selection, expected and observed result, and limitations. Mark a control unavailable when there is no defensible comparator. Controls check retrieval, denominators, and interpretation; they do not establish clinical benefit.

For time-to-event evidence, retain the source's endpoint, time origin, follow-up, and censoring description; do not compare survival summaries that use incompatible definitions. For treatment-response evidence, record regimen, line, comparator, response definition, and timing relative to the genomic sample. Missing treatment or follow-up context limits the claim class rather than being filled by inference.

## Sensitivity analysis

Keep the primary cancer type, cohort, sample list, assay, alteration definition, endpoint, and claim criteria frozen. Examine documented alternatives that could change scope or status:

- subtype, stage, eligibility, patient versus specimen unit, and duplicate/longitudinal samples;
- assay panel and coverage, purity or quality filters, variant class, and alteration threshold;
- numerator/denominator rules and missingness handling;
- treatment group, comparator, endpoint, follow-up window, and covariate adjustment;
- source release, cohort overlap, and evidence-lineage grouping.

Label post hoc splits exploratory. A result is fragile when a reasonable documented choice changes status, direction, material magnitude, or applicability. Report which cohort or assay choices drive the change and qualify or downgrade the claim rather than choosing the favorable subgroup.

## Applicability domain

Conclusions apply only to the included cancer population, stage, sample unit, assay coverage, alteration definitions, treatment context, endpoints, follow-up, and source releases. Public cancer cohorts and curated portals can be selectively assembled and may omit negative studies, untested genes, or source details. Estimates from one cohort do not automatically transport to other subtypes, stages, ancestries, assays, or clinical settings.

Research synthesis does not provide patient-specific interpretation. Mutation prevalence alone does not establish efficacy. Narrow or stop a claim when identity, denominator, cohort eligibility, assay coverage, endpoint, treatment context, or evidence lineage cannot be verified. Clinical actionability requires the appropriate clinical evidence and context beyond a cross-source research table.

For source-attributed actionability, retain the source name, classification system, release/date, disease context, alteration, therapy, and evidence identifiers; later versions may change the classification.

## Common failure modes and detection

- **Sample unit or denominator mismatch:** compare patient/sample definitions, exclusions, duplicate handling, and subgroup counts with the source.
- **Assay absence read as negative:** inspect gene/panel coverage and source completeness; separate tested-negative from untested.
- **Prevalence promoted to efficacy:** check whether the evidence tests a treatment outcome rather than frequency alone.
- **Prognostic label applied to predictive evidence or vice versa:** inspect treatment/comparator structure, endpoint, follow-up, and the frozen claim class.
- **Mechanism inferred from co-occurrence:** require experiments that directly test the proposed process; keep association and annotation separate.
- **Resistance inferred from baseline prevalence:** identify treatment exposure and timing; distinguish pre-existing from acquired alteration evidence.
- **Actionability overstated:** retain the source's tier, disease and therapy scope, date, and evidence class; do not convert it into patient advice.
- **False independence from copied records:** trace publications, cohorts, samples, and portal lineage; unknown lineage stays unknown.
- **Outcome-driven subgroup selection:** compare the final splits and endpoint with the frozen contract; label unplanned analyses exploratory.

## Sources

REMARK (McShane et al. 2005) addresses reporting of tumor-marker prognostic studies. PRISMA 2020 (Page et al. 2021) addresses transparent reporting of evidence identification and selection, not the quality of an individual study. AMP/ASCO/CAP (Li et al. 2017) provides a framework for somatic variant interpretation; its classification does not itself establish benefit for a particular patient. Each source is applied only within its stated scope.
