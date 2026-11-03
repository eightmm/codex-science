---
name: hit-to-lead-optimization
description: "Optimize an existing hit series using generation or supplied candidates, assay-bound property constraints, existing docking/QSAR routes, Pareto and diversity-aware follow-up selection. Use for hit-to-lead prioritization; supplied-property analysis does not execute molecular engines."
license: MIT
---

# Hit-to-Lead Optimization

## Decision contract

Role: conductor and analyzer. Use one existing coordinator checkpoint and ordinary
hashed artifacts. Freeze the decision, input identities, controls, endpoint units,
source kind, thresholds and resource envelope before inspecting outcomes.

## Reference usage

Read [stages](references/stages.md) before analysis or interpretation. Load
[method discovery](references/method-discovery.md) and dated
[method seeds](references/methods.json) when selecting or adding a method.
Load [plan](references/plan.json) when initializing existing checkpoint steps.
Record hashes of references that materially govern execution or claims.

## Workflow

1. **intake:** Freeze target, seed/parent chemical identities, objective assay/unit/source-kind and prospective versus held-out purpose.
2. **plan:** Search current generator, property and docking methods; freeze constraints, scaffold/identity splits, controls and selection budget.
3. **pilot:** Check preparation and scoring on the smallest approved control batch before generation or optimization.
4. **generate:** Generate or import candidates; preserve ancestry, source methods, all failed attempts and chemical identity normalization.
5. **evaluate:** Compute or import endpoint-bound properties and matched control results; retain unavailable values.
6. **select:** Apply frozen constraints then cost/diversity-bounded Pareto selection through the existing next-experiment planner.
7. **review:** Register inputs, method identities, full funnel and selection; independently review and define the next falsifying assay.

## Outputs

Run `python3 <plugin-root>/scripts/analyze_hit_to_lead.py <input.json>` to produce
`hit-to-lead-result-v1`. The standalone helper works from another directory and returns
JSON errors for invalid inputs. The checked artificial example and expected
output are in `examples/hit-to-lead-optimization/`. Register the output, frozen input, complete
candidate inventory and method/control evidence with `$science-provenance`.
The analysis result is not a campaign completion or independent-review receipt.

## Execution and review

Use existing audited skills and approved compute routes for external engines;
this helper consumes supplied values and never installs, downloads or executes
models. Search current primary sources, freeze exact code/weight/database/config
identity, validate the smallest matched control and preserve failures and nulls.
Do not silently switch endpoints or substitute predicted values for measured ones.
Use `$science-review` for material computational claims and report the smallest
next discriminating measurement. Ordering, synthesis and external assay submission
are separate actions, not authorized by discovering this skill.

For resumable local stages and later measured-outcome import, follow the shared
[campaign execution and feedback guide](../../docs/CAMPAIGN_WORKFLOWS.md).
Keep each candidate and its construct/target identity when constructing the
separate feedback contract; never feed held-out outcomes into selection.

## Boundaries

Supplied-property ranking and declared-scaffold diversity only. No chemical validation, generator, docking, QSAR/ADMET calibration, measured affinity or synthesis assessment is established.
