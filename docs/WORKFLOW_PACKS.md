# Workflow packs

A workflow pack is a fixed-stage procedure with frozen rules, a bundle of
inputs and a validator that recomputes the result and refuses anything the
rules do not allow. Each pack lives in `authored-skills/workflow-*`, ships
synthetic example bundles under `examples/`, and has a validator in `scripts/`.
The packs check arithmetic, identity and claim wording on supplied data; they do
not turn a synthetic fixture into a scientific or clinical result, and their
claim gates refuse conclusions the data cannot support.

Run a validator from the repository root with `python3 -I scripts/<validator>
<bundle>`. Newer packs take the `pack.json` of an example bundle (for example
`examples/workflow-cfu-plate-counts/pack.json`); older packs take the inputs
described in their example README or `--help`. Use `--help` first when unsure.

**Stages.** A pack freezes its rules before reading outcome data, validates input
identity, computes with the standard library, bounds the claims and hands off to
independent review. A claim that cites unavailable evidence is itself
`unavailable`, and `replicated` needs at least two independent studies.

**Refusals.** Newer validators print JSON on stdout for an accepted bundle and a
JSON refusal on stderr with exit 2, using the key `finding` and a `code:` prefix.
Older validators and a few newer ones differ in the refusal channel or key (for
example `error` instead of `finding`); read the individual validator before
scripting against it.

## Study planning and allocation

| Skill | Checks | Validator | Example |
| --- | --- | --- | --- |
| `workflow-experiment-design` | Conduct a fixed six-stage preregistered experiment-design procedure for lab or computational studies, from question and independent-unit power planning through randomisation, frozen analysis, controls and independent review handoff. | `scripts/validate_experiment_design_pack.py` | `examples/workflow-experiment-design/` |
| `workflow-sample-size-power` | Check frozen sample sizes, detectable effects, multiplicity and attrition for planned two-group continuous or binary laboratory and preclinical outcomes; exclude clinical trial design and observed-power arguments. | `scripts/validate_sample_size_power_pack.py` | `examples/workflow-sample-size-power/` |
| `workflow-randomization-audit` | Check seeded allocation of synthetic laboratory or preclinical units to experimental arms, including frozen rules, block and stratum identities, and baseline balance; use for offline arithmetic checks, never study validity. | `scripts/validate_randomization_audit_pack.py` | `examples/workflow-randomization-audit/` |

## Assay and instrument QC

| Skill | Checks | Validator | Example |
| --- | --- | --- | --- |
| `workflow-hts-plate-qc` | Check supplied plate-well screening signals against frozen control layouts, Z-prime, SSMD, positional drift and replicate-agreed robust-z hit rules. | `scripts/validate_hts_plate_qc_pack.py` | `examples/workflow-hts-plate-qc/` |
| `workflow-calibration-lod` | Check supplied synthetic assay standards and blanks with frozen linear calibration, back-calculated deviations, explicit refits and detection or quantification limits. | `scripts/validate_calibration_lod_pack.py` | `examples/workflow-calibration-lod/` |
| `workflow-immunoassay-4pl` | Check supplied plate immunoassay optical densities with a frozen four-parameter logistic standard curve, replicate controls, bracketed sample interpolation and dilution parallelism. | `scripts/validate_immunoassay_4pl_pack.py` | `examples/workflow-immunoassay-4pl/` |
| `workflow-qpcr-relative-quantification` | Check already-measured real-time PCR Cq tables with dilution-derived amplification efficiencies, frozen reference genes, censored nondetections, replicate controls and biological-unit fold-change intervals. | `scripts/validate_qpcr_relative_quantification_pack.py` | `examples/workflow-qpcr-relative-quantification/` |
| `workflow-enzyme-kinetics` | Check Michaelis-Menten Vmax, Km, kcat and Jacobian uncertainty from supplied synthetic initial-rate fixtures under frozen linear-window and depletion rules; offline arithmetic only, with no inhibitor or biological claims. | `scripts/validate_enzyme_kinetics_pack.py` | `examples/workflow-enzyme-kinetics/` |
| `workflow-flow-cytometry-qc` | Check already-acquired synthetic flow cytometry event tables against frozen compensation, singlet, live/dead and channel gates; return control-qualified counts and parent-relative percentages. | `scripts/validate_flow_cytometry_qc_pack.py` | `examples/workflow-flow-cytometry-qc/` |
| `workflow-growth-curve` | Estimate per-well microbial or cell-culture OD growth rates, tangent lag, observed carrying-capacity proxy, integrated OD and doubling times from supplied synthetic time series. | `scripts/validate_growth_curve_pack.py` | `examples/workflow-growth-curve/` |
| `workflow-cfu-plate-counts` | Check already-counted serial-dilution colony plates with frozen countable ranges, exposure-weighted CFU per mL and exact Poisson bounds. | `scripts/validate_cfu_plate_count_pack.py` | `examples/workflow-cfu-plate-counts/` |
| `workflow-stability-shelf-life` | Check synthetic attribute measurements over storage time using frozen batch pooling and a one-sided mean bound against a specification. | `scripts/validate_stability_shelf_life_pack.py` | `examples/workflow-stability-shelf-life/` |
| `workflow-pk-nca-profile` | Check supplied preclinical concentration-time profiles with frozen censoring and terminal-fit rules; calculate observed peaks, trapezoidal exposure and reliable-only geometric summaries. | `scripts/validate_pk_nca_pack.py` | `examples/workflow-pk-nca-profile/` |
| `workflow-dose-response-curve` | Fit in-vitro concentration-response curves with frozen assay declarations, labelled biological and technical replicates, control separation, constrained four-parameter logistic curves and potency intervals. | `scripts/validate_dose_response_pack.py` | `examples/workflow-dose-response-curve/` |

## Omics and sequencing

| Skill | Checks | Validator | Example |
| --- | --- | --- | --- |
| `workflow-bulk-expression-analysis` | Conduct a fixed-stage bulk expression differential analysis from an admitted dataset and declared design through QC, a frozen contrast, multiplicity-controlled testing, supplied gene-set enrichment, and independent review handoff. | `scripts/validate_bulk_expression_pack.py` | `examples/workflow-bulk-expression-analysis/` |
| `workflow-single-cell-pseudobulk` | Compare single-cell RNA counts between conditions using donor or biological-sample pseudobulk units. | `scripts/validate_single_cell_pseudobulk_pack.py` | `examples/workflow-single-cell-pseudobulk/` |
| `workflow-proteomics-differential-abundance` | Compare quantified protein intensities between biological conditions with a frozen contrast, peptide controls, missingness records and BH-adjusted abundance differences. | `scripts/validate_proteomics_pack.py` | `examples/workflow-proteomics-differential-abundance/` |
| `workflow-metabolomics-feature-qc` | Check an already-acquired untargeted LC-MS feature table using pooled QC, blanks, injection order and a dilution series before differential comparisons. | `scripts/validate_metabolomics_feature_qc_pack.py` | `examples/workflow-metabolomics-feature-qc/` |
| `workflow-microbiome-composition` | Compare microbial community composition between two conditions from supplied sample-by-taxon integer counts. | `scripts/validate_microbiome_composition_pack.py` | `examples/workflow-microbiome-composition/` |
| `workflow-batch-effect-assessment` | Assess technical batch structure in supplied omics matrices with frozen design rules, exact confounding checks and group-restricted permutations. | `scripts/validate_batch_effect_assessment_pack.py` | `examples/workflow-batch-effect-assessment/` |
| `workflow-crispr-screen-qc` | Check guide counts from an already-sequenced pooled CRISPR knockout screen against a frozen guide library, matched replicates and non-targeting controls. | `scripts/validate_crispr_screen_pack.py` | `examples/workflow-crispr-screen-qc/` |
| `workflow-peak-replicate-qc` | Check supplied genomic enrichment peak intervals, library read counts, FRiP, reciprocal replicate overlap and blacklist exclusions under frozen genome and consensus rules. | `scripts/validate_peak_replicate_qc_pack.py` | `examples/workflow-peak-replicate-qc/` |
| `workflow-gene-set-overrepresentation` | Test a frozen gene list against a versioned local gene-set collection using the tested-gene universe, exact upper tails, BH correction and overlap grouping. | `scripts/validate_gene_set_overrepresentation_pack.py` | `examples/workflow-gene-set-overrepresentation/` |
| `workflow-gwas-summary-qc` | Check supplied GWAS per-variant beta, standard error, p, sample size and alleles against frozen genome-build and quality rules; summarize positional loci without genotypes or an LD reference. | `scripts/validate_gwas_summary_qc_pack.py` | `examples/workflow-gwas-summary-qc/` |
| `workflow-callset-qc` | Check cohort quality in an already-called synthetic small-variant genotype table using frozen filters, controls-only exact Hardy-Weinberg tests, trio consistency and X heterozygosity. | `scripts/validate_callset_qc_pack.py` | `examples/workflow-callset-qc/` |

## Statistics and evidence synthesis

| Skill | Checks | Validator | Example |
| --- | --- | --- | --- |
| `workflow-diagnostic-accuracy` | Evaluate diagnostic accuracy of supplied per-subject continuous scores against a reference standard using frozen thresholds, bias refusals, Wilson intervals and tie-aware ROC AUC. | `scripts/validate_diagnostic_accuracy_pack.py` | `examples/workflow-diagnostic-accuracy/` |
| `workflow-survival-time-to-event` | Compare two baseline-defined groups using supplied per-subject follow-up, event flags and right censoring. | `scripts/validate_survival_pack.py` | `examples/workflow-survival-time-to-event/` |
| `workflow-meta-analysis-evidence` | Pool already-extracted study effects with frozen eligibility, cohort deduplication, comparable scales, heterogeneity and sensitivity gates. | `scripts/validate_meta_analysis_pack.py` | `examples/workflow-meta-analysis-evidence/` |

## Dossiers and screening

| Skill | Checks | Validator | Example |
| --- | --- | --- | --- |
| `workflow-target-assessment-dossier` | Build an evidence-based target and indication assessment through six fixed stages, identity and dependency gates, an unreviewed go/no-go memo and independent review handoff. | `scripts/validate_target_assessment_pack.py` | `examples/workflow-target-assessment-dossier/` |
| `workflow-variant-evidence-dossier` | Build an evidence-only public variant dossier through fixed normalization, public-source retrieval, dependency reconciliation, bounded claims and independent review handoff. | `scripts/validate_variant_dossier.py` | `examples/workflow-variant-evidence-dossier/` |
| `workflow-solid-state-screening` | Conduct CPU materials-model screening through fixed normalization, analytic control, convergence, uncertainty-aware ranking, and independent review stages. | `scripts/validate_solid_state_screening.py` | `examples/workflow-solid-state-screening/` |

## Adding a pack

Follow an existing pack of the same shape: an authored skill with `quality.json`
and `references/index.json`, `stages.md` and `plan.json` linked from the SKILL.md
Reference usage section; examples with an accepting bundle named `pack.json` and
negative cases; a validator CLI; a test module; a `scripts/check.sh` step; and a
policy entry in `catalog/native-skill-policy.json`. Add the pack to this index;
`tests/test_workflow_pack_index.py` fails when a `workflow-*` skill is missing.
