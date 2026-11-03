---
name: workflow-arrhenius-rate-fit
description: "Fit Arrhenius temperature dependence from supplied synthetic positive rate constants, frozen kelvin identities, replicate rules and units. Use for offline arithmetic checks of Ea, ln A and in-range rate intervals; exclude mechanism, shelf life, process safety and reaction order conclusions."
license: MIT
---

# Arrhenius Rate Fit

Role: conductor with an offline reference analyzer. Every checked-in rate table and expected artifact is a synthetic fixture. This pack consumes already-measured rate constants; it does not measure rates or validate physical models.

## Decision contract

Before reading rates, freeze positive kelvin temperatures and run/replicate identities, rate units, energy units, gas constant and its units, mean-log replicate collapse, weighting, minimum distinct temperatures of at least four, positive minimum temperature span, requested prediction temperature, forbidden extrapolation, confidence level and lack-of-fit threshold. Hash the rules before opening rates. Record the exact question, system, descriptive claim IDs, evidence cutoff, comparison baseline, uncertainty, falsifier, exclusions, missingness and rejected choices. A rule hash cannot prove historical preregistration.

Default to ordinary least squares on one mean ln k per distinct temperature against 1/T. Only declared replicate-variance weighting is available as an alternative; a post-outcome weighting change requires exploratory labelling and recomputation without replacing the original rules. Technical replicates never increase the distinct-temperature denominator. Below the frozen distinct-temperature count or temperature span, every parameter stays unavailable. A requested temperature outside the measured inverse-temperature range has status outside-range and no predicted value.

The synthetic acceptance case has ln A equal to 4 and Ea equal to 1000 times R. The noisy case has four temperatures, eight runs, regression df 2, residual sum of squares .04 and mean ln rate 1.5 at 400 K. Agreement checks software arithmetic only. Freeze the log-linear error and replicate-precision assumptions; method review must address sensitivity to weighting, measurement precision and model form.

## Reference usage

Read [the reference index](references/index.json) and [stages and record shapes](references/stages.md) before rule freeze, table admission, fitting, validation or claim handoff. Reuse [the ordered plan](references/plan.json) in the existing manifest step shape. Register controlling reference identities in the existing reference-use-ledger. Procedure references are never scientific evidence.

## Workflow

1. **01-rule-freeze.** Use $cx-statistical-decision-analysis for decision and uncertainty framing. Freeze arr-rules-v1 and its SHA-256 before reading rate bytes. Keep original rules and rejected alternatives. A material interpretation-changing choice needs a human decision; offline admission needs no extra prompt.
2. **02-table-qc.** Admit immutable path-plus-hash arr-rates-v1. Check unique run IDs, frozen kelvin and replicate identities, positive finite rates and consistent units. Collapse replicates within temperature by mean ln k. Preserve source tables and failed controls; never silently relabel Celsius or log-transform zero/negative rates.
3. **03-fit.** Run scripts/validate_arrhenius_rate_fit_pack.py on the synthetic fixture first. Fit ln k = ln A - Ea/(R T), report parameter standard errors, residual standard error, df and Student t intervals. Preserve the classical pure-error lack-of-fit flag when estimable. Prediction intervals propagate uncertainty of the fitted mean ln rate and exponentiate its endpoints; they are not future-run intervals. Never extrapolate. Insufficient count/span remains unavailable.
4. **04-summary.** Preserve run and distinct-temperature counts, replicate variances, unavailable fields, failed controls, negative results, dependencies, conflicts, assumptions, sensitivity needs and applicability. A lack-of-fit flag remains visible for method review; neither its absence nor an unavailable test validates the relation.
5. **05-handoff.** Use $science-provenance for ordinary domain artifacts and separate entries in the existing claim register. Pass rules, rates, input hashes, reference ledger, results, failures, execution/environment identities and bounded claims to $science-review in record, source and method modes. The coordinator owns rigor classification and receipt registration; this pack always leaves review unavailable.

Use one coordinator checkpoint and the five ordered stage IDs per run. There is no new execution engine. Retry only after correcting a specific defect and preserve failed revisions. Missing evidence stays unavailable, never negative. Choose reversible display details internally; stop only for essential missing input or interpretation-changing choices.

## Outputs

Pack-local schemas: arr-pack-v1, arr-rules-v1, arr-rates-v1, arr-report-v1, arr-evidence-v1 and arr-result-v1. Exact fields and bounds are in the stages reference. They are ordinary artifacts; no existing manifest, receipt, claim-register or MCP schema changes.

Return normalized assumptions, immutable input identities, collapsed temperatures, Ea and ln A with standard errors and t intervals or unavailable, regression df and residual error, lack-of-fit flag or unavailable, bounded mean-response predictions, inclusion/exclusion rationale, denominators, uncertainty, applicability, dependencies, conflicts, rejected alternatives and the smallest falsifiable next measurement. The coordinator records supported, contradicted, inconclusive and unavailable interpretations separately. Computed agreement cannot support a positive scientific claim.

Synthetic bundles, expected artifacts and negative cases are in examples/workflow-arrhenius-rate-fit/. Frozen questions and CPU budgets are in benchmarks/workflow-arrhenius-rate-fit/tasks.json. L4 means offline synthetic acceptance in tests/test_workflow_arr_pack.py; it establishes no mechanism, shelf life, process safety, reaction order or physical validity.

## Boundaries

Refuse mechanism, shelf life, process safety, reaction order, causal, therapeutic, clinical-action, efficacy and physical-validity claims, including under descriptive labels. The conservative English lexical gate is defined in the stages reference and is incomplete for paraphrases and other languages. Its activation-word family means prose about Ea must use the symbol rather than assert an activation claim.

Association is never causality. Computation is never physical or clinical validity. Review approval is never truth. Every positive claim citing review approval or computed records is refused by both declared kind and result. Any unavailable citation requires unavailable status; an empty evidence list requires unavailable status. Unavailable claims cannot assert positive evidence. Replicated status is always refused for this synthetic fixture. External, independent or preregistered labels cannot alias supplied study artifacts by path or hash.

This route uses local CPU, standard library code and offline synthetic fixtures only. No network, download, installation, GPU, remote or heavy compute occurs. Human gates apply only before installation, restricted transfers, new hosts, GPU/remote/heavy compute or interpretation-changing choices. Hashes and declared kelvin labels cannot prove measurement provenance or detect deliberately false unit metadata. Preserve failed controls and negative results; never treat absent records as negative evidence.
