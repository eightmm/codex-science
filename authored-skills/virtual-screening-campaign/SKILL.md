---
name: virtual-screening-campaign
description: "Conduct a controlled virtual-screening campaign from target/library preparation through method discovery, redock controls, existing docking or rescoring engines, compound-level state/pose aggregation, labeled enrichment analysis and reviewed shortlist. Also analyze supplied score tables offline without claiming docking execution."
license: MIT
---

# Virtual Screening Campaign

## Decision contract

Role: conductor and analyzer. Freeze the target/assembly/state, library identities,
prediction unit (compound), permitted pocket information, score name/direction,
state/pose aggregation, split, label meaning and assay source, baseline, thresholds,
budget and controls before execution. Choose prospective prioritization or labeled
retrospective evaluation explicitly. Without valid activity labels, ranking remains
exploratory; no enrichment or affinity claim is available. Use one existing
coordinator checkpoint and ordinary manifest artifacts, not a new runtime backend.

## Reference usage

Read [stages](references/stages.md) before intake, aggregation or claims. Read
[method discovery](references/method-discovery.md) and dated
[seeds](references/methods.json) when selecting or adding methods. Load
[plan steps](references/plan.json) only to initialize the existing manifest plan.
Record reference hashes when they govern a material decision.

## Workflow

1. **intake:** inventory target, library, chemical identities, states, all planned
   attempts, label/assay provenance and source-to-prepared atom maps. Use
   `$cx-molecular-input-preparation`; stop on unresolved chemistry or pocket identity.
2. **plan:** search current primary sources, select a compatible existing executor
   and explicit scoring endpoint; freeze aggregation, direction, ties, compound
   grouping, evaluation split, thresholds, seeds and full-denominator control plan.
   Reuse `$cx-docking-validation`. Record the selected method descriptor and hashes.
3. **pilot:** obtain approval once for new installations/downloads, restricted data
   transfer/new hosts, GPU/remote/heavy compute and interpretation-changing choices.
   State exact pins, assets, resource caps and output path; do not re-ask unchanged
   approved scope. Run the smallest valid positive redock. Failed essential control
   blocks accepted conclusions; preserve it and diagnose within approved bounds.
4. **execute:** use `$cx-autodock-vina-docking`, `$cx-gnina-docking` or an explicitly
   admitted alternative. Supplied-score mode skips engine execution and says so.
   Preserve all attempts, raw poses/logs, states, score fields, failures and hashes.
5. **analyze:** run the stdlib `scripts/analyze_virtual_screening.py` helper on the
   pack-local JSON record described in stages. It aggregates supplied poses/states,
   preserves missing results, and computes AP/enrichment only from explicit labels.
   This helper does not execute an engine. Inspect matched controls, preparation/
   seed/aggregation sensitivity and applicable interactions with
   `$cx-plip-interaction-analysis`; missing analyses remain unavailable.
6. **select:** reconcile all denominators before reporting a shortlist. Keep tied
   score groups, failed controls, exclusions and zero survivors visible. Compare
   ranking against its constant-score baseline before making a qualified claim;
   do not tune thresholds after inspecting outcomes.
7. **review:** register input, frozen contract, commands, logs, tables and outputs
   with `$science-provenance`, then obtain independent `$science-review` in record
   and method modes as applicable. Resolve blocking findings and preserve the
   receipt; deliver a computational shortlist and smallest falsifiable next assay.

## Outputs

Produce `virtual-screening-analysis-v1`, a full compound/attempt table, metrics,
control outcomes, limitations and next action under `artifacts/<run-id>/`.
Register these as ordinary hashed artifacts with separately adjudicated claim
register entries. The helper's `accepted_analysis` is a narrow analysis result,
not an independent-review receipt or completed scientific campaign. Save the
method descriptor, preparation ledger, split/label provenance and failed attempts.

## Boundaries

Docking scores, CNN confidence, pose recovery and interaction counts do not establish
measured affinity, binding, mechanism or prospective efficacy. No-label results
remain exploratory; no-survivor results remain explicit. The offline fixture tests
real arithmetic and contract failures only, never molecular docking. Controls and
identity declarations need source review. Never order compounds, submit screening,
install tools or launch unapproved compute merely because this pack is discovered.
