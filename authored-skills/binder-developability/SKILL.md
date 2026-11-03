---
name: binder-developability
description: "Triage minibinder, antibody Fv and VHH candidates for sequence liabilities and matched on/off-target panels before selecting follow-up measurements. Compute chain-local sequence observations and supplied selectivity margins; route structure-dependent developability predictors explicitly."
license: MIT
---

# Binder Developability

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

1. **intake:** Freeze binder class, construct/chain sequences, target and protected framework/disulfide positions.
2. **plan:** Choose sequence/structure/assay analyses and freeze user-declared limits, matched panel endpoints and controls.
3. **pilot:** Validate chain and residue maps; check controls and optional external predictor compatibility.
4. **sequence:** Compute chain-local sequence observations without assigning uncalibrated developability probabilities.
5. **panel:** Evaluate complete construct-matched on/off-target response panels, retaining predicted versus measured source kind.
6. **select:** Apply explicit limits and control outcomes; retain all rejected and unavailable cases with reasons.
7. **review:** Review computational evidence and propose expression, aggregation or specificity measurements as appropriate.

## Outputs

Run `python3 <plugin-root>/scripts/analyze_binder_developability.py <input.json>` to produce
`binder-developability-result-v1`. The standalone helper works from another directory and returns
JSON errors for invalid inputs. The checked artificial example and expected
output are in `examples/binder-developability/`. Register the output, frozen input, complete
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

Use the shared [campaign execution and feedback guide](../../docs/CAMPAIGN_WORKFLOWS.md)
to capture actual runtime assets, run declared local stages and import later assay
outcomes. Preserve distinct binder construct and target construct identities;
the feedback input is a separate contract, not this pack's record renamed.

## Boundaries

Sequence observations and supplied matched-panel margins only; no TAP/TNP execution, aggregation/solubility/expression/immunogenicity predictor, antibody annotation, independent assay or clinical assessment.
