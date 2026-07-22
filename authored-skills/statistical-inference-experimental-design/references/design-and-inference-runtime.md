# Design and inference runtime

## Design audit

Run before outcome-driven analysis:

```bash
uv run python scripts/validate_research_design.py design.json \
  --output artifacts/run/research-design.json \
  --require-clean
```

Required concepts are question, experimental and observational units, outcome measurement, estimand, assignment, analysis method, primary endpoints, multiplicity family, missing-data strategy, exclusions, stopping, sample-size rationale, sensitivity analyses, blinding, and whether the design was locked before outcomes.

The deterministic audit detects pseudoreplication, outcome-dependent design, uncorrected multiplicity, optional stopping, post-hoc exclusions, missing sample-size rationale, unstated missingness assumptions, causal-identification gaps, observational confounding gaps, incomplete randomization, and unblinded subjective outcomes.

A clean audit means the record is internally complete. It does not make the assumptions true.

## Statistical execution

The built-in runtime is limited to independent or paired two-group mean or median differences:

```bash
uv run python scripts/run_statistical_analysis.py analysis.json \
  --output artifacts/run/statistical-analysis.json
```

Each record contains `unit_id`, `group`, and `value`; paired records also contain `pair_id`. Repeated observations for one unit are aggregated by the explicitly selected mean or median before inference.

The runtime computes:

- mean or median difference in the declared direction;
- Hedges g or paired standardized mean where defined;
- deterministic percentile-bootstrap interval;
- exact randomization or sign-flip test when the state space is bounded;
- seeded Monte Carlo randomization otherwise;
- optional Benjamini-Hochberg q-values for an externally declared family;
- raw row count, missing count, independent-unit count, duplicate aggregation, and incomplete-pair exclusions.

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
