# Design and inference runtime

## Design audit

Run before outcome-driven analysis:

```bash
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/validate_research_design.py" design.json \
  --output artifacts/run/research-design.json \
  --require-clean
```

Required concepts are question, experimental and observational units, outcome measurement, estimand, assignment, analysis method, primary endpoints, multiplicity family, missing-data strategy, exclusions, stopping, sample-size rationale, sensitivity analyses, blinding, and whether the design was locked before outcomes.

The deterministic audit detects pseudoreplication, outcome-dependent design, uncorrected multiplicity, optional stopping, post-hoc exclusions, missing sample-size rationale, unstated missingness assumptions, causal-identification gaps, observational confounding gaps, incomplete randomization, and unblinded subjective outcomes.

Design strings must be non-empty strings, flags must be JSON booleans, and `sample_size.planned`, `multiplicity.family_size`, and `stopping.planned_looks` must be positive integers (booleans are refused). A null optional field is treated as absent; for example, null `alpha_spending` does not control repeated looks. Invalid types raise a field-naming error before an audit can pass.

A clean audit means the record is internally complete. It does not make the assumptions true.

## Statistical execution

The built-in runtime is limited to independent or paired two-group mean or median differences:

```bash
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/run_statistical_analysis.py" analysis.json \
  --output artifacts/run/statistical-analysis.json
```

The effect, interval and `alternative` refer to `group_labels[1] - group_labels[0]`, so list the reference group first: `["control", "treated"]` gives contrast `treated - control`, and `greater` tests `treated - control > 0`.

Each record contains `unit_id`, `group`, and `value`; paired records also contain `pair_id`. Repeated observations for one unit are aggregated by the explicitly selected mean or median before inference. In paired analysis, aggregation occurs within each group and `unit_id` before pairing: one `unit_id` cannot appear under multiple `pair_id` values, and each complete pair must contain exactly one unit per group. Conflicting mappings are refused, including mappings on missing observations; incomplete pairs are excluded and counted. At least two experimental units per group, or two complete pairs, are required.

The runtime computes:

- mean or median difference in the declared direction; paired `median-difference` is the median of the within-pair differences, rather than a difference of group medians;
- Hedges g or paired standardized mean where defined;
- deterministic percentile-bootstrap interval;
- exact randomization or sign-flip test when the state space is bounded;
- seeded Monte Carlo randomization otherwise;
- optional Benjamini-Hochberg q-values for an externally declared family;
- raw row count, missing count, independent-unit count, duplicate aggregation, and incomplete-pair exclusions.

Randomization comparisons use a tolerance tied to floating-point precision at the effect scale. Non-finite computed effects, bootstrap estimates, intervals, and standardized effects are refused before a completed receipt is returned. Receipt validation also checks probability ranges (`confidence_level` in `(0.5, 1)`, p-values and q-values in `[0, 1]`) and non-negative integer counts, refusing boolean counts.

The input requires an explicit seed even when an exact test is possible, so all stochastic interval work remains reproducible.

## Unsupported cases

Use an appropriate specialized model and preserve equivalent receipts instead of forcing the built-in runtime when any of these are material:

- more than two groups or factorial interaction;
- survival or censoring;
- longitudinal, spatial, network, or complex multilevel dependence;
- binary, count, ordinal, compositional, or zero-inflated outcomes requiring a likelihood model;
- survey weights or complex sampling;
- adaptive randomization or sequential monitoring;
- measurement error in predictors;
- causal adjustment, mediation, instrumental variables, regression discontinuity, or difference-in-differences;
- Bayesian posterior inference.

Do not reduce a complex design to a two-group test only because the CLI is convenient.

## Review checklist

- Reconstruct the independent-unit count from raw records.
- Confirm that the analysis contrast matches the estimand direction.
- Check that exclusions and missingness match the preregistration.
- Verify exact versus Monte Carlo randomization status and seed.
- Inspect effect and interval before p-value.
- Confirm the multiplicity family was declared before outcomes.
- Review sensitivity analyses and model diagnostics.
- Separate association, prediction, and causal claims.
- Record limitations and failed analyses rather than deleting them.
