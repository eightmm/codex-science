# Gene Burden Evidence: evidence calibration

## Claim semantics

Use four statuses consistently. `supported` means the prespecified claim criterion is met by traceable evidence in the stated scope. `contradicted` means adequate, relevant evidence conflicts with the claim. `inconclusive` means evidence exists but remains insufficient, imprecise, heterogeneous, or unresolved. `unavailable` means the required source or observation could not be accessed or verified. Apply status to a claim and scope, not to a study as a whole.

Keep claim classes distinct:

- **Gene-level burden association:** assign when a declared gene/transcript, phenotype, cohort, qualifying mask, model, and correction scope show an association under the frozen criterion. Report the unit, denominator, estimate, uncertainty, and correction family.
- **Direction of effect:** assign only when the model and reported estimate identify a direction for the stated allele/mask and phenotype. A variance-component test such as SKAT can test aggregate association without a single signed effect; do not infer direction from its p-value.
- **Mask or variant-class specificity:** assign only to the tested transcript, consequence classes, frequency threshold, and inclusion/exclusion rules. A result under one mask does not establish a result for another mask or every variant in the gene.
- **Replication:** assign exact replication only when gene/transcript, phenotype, mask, frequency rule, ancestry, build, estimand/model, and correction criterion align in an independent cohort. Otherwise report the specific partial or near-match.
- **Dosage or mechanism:** assign only when independent dosage or functional evidence directly tests the proposed mechanism and is linked to the burden result. Burden association alone does not identify a causal variant, disease mechanism, or dosage effect.

Record the criterion and evidence IDs for each claim. Do not turn a p-value threshold, gene-level label, or portal annotation into a claim by itself. Preserve missing p-values and null estimates; missing evidence does not establish nonsignificance.

## Source dependencies and independence

Pin source name, cohort/study identifier, release or update value as reported, query, access time, and retrieval completeness. Retain original gene/transcript and variant identifiers alongside normalized forms, genome build, and mapping decisions. Record the exact mask definition and whether frequency is cohort-specific, external, or otherwise sourced.

Trace shared participants, biobanks, controls, linked studies, reused sequencing data, and summary statistics propagated through portals or meta-analyses. Record dependency groups. A reproduced table or a second portal entry from the same study is not an independent replication.

Treat release, build, transcript annotation, variant calling, phenotype definition, ancestry, sample selection, model, and correction-family changes as potential explanations for disagreement. Keep source records and transformation history. If overlap, lineage, or mask provenance cannot be verified, mark independence or mask alignment unknown and do not count the result as confirmed replication.

## Uncertainty and missing evidence

Carry reported effect estimates and intervals with sampling uncertainty, plus uncertainty from phenotype definition, ancestry, case-control composition, variant calling, coverage, mask construction, transcript choice, model fit, correction scope, and cohort dependence. Report case and control counts, missing fields, and whether denominators reflect people, samples, or variants.

Do not impute absent p-values or effects, treat null as zero, read unavailable as negative, or infer no burden from omitted records. Distinguish imprecision from bias, confounding, and limited transportability. State which uncertainty could change the claim status and what source data or analysis would resolve it.

## Interpreting burden rows

Keep participant counts distinct from allele counts, variant counts, and carrier counts. A source may report one or several of these, and they have different denominators.
Retain the test name and model beside its estimate; do not compare p-values from different masks or models as if they measured the same effect.
When a result provides only a test statistic or p-value, report association evidence without manufacturing a signed effect or interval.
When the source omits its correction family or mask details, preserve the returned record but mark the relevant claim inconclusive until those dependencies are resolved.

## Controls and sanity checks

- Examine synonymous burden as a negative-control variant class when the assay and annotation make it interpretable. A signal may expose technical or ancestry structure; no signal is not proof that other classes are calibrated.
- Inspect a Q-Q plot or the source's reported calibration diagnostics for test-statistic inflation. Interpret inflation in context: population structure, relatedness, batch effects, model misspecification, and true polygenicity can contribute.
- Check case-control matching or adjustment for ancestry, age/sex where relevant, recruitment, sequencing/calling pipeline, and technical batch. Confirm group counts and covariate balance rather than relying on a matching label.
- Where available, use an established in-scope positive-control gene/phenotype and an unrelated negative-control phenotype or gene under the same pipeline; document expected and observed results.
- Reconcile tested genes, variants, masks, and exclusions against reported denominators and inspect missing estimates, duplicate samples, and allele/build mismatches.

Controls evaluate assay, cohort, and model behavior; they do not establish disease causality. Record control availability and any reason a proposed control is not interpretable.

Read a synonymous-control signal with its annotation and assay context: synonymous variants can still reflect splicing effects, linkage, or technical structure, so they are not guaranteed neutral. Likewise, a calibrated global statistic does not rule out gene-specific confounding. Report these checks as diagnostics alongside, not replacements for, matching and model review.

## Sensitivity analysis

Preserve the primary mask and analysis contract. Vary documented alternatives that can affect burden membership or inference:

- mask definition, transcript, consequence class, and inclusion of predicted damaging variants;
- minor-allele-frequency threshold and whether frequencies come from the cohort or an external reference;
- ancestry strata and reasonable ancestry adjustment, without treating small strata as definitive;
- phenotype definition, case/control eligibility, covariates, relatedness handling, and analysis model;
- cohort inclusion, variant-calling release, and multiple-testing family.

Label post hoc variants exploratory. A result is fragile when a reasonable alternative changes status, direction where estimable, material effect size, or applicability. Report which variants and participants drive the change; qualify or downgrade instead of selecting the favorable mask or threshold.

When an ancestry stratum is too small for stable estimation, label the estimate imprecise or unavailable rather than treating a non-significant result as evidence of no effect. Keep stratum-specific frequencies and masks explicit; pooled results may obscure ancestry-specific variant membership.

## Applicability domain

Conclusions apply to the represented phenotype definition, cohort ascertainment, ancestry, sequencing/calling platform, transcript annotation, mask, frequency threshold, model, and release. Rare-variant tests can be underpowered for small cohorts, ancestry-specific variants, or narrow phenotypes. A null result does not exclude effects outside the tested mask, transcript, population, or detectable frequency range.

Portal summaries may omit masks, nonsignificant rows, sample overlap, or calibration details. Stop or narrow the claim when gene identity, phenotype, mask, cohort denominator, model, or result provenance cannot be verified. Burden evidence alone is not proof of causality, mechanism, or dosage.

## Common failure modes and detection

- **Mask inferred from a generic label:** obtain the source definition for transcript, consequence, frequency, and filters; otherwise mark alignment unknown.
- **Direction inferred from a nondirectional test:** inspect model and signed effect fields; report association without direction when none is estimable.
- **Replication claimed across different tests:** compare gene, phenotype, ancestry, mask, threshold, model, correction, and cohort lineage against the frozen criteria.
- **Technical or ancestry confounding:** review matching/covariate balance, calibration plots, synonymous controls, batch and calling metadata.
- **Missing result treated as a null:** inspect query filters, completeness, denominators, omitted estimates, and source release.
- **Inflated evidence from dependent cohorts:** trace participants, biobanks, controls, and propagated summary rows; count each dependency group once.
- **Mechanism inferred from association:** check for direct dosage or functional evidence and keep it separate from burden statistics.

## Sources

STREGA (Little et al. 2009) addresses reporting of genetic association studies. SKAT (Wu et al. 2011) and SKAT-O (Lee et al. 2012) describe named rare-variant association methods; SKAT's variance-component test does not by itself supply a single signed gene effect. These sources do not define a universal mask, frequency threshold, or replication rule.
