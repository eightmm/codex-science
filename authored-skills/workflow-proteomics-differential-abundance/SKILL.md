---
name: workflow-proteomics-differential-abundance
description: "Compare quantified protein intensities between biological conditions with a frozen contrast, peptide controls, missingness records and BH-adjusted abundance differences. Use for supplied protein-by-sample tables; exclude raw spectra, peptide search engines and causal or clinical conclusions."
license: MIT
---

# Proteomics Differential Abundance

Role: conductor composed with a small offline reference analyzer. Output states statistical evidence only. All checked-in examples are redistributable synthetic software fixtures, never biological evidence.

## Decision contract

Record the exact question, organism, population, assay, evidence cutoff, two-condition ordered contrast, biological replicate unit, independent sample identities, batches, protein database name and version, claim IDs, uncertainty rule and falsifier. Reuse `$cx-public-omics-dataset-discovery` for dataset fitness and `$cx-mass-spectrometry-identification` for upstream assay context only. This pack starts with already-quantified protein intensities; it never reads raw spectra or runs a search engine.

Before reading the intensity table, freeze and hash the design and every interpretation-changing control: contrast, biological replicate unit, normalization method, missing-value rule, FDR alpha, BH family, minimum peptides per protein, minimum genuinely observed values per group, missing-rate and total-intensity thresholds. The fixture uses four independent biological samples per group, a minimum of three observed values and two peptides; these are software acceptance controls, never a power justification. Refuse technical runs counted as biological units or a batch perfectly confounded with condition. Paired designs and covariate-adjusted models require another method.

The deliverable is unreviewed statistical evidence. Fixture acceptance requires the planted `CHANGED` protein alone to pass BH while the balanced planted `BATCH` effect and null proteins remain nonsignificant. Missing, zero-variance, low-peptide, decoy and contaminant rows remain visible as untestable. Missing essential identities stop admission; an unavailable record never becomes negative evidence. Resolve interpretation-changing ambiguity before computing; infer reversible presentation details.

## Reference usage

Read [the index](references/index.json) and [stages and record shapes](references/stages.md) before admitting data, freezing controls, computing, validating or handing off results. Copy [the plan](references/plan.json) using the existing manifest step shape. Record materially controlling reference paths and hashes in the existing `reference-use-ledger`. These references constrain procedure and do not establish scientific support.

## Workflow

1. **01-design — freeze before intensity admission.** Hash the specification and the biological-sample design before loading the quantified table. Preserve the original freeze. A changed normalization, contrast or other control needs an exploratory label and a retained original specification. Content hashes cannot prove historical timing.
2. **02-qc — admit identities and retain controls.** Check organism and database name/version across every sample and the table. Retain sample-level total intensity, log2 total-intensity deviation and missing rate. Keep decoy/contaminant flags and peptide counts visible. A failed sample control blocks hits and marks every comparison untestable; retain its measurements and failures. Do not silently delete outliers.
3. **03-normalization — preserve missingness.** Use median log2 normalization of genuinely observed, non-decoy, non-contaminant proteins. Report offsets. Missing values stay missing under `keep-missing`. The explicit frozen `constant-log2` rule may fill displayed values; flag them, never count them as observed and never use them in the reference Welch test. Zero intensity is refused rather than interpreted as absent protein.
4. **04-testing — bounded abundance evidence.** Compare observed normalized log2 intensities with an unpaired, two-sided Welch t-test. Require the frozen observed minimum and positive within-group variance in both groups. Report all below-minimum and degenerate proteins as untestable with null p/q/significance, never as nonsignificant. Apply BH to every tested protein together, with no post-test selection. Decoys, contaminants and below-minimum-peptide proteins cannot become hits. Preserve nulls and failed controls.
5. **05-handoff — bounded claims and independent review.** Register ordinary domain artifacts and their immutable path-plus-hash identities with `$science-provenance`; keep separate entries in the existing claim register. Include assumptions, QC, exclusions, missingness, all p/q values, dependencies, conflicts, uncertainty, rejected alternatives, limitations and the smallest falsifiable next measurement. Hand the unchanged inputs, specification, result, execution record and claims to `$science-review` in record, source and method modes. The coordinator owns rigor classification, independent review and receipt registration.

Use one coordinator checkpoint per run with the five ordered stage IDs. The validator creates no checkpoint, manifest, execution engine or review receipt. Correct an identified input defect before a bounded retry, preserving the failed evidence and the original freeze; never weaken a control to obtain a hit. Real data additionally need normalization/missingness sensitivity, batch balance assessment, design-specific power and independent method review.

## Outputs

Pack-local schemas are `proteomics-pack-v1`, `proteomics-design-v1`, `proteomics-intensities-v1`, `proteomics-evidence-v1` and `proteomics-result-v1`. Their exact fields and public Python/CLI entry points are in the stages reference. They add no keys to existing manifests, claim registers or receipts.

Return the normalized assumptions, frozen identities, complete sample QC, normalization offsets, displayed log2 intensities with observed/imputed masks, all differential rows with observed denominators and untestable reasons, claims, limitations and `review: unavailable`. The coordinator separately records supported, contradicted, inconclusive and unavailable conclusions using existing claim semantics. An empty evidence list requires unavailable status. Review approval and computed agreement cannot support a positive claim.

The synthetic fixture bundle is `examples/workflow-proteomics-differential-abundance/pack.json`; `expected.json` and all 30 negative bundles are exercised by `tests/test_workflow_proteomics_pack.py`. Frozen questions, CPU budgets and acceptance criteria are in `benchmarks/workflow-proteomics-differential-abundance/tasks.json`. L4 means synthetic fixture acceptance under unittest discovery; it does not validate a real cohort or biological claim.

## Boundaries

Refuse association promoted to causality, mechanism, binding, affinity, inhibition, activation, therapeutic benefit, clinical action or efficacy. Numerical agreement never establishes physical or clinical validity. Review approval never establishes truth. Every positive status checks the declared kind and result of each evidence record, in addition to the claim text and recomputed protein result. The conservative English wording filter is specified in the stages reference and remains incomplete; independent review must assess meaning and unlisted paraphrases.

Refuse pseudoreplication, perfect batch confounding, database-version mixtures, undeclared imputation, zero-filled missing values, incomplete BH correction, unlabelled post-hoc changes, or hits from untestable or flagged proteins. Preserve negative results, failed controls and source dependencies. Declaring evidence external, independent or preregistered cannot replace source identity checks or establish actual independence.

This route is CPU-only, offline and standard-library-only. No network, download, installation, GPU, remote job or new host is authorized. Human gates apply before installation, restricted transfers, new hosts, GPU/remote/heavy compute or interpretation-changing choices; do not add a gate at every admitted local stage. A process exit, successful validator, synthetic numerical agreement or independent reviewer approval is never biological truth.
