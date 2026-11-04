---
name: workflow-cell-count-viability
description: "Check recorded hemocytometer or automated-counter cell counts with frozen chamber volumes, dilution, dye mixing, replicate agreement and exact live-fraction bounds. Use for supplied synthetic count tables; exclude culture-health, potency, release and medical conclusions."
license: MIT
---

# Cell Count and Viability

Role: conductor with an offline reference analyzer. All checked-in counts, questions and expected artifacts are synthetic fixtures. This pack checks recorded arithmetic, never images, culture health, assay validity or product acceptance.

## Decision contract

Before opening counts, define the question, descriptive claim IDs, system, evidence cutoff, baseline, falsifier, controls, exclusions, missingness and uncertainty assumptions. Freeze sample, chamber, counter and square identities, chamber volume per square in mL, predye dilution multiplier, dye mixing ratio, inclusive countable range, minimum cells per sample, maximum relative chamber disagreement, live/(live+dead) definition, Clopper-Pearson method and confidence level. Hash the rules first. A hash declares an immutable identity; it cannot establish historical preregistration.

The deliverable is concentration and an exact binomial live-fraction interval for eligible recorded counts. Technical squares and chambers never increase sample n. Fix independent Poisson counting, binomial sampling and recorded exposure assumptions before outcomes; sensitivity to clumping, countability, mixing and measurement error requires separate method review. The hand-derived synthetic fixture has 40 cells across four squares, 400000 cells/mL and live fraction 32/40; the low-count sample retains its four observed cells with unavailable estimates.

## Reference usage

Read [the reference index](references/index.json) and [stages and local records](references/stages.md) before rule freeze, admission, computation, validation or review handoff. Reuse [the ordered plan](references/plan.json) with the existing manifest step shape. Record controlling reference identities in the existing hash-bound `reference-use-ledger`; procedure documents never become scientific evidence.

## Workflow

1. **01-rule-freeze.** Use `$cx-statistical-decision-analysis` for framing, then preserve and hash `cell-rules-v1` before counts are read. Retain every revision and rejected alternative. Selecting a different recorded square set later requires an exploratory label, recomputation and an interpretation-changing human decision; never rewrite the frozen rules.
2. **02-count-qc.** Admit `cell-counts-v1` by path plus hash. Check globally unique chamber/counter identities, one row for every frozen square/chamber pair, matching dilution, volume and mixing, real nonnegative integer counts and a real boolean clumping flag. Missing live/dead counts are both null, never zero. Preserve clumped counts as recorded but exclude them from estimates. Failed controls and negative results stay in the artifacts.
3. **03-concentration-viability.** Smoke-check `examples/workflow-cell-count-viability/pack.json` through `scripts/validate_cell_count_viability_pack.py`. Compute mean cells per eligible square times the dilution and mixing multipliers divided by frozen square volume. Require complete countable unclumped applied squares and the frozen minimum cells. Otherwise return unavailable concentration and viability, never zero estimates. Refuse pooling beyond the replicate-disagreement bound. Report Poisson standard error and the exact Clopper-Pearson interval, never Wald bounds.
4. **04-summary.** Retain all frozen samples, raw count totals with observed-square denominators, usable counts, included/excluded square identities, replicate disagreement, uncertainty and missingness. No eligible or observed records imply unavailable estimates or recorded counts respectively. Report sample n and quantified/unavailable denominators. Preserve dependencies, conflicts, null results and limitations.
5. **05-handoff.** Register rules, counts, reports and results as ordinary artifacts through `$science-provenance`, with separate entries in the existing claim register. Hand hashes, assumptions, failed revisions, rejected choices, controls, environment/code identity, reference ledger and bounded claims to `$science-review` for record, source and method review. The coordinator owns rigor and independent review registration. The pack always returns review unavailable.

Use one coordinator checkpoint per run and these ordered stage IDs. This adds no execution engine. Retry only after correcting an identified input defect, retaining the failed revision. Proceed with reversible in-scope checks; stop for missing essential inputs or an interpretation-changing choice.

## Outputs

Pack-local ordinary artifact schemas: `cell-pack-v1`, `cell-rules-v1`, `cell-counts-v1`, `cell-report-v1`, `cell-evidence-v1` and `cell-result-v1`. The stages reference specifies exact fields, numerical tolerances and admission limits. Existing manifests, claim registers, receipts and MCP interfaces are unchanged.

Return normalized assumptions, immutable identities, count/QC tables, descriptive quantities, inclusion/exclusion rationale, controls, uncertainty, dependencies, conflicts, applicability, limitations and the smallest falsifiable next measurement. The coordinator records supported, contradicted, inconclusive and unavailable interpretations separately. Neither a computed match nor review approval supports a positive scientific claim.

Synthetic acceptance artifacts and seeded defects live in `examples/workflow-cell-count-viability/`. Frozen questions and CPU budgets live in `benchmarks/workflow-cell-count-viability/tasks.json`. L4 means offline fixture acceptance in `tests/test_workflow_cell_pack.py`, never physical, biological or clinical validation.

## Boundaries

Refuse culture-health, potency, release, clinical, efficacy, causal, mechanism, therapeutic or physical-validity claims, regardless of a descriptive label. The conservative English lexical gate is incomplete; the stages reference lists its wording families. Association is never causality; numerical agreement is never physical or clinical validity; review approval is never truth. Unavailable evidence requires unavailable status, including mixed citations. Empty evidence requires unavailable status. Unavailable claims cannot assert positive evidence. This synthetic fixture never establishes replication. External, independent and preregistered labels must not alias any supplied study output by path or hash.

Execution is local CPU, standard library and offline synthetic fixtures only: no network, download, installation, GPU, remote or heavy compute. Human gates apply only before installation, restricted transfer, new hosts, GPU/remote/heavy compute or an interpretation-changing choice. Failed controls and negative results are preserved; absent records never become negative evidence.
