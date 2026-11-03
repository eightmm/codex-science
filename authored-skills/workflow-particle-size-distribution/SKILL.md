---
name: workflow-particle-size-distribution
description: "Check supplied binned particle diameters with frozen micrometre edges, cumulative D10/D50/D90, span, midpoint means and replicate agreement. Use for already-measured synthetic count or volume tables; exclude product quality, stability, performance and regulatory conclusions."
license: MIT
---

# Particle Size Distribution

Role: conductor with an offline reference analyzer. Every checked-in table and expected artifact is a synthetic fixture. This pack checks arithmetic on already-measured bins; it neither measures particles nor validates an instrument or product.

## Decision contract

Before opening the table, freeze unique sample and measurement identities, strictly increasing bin edges in micrometres, count or volume basis, linear interpolation within bins on the cumulative curve, D10/D50/D90, span, mean by number, volume-weighted mean, the midpoint/spherical-volume convention, minimum total count, minimum replicate measurements, D50 and span relative-range bounds, and the out-of-range tail limit and exclusion rule. Hash the rule bytes first. Record the question, descriptive claim IDs, system, evidence cutoff, baseline, exclusions, missingness, uncertainty, falsifier and rejected alternatives. Hash declarations identify bytes but cannot establish historical freeze timing.

Use the recorded basis for percentiles; never compare a count median with a volume median as though they were the same quantity. The means approximate each bin by its midpoint and assume particle volume proportional to diameter cubed. Freeze this interpretation before outcomes. Percentiles include recorded tail fractions; means describe the in-range bins only. Binning and shape assumptions require separate method review. The synthetic acceptance case has sample A D10/D50/D90 of 2/4/6 micrometres and sample B 1.5/3.5/6. These numbers establish no physical validity.

## Reference usage

Read [the reference index](references/index.json) and [stages and record shapes](references/stages.md) before freezing rules, admitting tables, computing quantities, validating artifacts or handing off claims. Reuse [the ordered plan](references/plan.json) in the existing manifest step shape. Record controlling reference paths and hashes in the existing `reference-use-ledger`; procedural documents are never scientific evidence.

## Workflow

1. **01-rule-freeze.** Use `$cx-statistical-decision-analysis` to frame uncertainty and freeze the decision contract as `psd-rules-v1`. Preserve its path and SHA-256 before reading table bytes. A later interpretation-changing choice needs a human decision; retain the original rules. Adjacent-bin merging after outcomes requires an exploratory label and recomputation.
2. **02-table-qc.** Admit a hash-bound `psd-table-v1`. Check identities, strict edges, matching count or volume basis, real nonnegative integer counts or fractions summing to one within 1e-9, total count and both tails. Unavailable measurements have explicit null data, never zeros. Measurements at or below the count minimum, or at or above the combined tail limit, are unreliable and excluded. Preserve failed controls and negative results.
3. **03-distribution.** Run `scripts/validate_particle_size_distribution_pack.py` on the synthetic fixture first. Compute cumulative within-bin D10, D50 and D90, span, and the frozen midpoint means for reliable measurements. Check relative ranges of D50 and span before averaging per-measurement quantities. Use all reliable replicates or none; never select a favorable subset. Fewer than the frozen minimum (at least two), or disagreement, makes the sample summary unavailable.
4. **04-summary.** Retain every sample and measurement, including excluded and unavailable records, sample n, measurement denominators, relative ranges, dependencies, conflicts, sensitivity needs and limitations. Technical measurements never increase independent sample n. Preserve the basis and units; do not pool distributions or substitute unavailable values into means.
5. **05-handoff.** Register domain records as ordinary artifacts with `$science-provenance` and separate entries in the existing claim register. Send rules, tables, hashes, results, failed controls, negative results, execution/environment identity, references and bounded claims to `$science-review` in record, source and method modes. Rigor classification and independent receipt registration remain coordinator-owned. This pack always leaves review unavailable.

Use one coordinator checkpoint per run and these five ordered stage IDs. There is no execution engine. Retry only after correcting a specific input defect; retain each failed revision. Stop for essential missing inputs or an interpretation-changing choice. Reversible display preferences need no additional gate.

## Outputs

Pack-local schemas are `psd-pack-v1`, `psd-rules-v1`, `psd-table-v1`, `psd-report-v1`, `psd-evidence-v1` and `psd-result-v1`; the stages reference defines exact fields. No existing manifest, receipt, claim-register or MCP contract changes.

Return normalized inputs and assumptions, immutable path-plus-hash identities, per-measurement quantities, reliability and exclusions, per-sample agreeing-replicate means or unavailable, denominators, dependencies, conflicts, rejected alternatives, uncertainty, applicability, limitations and the smallest falsifiable next measurement. The coordinator records supported, contradicted, inconclusive and unavailable interpretations separately. Numerical agreement cannot support a positive scientific claim.

Synthetic fixtures and hand-derived expected artifacts live in `examples/workflow-particle-size-distribution/`. Frozen questions, criteria and CPU budgets live in `benchmarks/workflow-particle-size-distribution/tasks.json`. L4 denotes offline synthetic software acceptance in `tests/test_workflow_psd_pack.py`, never instrument, product or scientific validation.

## Boundaries

Refuse product quality, stability, performance, regulatory, causal, therapeutic, clinical-action, efficacy and mechanism wording, even under a descriptive label. The stages reference defines the conservative English lexical gate and its incomplete scope. Association is never causality; computed agreement is never physical or clinical validity; review approval is never truth. Computed or review-approval records never support positive claims. Any unavailable evidence requires unavailable claims; empty evidence requires unavailable. This single synthetic fixture cannot establish replication. External, independent and preregistered labels cannot alias study artifacts by path or hash.

This route uses local CPU, standard library code and offline synthetic fixtures only. No network, downloads, installation, GPU, remote or heavy compute is performed. Human gates apply only before installation, restricted transfers, new hosts, GPU/remote/heavy compute or interpretation-changing choices. No gate is needed at each admitted offline stage. Preserve failed controls and negative results; absence of a record is unavailable, never negative evidence.
