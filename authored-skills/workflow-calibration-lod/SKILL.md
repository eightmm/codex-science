---
name: workflow-calibration-lod
description: "Check supplied synthetic assay standards and blanks with frozen linear calibration, back-calculated deviations, explicit refits and detection or quantification limits. Use for offline arithmetic checks of already-measured fixtures; excludes clinical cut-offs and extrapolated concentrations."
license: MIT
---

# Calibration and Detection Limits

This conductor checks already-measured synthetic standards and blanks with a
small standard-library reference calculation. Every checked-in example is a
redistributable synthetic fixture. Numerical agreement is software evidence only.

## Decision contract

Before reading responses, freeze the analyte, concentration and response units,
linear or weighted-linear model, one weighting choice, free or zero intercept,
back-calculated percent deviation limits with a looser lowest-level threshold, minimum levels
and replicates, blank count, one LOD/LOQ rule and its multipliers, validity range
and exclusion rule. Hash those rules before opening response data. Record the
freeze and first-response-read timestamps; declarations do not prove history.

The deliverable is an arithmetic check within the supplied standard range.
Back-calculated percent deviations, residuals and replicate counts are primary
acceptance evidence. R-squared alone cannot establish acceptance. A failed
identity or numerical control falsifies admission; failed standard acceptance
remains a recorded negative result and disables unknown quantification.
Changing units, model, intercept, acceptance, exclusion, weights, limits or range
changes interpretation: preserve the first run and resolve a new freeze with
the coordinator. Exploratory weight changes need a separate labelled bundle.

## Reference usage

Read [stages and local records](references/stages.md) before freezing rules,
admitting data, running arithmetic or authoring a claim. Read [the ordered
plan](references/plan.json) before creating the coordinator's plan. The
[reference index](references/index.json) controls progressive loading.
Record materially controlling reference paths and SHA-256 identities in the
existing `reference-use-ledger`; references guide procedure, never supply evidence.

## Workflow

Use one coordinator checkpoint with the five existing manifest `plan` steps
in the reference plan. This pack adds no engine, global schema or MCP tool.

1. **01-freeze:** validate and hash the rule record before opening responses.
   Preserve the chosen model, weighting, intercept, thresholds and exclusion rule.
2. **02-identity-qc:** admit immutable path-plus-hash identities, unique IDs,
   strictly increasing positive standard levels with contiguous replicates,
   finite responses, sufficient blanks and consistent units. Never repair silently.
3. **03-fit-limits:** run the smallest synthetic fixture first. Preserve the
   initial fit, per-standard deviations and flags. Exclude only failures allowed
   by the frozen one-pass rule and show the refit. Compute LOD/LOQ from blank
   sample SD using the one frozen rule. Refuse LOQ outside supported validity.
   Report out-of-range unknowns without a concentration; never extrapolate.
4. **04-summary:** compare the submitted arithmetic record with recomputation.
   Return slope, intercept, R-squared, residual standard error, back-calculations,
   n per level before and after exclusions, all failed controls and negative
   results. A failed standard acceptance result is retained, never hidden.
5. **05-handoff:** register domain records as ordinary artifacts through
   `$science-provenance`, with separate existing claim-register entries. Send
   the freeze, input identities, deviations, residuals, failures, counts,
   dependencies, assumptions and limitations to coordinator-owned `$science-review`
   in record, source and method modes. This pack's review stays `unavailable`.

Execution is CPU-only and offline. Record Python version, code revision, command
and environment through existing provenance. Deterministic refusals get no
automatic retries. Preserve the failed attempt before correcting an identity
or making an interpretation-changing choice.

## Outputs

The read-only CLI prints `calibration-lod-result-v1`; the stages reference lists
all pack-local record schemas. It writes nothing. Include normalized assumptions,
input hashes, both fits, standard acceptance evidence, explicit exclusions,
blank count/mean/SD, limits, per-level n, bounded unknown results and limitations.
Evidence is `synthetic-arithmetic-only`, never a biological or clinical finding.

The coordinator's separate claim register retains supported, contradicted,
inconclusive and unavailable claim IDs, applicability, dependencies, conflicts,
rejected alternatives and falsifiers. Empty evidence requires `unavailable`;
any unavailable citation does too, even beside available records. Missing
records are unavailable, never negative evidence. The smallest next falsifiable
action is independent arithmetic reproduction or a source audit that could
change the admitted standard identities or acceptance result.

## Boundaries

Association never establishes causality. Computed agreement never establishes
physical or clinical validity. Review approval never establishes truth. The
validator enforces these as refusals, including clinical cut-offs, diagnostic
accuracy, regulatory validity and patient-level claims. One synthetic fixture
cannot establish replication; positive scientific statuses are refused.

The conservative English lexical claim filter is incomplete and refuses
negations too. Independent review must assess paraphrases, source authenticity,
historical freeze timing and applicability. Neither a fitted concentration nor
its arithmetic check establishes a sample's true concentration. No estimate
extends beyond the supplied standards or frozen validity range.

Stop on missing essential input, changed identity, failed numerical control or
interpretation-changing ambiguity. Do not overwrite failed controls or negative
results. No network, installation, restricted transfer, new host, GPU, remote or
heavy compute is included; any extension needs separate authorization. Admitted
offline stages require no repeated human gate. Rigor and independent review
remain with the coordinator; this pack cannot mark itself reviewed.
