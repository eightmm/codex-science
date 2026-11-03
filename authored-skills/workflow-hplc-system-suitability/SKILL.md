---
name: workflow-hplc-system-suitability
description: "Check recorded replicate standard injections using frozen HPLC peak identities, retention-time and area RSD, tailing, plates, nearest-peak resolution and blank carryover. Use with synthetic peak tables; exclude method validation and release decisions."
license: MIT
---

# HPLC System Suitability

Role: conductor with an offline reference analyzer. All checked-in peak tables, questions and expected artifacts are synthetic fixtures. The deliverable is an inspectable arithmetic check on already-recorded standard injections.

## Decision contract

Before opening peak data, freeze the analyte and optional reference peak, standard and blank injection identities, planned and minimum standard counts, all seven acceptance limits, units, width definitions and formulas. Hash the rule bytes before table admission. Record the question, system, evidence cutoff, descriptive claim IDs, baseline, falsifier, missingness, exclusions, uncertainty and rejected alternatives. Hashes identify a revision; they cannot prove historical freeze timing.

Use sample standard deviation for replicate RSD. Require half-height plates with constant 5.54, five-percent-height tailing, baseline-width nearest-peak resolution, recorded signal-to-noise and a blank immediately following its recorded standard. Failed criteria remain in the summary. With fewer than the frozen minimum standards, RSDs are unavailable, never zero or pass. Zero replicate variance refuses rather than appearing to establish precision.

The six-injection synthetic smoke case has five standards and one blank. Hand checks require retention-time RSD about 3.1623%, area RSD about 1.5811%, first-injection plates 12764.16, tailing 2 (failed), resolution 2.5 and carryover 0.5%. Fixture acceptance is a software check, not an observation about method validity.

## Reference usage

Read [the reference index](references/index.json) and [stages and record shapes](references/stages.md) before freezing rules, admitting tables, computing quantities, checking claims or handing off. Reuse [the ordered plan](references/plan.json) with the existing manifest step shape. Record controlling reference paths and hashes in the existing reference-use-ledger. Procedure references are not scientific evidence.

## Workflow

1. **01-rule-freeze.** Preserve rules.json as hplc-rules-v1 with SHA-256 before opening table.json. Use $cx-statistical-decision-analysis for decision framing and uncertainty. Keep the original revision immutable. Applied limits changed after outcomes require an exploratory label and recomputation.
2. **02-table-qc.** Admit hplc-table-v1 by path and hash. Check unique injection IDs, strict order, frozen standard/blank identities, finite positive retention times and widths, required heights, optional reference identity, and every frozen blank. Never mix blanks into replicates or invent a missing peak.
3. **03-suitability.** Run scripts/validate_hplc_system_suitability_pack.py on the synthetic fixture first. Compute sample RSDs, per-injection plates, tailing, nearest-peak resolution, recorded signal-to-noise and blank/preceding-standard carryover. Every criterion has pass, fail or unavailable status. Preserve the original failed input if validation refuses; retry only after correcting its specific defect.
4. **04-summary.** Retain all seven criteria, every injection, replicate IDs and actual count. Failure takes precedence over unavailable, which takes precedence over pass in per-criterion summaries. Preserve negative results, missingness, dependencies, conflicts, uncertainty and sensitivity to threshold choices. Never drop a failed criterion to obtain acceptance.
5. **05-handoff.** Register domain records as ordinary artifacts through $science-provenance with separate entries in the existing claim register. Supply original rule/table hashes, results, failed controls and revisions, assumptions, execution/environment identities, reference ledger and the smallest falsifiable next measurement to $science-review in record, source and method modes. The coordinator owns rigor classification and review receipt registration. This pack leaves review unavailable.

Keep one coordinator checkpoint per run with these five ordered IDs. There is no new execution engine. Stop for essential missing input or an interpretation-changing choice; resolve reversible display choices internally.

## Outputs

Pack-local schemas: hplc-pack-v1, hplc-rules-v1, hplc-table-v1, hplc-report-v1, hplc-evidence-v1 and hplc-result-v1. Exact fields and limits are in the stages reference. Existing manifest, receipt, claim-register and MCP contracts are unchanged.

Return normalized inputs and assumptions; immutable path-plus-hash identities; actual standard count and IDs; per-injection values and statuses; replicate RSDs; carryover; complete criterion summary; exclusions, dependencies, conflicts, rejected alternatives, uncertainty, applicability and limitations. The coordinator records supported, contradicted, inconclusive and unavailable interpretations separately. Computed agreement cannot support positive scientific claims.

Synthetic fixtures and negative cases are in examples/workflow-hplc-system-suitability/. Frozen questions and CPU budgets are in benchmarks/workflow-hplc-system-suitability/tasks.json. L4 denotes checks exercised by tests/test_workflow_hplc_pack.py, not real chromatographic or product acceptance.

## Boundaries

Refuse claims of method validity, system qualification for release, product quality, regulatory status, causality, mechanism, therapeutic or clinical action, efficacy, or physical validity, including under descriptive labels. The stages reference specifies an incomplete conservative English wording gate. Association is never causality; numerical agreement is never physical or clinical validity; review approval is never truth. Missing evidence requires unavailable status, never negative evidence. Unavailable sources require unavailable claims; empty evidence requires unavailable status. A single synthetic fixture cannot establish replication. External, independent or preregistered labels cannot alias own outputs by path or hash.

This route is CPU-only, offline and standard-library-only. No network, download, installation, GPU, remote or heavy compute is performed. Human gates apply only before installation, restricted transfer, a new host, GPU/remote/heavy compute or an interpretation-changing choice. Preserve failed controls and negative results. The validator writes nothing; concurrent calls read independently, and interruption may truncate stdout without changing supplied files.
