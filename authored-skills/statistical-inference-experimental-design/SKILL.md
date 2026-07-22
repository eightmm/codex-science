---
name: statistical-inference-experimental-design
description: "Design experiments and perform defensible statistical inference with explicit estimands, experimental units, preregistration, effect sizes, intervals, multiplicity, missingness, randomization, diagnostics, and machine-readable analysis receipts."
license: MIT
---

# Statistical Inference and Experimental Design

## Decision contract

Before looking at outcomes, state the population, experimental unit, observational unit, treatment or exposure, outcome, estimand, assignment mechanism, observation window, primary family, decision rule, missing-data assumptions, exclusions, stopping rule, and scientifically meaningful effect scale. Mark the work confirmatory or exploratory.

Do not use the number of cells, images, technical repeats, time points, or model outputs as the sample size when treatment was assigned at a higher unit.

## Reference usage

Read [the design and inference runtime](references/design-and-inference-runtime.md) before `research-design-audit` or `statistical-analysis`. It contains the exact input fields, CLI arguments, supported bounded methods, and interpretation limits. Do not infer a model, p-value meaning, multiplicity family, or independent-unit count from an operation name.

For material work, record the reference hash with `scripts/reference_lookup.py` and preserve the design and result files with `$science-provenance`.

## Workflow

1. Author a `research-design` input and run `scripts/validate_research_design.py --require-clean` before outcome-dependent analysis.
2. Match the analysis to assignment and sampling. Use blocking, pairing, hierarchy, survey weights, censoring, or longitudinal dependence only with a method that represents them.
3. For a bounded independent or paired two-group contrast, run `scripts/run_statistical_analysis.py`; for more complex models, use a suitable external implementation but emit equivalent design, effect, interval, diagnostic, seed, and environment records.
4. Report effect size, interval, independent-unit count, missingness, exclusions, and multiplicity handling before p-values.
5. Run prespecified sensitivity analyses and diagnose design/model mismatch.
6. Package the design and analysis sidecars, then run `$science-review`.

## Outputs

- `research-design` with deterministic audit and fingerprint;
- `statistical-analysis` with effect, interval, randomization result, unit counts, seed, and limitations;
- data/source hashes and preprocessing records;
- diagnostics and sensitivity analyses;
- manifest claim IDs that distinguish association, prediction, and causal interpretation;
- independent review receipt for material conclusions.

## Boundaries

- A p-value is not effect magnitude, practical importance, replication, or causal identification.
- Randomization inference is valid only for the recorded assignment or exchangeability model.
- Bootstrap intervals are conditional on the resampling unit and may fail for small, irregular, or dependent samples.
- A clean deterministic design audit does not prove that all domain assumptions are scientifically justified.
- Do not alter exclusions, endpoints, transformations, stopping rules, or multiplicity families to obtain a preferred result without labeling the change exploratory.
- Stop or downgrade the claim when the experimental unit is ambiguous, the model cannot represent the design, missingness assumptions are indefensible, or the causal estimand is unidentified.

## Source basis

Original synthesis informed by OpenIntro statistics materials and Seltman's experimental-design text; source and license details are in `../../docs/TEXTBOOK_SOURCES.md`.
