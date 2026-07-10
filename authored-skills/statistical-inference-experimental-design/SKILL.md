---
name: statistical-inference-experimental-design
description: "Design experiments and perform defensible statistical inference. Use for estimands, randomization, blocking, sample-size planning, regression, hypothesis tests, intervals, multiple comparisons, missing data, diagnostics, and reproducible analysis plans."
license: MIT
---

# Statistical Inference and Experimental Design

## Define the claim before analysis

State the population, experimental unit, treatment or exposure, outcome, estimand, observation window, and
decision threshold. Separate confirmatory hypotheses from exploratory questions. Identify clustering,
repeated measures, censoring, missingness, and plausible confounders before selecting a test.

## Design the experiment

1. Prefer randomized assignment; state the randomization unit and allocation mechanism.
2. Use blocking, pairing, or stratification only with a declared analysis that respects the design.
3. Plan replication at the independent-unit level, not the number of technical readings.
4. Size the study from a scientifically meaningful effect, variability range, power target, and attrition.
5. Predefine exclusions, transformations, primary outcomes, stopping rules, and multiplicity handling.

## Analyze

Match the likelihood or estimating procedure to the outcome and sampling process. Report effect sizes and
intervals, not only p-values. Preserve continuous outcomes unless categorization is scientifically required.
Use hierarchical or robust methods for grouped data and sensitivity analyses for missing-data assumptions.

## Verify

- Confirm units, independence structure, balance, missingness, and data provenance.
- Inspect residuals, influential cases, model specification, and numerical convergence.
- Compare a simple baseline with the chosen model and rerun key claims under reasonable alternatives.
- Control or clearly label multiple testing; never select a model using the held-out confirmatory set.
- Check interval coverage or calibration with simulation when the design or estimator is nonstandard.

## Deliver

Provide the design, estimand, analysis population, model, effect and interval, diagnostics, sensitivity results,
and a clear separation between association, prediction, and causal claims.

## Source basis

Original synthesis informed by OpenIntro statistics materials and Seltman's experimental-design text; source
and license details are in `../../docs/TEXTBOOK_SOURCES.md`.
