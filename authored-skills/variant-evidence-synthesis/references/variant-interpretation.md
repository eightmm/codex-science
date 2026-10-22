# Variant interpretation evidence method

## Claim semantics

Keep claims allele-specific and context-bound. Use these classes and assignment rules:

- **Direct observation:** the allele or molecular phenotype was measured in a defined sample or assay. Record assembly, normalization, assay, sample context, denominator, and result.
- **Population frequency and constraint:** population frequency describes observed allele counts in specified samples and ancestry strata; preserve allele count, denominator, coverage/QC, and dataset release. Frequency can contextualize rarity and compatibility with a proposed model, but cannot by itself establish pathogenicity, penetrance, causality, or absence in underrepresented populations. Gene-level constraint summarizes depletion of a consequence class under a model; it may contextualize tolerance but cannot establish that this variant is functional or associated with this phenotype.
- **Population association:** an effect estimate links a defined allele to a phenotype in a named population and design. Require effect allele, direction, uncertainty, sample size, phenotype definition, ancestry, covariates, and multiplicity scope. Association does not establish causality.
- **Cross-cohort PheWAS:** association scans relate a variant or tagged signal to multiple phenotypes across defined cohorts. Record tested phenotype set, cohort/sample dependencies, ancestry, allele alignment, effect direction, uncertainty, and correction scope. A PheWAS result can identify phenotype associations or pleiotropy hypotheses for follow-up; correlated phenotypes, LD, multiple testing, and shared participants prevent it from proving a causal allele or mechanism.
- **Clinical assertion:** a submitter or expert panel classifies a variant for a specified condition and inheritance context. Preserve assertion, review status, criteria, date/version, submitter, and condition; assertion is evidence about the classification process, not an independent experiment or treatment recommendation.
- **Functional evidence:** an experiment tests a molecular consequence in a specified construct, cell, tissue, or organism. Record perturbation, comparator, assay validity, biological replicate unit, uncertainty, and relevance to the claimed mechanism.
- **Prediction:** a computational model estimates consequence. Record model and version, input allele/transcript, training/evaluation scope when known, score meaning, and calibration limitations. A prediction is not measured function.
- **Regulatory overlap:** an allele overlaps or is linked to a regulatory feature in a specified genome build, tissue/state, and assay. Overlap alone does not show that the variant regulates the target gene or causes phenotype.

Split claims when they concern different alleles, transcripts, conditions, populations, molecular endpoints, or inference levels. Preserve the source's original claim and separately state any synthesis inference.

## Source, release, and dependence

Prefer primary association, functional, and clinical-evidence records for result-level support. Curated resources help discover and interpret records; they may reproduce the same study or assertion. Record database/resource name, release or version, access date, exact record identifier, query, genome build, and immutable saved response or hash. For resources without stable releases, record retrieval date and exact returned record.

Build a dependency map linking reports to studies, cohorts, samples, assays, submitters, and propagated portal records. Count repeated representations of one association or clinical submission once. Overlapping biobanks or cohorts are not independent replications; if overlap is unknown, mark it unknown. Record exclusions, deduplication, and review status. Do not infer independence from different database names.

## Uncertainty and evidence status

Retain effect estimates and source-reported uncertainty, sample size, allele frequency denominator, missingness, QC, ancestry, phenotype ascertainment, and correction scope. Keep distinct statistical imprecision, allele-mapping uncertainty, LD ambiguity, phenotype heterogeneity, model uncertainty, and source-dependence uncertainty. Missing values remain `not reported`; do not reconstruct them from rounded summaries without labeling the calculation.

Report confidence per claim, conditional on allele identity, phenotype, population, transcript, and assay context. Distinguish `supported`, `replicated` (independent relevant cohorts/experiments), `suggestive`, `conflicting`, `unsupported within assessed evidence`, and `unavailable`. A database assertion can support a statement about that assertion without independently replicating the biological association. Conflicting results remain visible with candidate explanations, not averaged into a hidden score.

## Controls and sensitivity

Use allele identity controls: verify reference allele against the declared assembly and a trusted sequence record, check strand and effect-allele convention, and validate normalization with an independent implementation or source where available. For an association analysis, examine known positive controls of comparable allele frequency and phenotype class and negative/unrelated phenotype or allele controls where the source supports them. For functional work, require assay positive and vehicle/empty-vector or wild-type controls as appropriate to the design. A failed control limits or invalidates the affected lane and is recorded.

Repeat synthesis after (1) restricting to directly harmonized alleles, (2) stratifying by ancestry, (3) excluding overlapping or uncertain cohorts, (4) changing source release where available, (5) separating transcript or tissue contexts, and (6) removing predicted or indirect evidence. Direction reversal, loss of all independent support, or a claim-status change is fragile. State the driver and retain the original and sensitivity results; do not select a favorable analysis post hoc.

## Applicability domain and failure modes

Interpretation is limited to the declared genome build, allele, transcript/regulatory context, phenotype, ancestry and ascertainment, tissue/state, and evidence cutoff. LD-based association signals may not identify the causal allele; allele frequency does not establish penetrance; one tissue may not represent another; functional assays may not transfer to human physiology. Clinical use requires qualified, context-specific assessment and is outside this research workflow.

Detect common errors by checking reference/alternate allele and strand against source records; build and liftover against coordinate context; effect allele against reported direction; multiallelic normalization against original records; phenotype and ancestry against cohort methods; duplicated associations by study identifiers and estimates; and claim inflation by tracing each conclusion to direct evidence and its inference step. Flag unresolved mapping rather than silently harmonizing.

## Sources

Use the ACMG/AMP sequence-variant interpretation standards (Richards et al., 2015) as a framework for evidence categories, not as an automatic classification engine. Use ClinGen Sequence Variant Interpretation recommendations where relevant: Abou Tayoun et al. (2018) for the PVS1 loss-of-function criterion and Brnich et al. (2019) for calibrating PS3/BS3 functional evidence. STREGA (Little et al., 2009) informs reporting of genetic association studies. These sources do not make research synthesis equivalent to clinical diagnosis.
